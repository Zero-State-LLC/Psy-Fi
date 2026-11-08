"""Host power trace for browser captures (ADR 0011).

A browser cannot read GPU power, and it is scored after the fact, so there is no sampling window
for ``power.py`` to integrate. Instead the host runs ``psyfi-bench power-trace`` while the bench
page runs, and ``psyfi-bench ingest --power-trace`` pairs the trace with each stage's measured
window on the wall clock. It refuses rather than guesses: a trace from another host or GPU vendor,
a stage with no window, or a trace that does not reach the window writes no power and says why.
"""

from __future__ import annotations

import json
import math
import shutil
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from psyfi_bench.environment import hostname_hash
from psyfi_bench.power import (
    DERIVATION,
    STREAM_INTERVAL_S,
    NvidiaSmiStreamSampler,
    PowerSample,
    build_power_record,
    probe_gpu_name,
    probe_power_field,
)
from psyfi_bench.schemas import CaptureStage, EnvironmentRecord, PowerTrace, PowerTraceSample, StageRecord
from psyfi_bench.timing import utc_now_iso

TRACE_DERIVATION = (
    f"{DERIVATION}; paired after the run from a host power trace (psyfi-bench power-trace) against the browser's measured window "
    "on the wall clock (performance.timeOrigin + performance.now(), warm-up excluded): this is board power while the stage "
    "rendered, so it includes idle draw, the compositor and anything else on the GPU"
)


class PowerTraceUnavailable(RuntimeError):
    """This host cannot record a power trace; the message says why."""


def record_power_trace(
    *, stop: threading.Event, duration_s: float | None = None, interval_s: float = STREAM_INTERVAL_S, on_start: Callable[[str], None] | None = None,
) -> PowerTrace:
    """Sample GPU 0 until ``stop`` is set (or ``duration_s`` passes) and return the trace."""
    if shutil.which("nvidia-smi") is None:
        raise PowerTraceUnavailable("nvidia-smi is not on this host's PATH, so no power trace can be recorded")
    power_field = probe_power_field()
    if power_field is None:
        raise PowerTraceUnavailable("nvidia-smi reports no power reading for GPU 0 (vGPU slices and some boards do not expose board power)")
    gpu_name = probe_gpu_name()
    sampler = NvidiaSmiStreamSampler(power_field, interval_s=interval_s, clock="epoch")
    started_ns = time.time_ns()
    sampler.start()
    note = None
    try:
        if on_start is not None:
            on_start(f"recording {power_field} for GPU 0 ({gpu_name or 'name unknown'}) every {interval_s * 1000:g} ms; press Ctrl-C to stop")
        deadline = None if duration_s is None else time.monotonic() + duration_s
        while not stop.is_set():
            if deadline is not None and time.monotonic() >= deadline:
                break
            if not sampler.running():
                note = "nvidia-smi exited before the trace was stopped; the trace ends at its last sample"
                break
            stop.wait(0.05)
    finally:
        samples = sampler.stop()
    return PowerTrace(
        created_at=utc_now_iso(),
        source=sampler.name,
        query=sampler.query,
        interval_s=interval_s,
        gpu_name=gpu_name,
        gpu_vendor="nvidia",
        hostname_hash=hostname_hash(),
        started_epoch_s=started_ns / 1e9,
        stopped_epoch_s=time.time_ns() / 1e9,
        samples=[PowerTraceSample(t_epoch_s=s.t_s, power_w=s.power_w, temperature_c=s.temperature_c, sm_clock_mhz=s.sm_clock_mhz) for s in samples],
        note=note,
    )


def write_power_trace(trace: PowerTrace, path: str | Path) -> None:
    # Compact: a long bench session holds tens of thousands of samples.
    Path(path).write_text(json.dumps(trace.model_dump(by_alias=True), separators=(",", ":")) + "\n", encoding="utf-8")


def load_power_trace(source: str | Path | dict[str, Any] | PowerTrace) -> PowerTrace:
    if isinstance(source, PowerTrace):
        return source
    if isinstance(source, dict):
        return PowerTrace.model_validate(source)
    return PowerTrace.model_validate(json.loads(Path(source).read_text(encoding="utf-8")))


