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

## N0 native computational kernel — completed, promotion rejected

N0 established a bounded research-only PyO3 seam, but representative and large workloads were slower than NumPy, so `auto` remains on Python. See [`N0_NATIVE_COMPUTE_PLAN.md`](N0_NATIVE_COMPUTE_PLAN.md) and [`N0_EVIDENCE.md`](N0_EVIDENCE.md).

- Select exactly one pure deterministic `psyfi_core` kernel after profiling and FFI suitability review.
- Retain Python as the semantic reference and simulation authority.
- Build one `psyfi-native` PyO3/maturin crate behind an internal Python adapter.
- Require parity, determinism, unchanged API/scene/goldens, realistic end-to-end benchmarks, and CI evidence.
- Enable native execution for `auto` only if the promotion gate passes, normally including at least 2x representative-workload speedup.
- Treat `NO_JUSTIFIED_NATIVE_KERNEL` or `N0_PROMOTION = REJECTED` as valid evidence-based outcomes.
- Do not implement N1 replay receipts, N2 additional kernels, N3 sweeps, N4 parallel execution, N5 a native runner, or N6 WASM reassessment in N0.

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
