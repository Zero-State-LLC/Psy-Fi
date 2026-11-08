# Runtime audit

Source reviewed: `main` at `7ca678e00fc9c810ad795a5fdc0ff94158f8a2b9` (2026-10-24).
Specs: `docs/specs/`.
Method: read the decision, then the handler, model, workflow, or test that is supposed to enforce it. The Python suite and the GPU suite were not executed in this pass. A "conform" verdict means the source agrees. It does not mean a test run passed.

Verdicts:

- **conform** — the runtime matches the decision.
- **diverge** — the runtime contradicts the decision.
- **unproven** — the decision is a document, a device claim, or a test that only checks prose.

## Later main

Read this before the grid below. The grid is the pass on `7ca678e` (2026-10-24). It is not the open-work list.

On current `main`, after pull requests #24 through #40:

- CI runs pytest, the README lint, and the GPU build. `pyproject.toml` license text matches `LICENSE`. The Noema deploy workflow is not in the tree.
- Worker `psy-fi` is configured for `https://psy-fi.space`. The image-reading route exists. The vision bench is implemented and adds no public route. See [vision-bench.md](vision-bench.md) and the host decisions in [cloudflare-nvidia.md](cloudflare-nvidia.md).
- The old "next fixes" for pytest in CI, the license text, and the Noema workflow are done.
- Still true, and not an agent ticket unless a later accepted intent says so: catalog reload is implemented and undecided, and the public host has no login and no AI Gateway.
- The Cloudflare rows below that say `main` has no Worker are stale.
- This note did not re-score the ten-spec grid. Do not open or close issues from those counts.

## Result

Ten specs. The instrument core (seeded simulation, jobs, ParameterField, freeze pack, shell worker, telemetry default-off, GPU present safety) matches the source. The ship gate does not. CI does not run the suite the deploy spec requires, and the tests that say the project is production-ready check that the board contains the right words.

The counts below are `main` at `7ca678e`. Branch `spec/cloudflare-nvidia-image-reading` adds the Worker, the Container binding, and `POST /api/v1/visualize/image-reading`. That branch is not merged and is not deployed. The Noema workflow is still on `main`.

| Spec | Conform | Diverge | Unproven |
| --- | --- | --- | --- |
| Public API v1 | 6 | 2 | 0 |
| Simulation and jobs | 5 | 1 | 0 |
| Live Experience | 5 | 1 | 1 |
| Image seed | 4 | 1 | 0 |
| GPU Lab | 5 | 1 | 2 |
| Shell and PWA | 4 | 0 | 1 |
| MIDI | 3 | 2 | 0 |
| Telemetry | 4 | 1 | 0 |
| Deploy and CI | 3 | 6 | 1 |
| Cloudflare and NVIDIA | 1 | 3 | 1 |

## Public API v1

**Conform.** `/api/v1` and the legacy mounts share routers (`psyfi_api/main.py`). The freeze manifest status is `hard_frozen` with id `psyfi-api-v1-hard-2026-07-25`. Frozen OpenAPI, schema bodies, and overlay goldens have tests that compare files to the live app (`tests/test_frozen_contracts.py`, `tests/test_openapi_contract.py`). Simulate bounds are on the request model (width and height 8–512, steps 1–1000). Preset miss raises `PresetNotFoundError` and the route returns 404.

**Diverge.** CORS is `allow_origins=["*"]` with `allow_credentials=True` in `psyfi_api/main.py`. `.env.example` defines `ALLOWED_ORIGINS`, `API_KEY_REQUIRED`, `SECRET_KEY`, and `RATE_LIMIT_ENABLED`. Nothing in the Python tree reads those names. The spec's trust decision is "whoever can open the port." The sample environment file describes a different control plane that does not exist.

**Diverge.** `POST /api/v1/experiences/reload-catalog` is implemented and returns the catalog filesystem path. The freeze route list does not name it. Additive routes are allowed, so this is an inventory miss, not a version break.

## Simulation and jobs

