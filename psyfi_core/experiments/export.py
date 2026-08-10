"""Structured, traversal-safe experiment directory export."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
from .hashing import stable_json
from .models import ExperimentResult, ExperimentSpec


def _write(path: Path, value) -> None:
    path.write_text(stable_json(value) + "\n", encoding="utf-8")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_experiment(spec: ExperimentSpec, result: ExperimentResult, base_dir: str | Path) -> Path:
    base = Path(base_dir).resolve()
    target = (base / spec.experiment_id).resolve()
    if target.parent != base:
        raise ValueError("experiment export path escapes base directory")
    target.mkdir(parents=True, exist_ok=True)
    files = {
        "experiment.json": spec.model_dump(mode="json"),
        "summary.json": result.summary.model_dump(mode="json"),
        "provenance.json": {"canonical": result.provenance, "environment": result.environment},
    }
    for name, value in files.items():
        _write(target / name, value)
    (target / "runs.jsonl").write_text(
        "".join(stable_json(r.model_dump(mode="json")) + "\n" for r in result.receipts),
        encoding="utf-8",
    )
    identities = {name: _file_hash(target / name) for name in (*files, "runs.jsonl")}
    manifest = {
        "schema_version": "psyfi.experiment_manifest.v1",
        "experiment_id": spec.experiment_id,
        "spec_hash": result.spec_hash,
        "run_count": result.run_count,
        "schemas": {
            "experiment": spec.schema_version,
            "receipt": "psyfi.experiment_run_receipt.v1",
            "result": result.schema_version,
        },
        "files": identities,
    }
    _write(target / "manifest.json", manifest)
    return target
