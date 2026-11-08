"""Power sampling during a stage (``nvidia-smi``), reported as measured evidence only.

The sampler is injectable: tests pass a fake, CI has no GPU. When ``nvidia-smi`` is absent
``make_power_sampler`` returns ``None`` and no power field is written anywhere; the environment
keeps its ``unavailable.power`` reason. Energy comes only from the samples taken: trapezoid
integration between the first and last sample, no extrapolation, no interpolation across gaps.

On Ampere and newer GPUs, ``power.draw`` is the average over the last second, and the board
sensor updates about every 100 ms (Yang et al., "Part-time Power Measurements: nvidia-smi's Lack
of Attention", arXiv:2312.02741). So the live sampler reads ``power.draw.instant`` where the
driver has it, runs one ``nvidia-smi -lms 100`` process instead of spawning one per sample, and
stamps each reading with nvidia-smi's own timestamp. Per-unit energy needs a stage of at least
one second.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import datetime
from dataclasses import dataclass
from typing import Protocol

from psyfi_bench.schemas import PowerRecord

# Preferred first: power.draw is a 1 s average on Ampere and newer; power.draw.instant is not.
POWER_FIELDS = ("power.draw.instant", "power.draw")
OTHER_FIELDS = "temperature.gpu,clocks.sm"
NVIDIA_SMI_QUERY = f"power.draw,{OTHER_FIELDS}"  # the query when no live sampler says otherwise
STREAM_INTERVAL_S = 0.1  # about the board sensor's update period
DERIVATION = (
    "energy_j = trapezoid integral of sampled board power (W) over the samples taken inside the measured window that "
    "carry a power reading, from the first to the last of them (no extrapolation to the stage edges; readings after "
    "the stage are dropped); per-unit energy = energy_j / work units completed in the window, reported only for a "
    "window of at least 1 s whose samples span at least 90% of it; samples are nvidia-smi readings of GPU index 0, "
    "power.draw.instant where the driver has it, else power.draw (a 1 s average on Ampere and newer), whichever "
    "backend ran the stage; the sensor itself sees part of each update period (arXiv:2312.02741)"
)
MIN_SPAN_COVERAGE = 0.9
MIN_WINDOW_S = 1.0


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


def _query_for(power_field: str) -> str:
    return f"timestamp,{power_field},{OTHER_FIELDS}"


def probe_power_field() -> str | None:
    """The first power field in ``POWER_FIELDS`` that nvidia-smi answers with a number for GPU 0."""
    for field in POWER_FIELDS:
        try:
            out = subprocess.run(
                ["nvidia-smi", "-i", "0", f"--query-gpu={field}", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5.0, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        lines = out.stdout.strip().splitlines()
        if out.returncode == 0 and lines and _num(lines[0]) is not None:
            return field
    return None


def parse_stream_line(line: str, clock_offset_s: float) -> PowerSample | None:
    """One ``timestamp, power, temperature, sm clock`` line, stamped on the runner's clock.

    nvidia-smi's timestamp is local wall time with milliseconds; ``clock_offset_s`` is
    ``perf_counter() - time.time()`` taken when sampling started.
    """
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 4:
        return None
    try:
        wall = datetime.strptime(parts[0], "%Y/%m/%d %H:%M:%S.%f").timestamp()
    except ValueError:
        return None
    return PowerSample(
        t_s=wall + clock_offset_s, power_w=_num(parts[1]), temperature_c=_num(parts[2]), sm_clock_mhz=_num(parts[3]),
    )


class NvidiaSmiStreamSampler:
    """One ``nvidia-smi -lms`` process for the whole stage; a reader thread keeps its lines."""

    name = "nvidia-smi"

    def __init__(self, power_field: str, *, interval_s: float = STREAM_INTERVAL_S) -> None:
        self.power_field = power_field
        self.query = _query_for(power_field)
        self.interval_s = interval_s
        self._samples: list[PowerSample] = []
        self._proc: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None

    def _read(self, proc: subprocess.Popen[str], offset: float) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            sample = parse_stream_line(line, offset)
            if sample is not None:
                self._samples.append(sample)

    def start(self) -> None:
        self._samples = []
        offset = time.perf_counter() - time.time()
        self._proc = subprocess.Popen(
            ["nvidia-smi", "-i", "0", f"--query-gpu={self.query}", "--format=csv,noheader,nounits",
             "-lms", str(max(1, round(self.interval_s * 1000)))],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        self._thread = threading.Thread(target=self._read, args=(self._proc, offset), name="psyfi-bench-power", daemon=True)
        self._thread.start()

    def stop(self) -> list[PowerSample]:
        """End the nvidia-smi process and return its readings. Safe to call twice."""
        proc, self._proc = self._proc, None
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5.0)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        return list(self._samples)


class ThreadedSampler:
    """Polls ``read`` on a daemon thread every ``interval_s`` until ``stop()`` (for injected readers)."""

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
        """End sampling and return the readings. Safe to call twice."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None
        return list(self._samples)


