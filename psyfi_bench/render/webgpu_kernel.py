"""Score the browser WGSL Kuramoto kernel validation (stage kind ``webgpu_kernel``).

Status rules (Python is the judge; the browser's own ``passed`` is informational):

* ``skipped`` — the browser reported WebGPU compute unsupported (explicit reason, no number).
* ``failed``  — the kernel errored, the fixture hash differs from the committed fixture, the
  output had non-finite values, or max abs error exceeds ``KERNEL_TOLERANCE``.
* ``ok``      — max abs error within ``KERNEL_TOLERANCE``.

Per-dispatch time is labelled by its source: ``timestamp-query`` is GPU pass time, ``wall`` is
submit to ``onSubmittedWorkDone`` and is never reported as GPU time. CPU simulation stays the
authority; nothing here feeds the GPU field anywhere.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from psyfi_bench.schemas import CaptureKernel, StageRecord
from psyfi_bench.stats import summarize

KERNEL_STAGE_KIND = "webgpu_kernel"


def _committed_fixture() -> dict[str, Any] | None:
    from psyfi_bench.compute.kuramoto_fixture import FIXTURE_PATH, load_committed_fixture

    if not FIXTURE_PATH.exists():
        return None
    return load_committed_fixture()


def score_kernel(k: CaptureKernel, *, measurement_class: str = "measured", resamples: int = 1000, seed: int = 0, fixture: dict[str, Any] | None = None) -> StageRecord:
    from psyfi_bench.compute.kuramoto_fixture import KERNEL_TOLERANCE

    fixture = fixture if fixture is not None else _committed_fixture()
    stage = StageRecord(
        id=k.id,
        kind=KERNEL_STAGE_KIND,
        measurement_class=measurement_class,  # type: ignore[arg-type]
        params={"kernel": k.kernel, "fixture_id": k.fixture_id, "width": k.width, "height": k.height, "steps": k.steps, "execution_class": "webgpu"},
    )
    tol = float(KERNEL_TOLERANCE)
    stage.metrics.update(
        {
            "tolerance": tol,
            "browser_tolerance": k.tolerance,
            "browser_passed": k.passed,
            "authority": "numpy evolve_consciousness_omega (CPU); the GPU field is compared, never used",
        }
    )
    if k.adapter:
        stage.metrics["adapter"] = k.adapter
    if k.note:
        stage.metrics["note"] = k.note

    if k.status == "unsupported":
        stage.status = "skipped"
        stage.error = f"unsupported: {k.unsupported_reason or 'WebGPU compute unavailable'}"
        return stage
    if k.status == "error":
        stage.status = "failed"
        stage.error = f"RuntimeError: kernel failed in the browser: {k.error or 'unknown error'}"
        return stage

    if fixture is not None:
        stage.metrics["fixture_hash"] = fixture.get("content_hash")
        if k.fixture_hash != fixture.get("content_hash") or k.fixture_id != fixture.get("id"):
            stage.status = "failed"
            stage.error = f"ValueError: capture ran fixture {k.fixture_id}@{k.fixture_hash}, committed fixture is {fixture.get('id')}@{fixture.get('content_hash')}"
            return stage

    # Timing first so a failed numeric check still shows what was measured.
    wall = [float(v) for v in k.wall_dispatch_ms if math.isfinite(v) and v >= 0]
    stage.wall_ms = wall
    stage.metrics["timing_source"] = k.timing_source
    disp = [float(v) for v in k.dispatch_ms if math.isfinite(v) and v >= 0]
    if disp:
        key = "gpu_dispatch_ms" if k.timing_source == "timestamp-query" else "wall_dispatch_ms"
        stage.metrics[f"{key}_p50"] = float(np.percentile(disp, 50))
        stage.metrics[f"{key}_mean"] = float(np.mean(disp))
        stage.metrics["dispatches"] = len(disp)
        if len(disp) >= 2:
            stage.statistics[key] = summarize(disp, unit="ms", resamples=resamples, seed=seed)
    if k.timing_source != "timestamp-query":
        stage.metrics["gpu_ms_unavailable"] = "timestamp-query not exposed; per-dispatch time is wall time (submit to onSubmittedWorkDone), not GPU time"
    if k.warmup_runs:
        stage.metrics["warmup_runs"] = k.warmup_runs

    err = k.max_abs_error
    stage.metrics["max_abs_error"] = err if err is not None and math.isfinite(err) else None
    stage.metrics["nonfinite_count"] = k.nonfinite_count
    if err is None or not math.isfinite(err) or (k.nonfinite_count or 0) > 0:
        stage.status = "failed"
        stage.error = f"ValueError: kernel output is non-finite ({k.nonfinite_count or 'unknown'} non-finite values; max_abs_error={err})"
        return stage
    stage.metrics["passed"] = bool(err <= tol)
    if k.passed is not None and k.passed != stage.metrics["passed"]:
        stage.metrics["warning"] = f"browser verdict passed={k.passed} disagrees with Python at tolerance {tol}"
    if err > tol:
        stage.status = "failed"
        stage.error = f"ValueError: max abs error {err:.3g} exceeds declared tolerance {tol:g}"
    return stage


def score_kernels(kernels: list[CaptureKernel], *, measurement_class: str = "measured", resamples: int = 1000, seed: int = 0) -> list[StageRecord]:
    if not kernels:
        return []
    fixture = _committed_fixture()
    return [score_kernel(k, measurement_class=measurement_class, resamples=resamples, seed=seed, fixture=fixture) for k in kernels]


def kernel_summary(stages: list[StageRecord]) -> dict[str, Any] | None:
    rows = [s for s in stages if s.kind == KERNEL_STAGE_KIND]
    if not rows:
        return None
    return {
        s.id: {
            "status": s.status,
            "max_abs_error": s.metrics.get("max_abs_error"),
            "tolerance": s.metrics.get("tolerance"),
            "timing_source": s.metrics.get("timing_source"),
            "dispatch_ms_p50": s.metrics.get("gpu_dispatch_ms_p50", s.metrics.get("wall_dispatch_ms_p50")),
            "error": s.error,
        }
        for s in rows
    }
