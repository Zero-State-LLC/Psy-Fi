# Frontend Boundary Decision

Status: updated 2026-11-07  
Related: [`PLANS.md`](../PLANS.md), [`docs/WEB_ARCHITECTURE.md`](WEB_ARCHITECTURE.md), [`docs/rendering/`](rendering/)

## Decision

**Two coexisting surfaces:**

1. **Legacy product shell (default `/`)** — progressively enhanced `psyfi_api` static shell (`templates/index.html`, `static/app.js`, Canvas/WebGL Live Experience). Remains the compatibility / PWA path.
2. **GPU platform (optional `/gpu/`)** — Vite + React + TypeScript package `packages/psyfi-gpu-renderer` (React Three Fiber + Three.js `WebGPURenderer`). Served by FastAPI when `dist/` is built. **Does not patch** `static/viz/*`.

Both consume the same authoritative `/api/v1` contracts. The GPU client’s sole render input is immutable `psyfi.scene_snapshot.v1` from `POST /api/v1/visualize/scene-snapshot`.

## Criteria Applied

| Criterion | Existing constraint | Implication |
|---|---|---|
| Deployment model | Docker + FastAPI serve UI + API together | Mount GPU `dist/` at `/gpu/`; no Azure/Render host required |
| Contributor skill / repo shape | Python-first + growing TS package | Workspace under `packages/`; Python stays simulation authority |
| Bundle/runtime cost | Legacy remains zero-build | GPU build is opt-in (`npm run gpu:build`) |
| API coupling | Soft-frozen `/api/v1` | Additive `scene-snapshot` route; shared ParameterField |
| Accessibility | Neutral View / reduce-motion | Snapshot flags + mandatory safety pass in GPU graph |
| Migration | See [`rendering/MIGRATION_PLAN.md`](rendering/MIGRATION_PLAN.md) | Coexist → feature flag → cutover |

## What Stays Authoritative

- Simulation truth: `psyfi_core` + FastAPI responses
- Design tokens: existing `--pf-*` CSS / `docs/DESIGN_SYSTEM.md` (GPU shell mirrors neutrals)
- Icons: `docs/icons` served at `/assets/icons`
- Contracts: Pydantic models, OpenAPI, freeze pack under `docs/contracts/frozen/`

## Present path

The `/gpu/` picture is the TypeScript post graph in `packages/psyfi-gpu-renderer` (`PresentPipeline`). When the tier enables a pass, the order is ambient occlusion, reflections, bloom, depth of field, motion blur, chroma, temporal accumulate, then grade. A safety attenuator follows on every presented frame. Neutral collapses that stack: exposure and the attenuator drop, bloom strength is zero, and temporal history is off.

The WGSL files under `packages/psyfi-gpu-renderer/shaders/` are not that path. Bloom, ambient occlusion, reflections, and the material shaders are stubs that return black. The safety-clamp sketch is not the attenuator `PresentPipeline` runs. Do not implement those files as the picture.

## Still deferred

- Hard cutover of `/` to the GPU shell
- Native iOS (`docs/IOS_MIGRATION.md`)
- Hardware Ultra capture. This document does not record measured frame times.