def make_power_sampler() -> PowerSampler | None:
    """A live ``nvidia-smi`` stream sampler, or None when the tool is absent or reports no power."""
    if shutil.which("nvidia-smi") is None:
        return None
    field = probe_power_field()
    return NvidiaSmiStreamSampler(field) if field else None


def _trapezoid_j(samples: list[PowerSample]) -> float | None:
    pts = [s for s in samples if s.power_w is not None]
    if len(pts) < 2:
        return None
    return sum((b.t_s - a.t_s) * (a.power_w + b.power_w) / 2.0 for a, b in zip(pts, pts[1:]))  # type: ignore[operator]


def build_power_record(
    samples: list[PowerSample], *, source: str, interval_s: float, window_s: float,
    window_start_s: float | None = None, work_unit: str | None = None, work_units: float | None = None,
    query: str = NVIDIA_SMI_QUERY,
) -> PowerRecord:
    """Summarize samples. Fields that the samples cannot support stay None with a reason.

    With ``window_start_s`` (same clock as the sample timestamps), only samples inside
    ``[window_start_s, window_start_s + window_s]`` count: a reading that lands after the stage,
    such as the one in flight when the sampler stops, is not evidence about the stage.
    """
    if window_start_s is not None:
        end = window_start_s + window_s
        samples = [s for s in samples if window_start_s <= s.t_s <= end]
    watts = [s.power_w for s in samples if s.power_w is not None]
    temps = [s.temperature_c for s in samples if s.temperature_c is not None]
    clocks = [s.sm_clock_mhz for s in samples if s.sm_clock_mhz is not None]
    energy = _trapezoid_j(samples)
    # The span that energy is integrated over: power readings only, so a sample with just a
    # temperature or clock cannot stretch the coverage.
    powered = [s for s in samples if s.power_w is not None]
    span = (powered[-1].t_s - powered[0].t_s) if len(powered) >= 2 else 0.0
    reason = None
    if energy is None:
        reason = f"fewer than 2 power samples ({len(watts)}) in a {window_s:.3f}s window; energy not reported"
    per_unit = None
    if energy is not None and work_units:
        coverage = span / window_s if window_s > 0 else 0.0
        if window_s < MIN_WINDOW_S:
            reason = (
                f"stage window {window_s:.3f}s is shorter than {MIN_WINDOW_S:g} s; the board sensor updates about "
                "every 100 ms, so per-unit energy is not reported"
            )
        elif coverage >= MIN_SPAN_COVERAGE:
            per_unit = energy / work_units
        else:
            # The work ran over the whole window but the energy only over the sampled span.
            reason = (
                f"samples span {span:.3f}s of a {window_s:.3f}s window ({coverage:.0%}, under "
                f"{MIN_SPAN_COVERAGE:.0%}); per-unit energy not reported"
            )
    return PowerRecord(
        source=source, query=query, interval_s=interval_s, sample_count=len(samples),
        window_s=window_s, sampled_span_s=span,
        power_w_mean=(sum(watts) / len(watts)) if watts else None, power_w_max=max(watts) if watts else None,
        temperature_c_max=max(temps) if temps else None,
        sm_clock_mhz_mean=(sum(clocks) / len(clocks)) if clocks else None, sm_clock_mhz_max=max(clocks) if clocks else None,
        energy_j=energy, work_unit=work_unit, work_units=work_units, energy_j_per_work_unit=per_unit,
        derivation=DERIVATION, unavailable_reason=reason,
    )
