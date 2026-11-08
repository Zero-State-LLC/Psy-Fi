"""Family A: field-compute workloads, determinism locks, timeouts, accelerator validation."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from psyfi_bench.compute.backends import (
    BackendUnavailable,
    NumpyBackend,
    available_backend_names,
    make_backend,
    validate_against_reference,
)
from psyfi_bench.families.field_compute import lock_references, stage_points
from psyfi_bench.registry import load_manifest
from psyfi_bench.runner import RunContext, run_workload
from psyfi_bench.schemas import Protocol
from psyfi_bench.store import ResultStore
from psyfi_core import ABXRuntime
from psyfi_core.engines import ConsciousnessOmegaParams, NormalizationParams
from psyfi_core.simulation import SimulationSettings, initial_field, run_simulation, simulate_field

FAST = Protocol(warmup_runs=1, repeats=2, cold_start=True, timeout_s=120, memory_probe=True, bootstrap_resamples=200)


def _fast(manifest, **inputs):
    m = manifest.model_copy(update={"protocol": FAST})
    ctx = RunContext(inputs=inputs, include_gpu_env=False)
    return m, ctx


def test_simulation_refactor_keeps_api_output_and_exposes_the_field() -> None:
    from psyfi_api.simulation_service import run_simulation as api_run

    assert api_run is run_simulation
    payload = run_simulation(width=24, height=16, steps=5, seed=11, preset="lsd")
    out = simulate_field(width=24, height=16, steps=5, seed=11, settings=SimulationSettings(coupling_strength=payload["session"]["parameters"]["coupling_strength"], normalization_P=payload["session"]["parameters"]["normalization_P"], normalization_V=payload["session"]["parameters"]["normalization_V"]))
    assert out.valence is not None
    assert out.valence.valence_score == pytest.approx(payload["valence"])
    assert out.normalized_field.dtype == np.complex64
    assert payload["module_chain"][:1] == ["consciousness_omega"]


def test_scaling_workload_runs_and_matches_locked_reference(tmp_path) -> None:
    manifest, ctx = _fast(load_manifest("field-compute.scaling"), grid_sizes=[32, 48])
    ctx.store = ResultStore(tmp_path)
    result = run_workload(manifest, ctx)
    assert result.status == "complete", result.failures
    assert result.measurement_class == "measured"
    assert [s.id for s in result.stages] == ["grid_32x32", "grid_48x48"]
    g32 = result.stages[0]
    assert g32.status == "ok"
    assert len(g32.wall_ms) == 2 and g32.cold_wall_ms is not None
    assert g32.statistics["wall_ms"].n == 2
    assert g32.metrics["cell_steps_per_s_median"] > 0
    assert g32.memory is not None and g32.memory.tracemalloc_peak_bytes
    assert g32.determinism is not None
    assert g32.determinism.bitwise_identical_across_repeats is True
    # 32x32 is a locked stage; 48x48 is not in the manifest's locks.
    assert g32.determinism.reference_within_tolerance is True
    assert g32.determinism.reference_max_abs_error is not None
    assert g32.determinism.reference_match in (True, False)  # digest equality is platform-class evidence
    assert result.stages[1].determinism.reference_match is None
    assert result.stages[1].determinism.reference_within_tolerance is None
    assert result.metrics["scaling"]["n"] == 2
    assert result.verify()
    assert ctx.store.list(manifest_id="field-compute.scaling")


def test_all_locked_manifests_still_match_on_this_platform() -> None:
    """The locked summary must reproduce within tolerance on every platform (H2, revised).

    Quantized digests at 1e-4 differ between Linux x86-64 and Apple arm64 for the larger stages
    (observed in CI on 2026-11-08), so digest equality is reported as a platform-class finding and
    only the tolerance check is asserted.
    """
    from psyfi_bench.determinism import summary_error

    for ref in ("field-compute.scaling", "field-compute.steps", "field-compute.presets"):
        manifest = load_manifest(ref)
        relocked = lock_references(manifest).references
        for stage_id, lock in manifest.references["summary"].items():
            err = summary_error(relocked["summary"][stage_id], lock)
            assert err <= manifest.tolerances.reference_atol, f"{ref}/{stage_id}: summary drifted by {err}"
        drifted = [k for k, v in manifest.references["quantized_sha256"].items() if relocked["quantized_sha256"].get(k) != v]
        if drifted:
            warnings.warn(f"{ref}: quantized digests differ on this platform for {drifted} (summary within tolerance)", stacklevel=1)


def test_presets_workload_covers_registry_and_full_pipeline(tmp_path) -> None:
    manifest, ctx = _fast(load_manifest("field-compute.presets"))
    ctx.limit = 2
    result = run_workload(manifest, ctx)
    assert result.status == "complete", result.failures
    assert len(result.stages) == 2
    for stage in result.stages:
        assert stage.params["pipeline"] == "full"
        assert "valence" in stage.metrics["valence"]
        assert stage.determinism and stage.determinism.reference_within_tolerance is True


def test_unknown_preset_is_a_validation_failure_not_a_crash() -> None:
    manifest, ctx = _fast(load_manifest("field-compute.presets"), presets=["no-such-preset"])
    result = run_workload(manifest, ctx)
    assert result.status == "failed"
    assert result.stages[0].status == "failed"
    assert result.failures and result.failures[0].category == "validation"


def test_timeout_is_classified_and_does_not_raise() -> None:
    manifest = load_manifest("field-compute.scaling").model_copy(
        update={"protocol": Protocol(warmup_runs=0, repeats=3, cold_start=False, timeout_s=0.0005, memory_probe=False)}
    )
    ctx = RunContext(inputs={"grid_sizes": [256], "steps": 200}, include_gpu_env=False)
    result = run_workload(manifest, ctx)
    assert result.stages[0].status == "timeout", result.stages[0]
    assert result.failures[0].category == "timeout"
    assert result.status == "failed"


def test_sustained_workload_reports_drift() -> None:
    manifest = load_manifest("field-compute.sustained").model_copy(
        update={"protocol": Protocol(warmup_runs=1, repeats=4, cold_start=True, timeout_s=120, min_duration_s=0.05, memory_probe=False, bootstrap_resamples=200)}
    )
    ctx = RunContext(inputs={"grid": 32, "steps": 5}, include_gpu_env=False)
    result = run_workload(manifest, ctx)
    assert result.status == "complete", result.failures
    sustained = result.metrics["sustained"]
    assert sustained["repeats"] >= 4
    assert "slope_ms_per_1000_frames" in sustained


def test_stage_points_respect_limit_and_kind() -> None:
    manifest = load_manifest("field-compute.steps")
    pts = stage_points(manifest, RunContext(limit=2))
    assert [p["id"] for p in pts] == ["steps_10", "steps_50"]
    with pytest.raises(ValueError):
        stage_points(manifest.model_copy(update={"params": {**manifest.params, "kind": "bogus"}}), RunContext())


class _DriftingBackend(NumpyBackend):
    """A fake accelerator that is wrong by 1e-3: must fail validation at atol=1e-4."""

    name = "fake-accel"
    canonical = False

    def evolve(self, field, params):
        return (super().evolve(field, params) + np.complex64(1e-3)).astype(np.complex64)


def test_accelerator_validation_rejects_a_wrong_port() -> None:
    runtime = ABXRuntime(deterministic=True, seed=5)
    field = initial_field(runtime, 16, 16)
    params = ConsciousnessOmegaParams(coupling_strength=0.5, steps=4, dt=0.1)
    norm = NormalizationParams(P=1.0, V=1.0, surround_radius=3)
    report = validate_against_reference(_DriftingBackend(), field, params, norm)
    assert report["evolve_max_abs_error"] >= 9e-4
    exact = validate_against_reference(NumpyBackend(), field, params, norm)
    assert exact["pipeline_max_abs_error"] == 0.0


def test_unavailable_backend_is_skipped_with_a_reason() -> None:
    with pytest.raises(BackendUnavailable):
        make_backend("quantum")
    names = available_backend_names()
    assert names["numpy"] is True
    manifest, ctx = _fast(load_manifest("field-compute.accelerator"), grid_sizes=[16])
    ctx.backend = "quantum"
    result = run_workload(manifest, ctx)
    assert result.stages[0].status == "skipped"
    assert result.failures[0].category == "unsupported"


@pytest.mark.skipif(not available_backend_names().get("torch"), reason="torch not installed")
def test_torch_backend_matches_reference_within_tolerance() -> None:
    backend = make_backend("torch")
    runtime = ABXRuntime(deterministic=True, seed=5)
    field = initial_field(runtime, 32, 32)
    params = ConsciousnessOmegaParams(coupling_strength=0.5, steps=10, dt=0.1)
    norm = NormalizationParams(P=1.0, V=1.0, surround_radius=3)
    report = validate_against_reference(backend, field, params, norm)
    assert report["pipeline_max_abs_error"] <= 1e-3, report
