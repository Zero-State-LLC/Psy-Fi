# PsyFi Project Index

Navigable map of the Psy-Fi monorepo for contributors and agents. Prefer this file when locating ownership, entry points, and contracts; deep detail lives in the linked docs.

**Product:** deterministic consciousness-field simulation (Python) + web visualization instrument (browser). Research/visualization only — not medical advice.  
**Freeze:** `/api/v1` hard-frozen as `psyfi-api-v1-hard-2026-07-25` — see [`docs/contracts/frozen/API_V1_FREEZE.md`](docs/contracts/frozen/API_V1_FREEZE.md).  
**Status board:** [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md) · next work: [`docs/CONTINUATION_PLAN.md`](docs/CONTINUATION_PLAN.md) · phases: [`PLANS.md`](PLANS.md).

### Codebase Memory (graph index)

Indexed with [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) for structural navigation.

| Item | Value |
| --- | --- |
| Project name | `workspace` (when rooted at `/workspace`) |
| Status | ready |
| Scale | ~5.4k nodes · ~13k edges |
| Languages | Python, TypeScript, JavaScript, CSS, Bash, YAML, HTML, TOML |
| Skill | [`.agents/skills/codebase-memory/SKILL.md`](.agents/skills/codebase-memory/SKILL.md) |
| MCP (Cursor) | [`.cursor/mcp.json`](.cursor/mcp.json) |
| ADR | stored in graph via `manage_adr` |

```bash
# Install (once) then index / refresh
curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
codebase-memory-mcp cli index_repository --repo-path .
codebase-memory-mcp cli get_architecture --project workspace
```

---

## Architecture (one glance)

```text
Browser
  ├─ `/`     legacy PWA shell (Canvas / WebGL Live Experience)
  └─ `/gpu/` optional R3F + WebGPU platform
        │ HTTPS /api/v1 (hard-frozen)
FastAPI (psyfi_api)
        │ typed Python calls
psyfi_core (ABX-Core v1.3 + engines + presets + visualization)
```

**Invariants**

1. Simulation truth stays in Python; UI never becomes authoritative.
2. Visual authority is the immutable `PsyFiParameterField` / `scene_snapshot`, then a mandatory safety pass.
3. Public browser API is `/api/v1`; legacy `/api/*` and `/simulate/` are mirrors.

Details: [`docs/WEB_ARCHITECTURE.md`](docs/WEB_ARCHITECTURE.md), [`docs/FRONTEND_BOUNDARY.md`](docs/FRONTEND_BOUNDARY.md).

---

## Repository layout

| Path | Role |
| --- | --- |
| [`psyfi_core/`](psyfi_core/) | Deterministic simulation authority (ABX runtime, engines, models, presets, viz schemas) |
| [`psyfi_api/`](psyfi_api/) | FastAPI app, routers, Jinja shell, static PWA assets |
| [`packages/psyfi-gpu-renderer/`](packages/psyfi-gpu-renderer/) | Optional Vite + React + R3F WebGPU client → served at `/gpu/` |
| [`data/phenomenology/`](data/phenomenology/) | Source phenomenology → catalog / overlays (build scripts) |
| [`docs/`](docs/) | Architecture, contracts, rendering, QA, design |
| [`AGENTS.md`](AGENTS.md) | Agent contract (intent → spec/plan → code; Escalation) |
| [`intent/`](intent/) | Stage-0 intent blanks — no product invent |
| [`scripts/`](scripts/) | Dev server, catalog build, OpenAPI/schema/freeze sync, deploy |
| [`tests/`](tests/) | Pytest suite (API, determinism, freeze, overlays, shell) |
| [`examples/`](examples/) | Sample usage |
| [`.agents/skills/hallmark/`](.agents/skills/hallmark/) | Hallmark design skill (agent tooling) |

Root packaging: Python via [`pyproject.toml`](pyproject.toml); npm workspaces via [`package.json`](package.json).

---

## Entry points

