"""Power sampling during a stage (``nvidia-smi``), reported as measured evidence only.

The sampler is injectable: tests pass a fake, CI has no GPU. When ``nvidia-smi`` is absent
``make_power_sampler`` returns ``None`` and no power field is written anywhere; the environment
keeps its ``unavailable.power`` reason. Energy comes only from the samples taken: trapezoid
integration between the first and last sample, no extrapolation, no interpolation across gaps.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from psyfi_bench.schemas import PowerRecord

NVIDIA_SMI_QUERY = "power.draw,temperature.gpu,clocks.sm"
DERIVATION = (
    "energy_j = trapezoid integral of sampled power.draw (W) over sample timestamps, from the first to the last "
    "sample (no extrapolation to the stage edges); per-unit energy = energy_j / work units completed in the "
    "sampled loop; samples are nvidia-smi readings of GPU index 0 (board power, whichever backend ran the stage)"
)


@dataclass(frozen=True)
class PowerSample:
    t_s: float  # monotonic seconds
    power_w: float | None
    temperature_c: float | None = None
    sm_clock_mhz: float | None = None


class PowerSampler(Protocol):
    """``start()`` begins sampling; ``stop()`` ends it and returns every sample taken."""

    name: str
    interval_s: float

    def start(self) -> None: ...

    def stop(self) -> list[PowerSample]: ...


def _num(raw: str) -> float | None:
    try:
        return float(raw.strip())
    except ValueError:  # "[N/A]", "[Not Supported]"
        return None


def read_nvidia_smi() -> PowerSample | None:
    """One ``nvidia-smi`` reading of GPU 0, or None when the call fails."""
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={NVIDIA_SMI_QUERY}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5.0, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    t = time.perf_counter()
    if out.returncode != 0 or not out.stdout.strip():
        return None
    parts = out.stdout.strip().splitlines()[0].split(",")
    if len(parts) < 3:
        return None
    return PowerSample(t_s=t, power_w=_num(parts[0]), temperature_c=_num(parts[1]), sm_clock_mhz=_num(parts[2]))


class ThreadedSampler:
    """Polls ``read`` on a daemon thread every ``interval_s`` until ``stop()``."""

    def __init__(self, read: Callable[[], PowerSample | None], *, name: str = "nvidia-smi", interval_s: float = 0.2) -> None:
        self._read = read
        self.name = name
        self.interval_s = interval_s
        self._samples: list[PowerSample] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            s = self._read()
            if s is not None:
                self._samples.append(s)
            self._stop.wait(self.interval_s)

    def start(self) -> None:
        self._samples = []
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="psyfi-bench-power", daemon=True)
        self._thread.start()

    def stop(self) -> list[PowerSample]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None
        return list(self._samples)


def make_power_sampler() -> PowerSampler | None:
    """A live ``nvidia-smi`` sampler, or None when the tool is absent or does not answer."""
    if shutil.which("nvidia-smi") is None or read_nvidia_smi() is None:
        return None
    return ThreadedSampler(read_nvidia_smi)


def _trapezoid_j(samples: list[PowerSample]) -> float | None:
    pts = [s for s in samples if s.power_w is not None]
    if len(pts) < 2:
        return None
    return sum((b.t_s - a.t_s) * (a.power_w + b.power_w) / 2.0 for a, b in zip(pts, pts[1:]))  # type: ignore[operator]


def build_power_record(
    samples: list[PowerSample], *, source: str, interval_s: float, window_s: float,
    work_unit: str | None = None, work_units: float | None = None,
) -> PowerRecord:
    """Summarize samples. Fields that the samples cannot support stay None with a reason."""
    watts = [s.power_w for s in samples if s.power_w is not None]
    temps = [s.temperature_c for s in samples if s.temperature_c is not None]
    clocks = [s.sm_clock_mhz for s in samples if s.sm_clock_mhz is not None]
    energy = _trapezoid_j(samples)
    span = (samples[-1].t_s - samples[0].t_s) if len(samples) >= 2 else 0.0
    reason = None
    if energy is None:
        reason = f"fewer than 2 power samples ({len(watts)}) in a {window_s:.3f}s window; energy not reported"
    per_unit = None
    if energy is not None and work_units:
        per_unit = energy / work_units
    return PowerRecord(
        source=source, query=NVIDIA_SMI_QUERY, interval_s=interval_s, sample_count=len(samples),
        window_s=window_s, sampled_span_s=span,
        power_w_mean=(sum(watts) / len(watts)) if watts else None, power_w_max=max(watts) if watts else None,
        temperature_c_max=max(temps) if temps else None,
        sm_clock_mhz_mean=(sum(clocks) / len(clocks)) if clocks else None, sm_clock_mhz_max=max(clocks) if clocks else None,
        energy_j=energy, work_unit=work_unit, work_units=work_units, energy_j_per_work_unit=per_unit,
        derivation=DERIVATION, unavailable_reason=reason,
    )
