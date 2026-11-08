"""Bench API sub-app, CLI, scorecards, and the contract export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from psyfi_api.main import app
from psyfi_bench import CAPABILITIES_SCHEMA
from psyfi_bench.cli import main as cli_main
from psyfi_bench.registry import load_manifest
from psyfi_bench.report import result_markdown, scorecard_markdown
from psyfi_bench.runner import RunContext, run_workload
from psyfi_bench.schemas import Protocol
from psyfi_bench.scoring import build_scorecard
from psyfi_bench.store import ResultStore

client = TestClient(app)
FAST = Protocol(warmup_runs=0, repeats=2, cold_start=False, memory_probe=False, bootstrap_resamples=200)


def test_bench_api_is_mounted_and_frozen_v1_paths_are_untouched() -> None:
    v1_paths = set(app.openapi()["paths"])
    assert not any(p.startswith("/api/bench") for p in v1_paths), "the bench API must not enter the frozen /api/v1 OpenAPI document"
    caps = client.get("/api/bench/v1/capabilities")
    assert caps.status_code == 200
    body = caps.json()
    assert body["schema"] == CAPABILITIES_SCHEMA
    assert body["run_enabled"] is False
    assert {"field_compute", "render", "interpretation", "fieldloop"} <= set(body["families"])
    assert any(w["id"] == "fieldloop.signature" for w in body["workloads"])
    assert body["environment"]["unavailable"]
    doc = client.get("/api/bench/openapi.json").json()
    assert "/v1/capabilities" in doc["paths"] and "/v1/captures" in doc["paths"]
    assert client.get("/api/bench/docs").status_code == 200


def test_bench_api_workloads_schemas_and_errors() -> None:
    assert client.get("/api/bench/v1/workloads?family=render").json()["workloads"]
    one = client.get("/api/bench/v1/workloads/render.webgpu.tiers").json()
    assert one["manifest_hash"] == load_manifest("render.webgpu.tiers").manifest_hash
    missing = client.get("/api/bench/v1/workloads/nope")
    assert missing.status_code == 404
    assert missing.json()["schema"] == "psyfi.bench.error.v1"
    assert missing.json()["error"]["code"] == "not_found"
    names = client.get("/api/bench/v1/schemas").json()["schemas"]
    assert "psyfi_bench_result.v1.json" in names
    assert client.get("/api/bench/v1/schemas/psyfi_bench_gpu_capture.v1.json").json()["properties"]["stages"]
    assert client.get("/api/bench/v1/schemas/none.json").status_code == 404
    assert client.get("/api/bench/v1/results/run_missing").status_code == 404


def test_capture_ingest_is_gated_and_bounded(monkeypatch, tmp_path: Path) -> None:
    from tests.bench.test_render_family import _capture

    payload = _capture("synthetic").model_dump(by_alias=True)
    monkeypatch.delenv("PSYFI_BENCH_INGEST", raising=False)
    denied = client.post("/api/bench/v1/captures", json=payload)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "ingest_disabled"
    monkeypatch.setenv("PSYFI_BENCH_INGEST", "1")
    monkeypatch.setenv("PSYFI_BENCH_RESULTS", str(tmp_path))
    bad = client.post("/api/bench/v1/captures", json={"schema": "x"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_capture"
    wrong = client.post("/api/bench/v1/captures", json={**payload, "manifest_id": "field-compute.scaling"})
    assert wrong.status_code == 409
    ok = client.post("/api/bench/v1/captures", json=payload)
    assert ok.status_code == 201, ok.text
    receipt = ok.json()
    assert receipt["measurement_class"] == "synthetic" and receipt["status"] == "complete"
    listed = client.get("/api/bench/v1/results?family=render").json()["results"]
    assert listed and listed[0]["run_id"] == receipt["run_id"]
    full = client.get(f"/api/bench/v1/results/{receipt['run_id']}").json()
    assert full["schema"] == "psyfi.bench.result.v1" and full["measurement_class"] == "synthetic"
    huge = {**payload, "stages": [{**payload["stages"][0], "frames_ms": [8.0] * 30_000}]}
    assert client.post("/api/bench/v1/captures", json=huge).status_code == 413


def _two_results(tmp_path: Path):
    manifest = load_manifest("field-compute.scaling").model_copy(update={"protocol": FAST})
    store = ResultStore(tmp_path)
    a = run_workload(manifest, RunContext(inputs={"grid_sizes": [16, 32]}, include_gpu_env=False, store=store))
    b = run_workload(manifest, RunContext(inputs={"grid_sizes": [16, 32]}, include_gpu_env=False, store=store))
    return store, a, b


def test_scorecard_dimensions_validity_and_markdown(tmp_path: Path) -> None:
    store, a, b = _two_results(tmp_path)
    card = build_scorecard([a, b], ["run-a", "run-b"])
    assert card.family == "field_compute"
    assert card.validity["comparable"] is True
    assert "throughput_cell_steps_per_s" in card.dimensions
    assert card.dimensions["bitwise_determinism"]["run-a"].value == 1.0
    assert card.recommendations and card.recommendations[0].startswith("Best throughput_cell_steps_per_s")
    md = scorecard_markdown(card)
    assert "## Dimensions" in md and "run-a" in md
    other = run_workload(load_manifest("field-compute.steps").model_copy(update={"protocol": FAST}), RunContext(inputs={"grid": 16, "steps_list": [2, 4]}, include_gpu_env=False))
    mixed = build_scorecard([a, other])
    assert mixed.validity["comparable"] is False and "mixed manifest hashes" in " ".join(mixed.validity["reasons"])
    assert mixed.recommendations[0].startswith("No ranking")
    with pytest.raises(ValueError):
        build_scorecard([])


def test_interpretation_scorecard_has_composites_with_formulas() -> None:
    manifest = load_manifest("interpretation.fieldread.smoke")
    oracle = run_workload(manifest, RunContext(provider="oracle", include_gpu_env=False))
    heur = run_workload(manifest, RunContext(provider="heuristic", include_gpu_env=False))
    card = build_scorecard([oracle, heur], ["oracle", "heuristic"])
    assert card.dimensions["fde_mean"]["oracle"].value == 0.0
    assert card.dimensions["fde_mean"]["heuristic"].value > 0
    comp = card.composites["oracle"]["valid_in_step_per_second"]
    assert "formula" in comp and "missing_data_rule" in comp
    assert card.composites["oracle"]["fidelity_per_currency"]["value"] is None, "no pricing => null, never imputed"
    assert card.recommendations[0].startswith("Best fde_mean") and "oracle" in card.recommendations[0]
    assert "oracle" in result_markdown(oracle)


def test_cli_round_trip(tmp_path: Path, capsys) -> None:
    assert cli_main(["list", "--family", "render"]) == 0
    out = capsys.readouterr().out
    assert "render.soft.g4" in out and "field-compute" not in out
    code = cli_main(["run", "field-compute.steps", "--limit", "1", "--repeats", "2", "--warmup", "0", "--param", "grid=16", "--param", "steps_list=[3]", "--out", str(tmp_path), "--json"])
    assert code == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["schema"] == "psyfi.bench.result.v1" and doc["stages"][0]["id"] == "steps_3"
    assert doc["manifest"]["params"]["grid"] == 16, "overrides are recorded in the result's manifest copy"
    stored = list((tmp_path / "field_compute").glob("*.json"))
    assert len(stored) == 1
    assert cli_main(["validate", str(stored[0])]) == 0
    assert json.loads(capsys.readouterr().out)["seal_valid"] is True
    assert cli_main(["results", "--out", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)[0]["manifest_id"] == "field-compute.steps"
    assert cli_main(["report", str(stored[0])]) == 0
    assert "## Stages" in capsys.readouterr().out
    assert cli_main(["score", str(stored[0]), "--labels", "only", "--out", str(tmp_path / "card.json")]) == 0
    assert json.loads((tmp_path / "card.json").read_text())["schema"] == "psyfi.bench.scorecard.v1"
    assert cli_main(["lock", "field-compute.steps"]) == 0
    assert "quantized_sha256" in capsys.readouterr().out
    assert cli_main(["show", "fieldloop.signature"]) == 0
    assert cli_main(["env"]) == 0
    assert cli_main(["export-schemas", "--out", str(tmp_path / "pkg")]) == 0
    assert (tmp_path / "pkg" / "schemas" / "psyfi_bench_result.v1.json").exists()
    assert (tmp_path / "pkg" / "contracts" / "openapi.bench.v1.json").exists()


def test_cli_run_exit_codes_reflect_status(capsys) -> None:
    code = cli_main(["run", "field-compute.accelerator", "--backend", "quantum", "--limit", "1", "--no-store", "--quiet"])
    assert code == 1
    code = cli_main(["run", "render.webgpu.tiers", "--no-store", "--quiet"])
    assert code == 1


def test_workload_route_rejects_path_like_ids() -> None:
    from fastapi.testclient import TestClient

    from psyfi_api.main import app
    from psyfi_bench.registry import is_registry_ref

    client = TestClient(app)
    for bad in ("../../pyproject.toml", "/etc/passwd", "x/y.json", "field-compute.scaling.v1.json"):
        assert client.get(f"/api/bench/v1/workloads/{bad}").status_code in (404, 422)
    assert is_registry_ref("field-compute.scaling") and is_registry_ref("field-compute.scaling@1")
    assert not is_registry_ref("../x") and not is_registry_ref("a/b") and not is_registry_ref("")


def test_dockerfile_copies_every_first_party_package_the_api_imports() -> None:
    """The image must carry every psyfi_* package `psyfi_api.main` imports, or uvicorn never boots.

    Regression guard for the unconditional ``psyfi_bench`` import (review on PR #56).
    """
    import re
    import sys
    from pathlib import Path

    import psyfi_api.main  # noqa: F401  (ensures its imports are loaded)

    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    copied = set(re.findall(r"^COPY (psyfi_[a-z_]+)/ \./\1/\s*$", dockerfile, flags=re.M))
    imported = {name.split(".")[0] for name in sys.modules if name.startswith("psyfi_") and (root / name.split(".")[0]).is_dir()}
    assert imported >= {"psyfi_core", "psyfi_api", "psyfi_bench"}
    missing = sorted(imported - copied)
    assert not missing, f"Dockerfile does not COPY first-party packages the API imports: {missing}"
