"""Family C — AI model interpretation of rendered and structured field states.

Deterministic references come from the generating parameters, so no model judges
another model. The headline metric is Field Displacement Error (FDE): the L1
distance in ParameterField ``parameters`` space between the oracle field and the
field reconstructed from the model's (mode, intensity) reading, with the nearest
"mode step" as ruler. Tasks: image_read, structured_read, perturbation,
repeatability. Baselines (oracle, constant, random, heuristic) calibrate the scale.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from typing import Any

import numpy as np

from psyfi_bench.providers.base import ModelRequest, ModelResponse
from psyfi_bench.providers.registry import make_provider
from psyfi_bench.providers.replay import RecordingProvider
from psyfi_bench.registry import register_family
from psyfi_bench.render.fidelity import perturb
from psyfi_bench.render.soft_raster import sha256_rgba, soft_present_snapshot
from psyfi_bench.runner import FamilyOutput, RunContext
from psyfi_bench.schemas import EnvironmentRecord, FailureRecord, StageRecord, WorkloadManifest
from psyfi_bench.stats import bootstrap_ci, summarize
from psyfi_core.experiences.parameter_mapper import MODE_BIASES, map_parameters
from psyfi_core.visualization.scene_snapshot import build_scene_snapshot

MODES = tuple(MODE_BIASES.keys())  # open, attractor, void, power
PROMPT_REVISION = 1
IMAGE_PROMPT = (
    "This image is a rendering of a parameter field produced by a deterministic simulation instrument. "
    "The field has one of four modes: open (balanced, moderate structure), attractor (dense repeated geometry, "
    "strong symmetry, many crystalline forms), void (sparse, dim, expanded emptiness, few forms), power (bright, "
    "high energy, many large overlapping forms). Intensity runs from 0 (faint, few forms, low opacity) to 1 "
    "(saturated, many forms, high opacity). Estimate the field. Reply with JSON only, exactly of the form "
    '{"mode": "<open|attractor|void|power>", "intensity": <number from 0 to 1>}. No other text.'
)
STRUCTURED_PROMPT = (
    "The JSON below is an immutable scene snapshot generated from a parameter field by a deterministic simulation "
    "instrument. It lists procedural geometry (glyphs, ribbons, metaballs, crystals, volumes), lighting, post flags "
    "and palette. The field's mode and intensity were removed. Modes: open (balanced), attractor (dense repeated "
    "geometry, many crystals, hard metaballs), void (sparse, soft, few forms), power (many large forms, high energy). "
    "Intensity runs from 0 to 1 and scales form counts, radii and energy. Infer the field. Reply with JSON only, "
    'exactly of the form {"mode": "<open|attractor|void|power>", "intensity": <number from 0 to 1>}. No other text.'
)
TASKS = ("image_read", "structured_read", "perturbation", "repeatability")


# --- corpus ---------------------------------------------------------------------


def item_key(substance: str, mode: str, intensity: float, seed: int) -> str:
    return f"{substance}:{mode}:{intensity:g}:{seed}"


def build_items(corpus: dict[str, Any], limit: int | None = None) -> list[dict[str, Any]]:
    substances = list(corpus.get("substances") or ["lsd"])
    modes = list(corpus.get("modes") or MODES)
    intensities = [float(i) for i in (corpus.get("intensities") or [0.5])]
    seeds = [int(s) for s in (corpus.get("seeds") or [42])]
    phase_t = float(corpus.get("phase_t", 0.4))
    tier = str(corpus.get("tier", "balanced"))
    items: list[dict[str, Any]] = []
    for substance in substances:
        for mode in modes:
            for intensity in intensities:
                for seed in seeds:
                    items.append({"key": item_key(substance, mode, intensity, seed), "substance": substance, "mode": mode, "intensity": intensity, "seed": seed, "phase_t": phase_t, "tier": tier})
    if limit is not None:
        # Deterministic stratified subset: round-robin over modes so every mode stays represented.
        by_mode: dict[str, list[dict[str, Any]]] = {}
        for it in items:
            by_mode.setdefault(it["mode"], []).append(it)
        picked: list[dict[str, Any]] = []
        while len(picked) < min(limit, len(items)):
            for mode in modes:
                if by_mode.get(mode):
                    picked.append(by_mode[mode].pop(0))
                if len(picked) >= limit:
                    break
        items = picked
    return items


def oracle_parameters(item: dict[str, Any], mode: str | None = None, intensity: float | None = None) -> dict[str, float]:
    field = map_parameters(
        substance=item["substance"],
        mode=mode or item["mode"],
        intensity=float(item["intensity"] if intensity is None else intensity),
        seed=int(item["seed"]),
        phase_t=float(item.get("phase_t", 0.4)),
        quality_tier=str(item.get("tier", "balanced")),
    )
    return dict(field.parameters)


def item_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    field = map_parameters(
        substance=item["substance"], mode=item["mode"], intensity=float(item["intensity"]), seed=int(item["seed"]),
        phase_t=float(item.get("phase_t", 0.4)), quality_tier=str(item.get("tier", "balanced")),
    ).to_dict()
    return build_scene_snapshot(parameter_field=field, quality_tier=str(item.get("tier", "balanced")), sequence=1, snapshot_id=f"bench:{item['key']}")


def render_item(item: dict[str, Any], size: int) -> np.ndarray:
    return soft_present_snapshot(item_snapshot(item), size)


def structured_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    """The snapshot without the answer: no parameter_field, no simulation, no ids that encode the key."""
    keep = {k: snapshot[k] for k in ("quality_tier", "procedural", "camera", "lighting", "post") if k in snapshot}
    pf = snapshot.get("parameter_field") or {}
    keep["palette"] = pf.get("palette")
    keep["substance"] = pf.get("substance")
    return keep


def corpus_digest(items: list[dict[str, Any]], size: int) -> str:
    h = hashlib.sha256()
    for it in items:
        h.update(it["key"].encode())
        h.update(sha256_rgba(render_item(it, size)).encode())
    return h.hexdigest()


# --- parsing -----------------------------------------------------------------------


def parse_strict(text: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {"parse_ok": False, "mode": None, "intensity": None, "violation": None, "extra_keys": 0}
    if text is None:
        out["violation"] = "no_text"
        return out
    try:
        doc = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        out["violation"] = "not_json"
        return out
    if not isinstance(doc, dict):
        out["violation"] = "not_object"
        return out
    out["extra_keys"] = len(set(doc) - {"mode", "intensity"})
    mode = doc.get("mode")
    intensity = doc.get("intensity")
    if not isinstance(mode, str) or mode not in MODES:
        out["violation"] = "bad_mode"
        return out
    if isinstance(intensity, bool) or not isinstance(intensity, (int, float)):
        out["violation"] = "bad_intensity_type"
        return out
    value = float(intensity)
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        out["violation"] = "intensity_out_of_range"
        return out
    out.update(parse_ok=True, mode=mode, intensity=value)
    return out


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_OBJ = re.compile(r"\{.*?\}", re.S)


def parse_lenient(text: str | None) -> dict[str, Any]:
    """Recovery for diagnostics only: strip fences, find the first object, lowercase the mode, clamp."""
    if text is None:
        return parse_strict(None)
    candidates = [m.group(1) for m in _FENCE.finditer(text)] + [m.group(0) for m in _OBJ.finditer(text)] + [text]
    for cand in candidates:
        try:
            doc = json.loads(cand)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(doc, dict):
            continue
        mode = str(doc.get("mode", "")).strip().lower()
        inten = doc.get("intensity")
        percent = isinstance(inten, str) and inten.strip().endswith("%")
        try:
            value = float(inten.strip().rstrip("%")) if isinstance(inten, str) else float(inten)
        except (TypeError, ValueError):
            continue
        if percent:
            value = value / 100.0
        if mode in MODES and math.isfinite(value):
            return {"parse_ok": True, "mode": mode, "intensity": min(1.0, max(0.0, value)), "violation": None, "extra_keys": 0, "recovered": True}
    return parse_strict(text)


# --- field metrics -------------------------------------------------------------


def l1(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    return round(sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys), 4)


def field_displacement(item: dict[str, Any], model_mode: str, model_intensity: float) -> dict[str, Any]:
    oracle = oracle_parameters(item)
    model = oracle_parameters(item, model_mode, model_intensity)
    steps = {m: l1(oracle, oracle_parameters(item, m, None)) for m in MODES if m != item["mode"]}
    ruler = min(steps.values())
    fde = l1(oracle, model)
    return {
        "fde": fde,
        "mode_steps": steps,
        "mode_step_min": ruler,
        "fde_normalized": round(fde / ruler, 4) if ruler > 0 else None,
        "within_mode_step": fde <= ruler,
        "fde_mode_only": l1(oracle, oracle_parameters(item, model_mode, None)),
        "fde_intensity_only": l1(oracle, oracle_parameters(item, None, model_intensity)),
        "mode_match": model_mode == item["mode"],
        "intensity_abs_error": round(abs(float(model_intensity) - float(item["intensity"])), 4),
    }


def _spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    from scipy.stats import spearmanr

    rho = spearmanr(x, y).statistic
    return None if rho is None or not math.isfinite(rho) else float(rho)


def discriminability(items: list[dict[str, Any]], readings: dict[str, dict[str, float]], *, max_pairs: int = 600, seed: int = 0) -> dict[str, Any]:
    """Spearman ρ between field-space distances (oracle vs oracle) and reading-space distances (reconstructed vs reconstructed)."""
    keys = [it["key"] for it in items if it["key"] in readings]
    if len(keys) < 3:
        return {"pairs": 0, "spearman_rho": None, "mean_reading_distance": None}
    rng = np.random.default_rng(seed)
    pairs = [(i, j) for i in range(len(keys)) for j in range(i + 1, len(keys))]
    if len(pairs) > max_pairs:
        idx = rng.choice(len(pairs), size=max_pairs, replace=False)
        pairs = [pairs[i] for i in idx]
    by_key = {it["key"]: it for it in items}
    oracle = {k: oracle_parameters(by_key[k]) for k in keys}
    fd: list[float] = []
    rd: list[float] = []
    for i, j in pairs:
        fd.append(l1(oracle[keys[i]], oracle[keys[j]]))
        rd.append(l1(readings[keys[i]], readings[keys[j]]))
    return {"pairs": len(pairs), "spearman_rho": _spearman(fd, rd), "mean_field_distance": float(np.mean(fd)), "mean_reading_distance": float(np.mean(rd))}


# --- the run ---------------------------------------------------------------------


def _cost(usage: dict[str, int] | None, pricing: dict[str, Any] | None) -> float | None:
    if not usage or not pricing:
        return None
    inp = float(pricing.get("input_per_million", 0.0)) * usage.get("input_tokens", 0) / 1e6
    out = float(pricing.get("output_per_million", 0.0)) * usage.get("output_tokens", 0) / 1e6
    return inp + out


def _ask(provider: Any, request: ModelRequest) -> ModelResponse:
    try:
        return provider.complete(request)
    except Exception as exc:  # noqa: BLE001 — a provider crash is a row, not an abort
        return ModelResponse(text=None, latency_ms=0.0, provider=getattr(provider, "name", "?"), model=getattr(provider, "model", "?"), locality=getattr(provider, "locality", "remote"), error=f"{type(exc).__name__}: {exc}"[:200])


def _row(item: dict[str, Any], resp: ModelResponse, pricing: dict[str, Any] | None, *, variant: str = "base") -> dict[str, Any]:
    strict = parse_strict(resp.text)
    lenient = parse_lenient(resp.text) if not strict["parse_ok"] else strict
    row: dict[str, Any] = {
        "key": item["key"],
        "variant": variant,
        "reference": {"mode": item["mode"], "intensity": item["intensity"], "substance": item["substance"]},
        "text": (resp.text or "")[:200],
        "provider_error": resp.error,
        "parse_ok": strict["parse_ok"],
        "violation": strict["violation"] if not strict["parse_ok"] else None,
        "recoverable": bool(lenient.get("parse_ok")) and not strict["parse_ok"],
        "extra_keys": strict.get("extra_keys", 0),
        "latency_ms": resp.latency_ms,
        "usage": resp.usage,
        "cost": _cost(resp.usage, pricing),
        "reading": None,
        "reading_lenient": {"mode": lenient["mode"], "intensity": lenient["intensity"]} if lenient.get("parse_ok") else None,
    }
    if strict["parse_ok"]:
        row["reading"] = {"mode": strict["mode"], "intensity": strict["intensity"]}
        row.update(field_displacement(item, strict["mode"], float(strict["intensity"])))
    elif lenient.get("parse_ok"):
        row["lenient"] = field_displacement(item, lenient["mode"], float(lenient["intensity"]))
    return row


def aggregate(rows: list[dict[str, Any]], *, seed: int = 0) -> dict[str, Any]:
    n = len(rows)
    ok = [r for r in rows if r.get("parse_ok")]
    provider_errors = sum(1 for r in rows if r.get("provider_error"))
    agg: dict[str, Any] = {
        "n": n,
        "parsed": len(ok),
        "parse_rate": len(ok) / n if n else None,
        "provider_error_rate": provider_errors / n if n else None,
        "schema_violation_rate": (n - len(ok) - provider_errors) / n if n else None,
        "recoverable_format_violations": sum(1 for r in rows if r.get("recoverable")),
        "extra_keys_rate": (sum(1 for r in rows if r.get("extra_keys")) / n) if n else None,
        "violations": {},
    }
    for r in rows:
        if r.get("violation"):
            agg["violations"][r["violation"]] = agg["violations"].get(r["violation"], 0) + 1
    if ok:
        fde = [r["fde"] for r in ok]
        agg.update(
            {
                "mode_accuracy": sum(1 for r in ok if r["mode_match"]) / len(ok),
                "intensity_mae": float(np.mean([r["intensity_abs_error"] for r in ok])),
                "fde_mean": float(np.mean(fde)),
                "fde_median": float(np.median(fde)),
                "fde_ci95_mean": bootstrap_ci(fde, "mean", seed=seed),
                "fde_normalized_mean": float(np.mean([r["fde_normalized"] for r in ok if r["fde_normalized"] is not None])) if any(r["fde_normalized"] is not None for r in ok) else None,
                "within_mode_step_rate": sum(1 for r in ok if r["within_mode_step"]) / len(ok),
                "fde_mode_only_mean": float(np.mean([r["fde_mode_only"] for r in ok])),
                "fde_intensity_only_mean": float(np.mean([r["fde_intensity_only"] for r in ok])),
            }
        )
    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None and r["latency_ms"] > 0]
    agg["latency_ms"] = summarize(latencies, unit="ms", seed=seed).model_dump() if len(latencies) >= 1 else None
    tokens_in = sum((r.get("usage") or {}).get("input_tokens", 0) for r in rows)
    tokens_out = sum((r.get("usage") or {}).get("output_tokens", 0) for r in rows)
    agg["tokens"] = {"input": tokens_in, "output": tokens_out} if (tokens_in or tokens_out) else None
    costs = [r["cost"] for r in rows if r.get("cost") is not None]
    agg["cost_total"] = float(sum(costs)) if costs else None
    agg["cost_per_valid_result"] = (float(sum(costs)) / len(ok)) if costs and ok else None
    return agg


@register_family("interpretation")
def run_interpretation(manifest: WorkloadManifest, ctx: RunContext, env: EnvironmentRecord) -> FamilyOutput:
    p = {**manifest.params, **ctx.inputs}
    corpus = dict(p.get("corpus") or {})
    size = int(p.get("image_size", 256))
    tasks = [t for t in (p.get("tasks") or TASKS) if t in TASKS]
    max_tokens = int(p.get("max_tokens", 64))
    temperature = float(p.get("temperature", 0.0))
    pricing = ctx.provider_options.get("pricing") or p.get("pricing")
    spec = ctx.provider or p.get("provider") or "heuristic"
    failures: list[FailureRecord] = []
    notes: list[str] = [f"prompt_revision={PROMPT_REVISION}", f"image_size={size}"]

    try:
        base_provider = make_provider(spec, ctx.provider_options)
    except Exception as exc:  # noqa: BLE001
        stage = StageRecord(id="provider", kind="provider", status="skipped", error=f"unsupported: {exc}")
        return FamilyOutput(stages=[stage], metrics={"provider": spec, "skipped": True}, failures=[FailureRecord(stage="provider", category="unsupported", detail=str(exc))])
    provider: Any = RecordingProvider(base_provider) if ctx.provider_options.get("record") else base_provider
    locality = getattr(provider, "locality", "remote")
    measurement_class = "replay" if locality == "replay" else ("synthetic" if locality == "baseline" else "measured")
    notes.append(f"provider={json.dumps(provider.describe(), default=str)}")

    items = build_items(corpus, ctx.limit)
    locks = manifest.references.get("corpus_sha256")
    corpus_lock_ok: bool | None = None
    if locks and ctx.limit is None and not ctx.param_overrides():
        corpus_lock_ok = corpus_digest(items, size) == locks
        if not corpus_lock_ok:
            failures.append(FailureRecord(stage="corpus", category="validation", detail="corpus digest differs from the manifest lock; renderer or mapper changed"))

    images: dict[str, np.ndarray] = {}
    snapshots: dict[str, dict[str, Any]] = {}
    t0 = time.perf_counter()
    for it in items:
        snapshots[it["key"]] = item_snapshot(it)
        images[it["key"]] = soft_present_snapshot(snapshots[it["key"]], size)
    corpus_build_ms = (time.perf_counter() - t0) * 1000

    stages: list[StageRecord] = []
    consecutive_errors = 0
    aborted = False
    readings_image: dict[str, dict[str, float]] = {}
    readings_struct: dict[str, dict[str, float]] = {}
    base_rows_by_key: dict[str, dict[str, Any]] = {}

    def run_task(task: str, requests: list[tuple[dict[str, Any], ModelRequest, str]]) -> StageRecord:
        nonlocal consecutive_errors, aborted
        rows: list[dict[str, Any]] = []
        stage = StageRecord(id=task, kind=task, measurement_class=measurement_class, params={"items": len(requests), "prompt_revision": PROMPT_REVISION, "max_tokens": max_tokens, "temperature": temperature})
        for item, request, variant in requests:
            if aborted or (ctx.cancel is not None and ctx.cancel()):
                stage.status = "cancelled" if not aborted else "failed"
                stage.error = stage.error or "aborted after consecutive provider errors"
                break
            resp = _ask(provider, request)
            row = _row(item, resp, pricing, variant=variant)
            rows.append(row)
            if resp.latency_ms and resp.latency_ms > 0:
                stage.wall_ms.append(resp.latency_ms)
            if resp.error:
                consecutive_errors += 1
                if consecutive_errors >= int(p.get("abort_after_consecutive_errors", 3)) and locality in ("local", "remote"):
                    aborted = True
                    stage.status = "failed"
                    stage.error = f"aborted: {consecutive_errors} consecutive provider errors ({resp.error})"
            else:
                consecutive_errors = 0
        stage.metrics["rows"] = rows
        stage.metrics["summary"] = aggregate(rows, seed=manifest.protocol.bootstrap_seed)
        if stage.wall_ms:
            stage.statistics["latency_ms"] = summarize(stage.wall_ms, unit="ms", resamples=manifest.protocol.bootstrap_resamples, seed=manifest.protocol.bootstrap_seed)
        return stage

    if "image_read" in tasks:
        reqs = [(it, ModelRequest(prompt=IMAGE_PROMPT, images=[images[it["key"]]], max_tokens=max_tokens, temperature=temperature, seed=ctx.seed, metadata={"reference": {"mode": it["mode"], "intensity": it["intensity"]}}), "base") for it in items]
        stage = run_task("image_read", reqs)
        for r in stage.metrics["rows"]:
            base_rows_by_key[r["key"]] = r
            if r.get("reading"):
                it = next(i for i in items if i["key"] == r["key"])
                readings_image[r["key"]] = oracle_parameters(it, r["reading"]["mode"], r["reading"]["intensity"])
        stage.metrics["discriminability"] = discriminability(items, readings_image, seed=manifest.protocol.bootstrap_seed)
        stages.append(stage)

    if "structured_read" in tasks and not aborted:
        reqs = [(it, ModelRequest(prompt=STRUCTURED_PROMPT, structured=structured_view(snapshots[it["key"]]), max_tokens=max_tokens, temperature=temperature, seed=ctx.seed, metadata={"reference": {"mode": it["mode"], "intensity": it["intensity"]}}), "structured") for it in items]
        stage = run_task("structured_read", reqs)
        agree_mode = 0
        agree_n = 0
        d_int: list[float] = []
        for r in stage.metrics["rows"]:
            it = next(i for i in items if i["key"] == r["key"])
            if r.get("reading"):
                readings_struct[r["key"]] = oracle_parameters(it, r["reading"]["mode"], r["reading"]["intensity"])
            base = base_rows_by_key.get(r["key"])
            if base and base.get("reading") and r.get("reading"):
                agree_n += 1
                agree_mode += int(base["reading"]["mode"] == r["reading"]["mode"])
                d_int.append(abs(base["reading"]["intensity"] - r["reading"]["intensity"]))
        stage.metrics["discriminability"] = discriminability(items, readings_struct, seed=manifest.protocol.bootstrap_seed)
        stage.metrics["cross_modal"] = {
            "pairs": agree_n,
            "mode_agreement_rate": agree_mode / agree_n if agree_n else None,
            "intensity_mean_abs_delta": float(np.mean(d_int)) if d_int else None,
            "reading_distance_mean": float(np.mean([l1(readings_image[k], readings_struct[k]) for k in readings_struct if k in readings_image])) if any(k in readings_image for k in readings_struct) else None,
        }
        stages.append(stage)

    if "perturbation" in tasks and not aborted:
        kinds = list(p.get("perturbations") or ["noise", "brightness_up", "brightness_down", "flip_h"])
        subset = build_items(corpus, int(p.get("perturbation_subset", 8)))
        reqs = []
        for it in subset:
            for kind in kinds:
                img = perturb(images[it["key"]], kind, seed=int(it["seed"]), amount=float(p.get("perturbation_amount", 0.02)))
                reqs.append((it, ModelRequest(prompt=IMAGE_PROMPT, images=[img], max_tokens=max_tokens, temperature=temperature, seed=ctx.seed, metadata={"reference": {"mode": it["mode"], "intensity": it["intensity"]}}), kind))
        stage = run_task("perturbation", reqs)
        inv: list[float] = []
        mode_flips = 0
        counted = 0
        for r in stage.metrics["rows"]:
            base = base_rows_by_key.get(r["key"])
            if base and base.get("reading") and r.get("reading"):
                it = next(i for i in subset if i["key"] == r["key"])
                counted += 1
                inv.append(l1(oracle_parameters(it, base["reading"]["mode"], base["reading"]["intensity"]), oracle_parameters(it, r["reading"]["mode"], r["reading"]["intensity"])))
                mode_flips += int(base["reading"]["mode"] != r["reading"]["mode"])
        disc = stages[0].metrics.get("discriminability", {}) if stages else {}
        mean_inv = float(np.mean(inv)) if inv else None
        stage.metrics["invariance"] = {
            "pairs": counted,
            "mean_reading_distance_under_perturbation": mean_inv,
            "mode_flip_rate": (mode_flips / counted) if counted else None,
            "mean_reading_distance_across_fields": disc.get("mean_reading_distance"),
            "invariance_to_discriminability_ratio": (disc["mean_reading_distance"] / mean_inv) if (mean_inv and disc.get("mean_reading_distance") is not None and mean_inv > 0) else None,
            "perturbations": kinds,
        }
        stages.append(stage)

    if "repeatability" in tasks and not aborted:
        rep = dict(p.get("repeatability") or {})
        subset = build_items(corpus, int(rep.get("subset", 6)))
        repeats = int(rep.get("repeats", 3))
        reqs = [(it, ModelRequest(prompt=IMAGE_PROMPT, images=[images[it["key"]]], max_tokens=max_tokens, temperature=temperature, seed=ctx.seed, metadata={"reference": {"mode": it["mode"], "intensity": it["intensity"]}}), f"repeat_{k}") for it in subset for k in range(repeats)]
        stage = run_task("repeatability", reqs)
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in stage.metrics["rows"]:
            if r.get("reading"):
                groups.setdefault(r["key"], []).append(r["reading"])
        exact = 0
        mode_agree = 0
        stds: list[float] = []
        full = 0
        for key, rs in groups.items():
            if len(rs) < 2:
                continue
            full += 1
            modes_set = {x["mode"] for x in rs}
            ints = [x["intensity"] for x in rs]
            mode_agree += int(len(modes_set) == 1)
            exact += int(len(modes_set) == 1 and max(ints) - min(ints) < 1e-9)
            stds.append(float(np.std(ints)))
        stage.metrics["repeatability"] = {"items": full, "repeats": repeats, "exact_agreement_rate": exact / full if full else None, "mode_agreement_rate": mode_agree / full if full else None, "intensity_std_mean": float(np.mean(stds)) if stds else None}
        stages.append(stage)

    if isinstance(provider, RecordingProvider):
        ctx.inputs["_receipt"] = provider.receipt()

    headline: dict[str, Any] = {
        "provider": provider.describe(),
        "locality": locality,
        "prompt_revision": PROMPT_REVISION,
        "corpus": {"items": len(items), "image_size": size, "build_ms": corpus_build_ms, "lock_ok": corpus_lock_ok},
        "tasks": {},
        "aborted": aborted,
    }
    for s in stages:
        summ = dict(s.metrics.get("summary") or {})
        for k in ("discriminability", "cross_modal", "invariance", "repeatability"):
            if k in s.metrics:
                summ[k] = s.metrics[k]
        headline["tasks"][s.id] = summ
    img = headline["tasks"].get("image_read") or {}
    headline["fde_mean"] = img.get("fde_mean")
    headline["within_mode_step_rate"] = img.get("within_mode_step_rate")
    headline["mode_accuracy"] = img.get("mode_accuracy")
    headline["parse_rate"] = img.get("parse_rate")
    return FamilyOutput(stages=stages, metrics=headline, failures=failures, measurement_class=measurement_class, notes=notes)


def lock_references(manifest: WorkloadManifest, ctx: RunContext | None = None) -> WorkloadManifest:
    items = build_items(dict(manifest.params.get("corpus") or {}))
    refs = dict(manifest.references)
    refs["corpus_sha256"] = corpus_digest(items, int(manifest.params.get("image_size", 256)))
    refs["corpus_items"] = len(items)
    refs["oracle_modes"] = sorted({it["mode"] for it in items})
    refs["locked_with"] = {"raster": "psyfi_bench.render.soft_raster", "prompt_revision": PROMPT_REVISION}
    return manifest.model_copy(update={"references": refs})
