# FieldLoop Phase 1: Discovery and gap analysis

Date: 2026-11-07
Repo: `Zero-State-LLC/Psy-Fi`, `main` at `7372d31` (merge of pull request #44)
Author: Fable, benchmark architecture owner
Scope: what the repository already does, what it only claims, and what a benchmark platform can reuse

This document is evidence for the benchmark design in [`RESEARCH.md`](RESEARCH.md). It records what was read, not what was wished. A claim labeled "verified" means the source file was read and the behavior follows from the code. A claim labeled "unverified" means a document says it and no test or code run in this pass proves it. No hardware was measured for this document.

## 1. Architecture map

```text
Browser
  /            legacy PWA shell: psyfi_api/templates/index.html, static/app.js,
               static/viz/* (Canvas + WebGL ParameterField engines, safetyPass.js)
  /gpu/        optional R3F + three.js WebGPURenderer build:
               packages/psyfi-gpu-renderer (App.tsx, SceneRoot, PresentPipeline,
               FrameProfiler, DebugHud, qa/measureUltraFps, goldens/softPresent)
        |  HTTPS JSON, /api/v1 hard-frozen (psyfi-api-v1-hard-2026-07-25)
FastAPI  psyfi_api/main.py
  routers/simulate.py, jobs.py, presets.py, experiences.py, midi.py, telemetry.py
  simulation_service.run_simulation      (sync and job paths share 4 slots)
  image_reading.read_image               (one POST to the NVIDIA integrate host)
        |  typed Python calls
psyfi_core
  abx_core/        ABXRuntime (seeded numpy Generator), ABXMetrics, ProvenanceRecord
  engines/         consciousness_omega (Kuramoto), normalization_nu, valence_kappa, ...
  experiences/     parameter_mapper.map_parameters -> immutable ParameterField (hash)
  visualization/   scene_snapshot.build_scene_snapshot, magnitude, image_seed,
                   planner, journey, vision_bench (Daniel, PR #40)
Public host
  Cloudflare Worker `psy-fi` (workers/psyfi/src/route.mjs): /api/*, /simulate/*,
  /health, /ready, /docs, /openapi.json reach the Python container;
  everything else is a static asset.
```

Invariants that every file above repeats: simulation truth stays in Python; the immutable `ParameterField` (then the scene snapshot) is the visual authority; a safety pass runs on every presented frame; `/api/v1` is additive-only under the current freeze id.

The Worker routes every `/api/` path to the container (`workers/psyfi/src/route.mjs`). A bench API under `/api/bench` is therefore reachable from the public hostname. That is why the bench API is read-only and its capture ingest is gated by an environment flag.

## 2. Capability inventory

Classification key: **Implemented and verified** (code read, behavior follows, tests exist and the suite passed in this session), **Implemented but unverified** (code exists, no test or no run proves the claim), **Partially implemented**, **Scaffolded**, **Proposed**, **Obsolete**.

| Capability | Where | Classification | Evidence and notes |
| --- | --- | --- | --- |
| ABX deterministic runtime | `psyfi_core/abx_core/runtime.py`, `metrics.py`, `provenance.py` | Implemented and verified | Seeded `np.random.default_rng`; default seed 1337; `ABXMetrics` counts steps, grid size, entropy proxy. No timing or memory fields. `tests/test_engines_determinism.py` passes. |
| Kuramoto field evolution | `psyfi_core/engines/consciousness_omega.py` | Implemented and verified | Pure numpy: four `np.roll` neighbours, `np.sin` coupling, `dt` 0.1, cancel callback per step, complex64 output. Determinism test exists. The engine does not use the runtime RNG; its own test file says so. |
| Other engines (normalization, valence, resonance, gestalt, retina, psychedelic, meditative) | `psyfi_core/engines/*.py` | Implemented but unverified for performance | Pure functions over numpy and scipy (`uniform_filter`, `gaussian_filter`, `RegularGridInterpolator`, morphology). Determinism is structural. No timing anywhere. |
| Simulation service and slots | `psyfi_api/simulation_service.py`, `psyfi_api/jobs.py` | Implemented and verified | `run_simulation` seeds, evolves, normalizes, scores valence, builds a `PsyFiSession` and a 64x64 magnitude visualization. Four shared slots, 64 retained jobs. `tests/test_simulation_slots.py`, `tests/test_jobs_and_cancel.py` pass. |
| ParameterField mapper | `psyfi_core/experiences/parameter_mapper.py` | Implemented and verified | `map_parameters` is deterministic: substance defaults, overlay, mode biases, phase envelope, intensity scaling, safety clamps, 16-hex `_stable_hash`. Overlay goldens and G4 goldens pass. |
| Scene snapshot | `psyfi_core/visualization/scene_snapshot.py` | Implemented and verified | Deterministic procedural descriptors from `master_seed` and field hash; tier post table; Neutral collapses post. `published_at` and `snapshot_id` are non-deterministic by design. `tests/test_scene_snapshot.py`, `tests/test_g4_scene_goldens.py` pass. |
| Soft-present pixel goldens | `packages/psyfi-gpu-renderer/src/goldens/softPresent.ts`, `pixelGolden.test.ts` | Implemented and verified | Deterministic 64x64 CPU raster; SHA-256 plus 16-bin histogram locked for three G4 seeds. Not a WebGPU still. `npm run gpu:test` passed (101 tests). |
| R3F still capture | `src/goldens/r3fStillCapture.ts`, `webgpuCapture.ts` | Scaffolded | `capturePixelFrame` returns soft by default; the WebGPU path is a palette clear and readback smoke, documented as "NOT a scene golden". Full stills are deferred to a GPU CI runner that does not exist. |
| FrameProfiler and DebugHud | `src/Profiling/FrameProfiler.ts`, `src/DebugOverlay/DebugHud.tsx`, `src/App.tsx` | Partially implemented | Keeps 120 samples, avg, p95, max, fps from the average. The `cpuMs` pushed by `App.tsx` is `Math.max(cpuMs, dt * 1000)`, which is wall-clock rAF spacing, not CPU time. `snapshotLagMs` is always 0. `drawCalls` is the enabled pass count, not a draw count. |
| Ultra fps capture | `src/qa/measureUltraFps.ts`, `App.tsx` `measure_fps` | Implemented but unverified on hardware | 60 warm-up plus 180 sample frames of rAF spacing; avg fps, 1% low from instantaneous fps, p95 ms; adapter string matched to `ULTRA_QA_TARGETS`; JSON download. No GPU timestamps. Never run on a discrete GPU in this repo. |
| Ultra fps matrix | `src/qa/ultraFpsMatrix.ts`, `fixtures/qa/ultra_fps_matrix.synthetic.v1.json`, `ultra_fps_matrix.measured.v1.json` | Synthetic only | Every synthetic row is 132 avg / 118 low / 8.47 ms p95 regardless of GPU. The measured fixture has `"samples": []`. `evaluateFpsSample` passes when avg >= target, 1% low >= 0.9 x target, p95 <= 1.15 x target ms. |
| Simulated Ultra QA | `src/qa/simulateUltraQa.ts`, `tests/test_simulate_ultra_qa.py`, `docs/SIMULATED_ULTRA_QA.md` | Implemented and verified as a simulation | Checks adapter string to band, tier, pass graph, Neutral collapse, snapshot distinctness, synthetic fps rows. The doc says "passed (simulated)" and lists what is not claimed. The Python test rewrites `tests/fixtures/qa/simulated_ultra_qa.v1.json` on every run. |
| GPU adapter classification | `src/contracts/GpuAdapter.ts`, `QualityTier.ts` | Implemented and verified by string tests | Regex over the adapter description; `requestAdapter({ powerPreference: 'high-performance' })`; bands ultra / high / integrated / unknown. No capability or limit probing beyond that. |
| Render graph and tiers | `src/contracts/RenderGraph.ts`, `QualityTier.ts`, `benchmarks/renderGraph.bench.test.ts` | Implemented and verified as contracts | Pass enablement per tier; the file named `benchmarks/` is a vitest of pass counts and particle budgets, not a benchmark. |
| WGSL shader tree | `packages/psyfi-gpu-renderer/shaders/wgsl/**` | Obsolete as a render path | `docs/specs/gpu-lab.md` and `docs/FRONTEND_BOUNDARY.md` say bloom, SSAO, SSR and material files are stubs returning black; the live post path is the TSL graph in `PresentPipeline.tsx`. |
| Present pipeline and safety attenuator | `src/PostProcessing/PresentPipeline.tsx` | Implemented but unverified in a browser here | TSL graph: GTAO, SSR, bloom, DoF, motion blur, chroma, afterImage, grade, safety uniform. Not driven in this session. |
| Vision bench | `psyfi_core/visualization/vision_bench.py`, `scripts/capture_vision_bench.py`, `docs/specs/vision-bench.md` | Implemented and verified (Daniel, PR #40) | Four generated 64x64 images, oracle lock on `recommend_mode_intensity`, `field_displacement` as L1 over `parameters`, `mode_steps` ruler, catalog switch, receipt scoring, no public route, no committed receipt. 13 tests pass, 1 skips. Prior art for FDE, not a rebuild target. |
| Image reading provider call | `psyfi_api/image_reading.py` | Implemented and verified with a stub transport | One `urllib` POST to `{NVIDIA_API_BASE or integrate host}/v1/chat/completions`, `nvidia/` namespace check, `max_tokens` 256, `reasoning_effort` none, 30 s timeout, key redaction. Reusable pattern for a provider adapter; the function itself is API-bound. |
| Telemetry | `psyfi_api/telemetry.py`, `routers/telemetry.py` | Implemented and verified | Default off; in-process deque; no sink. Not benchmark telemetry. |
| CI | `.github/workflows/ci.yml` | Implemented and verified by reading | Installs `.[dev]`, runs `python -m pytest -q`, `npx hallmark lint README.md`, `npm run gpu:test`, `gpu:typecheck`, `gpu:build`. No GPU runner, no provider call. Baseline in this session: 192 passed, 1 skipped; vitest 101 passed. |
| Hardware detection (Python) | none | Proposed | Nothing in `psyfi_core` or `psyfi_api` reads CPU, GPU, driver, or BLAS information. |
| Power and thermal telemetry | none | Proposed | No `nvidia-smi`, `rocm-smi`, or `powermetrics` use anywhere. |
| Statistics (CI, bootstrap, CV) | none | Proposed | No percentile beyond p95, no confidence interval, no variance analysis in either language. |
| Workload manifests and result schemas | none | Proposed | Fixtures exist for goldens and the fps matrix; no versioned workload definition or result envelope exists. |

## 3. Simulated Ultra QA versus physical hardware

The readiness board (`docs/PRODUCTION_READINESS.md`) marks "Desktop discrete Ultra path" as **done** and the README table says "Desktop Ultra (30/40/50 + peers): ready". The evidence behind those rows is:

- `simulateUltraQa.ts`: string classification of adapter names and pass-graph composition. It exercises no GPU.
- `ultra_fps_matrix.synthetic.v1.json`: identical invented rows for eight GPUs, labeled `"source": "synthetic"`.
- `ultra_fps_matrix.measured.v1.json`: empty.
- `docs/SIMULATED_ULTRA_QA.md`: honest about what is not claimed (frame times, 1% lows, driver forcing).
- `docs/HARDWARE_ULTRA_FPS.md`: a capture procedure that has not been executed in this repo.

The distinction matters for the benchmark: the existing harness proves the tiering logic is coherent, not that any GPU meets any budget. `docs/specs/AUDIT.md` already lists the Ultra path as **unproven**. `HANDOFF.md` (PR #42) says this Mac is not Ultra evidence. The benchmark design keeps the same stance: a result carries a measurement class and a hardware class, and an integrated Apple result is never promoted into an Ultra fixture.

## 4. Benchmark infrastructure assessment

What exists is QA tooling, not a benchmark:

| Need | Present today | Gap |
| --- | --- | --- |
| Versioned workload | G4 seed list (`g4Parity.ts`), fixed capture URL | No manifest, no hash, no parameter sweep |
| Timing | rAF spacing in the browser; nothing in Python | No CPU time, no GPU time, no warm-up policy beyond 60 frames |
| Memory | none | No RSS, no tracemalloc, no GPU memory |
| Repetition and variance | one capture, 180 frames | No repeats, no CI, no cold versus steady split |
| Determinism check | hashes for ParameterField and procedural structure | No output-field hash for the simulation, no cross-run comparison tool |
| Reference outputs | overlay goldens, G4 goldens, soft pixel goldens | None for simulation fields, none for rendered frames per tier |
| Hardware identity | adapter description regex | No driver, OS, browser, CPU, BLAS or Python versions recorded |
| Model evaluation | vision bench: four images, one metric, receipt file | No corpus beyond four images, no structured input, no baselines, no repeatability, no cost or token accounting |
| Result envelope | `psyfi.ultra_fps_sample.v1`, `psyfi.vision_bench_capture.v1` | Two unrelated ad hoc shapes; no common provenance block |
| Scoring and statistics | pass or fail thresholds in `evaluateFpsSample` | No scorecard, no normalization rules, no sensitivity |
| Reporting | printed JSON | No report generator, no comparison tool |

## 5. Technical debt and architectural weaknesses

1. **`FrameProfiler.cpuMs` is not CPU time.** `App.tsx` pushes `Math.max(cpuMs, dt * 1000)`, where `dt` is the rAF interval. The HUD therefore shows frame spacing, and `fps` is `1000 / average`. Average-derived fps hides pacing jitter and is biased by outliers in a way that a median or a frame-time distribution is not.
2. **Draw-call field is a pass count.** `drawCalls: passes.length` in `App.tsx`. The budget document (`docs/rendering/GPU_PERFORMANCE_BUDGET.md`) sets draw-call budgets of 40 and 80 that nothing measures.
3. **`snapshotLagMs` is hard-coded to 0.** The budget document lists snapshot lag as instrumentation that exists; it is a constant.
4. **Pass or fail thresholds without variance.** `evaluateFpsSample` compares one capture to a target. No CI, no repeat, and a 1% low from 180 frames is one or two frames.
5. **Synthetic matrix presented beside "done".** The board and README say the Ultra path is done; the fixture is invented. The simulated QA doc is honest, the board is not.
6. **Prose tests.** `tests/test_production_readiness.py` asserts strings such as `"✅ pass"` and `"RTX 5060"` in Markdown. `docs/specs/AUDIT.md` already names this. A benchmark must not add tests of that kind.
7. **Mutating test.** `tests/test_simulate_ultra_qa.py` rewrites a committed fixture on every run, which leaves the tree dirty after `pytest`. Observed in this session.
8. **No scaling knowledge.** `PsyFiConfig.max_grid_size` is 1024 x 1024 and the simulate request allows 512 x 512 x 1000 steps, but no document records how long any size takes on any machine. `docs/PERFORMANCE_BUDGETS.md` sets 2.0 s and 15.0 s budgets that nothing measures.
9. **Three sources of run-to-run noise are unhandled.** Wall time depends on thermal and scheduler state, RSS depends on allocator state, and `published_at` and `snapshot_id` make snapshot documents non-identical across runs. A benchmark has to separate deterministic content (hashable) from measurement (statistical).
10. **No power or thermal telemetry.** Energy efficiency appears in the mission but nowhere in the tree.
11. **No statistics in either language.** The only percentile function is a nearest-rank `percentile()` duplicated in `FrameProfiler.ts` and `measureUltraFps.ts`.
12. **Provider client is API-bound.** `image_reading.py` reads environment variables inside the call and is tied to one host and one prompt. A benchmark needs a provider abstraction with injectable transports and recorded receipts.
13. **Vision bench is a single-model, four-image receipt.** By its own spec that is the decision. A general interpretation benchmark needs a larger corpus, baselines and repeatability, which is new work beside it, not a change to it.
14. **CORS is `allow_origins=["*"]` with credentials** (`psyfi_api/main.py`). Recorded in `docs/specs/api-v1.md` as outside the freeze text. Not a benchmark defect, but any bench ingest endpoint inherits it, which is a second reason to gate ingest.

## 6. Reusable components

| Component | Reuse in FieldLoop |
| --- | --- |
| `ABXRuntime`, `evolve_consciousness_omega`, `apply_normalization`, `compute_valence_metrics` | Family A workload bodies, called exactly as `run_simulation` calls them |
| `run_simulation` | Reference path for the FieldLoop simulate stage |
| `map_parameters`, `MODE_BIASES` | Oracle fields, FDE, mode-step ruler |
| `build_scene_snapshot`, `_procedural_from_field` | Render stage input for both soft and WebGPU classes |
| `softPresent.ts` | Specification for the Python soft raster; parity target |
| `metricsFromFrame`, `histogramL1` (TS) | Pixel metrics to mirror in Python |
| `analyze_features`, `recommend_mode_intensity` | Photometric heuristic baseline |
| `vision_bench.field_metrics` idea | FDE definition; the bench imports nothing from that module and shares no score |
| `classifyAdapterInfo`, `probeGpuAdapter` | Adapter block in `psyfi.bench.gpu_capture.v1` |
| `SceneRoot`, `PsyFiGPUCanvas`, `PresentPipeline` | Rendered unchanged by the bench runner page |
| `tierConfig`, `enabledPasses` | Stage definitions per tier |
| `image_reading._post_once` pattern | Transport shape for the OpenAI-compatible provider adapter |
| `jobs.simulation_slot` | Not reused; bench runs are CLI processes, not API jobs |

## 7. Missing capabilities

- Versioned workload manifests with content hashes.
- Python timing and memory instrumentation (`perf_counter`, `process_time`, `resource.getrusage`, `tracemalloc`).
- Deterministic field hashing (exact bytes and quantized) and a compare tool.
- Statistical module: percentiles, CV, MAD, seeded percentile bootstrap.
- Environment capture: OS, CPU, cores, RAM, Python, numpy, scipy, BLAS, git commit; GPU and driver where a tool exists; browser UA, adapter, limits, timer quantization state.
- Python soft raster of scene snapshots and pixel fidelity metrics.
- Browser bench runner with scripted stages, GPU timestamps, thumbnails, capture upload.
- Model provider abstraction, replay provider, baseline providers, receipt store.
- Interpretation corpus from a seed grid with structured and image inputs, perturbations, repeatability.
- Result envelope, scorecard, report and comparison CLI.
- Bench API (read, capabilities, schemas, gated ingest) separate from `/api/v1`.
- Power sampling where available; explicit `unavailable` otherwise.

## 8. Ownership boundaries

Daniel owns the frontend: `psyfi_api/templates/`, `psyfi_api/static/`, the `/gpu/` experience and its React components, styling, navigation, and active branches (`fix/social-preview`, `docs/fable-handoff`, `fix/pr-template-case` were open on 2026-11-07). The benchmark does not edit those files. The browser runner is a new `bench.html` entry plus new files under `src/bench/` and one additive Vite input; existing components are imported, not modified.

Fable owns `psyfi_bench/`, `docs/bench/`, `docs/schemas/bench/`, `docs/contracts/bench/`, the bench tests, and the bench spec in `docs/specs/`.

Governance conflict, stated plainly. `HANDOFF.md` in pull request #42 (unmerged on 2026-11-07) lists as "not yours until a human accepts an intent": a GPU frame-time bench, hardware-quality scaling, and recording frame times. Aaron's mission brief of 2026-11-07 explicitly authorizes a GPU visualization benchmark with frame-time percentiles, hardware detection, and actual device measurements. The mission is the delegating human's instruction and this work follows it for those three items. Every other hard stop in `HANDOFF.md` stays in force: no login, API key check, origin allowlist, rate limit or AI Gateway; catalog reload left alone; no model id pinned; no key or vision-bench receipt committed; freeze id, `api_version`, FastAPI `version`, engine default, image-reading sentence and `reasoning_effort` unchanged; no `www`; no force-push; no admin-merge; product version `1.4.0` untouched. Issue #10 stays in Backlog and the Ultra fps fixtures are not modified by anything the bench produces.

## 9. Dependency and risk analysis

| Dependency or risk | Effect | Mitigation |
| --- | --- | --- |
| numpy and scipy versions and BLAS backend | Bitwise field output can differ across machines | Record versions; exact hash for same-machine, quantized hash (1e-5) for cross-platform |
| Apple M5 integrated GPU is the only GPU here | No discrete-GPU measurement possible in this session | Label hardware class; keep Ultra fixtures untouched; document the gap |
| WebGPU in the available browser | Runner may not run here | Runner degrades to a capabilities report; vitest covers pure modules |
| Chrome timer quantization for `timestamp-query` | GPU pass times coarse unless developer flag | Record the quantization state in the capture; wall time stays primary |
| Provider access (NVIDIA key, Anthropic key, local server) | Interpretation family cannot be measured live without a key | Replay and baseline providers; CI never opens a socket |
| `.github/PULL_REQUEST_TEMPLATE.md` case collision on macOS | Appears modified in every checkout | Never stage it |
| `tests/test_simulate_ultra_qa.py` rewrites a fixture | Dirty tree after `pytest` | Revert before commit; do not add tests that write committed files |
| Hallmark lint on `README.md` | A malformed table fails CI | Only one added row, padded |
| Frozen OpenAPI full-body equality | Any new route on `app` fails two tests | Bench API mounted as a sub-app; parent OpenAPI unchanged |
| Daniel's concurrent branches | Merge conflicts in shared files | Bench touches `psyfi_api/main.py` (one mount line), `pyproject.toml`, `vite.config.ts`, `README.md`; nothing else shared |
| Model prompt sensitivity | Scores move with wording | Prompt text and revision are part of the manifest hash |
| Soft raster information content | Interpretation task may be too easy or ill-posed | Baselines are run and reported beside every model |

## 10. What this pass did not do

- Did not run the `/gpu/` page or the present pipeline in a browser.
- Did not run any provider call.
- Did not build the Docker image.
- Did not measure any GPU. The only machine present is an Apple M5 laptop with an integrated GPU.
