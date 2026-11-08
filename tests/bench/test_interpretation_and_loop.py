"""Family C and D: corpus locks, parsing, FDE, baselines, abort policy, and the FieldLoop."""

from __future__ import annotations

import json

import httpx
import numpy as np
import pytest

from psyfi_bench.families.interpretation import (
    IMAGE_PROMPT,
    MODES,
    STRUCTURED_PROMPT,
    aggregate,
    build_items,
    corpus_digest,
    discriminability,
    field_displacement,
    lock_references,
    oracle_parameters,
    parse_lenient,
    parse_strict,
    structured_view,
    item_snapshot,
)
from psyfi_bench.providers.http import OpenAICompatProvider
from psyfi_bench.registry import load_manifest
from psyfi_bench.runner import RunContext, run_workload
from psyfi_bench.schemas import Protocol


def test_corpus_is_deterministic_and_locked() -> None:
    smoke = load_manifest("interpretation.fieldread.smoke")
    items = build_items(smoke.params["corpus"])
    assert len(items) == smoke.references["corpus_items"] == 8
    assert corpus_digest(items, smoke.params["image_size"]) == smoke.references["corpus_sha256"]
    assert lock_references(smoke).references["corpus_sha256"] == smoke.references["corpus_sha256"]
    full = load_manifest("interpretation.fieldread")
    assert full.references["corpus_items"] == 96
    sub = build_items(full.params["corpus"], limit=4)
    assert [i["mode"] for i in sub] == list(MODES), "limited subsets stay stratified by mode"


def test_structured_view_removes_the_answer() -> None:
    item = build_items(load_manifest("interpretation.fieldread.smoke").params["corpus"])[0]
    view = structured_view(item_snapshot(item))
    assert "parameter_field" not in view and "simulation" not in view
    assert "procedural" in view and "palette" in view
    blob = json.dumps(view)
    assert item["mode"] not in blob.replace(item["substance"], "") or item["mode"] == "open"


def test_parsers() -> None:
    ok = parse_strict('{"mode": "void", "intensity": 0.25}')
    assert ok["parse_ok"] and ok["mode"] == "void" and ok["intensity"] == 0.25
    assert parse_strict('{"mode": "Void", "intensity": 0.25}')["violation"] == "bad_mode"
    assert parse_strict('{"mode": "void", "intensity": 25}')["violation"] == "intensity_out_of_range"
    assert parse_strict('{"mode": "void", "intensity": "0.2"}')["violation"] == "bad_intensity_type"
    assert parse_strict("sure! here")["violation"] == "not_json"
    assert parse_strict("[1]")["violation"] == "not_object"
    assert parse_strict(None)["violation"] == "no_text"
    assert parse_strict('{"mode": "void", "intensity": 0.2, "why": "x"}')["extra_keys"] == 1
    fenced = parse_lenient('```json\n{"mode": "Void", "intensity": "40%"}\n```')
    assert fenced["parse_ok"] and fenced["mode"] == "void" and fenced["intensity"] == pytest.approx(0.4)
    assert parse_lenient("nothing here")["parse_ok"] is False


def test_field_displacement_uses_the_mode_step_ruler() -> None:
    item = {"key": "k", "substance": "lsd", "mode": "void", "intensity": 0.5, "seed": 42, "phase_t": 0.4, "tier": "balanced"}
    same = field_displacement(item, "void", 0.5)
    assert same["fde"] == 0.0 and same["within_mode_step"] and same["mode_match"]
    moved = field_displacement(item, "power", 0.5)
    assert moved["fde"] == moved["mode_steps"]["power"] > 0
    assert moved["fde_intensity_only"] == 0.0
    nudged = field_displacement(item, "void", 0.55)
    assert 0 < nudged["fde"] and nudged["fde_mode_only"] == 0.0 and nudged["intensity_abs_error"] == pytest.approx(0.05)
    assert set(moved["mode_steps"]) == {"open", "attractor", "power"}
    assert oracle_parameters(item) == oracle_parameters(item, "void", 0.5)