| Action | Command / path |
| --- | --- |
| Dev server | `python3 scripts/run_dev_server.py` → `http://localhost:8000` |
| Docker | `docker compose up -d --build` |
| API app | `psyfi_api/main.py` |
| Legacy UI | `GET /` → `psyfi_api/templates/index.html` + `static/app.js` |
| GPU UI | `npm run gpu:build` → mount `packages/psyfi-gpu-renderer/dist` at `/gpu/` |
| Health | `GET /health`, `GET /ready` |
| Interactive OpenAPI | `/docs` when server is running |
| Python tests | `python3 -m pytest tests/ -q` |
| README lint | `npm test` (hallmark) |
| GPU tests / build | `npm run gpu:test` · `npm run gpu:build` |

---

## `psyfi_core` — simulation authority

| Module | Purpose |
| --- | --- |
| [`abx_core/`](psyfi_core/abx_core/) | ABX runtime, provenance, metrics, determinism errors |
| [`engines/`](psyfi_core/engines/) | Modular field engines (`*_phi`, `*_omega`, valence, resonance, …) |
| [`models/`](psyfi_core/models/) | Pydantic: session, substance presets, resonance frame, profiles |
| [`presets/`](psyfi_core/presets/) | `substance_presets.json` + schema |
| [`experiences/`](psyfi_core/experiences/) | Builtin catalog JSON, catalog loader, parameter mapper → overlays |
| [`visualization/`](psyfi_core/visualization/) | Magnitude, scene snapshot, image seed, export journey, asset packs |
| [`schemas/`](psyfi_core/schemas/) | Exported JSON Schema (`session`, `visualization`) |
| [`midi/`](psyfi_core/midi/) | MIDI service (process-global) |
| [`config.py`](psyfi_core/config.py) | `ABXCoreConfig` / `PsyFiConfig` |

Config and public exports: [`psyfi_core/__init__.py`](psyfi_core/__init__.py).

---

## `psyfi_api` — HTTP + product shell

| File / dir | Purpose |
| --- | --- |
| [`main.py`](psyfi_api/main.py) | App, mounts (`/static`, `/assets/icons`, `/gpu`), routers, `/`, SW, health |
| [`simulation_service.py`](psyfi_api/simulation_service.py) | Sync simulate orchestration |
| [`jobs.py`](psyfi_api/jobs.py) | In-memory cancelable job store |
| [`telemetry.py`](psyfi_api/telemetry.py) | Opt-in telemetry (off by default) |
| [`routers/simulate.py`](psyfi_api/routers/simulate.py) | `POST …/simulate/` |
| [`routers/jobs.py`](psyfi_api/routers/jobs.py) | Async simulate jobs |
| [`routers/presets.py`](psyfi_api/routers/presets.py) | Substance preset catalog |
| [`routers/experiences.py`](psyfi_api/routers/experiences.py) | Experiences, substances, visualize/\* (timeline, field-frame, scene-snapshot, image-seed, export) |
| [`routers/midi.py`](psyfi_api/routers/midi.py) | MIDI devices / CC / notes |
| [`routers/telemetry.py`](psyfi_api/routers/telemetry.py) | Telemetry status / opt-in / events |
| [`templates/index.html`](psyfi_api/templates/index.html) | Legacy shell |
| [`static/app.js`](psyfi_api/static/app.js) | Client: jobs, presets, IndexedDB, Live Experience wiring |
| [`static/viz/`](psyfi_api/static/viz/) | Canvas/WebGL engines, ParameterField, safety pass, experience player |
| [`static/sw.js`](psyfi_api/static/sw.js) | PWA service worker (served from `/sw.js` with root scope) |

Route inventory: [`docs/API_CONTRACT_INVENTORY.md`](docs/API_CONTRACT_INVENTORY.md).

### Canonical `/api/v1` routes (do not rename lightly)

- `POST /api/v1/simulate/`
- `POST /api/v1/jobs/simulate` · `GET/DELETE /api/v1/jobs/{id}`
- `GET /api/v1/presets/` · `GET /api/v1/presets/{id}`
- `GET /api/v1/experiences` · `GET /api/v1/experiences/{id}`
- `GET /api/v1/substances`
- `POST /api/v1/visualize/parameter-timeline`
- `POST /api/v1/visualize/field-frame`
- `POST /api/v1/visualize/scene-snapshot` ← sole GPU render input
- `POST /api/v1/visualize/image-seed` (+ `/json`)
- `POST /api/v1/visualize/image-seed-journey`
- `POST /api/v1/visualize/export-journey`
- `GET/POST /api/v1/telemetry/*` · MIDI under `/api/v1/midi/*`
- `GET /health` · `GET /ready`

