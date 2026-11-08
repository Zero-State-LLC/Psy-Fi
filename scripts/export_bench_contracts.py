#!/usr/bin/env python3
"""Export the FieldLoop integration package: JSON schemas, bench OpenAPI, and example documents.

Examples are produced from real runs on this machine (labelled with their environment and
measurement class) or from synthetic captures that say so. Nothing here is Ultra evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psyfi_bench.contracts import CONTRACT_DIR, export_contracts  # noqa: E402


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> int:
    for p in export_contracts():
        print(f"wrote {p.relative_to(ROOT)}")

    from fastapi.testclient import TestClient

    from psyfi_api.main import app
    from psyfi_bench.registry import load_manifest
    from psyfi_bench.runner import RunContext, run_workload
    from psyfi_bench.schemas import Protocol
    from psyfi_bench.scoring import build_scorecard

    examples = CONTRACT_DIR / "examples"
    client = TestClient(app)
    _write(examples / "capabilities.json", client.get("/api/bench/v1/capabilities").json())
    _write(examples / "workload.render.webgpu.tiers.json", client.get("/api/bench/v1/workloads/render.webgpu.tiers").json())
    _write(examples / "error.ingest_disabled.json", client.post("/api/bench/v1/captures", json={"schema": "x"}).json())
    _write(examples / "error.not_found.json", client.get("/api/bench/v1/workloads/nope").json())

    fast = Protocol(warmup_runs=1, repeats=3, cold_start=True, memory_probe=True, bootstrap_resamples=1000)
    scaling = run_workload(load_manifest("field-compute.scaling").model_copy(update={"protocol": fast}), RunContext(inputs={"grid_sizes": [32, 64]}, include_gpu_env=True, command="scripts/export_bench_contracts.py"))
    _write(examples / "result.field-compute.scaling.json", scaling.model_dump(by_alias=True))

    smoke = load_manifest("interpretation.fieldread.smoke")
    oracle = run_workload(smoke, RunContext(provider="oracle", include_gpu_env=True, command="scripts/export_bench_contracts.py"))
    heur = run_workload(smoke, RunContext(provider="heuristic", include_gpu_env=True, command="scripts/export_bench_contracts.py"))
    _write(examples / "result.interpretation.smoke.oracle.json", oracle.model_dump(by_alias=True))
    _write(examples / "scorecard.interpretation.smoke.json", build_scorecard([oracle, heur], ["oracle", "heuristic"]).model_dump(by_alias=True))

    loop = run_workload(load_manifest("fieldloop.signature").model_copy(update={"protocol": Protocol(warmup_runs=1, repeats=2, cold_start=True, memory_probe=False, bootstrap_resamples=500)}), RunContext(provider="heuristic", include_gpu_env=True, limit=2, command="scripts/export_bench_contracts.py"))
    _write(examples / "result.fieldloop.signature.heuristic.json", loop.model_dump(by_alias=True))

    from tests.bench.test_render_family import _capture

    capture = _capture("synthetic")
    _write(examples / "gpu_capture.synthetic.json", capture.model_dump(by_alias=True))
    scored = run_workload(load_manifest("render.webgpu.tiers"), RunContext(inputs={"capture": capture.model_dump(by_alias=True)}, include_gpu_env=True, command="scripts/export_bench_contracts.py"))
    _write(examples / "result.render.webgpu.synthetic-capture.json", scored.model_dump(by_alias=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
