# Spec: Public API v1

Status: ready-for-agent. The remaining gap is GitHub issue #20. This file stays the decision record. Do not reopen the freeze.
Seam: the FastAPI app, its OpenAPI path set, and the freeze pack.

## Problem Statement

A browser, a script, and a later GPU client all need one stable way to ask the Python instrument for a simulation, a preset, a visual field, or a scene snapshot. If each surface invents its own payload, the shell and the GPU lab drift apart, and a rename silently breaks a frozen client.

## Solution

`/api/v1` is the public browser API. Legacy `/api/*` and `/simulate/` mirror the same handlers. The freeze pack is the contract. Additive fields and routes are allowed. A rename, removal, or semantic break needs a new API version or a new freeze id. The instrument is research and visualization. Responses are modeled outputs, not medical, diagnostic, or therapeutic findings.

## User Stories

1. As a browser operator, I want one canonical prefix, so that the shell and the GPU lab call the same contract.
2. As a browser operator, I want the legacy `/api` and `/simulate/` paths to keep working, so that an older shell does not break on the freeze.
3. As an API client, I want `GET /health` and `GET /ready` (and `/api/v1/ready`), so that I can tell a live process from a process that is missing presets or shell assets.
4. As an API client, I want `GET /api/v1/info`, so that I can read the service version and whether server telemetry is enabled.
5. As an API client, I want `POST /api/v1/simulate/`, so that I can run one seeded simulation and receive metrics, a session document, and a provenance id.
6. As an API client, I want `POST /api/v1/jobs/simulate` plus `GET` and `DELETE /api/v1/jobs/{id}`, so that a long run can be watched and cancelled.
7. As an API client, I want `GET /api/v1/presets/` and `GET /api/v1/presets/{id}`, so that I can list substance presets and read one.
8. As an API client, I want `GET /api/v1/experiences`, `GET /api/v1/experiences/{id}`, and `GET /api/v1/substances`, so that I can drive Live Experience from the catalog.
9. As an API client, I want `POST /api/v1/visualize/parameter-timeline` and `POST /api/v1/visualize/field-frame`, so that I can get an immutable ParameterField without treating the UI as authority.
10. As an API client, I want `POST /api/v1/visualize/scene-snapshot`, so that the GPU lab receives one immutable scene description.
11. As an API client, I want image-seed, image-seed JSON, image-seed journey, export-journey, planner, and journey routes, so that Pass 1, Pass 2, and the instrument objects share the same API.
12. As an API client, I want telemetry status, opt-in, and events under `/api/v1/telemetry`, so that diagnostics stay behind the same prefix.
13. As a maintainer, I want the living OpenAPI path set to match the app, so that a new route cannot land only in code or only in the snapshot.
14. As a maintainer, I want the frozen OpenAPI path set to equal the living snapshot, so that the freeze pack cannot drift from the app.
15. As a maintainer, I want overlay goldens to reject a substance overlay that silently collapses into another, so that catalog distinctness stays checkable.
16. As a maintainer, I want additive routes to be legal under the current freeze id, so that instrument work can land without a version break.
17. As a maintainer, I want a breaking change to require a new freeze id, so that old clients are not rewritten by accident.

## Implementation Decisions

- Simulation truth stays in Python. The UI never becomes the source of metrics.
- Visual authority is an immutable ParameterField, then a scene snapshot for the GPU path, then a mandatory safety pass.
- Public routes listed in the freeze doc are the canonical set. Legacy mounts call the same routers.
- Freeze artifacts are the OpenAPI snapshot, session schema, experience recipe schema, parameter field schema, visual frame schema, scene snapshot schema, overlay goldens, and the overlay document. Status is `hard_frozen`.
- Device-matrix and Phase 4 evidence are living QA. They are not required to keep the freeze.
- Grid size, step count, and seed on simulate requests are bounded.
- Interactive API docs are the framework default at `/docs`.
- No multi-tenant identity, account, or API key is part of this contract. The process trusts whoever can open the port.

## Testing Decisions

A good test calls the app or compares the exported contract to a fixture. It does not assert a private helper's control flow.

Prior art: OpenAPI path-set tests, frozen-contract tests, overlay golden tests, session round-trip tests, and the route tests for simulate, jobs, presets, and experiences.

## Out of Scope

- Native iOS.
- Azure or Render one-click hosting.
- A second public version prefix.
- Medical, diagnostic, or therapeutic claims.
- Authentication, per-caller quotas, and a persistent database. Those are not decisions of this freeze.

## Further Notes

`POST /api/v1/experiences/reload-catalog` exists as a dev helper and is not in the canonical route list. Additive routes are allowed. The inventory should name it or drop it.

CORS is hardcoded to allow any origin with credentials. The sample environment file's origin list and `API_KEY_REQUIRED` are not read. That is outside the freeze text and is audited separately.
