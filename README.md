<div align="center">

<img src="docs/images/psyfi-hero.jpg" alt="PsyFi consciousness field visualization hero" width="100%" />

# PsyFi

> Deterministic consciousness-field simulation workspace and phenomenology visualization instrument.\
> Web-first · ABX-Core v1.3 · research/visualization only — _not medical advice_.

[![CI](https://img.shields.io/github/actions/workflow/status/scrimshawlife-ctrl/Psy-Fi/ci.yml?branch=main\&label=CI)](https://github.com/scrimshawlife-ctrl/Psy-Fi/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python\&logoColor=white)](https://www.python.org/downloads/)
[![ABX-Core](https://img.shields.io/badge/ABX--Core-v1.3-3EE7F2)](psyfi_core/abx_core)
[![API](https://img.shields.io/badge/api-/api/v1-3EE7F2)](docs/contracts/frozen/API_V1_FREEZE.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-informational)](LICENSE)
[![PWA](https://img.shields.io/badge/PWA-installable-3EE7F2)](MOBILE_PWA_GUIDE.md)
[![Markdown Style Guide](https://img.shields.io/badge/hallmark-informational?logo=markdown)](https://github.com/vweevers/hallmark)

[Install](#install) · [Usage](#usage) · [Live Experience](#live-experience) · [Production readiness](#production-readiness) · [API](#api) · [Documentation](#documentation) · [Contributing](#contributing)

</div>

---

## Why

PsyFi keeps **simulation truth in Python** and puts an expressive, safety-clamped visual instrument in the browser:

- Deterministic ABX-Core runtime with provenance
- Substance presets + phenomenology catalog → distilled visual overlays
- Immutable `ParameterField` → Canvas / optional WebGL engines → mandatory safety pass
- Cancelable `/api/v1` jobs, IndexedDB history, installable PWA shell

> The field is expressive. The instrument is precise.

## Production readiness

Full board: [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md).

| Track                              | Status           | Notes                                                                       |
| ---------------------------------- | ---------------- | --------------------------------------------------------------------------- |
| `/api/v1` contracts                | **hard\_frozen** | `psyfi-api-v1-hard-2026-07-25`                                              |
| CI (pytest + hallmark + GPU build) | **green path**   | `.github/workflows/ci.yml`                                                  |
| Docker deploy                      | **ready**        | Compose + urllib healthcheck + GPU `dist/` bake                             |
| Live Experience + safety           | **ready**        | Neutral View · ParameterField authority                                     |
| GPU platform G0–G3                 | **ready**        | `/gpu/` present · compute · TAA · premium post                              |
| GPU G4 cutover ship gates          | **ready**        | assets · parity · goldens · [`G4_CUTOVER.md`](docs/rendering/G4_CUTOVER.md) |
| Desktop Ultra (30/40/50 + peers)   | **ready**        | NVIDIA · AMD RX · Intel Arc · Apple Pro/Max                                 |
| PWA (`/` shell + `/gpu/` route)    | **ready**        | separate `/gpu/` · SW v41 · [`PWA_GPU_ROUTE.md`](docs/PWA_GPU_ROUTE.md)      |
| Device matrix + Phase 4            | **filled**       | 2026-07-25 human + simulated Ultra QA                                       |
| Simulated Ultra QA                 | **passed**       | [`SIMULATED_ULTRA_QA.md`](docs/SIMULATED_ULTRA_QA.md)                       |
| Soft-present pixel goldens         | **ready**        | [`PIXEL_GOLDENS.md`](docs/rendering/PIXEL_GOLDENS.md)                       |
| Native iOS                         | deferred         | `docs/IOS_MIGRATION.md`                                                     |

Ship checklist: `pytest` → `npm test && npm run gpu:test && npm run gpu:build` → `docker compose up -d --build` → `/health` `/ready` `/` `/gpu/`.

**Optional next:** hardware Ultra fps confirmation; full R3F stills on a GPU CI runner.  
**Instrument track:** I1–I5 landed (instrument map, hold-and-compare, spatiotemporal anchors, planner, Journey objects) — see [`docs/CONTINUATION_PLAN.md`](docs/CONTINUATION_PLAN.md) and [`docs/INSTRUMENT_GROUNDING_PLAN.md`](docs/INSTRUMENT_GROUNDING_PLAN.md).

## Install

```bash
git clone https://github.com/scrimshawlife-ctrl/Psy-Fi.git
cd Psy-Fi
pip install -e ".[dev]"

# Optional: markdown lint/fix tooling for README
npm install
```

Optional MIDI extras are already included in the default install (`mido`, `python-rtmidi`).

## Usage

```bash
# Rebuild phenomenology catalog + substance visual overlays
python3 scripts/build_experience_catalog.py

# Hard-freeze sync (after OpenAPI / golden updates)
python3 scripts/export_openapi.py
python3 scripts/regenerate_overlay_goldens.py
python3 scripts/sync_frozen_contracts.py

# Tests
python3 -m pytest tests/ -q
npm test   # hallmark README lint
npm run gpu:test

# Optional GPU platform (R3F + WebGPU)
npm run gpu:build
# → served at /gpu/ when the API runs

# Dev server
python3 scripts/run_dev_server.py
# → http://localhost:8000

# Production-style Docker
docker compose up -d --build
# → http://localhost:8000
```

## Live Experience

1. Open **Live Experience**
2. Choose substance + recipe + mode (`Open` / `Attractor` / `Void` / `Power`)
3. Set intensity / seed; scrub the phase timeline
4. Hit **Neutral View** (`N`) anytime
5. Optional: camera / motion / MIDI modulators (ParameterField only), export, bridge from the last workspace simulation

```bash
curl -s 'http://localhost:8000/api/v1/substances' | python3 -m json.tool | head
curl -s -X POST http://localhost:8000/api/v1/visualize/parameter-timeline \
  -H 'Content-Type: application/json' \
  -d '{"substance":"dmt","mode":"power","intensity":0.8,"seed":1337,"steps":8}'
```

## Features

| Area                                      | Status                    |
| ----------------------------------------- | ------------------------- |
| ABX-Core deterministic runtime            | yes                       |
| Modular field engines                     | yes                       |
| 22+ substance presets                     | yes                       |
| Phenomenology catalog + overlays          | yes                       |
| Live Experience (Canvas + optional WebGL) | yes                       |
| Cancelable `/api/v1/jobs`                 | yes                       |
| PWA shell + IndexedDB history             | yes                       |
| MIDI / audio / haptics modulators         | yes (opt-in, gated)       |
| WebGPU `/gpu/` platform (G0–G2)           | yes                       |
| `/api/v1` hard freeze                     | yes                       |
| Native iOS                                | deferred (separate track) |

## Architecture

```text
seed + substance/experience + optional modulators
        ↓
immutable PsyFiParameterField
        ↓
Canvas / WebGL engines
        ↓
mandatory SafetyPass
        ↓
quiet chrome + provenance
```

Simulation metrics remain Python-authoritative. UI never becomes the source of truth.

## API

Canonical browser API is **`/api/v1`** (**hard-frozen**). Legacy `/api/*` and `/simulate/` remain mirrored.

- OpenAPI living snapshot: [`docs/contracts/openapi.json`](docs/contracts/openapi.json)
- Hard-freeze pack: [`docs/contracts/frozen/`](docs/contracts/frozen/)
- Interactive docs: `/docs` when the server is running

## Documentation

| Doc                                                                                | Purpose                         |
| ---------------------------------------------------------------------------------- | ------------------------------- |
| [`AGENTS.md`](AGENTS.md)                                                           | Agent contract (intent → spec/plan → code) |
| [`intent/`](intent/)                                                               | Stage-0 intent blanks — no product invent |
| [`PROJECT_INDEX.md`](PROJECT_INDEX.md)                                             | Codebase map & ownership index  |
| [`.agents/skills/codebase-memory/`](.agents/skills/codebase-memory/)               | Codebase Memory graph skill     |
| [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md)                     | Production readiness board      |
| [`docs/CONTINUATION_PLAN.md`](docs/CONTINUATION_PLAN.md)                           | Web-track next steps            |
| [`docs/INSTRUMENT_GROUNDING_PLAN.md`](docs/INSTRUMENT_GROUNDING_PLAN.md)           | Instrument + spatiotemporal grounding plan (I1–I5) |
| [`docs/rendering/ROADMAP.md`](docs/rendering/ROADMAP.md)                           | GPU G0–G5 roadmap               |
| [`docs/rendering/G4_CUTOVER.md`](docs/rendering/G4_CUTOVER.md)                     | G4 cutover checklist            |
| [`docs/rendering/PIXEL_GOLDENS.md`](docs/rendering/PIXEL_GOLDENS.md)               | Soft-present pixel goldens      |
| [`docs/DESKTOP_GPU.md`](docs/DESKTOP_GPU.md)                                       | Multi-vendor WebGPU Ultra       |
| [`docs/PWA_GPU_ROUTE.md`](docs/PWA_GPU_ROUTE.md)                                   | `/gpu/` separate-route decision |
| [`docs/SIMULATED_ULTRA_QA.md`](docs/SIMULATED_ULTRA_QA.md)                         | Simulated P0 Ultra desktop QA   |
| [`docs/NVIDIA_GPU.md`](docs/NVIDIA_GPU.md)                                         | NVIDIA drivers + Compose        |
| [`PLANS.md`](PLANS.md)                                                             | Product phases + gates          |
| [`docs/VISUAL_EXPERIENCES.md`](docs/VISUAL_EXPERIENCES.md)                         | Live Experience guide           |
| [`docs/rendering/README.md`](docs/rendering/README.md)                             | WebGPU platform docs            |
| [`DEPLOYMENT.md`](DEPLOYMENT.md)                                                   | Docker deploy guide             |
| [`docs/PHENOMENOLOGY_PIPELINE.md`](docs/PHENOMENOLOGY_PIPELINE.md)                 | Scraped → overlays              |
| [`docs/BROWSER_CAPABILITY_MATRIX.md`](docs/BROWSER_CAPABILITY_MATRIX.md)           | Device QA (filled)              |
| [`docs/contracts/frozen/API_V1_FREEZE.md`](docs/contracts/frozen/API_V1_FREEZE.md) | Contract hard freeze            |
| [`docs/PHASE4_USABILITY.md`](docs/PHASE4_USABILITY.md)                             | Usability checklist             |
| [`MOBILE_PWA_GUIDE.md`](MOBILE_PWA_GUIDE.md)                                       | PWA guidance                    |
| [`docs/IOS_MIGRATION.md`](docs/IOS_MIGRATION.md)                                   | Deferred native notes           |

## Non-claims

Modeled phenomenology for research and visualization only.\
Not medical, diagnostic, or therapeutic advice.\
Motifs/parameters are **INFERRED**; source existence is **OBSERVED**.

## Contributing

- Keep simulation outputs deterministic for fixed seeds/params
- Prefer `/api/v1` for new routes; update OpenAPI + run `scripts/sync_frozen_contracts.py`
- Do not bypass the visual safety pass
- Do not add medical/healing claims to UI copy
- Native iOS stays out of the web track
- Device matrix / Phase 4 are living QA — not freeze blockers
- Keep root markdown hallmark-clean: `npx hallmark fix README.md`

```bash
python3 -m pytest tests/ -q
npx hallmark lint README.md
python3 scripts/export_openapi.py
python3 scripts/build_experience_catalog.py
python3 scripts/sync_frozen_contracts.py
```

## License

[MIT](LICENSE) © Applied Alchemy Labs.


## License

Copyright © 2026 Zero State LLC. All Rights Reserved. Licensed under the Zero State Proprietary License v1.0. See [`LICENSE`](LICENSE).

Third-party components remain subject to their respective licenses.
