# Changelog

Product versions follow [docs/VERSIONING.md](docs/VERSIONING.md). Tags `v0.1.0` through `v1.4.0` were applied on 2026-11-07 to commits already on `main`. The trees through `v1.3.1` still contain the string `0.1.0`. The notes below name the ship point, not every commit in between.

## Unreleased

- FieldLoop benchmark subsystem (`psyfi_bench`): four workload families, locked references, sealed results, scorecards, CLI, mounted `/api/bench` read API, browser runner `/gpu/bench.html`. Product version unchanged.
- `run_simulation` moved to `psyfi_core.simulation`; `psyfi_api.simulation_service` re-exports it.
- Field-compute locks gain a tolerance-checked summary (`reference_within_tolerance`) after CI showed 1e-4 digests differ between Linux x86-64 and Apple arm64; `tolerances.reference_atol` added, so every manifest hash changed. Bench API resolves workload ids from the registry only.

## 1.4.0 — 2026-11-07

- Cloudflare Worker and Container host. Compose remains the local seam. CI does not deploy.
- Inferred image reading at `POST /api/v1/visualize/image-reading`. It does not write presets or the catalog.
- Product version is `psyfi_core/VERSION`. `/health`, `/ready`, `/api/info`, and the shell badge report it.
- Tag `v1.4.0` on `84334ad`.

## 1.3.1 — 2026-10-23

Tag `v1.3.1` on `7ca678e`.

- Zero State Proprietary License v1.0, CodeQL, and org project automation.
- Dependency bumps and the continuation-plan note.

## 1.3.0 — 2026-08-04

Tag `v1.3.0` on `077ac90`.

- Instrument I1–I5: intensity map, Neutral lever, hold-and-compare, anchors, planner, and journeys.

## 1.2.0 — 2026-07-25

Tag `v1.2.0` on `2f0895b`.

- Shell, safety, and device-scan passes after G4.
- Two-pass image seed, GPU texture handoff, and the export-journey sidecar.

## 1.1.0 — 2026-07-25

Tag `v1.1.0` on `a3aeead`.

- G4 scene snapshots, the separate `/gpu/` route, and soft-present pixel goldens.

## 1.0.0 — 2026-07-25

Tag `v1.0.0` on `76f9895`.

- Hard freeze `psyfi-api-v1-hard-2026-07-25`.
- Docker-only deploy. Azure and Render paths removed in the commits after the soft freeze.
- GPU platform through G3.

## 0.5.0 — 2026-07-25

Tag `v0.5.0` on `d296357`.

- Web-first plan, live visual experiences, and the `/api/v1` soft freeze.

## 0.4.0 — 2025-12-21

Tag `v0.4.0` on `6fd80f0`.

- Health payload reports the app version.
- Core engines as pure functions.
- Tighter MIDI route activity checks.

## 0.3.0 — 2025-12-01

Tag `v0.3.0` on `959f8b2`.

- MIDI control of the field.
- First multi-host deploy configs.

## 0.2.0 — 2025-11-27

Tag `v0.2.0` on `30216da`.

- Style pack and substance preset suite.

## 0.1.0 — 2025-11-27

Tag `v0.1.0` on `48acc6f`.

- First consciousness-field engine, brand, and PWA shell.
- This is the version string the tree kept until 1.4.0.
