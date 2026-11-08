"""Local artifact store: one JSON per result plus an index. Atomic writes."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from psyfi_bench.environment import REPO_ROOT
from psyfi_bench.schemas import BenchResult

DEFAULT_ROOT = REPO_ROOT / "bench_results"


def default_root() -> Path:
    env = os.environ.get("PSYFI_BENCH_RESULTS", "").strip()
    return Path(env).expanduser() if env else DEFAULT_ROOT


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


class ResultStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else default_root()
        self._lock = threading.Lock()

    @property
    def index_path(self) -> Path:
        return self.root / "index.json"

    def _read_index(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return list(data.get("results", [])) if isinstance(data, dict) else []

    def save(self, result: BenchResult) -> Path:
        if result.result_hash is None:
            result.seal()
        family = str(result.manifest.get("family", "unknown"))
        path = self.root / family / f"{result.run_id}.json"
        with self._lock:
            _atomic_write(path, json.dumps(result.model_dump(by_alias=True), indent=2, default=str) + "\n")
            entries = [e for e in self._read_index() if e.get("run_id") != result.run_id]
            entries.append(self.summary(result, path))
            entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
            _atomic_write(
                self.index_path,
                json.dumps({"schema": "psyfi.bench.index.v1", "results": entries}, indent=2) + "\n",
            )
        return path

    def summary(self, result: BenchResult, path: Path | None = None) -> dict[str, Any]:
        env = result.environment
        return {
            "run_id": result.run_id,
            "created_at": result.created_at,
            "family": result.manifest.get("family"),
            "manifest_id": result.manifest.get("id"),
            "manifest_version": result.manifest.get("version"),
            "manifest_hash": result.manifest_hash,
            "measurement_class": result.measurement_class,
            "status": result.status,
            "hardware_class": env.hardware_class,
            "cpu": (env.cpu or {}).get("brand"),
            "gpus": [g.name for g in env.gpus],
            "headline": result.metrics,
            "path": str(path.relative_to(self.root)) if path else None,
        }

    def list(self, *, family: str | None = None, manifest_id: str | None = None) -> list[dict[str, Any]]:
        entries = self._read_index()
        if family:
            entries = [e for e in entries if e.get("family") == family]
        if manifest_id:
            entries = [e for e in entries if e.get("manifest_id") == manifest_id]
        return entries

    def load(self, run_id: str) -> BenchResult | None:
        for entry in self._read_index():
            if entry.get("run_id") == run_id and entry.get("path"):
                path = self.root / entry["path"]
                if path.exists():
                    return BenchResult.model_validate(json.loads(path.read_text(encoding="utf-8")))
        return None

    def load_path(self, path: Path) -> BenchResult:
        return BenchResult.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
