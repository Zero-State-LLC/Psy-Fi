"""Hardware, software, and provenance detection. Missing telemetry is reported, never estimated."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from psyfi_bench import BENCH_VERSION
from psyfi_bench.schemas import EnvironmentRecord, GpuRecord
from psyfi_bench.timing import utc_now_iso

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], timeout: float = 5.0) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def _sysctl(key: str) -> str | None:
    return _run(["sysctl", "-n", key], timeout=3.0)


def cpu_info(unavailable: dict[str, str]) -> dict[str, Any]:
    system = platform.system()
    info: dict[str, Any] = {
        "brand": None,
        "architecture": platform.machine(),
        "logical_cores": os.cpu_count(),
        "physical_cores": None,
    }
    if system == "Darwin":
        info["brand"] = _sysctl("machdep.cpu.brand_string")
        phys = _sysctl("hw.physicalcpu")
        info["physical_cores"] = int(phys) if phys and phys.isdigit() else None
        perf = _sysctl("hw.perflevel0.physicalcpu")
        eff = _sysctl("hw.perflevel1.physicalcpu")
        if perf and perf.isdigit():
            info["performance_cores"] = int(perf)
        if eff and eff.isdigit():
            info["efficiency_cores"] = int(eff)
    elif system == "Linux":
        try:
            text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if line.lower().startswith("model name"):
                    info["brand"] = line.split(":", 1)[1].strip()
                    break
            cores = {
                line.split(":", 1)[1].strip()
                for line in text.splitlines()
                if line.lower().startswith("core id")
            }
            info["physical_cores"] = len(cores) or None
        except OSError as exc:
            unavailable["cpu.brand"] = f"/proc/cpuinfo unreadable: {exc}"
    else:
        info["brand"] = platform.processor() or None
    if not info["brand"]:
        unavailable.setdefault("cpu.brand", "no CPU brand string on this platform")
    return info


def memory_info(unavailable: dict[str, str]) -> dict[str, Any]:
    system = platform.system()
    total: int | None = None
    if system == "Darwin":
        raw = _sysctl("hw.memsize")
        total = int(raw) if raw and raw.isdigit() else None
    elif system == "Linux":
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1]) * 1024
                    break
        except OSError:
            total = None
    if total is None:
        try:
            total = int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))  # type: ignore[attr-defined]
        except (ValueError, OSError, AttributeError):
            unavailable["memory.total"] = "no memory size API on this platform"
    return {"total_bytes": total}


def _nvidia_gpus(unavailable: dict[str, str]) -> list[GpuRecord]:
    out = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ],
        timeout=5.0,
    )
    if out is None:
        return []
    gpus: list[GpuRecord] = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        mem = None
        try:
            mem = int(float(parts[1])) * 1024 * 1024
        except ValueError:
            unavailable["gpu.memory"] = f"nvidia-smi memory.total unparsable: {parts[1]!r}"
        gpus.append(
            GpuRecord(vendor="nvidia", name=parts[0], memory_bytes=mem, driver=parts[2], source="nvidia-smi", hardware_class="discrete")
        )
    return gpus


def _rocm_gpus() -> list[GpuRecord]:
    out = _run(["rocm-smi", "--showproductname", "--json"], timeout=5.0)
    if not out:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    gpus: list[GpuRecord] = []
    for card, fields in data.items():
        if not isinstance(fields, dict):
            continue
        name = fields.get("Card series") or fields.get("Card SKU") or card
        gpus.append(GpuRecord(vendor="amd", name=str(name), source="rocm-smi", hardware_class="discrete"))
    return gpus


def _apple_gpus(unavailable: dict[str, str]) -> list[GpuRecord]:
    out = _run(["system_profiler", "SPDisplaysDataType", "-json"], timeout=15.0)
    if not out:
        unavailable["gpu.apple"] = "system_profiler unavailable or timed out"
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        unavailable["gpu.apple"] = "system_profiler returned non-JSON"
        return []
    gpus: list[GpuRecord] = []
    for entry in data.get("SPDisplaysDataType", []):
        name = entry.get("sppci_model") or entry.get("_name") or "Apple GPU"
        cores = entry.get("sppci_cores")
        vendor_raw = str(entry.get("spdisplays_vendor") or "").lower()
        vendor = "apple" if "apple" in vendor_raw or "apple" in str(name).lower() else (vendor_raw or "unknown")
        bus = str(entry.get("sppci_bus") or "").lower()
        hw_class = "integrated" if "builtin" in bus or vendor == "apple" else "unknown"
        gpus.append(
            GpuRecord(
                vendor=vendor,
                name=str(name),
                cores=int(cores) if isinstance(cores, str) and cores.isdigit() else None,
                memory_bytes=None,
                driver=str(entry.get("spdisplays_metal") or "") or None,
                source="system_profiler",
                hardware_class=hw_class,
            )
        )
    if gpus and all(g.memory_bytes is None for g in gpus):
        unavailable["gpu.memory"] = "Apple unified memory: GPU memory is shared with system RAM"
    return gpus


def torch_accelerators() -> dict[str, Any]:
    """Optional accelerator availability via torch (never required)."""
    try:
        import torch  # type: ignore
    except Exception:  # noqa: BLE001
        return {"torch": None}
    info: dict[str, Any] = {"torch": torch.__version__, "cuda": False, "mps": False, "devices": []}
    try:
        if torch.cuda.is_available():
            info["cuda"] = True
            info["devices"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
            info["mps"] = True
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)
    return info


def gpu_info(unavailable: dict[str, str]) -> list[GpuRecord]:
    gpus = _nvidia_gpus(unavailable)
    gpus += _rocm_gpus()
    if platform.system() == "Darwin":
        gpus += _apple_gpus(unavailable)
    if not gpus:
        unavailable.setdefault("gpu", "no GPU inventory tool answered (nvidia-smi, rocm-smi, system_profiler)")
    return gpus


def software_info() -> dict[str, Any]:
    import numpy as np

    info: dict[str, Any] = {
        "python": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "numpy": np.__version__,
        "bench_version": BENCH_VERSION,
    }
    try:
        import scipy  # type: ignore

        info["scipy"] = scipy.__version__
    except Exception:  # noqa: BLE001
        info["scipy"] = None
    try:
        from psyfi_core.version import __version__ as psyfi_version

        info["psyfi_version"] = psyfi_version
    except Exception:  # noqa: BLE001
        info["psyfi_version"] = None
    try:
        cfg = np.show_config(mode="dicts")  # type: ignore[call-arg]
        blas = (cfg.get("Build Dependencies") or {}).get("blas") or {}
        info["blas"] = {k: blas.get(k) for k in ("name", "version") if k in blas}
    except Exception:  # noqa: BLE001
        info["blas"] = None
    info["env_threads"] = {
        k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS") if os.environ.get(k)
    }
    return info


def git_info(root: Path = REPO_ROOT) -> tuple[str | None, bool | None]:
    if shutil.which("git") is None or not (root / ".git").exists():
        return None, None
    commit = _run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=5.0)
    porcelain = _run(["git", "-C", str(root), "status", "--porcelain"], timeout=5.0)
    dirty = None if porcelain is None else bool(porcelain.strip())
    return commit, dirty


def classify_hardware(gpus: list[GpuRecord]) -> str:
    if any(g.hardware_class == "discrete" for g in gpus):
        return "discrete"
    if any(g.hardware_class == "integrated" for g in gpus):
        return "integrated"
    return "cpu_only" if not gpus else "unknown"


def collect_environment(*, include_gpu: bool = True) -> EnvironmentRecord:
    unavailable: dict[str, str] = {}
    gpus = gpu_info(unavailable) if include_gpu else []
    accel = torch_accelerators()
    software = software_info()
    software["accelerators"] = accel
    commit, dirty = git_info()
    software["git_commit"] = commit
    software["git_dirty"] = dirty
    unavailable.setdefault("power", "no power sampler on this host (nvidia-smi absent or not sampled)")
    unavailable.setdefault("thermal", "no thermal sensor API without elevated privileges")
    try:
        host_hash = hashlib.sha256(socket.gethostname().encode()).hexdigest()[:12]
    except OSError:
        host_hash = None
    return EnvironmentRecord(
        captured_at=utc_now_iso(),
        hostname_hash=host_hash,
        platform={
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version()[:120],
            "machine": platform.machine(),
        },
        cpu=cpu_info(unavailable),
        memory=memory_info(unavailable),
        gpus=gpus,
        software=software,
        hardware_class=classify_hardware(gpus),  # type: ignore[arg-type]
        unavailable=unavailable,
    )
