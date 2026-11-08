# ADR 0008: Simulation orchestration moved to `psyfi_core.simulation`

Status: accepted, 2026-11-07.

## Problem

`run_simulation`, the canonical pipeline (seeded initial field, Kuramoto evolution, normalization, valence), lived in `psyfi_api.simulation_service`. The bench must call it without importing the API package, and the authority belongs in `psyfi_core`.

## Decision

New module `psyfi_core/simulation.py` with `SimulationSettings`, `resolve_preset_settings`, `initial_field`, `simulate_field` (returns every intermediate array) and `run_simulation` (unchanged payload). `psyfi_api/simulation_service.py` becomes a re-export so routers and tests keep their imports.

## Alternatives

- Duplicate the pipeline in the bench: two implementations would drift.
- Import `psyfi_api` from the bench: wrong dependency direction.

## Consequences

Verified identical payloads for presets None, lsd, dmt and ketamine (metrics, visualization values, session parameters, provenance). RNG draw order is documented as part of the contract.
