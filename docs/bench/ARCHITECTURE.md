# FieldLoop benchmark: architecture specification

Date: 2026-11-07
Status: implemented on branch `bench/fieldloop-foundation`; open tasks listed at the end.
Package: `psyfi_bench/` (bench version `0.1.0`, name `FieldLoop`).
Related: [DISCOVERY.md](DISCOVERY.md), [RESEARCH.md](RESEARCH.md), [METHODOLOGY.md](METHODOLOGY.md), [adr/](adr/).

This document describes the subsystem as it is in the code. Anything not yet built is marked "not implemented".

## 1. System architecture

```text
                       psyfi_core (simulation authority)
          ABXRuntime · engines · psyfi_core.simulation.simulate_field / run_simulation
          parameter_mapper.map_parameters · scene_snapshot.build_scene_snapshot
                                   │ typed Python calls (bench never imports psyfi_api)
                                   ▼
  psyfi_bench
  ├─ registry.py        manifests on disk (psyfi_bench/workloads/*.json) + family runner registry
  ├─ runner.py          RunContext · measure_stage · run_workload → sealed BenchResult
  ├─ families/
  │    field_compute.py   A: Kuramoto pipeline, scaling, sustained, presets, accelerator validation
  │    render.py          B: soft raster (CPU) · webgpu capture scoring
  │    interpretation.py  C: image_read / structured_read / perturbation / repeatability, FDE
  │    fieldloop.py       D: simulate → snapshot → render → interpret → reconstruct
  ├─ compute/backends.py  NumpyBackend (canonical) · TorchBackend (optional, validated)
  ├─ render/              soft_raster.py (port of softPresent.ts) · fidelity.py · adapter.py
  ├─ providers/           base · baselines · replay · http (OpenAI-compatible, Anthropic) · registry
  ├─ stats.py · determinism.py · timing.py · environment.py
  ├─ scoring.py · report.py · contracts.py
  ├─ store.py            bench_results/<family>/<run_id>.json + index.json
  ├─ api.py              FastAPI sub-app `bench_app`
  └─ cli.py              `psyfi-bench` (entry point in pyproject)

  psyfi_api/main.py:  app.mount("/api/bench", bench_app)      ← own OpenAPI, /api/v1 frozen doc untouched

  Browser: /gpu/bench.html (packages/psyfi-gpu-renderer/src/bench/)
     BenchApp.tsx ── POST /api/v1/visualize/scene-snapshot (existing frozen route)
                 ── GET  /api/bench/v1/workloads/render.webgpu.tiers
                 ── reuses PsyFiGPUCanvas + SceneRoot unchanged; BenchProbe inside the canvas
                 ── downloads or POSTs psyfi.bench.gpu_capture.v1 → /api/bench/v1/captures (env gated)

  Providers: local (OpenAI-compatible on localhost) · remote (NVIDIA integrate, Anthropic, any
             OpenAI-compatible host) · baseline (oracle, constant, random, heuristic) · replay (receipt)
```

## 2. Domain model

All contracts are Pydantic v2 models in `psyfi_bench/schemas.py`. Every document carries a `schema` id. JSON Schema exports live in `docs/schemas/bench/` and are produced by `export_json_schemas()`.