---

## GPU package — `@psyfi/gpu-renderer`

Root: [`packages/psyfi-gpu-renderer/`](packages/psyfi-gpu-renderer/). Consumes **only** `psyfi.scene_snapshot.v1` from `POST /api/v1/visualize/scene-snapshot`.

| `src/` area | Purpose |
| --- | --- |
| `App.tsx` / `main.tsx` | Shell entry |
| `bridge/` | Launch params, snapshot store, image-seed handoff, analysis publisher |
| `contracts/` | Scene snapshot, render graph, quality tiers, GPU adapter, G4 parity |
| `Renderer/` · `SceneGraph/` · `procedural/` | R3F scene + procedural fields |
| `compute/` | Flow / particles / LOD / cull (WebGPU compute where available) |
| `AssetPipeline/` | Draco / KTX2 / Basis decode + GPU upload + worker |
| `PostProcessing/` · `Effects/` · `Lighting/` · `CameraPipeline/` | Present stack, TAA, safety note, premium passes |
| `Profiling/` · `DebugOverlay/` · `qa/` · `goldens/` | Budgets, Ultra QA, pixel goldens |
| `ShaderLibrary/` · `shaders/` | WGSL / shader registry |
| `MaterialSystem/` | Materials |

Docs hub: [`docs/rendering/README.md`](docs/rendering/README.md) · cutover: [`docs/rendering/G4_CUTOVER.md`](docs/rendering/G4_CUTOVER.md).

---

## Contracts & schemas

| Artifact | Location |
| --- | --- |
| Living OpenAPI | [`docs/contracts/openapi.json`](docs/contracts/openapi.json) |
| Hard-freeze pack | [`docs/contracts/frozen/`](docs/contracts/frozen/) |
| Freeze policy | [`docs/contracts/frozen/API_V1_FREEZE.md`](docs/contracts/frozen/API_V1_FREEZE.md) |
| Fixtures | [`docs/contracts/fixtures/`](docs/contracts/fixtures/) |
| Session / viz JSON Schema (core) | [`psyfi_core/schemas/`](psyfi_core/schemas/) |
| Exported schema copies | [`docs/schemas/`](docs/schemas/) |
| Design tokens | [`docs/style/`](docs/style/), [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) |

**Resync freeze**

```bash
python3 scripts/export_openapi.py
python3 scripts/build_experience_catalog.py
python3 scripts/regenerate_overlay_goldens.py
python3 scripts/sync_frozen_contracts.py
```

---

## Scripts

| Script | Purpose |
| --- | --- |
| [`run_dev_server.py`](scripts/run_dev_server.py) | Local uvicorn |
| [`build_experience_catalog.py`](scripts/build_experience_catalog.py) | Phenomenology → catalog + overlays |
| [`export_openapi.py`](scripts/export_openapi.py) | OpenAPI snapshot |
| [`export_schemas.py`](scripts/export_schemas.py) | JSON Schema export |
| [`sync_frozen_contracts.py`](scripts/sync_frozen_contracts.py) | Freeze pack sync |
| [`regenerate_overlay_goldens.py`](scripts/regenerate_overlay_goldens.py) | Substance overlay goldens |
| [`generate_pwa_icons.py`](scripts/generate_pwa_icons.py) | PWA icons |
| [`vendor_gpu_codecs.sh`](scripts/vendor_gpu_codecs.sh) | Draco / Basis vendors |
| [`deploy.sh`](scripts/deploy.sh) · [`check_nvidia_host.sh`](scripts/check_nvidia_host.sh) | Deploy / NVIDIA host checks |
| [`merge_ultra_fps_measured.py`](scripts/merge_ultra_fps_measured.py) | Ultra fps matrix merge |

---

## Tests & CI

| Area | Where |
| --- | --- |
| Python | [`tests/`](tests/) — API, jobs, freeze, overlays, experiences, shell assets, Ultra QA, scene snapshot, MIDI, … |
| GPU / TS | `packages/psyfi-gpu-renderer` via `npm run gpu:test` |
| CI | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — pytest + hallmark + GPU build |
| Startup smoke | [`test_startup.py`](test_startup.py) |

---

## Documentation map