**Conform.** `run_simulation` uses an explicit seed and the preset registry. Job slots are 4 and retention is 64 (`psyfi_api/jobs.py`). `finalize_after_run` holds the same lock as cancel and drops the result when cancel is set. Job ids are `job_` plus 12 random hex characters. There is no list route. Tests cover create, cancel, slot refusal, and retention (`tests/test_jobs_and_cancel.py`). Engine determinism tests exist.

**Diverge.** The synchronous simulate route does not acquire a worker slot. Overlapping `POST /api/v1/simulate/` calls, and scene snapshots with `include_simulation`, bypass the cap of four. The spec requires bounded parallel work. Only the job route is bounded.

## Live Experience

**Conform.** Neutral rematerializes frames (`tests/test_scene_snapshot.py` names that behavior, and `experiences.py` rebuilds through `map_parameters` when `neutral_view` is set). Intensity uses the strictest of experience and overlay (same test module). Reduce Motion, mode difference, and catalog coverage have tests in `tests/test_experiences.py`. Planner text is labeled inferred and includes the not-medical-advice sentence (`psyfi_core/visualization/planner.py`). Canvas safety lives in `psyfi_api/static/viz/safetyPass.js`.

**Diverge.** Story 15 says planner text is shown as text. `psyfi_api/static/app.js` assigns `body.planner_text` through `innerHTML`. Operator notes are copied into that string (truncated). The same pattern interpolates preset names, history fields, comparison titles, and journey titles. A note can change the page.

**Unproven.** Hold-and-compare, the station dial, and phone usability are claimed in the continuation plan and Phase 4 log. This pass did not drive the browser. The Python tests do not click those controls.

## Image seed

**Conform.** Raw bytes are not written to disk. The same builder path serves multipart and JSON. Recommend-only skips conditioning. The journey route rejects `recommend_only`. Influence changes pixels. Tests cover those cases in `tests/test_image_seed.py`. The working image is resized to a max edge of 384 after decode (`psyfi_core/visualization/image_seed.py`).

**Diverge.** The bound is not in front of allocation. Multipart does `await file.read()` with no limit (`psyfi_api/routers/experiences.py`). The 12 MB check runs after that read, inside `decode_image_bytes`. `Image.open` plus `convert("RGBA")` plus a float32 array happens before `_resize_max_edge`. A file under Pillow's pixel cap and under or just over 12 MB still allocates the full raster first. Nginx's 10 MB cap applies only when the optional nginx profile is in front. The image command serves Uvicorn directly.

## GPU Lab

**Conform.** `/gpu/` is a separate mount, present only when `dist/index.html` exists, and can be turned off with `PSYFI_SERVE_GPU=0`. The lab reads launch parameters from the query (`packages/psyfi-gpu-renderer/src/bridge/launchParams.ts`). The present path in `PresentPipeline.tsx` chains GTAO, SSR, bloom, depth of field, motion blur, chroma, temporal accumulate, grade, a peak scale at 0.96, and the safety uniform. `SafetyPassNote` renders nothing. Neutral collapse and fixture-asset opt-in have tests. Unknown packs leave procedural assets (`tests/test_asset_packs.py`). The Dockerfile's first stage runs `npm run gpu:build` and copies `dist/`.

**Diverge.** `docs/FRONTEND_BOUNDARY.md` still says the Ultra post stack is scaffolded and out of scope for G0. The running path is the TypeScript post graph. The WGSL files for bloom, SSAO, SSR, and the material shaders are stubs that return black (`shaders/wgsl/post/bloom.wgsl` and its neighbors). `safety_clamp.wgsl` is a real sketch and is not what `PresentPipeline` executes. The spec says the WGSL tree is not the present path. The boundary doc disagrees with both the spec and the code.

**Unproven.** "Desktop discrete Ultra path done" on the readiness board, including named NVIDIA, AMD, and Intel classes. `docs/SIMULATED_ULTRA_QA.md` is a synthetic matrix. Hardware measurement is optional. No GPU runner result is in this commit.

