"""Family D — FieldLoop, the signature benchmark.

seed → ABX simulation → ParameterField + scene snapshot → render → model
interpretation → field reconstruction → Field Displacement Error. Every stage
is timed on its own; the loop is timed end to end. Local and remote inference
are labelled; browser/network time is only reported when a capture supplies it.
"""

from __future__ import annotations

import json
import time
from typing import Any

import numpy as np

from psyfi_bench.families.interpretation import IMAGE_PROMPT, PROMPT_REVISION, field_displacement, parse_strict
from psyfi_bench.providers.base import ModelRequest
from psyfi_bench.providers.registry import make_provider
from psyfi_bench.registry import register_family
from psyfi_bench.render.soft_raster import sha256_rgba, soft_present_snapshot
from psyfi_bench.runner import FamilyOutput, RunContext
from psyfi_bench.schemas import EnvironmentRecord, FailureRecord, StageRecord, WorkloadManifest
from psyfi_bench.stats import summarize
from psyfi_bench.timing import Deadline
from psyfi_core.experiences.parameter_mapper import map_parameters
from psyfi_core.models.substance_preset import get_registry
from psyfi_core.simulation import run_simulation
from psyfi_core.visualization.scene_snapshot import build_scene_snapshot

STAGE_ORDER = ("simulate", "snapshot", "render", "interpret", "reconstruct")


def run_loop_once(case: dict[str, Any], provider: Any, *, image_size: int, sim: dict[str, Any], max_tokens: int, temperature: float, seed: int | None, deadline: Deadline) -> dict[str, Any]:
    timings: dict[str, float] = {}
    t_start = time.perf_counter_ns()

    # 1. simulate (API-equivalent payload; preset = substance when the registry has it)
    preset = case["substance"] if case["substance"] in set(get_registry().list_presets()) else None
    t0 = time.perf_counter_ns()
    payload = run_simulation(width=int(sim.get("width", 32)), height=int(sim.get("height", 32)), steps=int(sim.get("steps", 4)), seed=int(case["seed"]), preset=preset, should_cancel=deadline.should_cancel)
    timings["simulate"] = (time.perf_counter_ns() - t0) / 1e6
    deadline.check()

    # 2. snapshot
    t0 = time.perf_counter_ns()
    field = map_parameters(substance=case["substance"], mode=case["mode"], intensity=float(case["intensity"]), seed=int(case["seed"]), phase_t=float(case.get("phase_t", 0.4)), quality_tier=str(case.get("tier", "balanced"))).to_dict()
    snapshot = build_scene_snapshot(parameter_field=field, simulation=payload, quality_tier=str(case.get("tier", "balanced")), sequence=1, snapshot_id=f"fieldloop:{case['key']}")
    timings["snapshot"] = (time.perf_counter_ns() - t0) / 1e6
    deadline.check()

    # 3. render (CPU soft raster; a webgpu capture thumbnail may replace this in a browser loop)
    t0 = time.perf_counter_ns()
    image = soft_present_snapshot(snapshot, image_size)
    timings["render"] = (time.perf_counter_ns() - t0) / 1e6
    deadline.check()

    # 4. interpret
    request = ModelRequest(prompt=IMAGE_PROMPT, images=[image], max_tokens=max_tokens, temperature=temperature, seed=seed, metadata={"reference": {"mode": case["mode"], "intensity": case["intensity"]}})
    t0 = time.perf_counter_ns()
    try:
        resp = provider.complete(request)
    except Exception as exc:  # noqa: BLE001
        from psyfi_bench.providers.base import ModelResponse

        resp = ModelResponse(text=None, latency_ms=0.0, provider=getattr(provider, "name", "?"), model=getattr(provider, "model", "?"), locality=getattr(provider, "locality", "remote"), error=f"{type(exc).__name__}: {exc}"[:200])
    timings["interpret"] = (time.perf_counter_ns() - t0) / 1e6
    timings["interpret_provider_reported"] = resp.latency_ms

    # 5. reconstruct + score
    t0 = time.perf_counter_ns()
    parsed = parse_strict(resp.text)
    score: dict[str, Any] = {"parse_ok": parsed["parse_ok"], "violation": parsed["violation"], "provider_error": resp.error}
    if parsed["parse_ok"]:
        score.update(field_displacement({**case, "phase_t": case.get("phase_t", 0.4), "tier": case.get("tier", "balanced")}, parsed["mode"], float(parsed["intensity"])))
        score["reading"] = {"mode": parsed["mode"], "intensity": parsed["intensity"]}
    timings["reconstruct"] = (time.perf_counter_ns() - t0) / 1e6
    timings["end_to_end"] = (time.perf_counter_ns() - t_start) / 1e6

    return {
        "timings": timings,
        "score": score,
        "image_sha256": sha256_rgba(image),
        "field_hash": field["hash"],
        "simulation": {"provenance_id": payload.get("provenance_id"), "valence": payload.get("valence"), "coherence": payload.get("coherence")},
        "usage": resp.usage,
        "locality": resp.locality,
        "text": (resp.text or "")[:200],
    }