| Doc | When to open it |
| --- | --- |
| [`README.md`](README.md) | Install, usage, ship checklist |
| [`PLANS.md`](PLANS.md) | Phase gates and product direction |
| [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md) | Ship status board |
| [`docs/CONTINUATION_PLAN.md`](docs/CONTINUATION_PLAN.md) | Active engineering queue |
| [`docs/WEB_ARCHITECTURE.md`](docs/WEB_ARCHITECTURE.md) | System shape and ownership |
| [`docs/FRONTEND_BOUNDARY.md`](docs/FRONTEND_BOUNDARY.md) | `/` vs `/gpu/` decision |
| [`docs/API_CONTRACT_INVENTORY.md`](docs/API_CONTRACT_INVENTORY.md) | Live routes + static/PWA inventory |
| [`docs/VISUAL_EXPERIENCES.md`](docs/VISUAL_EXPERIENCES.md) | Live Experience product guide |
| [`docs/PHENOMENOLOGY_PIPELINE.md`](docs/PHENOMENOLOGY_PIPELINE.md) | Scraped data → overlays |
| [`docs/IMAGE_SEED_PIPELINE.md`](docs/IMAGE_SEED_PIPELINE.md) | Image-seed two-pass + GPU handoff |
| [`docs/rendering/`](docs/rendering/) | GPU architecture, budgets, G4, goldens, migration |
| [`docs/DESKTOP_GPU.md`](docs/DESKTOP_GPU.md) · [`docs/NVIDIA_GPU.md`](docs/NVIDIA_GPU.md) | Multi-vendor Ultra / NVIDIA Compose |
| [`docs/PWA_GPU_ROUTE.md`](docs/PWA_GPU_ROUTE.md) · [`MOBILE_PWA_GUIDE.md`](MOBILE_PWA_GUIDE.md) | PWA + `/gpu/` route |
| [`docs/BROWSER_CAPABILITY_MATRIX.md`](docs/BROWSER_CAPABILITY_MATRIX.md) | Device QA |
| [`docs/SIMULATED_ULTRA_QA.md`](docs/SIMULATED_ULTRA_QA.md) | Simulated Ultra pass |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) · [`QUICK_DEPLOY.md`](QUICK_DEPLOY.md) | Docker deploy |
| [`docs/MIDI.md`](docs/MIDI.md) | MIDI surface |
| [`docs/IOS_MIGRATION.md`](docs/IOS_MIGRATION.md) | Deferred native track |
| [`design.md`](design.md) · [`docs/FIGMA_GUIDE.md`](docs/FIGMA_GUIDE.md) | Design notes |
| [`MEMORIES.md`](MEMORIES.md) | Open/rejected automation bug ledger |
| [`AGENTS.md`](AGENTS.md) · [`intent/`](intent/) | Agent contract + intent blanks |
| [`CLAUDE.md`](CLAUDE.md) | Thin adapter → `AGENTS.md` only |

---

## Data flow (Live Experience)

```text
substance + recipe + mode + intensity + seed
        → psyfi_core experiences / parameter_mapper
        → immutable PsyFiParameterField (+ timeline / field-frame / scene-snapshot)
        → Canvas/WebGL (`static/viz`) or GPU (`/gpu/` + scene-snapshot)
        → SafetyPass
        → chrome + provenance (IndexedDB history on shell)
```

Phenomenology rebuild: `python3 scripts/build_experience_catalog.py` (sources under `data/phenomenology/`).

---

## Deploy & env

| Item | Location |
| --- | --- |
| Compose | [`docker-compose.yml`](docker-compose.yml) |
| Image | [`Dockerfile`](Dockerfile) |
| Nginx | [`nginx.conf`](nginx.conf) |
| Env template | [`.env.example`](.env.example) |
| GPU serve toggle | `PSYFI_SERVE_GPU` (default on when `dist/` exists) |

---

## Contribution quick rules

- Non-trivial work: intent → spec/plan → code ([`AGENTS.md`](AGENTS.md), [`intent/`](intent/)).
- Keep outputs deterministic for fixed seeds/params.
- Prefer `/api/v1`; after contract changes run freeze resync scripts.
- Do not bypass the visual safety pass.
- Do not add medical/healing claims.
- Native iOS is out of the web track.
- Keep root README hallmark-clean: `npx hallmark fix README.md`.
