# ADR 0002: A separately mounted bench API at `/api/bench`

Status: accepted, 2026-11-07.

## Problem

`tests/test_openapi_contract.py` and `tests/test_frozen_contracts.py` assert that the live app's OpenAPI path set equals the committed snapshot and the frozen pack, body for body. Any route added to the main app forces a freeze resync. The vision bench spec also set a precedent: no public route for a bench.

## Decision

`psyfi_bench.api.bench_app` is its own FastAPI application mounted with `app.mount("/api/bench", bench_app)`. A mounted application does not appear in the parent's OpenAPI document, so the `/api/v1` freeze stays byte-identical. The sub-app has its own document at `/api/bench/openapi.json`, exported to `docs/contracts/bench/openapi.bench.v1.json` with a drift test. The surface is read-only plus an env-gated capture ingest.

## Alternatives

- Additive routes under `/api/v1` with a freeze resync: legal under the freeze policy but rewrites the frozen pack and `MANIFEST.json` timestamp on every bench change.
- No API at all: leaves the frontend to parse result files by hand.

## Consequences

The Worker routes `/api/*` to the container, so the bench read surface is public on `psy-fi.space`. That is why execution is CLI-only (ADR 0009) and ingest is off by default and bounded.
