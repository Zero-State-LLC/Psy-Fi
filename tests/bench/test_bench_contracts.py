"""The exported integration package must match the live code (drift check, like the v1 freeze)."""

from __future__ import annotations

import json
from pathlib import Path

from psyfi_bench.contracts import CONTRACT_DIR, SCHEMA_DIR, bench_openapi
from psyfi_bench.schemas import export_json_schemas

ROOT = Path(__file__).resolve().parents[2]


def test_exported_json_schemas_match_live_models() -> None:
    live = export_json_schemas()
    for name, schema in live.items():
        path = SCHEMA_DIR / name
        assert path.exists(), f"run `psyfi-bench export-schemas`: missing {path}"
        assert json.loads(path.read_text(encoding="utf-8")) == schema, f"drift: {name}"


def test_exported_bench_openapi_matches_live_app() -> None:
    path = CONTRACT_DIR / "openapi.bench.v1.json"
    assert path.exists(), "run `psyfi-bench export-schemas`"
    frozen = json.loads(path.read_text(encoding="utf-8"))
    live = bench_openapi()
    assert set(frozen["paths"]) == set(live["paths"])
    assert frozen["info"]["version"] == live["info"]["version"]
    for required in ("/v1/capabilities", "/v1/workloads", "/v1/workloads/{workload_id}", "/v1/results", "/v1/results/{run_id}", "/v1/schemas/{name}", "/v1/captures"):
        assert required in frozen["paths"]


def test_examples_are_valid_documents() -> None:
    examples = CONTRACT_DIR / "examples"
    assert examples.exists(), "run scripts/export_bench_contracts.py"
    from psyfi_bench.schemas import BenchResult, Capabilities, GpuCapture, Scorecard, WorkloadManifest

    BenchResult.model_validate(json.loads((examples / "result.field-compute.scaling.json").read_text()))
    BenchResult.model_validate(json.loads((examples / "result.interpretation.smoke.oracle.json").read_text()))
    GpuCapture.model_validate(json.loads((examples / "gpu_capture.synthetic.json").read_text()))
    Scorecard.model_validate(json.loads((examples / "scorecard.interpretation.smoke.json").read_text()))
    WorkloadManifest.model_validate({k: v for k, v in json.loads((examples / "workload.render.webgpu.tiers.json").read_text()).items() if k != "manifest_hash"})
    caps = json.loads((examples / "capabilities.json").read_text())
    assert caps["run_enabled"] is False
    err = json.loads((examples / "error.ingest_disabled.json").read_text())
    assert err["schema"] == "psyfi.bench.error.v1"
    cap = json.loads((examples / "gpu_capture.synthetic.json").read_text())
    assert cap["measurement_class"] == "synthetic", "the committed capture example must never pose as measured"
    res = json.loads((examples / "result.field-compute.scaling.json").read_text())
    assert res["environment"]["hardware_class"] in ("integrated", "cpu_only", "discrete", "unknown")