@register_family("fieldloop")
def run_fieldloop(manifest: WorkloadManifest, ctx: RunContext, env: EnvironmentRecord) -> FamilyOutput:
    p = {**manifest.params, **ctx.inputs}
    protocol = ctx.protocol(manifest)
    cases = list(p.get("cases") or [])
    for c in cases:
        c.setdefault("key", f"{c['substance']}_{c['mode']}_{c['seed']}")
    if ctx.limit is not None:
        cases = cases[: max(1, ctx.limit)]
    spec = ctx.provider or p.get("provider") or "heuristic"
    try:
        provider = make_provider(spec, ctx.provider_options)
    except Exception as exc:  # noqa: BLE001
        return FamilyOutput(stages=[StageRecord(id="provider", kind="provider", status="skipped", error=f"unsupported: {exc}")], metrics={"provider": spec, "skipped": True}, failures=[FailureRecord(stage="provider", category="unsupported", detail=str(exc))])
    locality = getattr(provider, "locality", "remote")
    measurement_class = "replay" if locality == "replay" else ("synthetic" if locality == "baseline" else "measured")
    sim = dict(p.get("simulation") or {"width": 32, "height": 32, "steps": 4})
    image_size = int(p.get("image_size", 256))
    stages: list[StageRecord] = []

    for case in cases:
        stage = StageRecord(id=case["key"], kind="fieldloop", measurement_class=measurement_class, params={"case": case, "simulation": sim, "image_size": image_size, "prompt_revision": PROMPT_REVISION})
        deadline = Deadline(protocol.timeout_s, ctx.cancel)
        runs: list[dict[str, Any]] = []
        try:
            warm = max(protocol.warmup_runs, 1 if protocol.cold_start else 0)
            for i in range(warm):
                r = run_loop_once(case, provider, image_size=image_size, sim=sim, max_tokens=int(p.get("max_tokens", 64)), temperature=float(p.get("temperature", 0.0)), seed=ctx.seed, deadline=deadline)
                if i == 0 and protocol.cold_start:
                    stage.cold_wall_ms = r["timings"]["end_to_end"]
                stage.warmup_wall_ms.append(r["timings"]["end_to_end"])
            for _ in range(protocol.repeats):
                r = run_loop_once(case, provider, image_size=image_size, sim=sim, max_tokens=int(p.get("max_tokens", 64)), temperature=float(p.get("temperature", 0.0)), seed=ctx.seed, deadline=deadline)
                runs.append(r)
                stage.wall_ms.append(r["timings"]["end_to_end"])
        except Exception as exc:  # noqa: BLE001 — every failure becomes evidence
            from psyfi_bench.runner import classify_exception

            category = classify_exception(exc)
            if category == "timeout" or deadline.expired:
                stage.status = "timeout"
            elif category == "cancelled":
                stage.status = "cancelled"
            else:
                stage.status = "failed"
            stage.error = f"{type(exc).__name__}: {exc}"[:240]
        if runs:
            stage.statistics["end_to_end_ms"] = summarize(stage.wall_ms, unit="ms", resamples=protocol.bootstrap_resamples, seed=protocol.bootstrap_seed)
            per_stage = {k: summarize([r["timings"][k] for r in runs], unit="ms", seed=protocol.bootstrap_seed).model_dump() for k in STAGE_ORDER}
            e2e_med = float(np.median(stage.wall_ms))
            shares = {k: (per_stage[k]["median"] / e2e_med if e2e_med > 0 else None) for k in STAGE_ORDER}
            scored = [r["score"] for r in runs if r["score"].get("parse_ok")]
            stage.metrics = {
                "runs": len(runs),
                "stage_ms": per_stage,
                "stage_share_of_e2e": shares,
                "provider_reported_latency_ms_median": float(np.median([r["timings"]["interpret_provider_reported"] for r in runs])),
                "loop_closed_rate": len(scored) / len(runs),
                "fde_median": float(np.median([s["fde"] for s in scored])) if scored else None,
                "within_mode_step_rate": (sum(1 for s in scored if s["within_mode_step"]) / len(scored)) if scored else None,
                "mode_accuracy": (sum(1 for s in scored if s["mode_match"]) / len(scored)) if scored else None,
                "readings": [r["score"].get("reading") for r in runs],
                "image_sha256": runs[0]["image_sha256"],
                "field_hash": runs[0]["field_hash"],
                "simulation": runs[0]["simulation"],
                "deterministic_image_across_runs": len({r["image_sha256"] for r in runs}) == 1,
                "locality": runs[0]["locality"],
                "provider_errors": sum(1 for r in runs if r["score"].get("provider_error")),
            }
            if stage.status == "ok" and not scored:
                stage.status = "failed"
                stage.error = "loop never closed: no parseable reading"
        stages.append(stage)

    ok = [s for s in stages if s.status == "ok" and s.metrics]
    metrics: dict[str, Any] = {
        "provider": provider.describe(),
        "locality": locality,
        "cases": len(cases),
        "closed": len(ok),
        "e2e_ms_median": float(np.median([s.statistics["end_to_end_ms"].median for s in ok])) if ok else None,
        "fde_median": float(np.median([s.metrics["fde_median"] for s in ok if s.metrics.get("fde_median") is not None])) if any(s.metrics.get("fde_median") is not None for s in ok) else None,
        "within_mode_step_rate": float(np.mean([s.metrics["within_mode_step_rate"] for s in ok if s.metrics.get("within_mode_step_rate") is not None])) if ok else None,
        "stage_share_of_e2e_mean": {k: float(np.mean([s.metrics["stage_share_of_e2e"][k] for s in ok if s.metrics["stage_share_of_e2e"][k] is not None])) for k in STAGE_ORDER} if ok else None,
        "render_source": "soft",
        "note": "CPU loop: render is the deterministic soft raster. A browser loop would substitute a WebGPU capture thumbnail and add browser, network and provider time as separate stages.",
    }
    return FamilyOutput(stages=stages, metrics=metrics, measurement_class=measurement_class, notes=[f"provider={json.dumps(provider.describe(), default=str)}"])
