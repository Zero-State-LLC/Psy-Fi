"""Family B — rendering. Two execution classes:

* ``soft``   — Python CPU raster of scene snapshots (bit-identical to the TS soft-present).
* ``webgpu`` — a browser capture (``psyfi.bench.gpu_capture.v1``) produced by the
  additive ``bench.html`` runner in the GPU package, scored here. Frame times are
  reported as the browser measured them; fidelity is compared only within the
  same device against that device's Ultra capture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from psyfi_bench.registry import register_family
from psyfi_bench.render.adapter import classify_adapter
from psyfi_bench.render.fidelity import compare, decode_png_base64, summarize_frame
from psyfi_bench.render.soft_raster import sha256_rgba, soft_present_snapshot
from psyfi_bench.runner import FamilyOutput, RunContext, measure_stage
from psyfi_bench.schemas import EnvironmentRecord, FailureRecord, GpuCapture, StageRecord, WorkloadManifest
from psyfi_bench.stats import fps_from_frame_ms, frame_pacing, low_1pct_fps, summarize, sustained_drift
from psyfi_core.experiences.parameter_mapper import map_parameters
from psyfi_core.visualization.scene_snapshot import build_scene_snapshot

TIER_ORDER = ("ultra", "high", "balanced", "battery")
# From packages/psyfi-gpu-renderer/src/contracts/QualityTier.ts (targetFrameMs). Manifests may override.
DEFAULT_TIER_TARGET_MS = {"ultra": 8.3, "high": 16.7, "balanced": 16.7, "battery": 33.0}
G4_CASES = [
    {"key": "lsd_open_42", "substance": "lsd", "mode": "open", "seed": 42, "intensity": 0.75},
    {"key": "psilocybin_attractor_7", "substance": "psilocybin", "mode": "attractor", "seed": 7, "intensity": 0.6},
    {"key": "dmt_void_99", "substance": "dmt", "mode": "void", "seed": 99, "intensity": 0.85},
]


def case_key(case: dict[str, Any]) -> str:
    return str(case.get("key") or f"{case['substance']}_{case['mode']}_{case['seed']}")


def build_case_snapshot(case: dict[str, Any], tier: str, *, phase_t: float = 0.4) -> dict[str, Any]:
    """ParameterField + immutable scene snapshot for one case at one tier (no simulation, no assets)."""
    field = map_parameters(
        substance=str(case["substance"]),
        mode=str(case["mode"]),
        intensity=float(case["intensity"]),
        seed=int(case["seed"]),
        quality_tier=tier,
        phase_t=float(case.get("phase_t", phase_t)),
        neutral_view=bool(case.get("neutral_view", False)),
    ).to_dict()
    return build_scene_snapshot(
        parameter_field=field,
        quality_tier=tier,
        sequence=1,
        snapshot_id=f"bench:{case_key(case)}:{tier}",
    )


def soft_stage_fn(case: dict[str, Any], tier: str, size: int, splits: dict[str, list[float]]):
    import time

    def fn(should_cancel):
        t0 = time.perf_counter_ns()
        snap = build_case_snapshot(case, tier)
        t1 = time.perf_counter_ns()
        if should_cancel():
            raise InterruptedError("cancelled before raster")
        rgba = soft_present_snapshot(snap, size)
        t2 = time.perf_counter_ns()
        splits.setdefault("snapshot_ms", []).append((t1 - t0) / 1e6)
        splits.setdefault("raster_ms", []).append((t2 - t1) / 1e6)
        return rgba

    return fn


def _soft_stages(manifest: WorkloadManifest, ctx: RunContext) -> list[dict[str, Any]]:
    p = {**manifest.params, **ctx.inputs}
    cases = p.get("cases") or G4_CASES
    sizes = [int(s) for s in (p.get("sizes") or [64])]
    tiers = [str(t) for t in (p.get("tiers") or ["ultra", "balanced", "battery"])]
    pts: list[dict[str, Any]] = []
    for case in cases:
        for size in sizes:
            for tier in tiers:
                pts.append({"id": f"{case_key(case)}.{tier}.{size}", "case": case, "tier": tier, "size": size})
    if ctx.limit is not None:
        pts = pts[: max(1, ctx.limit)]
    return pts


def run_soft(manifest: WorkloadManifest, ctx: RunContext, env: EnvironmentRecord) -> FamilyOutput:
    protocol = ctx.protocol(manifest)
    locks: dict[str, str] = dict(manifest.references.get("sha256", {}) or {})
    stages: list[StageRecord] = []
    frames: dict[str, np.ndarray] = {}
    for pt in _soft_stages(manifest, ctx):
        splits: dict[str, list[float]] = {}
        case, tier, size = pt["case"], pt["tier"], pt["size"]

        def metrics_fn(result, wall_ms, _splits=splits, _size=size):
            med_r = float(np.median(_splits.get("raster_ms", [float("nan")])))
            med_s = float(np.median(_splits.get("snapshot_ms", [float("nan")])))
            mp = (_size * _size) / 1e6
            return {
                "pixels": _size * _size,
                "snapshot_ms_median": med_s,
                "raster_ms_median": med_r,
                "raster_ms_per_megapixel": med_r / mp if mp else float("nan"),
                "frame": summarize_frame(result) if isinstance(result, np.ndarray) else None,
            }

        stage = measure_stage(
            stage_id=pt["id"],
            kind="soft_raster",
            params={"case": case, "tier": tier, "size": size, "execution_class": "soft"},
            fn=soft_stage_fn(case, tier, size, splits),
            protocol=protocol,
            quantization=manifest.tolerances.quantization,
            reference_digest=None,
            digest_fn=lambda r: r if isinstance(r, np.ndarray) else None,
            metrics_fn=metrics_fn,
            cancel=ctx.cancel,
        )
        if stage.status == "ok" and stage.metrics.get("frame"):
            sha = stage.metrics["frame"]["sha256"]
            if pt["id"] in locks:
                stage.metrics["reference_match"] = locks[pt["id"]] == sha
                if stage.determinism:
                    stage.determinism.reference_match = locks[pt["id"]] == sha
            frames[pt["id"]] = None  # placeholder; filled below from a fresh deterministic raster
        stages.append(stage)

    # Fidelity vs the Ultra raster of the same case/size (deterministic, so re-raster once).
    by_key: dict[tuple[str, int], dict[str, np.ndarray]] = {}
    for s in stages:
        if s.status != "ok":
            continue
        case, tier, size = s.params["case"], s.params["tier"], s.params["size"]
        by_key.setdefault((case_key(case), size), {})[tier] = soft_present_snapshot(build_case_snapshot(case, tier), size)
    for s in stages:
        if s.status != "ok":
            continue
        case, tier, size = s.params["case"], s.params["tier"], s.params["size"]
        group = by_key.get((case_key(case), size), {})
        if "ultra" in group and tier in group:
            s.metrics["fidelity_vs_ultra"] = compare(group["ultra"], group[tier])

    ok = [s for s in stages if s.status == "ok"]
    per_tier: dict[str, Any] = {}
    for tier in TIER_ORDER:
        rows = [s for s in ok if s.params["tier"] == tier]
        if not rows:
            continue
        per_tier[tier] = {
            "stages": len(rows),
            "raster_ms_per_megapixel_median": float(np.median([s.metrics["raster_ms_per_megapixel"] for s in rows])),
            "ssim_vs_ultra_mean": float(np.mean([s.metrics["fidelity_vs_ultra"]["ssim"] for s in rows if "fidelity_vs_ultra" in s.metrics])) if any("fidelity_vs_ultra" in s.metrics for s in rows) else None,
        }
    parity = ts_golden_parity(stages)
    metrics = {
        "execution_class": "soft",
        "per_tier": per_tier,
        "cross_language_parity": parity,
        "determinism": {
            "all_bitwise_identical_across_repeats": all(s.determinism.bitwise_identical_across_repeats for s in ok if s.determinism) if ok else None,
            "reference_locks": len(locks),
            "reference_mismatches": [s.id for s in ok if s.metrics.get("reference_match") is False],
        },
        "note": "The soft raster ignores post-processing flags; ultra, high and balanced tiers raster identically. Tier fidelity is meaningful for the webgpu execution class.",
    }
    return FamilyOutput(stages=stages, metrics=metrics, determinism=metrics["determinism"], notes=["execution_class=soft"])


def ts_golden_parity(stages: list[StageRecord] | None = None, size: int | None = None) -> dict[str, Any]:
    """Raster the TypeScript golden fixture snapshots with the Python raster and compare SHA-256.

    This is the cross-language determinism check: same snapshot document in, same pixels out.
    It uses the fixture snapshots themselves (not rebuilt ones) so a mapper change cannot mask
    or fake a raster divergence.
    """
    from psyfi_bench.environment import REPO_ROOT

    fixtures = REPO_ROOT / "packages" / "psyfi-gpu-renderer" / "fixtures" / "pixel-goldens"
    golden_path = fixtures / "g4_pixel_goldens.v1.json"
    index_path = fixtures / "index.json"
    if not golden_path.exists() or not index_path.exists():
        return {"available": False, "reason": "TS pixel goldens fixture not found"}
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    by_key = {c["key"]: c["metrics"] for c in golden.get("cases", [])}
    px = int(size or golden.get("size", 64))
    compared = matched = 0
    mismatched: list[str] = []
    for case in index.get("cases", []):
        key = case.get("key")
        if key not in by_key:
            continue
        snap = json.loads((fixtures / case["file"]).read_text(encoding="utf-8"))
        rgba = soft_present_snapshot(snap, px)
        compared += 1
        if sha256_rgba(rgba) == by_key[key]["sha256"]:
            matched += 1
        else:
            mismatched.append(key)
    return {"available": True, "size": px, "compared": compared, "matched": matched, "mismatched": mismatched, "fixture": str(golden_path.relative_to(REPO_ROOT)), "note": "Python soft raster vs packages/psyfi-gpu-renderer soft-present goldens (same fixture snapshots)"}


# --- webgpu capture scoring --------------------------------------------------


def load_capture(source: str | Path | dict[str, Any] | GpuCapture) -> GpuCapture:
    if isinstance(source, GpuCapture):
        return source
    if isinstance(source, dict):
        return GpuCapture.model_validate(source)
    return GpuCapture.model_validate(json.loads(Path(source).read_text(encoding="utf-8")))


def score_capture(capture: GpuCapture, manifest: WorkloadManifest, env: EnvironmentRecord, ctx: RunContext | None = None) -> FamilyOutput:
    p = dict(manifest.params)
    targets = {**DEFAULT_TIER_TARGET_MS, **(p.get("tier_targets_ms") or {})}
    protocol = (ctx or RunContext()).protocol(manifest)
    stages: list[StageRecord] = []
    failures: list[FailureRecord] = []
    thumbs: dict[str, dict[str, np.ndarray]] = {}
    for cs in capture.stages:
        stage = StageRecord(
            id=cs.id,
            kind="webgpu_frames",
            measurement_class=capture.measurement_class,
            params={"tier": cs.tier, "snapshot_key": cs.snapshot_key, "requested_frames": cs.requested_frames, "warmup_frames": cs.warmup_frames, "execution_class": "webgpu"},
            wall_ms=list(cs.frames_ms),
        )
        frames = [f for f in cs.frames_ms if np.isfinite(f) and f > 0]
        if len(frames) < 2:
            stage.status = "failed"
            stage.error = "ValueError: fewer than two finite frame samples"
            stages.append(stage)
            continue
        stage.statistics["frame_ms"] = summarize(frames, unit="ms", resamples=protocol.bootstrap_resamples, seed=protocol.bootstrap_seed)
        target = float(targets.get(cs.tier, DEFAULT_TIER_TARGET_MS["balanced"]))
        target_fps = 1000.0 / target
        avg_fps = fps_from_frame_ms(frames)
        low = low_1pct_fps(frames)
        p95 = float(np.percentile(frames, 95))
        stage.metrics.update(
            {
                "frames": len(frames),
                "duration_ms": cs.duration_ms,
                "fps_avg": avg_fps,
                "fps_1pct_low": low,
                "frame_ms_p50": float(np.percentile(frames, 50)),
                "frame_ms_p95": p95,
                "frame_ms_p99": float(np.percentile(frames, 99)),
                "frame_ms_max": float(np.max(frames)),
                "frame_ms_mean": float(np.mean(frames)),
                "pacing": frame_pacing(frames),
                "tier_target_ms": target,
                "p95_over_target": p95 / target,
                # Same rule as measureUltraFps/ultraFpsMatrix.ts evaluateFpsSample.
                "budget_ok": bool(avg_fps + 1e-6 >= target_fps and low + 1e-6 >= 0.9 * target_fps and p95 <= target * 1.15),
                "draw_calls": cs.draw_calls,
                "triangles": cs.triangles,
                "js_heap_bytes": cs.js_heap_bytes,
            }
        )
        if cs.js_errors:
            stage.metrics["js_errors"] = cs.js_errors
            stage.metrics["warning"] = f"{cs.js_errors} uncaught errors during the measured window; frames are not trustworthy"
            stage.status = "failed"
            stage.error = f"ValueError: {cs.js_errors} uncaught renderer errors during measurement"
        if len(frames) >= 8 and (cs.requested_frames >= 600 or "sustained" in cs.id):
            stage.metrics["sustained"] = sustained_drift(frames)
        if cs.gpu_ms:
            gpu = [g for g in cs.gpu_ms if np.isfinite(g) and g >= 0]
            if gpu:
                stage.statistics["gpu_ms"] = summarize(gpu, unit="ms", resamples=protocol.bootstrap_resamples, seed=protocol.bootstrap_seed)
                stage.metrics["gpu_ms_p50"] = float(np.percentile(gpu, 50))
        else:
            stage.metrics["gpu_ms_unavailable"] = "timestamp-query not exposed by this adapter/browser"
        if cs.thumbnail_png_base64:
            try:
                rgba = decode_png_base64(cs.thumbnail_png_base64)
                thumbs.setdefault(cs.snapshot_key, {})[cs.tier] = rgba
                stage.metrics["frame"] = summarize_frame(rgba)
            except Exception as exc:  # noqa: BLE001
                stage.metrics["thumbnail_error"] = f"{type(exc).__name__}: {exc}"
        stages.append(stage)

    for s in stages:
        if s.status != "ok":
            continue
        group = thumbs.get(s.params["snapshot_key"], {})
        if "ultra" in group and s.params["tier"] in group:
            s.metrics["fidelity_vs_ultra"] = compare(group["ultra"], group[s.params["tier"]])
            ms = s.metrics.get("frame_ms_p50")
            if ms:
                s.metrics["ssim_per_ms"] = s.metrics["fidelity_vs_ultra"]["ssim"] / ms

    ok = [s for s in stages if s.status == "ok"]
    per_tier: dict[str, Any] = {}
    for tier in TIER_ORDER:
        rows = [s for s in ok if s.params["tier"] == tier]
        if rows:
            per_tier[tier] = {
                "stages": len(rows),
                "fps_avg_median": float(np.median([s.metrics["fps_avg"] for s in rows])),
                "fps_1pct_low_median": float(np.median([s.metrics["fps_1pct_low"] for s in rows])),
                "frame_ms_p95_median": float(np.median([s.metrics["frame_ms_p95"] for s in rows])),
                "budget_ok_all": all(s.metrics["budget_ok"] for s in rows),
                "ssim_vs_ultra_mean": float(np.mean([s.metrics["fidelity_vs_ultra"]["ssim"] for s in rows if "fidelity_vs_ultra" in s.metrics])) if any("fidelity_vs_ultra" in s.metrics for s in rows) else None,
            }
    adapter = classify_adapter((capture.browser or {}).get("adapter"))
    env.browser = {**(capture.browser or {}), "adapter_classified": adapter}
    if adapter["hardware_class"] in ("discrete", "integrated"):
        env.hardware_class = adapter["hardware_class"]  # type: ignore[assignment]
    sustained = [s for s in ok if "sustained" in s.metrics]
    metrics = {
        "execution_class": "webgpu",
        "measurement_class": capture.measurement_class,
        "adapter": adapter,
        "timestamp_query": bool((capture.browser or {}).get("features", {}).get("timestamp_query")) if isinstance((capture.browser or {}).get("features"), dict) else None,
        "per_tier": per_tier,
        "sustained": {s.id: s.metrics["sustained"] for s in sustained} if sustained else None,
        "aborted": capture.aborted,
        "note": "Frame times are the browser's wall-clock requestAnimationFrame spacing after warm-up. Tier fidelity compares each tier to this device's Ultra capture; cross-device fidelity is not computed.",
    }
    if capture.measurement_class != "measured":
        metrics["warning"] = f"this capture is {capture.measurement_class}; it is not hardware evidence"
    return FamilyOutput(stages=stages, metrics=metrics, failures=failures, measurement_class=capture.measurement_class)


@register_family("render")
def run_render(manifest: WorkloadManifest, ctx: RunContext, env: EnvironmentRecord) -> FamilyOutput:
    p = {**manifest.params, **ctx.inputs}
    execution_class = p.get("execution_class", "soft")
    if execution_class == "soft":
        return run_soft(manifest, ctx, env)
    if execution_class == "webgpu":
        source = ctx.inputs.get("capture")
        if source is None:
            stage = StageRecord(id="capture", kind="webgpu_frames", status="skipped", error="unsupported: needs a browser capture (run /gpu/bench.html, then `psyfi-bench ingest <capture.json>`)")
            return FamilyOutput(stages=[stage], metrics={"execution_class": "webgpu", "skipped": True}, failures=[FailureRecord(stage="capture", category="unsupported", detail="no browser capture supplied")])
        capture = load_capture(source)
        if capture.manifest_id != manifest.id:
            return FamilyOutput(stages=[StageRecord(id="capture", kind="webgpu_frames", status="failed", error=f"ValueError: capture is for manifest {capture.manifest_id!r}, not {manifest.id!r}")], metrics={"execution_class": "webgpu"}, failures=[FailureRecord(stage="capture", category="validation", detail="manifest id mismatch")])
        if capture.manifest_hash and capture.manifest_hash != manifest.manifest_hash:
            ctx.notes.append(f"capture manifest_hash {capture.manifest_hash} differs from current {manifest.manifest_hash}; comparisons across hashes are invalid")
        return score_capture(capture, manifest, env, ctx)
    raise ValueError(f"unknown render execution_class {execution_class!r}")


def lock_references(manifest: WorkloadManifest, ctx: RunContext | None = None) -> WorkloadManifest:
    ctx = ctx or RunContext()
    locks: dict[str, str] = {}
    for pt in _soft_stages(manifest, ctx):
        rgba = soft_present_snapshot(build_case_snapshot(pt["case"], pt["tier"]), pt["size"])
        locks[pt["id"]] = sha256_rgba(rgba)
    refs = dict(manifest.references)
    refs["sha256"] = locks
    refs["locked_with"] = {"raster": "psyfi_bench.render.soft_raster", "parity": "packages/psyfi-gpu-renderer/src/goldens/softPresent.ts"}
    return manifest.model_copy(update={"references": refs})
