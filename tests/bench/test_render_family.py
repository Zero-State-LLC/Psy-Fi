"""Family B: soft raster parity with the TS goldens, tier fidelity, and webgpu capture scoring."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from psyfi_bench.families.render import G4_CASES, build_case_snapshot, load_capture, lock_references, score_capture
from psyfi_bench.registry import load_manifest
from psyfi_bench.render.adapter import classify_adapter
from psyfi_bench.render.fidelity import block_resize, compare, decode_png_base64, encode_png_base64, perturb, ssim
from psyfi_bench.render.soft_raster import rgba_histogram, sha256_rgba, soft_present_snapshot
from psyfi_bench.runner import RunContext, run_workload
from psyfi_bench.schemas import GpuCapture, Protocol
from psyfi_bench.timing import utc_now_iso

ROOT = Path(__file__).resolve().parents[2]
GOLDENS = ROOT / "packages" / "psyfi-gpu-renderer" / "fixtures" / "pixel-goldens"


def test_python_raster_is_bit_identical_to_the_typescript_goldens() -> None:
    golden = json.loads((GOLDENS / "g4_pixel_goldens.v1.json").read_text())
    index = json.loads((GOLDENS / "index.json").read_text())
    assert golden["size"] == 64
    for case, gcase in zip(index["cases"], golden["cases"]):
        snap = json.loads((GOLDENS / case["file"]).read_text())
        rgba = soft_present_snapshot(snap, 64)
        assert rgba.shape == (64, 64, 4) and rgba.dtype == np.uint8
        assert sha256_rgba(rgba) == gcase["metrics"]["sha256"], case["key"]
        assert rgba_histogram(rgba) == gcase["metrics"]["histogram"]["bins"], case["key"]
        neutral = soft_present_snapshot({**snap, "parameter_field": {**snap["parameter_field"], "neutral_view": True}}, 64)
        assert sha256_rgba(neutral) != sha256_rgba(rgba)
        with_assets = soft_present_snapshot({**snap, "assets": {**snap.get("assets", {}), "ktx2": [{"id": "g", "url": "/x", "role": "ground"}]}}, 64)
        assert sha256_rgba(with_assets) != sha256_rgba(rgba)


def test_fidelity_metrics_behave() -> None:
    a = soft_present_snapshot(build_case_snapshot(G4_CASES[0], "ultra"), 128)
    same = compare(a, a.copy())
    assert same["rmse"] == 0.0 and same["ssim"] == pytest.approx(1.0) and same["histogram_l1"] == 0.0
    noisy = perturb(a, "noise", seed=1, amount=0.05)
    diff = compare(a, noisy)
    assert 0 < diff["rmse"] < 0.2 and diff["ssim"] < 1.0
    assert compare(a, perturb(a, "flip_h"))["rmse"] > 0
    assert compare(a, block_resize(soft_present_snapshot(build_case_snapshot(G4_CASES[0], "ultra"), 256), 128))["ssim"] > 0.5
    rt = decode_png_base64(encode_png_base64(a))
    assert np.array_equal(rt, a)
    with pytest.raises(ValueError):
        perturb(a, "teleport")
    assert ssim(a, a) == pytest.approx(1.0)


def test_soft_render_workload_runs_with_locks_and_parity() -> None:
    manifest = load_manifest("render.soft.g4").model_copy(update={"protocol": Protocol(warmup_runs=1, repeats=2, memory_probe=False, bootstrap_resamples=200)})
    ctx = RunContext(inputs={"sizes": [64], "tiers": ["ultra", "battery"]}, include_gpu_env=False)
    result = run_workload(manifest, ctx)
    assert result.status == "complete", result.failures
    assert len(result.stages) == 6
    for s in result.stages:
        assert s.status == "ok"
        assert s.metrics["raster_ms_median"] > 0
        assert s.metrics["frame"]["sha256"]
        assert s.metrics["reference_match"] is True
        assert "fidelity_vs_ultra" in s.metrics
        if s.params["tier"] == "ultra":
            assert s.metrics["fidelity_vs_ultra"]["ssim"] == pytest.approx(1.0)
    battery = [s for s in result.stages if s.params["tier"] == "battery"]
    assert any(s.metrics["fidelity_vs_ultra"]["rmse"] > 0 for s in battery), "battery tier must differ from ultra"
    parity = result.metrics["cross_language_parity"]
    assert parity["available"] and parity["compared"] >= 1 and parity["matched"] == parity["compared"]
    assert result.metrics["determinism"]["all_bitwise_identical_across_repeats"] is True


def test_render_locks_are_current() -> None:
    manifest = load_manifest("render.soft.g4")
    assert lock_references(manifest).references["sha256"] == manifest.references["sha256"]


def _capture(measurement_class: str = "synthetic") -> GpuCapture:
    rng = np.random.default_rng(0)
    stages = []
    for key_case in G4_CASES[:1]:
        for tier, base in (("ultra", 7.5), ("balanced", 9.0), ("battery", 20.0)):
            frames = list(np.clip(rng.normal(base, 0.4, 240), 1, None))
            frames[10] = base * 3  # one stutter
            thumb = encode_png_base64(soft_present_snapshot(build_case_snapshot(key_case, tier), 128))
            stages.append({"id": f"{key_case['key']}.{tier}", "tier": tier, "snapshot_key": key_case["key"], "requested_frames": 240, "warmup_frames": 60, "frames_ms": frames, "gpu_ms": list(np.clip(rng.normal(base * 0.6, 0.2, 240), 0, None)) if tier == "ultra" else None, "draw_calls": 30, "duration_ms": float(sum(frames)), "thumbnail_png_base64": thumb})
    stages.append({"id": "sustained.lsd_open_42.ultra", "tier": "ultra", "snapshot_key": "lsd_open_42", "requested_frames": 1800, "warmup_frames": 60, "frames_ms": list(7.5 + np.arange(1800) * 0.001), "duration_ms": 14000.0})
    return GpuCapture(captured_at=utc_now_iso(), manifest_id="render.webgpu.tiers", measurement_class=measurement_class, browser={"user_agent": "test", "adapter": {"vendor": "nvidia", "description": "NVIDIA GeForce RTX 4070 SUPER", "architecture": "ada-lovelace"}, "features": {"timestamp_query": True}}, stages=stages)


def test_webgpu_capture_scoring_is_labelled_and_complete(tmp_path: Path) -> None:
    manifest = load_manifest("render.webgpu.tiers")
    capture = _capture("synthetic")
    path = tmp_path / "cap.json"
    path.write_text(json.dumps(capture.model_dump(by_alias=True)))
    assert load_capture(path).manifest_id == "render.webgpu.tiers"
    result = run_workload(manifest, RunContext(inputs={"capture": str(path)}, include_gpu_env=False))
    assert result.status == "complete", result.failures
    assert result.measurement_class == "synthetic"
    assert "warning" in result.metrics
    ultra = next(s for s in result.stages if s.id == "lsd_open_42.ultra")
    assert ultra.measurement_class == "synthetic"
    assert ultra.metrics["fps_avg"] == pytest.approx(1000.0 / np.mean(ultra.wall_ms))
    assert ultra.metrics["pacing"]["stutter_frames"] >= 1
    assert "gpu_ms" in ultra.statistics
    assert ultra.metrics["fidelity_vs_ultra"]["ssim"] == pytest.approx(1.0)
    battery = next(s for s in result.stages if s.id == "lsd_open_42.battery")
    assert battery.metrics["fidelity_vs_ultra"]["rmse"] > 0
    assert battery.metrics["tier_target_ms"] == 33.0
    assert "gpu_ms_unavailable" in battery.metrics
    sustained = next(s for s in result.stages if s.id.startswith("sustained"))
    assert sustained.metrics["sustained"]["slope_ms_per_1000_frames"] == pytest.approx(1.0, rel=0.05)
    assert result.metrics["adapter"]["hardware_class"] == "discrete"
    assert result.environment.hardware_class == "discrete"
    assert ultra.metrics["budget_ok"] is True
    # The sustained stage drifts from 7.5 to 9.3 ms: its average falls under the 120 fps Ultra target,
    # so the per-tier roll-up must report the budget as not met. Drift is caught, not hidden.
    assert sustained.metrics["budget_ok"] is False
    assert result.metrics["per_tier"]["ultra"]["budget_ok_all"] is False


def test_webgpu_without_capture_is_skipped_and_mismatch_fails() -> None:
    manifest = load_manifest("render.webgpu.tiers")
    skipped = run_workload(manifest, RunContext(include_gpu_env=False))
    assert skipped.stages[0].status == "skipped"
    assert skipped.failures[0].category == "unsupported"
    wrong = _capture().model_copy(update={"manifest_id": "render.soft.g4"})
    bad = run_workload(manifest, RunContext(inputs={"capture": wrong.model_dump(by_alias=True)}, include_gpu_env=False))
    assert bad.status == "failed" and bad.failures[0].category == "validation"


def test_adapter_classification() -> None:
    assert classify_adapter({"vendor": "nvidia", "description": "NVIDIA GeForce RTX 5060"})["perf_band"] == "ultra"
    assert classify_adapter({"vendor": "apple", "description": "Apple M5"})["hardware_class"] == "integrated"
    assert classify_adapter({"vendor": "apple", "description": "Apple M3 Max"})["perf_band"] == "ultra"
    assert classify_adapter({"vendor": "intel", "description": "Intel(R) UHD Graphics 630"})["perf_band"] == "integrated"
    assert classify_adapter({"vendor": "amd", "description": "AMD Radeon RX 7800 XT"})["hardware_class"] == "discrete"
    assert classify_adapter(None)["vendor"] == "unknown"
