"""Browser WGSL Kuramoto kernel: the reference fixture cannot rot, and Python scores the stage kind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from psyfi_bench.compute.kuramoto_fixture import (
    FIXTURE_PATH,
    KERNEL_TOLERANCE,
    REGENERATION_ATOL,
    build_kuramoto_fixture,
    fixture_text,
    load_committed_fixture,
    reference_params,
)
from psyfi_bench.families.render import load_capture
from psyfi_bench.registry import load_manifest
from psyfi_bench.render.webgpu_kernel import KERNEL_STAGE_KIND
from psyfi_bench.runner import RunContext, run_workload
from psyfi_bench.schemas import GpuCapture, stable_hash
from psyfi_bench.timing import utc_now_iso
from psyfi_core.engines import evolve_consciousness_omega

PLANES = ("initial", "evolved")


def _field(doc: dict[str, Any], key: str) -> np.ndarray:
    h, w = doc["height"], doc["width"]
    return (np.asarray(doc[key]["re"], np.float32) + 1j * np.asarray(doc[key]["im"], np.float32)).reshape(h, w).astype(np.complex64)


def test_committed_fixture_matches_a_fresh_regeneration() -> None:
    committed = load_committed_fixture()
    fresh = build_kuramoto_fixture()
    meta = lambda d: {k: v for k, v in d.items() if k not in (*PLANES, "content_hash")}  # noqa: E731
    assert meta(committed) == meta(fresh), "fixture metadata drifted: run `python -m psyfi_bench.compute.kuramoto_fixture`"
    for key in PLANES:
        for part in ("re", "im"):
            err = float(np.max(np.abs(np.asarray(committed[key][part]) - np.asarray(fresh[key][part]))))
            assert err <= REGENERATION_ATOL, f"{key}.{part} drifted by {err:g} (> {REGENERATION_ATOL:g})"
    assert committed["content_hash"] == stable_hash({k: committed[k] for k in PLANES}), "content_hash does not cover the committed planes"
    assert committed["tolerance"]["max_abs_error"] == KERNEL_TOLERANCE
    assert (committed["width"], committed["height"], committed["seed"], committed["steps"]) == (32, 32, 1337, 10)
    # The file is the canonical text rendering of its own document (written by write_fixture).
    assert FIXTURE_PATH.read_text(encoding="utf-8") == fixture_text(committed)


def test_evolved_plane_is_numpy_evolution_of_the_initial_plane() -> None:
    doc = load_committed_fixture()
    evolved = evolve_consciousness_omega(_field(doc, "initial"), reference_params(), None)
    assert float(np.max(np.abs(evolved - _field(doc, "evolved")))) <= REGENERATION_ATOL


def test_tolerance_discriminates_formula_slips() -> None:
    """A wrong dt or a summed (not averaged) coupling must move the field far past the tolerance."""
    doc = load_committed_fixture()
    init, ref = _field(doc, "initial"), _field(doc, "evolved")
    params = reference_params()
    for update in ({"dt": params.dt * 1.1}, {"coupling_strength": params.coupling_strength * 1.1}, {"steps": params.steps - 1}):
        wrong = evolve_consciousness_omega(init, params.model_copy(update=update), None)
        assert float(np.max(np.abs(np.stack([wrong.real - ref.real, wrong.imag - ref.imag])))) > 10 * KERNEL_TOLERANCE, update


# --- scoring synthetic captures ---------------------------------------------------------------


def _kernel(**over: Any) -> dict[str, Any]:
    doc = load_committed_fixture()
    base = {
        "id": "kernel.kuramoto_symmetric_step.32x32",
        "kernel": "kuramoto_symmetric_step",
        "fixture_id": doc["id"],
        "fixture_hash": doc["content_hash"],
        "width": 32,
        "height": 32,
        "steps": 10,
        "status": "ran",
        "max_abs_error": 4.2e-7,
        "nonfinite_count": 0,
        "tolerance": KERNEL_TOLERANCE,
        "passed": True,
        "timing_source": "wall",
        "dispatch_ms": [0.21, 0.18, 0.17, 0.2, 0.19, 0.18, 0.17, 0.18, 0.2, 0.19],
        "wall_dispatch_ms": [0.21, 0.18, 0.17, 0.2, 0.19, 0.18, 0.17, 0.18, 0.2, 0.19],
        "warmup_runs": 1,
        "adapter": {"vendor": "test", "timestamp_query": False},
    }
    base.update(over)
    return base


def _run(kernels: list[dict[str, Any]], tmp_path: Path | None = None):
    capture = GpuCapture(captured_at=utc_now_iso(), manifest_id="render.webgpu.tiers", measurement_class="synthetic", browser={"user_agent": "test"}, stages=[], kernels=kernels)
    source: Any = capture.model_dump(by_alias=True)
    if tmp_path is not None:
        path = tmp_path / "cap.json"
        path.write_text(json.dumps(source))  # NaN survives as a JSON NaN literal, as Python's loader accepts
        source = str(path)
    result = run_workload(load_manifest("render.webgpu.tiers"), RunContext(inputs={"capture": source}, include_gpu_env=False))
    return result, [s for s in result.stages if s.kind == KERNEL_STAGE_KIND]


def test_kernel_within_tolerance_is_ok_with_wall_time_labelled() -> None:
    result, (stage,) = _run([_kernel()])
    assert result.status == "complete", result.failures
    assert stage.status == "ok" and stage.metrics["passed"] is True
    assert stage.metrics["max_abs_error"] == pytest.approx(4.2e-7)
    assert stage.metrics["tolerance"] == KERNEL_TOLERANCE
    assert stage.metrics["timing_source"] == "wall"
    assert "wall_dispatch_ms" in stage.statistics and "gpu_dispatch_ms" not in stage.statistics
    assert "gpu_ms_unavailable" in stage.metrics
    assert stage.wall_ms and len(stage.wall_ms) == 10
    assert result.metrics["kernels"][stage.id]["status"] == "ok"


def test_kernel_timestamp_query_is_reported_as_gpu_time() -> None:
    _, (stage,) = _run([_kernel(timing_source="timestamp-query", dispatch_ms=[0.004] * 10)])
    assert stage.status == "ok"
    assert stage.metrics["gpu_dispatch_ms_p50"] == pytest.approx(0.004)
    assert "gpu_ms_unavailable" not in stage.metrics


def test_kernel_over_tolerance_fails_even_if_the_browser_says_pass() -> None:
    result, (stage,) = _run([_kernel(max_abs_error=0.02, passed=True)])
    assert stage.status == "failed" and "exceeds declared tolerance" in (stage.error or "")
    assert "warning" in stage.metrics
    assert result.status == "failed"
    assert result.failures[0].category == "validation"


def test_kernel_nan_output_fails(tmp_path: Path) -> None:
    _, (stage,) = _run([_kernel(max_abs_error=float("nan"), passed=False)], tmp_path)
    assert stage.status == "failed" and "non-finite" in (stage.error or "")
    _, (stage2,) = _run([_kernel(max_abs_error=None, nonfinite_count=3, passed=False)])
    assert stage2.status == "failed" and stage2.metrics["nonfinite_count"] == 3


def test_kernel_unsupported_is_skipped_with_reason() -> None:
    result, (stage,) = _run([_kernel(status="unsupported", unsupported_reason="navigator.gpu is not available", max_abs_error=None, passed=None, timing_source=None, dispatch_ms=[], wall_dispatch_ms=[])])
    assert stage.status == "skipped"
    assert "navigator.gpu is not available" in (stage.error or "")
    assert "max_abs_error" not in stage.metrics
    assert result.failures[0].category == "unsupported"


def test_kernel_fixture_mismatch_and_browser_error_fail() -> None:
    _, (stage,) = _run([_kernel(fixture_hash="0000000000000000")])
    assert stage.status == "failed" and "committed fixture" in (stage.error or "")
    _, (err,) = _run([_kernel(status="error", error="WebGPU validation error: x", max_abs_error=None)])
    assert err.status == "failed" and "validation error" in (err.error or "")


def test_kernel_field_is_additive_to_frame_captures() -> None:
    from tests.bench.test_render_family import _capture

    frames_only = _capture()
    assert frames_only.kernels == []
    mixed = frames_only.model_copy(update={"kernels": [load_capture({**frames_only.model_dump(by_alias=True), "kernels": [_kernel()]}).kernels[0]]})
    result = run_workload(load_manifest("render.webgpu.tiers"), RunContext(inputs={"capture": mixed.model_dump(by_alias=True)}, include_gpu_env=False))
    assert result.status == "complete", result.failures
    kinds = [s.kind for s in result.stages]
    assert kinds[-1] == KERNEL_STAGE_KIND and kinds.count("webgpu_frames") == len(frames_only.stages)


def test_scorer_fixture_ships_as_package_data_and_matches_the_page_copy() -> None:
    import psyfi_bench
    from psyfi_bench.compute.kuramoto_fixture import BENCH_PAGE_FIXTURE_PATH

    assert FIXTURE_PATH.is_relative_to(Path(psyfi_bench.__file__).resolve().parent)
    assert FIXTURE_PATH.read_bytes() == BENCH_PAGE_FIXTURE_PATH.read_bytes()


def test_missing_reference_fixture_fails_instead_of_passing_on_trust(monkeypatch) -> None:
    from psyfi_bench.render import webgpu_kernel
    from psyfi_bench.schemas import CaptureKernel

    monkeypatch.setattr(webgpu_kernel, "_committed_fixture", lambda: None)
    stage = webgpu_kernel.score_kernel(CaptureKernel.model_validate(_kernel()))
    assert stage.status == "failed"
    assert "reference fixture unavailable" in (stage.error or "")