**Unproven.** Full R3F still hashes. The spec marks them optional. The board must not be read as if those stills were locked.

## Shell and PWA

**Conform.** `GET /sw.js` sets `Service-Worker-Allowed: /` and the worker cache is `psyfi-shell-v41` (`psyfi_api/main.py`, `psyfi_api/static/sw.js`). API, simulate, health, docs, and OpenAPI skip the cache. `/gpu/` is network-first and is not precached as shell HTML. Offline GPU navigation falls back to `/`. `tests/test_jobs_and_cancel.py` asserts the scope header and cache name. Ready checks icons, renderer, catalog, and overlays.

**Unproven.** The filled device matrix and Phase 4 pass marks. `tests/test_production_readiness.py` asserts that the markdown contains device names and the words "filled" and "✅ pass". That is a document test, not a device run.

## MIDI

**Conform.** One global service. A second start returns 409. Missing libraries return 503 on start and an empty device list. Send requires a running service and an output port. Bounds exist on the request models. Tests substitute a fake port (`tests/test_midi_routes.py`). The service does not start with the process.

**Diverge.** `docs/MIDI.md` says to install `mido` and `python-rtmidi` as extras. `pyproject.toml` puts both in the default dependencies. The spec records the default install. The guide is wrong.

**Diverge.** Stories assume one operator per process. The image and `.env.example` bind `0.0.0.0`, and Compose publishes `8000:8000`. Any client that can open that port can list ports, start the service, and send CC or notes. There is no check in `psyfi_api/routers/midi.py`. Exception text from a failed open is returned to the client.

## Telemetry

**Conform.** Default flag is off. Opt-in while the flag is off does not activate collection (`tests/test_jobs_and_cancel.py`). Opt-out clears the buffer. Sensitive keys are dropped in `psyfi_api/telemetry.py`. Events stay in a deque capped from `PSYFI_TELEMETRY_MAX_EVENTS` (default 200). No sink is coded. Legacy and v1 routes share the router.

**Diverge.** "Client opt-in" is one boolean on the process, not on the caller. `GET /api/v1/telemetry/events` returns that buffer to any caller. With the flag off the buffer stays empty, so this is latent. It still contradicts a per-client reading of the policy.

## Deploy and CI

**Conform.** The image is multi-stage, creates uid 1000, and healthchecks with `urllib`. The command is a single Uvicorn process on `0.0.0.0:8000`. The NVIDIA and nginx services are behind Compose profiles. Python simulation does not import a CUDA runtime.

**Diverge.** `.github/workflows/ci.yml` checks out the repo, sets up Python, and stops. It does not install project dependencies, and it does not run pytest, Hallmark, or the GPU scripts. The last `main` run of that workflow finished in about 13 seconds. `docs/PRODUCTION_READINESS.md` marks "pytest + hallmark + gpu test/typecheck/build" done and points at that file. `package.json` does define `test`, `gpu:test`, `gpu:typecheck`, and `gpu:build`. CI never calls them.

**Diverge.** `tests/test_production_readiness.py` is the suite that guards the ship board. It reads markdown and asserts substrings (`RTX 5060`, `G3 premium desktop stack`, `✅ pass`, `hard_frozen`). It never reads `ci.yml`. A green run of this file can coexist with a CI workflow that runs nothing.

**Diverge.** The README CI badge and `package.json` `repository.url` point at `scrimshawlife-ctrl/Psy-Fi`, which is archived. The live repo is `Zero-State-LLC/Psy-Fi`.

**Diverge.** `LICENSE` is the Zero State Proprietary License. `pyproject.toml` says `MIT`. The README badge says MIT.

**Diverge.** `.github/workflows/deploy-worker-pin-pr.yml` is a manual production deploy for Noema (`https://noema.guru`). It requests Cloudflare, Supabase, Resend, and pin-PR tokens. This repo has no `workers/noema` and no `spec-compat.json`, so a dispatch fails before deploy. The workflow is still in the default branch.

