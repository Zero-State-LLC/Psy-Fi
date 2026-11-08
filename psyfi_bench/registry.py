"""Workload manifests on disk and the family runner registry."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from psyfi_bench.schemas import WorkloadManifest

WORKLOADS_DIR = Path(__file__).resolve().parent / "workloads"

FamilyRunner = Callable[..., Any]
_FAMILY_RUNNERS: dict[str, FamilyRunner] = {}


class ManifestNotFound(KeyError):
    pass


def register_family(name: str) -> Callable[[FamilyRunner], FamilyRunner]:
    def deco(fn: FamilyRunner) -> FamilyRunner:
        _FAMILY_RUNNERS[name] = fn
        return fn

    return deco


def load_families() -> None:
    """Import family modules so their runners register (idempotent)."""
    import importlib

    for mod in (
        "psyfi_bench.families.field_compute",
        "psyfi_bench.families.render",
        "psyfi_bench.families.interpretation",
        "psyfi_bench.families.fieldloop",
    ):
        try:
            importlib.import_module(mod)
        except ModuleNotFoundError as exc:  # a family not yet shipped is not an error
            if exc.name != mod:
                raise


def get_family_runner(family: str) -> FamilyRunner:
    load_families()
    try:
        return _FAMILY_RUNNERS[family]
    except KeyError as exc:
        raise KeyError(f"no runner registered for family {family!r}") from exc


def manifest_paths(directory: Path | None = None) -> list[Path]:
    d = directory or WORKLOADS_DIR
    return sorted(p for p in d.glob("*.json") if not p.name.startswith("_"))


def load_manifest_file(path: Path) -> WorkloadManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data.pop("manifest_hash", None)  # recomputed, never trusted from disk
    return WorkloadManifest.model_validate(data)


def list_manifests(directory: Path | None = None) -> list[WorkloadManifest]:
    return [load_manifest_file(p) for p in manifest_paths(directory)]


MANIFEST_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}(@[0-9]+)?$")


def is_registry_ref(ref: str) -> bool:
    """True for an ``id`` or ``id@version`` that can only resolve inside the packaged registry."""
    return bool(MANIFEST_REF_PATTERN.match(ref)) and "/" not in ref and "\\" not in ref and ".." not in ref


def load_registered_manifest(ref: str, directory: Path | None = None) -> WorkloadManifest:
    """Resolve ``id`` or ``id@version`` from the registry only. Never touches a caller-supplied path."""
    if not is_registry_ref(ref):
        raise ManifestNotFound(ref)
    want_id, _, want_version = ref.partition("@")
    candidates = [m for m in list_manifests(directory) if m.id == want_id]
    if want_version:
        candidates = [m for m in candidates if str(m.version) == want_version]
    if not candidates:
        raise ManifestNotFound(ref)
    return max(candidates, key=lambda m: m.version)


def load_manifest(ref: str | Path, directory: Path | None = None) -> WorkloadManifest:
    """``ref`` is an id, ``id@version``, or a filesystem path (CLI use; the API uses ``load_registered_manifest``)."""
    ref = str(ref)
    if is_registry_ref(ref):
        return load_registered_manifest(ref, directory)
    path = Path(ref)
    if path.suffix == ".json" and path.exists():
        return load_manifest_file(path)
    want_id, _, want_version = ref.partition("@")
    candidates = [m for m in list_manifests(directory) if m.id == want_id]
    if want_version:
        candidates = [m for m in candidates if str(m.version) == want_version]
    if not candidates:
        raise ManifestNotFound(ref)
    return max(candidates, key=lambda m: m.version)


def save_manifest(manifest: WorkloadManifest, path: Path) -> None:
    path.write_text(json.dumps(manifest.to_document(), indent=2) + "\n", encoding="utf-8")
