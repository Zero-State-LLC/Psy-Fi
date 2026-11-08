"""Scorecards: multidimensional, per family, with validity gates. No universal score.

Composites are optional, named, and carry their formula, inputs, weights,
normalization, a local sensitivity sweep, and the missing-data rule. A composite
with a missing input is ``null`` with a reason, never an imputed value.
"""

from __future__ import annotations

from typing import Any

from psyfi_bench import NON_CLAIM
from psyfi_bench.schemas import BenchResult, ScoreDimension, Scorecard
from psyfi_bench.timing import utc_now_iso

Better = str  # "lower" | "higher"


def _dim(value: Any, unit: str, better: Better, source: str, ci: tuple[float, float] | None = None, missing: str | None = None) -> ScoreDimension:
    if value is None or (isinstance(value, float) and value != value):
        return ScoreDimension(value=None, unit=unit, better=better, source=source, missing_reason=missing or "not measured")  # type: ignore[arg-type]
    return ScoreDimension(value=float(value), unit=unit, better=better, source=source, ci95=ci)  # type: ignore[arg-type]


def _largest_stage(result: BenchResult):
    ok = [s for s in result.stages if s.status == "ok" and "cells" in s.metrics]
    return max(ok, key=lambda s: s.metrics["cells"]) if ok else None


def dimensions_field_compute(r: BenchResult) -> dict[str, ScoreDimension]:
    m = r.metrics
    big = _largest_stage(r)
    det = m.get("determinism") or {}
    dims = {
        "throughput_cell_steps_per_s": _dim(m.get("peak_cell_steps_per_s"), "cell-steps/s", "higher", "metrics.peak_cell_steps_per_s"),
        "wall_ms_largest_grid_p50": _dim(big.statistics["wall_ms"].p50 if big else None, "ms", "lower", f"stages.{big.id}.statistics.wall_ms.p50" if big else "n/a", ci=big.statistics["wall_ms"].ci95_median if big else None),
        "wall_ms_largest_grid_cv": _dim(big.statistics["wall_ms"].cv if big else None, "ratio", "lower", f"stages.{big.id}.statistics.wall_ms.cv" if big else "n/a"),
        "scaling_deviation_from_linear": _dim(abs((m.get("scaling") or {}).get("exponent", float("nan")) - 1.0) if m.get("scaling") else None, "|k-1|", "lower", "metrics.scaling.exponent", missing="scaling needs two or more grid sizes"),
        "peak_tracemalloc_bytes_per_cell": _dim(big.metrics.get("tracemalloc_peak_bytes_per_cell") if big else None, "bytes/cell", "lower", f"stages.{big.id}.metrics" if big else "n/a", missing="memory probe disabled"),
        "bitwise_determinism": _dim(1.0 if det.get("all_bitwise_identical_across_repeats") else (0.0 if det.get("all_bitwise_identical_across_repeats") is False else None), "0|1", "higher", "metrics.determinism"),
        "reference_lock_matches": _dim(det.get("reference_matches"), "count", "higher", "metrics.determinism.reference_matches"),
        "reference_within_tolerance": _dim(det.get("reference_within_tolerance"), "count", "higher", "metrics.determinism.reference_within_tolerance"),
    }
    if m.get("sustained"):
        dims["sustained_drift_ratio"] = _dim(m["sustained"].get("last_first_quartile_ratio"), "ratio", "lower", "metrics.sustained")
    return dims


def dimensions_render(r: BenchResult) -> dict[str, ScoreDimension]:
    m = r.metrics
    dims: dict[str, ScoreDimension] = {}
    per_tier = m.get("per_tier") or {}
    if m.get("execution_class") == "soft":
        for tier, row in per_tier.items():
            dims[f"{tier}.raster_ms_per_megapixel"] = _dim(row.get("raster_ms_per_megapixel_median"), "ms/MP", "lower", f"metrics.per_tier.{tier}")
        parity = m.get("cross_language_parity") or {}
        dims["ts_parity_matched"] = _dim(parity.get("matched"), "count", "higher", "metrics.cross_language_parity", missing=parity.get("reason"))
        return dims
    for tier, row in per_tier.items():
        dims[f"{tier}.fps_avg"] = _dim(row.get("fps_avg_median"), "fps", "higher", f"metrics.per_tier.{tier}")
        dims[f"{tier}.fps_1pct_low"] = _dim(row.get("fps_1pct_low_median"), "fps", "higher", f"metrics.per_tier.{tier}")
        dims[f"{tier}.frame_ms_p95"] = _dim(row.get("frame_ms_p95_median"), "ms", "lower", f"metrics.per_tier.{tier}")
        dims[f"{tier}.budget_ok"] = _dim(1.0 if row.get("budget_ok_all") else 0.0, "0|1", "higher", f"metrics.per_tier.{tier}.budget_ok_all")
        dims[f"{tier}.ssim_vs_ultra"] = _dim(row.get("ssim_vs_ultra_mean"), "ssim", "higher", f"metrics.per_tier.{tier}", missing="no thumbnails in capture")
    sustained = m.get("sustained") or {}
    if sustained:
        first = next(iter(sustained.values()))
        dims["sustained_drift_ms_per_1000_frames"] = _dim(first.get("slope_ms_per_1000_frames"), "ms/1000 frames", "lower", "metrics.sustained")
    return dims


