"""Family A — deterministic field computation (ABX-Core Kuramoto pipeline).

Measures CPU wall/CPU time, peak memory, throughput in cell-steps per second,
scaling with grid size and step count, sustained behaviour, output integrity
(exact + quantized digests) and numerical stability. Optional accelerator
backends are validated against the NumPy authority before their timings count.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from psyfi_bench.compute.backends import (
    BackendUnavailable,
    ComputeBackend,
    make_backend,
    validate_against_reference,
)
from psyfi_bench.registry import register_family
from psyfi_bench.runner import FamilyOutput, RunContext, measure_stage
from psyfi_bench.schemas import EnvironmentRecord, FailureRecord, StageRecord, WorkloadManifest
from psyfi_bench.stats import scaling_exponent, sustained_drift, summarize
from psyfi_core import ABXRuntime
from psyfi_core.abx_core.errors import SimulationCancelled
from psyfi_core.engines import ConsciousnessOmegaParams, NormalizationParams
from psyfi_core.simulation import (
    SimulationSettings,
    initial_field,
    resolve_preset_settings,
    run_simulation,
    simulate_field,
)

KINDS = ("scaling", "steps", "sustained", "presets")
PIPELINES = ("evolve", "field", "full")


def _settings(params: dict[str, Any]) -> SimulationSettings:
    return SimulationSettings(
        coupling_strength=float(params.get("coupling_strength", 0.5)),
        normalization_P=float(params.get("normalization_P", 1.0)),
        normalization_V=float(params.get("normalization_V", 1.0)),
        dt=float(params.get("dt", 0.1)),
        surround_radius=int(params.get("surround_radius", 3)),
    )


def _grids(params: dict[str, Any]) -> list[tuple[int, int]]:
    if "grids" in params:
        return [(int(w), int(h)) for w, h in params["grids"]]
    sizes = params.get("grid_sizes") or [int(params.get("grid", 64))]
    return [(int(s), int(s)) for s in sizes]


def make_stage_fn(
    *,
    width: int,
    height: int,
    steps: int,
    seed: int,
    settings: SimulationSettings,
    pipeline: str,
    backend: ComputeBackend,
    preset: str | None = None,
):
    """Return ``fn(should_cancel) -> result`` for one workload point."""

    def fn(should_cancel):
        if pipeline == "full":
            return run_simulation(width=width, height=height, steps=steps, seed=seed, preset=preset, should_cancel=should_cancel)
        if backend.canonical:
            out = simulate_field(
                width=width,
                height=height,
                steps=steps,
                seed=seed,
                settings=settings,
                should_cancel=should_cancel,
                compute_valence=False,
            )
            return out.evolved_field if pipeline == "evolve" else out.normalized_field
        # Accelerator port: identical seeded initial field, backend evolve/normalize.
        runtime = ABXRuntime(deterministic=True, seed=seed)
        field = initial_field(runtime, width, height)
        if should_cancel():
            raise SimulationCancelled("cancelled before accelerator evolve")
        params = ConsciousnessOmegaParams(
            coupling_type="symmetric", coupling_strength=settings.coupling_strength, steps=steps, dt=settings.dt
        )
        evolved = backend.evolve(field, params)
        if pipeline == "evolve":
            backend.synchronize()
            return evolved
        norm = backend.normalize(
            evolved,
            NormalizationParams(P=settings.normalization_P, V=settings.normalization_V, surround_radius=settings.surround_radius),
        )
        backend.synchronize()
        return norm

    return fn


def _digest_of(result: Any) -> np.ndarray | None:
    if isinstance(result, np.ndarray):
        return result
    if isinstance(result, dict) and "visualization" in result:
        return np.asarray(result["visualization"]["field"]["values"], dtype=np.float32)
    return None


def _throughput_metrics(width: int, height: int, steps: int):
    cells = width * height
    cell_steps = cells * steps

    def metrics(result: Any, wall_ms: list[float]) -> dict[str, Any]:
        med = float(np.median(wall_ms)) if wall_ms else float("nan")
        out: dict[str, Any] = {
            "cells": cells,
            "steps": steps,
            "cell_steps": cell_steps,
            "wall_ms_median": med,
            "ms_per_step_median": med / steps if steps else float("nan"),
            "cell_steps_per_s_median": (cell_steps / (med / 1000.0)) if med > 0 else float("nan"),
        }
        if isinstance(result, dict) and "valence" in result:
            out["valence"] = {k: result[k] for k in ("valence", "coherence", "symmetry", "roughness", "richness")}
        return out

    return metrics


def _accelerator_check(backend: ComputeBackend, width: int, height: int, steps: int, seed: int, settings: SimulationSettings, atol: float) -> dict[str, Any]:
    runtime = ABXRuntime(deterministic=True, seed=seed)
    field = initial_field(runtime, width, height)
    params = ConsciousnessOmegaParams(coupling_type="symmetric", coupling_strength=settings.coupling_strength, steps=steps, dt=settings.dt)
    norm = NormalizationParams(P=settings.normalization_P, V=settings.normalization_V, surround_radius=settings.surround_radius)
    report = validate_against_reference(backend, field, params, norm)
    report["atol"] = atol
    report["within_tolerance"] = bool(report["pipeline_max_abs_error"] <= atol)
    return report


def stage_points(manifest: WorkloadManifest, ctx: RunContext) -> list[dict[str, Any]]:
    """Expand the manifest into stage definitions (id + params)."""
    p = {**manifest.params, **ctx.inputs}
    kind = p.get("kind", "scaling")
    if kind not in KINDS:
        raise ValueError(f"unknown field_compute kind {kind!r}")
    seed = int(ctx.seed if ctx.seed is not None else p.get("seed", 1337))
    pipeline = p.get("pipeline", "field")
    if pipeline not in PIPELINES:
        raise ValueError(f"unknown pipeline {pipeline!r}")
    points: list[dict[str, Any]] = []
    if kind == "scaling":
        for w, h in _grids(p):
            points.append({"id": f"grid_{w}x{h}", "width": w, "height": h, "steps": int(p.get("steps", 20)), "seed": seed, "pipeline": pipeline})
    elif kind == "steps":
        w, h = _grids(p)[0]
        for s in p.get("steps_list") or [int(p.get("steps", 20))]:
            points.append({"id": f"steps_{int(s)}", "width": w, "height": h, "steps": int(s), "seed": seed, "pipeline": pipeline})
    elif kind == "sustained":
        w, h = _grids(p)[0]
        points.append({"id": f"sustained_{w}x{h}_s{int(p.get('steps', 50))}", "width": w, "height": h, "steps": int(p.get("steps", 50)), "seed": seed, "pipeline": pipeline})
    elif kind == "presets":
        presets = p.get("presets", "all")
        if presets == "all":
            from psyfi_core.models.substance_preset import get_registry

            presets = sorted(get_registry().list_presets())
        w, h = _grids(p)[0]
        for name in presets:
            points.append({"id": f"preset_{name}", "width": w, "height": h, "steps": int(p.get("steps", 20)), "seed": seed, "pipeline": "full", "preset": name})
    if ctx.limit is not None:
        points = points[: max(1, ctx.limit)]
    return points


@register_family("field_compute")
def run_field_compute(manifest: WorkloadManifest, ctx: RunContext, env: EnvironmentRecord) -> FamilyOutput:
    p = {**manifest.params, **ctx.inputs}
    protocol = ctx.protocol(manifest)
    kind = p.get("kind", "scaling")
    backend_name = ctx.backend or p.get("backend", "numpy")
    failures: list[FailureRecord] = []
    notes: list[str] = []
    stages: list[StageRecord] = []
    points = stage_points(manifest, ctx)

    try:
        backend = make_backend(backend_name)
    except BackendUnavailable as exc:
        for pt in points:
            stages.append(StageRecord(id=pt["id"], kind=kind, status="skipped", params=pt, error=f"unsupported: {exc}"))
        failures.append(FailureRecord(stage="*", category="unsupported", detail=str(exc)))
        return FamilyOutput(stages=stages, metrics={"backend": backend_name, "skipped": True}, failures=failures, notes=[f"backend {backend_name!r} unavailable"])

    notes.append(f"backend={backend.describe()}")
    if not backend.canonical:
        notes.append("accelerator timings include host->device transfer of the seeded initial field; CPU simulation remains the authority")

    locks: dict[str, str] = dict(manifest.references.get("quantized_sha256", {}) or {})
    quantization = manifest.tolerances.quantization

    for pt in points:
        try:
            settings = resolve_preset_settings(pt.get("preset")) if pt.get("preset") else _settings(p)
        except ValueError as exc:  # unknown preset, bad settings: a validation failure, not a crash
            stages.append(StageRecord(id=pt["id"], kind=kind, status="failed", params=pt, error=f"ValueError: {exc}"))
            continue
        fn = make_stage_fn(
            width=pt["width"], height=pt["height"], steps=pt["steps"], seed=pt["seed"], settings=settings,
            pipeline=pt["pipeline"], backend=backend, preset=pt.get("preset"),
        )
        stage = measure_stage(
            stage_id=pt["id"],
            kind=kind,
            params={**pt, "backend": backend.name, "settings": settings.__dict__},
            fn=fn,
            protocol=protocol,
            quantization=quantization,
            reference_digest=locks.get(pt["id"]),
            digest_fn=_digest_of,
            metrics_fn=_throughput_metrics(pt["width"], pt["height"], pt["steps"]),
            cancel=ctx.cancel,
        )
        if stage.status == "ok" and not backend.canonical:
            try:
                stage.metrics["accelerator_validation"] = _accelerator_check(
                    backend, pt["width"], pt["height"], pt["steps"], pt["seed"], settings, manifest.tolerances.accelerator_atol
                )
                if not stage.metrics["accelerator_validation"]["within_tolerance"]:
                    stage.status = "failed"
                    stage.error = "accelerator output outside tolerance of the NumPy reference"
            except Exception as exc:  # noqa: BLE001
                stage.status = "failed"
                stage.error = f"accelerator validation failed: {exc}"
        if stage.memory and stage.memory.tracemalloc_peak_bytes is not None:
            cells = pt["width"] * pt["height"]
            stage.metrics["tracemalloc_peak_bytes_per_cell"] = stage.memory.tracemalloc_peak_bytes / cells
        stages.append(stage)

    metrics: dict[str, Any] = {"kind": kind, "backend": backend.name, "pipeline": p.get("pipeline", "field")}
    ok = [s for s in stages if s.status == "ok"]
    if kind == "scaling" and len(ok) >= 2:
        sizes = [s.metrics["cells"] for s in ok]
        times = [s.metrics["wall_ms_median"] for s in ok]
        metrics["scaling"] = scaling_exponent(sizes, times)
    if kind == "steps" and len(ok) >= 2:
        metrics["scaling_steps"] = scaling_exponent([s.metrics["steps"] for s in ok], [s.metrics["wall_ms_median"] for s in ok])
    if ok:
        metrics["peak_cell_steps_per_s"] = max(s.metrics["cell_steps_per_s_median"] for s in ok)
        metrics["largest_cells"] = max(s.metrics["cells"] for s in ok)
    if kind == "sustained" and ok:
        s = ok[0]
        metrics["sustained"] = {
            **sustained_drift(s.wall_ms),
            "repeats": len(s.wall_ms),
            "wall_ms": summarize(s.wall_ms, unit="ms").model_dump(),
        }
    det = {
        "stages_with_digest": sum(1 for s in stages if s.determinism),
        "all_bitwise_identical_across_repeats": all(
            (s.determinism.bitwise_identical_across_repeats is True) for s in ok if s.determinism
        ) if ok else None,
        "all_quantized_identical_across_repeats": all(
            (s.determinism.quantized_identical_across_repeats is True) for s in ok if s.determinism
        ) if ok else None,
        "reference_locks": len(locks),
        "reference_matches": sum(1 for s in ok if s.determinism and s.determinism.reference_match is True),
        "reference_mismatches": [s.id for s in ok if s.determinism and s.determinism.reference_match is False],
        "nan_total": sum(s.determinism.nan_count for s in ok if s.determinism),
        "inf_total": sum(s.determinism.inf_count for s in ok if s.determinism),
        "quantization": quantization,
    }
    metrics["determinism"] = det
    return FamilyOutput(stages=stages, metrics=metrics, determinism=det, failures=failures, notes=notes)


def lock_references(manifest: WorkloadManifest, ctx: RunContext | None = None) -> WorkloadManifest:
    """Compute quantized digests for every stage with the canonical backend and store them."""
    ctx = ctx or RunContext()
    locks: dict[str, str] = {}
    from psyfi_bench.determinism import quantized_digest

    for pt in stage_points(manifest, ctx):
        settings = resolve_preset_settings(pt.get("preset")) if pt.get("preset") else _settings(manifest.params)
        fn = make_stage_fn(width=pt["width"], height=pt["height"], steps=pt["steps"], seed=pt["seed"], settings=settings, pipeline=pt["pipeline"], backend=make_backend("numpy"), preset=pt.get("preset"))
        arr = _digest_of(fn(lambda: False))
        if arr is not None:
            locks[pt["id"]] = quantized_digest(arr, manifest.tolerances.quantization)
    refs = dict(manifest.references)
    refs["quantized_sha256"] = locks
    refs["locked_with"] = {"backend": "numpy", "quantization": manifest.tolerances.quantization}
    return manifest.model_copy(update={"references": refs})
