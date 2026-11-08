# Intent — FieldLoop bench results page

Author: drafted by Claude for the operator
Date: 2026-11-08
Status: accepted (by the operator in chat, 2026-11-08: a shell page at `/bench`, for the local operator first)
Product: PsyFi (`Zero-State-LLC/Psy-Fi`)
Issue: #52 (umbrella #47)

This file is a proto-spec. It comes **before** specify / plan.

## Problem

FieldLoop (#56) stores sealed benchmark results and serves them read-only at `/api/bench/v1`. The only way to read one today is `curl` or the JSON file. The labels that qualify a number sit deep in the document: the measurement class, the hardware class, and the telemetry that was not collected. So it is easy to read a number without them. Scorecards come from `psyfi-bench score` and are read as Markdown or JSON.

[verified: `docs/bench/INTEGRATION.md`, the routes in `psyfi_bench/api.py`, issue #52]

## Outcome

Observable done:

- `GET /bench` serves a results page: from FastAPI on a local API, and as a staged static page on psy-fi.space.
- The results list reads `GET /api/bench/v1/results`. Every row shows `measurement_class` and `hardware_class` beside its numbers, and the list filters by family.
- Selecting a run shows its environment and every `environment.unavailable` entry with its reason. It also shows the stage statistics, failures, `result_hash` and `non_claim`.
- The scorecard view opens a `psyfi.bench.scorecard.v1` file. When `validity.comparable` is false, it shows the reasons and does not rank.
- On a host with no results, which is psy-fi.space today, the page says so and says how results are made. It never shows a number it did not read.
- Tests cover the route, the staged page, and the page's hooks. Nothing else changes: `/api/v1`, the bench API, the GPU lab components and the service-worker cache name stay as they are.

## Users / systems

- Users: the operator reading local CLI runs, and a visitor to psy-fi.space, who sees the empty state.
- Systems: `psyfi_api` (route and template), `static/bench.css` and `static/bench.js`, `scripts/stage_cloudflare_assets.py`, and `/api/bench/v1`, read only. The Worker's routing is unchanged: `/bench` is an asset.

## Constraints

Product-true locks:

- `design.md` stays the system: its tokens, Space Grotesk and IBM Plex, one cyan signal, the N9 nav and the Ft2 footer.
- Read only. No scorecard endpoint, no run and no ingest (ADR 0009).
- `measurement_class` and `hardware_class` appear next to every number. `non_claim` is printed, and so is "Not medical advice".

Non-goals:

- Publishing results on the public host.
- A link in the GPU lab header (GPU lab chrome).
- Charts.

## Open questions

- Whether psy-fi.space should publish selected results, and which ones.
- Whether a read-only scorecard endpoint should exist, so the page can compare runs without a file.

## Next

Implemented with issue #52.
