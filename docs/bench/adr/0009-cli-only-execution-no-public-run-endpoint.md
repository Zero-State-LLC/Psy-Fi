# ADR 0009: CLI-only execution, no public run endpoint

Status: accepted, 2026-11-07.

## Problem

The bench API is reachable on the public host through the Worker. A run endpoint would let anyone start CPU work or provider calls that spend a key.

## Decision

Benchmarks run only through `psyfi-bench`. The API exposes capabilities, workloads, results and schemas, and an ingest endpoint for browser captures that is off unless `PSYFI_BENCH_INGEST=1` and bounded to 8 MB and 20,000 frames. `run_enabled` is false in capabilities. A run endpoint, if ever wanted, needs an accepted intent.

## Alternatives

- A run endpoint behind the existing four simulation slots: still a public compute trigger and still a key spender.

## Consequences

The browser runner downloads its capture by default; a local operator ingests it with the CLI. Frontends read results, they do not start them.
