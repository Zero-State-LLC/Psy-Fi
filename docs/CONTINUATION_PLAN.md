## Current next milestone — living hardware and GPU evidence

The web/PWA/API ship gates are complete and the instrument track I1–I5 is landed. The next milestone is living QA: collect hardware Ultra performance evidence as available and, separately, lock full R3F WebGPU still SHAs on a GPU CI runner if that environment becomes available. These are evidence tasks, not permission to weaken the mandatory SafetyPass or Python-authoritative simulation; native iOS remains deferred. No calendar ship date is claimed.

# PsyFi Web Continuation Plan

Status: active — **production-ready Docker web ship**; G0–G4 ship gates met; living QA continues  
Scope: **web app / PWA / API only** — native iOS remains deferred (`docs/IOS_MIGRATION.md`).  
Deploy: **Docker only** (`DEPLOYMENT.md`).  
Board: [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md)

## Baseline

| Area | State |
| --- | --- |
| `/api/v1` + **hard freeze** | Done (`psyfi-api-v1-hard-2026-07-25`) — additive I3–I5 routes synced |
| Legacy Live Experience (Canvas/WebGL) | Done — full shell + I1–I5 + transitions |
| ParameterField + SafetyPass | Done |
| Image-seed pipeline | Done + anchors + planner notes |
| Export-journey | Done + anchors + planner |
| PWA + service worker | Done (root `/sw.js`, shell cache **v41**) |
| GPU Lab route | Done |
| Docker production | Done |

## Instrument & Spatiotemporal Grounding Track

Full plan: [`INSTRUMENT_GROUNDING_PLAN.md`](INSTRUMENT_GROUNDING_PLAN.md).

| ID | Item | Notes |
|----|------|-------|
| **I1** | Non-linear quantized controls + lever-style commits | map + stations dial + Neutral lever |
| **I2** | Dual-field / dual-timeline hold-and-compare | wipe / blink / split + IndexedDB archive |
| **I3** | Optional spatiotemporal anchors | lat/lon + year + hour + solar elevation |
| **I4** | Explicit planner stage | `psyfi.planner.v1` + `/visualize/planner` |
| **I5** | First-class Journey objects | `psyfi.journey.v1` + IndexedDB `journeys` |

### Active queue

- [x] **I1** — instrument map + Neutral lever + shell wiring
- [x] **I2** — pin / wipe / blink / split + IndexedDB comparison archive
- [x] **I3** — `psyfi.spatiotemporal_anchor.v1` on image-seed + export-journey (+ shell UI)
- [x] **I4** — deterministic planner (`psyfi.planner.v1`, motifs + lighting notes)
- [x] **I5** — Journey objects (`psyfi.journey.v1`, IndexedDB archive + restore)
- [x] Station dial + live solar lighting modulator polish
- [x] Lever commits — export-journey confirm + seed lock/unlock
- [x] WebGL hold-and-compare parity (pin FBO + wipe/blink/split dual-viewport)
- [x] Journey `comparison_id` link + restore hardening
- [x] Safety-clamped soft transitions (phase / Neutral / load / journey)
- [x] Doc + schema drift sync (planner/journey schemas, freeze route list, SW cites)
- [x] Viz helper numeric invariant tests (`tests/js/run_viz_helper_tests.mjs`)

## Next recommended

1. Living QA / hardware capture as needed (`PRODUCTION_READINESS.md`, `HARDWARE_ULTRA_FPS.md`).
2. Optional model-swappable client generative extensions (user key only) — non-goal for core path.

## Supporting patterns landed

- [x] Safety-clamped soft crossfades (`transitionSurface.js`) for phase, Neutral, load, journey restore — Canvas + WebGL; skipped under reduced motion and when hold-and-compare is active.
- [x] WebGL split dual-viewport parity with Canvas `compositeSplit`.

## Run

```bash
docker compose up -d --build
python3 scripts/run_dev_server.py
```

## Non-claims

Modeled phenomenology for research/visualization only. Not medical advice.