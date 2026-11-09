# PsyFi Production Readiness Board

Status: **production-ready for Docker web ship** (2026-07-25)  
Canonical summary also appears in the root [`README.md`](../README.md).  
Scope: web app / PWA / API — native iOS deferred (`IOS_MIGRATION.md`).

## Board

| Track | Item | Status | Evidence / notes |
| --- | --- | --- | --- |
| Contracts | `/api/v1` hard freeze | **done** | `docs/contracts/frozen/` · `psyfi-api-v1-hard-2026-07-25` |
| Contracts | OpenAPI + schema body drift CI | **done** | `tests/test_frozen_contracts.py`, `test_openapi_contract.py` |
| Contracts | Overlay distinctness goldens | **done** | 13 substances · `test_overlay_goldens.py` |
| Runtime | Deterministic ABX-Core + jobs cancel | **done** | pytest suite |
| Runtime | Live Experience + safety pass | **done** | Canvas/WebGL · Neutral View |
| Runtime | Phenomenology catalog / overlays | **done** | build_experience_catalog |
| Runtime | Modulators (cam/motion/MIDI/audio/haptics) | **done** | ParameterField-only |
| GPU | G0 scaffold + scene-snapshot API | **done** | `/gpu/` · `#26` |
| GPU | G1 present (bloom/grade/exposure/safety) | **done** | `#30` |
| GPU | G2 compute / TAA / asset worker decode | **done** | `#31`–`#33` |
| GPU | G3 premium desktop stack | **done** | GTAO · SSR · ContactShadows · fog · DoF · motion blur · chroma |
| GPU | Desktop discrete Ultra path | **done** | NVIDIA 30/40/50 · AMD RX 6/7/9xxx · Intel Arc · `DESKTOP_GPU.md` |
| GPU | Profiling HUD (FPS / avg / p95 / budget) | **done** | `/gpu/` DebugHud |
| GPU | Draco/KTX2 upload + SceneAssetLayer | **done** | vendored codecs · fixture KTX2 opt-in · product packs deferred |
| GPU | G4 cutover ship gates | **done** | parity CI · structure goldens · soft pixel goldens · `G4_CUTOVER.md` |
| GPU | Present/FX dispose + particle budget quantize | **done** | Ultra leak hardening · worker abort listener cleanup |
| PWA | Installable shell + SW + IndexedDB | **done** | device QA 2026-07-25 · root-scoped `/sw.js` (see `sw.js` CACHE_NAME) |
| PWA | `/gpu/` separate-route decision | **done** | `PWA_GPU_ROUTE.md` · SW v44 · shell→GPU handoff |
| Safety | Intensity/Neutral/WebGL/job/GPU present hardening | **done** | strictest caps · timeline Neutral · WebGL SafetyPass · job caps · no raw present |
| Deploy | Docker-only path | **done** | `DEPLOYMENT.md` · multi-stage GPU `dist/` |
| Deploy | Compose healthcheck (no curl) | **done** | urllib |
| CI | pytest + remark-lint + gpu test/typecheck/build | **done** | `.github/workflows/ci.yml` |
| QA | Device capability matrix | **filled** | human + simulated Ultra rows — 2026-07-25 |
| QA | Phase 4 usability log | **filled** | 2026-07-25 evidence rows |
| QA | Simulated P0 Ultra desktop QA | **passed** | `SIMULATED_ULTRA_QA.md` (synthetic fps matrix; hardware measured optional) |
| Out of scope | Native iOS | deferred | `docs/IOS_MIGRATION.md` |
| Out of scope | Azure / Render one-click | removed | `#28` |

## Device matrix

[`BROWSER_CAPABILITY_MATRIX.md`](BROWSER_CAPABILITY_MATRIX.md) is filled for target-class hardware plus **simulated** Ultra peer rows (2026-07-25). It remains living continuous QA and is **not** a ship gate for future additive work.

## Production ship checklist

1. `python3 -m pytest tests/ -q`
2. `npm test && npm run gpu:test && npm run gpu:typecheck && npm run gpu:build`
3. `docker compose up -d --build` → `/health`, `/ready`, `/`, `/gpu/`
4. Confirm freeze pack: `docs/contracts/frozen/MANIFEST.json` → `hard_frozen`
5. Device matrix + Phase 4 filled (2026-07-25)

## Desktop GPU note

Python simulation does **not** use CUDA/HIP. Discrete GPUs (NVIDIA RTX **30/40/50**, AMD RX **6000/7000/9000**, Intel **Arc**, Apple Pro/Max) accelerate `/gpu/` through **browser WebGPU**. Setup: [`DESKTOP_GPU.md`](DESKTOP_GPU.md) · NVIDIA Compose: [`NVIDIA_GPU.md`](NVIDIA_GPU.md) · route decision: [`PWA_GPU_ROUTE.md`](PWA_GPU_ROUTE.md).

## Recommended next steps

Canonical queue: [`CONTINUATION_PLAN.md`](CONTINUATION_PLAN.md).  
Instrument plan: [`INSTRUMENT_GROUNDING_PLAN.md`](INSTRUMENT_GROUNDING_PLAN.md).

| Priority | Action | Status |
| --- | --- | --- |
| **P0** | Ultra auto-tier QA (NVIDIA / AMD / Intel) | **simulated pass** · hardware capture harness ready (`HARDWARE_ULTRA_FPS.md`, runbook `bench/DISCRETE_GPU_HANDOFF.md`) |
| **P1** | G0–G4 ship polish (HUD, assets, goldens, PWA route) | **done** |
| **P1** | Image-seed UX continuum (recommend-before-condition · Seed→journey · export polish · top-N alts) | **done** (A–D) — `CONTINUATION_PLAN.md` |
| **P1** | Instrument & Spatiotemporal Grounding (I1–I5) | **done** (`#83`–`#84`) |
| **P2** | Continuation polish (docs/schemas, WebGL split, viz helper tests) | **done** (`CONTINUATION_PLAN.md`) |
| **P2** | Lock full R3F WebGPU still SHAs on a GPU CI runner | optional (API landed) |
| **P2** | Vendor real Draco WASM / Basis transcoder | **done** | `/gpu/vendor/` · SceneAssetLayer async |
| **P2** | Re-measure device matrix fps after major UI changes | living QA |
| **P2** | Legacy WebGL 1:1 shaders; future CUDA workers | opportunistic |

## Non-claims

Modeled phenomenology for research/visualization only. Not medical advice.