| Model | Schema id | Role |
| --- | --- | --- |
| `WorkloadManifest` | `psyfi.bench.manifest.v1` | Versioned workload: `id`, `version`, `family`, `execution`, `params`, `protocol`, `references`, `tolerances`, `requires`, `tags`. `manifest_hash` is `stable_hash` over id, version, family, execution, params, protocol, references, tolerances. Title and description are not hashed. |
| `Protocol` | part of manifest | `warmup_runs`, `repeats`, `cold_start`, `timeout_s`, `min_duration_s`, `memory_probe`, `bootstrap_resamples`, `bootstrap_seed`. |
| `Tolerances` | part of manifest | `timing_cv_max`, `quantization`, `accelerator_atol`, `accelerator_rtol`. Extra keys allowed. |
| `EnvironmentRecord` | embedded in result | `captured_at`, `hostname_hash` (12 hex chars of SHA-256, never the hostname), `platform`, `cpu`, `memory`, `gpus: list[GpuRecord]`, `software` (python, numpy, scipy, psyfi_version, bench_version, blas, accelerators, git_commit, git_dirty), optional `browser`, optional `power`, `hardware_class` (`discrete`, `integrated`, `cpu_only`, `remote`, `unknown`), `unavailable: dict[str, str]`. |
| `GpuRecord` | embedded | `vendor`, `name`, `memory_bytes`, `driver`, `cores`, `source` (nvidia-smi, rocm-smi, system_profiler, torch, webgpu, manual), `hardware_class`. |
| `StageRecord` | embedded | `id`, `kind`, `status`, `measurement_class`, `params`, `wall_ms[]`, `cpu_ms[]`, `cold_wall_ms`, `warmup_wall_ms[]`, `memory`, `metrics`, `statistics: dict[str, Statistics]`, `determinism`, `error`. |
| `Statistics` | embedded | `n`, `unit`, `mean`, `median`, `min`, `max`, `std`, `cv`, `mad`, `p50`, `p90`, `p95`, `p99`, `ci95_mean`, `ci95_median`, `bootstrap` (method, resamples, seed, level). |
| `MemoryRecord` | embedded | `rss_before_bytes`, `rss_peak_delta_bytes`, `tracemalloc_peak_bytes`, `tracemalloc_current_bytes`, `note`. |
| `DeterminismRecord` | embedded | `exact_sha256`, `quantized_sha256`, `quantization`, `bitwise_identical_across_repeats`, `quantized_identical_across_repeats`, `reference_match` (digest equality, None when no lock), `reference_within_tolerance`, `reference_max_abs_error`, `nan_count`, `inf_count`. |
| `FailureRecord` | embedded | `stage`, `category`, `detail`. |
| `Provenance` | embedded | `git_commit`, `git_dirty`, `command`, `bench_version`, `psyfi_version`, `seed`, `notes[]`. |
| `BenchResult` | `psyfi.bench.result.v1` | `run_id`, `created_at`, `manifest` (full document of the effective manifest), `manifest_hash`, `measurement_class`, `status`, `environment`, `stages[]`, `metrics` (headline), `determinism`, `failures[]`, `provenance`, `non_claim`, `result_hash`. `seal()` sets `result_hash` to the 64-char SHA-256 of the canonical JSON excluding itself; `verify()` recomputes it. |
| `GpuCapture` / `CaptureStage` | `psyfi.bench.gpu_capture.v1` | Browser payload: `captured_at`, `manifest_id`, `manifest_hash`, `measurement_class`, `browser` (user_agent, adapter, dpr, viewport, features), `stages[]`, `aborted`, `note`. A stage carries `tier`, `snapshot_key`, `requested_frames`, `warmup_frames`, `frames_ms[]`, optional `gpu_ms[]`, `draw_calls`, `triangles`, `duration_ms`, `js_heap_bytes`, `thumbnail_png_base64` (128 px), `snapshot_hash`, `note`. |
| `Scorecard` / `ScoreDimension` | `psyfi.bench.scorecard.v1` | `family`, `manifest_id`, `manifest_hash` (or `mixed`), `subjects[]`, `dimensions: name → label → ScoreDimension(value, unit, better, ci95, source, missing_reason)`, `composites: label → name → spec`, `validity`, `recommendations[]`, `non_claim`. |
| `Capabilities` | `psyfi.bench.capabilities.v1` | `families`, `workloads`, `providers`, `accelerators`, `environment`, `ingest_enabled`, `run_enabled` (always false), `non_claim`. |

Other ids used by the code: `psyfi.bench.index.v1` (store index), `psyfi.bench.workloads.v1`, `psyfi.bench.schema_index.v1`, `psyfi.bench.ingest_receipt.v1`, `psyfi.bench.error.v1`, `psyfi.bench.provider_receipt.v1` (replay receipts).

### Measurement classes

| Class | Meaning | Who sets it |
| --- | --- | --- |
| `measured` | A real process, device or live model answered. | `field_compute` and `render.soft` always; `interpretation` and `fieldloop` when the provider locality is `local` or `remote`; `render.webgpu` copies the capture's own class. |
| `synthetic` | Deterministic stand-in, not evidence about hardware or a model. | Baseline providers (oracle, constant, random, heuristic); a capture that declares itself synthetic. |
| `replay` | Recorded answers replayed offline. | `ReplayProvider`. |

