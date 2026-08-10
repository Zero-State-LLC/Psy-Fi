# Web-First Architecture

## Decision

PsyFi's first production client is the web application. The repository retains the deterministic Python simulation engine and FastAPI service while introducing a clean frontend boundary. A full TypeScript rewrite of the simulation core is not currently authorized; portability is achieved through versioned contracts, fixtures, and renderer-independent schemas.

## Target System

```text
Browser client
  ├─ application shell and accessible UI
  ├─ local session state
  ├─ visualization renderer
  ├─ IndexedDB persistence
  ├─ Web Worker compute adapters
  └─ browser capability adapters
          │ HTTPS / versioned JSON
FastAPI service
  ├─ request validation
  ├─ simulation orchestration
  ├─ provenance and metrics
  ├─ preset/catalog endpoints
  └─ export endpoints
          │ typed Python calls
PsyFi deterministic core
  ├─ ABX runtime
  ├─ field engines
  ├─ models and presets
  └─ deterministic tests and fixtures
```

## Repository Evolution

Preferred longer-term layout:

```text
packages/
  psyfi-gpu-renderer/   # R3F + WebGPU platform (optional /gpu/)
psyfi_api/               # FastAPI + legacy web shell at /
psyfi_core/              # deterministic Python authority + session/scene snapshots
tests/
docs/
  rendering/             # GPU architecture, budgets, migration
```

Migration is incremental and reuses current infrastructure first:

- contracts live as Pydantic models (`psyfi_core/models/session.py`) and exported schemas (`psyfi_core/schemas/`, `docs/schemas/`)
- OpenAPI snapshots export from the live FastAPI app into `docs/contracts/`
- design tokens alias onto existing `docs/style` / `psyfi_api/static` CSS variables
- icons are served from existing `docs/icons`
- frontend boundary: legacy shell + optional GPU platform (`docs/FRONTEND_BOUNDARY.md`, `docs/rendering/`)
- GPU renderer consumes `POST /api/v1/visualize/scene-snapshot` only (no inference in the client)

Existing static assets remain operational until GPU cutover gates pass (`docs/rendering/MIGRATION_PLAN.md`).

## Frontend Selection Gate

Do not select a framework by trend alone. Evaluate the existing deployment model, contributor skill, bundle/runtime cost, static hosting needs, API coupling, accessibility tooling, and migration complexity.

Accepted paths:

1. Progressive enhancement of the existing frontend for the shortest path.
2. Vite + React/TypeScript for a client-focused application.
3. Next.js only when server rendering, route-level backend behavior, or its deployment model is demonstrably required.

The default recommendation is Vite + React + TypeScript unless a documented requirement favors Next.js.

## State Ownership

- Simulation truth: Python core output plus provenance.
- API transport state: FastAPI/Pydantic contracts.
- UI state: local and disposable unless serialized into the session schema.
- Visualization state: derived from simulation output and rendering preferences.
- Persistent user state: versioned IndexedDB records with migration functions.

UI state must never mutate or reinterpret authoritative metrics without preserving the original result.

## API Standards

- Public browser routes are versioned under `/api/v1` (legacy `/api/*` and `/simulate/` remain mirrored).
- Use Pydantic models for all request and response bodies.
- Generate OpenAPI in CI and detect breaking changes.
- Include `schema_version`, engine version, seed, parameter set, and provenance identifier in saved results.
- Use bounded inputs, explicit units, stable enums, and structured errors.
- Define cancellation and timeout behavior for long simulations.

## Visualization Architecture

The visualization layer consumes a platform-neutral schema rather than raw backend internals.

Minimum schema concepts:
- field dimensions and normalized values;
- channels, layers, palettes, and blend semantics;
- camera/view state;
- temporal frame or sequence identity;
- provenance reference;
- renderer capability requirements;
- accessibility description and reduced-motion alternative.

Legacy Live Experience uses Canvas 2D / WebGL as the compatibility baseline.
The production-grade path is the modular WebGPU platform in `packages/psyfi-gpu-renderer`
(see `docs/rendering/ARCHITECTURE.md`): immutable scene snapshots, render graph, adaptive quality.

## Browser Capability Adapters

Each optional integration must expose `supported`, `permission`, `active`, `error`, and `fallback` states:

- camera;
- device motion/orientation;
- MIDI;
- audio;
- haptics/vibration;
- WebGL/WebGPU;
- persistent storage;
- file import/export;
- installability.

No unsupported API may block the core simulation workflow.

## Security and Privacy

- Production deployment requires HTTPS.
- Treat camera, motion, MIDI, uploaded files, and exported sessions as sensitive inputs.
- Request permissions in context, never at initial load.
- Keep analytics absent or opt-in until a privacy policy and data map exist.
- Validate content type, size, shape, and schema version for imports.
- Apply rate limits and bounded computation at the API boundary.
- Do not expose internal exceptions or filesystem details.

## Testing Strategy

- Python unit/property tests for deterministic core behavior.
- API contract tests and golden fixtures.
- Frontend unit tests for state and transforms.
- Component accessibility tests.
- End-to-end tests for configure → run → inspect → save → restore → export.
- Cross-browser smoke tests.
- Visual regression tests for canonical scenes.
- Performance tests against documented device classes and budgets.

## Operational Requirements

- Health, readiness, and version endpoints.
- Structured logs with request correlation IDs, excluding sensitive payloads.
- Reproducible builds and locked dependencies.
- CI gates for tests, type checks, linting, OpenAPI drift, accessibility smoke tests, and bundle budgets.
- Rollback-safe database and cache migrations.

## Headless experiment boundary

The browser does not own experiment truth. `psyfi_core.experiments` invokes the same Python simulation used by FastAPI, measures a closed versioned observable registry, and emits deterministic receipts and datasets. Experiment correctness excludes Canvas, R3F, WebGPU, WGSL, and scene snapshots. Presentation continues to consume existing contracts without changing `/api/v1`.