def dimensions_interpretation(r: BenchResult) -> dict[str, ScoreDimension]:
    t = (r.metrics.get("tasks") or {})
    img = t.get("image_read") or {}
    st = t.get("structured_read") or {}
    pert = (t.get("perturbation") or {}).get("invariance") or {}
    rep = (t.get("repeatability") or {}).get("repeatability") or {}
    lat = img.get("latency_ms") or {}
    dims = {
        "fde_mean": _dim(img.get("fde_mean"), "field L1", "lower", "tasks.image_read.fde_mean", ci=tuple(img["fde_ci95_mean"]) if img.get("fde_ci95_mean") else None, missing="no parsed readings"),
        "fde_normalized_mean": _dim(img.get("fde_normalized_mean"), "mode steps", "lower", "tasks.image_read.fde_normalized_mean"),
        "within_mode_step_rate": _dim(img.get("within_mode_step_rate"), "rate", "higher", "tasks.image_read.within_mode_step_rate"),
        "mode_accuracy": _dim(img.get("mode_accuracy"), "rate", "higher", "tasks.image_read.mode_accuracy"),
        "intensity_mae": _dim(img.get("intensity_mae"), "intensity", "lower", "tasks.image_read.intensity_mae"),
        "parse_rate": _dim(img.get("parse_rate"), "rate", "higher", "tasks.image_read.parse_rate"),
        "schema_violation_rate": _dim(img.get("schema_violation_rate"), "rate", "lower", "tasks.image_read.schema_violation_rate"),
        "discriminability_rho": _dim((img.get("discriminability") or {}).get("spearman_rho"), "rho", "higher", "tasks.image_read.discriminability"),
        "structured_fde_mean": _dim(st.get("fde_mean"), "field L1", "lower", "tasks.structured_read.fde_mean", missing="structured_read not run"),
        "cross_modal_mode_agreement": _dim((st.get("cross_modal") or {}).get("mode_agreement_rate"), "rate", "higher", "tasks.structured_read.cross_modal", missing="structured_read not run"),
        "invariance_to_discriminability_ratio": _dim(pert.get("invariance_to_discriminability_ratio"), "ratio", "higher", "tasks.perturbation.invariance", missing="perturbation not run or zero perturbation distance"),
        "perturbation_mode_flip_rate": _dim(pert.get("mode_flip_rate"), "rate", "lower", "tasks.perturbation.invariance", missing="perturbation not run"),
        "repeat_exact_agreement": _dim(rep.get("exact_agreement_rate"), "rate", "higher", "tasks.repeatability", missing="repeatability not run"),
        "latency_ms_p50": _dim(lat.get("p50"), "ms", "lower", "tasks.image_read.latency_ms.p50", missing="no latencies"),
        "cost_per_valid_result": _dim(img.get("cost_per_valid_result"), "currency", "lower", "tasks.image_read.cost_per_valid_result", missing="no pricing supplied"),
    }
    return dims


def dimensions_fieldloop(r: BenchResult) -> dict[str, ScoreDimension]:
    m = r.metrics
    shares = m.get("stage_share_of_e2e_mean") or {}
    return {
        "e2e_ms_median": _dim(m.get("e2e_ms_median"), "ms", "lower", "metrics.e2e_ms_median"),
        "fde_median": _dim(m.get("fde_median"), "field L1", "lower", "metrics.fde_median", missing="loop never closed"),
        "within_mode_step_rate": _dim(m.get("within_mode_step_rate"), "rate", "higher", "metrics.within_mode_step_rate"),
        "loop_closed_rate": _dim((m.get("closed") / m.get("cases")) if m.get("cases") else None, "rate", "higher", "metrics.closed/cases"),
        "interpret_share_of_e2e": _dim(shares.get("interpret"), "ratio", "lower", "metrics.stage_share_of_e2e_mean.interpret"),
    }