The result status, the scorecard validity gate, the index entry and the markdown report all show the class. A scorecard that mixes classes is marked not comparable.

## 3. Requirements

Functional:

- Run every family headlessly from the CLI without the frontend or a browser, except the `webgpu` execution class, which consumes a capture file.
- Produce self-describing, sealed results with embedded manifest, environment and provenance.
- Lock deterministic references in manifests and detect drift (`reference_match`).
- Compare results only when the manifest hash matches; record param overrides in the effective manifest so the hash changes.
- Score model readings against deterministic references (FDE) with baselines.
- Score browser captures in Python; the browser only collects.
- Expose a read surface for a frontend: capabilities, workloads, results, schemas.

Non-functional:

- CPU-only development path. `numpy` and `scipy` are the only compute dependencies; `torch` is optional and never required.
- `psyfi_bench` never imports `psyfi_api`. The dependency direction is `psyfi_api` → `psyfi_bench` → `psyfi_core`.
- Provider keys are read from the environment at call time, never stored. One POST per request, no retry, no second model.
- Ingest is bounded: 8 MB body, 20,000 frames, env-gated by `PSYFI_BENCH_INGEST=1`.
- Execution is CLI-only. The API has no run endpoint; `run_enabled` is false in capabilities.
- The frozen `/api/v1` OpenAPI document is byte-identical. The bench API is a mounted sub-application with its own document.
- No frontend component, stylesheet, template or route of the product shell is changed.

## 4. User and operator journeys

| Journey | Steps |
| --- | --- |
| Run a CPU workload | `psyfi-bench list` → `psyfi-bench run field-compute.scaling` → result saved under `bench_results/field_compute/`, markdown printed, exit 0. |
| Lock references | After an intentional change to the mapper or raster: `psyfi-bench lock field-compute.scaling --write` (or `render.soft.g4`, `interpretation.fieldread`). Tests assert the locks still hold. |
| Run a model provider and keep a replay | `psyfi-bench run interpretation.fieldread --provider openai:http://localhost:8080#qwen2.5-vl --record receipt.json`; later `psyfi-bench run interpretation.fieldread --provider replay:receipt.json` scores offline as class `replay`. |
| Run baselines | `--provider oracle`, `constant:void:0.3`, `random:7`, `heuristic`. Results are `synthetic`. |
| Browser GPU bench | Build the GPU package, start the API, open `/gpu/bench.html`, press Run, download the capture, then `psyfi-bench ingest capture.json`. With `PSYFI_BENCH_INGEST=1` the page can POST instead. |
| Build a scorecard | `psyfi-bench score a.json b.json --labels a,b --out card.json` → dimensions, composites, validity, recommendations. |
| Frontend reads results | `GET /api/bench/v1/capabilities`, `/v1/workloads`, `/v1/results`, `/v1/results/{run_id}`, `/v1/schemas/{name}`. |
| Verify a result file | `psyfi-bench validate result.json` recomputes the seal; exit 1 on tampering. |

## 5. Execution workflows and state transitions

`run_workload(manifest, ctx)`:

1. Collect `EnvironmentRecord` (or use `ctx.environment`).
2. Build the effective manifest: `ctx.inputs` minus the reserved keys `capture` and `_receipt` override `params`; a note records the override.
3. Dispatch to the registered family runner (`registry.get_family_runner`, which imports the four family modules).
4. Collect `FamilyOutput` (stages, metrics, determinism, failures, measurement class, notes), derive failures from non-ok stages, compute the result status, seal, and save when `ctx.store` is set.

`measure_stage(fn, protocol, ...)` for one stage (field_compute and render.soft):

1. Warm-up: `max(warmup_runs, 1 if cold_start else 0)` runs; the first is `cold_wall_ms`.
2. Repeats: `time_call` around `fn(should_cancel)`; wall and CPU ns; digest of the result per repeat.
3. Sustained: when `min_duration_s` is set, repeat until both the duration and `repeats` are reached.
4. Memory probe: one extra run under `tracemalloc` when `memory_probe` is true; its timing is excluded.
5. Statistics for `wall_ms` and `cpu_ms`; determinism aggregate across repeats; `metrics_fn` on the last result.