def test_discriminability_is_one_for_the_oracle_and_near_zero_for_noise() -> None:
    items = build_items(load_manifest("interpretation.fieldread").params["corpus"], limit=24)
    oracle = {it["key"]: oracle_parameters(it) for it in items}
    assert discriminability(items, oracle)["spearman_rho"] == pytest.approx(1.0)
    rng = np.random.default_rng(0)
    noise = {it["key"]: oracle_parameters(it, MODES[int(rng.integers(0, 4))], float(rng.uniform())) for it in items}
    assert abs(discriminability(items, noise)["spearman_rho"]) < 0.5
    assert discriminability(items[:2], oracle)["pairs"] == 0


def test_aggregate_counts_violations_and_costs() -> None:
    rows = [
        {"parse_ok": True, "fde": 0.5, "mode_match": True, "intensity_abs_error": 0.1, "fde_normalized": 0.4, "within_mode_step": True, "fde_mode_only": 0.0, "fde_intensity_only": 0.5, "latency_ms": 100, "usage": {"input_tokens": 100, "output_tokens": 10}, "cost": 0.001},
        {"parse_ok": False, "violation": "not_json", "latency_ms": 90, "usage": None, "cost": None, "recoverable": True},
        {"parse_ok": False, "violation": None, "provider_error": "timeout", "latency_ms": 0},
    ]
    agg = aggregate(rows)
    assert agg["n"] == 3 and agg["parsed"] == 1
    assert agg["schema_violation_rate"] == pytest.approx(1 / 3) and agg["provider_error_rate"] == pytest.approx(1 / 3)
    assert agg["violations"] == {"not_json": 1}
    assert agg["recoverable_format_violations"] == 1
    assert agg["cost_per_valid_result"] == pytest.approx(0.001)
    assert agg["tokens"] == {"input": 100, "output": 10}


def test_smoke_corpus_with_every_baseline() -> None:
    manifest = load_manifest("interpretation.fieldread.smoke")
    results = {spec: run_workload(manifest, RunContext(provider=spec, include_gpu_env=False)) for spec in ("oracle", "constant", "random:1", "heuristic")}
    for spec, r in results.items():
        assert r.status == "complete", (spec, r.failures)
        assert r.measurement_class == "synthetic"
        assert [s.id for s in r.stages] == ["image_read", "structured_read", "perturbation", "repeatability"]
        assert r.metrics["corpus"]["lock_ok"] is True
    oracle = results["oracle"].metrics
    assert oracle["fde_mean"] == 0.0 and oracle["mode_accuracy"] == 1.0 and oracle["within_mode_step_rate"] == 1.0
    assert oracle["tasks"]["image_read"]["discriminability"]["spearman_rho"] == pytest.approx(1.0)
    assert oracle["tasks"]["structured_read"]["cross_modal"]["mode_agreement_rate"] == 1.0
    assert oracle["tasks"]["repeatability"]["repeatability"]["exact_agreement_rate"] == 1.0
    const = results["constant"].metrics
    assert const["mode_accuracy"] == pytest.approx(0.25) and const["fde_mean"] > 0
    assert results["heuristic"].metrics["parse_rate"] == 1.0
    assert results["heuristic"].metrics["fde_mean"] > oracle["fde_mean"]