DIMENSIONS = {
    "field_compute": dimensions_field_compute,
    "render": dimensions_render,
    "interpretation": dimensions_interpretation,
    "fieldloop": dimensions_fieldloop,
}


def _sensitivity(formula_fn, inputs: dict[str, float], delta: float = 0.10) -> dict[str, Any]:
    base = formula_fn(inputs)
    out: dict[str, Any] = {"delta": delta, "base": base, "per_input": {}}
    for k, v in inputs.items():
        lo = formula_fn({**inputs, k: v * (1 - delta)})
        hi = formula_fn({**inputs, k: v * (1 + delta)})
        out["per_input"][k] = {"minus": lo, "plus": hi}
    return out


def composites_for(family: str, dims: dict[str, ScoreDimension]) -> dict[str, Any]:
    """Named composites with published formulas. Null when any input is missing."""
    out: dict[str, Any] = {}

    def val(name: str) -> float | None:
        d = dims.get(name)
        return None if d is None else d.value

    if family == "interpretation":
        inputs = {"within_mode_step_rate": val("within_mode_step_rate"), "parse_rate": val("parse_rate"), "latency_ms_p50": val("latency_ms_p50")}
        spec: dict[str, Any] = {
            "formula": "valid_in_step_per_second = within_mode_step_rate * parse_rate / (latency_ms_p50 / 1000)",
            "weights": "none (product/ratio of raw rates)",
            "normalization": "none; units are valid readings within one mode step per second",
            "inputs": inputs,
            "missing_data_rule": "null when any input is missing or latency is zero",
            "valid_comparison": "same manifest_hash, same prompt_revision, same image_size",
        }
        if all(v is not None for v in inputs.values()) and inputs["latency_ms_p50"]:
            fn = lambda i: (i["within_mode_step_rate"] * i["parse_rate"]) / (i["latency_ms_p50"] / 1000.0)  # noqa: E731
            spec["value"] = fn(inputs)  # type: ignore[arg-type]
            spec["sensitivity"] = _sensitivity(fn, inputs)  # type: ignore[arg-type]
        else:
            spec["value"] = None
        out["valid_in_step_per_second"] = spec
        cost = val("cost_per_valid_result")
        fden = val("fde_normalized_mean")
        spec2: dict[str, Any] = {
            "formula": "fidelity_per_currency = max(0, 1 - fde_normalized_mean) / cost_per_valid_result",
            "weights": "none",
            "normalization": "fde_normalized is in mode steps; 1 - that is clipped at 0",
            "inputs": {"fde_normalized_mean": fden, "cost_per_valid_result": cost},
            "missing_data_rule": "null without pricing",
            "valid_comparison": "same manifest_hash; prices must be stated per provider",
            "value": (max(0.0, 1.0 - fden) / cost) if (cost and fden is not None and cost > 0) else None,
        }
        out["fidelity_per_currency"] = spec2
    elif family == "render":
        for tier in ("ultra", "high", "balanced", "battery"):
            ssim_v = val(f"{tier}.ssim_vs_ultra")
            p95 = val(f"{tier}.frame_ms_p95")
            out[f"{tier}.ssim_per_ms_p95"] = {
                "formula": "ssim_vs_ultra / frame_ms_p95 (same device only)",
                "weights": "none",
                "normalization": "none",
                "inputs": {"ssim_vs_ultra": ssim_v, "frame_ms_p95": p95},
                "missing_data_rule": "null without thumbnails or frames",
                "valid_comparison": "within one device and one manifest_hash; never across devices",
                "value": (ssim_v / p95) if (ssim_v is not None and p95) else None,
            }
    elif family == "fieldloop":
        e2e = val("e2e_ms_median")
        rate = val("within_mode_step_rate")
        out["closed_loops_in_step_per_second"] = {
            "formula": "within_mode_step_rate * loop_closed_rate / (e2e_ms_median / 1000)",
            "weights": "none",
            "normalization": "none",
            "inputs": {"within_mode_step_rate": rate, "loop_closed_rate": val("loop_closed_rate"), "e2e_ms_median": e2e},
            "missing_data_rule": "null when the loop never closed",
            "valid_comparison": "same manifest_hash and same render source",
            "value": (rate * val("loop_closed_rate") / (e2e / 1000.0)) if (rate is not None and e2e and val("loop_closed_rate") is not None) else None,  # type: ignore[operator]
        }
    return out