Cancellation: `timing.Deadline(timeout_s, external_cancel)` exposes `should_cancel()`, which is passed into `simulate_field` and `evolve_consciousness_omega` (the ABX callback contract) and checked between repeats. `deadline.check()` raises `TimeoutError` or `InterruptedError`.

Stage status: `ok`, `failed`, `skipped` (missing capability, for example torch absent or no capture), `timeout`, `cancelled`.

Result status: `complete` (every stage ok, no failures), `partial` (some non-ok or failures), `failed` (no ok stage).

Failure categories (`FailureRecord.category`): `timeout`, `cancelled`, `provider`, `parse`, `validation`, `resource`, `unsupported`, `internal`. `runner.classify_exception` maps exceptions; `failures_from_stages` maps stage statuses and error text.

Family-specific flow:

- `interpretation`: builds the corpus with `build_items` (stratified by mode when `--limit` is set), renders it with the soft raster, checks the corpus lock, runs the tasks in order `image_read`, `structured_read`, `perturbation`, `repeatability`; aborts after `abort_after_consecutive_errors` (default 3) provider errors for local or remote providers; writes a replay receipt to `ctx.inputs["_receipt"]` when `provider_options["record"]` is set.
- `fieldloop`: per case, warm-up then `repeats` loops of `run_loop_once`; each loop times `simulate`, `snapshot`, `render`, `interpret`, `reconstruct` and `end_to_end`.
- `render.webgpu`: `load_capture` → manifest id must match (else `validation` failure) → `score_capture` builds one stage per capture stage, fidelity against the same device's Ultra thumbnail, per-tier roll-up, adapter classification into `environment.browser`.

## 6. Interfaces and contracts

### CLI (`psyfi-bench`, also `python -m psyfi_bench`)

| Subcommand | Purpose | Exit code |
| --- | --- | --- |
| `list [--family] [--json]` | List manifests | 0 |
| `show <manifest>` | Print one manifest document | 0 |
| `run <manifest> [--provider] [--backend] [--repeats] [--warmup] [--timeout] [--min-duration] [--seed] [--limit] [--param k=json] [--capture f] [--record f] [--pricing] [--out dir] [--no-store] [--json] [--quiet]` | Execute | 0 complete, 2 partial, 1 failed |
| `lock <manifest> [--write]` | Recompute `references` | 0 |
| `ingest <capture.json> [--manifest]` | Score a browser capture (shorthand for `run render.webgpu.tiers --capture`) | as `run` |
| `validate <result.json>` | Recompute the seal | 0 valid, 1 tampered |
| `score <result.json>... [--labels] [--out] [--json]` | Scorecard | 0 |
| `report <result.json>` | Markdown report | 0 |
| `results [--family] [--out]` | List the store index | 0 |
| `capabilities` | Capabilities document | 0 |
| `env` | Environment record | 0 |
| `export-schemas [--out]` | JSON schemas and bench OpenAPI | 0 |

### Bench API (mounted at `/api/bench`, OpenAPI at `/api/bench/openapi.json`, docs at `/api/bench/docs`)

| Method and path | Returns |
| --- | --- |
| `GET /v1/capabilities` | `psyfi.bench.capabilities.v1` |
| `GET /v1/workloads?family=` | `psyfi.bench.workloads.v1` |
| `GET /v1/workloads/{workload_id}` | manifest document or 404 |
| `GET /v1/results?family=&manifest_id=&limit=` | `psyfi.bench.index.v1` entries |
| `GET /v1/results/{run_id}` | `psyfi.bench.result.v1` or 404 |
| `GET /v1/schemas` | `psyfi.bench.schema_index.v1` |
| `GET /v1/schemas/{name}` | JSON Schema or 404 |
| `POST /v1/captures` | 201 `psyfi.bench.ingest_receipt.v1`; 403 unless `PSYFI_BENCH_INGEST=1`; 413 over 8 MB or 20,000 frames; 422 invalid body; 409 unknown or non-render manifest |

Error contract: `{"schema": "psyfi.bench.error.v1", "error": {"code", "message", "status"}}` with codes `not_found`, `ingest_disabled`, `payload_too_large`, `invalid_capture`, `manifest_mismatch`, `error`.

