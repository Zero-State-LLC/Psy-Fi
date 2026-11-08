"""Bench API — a separately versioned FastAPI sub-application mounted at ``/api/bench``.

It is read-only except for an env-gated capture ingest. Benchmarks execute only
through the CLI; the public host never runs compute on request. Its OpenAPI
document is its own contract (``docs/contracts/bench/openapi.bench.v1.json``)
and never touches the frozen ``/api/v1`` path set.
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from psyfi_bench import BENCH_VERSION, CAPABILITIES_SCHEMA, FAMILIES, NON_CLAIM
from psyfi_bench.schemas import GpuCapture, export_json_schemas

ERROR_SCHEMA = "psyfi.bench.error.v1"
MAX_CAPTURE_BYTES = 8 * 1024 * 1024
MAX_CAPTURE_FRAMES = 20_000


def ingest_enabled() -> bool:
    return os.environ.get("PSYFI_BENCH_INGEST", "").strip().lower() in {"1", "true", "yes", "on"}


def error_body(code: str, message: str, status: int) -> dict[str, Any]:
    return {"schema": ERROR_SCHEMA, "error": {"code": code, "message": message, "status": status}}


bench_app = FastAPI(
    title="PsyFi Bench API",
    description="FieldLoop benchmark read surface: capabilities, workload manifests, stored results, JSON schemas, and env-gated browser capture ingest. Research/visualization only. Not medical advice.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@bench_app.exception_handler(HTTPException)
async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
    code = {404: "not_found", 403: "ingest_disabled", 413: "payload_too_large", 422: "invalid_capture", 409: "manifest_mismatch"}.get(exc.status_code, "error")
    detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)
    return JSONResponse(status_code=exc.status_code, content=error_body(code, detail, exc.status_code))


@bench_app.get("/v1/capabilities", tags=["bench"])
async def capabilities() -> dict[str, Any]:
    from psyfi_bench.compute.backends import available_backend_names
    from psyfi_bench.environment import collect_environment
    from psyfi_bench.providers.registry import describe_available
    from psyfi_bench.registry import list_manifests

    env = collect_environment(include_gpu=True)
    return {
        "schema": CAPABILITIES_SCHEMA,
        "bench_version": BENCH_VERSION,
        "families": list(FAMILIES),
        "workloads": [{"id": m.id, "version": m.version, "family": m.family, "execution": m.execution, "requires": m.requires, "manifest_hash": m.manifest_hash, "title": m.title} for m in list_manifests()],
        "providers": describe_available(),
        "accelerators": available_backend_names(),
        "environment": env.model_dump(),
        "ingest_enabled": ingest_enabled(),
        "run_enabled": False,
        "non_claim": NON_CLAIM,
    }


@bench_app.get("/v1/workloads", tags=["bench"])
async def workloads(family: str | None = Query(default=None)) -> dict[str, Any]:
    from psyfi_bench.registry import list_manifests

    docs = [m.to_document() for m in list_manifests() if not family or m.family == family]
    return {"schema": "psyfi.bench.workloads.v1", "workloads": docs}


@bench_app.get("/v1/workloads/{workload_id}", tags=["bench"])
async def workload(workload_id: str) -> dict[str, Any]:
    from psyfi_bench.registry import ManifestNotFound, load_registered_manifest

    try:
        return load_registered_manifest(workload_id).to_document()
    except ManifestNotFound as exc:
        raise HTTPException(status_code=404, detail=f"unknown workload {workload_id!r}") from exc


@bench_app.get("/v1/results", tags=["bench"])
async def results(family: str | None = Query(default=None), manifest_id: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    from psyfi_bench.store import ResultStore

    entries = ResultStore().list(family=family, manifest_id=manifest_id)[:limit]
    return {"schema": "psyfi.bench.index.v1", "results": entries}


@bench_app.get("/v1/results/{run_id}", tags=["bench"])
async def result(run_id: str) -> dict[str, Any]:
    from psyfi_bench.store import ResultStore

    found = ResultStore().load(run_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown result {run_id!r}")
    return found.model_dump(by_alias=True)


@bench_app.get("/v1/schemas", tags=["bench"])
async def schemas() -> dict[str, Any]:
    return {"schema": "psyfi.bench.schema_index.v1", "schemas": sorted(export_json_schemas())}


@bench_app.get("/v1/schemas/{name}", tags=["bench"])
async def schema(name: str) -> dict[str, Any]:
    docs = export_json_schemas()
    if name not in docs:
        raise HTTPException(status_code=404, detail=f"unknown schema {name!r}")
    return docs[name]


@bench_app.post("/v1/captures", tags=["bench"], status_code=201)
async def ingest_capture(request: Request) -> dict[str, Any]:
    """Score a browser GPU capture. Disabled unless PSYFI_BENCH_INGEST=1."""
    if not ingest_enabled():
        raise HTTPException(status_code=403, detail="capture ingest is disabled on this host; download the capture and run `psyfi-bench ingest <file>`")
    length = int(request.headers.get("content-length") or 0)
    if length > MAX_CAPTURE_BYTES:
        raise HTTPException(status_code=413, detail=f"capture exceeds {MAX_CAPTURE_BYTES} bytes")
    raw = await request.body()
    if len(raw) > MAX_CAPTURE_BYTES:
        raise HTTPException(status_code=413, detail=f"capture exceeds {MAX_CAPTURE_BYTES} bytes")
    try:
        capture = GpuCapture.model_validate_json(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"invalid capture: {str(exc)[:300]}") from exc
    if sum(len(s.frames_ms) for s in capture.stages) > MAX_CAPTURE_FRAMES:
        raise HTTPException(status_code=413, detail=f"capture has more than {MAX_CAPTURE_FRAMES} frames")
    from psyfi_bench.registry import ManifestNotFound, load_registered_manifest
    from psyfi_bench.runner import RunContext, run_workload
    from psyfi_bench.store import ResultStore

    try:
        manifest = load_registered_manifest(capture.manifest_id)
    except ManifestNotFound as exc:
        raise HTTPException(status_code=409, detail=f"capture names unknown manifest {capture.manifest_id!r}") from exc
    if manifest.family != "render":
        raise HTTPException(status_code=409, detail="captures are scored only by render manifests")
    import anyio

    def _score():
        store = ResultStore()
        return run_workload(manifest, RunContext(inputs={"capture": capture.model_dump(by_alias=True)}, store=store, include_gpu_env=False, command="api:ingest"))

    res = await anyio.to_thread.run_sync(_score)
    return {"schema": "psyfi.bench.ingest_receipt.v1", "run_id": res.run_id, "status": res.status, "measurement_class": res.measurement_class, "manifest_hash": res.manifest_hash, "metrics": res.metrics}