PRIMARY = {
    "field_compute": ("throughput_cell_steps_per_s", "higher", "bitwise_determinism"),
    "render": ("ultra.fps_1pct_low", "higher", "ultra.budget_ok"),
    "interpretation": ("fde_mean", "lower", "parse_rate"),
    "fieldloop": ("e2e_ms_median", "lower", "loop_closed_rate"),
}


def recommend(family: str, labels: list[str], dims: dict[str, dict[str, ScoreDimension]], comparable: bool) -> list[str]:
    primary, better, gate = PRIMARY.get(family, (None, None, None))
    if not primary or not comparable:
        return ["No ranking: results are not comparable (different manifest hashes or measurement classes)."] if not comparable else []
    rows = []
    for label in labels:
        d = dims.get(primary, {}).get(label)
        g = dims.get(gate, {}).get(label) if gate else None
        if d is None or d.value is None:
            continue
        gate_ok = g is None or g.value is None or g.value >= 0.9
        rows.append((label, d.value, gate_ok))
    if not rows:
        return [f"No subject reported {primary}."]
    ranked = sorted(rows, key=lambda r: (not r[2], -r[1] if better == "higher" else r[1]))
    best = ranked[0]
    unit = next((dims[primary][l].unit for l in labels if l in dims.get(primary, {})), "")
    out = [f"Best {primary} ({better} is better, gate {gate} >= 0.9): {best[0]} at {best[1]:.4g} {unit}" + ("" if best[2] else " (gate not met)")]
    if len(ranked) > 1:
        out.append("Ranking: " + " > ".join(f"{l} ({v:.4g})" for l, v, _ in ranked))
    return out


def build_scorecard(results: list[BenchResult], labels: list[str] | None = None) -> Scorecard:
    if not results:
        raise ValueError("a scorecard needs at least one result")
    labels = labels or [r.run_id for r in results]
    if len(labels) != len(results):
        raise ValueError("labels must match results")
    family = str(results[0].manifest.get("family"))
    manifest_id = str(results[0].manifest.get("id"))
    hashes = {r.manifest_hash for r in results}
    classes = {r.measurement_class for r in results}
    families = {str(r.manifest.get("family")) for r in results}
    reasons: list[str] = []
    if len(families) > 1:
        reasons.append("mixed families")
    if len(hashes) > 1:
        reasons.append("mixed manifest hashes: workloads differ")
    if len(classes) > 1:
        reasons.append("mixed measurement classes: synthetic/replay results are not evidence")
    if any(r.status != "complete" for r in results):
        reasons.append("some results are partial or failed")
    comparable = not reasons or reasons == ["some results are partial or failed"]
    dim_fn = DIMENSIONS.get(family)
    per_subject = {label: (dim_fn(r) if dim_fn else {}) for label, r in zip(labels, results)}
    names = sorted({n for d in per_subject.values() for n in d})
    dimensions = {n: {label: per_subject[label][n] for label in labels if n in per_subject[label]} for n in names}
    composites = {label: composites_for(family, per_subject[label]) for label in labels}
    subjects = [
        {
            "label": label,
            "run_id": r.run_id,
            "created_at": r.created_at,
            "measurement_class": r.measurement_class,
            "status": r.status,
            "hardware_class": r.environment.hardware_class,
            "cpu": (r.environment.cpu or {}).get("brand"),
            "gpus": [g.name for g in r.environment.gpus],
            "provider": (r.metrics.get("provider") or {}).get("model") if isinstance(r.metrics.get("provider"), dict) else r.metrics.get("provider"),
            "backend": r.metrics.get("backend"),
        }
        for label, r in zip(labels, results)
    ]
    return Scorecard(
        generated_at=utc_now_iso(),
        family=family,  # type: ignore[arg-type]
        manifest_id=manifest_id,
        manifest_hash=next(iter(hashes)) if len(hashes) == 1 else "mixed",
        subjects=subjects,
        dimensions=dimensions,
        composites=composites,
        validity={"comparable": comparable, "reasons": reasons, "manifest_hashes": sorted(hashes), "measurement_classes": sorted(classes), "rule": "compare only identical manifest hashes; pixel fidelity only within one device; synthetic and replay results are never hardware or model evidence"},
        recommendations=recommend(family, labels, dimensions, comparable),
        non_claim=NON_CLAIM,
    )