**Diverge.** Compose sets `ENVIRONMENT=production` and bind-mounts `psyfi_api`, `psyfi_core`, and `docs` read-write over the image. It also sets `WORKERS=4`, which the process command ignores. The `psyfi` and `psyfi-nvidia` services both publish host port 8000. Nginx listens on 443 and the Compose file publishes 443, with no TLS certificate configuration in `nginx.conf`. The content security policy allows `'unsafe-inline'` plus any `http:` and `https:` URL.

**Unproven.** `docker compose up` was not run here. Image build success, `/gpu/` inside the container, and the healthcheck are source-level only.

CodeQL on the repo has two open alerts. Alert 2 is missing workflow permissions on `ci.yml`, which matches story 10. Alert 1 is `js/xss-through-dom` on the image-seed preview `src` assignment. That assignment prefixes `data:image/png;base64,`. The innerHTML planner sink above is the one that matches the Live Experience decision.

## Cloudflare and NVIDIA

On `7ca678e` these rows diverge. The image-reading branch adds `wrangler.jsonc`, `workers/psyfi`, and the reading route. It still does not deploy, and it does not remove the Noema workflow.

**Diverge.** `main` has no `wrangler.toml`, no `cloudflare.config.ts`, and no Worker. The only runnable host in the tree is Docker Compose. The Pages workflow uploads a `site/` directory this repo does not have.

**Diverge.** Nothing calls `https://integrate.api.nvidia.com` or an AI Gateway custom provider. No `NVIDIA_API_KEY` or `NVIDIA_VISION_MODEL` is read. Image-seed features in `psyfi_core/visualization/image_seed.py` are photometric (`analyze_features`: mean color, energy, contrast, edge density, warmth, size). There is no image-reading route and no vision response field.

**Conform.** `planner_text` and `build_t2v_prompt` are deterministic templates. `psyfi_core/visualization/export_journey.py` sets the sidecar `status` to `prompt_only` and states that PsyFi does not invoke a provider. MIDI, telemetry, the field solver, and the GPU present path do not call a model. That matches the decision that no second model class is required.

**Diverge.** `.github/workflows/deploy-worker-pin-pr.yml` is a Noema dispatch, recorded under Deploy and CI. It is not a Psy-Fi Worker and it is not an NVIDIA call.

**Unproven.** The operator's NVIDIA catalog was not queried from this audit, so no vision model id is pinned here. The spec requires the id to be chosen from that catalog at deploy and to be an `nvidia/` vision-language model.

## What this pass did not do

- Did not run `python3 -m pytest` or `npm run gpu:test`.
- Did not build the image or open the shell in a browser.
- Published the agent-ready gaps as GitHub issues #16–#23, labeled `ready-for-agent`. Shell and telemetry were left unlabeled because the code matches those decisions. Catalog reload (name it, or drop it) is still an open choice and has no issue.

## If the next change is a fix

The smallest fixes that would move a diverge to conform, without rewriting the instrument:

1. Make `ci.yml` install dependencies and run `python3 -m pytest tests/ -q`, `npm test`, `npm run gpu:test`, `npm run gpu:typecheck`, and `npm run gpu:build`.
2. Point the badge and `package.json` repository at `Zero-State-LLC/Psy-Fi`. Make `pyproject.toml` license text match `LICENSE`.
3. Delete or disable `deploy-worker-pin-pr.yml` in this repo.
4. Stop bind-mounting source in the default Compose service. Drop the unused `WORKERS` value or teach the process to honor a single worker on purpose.
5. Cap the image-seed read before decode, and reject dimensions before the float32 allocation.
6. Give synchronous simulate the same slot limit as jobs, or document a separate limit and enforce it.
7. Render planner and archive strings as text.
8. Either read `ALLOWED_ORIGINS` and drop credentialed wildcard CORS, or delete the unused security keys from `.env.example` so the file matches the "one operator per process" decision.
