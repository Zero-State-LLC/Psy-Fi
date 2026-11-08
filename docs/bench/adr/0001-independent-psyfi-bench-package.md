# ADR 0001: An independent `psyfi_bench` package

Status: accepted, 2026-11-07.

## Problem

Benchmark code could live inside `psyfi_core` (next to the vision bench), inside `psyfi_api`, or in the GPU package. The mission needs headless execution, its own versioned contracts, optional heavy dependencies and room for several families without entangling the simulation authority or the HTTP layer.

## Decision

A top-level Python package `psyfi_bench/` with its own schemas, manifests, families, providers, store, CLI and API sub-app. It imports `psyfi_core` only. `psyfi_api` imports it to mount the API. The GPU browser runner lives in the GPU package as an additive page and talks to the bench only through HTTP.

## Alternatives

- Extend `psyfi_core.visualization.vision_bench`: that module is Daniel's merged decision record and is deliberately narrow (four images, one receipt).
- Put it under `psyfi_api`: would force the simulation-side benchmark to depend on FastAPI and would blur the authority boundary.

## Consequences

Dependency direction is `psyfi_api` → `psyfi_bench` → `psyfi_core`. The simulation orchestration had to move into `psyfi_core` (ADR 0008). The package is installable with a `psyfi-bench` entry point and ships its manifests as package data.
