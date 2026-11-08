"""Export the frontend integration package: JSON schemas, bench OpenAPI, examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psyfi_bench.environment import REPO_ROOT
from psyfi_bench.schemas import export_json_schemas

SCHEMA_DIR = REPO_ROOT / "docs" / "schemas" / "bench"
CONTRACT_DIR = REPO_ROOT / "docs" / "contracts" / "bench"


def bench_openapi() -> dict[str, Any]:
    from psyfi_bench.api import bench_app

    doc = bench_app.openapi()
    doc.setdefault("servers", [{"url": "/api/bench", "description": "mounted under the PsyFi API"}])
    return doc


def _write(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=isinstance(payload, dict) and "openapi" in payload, default=str) + "\n", encoding="utf-8")
    return path


def export_contracts(out_root: Path | None = None) -> list[Path]:
    schema_dir = (out_root / "schemas") if out_root else SCHEMA_DIR
    contract_dir = (out_root / "contracts") if out_root else CONTRACT_DIR
    written: list[Path] = []
    for name, schema in export_json_schemas().items():
        written.append(_write(schema_dir / name, schema))
    written.append(_write(contract_dir / "openapi.bench.v1.json", bench_openapi()))
    return written