### Browser runner

`/gpu/bench.html` (source `packages/psyfi-gpu-renderer/src/bench/`). `schedule.ts` is pure (stage expansion, warm-up trimming, payload assembly, quick summary) and unit-tested. `BenchApp.tsx` fetches the manifest from `/api/bench/v1/workloads/render.webgpu.tiers` (falls back to an inline copy), fetches a scene snapshot per stage from `/api/v1/visualize/scene-snapshot`, renders through the unchanged `PsyFiGPUCanvas`, and collects frames with `BenchProbe.tsx` (frame spacing, `renderer.info`, GPU timestamps when `trackTimestamp` and `resolveTimestampsAsync` work, a 128 px thumbnail via a 2D canvas `drawImage` in a microtask). The payload is `psyfi.bench.gpu_capture.v1`, class `measured`, downloadable or posted.

### Provider spec grammar

`oracle` | `constant[:mode:intensity]` | `random[:seed]` | `heuristic` | `replay:<receipt.json>` | `nvidia[:<nvidia/model-id>]` | `anthropic:<model-id>` | `openai:<base_url>#<model>`.

`nvidia` requires an `nvidia/` id (from the argument or `NVIDIA_VISION_MODEL`), rejects `@cf/` ids, reads `NVIDIA_API_KEY` and `NVIDIA_API_BASE`, and sends `reasoning_effort: none`. `anthropic` reads `ANTHROPIC_API_KEY` and needs a model id (argument or `ANTHROPIC_MODEL`); no default model is pinned. `openai` on a localhost base needs no key and is classed `local`.

## 7. Data model and storage

- Results: `bench_results/<family>/<run_id>.json` plus `bench_results/index.json` (`psyfi.bench.index.v1`). Writes are atomic (temp file then `replace`). `PSYFI_BENCH_RESULTS` overrides the root. The directory is gitignored.
- Manifests: `psyfi_bench/workloads/*.json`, loaded by `registry.load_manifest` (by id, `id@version`, or path). The on-disk `manifest_hash` is informational and recomputed.
- Locks in `references`: `field_compute` stores `quantized_sha256` per stage id at `tolerances.quantization = 1e-4` (not for `sustained` and `accelerator`); `render.soft.g4` stores `sha256` per raster stage; `interpretation.*` stores `corpus_sha256` over item keys and image digests. `lock_references` in each family module recomputes them.
- Shipped manifests: `field-compute.scaling`, `field-compute.steps`, `field-compute.sustained`, `field-compute.presets`, `field-compute.accelerator`, `render.soft.g4`, `render.webgpu.tiers`, `interpretation.fieldread`, `interpretation.fieldread.smoke`, `fieldloop.signature`.
- Replay receipts (`psyfi.bench.provider_receipt.v1`) hold request keys, text, latency, usage and error per call. No key, no image.

## 8. Security and privacy

- The hostname is hashed; the record never stores it.
- No key is read from the repo, written to a result, a receipt or stdout. Provider error text passes through `redact` (key replaced, newlines removed, 300 chars).
- Model output is untrusted: `parse_strict` accepts only a JSON object with one of four mode strings and a finite number in [0, 1]. Lenient recovery is reported as a count, never silently promoted.
- The public host cannot run compute through the API. Ingest is off unless the environment says otherwise, and bounded.
- Thumbnails (128 px PNG) are the only image payload in a capture. Interpretation results store image digests and the first 200 characters of model text, not images.
- The vision bench, the caption route, `/api/v1`, the service worker and the shell are untouched.

## 9. Migration and compatibility