def _trace_refusal(trace: PowerTrace, *, scoring_hostname_hash: str | None, adapter_vendor: str) -> str | None:
    """Why this trace cannot be paired with this capture on this host; None when it can."""
    if not trace.hostname_hash or not scoring_hostname_hash:
        return "cannot tell that the power trace came from the scoring host: a hostname_hash is missing"
    if trace.hostname_hash != scoring_hostname_hash:
        return f"power trace hostname_hash {trace.hostname_hash} differs from the scoring host's {scoring_hostname_hash}; a trace must be recorded on the host that scores it"
    trace_vendor = trace.gpu_vendor.strip().lower()
    if adapter_vendor == "unknown":
        return f"the capture's adapter vendor is unknown, so it cannot be matched to the power trace's GPU ({trace_vendor})"
    if trace_vendor != adapter_vendor:
        return f"power trace GPU vendor {trace_vendor} is not the capture adapter's vendor {adapter_vendor}"
    return None


def _power_samples(trace: PowerTrace) -> list[PowerSample]:
    """The trace as samples on one clock (Unix epoch seconds), in time order; a non-finite reading counts as no reading."""
    out = [
        PowerSample(
            t_s=s.t_epoch_s,
            power_w=s.power_w if s.power_w is not None and math.isfinite(s.power_w) else None,
            temperature_c=s.temperature_c,
            sm_clock_mhz=s.sm_clock_mhz,
        )
        for s in trace.samples
        if math.isfinite(s.t_epoch_s)
    ]
    out.sort(key=lambda s: s.t_s)
    return out


def _pair_stage(cs: CaptureStage, stage: StageRecord, trace: PowerTrace, samples: list[PowerSample]) -> str | None:
    """Write ``stage.power`` from the trace, or return why it cannot be."""
    if stage.status != "ok":
        return "the stage did not complete, so no power is reported for it"
    if cs.window_epoch_ms is None:
        return "this stage has no window_epoch_ms (a capture from before ADR 0011), so there is nothing to line the trace up against"
    start_s, end_s = cs.window_epoch_ms[0] / 1000.0, cs.window_epoch_ms[1] / 1000.0
    if not (math.isfinite(start_s) and math.isfinite(end_s) and end_s > start_s):
        return f"this stage's window_epoch_ms {list(cs.window_epoch_ms)} is not a finite, increasing range"
    powered = [s for s in samples if s.power_w is not None]
    if not powered:
        return "the power trace has no samples with a power reading"
    if not any(start_s <= s.t_s <= end_s for s in powered):
        return f"the power trace (epoch {powered[0].t_s:.3f} to {powered[-1].t_s:.3f} s) does not reach this stage's window ({start_s:.3f} to {end_s:.3f} s)"
    stage.power = build_power_record(
        samples, source=trace.source, query=trace.query, interval_s=trace.interval_s,
        window_s=end_s - start_s, window_start_s=start_s, work_unit="frame", work_units=float(stage.metrics["frames"]),
    ).model_copy(update={"derivation": TRACE_DERIVATION})
    stage.metrics["power_window_epoch_ms"] = list(cs.window_epoch_ms)
    return None


def apply_power_trace(
    trace: PowerTrace, capture_stages: Sequence[CaptureStage], stages: Sequence[StageRecord], env: EnvironmentRecord, *, adapter_vendor: str,
) -> dict[str, Any]:
    """Pair ``trace`` with each capture stage. A stage it cannot support gets ``metrics.power_unavailable`` instead.

    ``stages`` holds one record per capture stage, in order. Returns the summary for the result metrics.
    """
    refusal = _trace_refusal(trace, scoring_hostname_hash=env.hostname_hash, adapter_vendor=adapter_vendor)
    samples = _power_samples(trace)
    reasons: list[str] = []
    for cs, stage in zip(capture_stages, stages):
        reason = refusal or _pair_stage(cs, stage, trace, samples)
        if reason:
            stage.metrics["power_unavailable"] = reason
            reasons.append(reason)
    with_power = [s for s in stages[: len(capture_stages)] if s.power is not None]
    if with_power:
        env.unavailable.pop("power", None)
        env.power = {"source": trace.source, "query": trace.query, "interval_s": trace.interval_s, "gpu_name": trace.gpu_name, "paired_from": "host power trace (ADR 0011)"}
    elif reasons:
        env.unavailable["power"] = f"power trace supplied but not paired with any stage: {reasons[0]}"
    return {
        "source": trace.source,
        "query": trace.query,
        "gpu_name": trace.gpu_name,
        "sample_count": len(samples),
        "stages_with_power": len(with_power),
        "stages_with_energy_per_frame": sum(1 for s in with_power if s.power.energy_j_per_work_unit is not None),  # type: ignore[union-attr]
        "stages_refused": len(reasons),
        "refused": refusal,
    }