def test_live_provider_rows_abort_after_consecutive_errors_and_record_receipt(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-abc123")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={"error": "down"})

    manifest = load_manifest("interpretation.fieldread.smoke")
    provider = OpenAICompatProvider("https://vlm.example.invalid", "m", transport=httpx.MockTransport(handler))
    import psyfi_bench.families.interpretation as fam

    monkeypatch.setattr(fam, "make_provider", lambda spec, options: provider)
    ctx = RunContext(provider="openai:https://vlm.example.invalid#m", include_gpu_env=False, provider_options={"record": True})
    result = run_workload(manifest, ctx)
    assert result.measurement_class == "measured"
    assert result.metrics["aborted"] is True
    assert calls["n"] == 3, "stops after three consecutive provider errors"
    assert result.status in ("failed", "partial")
    assert ctx.inputs["_receipt"]["schema"] == "psyfi.bench.provider_receipt.v1"
    assert "sk-secret-abc123" not in json.dumps(ctx.inputs["_receipt"])


def test_live_provider_success_path_scores_strictly(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    answers = iter(['{"mode": "void", "intensity": 0.6}', "```json\n{\"mode\": \"void\", \"intensity\": 0.6}\n```"] * 100)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": next(answers)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    manifest = load_manifest("interpretation.fieldread.smoke").model_copy(update={"params": {**load_manifest("interpretation.fieldread.smoke").params, "tasks": ["image_read"], "pricing": {"input_per_million": 1.0, "output_per_million": 2.0}}})
    import psyfi_bench.families.interpretation as fam

    monkeypatch.setattr(fam, "make_provider", lambda spec, options: OpenAICompatProvider("https://vlm.example.invalid", "m", transport=httpx.MockTransport(handler)))
    result = run_workload(manifest, RunContext(provider="openai:https://vlm.example.invalid#m", include_gpu_env=False))
    img = result.metrics["tasks"]["image_read"]
    assert img["n"] == 8 and img["parse_rate"] == 0.5
    assert img["recoverable_format_violations"] == 4
    assert img["violations"] == {"not_json": 4}
    assert img["cost_total"] == pytest.approx(8 * (10 * 1e-6 + 5 * 2e-6))
    assert img["cost_per_valid_result"] == pytest.approx(img["cost_total"] / 4)
    assert img["latency_ms"] is not None


def test_prompts_are_versioned_and_distinct_from_the_caption_prompt() -> None:
    from psyfi_api.image_reading import _PROMPT as CAPTION_PROMPT
    from psyfi_core.visualization.vision_bench import BENCH_PROMPT

    assert IMAGE_PROMPT != CAPTION_PROMPT and STRUCTURED_PROMPT != CAPTION_PROMPT
    assert IMAGE_PROMPT != BENCH_PROMPT
    assert "0.55" not in IMAGE_PROMPT and "0.28" not in IMAGE_PROMPT


def test_fieldloop_closes_and_times_every_stage() -> None:
    manifest = load_manifest("fieldloop.signature").model_copy(update={"protocol": Protocol(warmup_runs=1, repeats=2, cold_start=True, timeout_s=300, memory_probe=False, bootstrap_resamples=200)})
    result = run_workload(manifest, RunContext(provider="oracle", include_gpu_env=False, limit=2, inputs={"simulation": {"width": 16, "height": 16, "steps": 3}, "image_size": 64}))
    assert result.status == "complete", result.failures
    assert result.metrics["closed"] == 2 and result.metrics["fde_median"] == 0.0
    stage = result.stages[0]
    assert set(stage.metrics["stage_ms"]) == {"simulate", "snapshot", "render", "interpret", "reconstruct"}
    assert stage.cold_wall_ms is not None and len(stage.wall_ms) == 2
    assert stage.metrics["deterministic_image_across_runs"] is True
    assert sum(v for v in stage.metrics["stage_share_of_e2e"].values()) == pytest.approx(1.0, abs=0.15)
    assert result.measurement_class == "synthetic"


def test_fieldloop_timeout_is_a_stage_status() -> None:
    manifest = load_manifest("fieldloop.signature").model_copy(update={"protocol": Protocol(warmup_runs=0, repeats=1, cold_start=False, timeout_s=0.0001, memory_probe=False)})
    result = run_workload(manifest, RunContext(provider="constant", include_gpu_env=False, limit=1, inputs={"simulation": {"width": 128, "height": 128, "steps": 60}}))
    assert result.stages[0].status in ("timeout", "cancelled")
    assert result.status == "failed"