- `run_simulation` and `PresetNotFoundError` moved to `psyfi_core.simulation`; `psyfi_api.simulation_service` re-exports both. The routers and tests import unchanged names. A parity check confirmed identical payloads (metrics, visualization values, session parameters, provenance) for presets None, lsd, dmt and ketamine.
- New: `psyfi_core.simulation.simulate_field`, `initial_field`, `SimulationSettings`, `resolve_preset_settings`.
- `psyfi_api/main.py` gains one mount: `app.mount("/api/bench", bench_app)`. The `/api/v1` OpenAPI path set and body are unchanged; the frozen-contract tests pass without a resync.
- `packages/psyfi-gpu-renderer/vite.config.ts` gains a second rollup input (`bench.html`). No existing component, style or test changed. `npm run gpu:build` emits `dist/bench.html`.
- `pyproject.toml` gains the `psyfi-bench` script, the `psyfi_bench*` package and its data files.
- `.gitignore` gains `/bench_results/` and `/.claude/launch.json`.
- HANDOFF.md (PR #42) reserved "a GPU frame-time bench", hardware detection and frame-time recording for a later accepted intent; this mission, delegated by Aaron, authorizes them. Every other HANDOFF hard stop is kept. Issue #10 and the Ultra fps fixtures are untouched.

## 10. Acceptance tests

| Requirement | Test |
| --- | --- |
| Contracts, stable hash, statistics, digests, store round trip, schema export | `tests/bench/test_bench_core.py` |
| Family A runs, locks hold, timeouts classified, unknown preset is validation, accelerator validation, skipped backend | `tests/bench/test_field_compute.py` |
| Soft raster bit-identical to TS goldens, fidelity metrics, render locks, capture scoring, adapter classification, mismatch handling | `tests/bench/test_render_family.py` |
| Baselines, replay round trip, OpenAI-compatible and Anthropic request shape, redaction, local endpoints without key, NVIDIA namespace | `tests/bench/test_providers.py` |
| Corpus lock, parsers, FDE and ruler, discriminability, aggregation, baselines on the smoke corpus, abort policy, receipt, strict scoring, prompts distinct, FieldLoop closes and times stages, FieldLoop timeout | `tests/bench/test_interpretation_and_loop.py` |
| Bench API mounted with `/api/v1` paths untouched, error contract, gated and bounded ingest, scorecards and validity, composites, CLI round trip and exit codes | `tests/bench/test_api_cli_scoring.py` |
| Exported schemas, bench OpenAPI and examples match the live code | `tests/bench/test_bench_contracts.py` |
| Browser schedule, warm-up trimming, payload shape and clamp notes | `packages/psyfi-gpu-renderer/src/bench/schedule.test.ts` |
| Repository suite still green (frozen contracts, routers, vision bench) | `python -m pytest -q`, `npm run gpu:test`, `npm run gpu:typecheck`, `npm run gpu:build` |

## 11. Implementation tasks still open

Hardware-dependent:

- Captures from discrete GPUs (NVIDIA, AMD, Intel Arc, Apple Pro/Max) through `/gpu/bench.html`; this machine is integrated-class.
- Torch backend validation on CUDA and MPS; the port exists and is validated against NumPy, but torch is not installed here.
- A WGSL Kuramoto compute port in the browser validated against a Python reference field (not implemented).
- Power and temperature: when `nvidia-smi` exists, `field_compute` stages carry `StageRecord.power` (`psyfi_bench/power.py`): one `nvidia-smi -lms 100` process per stage reading `power.draw.instant` where the driver has it (else `power.draw`, which is a 1 s average on Ampere and newer; arXiv:2312.02741), stamped with nvidia-smi's own timestamps; only readings inside the measured window count, energy is the trapezoid integral of those with a power reading (no extrapolation), and `energy_j_per_work_unit` per cell-step is reported only for a stage of at least 1 s whose readings span at least 90% of it, mean and max watts, and max GPU temperature. With no tool, no power field is written and `environment.unavailable.power` stays. Energy per frame for webgpu captures is not wired: a capture is taken in a browser outside this process, so there is no sample window to integrate. [ADR 0011](adr/0011-host-power-trace-for-browser-captures.md) proposes a host power trace aligned to each stage's window (not accepted yet).

Provider-dependent:

- Live VLM runs with a key (NVIDIA integrate, Anthropic, local vLLM or llama.cpp) and committed replay receipts.
- Pricing tables per provider for `cost_per_valid_result`.

Frontend integration (Daniel):

- A results view over `/api/bench/v1/results`, a capabilities panel, and a link to `/gpu/bench.html`. Contracts are in `docs/contracts/bench/`.

Governance:

- A run endpoint, if ever wanted, only behind an accepted intent; `run_enabled` stays false.
