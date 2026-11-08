# Spec: FieldLoop benchmark platform

Status: implemented on branch `bench/fieldloop-foundation` (2026-11-07). This file is the decision record for the benchmark subsystem. The vision bench keeps its own record.
Seam: the `psyfi_bench` package (CLI and mounted `/api/bench` sub-application) over `psyfi_core`, plus the additive browser page `/gpu/bench.html`.

## Problem Statement

PsyFi can produce a deterministic field, a scene snapshot, a rendered frame and a model caption, but it cannot say how fast a GPU renders its tiers, how well a model reads its fields, or how the whole loop behaves on a given machine. The performance claims in the tree rest on a synthetic frame-time matrix and prose tests. A benchmark that borrowed a conventional leaderboard would not use what PsyFi has: a generative pipeline whose ground truth is known at every stage.

## Solution

FieldLoop closes a loop the instrument already contains: seed → ABX simulation → ParameterField and scene snapshot → render → model interpretation → field reconstruction. Each stage is a workload family with versioned manifests, locked references and a sealed result document. The headline interpretation metric is Field Displacement Error: the L1 distance in ParameterField parameter space between the generating field and the field a model's reading reconstructs, with the nearest mode step as ruler. Compute and rendering families report time, memory, throughput, percentiles, pacing and drift with seeded bootstrap intervals. Every result says whether it is measured, synthetic or replayed. There is no universal score; scorecards are per family with published composites and validity gates. Execution is headless and CLI-only; the public host exposes a read surface and an env-gated capture ingest. Daniel's frontend is untouched; the browser runner is one additive page that reuses the GPU lab's scene unchanged.

## User Stories

1. As an operator, I want `psyfi-bench list` to show versioned workloads with a hash, so that two runs can be matched before they are compared.
2. As an operator, I want `psyfi-bench run field-compute.scaling` on a CPU-only machine, so that the simulation pipeline is benchmarked without a GPU or a key.
3. As an operator, I want cell-steps per second, the log-log scaling exponent and peak memory per stage, so that grid and step cost is characterized and not just timed.
4. As an operator, I want exact and quantized digests on every stage, so that same-machine and cross-platform determinism are separate claims.
5. As a maintainer, I want locked references in the manifest, so that a drift in the simulation or the raster fails a test on purpose.
6. As an operator, I want a cold run, warm-ups and repeats recorded separately with bootstrap intervals, so that one slow first run cannot pass as the steady state.
7. As an operator, I want a sustained workload that reports drift, so that thermal and scheduling effects show up as a slope and a quartile ratio.
8. As an operator, I want an accelerator port validated against the NumPy authority before its timings count, so that a fast wrong answer is a failure.
9. As an operator, I want a Python raster of a scene snapshot that is bit-identical to the TypeScript soft-present, so that the CPU render class is one deterministic picture in both languages.
10. As an operator, I want the browser bench to run the G4 seeds at every tier for a fixed frame count after a warm-up, so that tiers are compared on the same frames.
11. As an operator, I want per-frame wall times, GPU timestamps when the adapter exposes them, draw calls and a small thumbnail per tier, so that frame rate, pacing and same-device fidelity are measured and not inferred.
12. As an operator, I want the capture scored in Python with p50/p95/p99, 1% low, pacing, drift, the tier budget rule and SSIM against that device's Ultra frame, so that the browser only measures and the scorer is testable.
13. As a maintainer, I want fidelity compared only within one device, so that driver differences are not scored as quality.
14. As an operator, I want a deterministic corpus of fields rendered at run time with a locked digest, so that every model sees the same pixels and no image file is committed.
15. As an operator, I want models asked for mode and intensity in perceptual language with strict JSON parsing, so that a label guess and a format failure are distinguished.
16. As an operator, I want FDE, mode accuracy, intensity error, schema-violation rate, latency, tokens and cost per valid result, so that quality and price sit beside each other.
17. As an operator, I want oracle, constant, random and photometric-heuristic baselines, so that a model's number has a floor and a ceiling.
18. As an operator, I want a structured-input task on the snapshot with the answer removed, so that visual and structural reasoning are compared on the same fields.
19. As an operator, I want perturbation and repeatability tasks, so that invariance to presentation and self-consistency are measured.
20. As an operator, I want local OpenAI-compatible endpoints, the NVIDIA integrate host and the Anthropic Messages API behind one interface, so that local and remote inference are benchmarked the same way and labelled by locality.
21. As an operator, I want a replayable receipt of raw model answers without the key or the image, so that a run can be re-scored offline and the replay is labelled as such.
22. As an operator, I want the FieldLoop workload to time simulate, snapshot, render, interpret and reconstruct separately and end to end, so that the pipeline's bottleneck is visible.
23. As an operator, I want a scorecard per family with units, direction, intervals and a validity gate, so that only identical workloads are ranked.
24. As an operator, I want composites to carry their formula, inputs, sensitivity and missing-data rule, so that no number arrives without its derivation.
25. As a maintainer, I want results sealed with a hash and stored with full environment and provenance, so that a result file can be verified later.
26. As a maintainer, I want missing telemetry listed with a reason, so that absent power or thermal data is never estimated.
27. As a maintainer, I want the bench API mounted as its own sub-application, so that the frozen `/api/v1` OpenAPI document does not change.
28. As a maintainer, I want capture ingest off by default and bounded when on, so that the public host cannot be used to store arbitrary data.
29. As a maintainer, I want no public run endpoint, so that the public host never executes compute on request.
30. As a maintainer, I want JSON schemas, the bench OpenAPI and example documents exported and drift-tested, so that Daniel integrates from contracts and not from code reading.
31. As a maintainer, I want the simulation orchestration in `psyfi_core`, so that the benchmark never imports the API package and the authority has one home.
32. As Daniel, I want no change to the shell, the GPU lab components or their styles, so that my frontend work and this work do not collide.
33. As Aaron, I want synthetic, replayed and integrated-class results labelled, so that nothing in a report can be mistaken for discrete-GPU evidence.

## Implementation Decisions

- Package `psyfi_bench/` with `schemas`, `stats`, `determinism`, `timing`, `environment`, `store`, `registry`, `runner`, `scoring`, `report`, `cli`, `api`, `contracts`, `compute/backends`, `render/{soft_raster,fidelity,adapter}`, `providers/*`, `families/{field_compute,render,interpretation,fieldloop}`, `workloads/*.json`. It imports `psyfi_core` and never `psyfi_api`.
- Schemas: `psyfi.bench.manifest.v1`, `psyfi.bench.result.v1`, `psyfi.bench.gpu_capture.v1`, `psyfi.bench.scorecard.v1`, `psyfi.bench.capabilities.v1`, `psyfi.bench.error.v1`, `psyfi.bench.index.v1`, `psyfi.bench.provider_receipt.v1`. Pydantic v2 models; JSON Schema exported to `docs/schemas/bench/`.
- A manifest hash covers id, version, family, execution, params, protocol, references and tolerances. CLI `--param` overrides are merged into the recorded manifest, so they change the hash.
- Measurement classes: `measured` (live compute, live provider, browser capture), `synthetic` (baseline providers, synthetic captures), `replay` (recorded receipts). The class is on the result and on every stage.
- Protocol: cold run recorded, warm-ups discarded, N repeats, optional min-duration loop, one memory probe under tracemalloc whose timing is excluded, seeded percentile bootstrap intervals, cooperative deadline through the ABX `should_cancel` callback.
- Field compute: `psyfi_core.simulation.simulate_field` is the canonical pipeline (moved from `psyfi_api.simulation_service`, which re-exports). Quantized digests at 1e-4 are the cross-platform reference; exact digests are same-machine. The torch backend is optional and must pass `validate_against_reference` within the manifest tolerance.
- Render: the Python soft raster is a line-for-line port of `softPresent.ts` and is checked against the TS goldens on the fixture snapshots. The browser runner is `packages/psyfi-gpu-renderer/bench.html` with `src/bench/*`; it reuses `PsyFiGPUCanvas` and `SceneRoot` unchanged and adds one Vite rollup input. Frame times are rAF wall spacing; GPU time comes from `trackTimestamp` and `resolveTimestampsAsync` when the adapter exposes timestamp queries; thumbnails are 128 px via a 2D canvas copy in a microtask after the render. The tier budget rule is the one in `ultraFpsMatrix.ts`.
- Interpretation: corpus of substances × modes × intensities × seeds, rendered at run time, locked by digest. Prompt revision 1 in perceptual language without numeric cutoffs. Strict JSON parse is scored; lenient recovery is counted separately. FDE, mode steps, decomposition into mode-only and intensity-only displacement, discriminability (Spearman), invariance ratio, cross-modal agreement, repeatability, latency, tokens, optional pricing. Three consecutive provider errors abort the remaining calls.
- Providers: `oracle`, `constant`, `random`, `heuristic` (the existing `recommend_mode_intensity`), `replay`, `openai:<base>#<model>` (local or remote by hostname), `nvidia` (an `nvidia/` id from the environment, `reasoning_effort: none`, no `response_format`), `anthropic:<model>`. One attempt, no retry, keys from the environment, redaction of every stored string.
- Scoring: dimensions per family in `psyfi_bench/scoring.py`; primary dimension plus gate per family; composites with formula, inputs, ±10 % sensitivity, missing-data rule; validity requires one manifest hash and flags mixed measurement classes.
- API: `bench_app` mounted at `/api/bench` in `psyfi_api/main.py`. Routes `GET /v1/capabilities`, `GET /v1/workloads`, `GET /v1/workloads/{id}`, `GET /v1/results`, `GET /v1/results/{run_id}`, `GET /v1/schemas`, `GET /v1/schemas/{name}`, `POST /v1/captures` (403 unless `PSYFI_BENCH_INGEST=1`; 413 over 8 MB or 20,000 frames; 422 invalid; 409 wrong manifest). `run_enabled` is false.
- Storage: `bench_results/` (gitignored), one JSON per result, `index.json`, atomic writes, `PSYFI_BENCH_RESULTS` override.
- Governance: this spec follows Aaron's mission brief, which authorizes the GPU frame-time bench and hardware detection that `HANDOFF.md` reserved. Every other HANDOFF hard stop holds. Issue #10 and the Ultra fps fixtures are untouched.

## Testing Decisions

A good test drives the package through its public surfaces (manifests, runner, CLI, mounted API, provider protocol over a mock transport) and checks locks, labels, and failure classification. It never calls a live provider, never needs a GPU, and never treats a synthetic capture as measured.

- Contracts: manifest hash stability, unique ids, on-disk hash currency, schema export coverage, result seal and tamper detection, store round trip.
- Statistics: percentiles against NumPy, seeded bootstrap reproducibility, scaling exponent recovery, pacing and drift helpers.
- Field compute: locked quantized digests still match, bitwise repeat identity, timeout classification, unknown preset as validation failure, fake accelerator rejected, torch validated when installed.
- Render: bit-identical SHA-256 against the TS goldens, fidelity metrics, lock currency, synthetic capture scored and labelled synthetic with a drifting sustained stage caught by the budget rule, missing or mismatched capture handled.
- Interpretation and loop: corpus lock, stratified limits, structured view without the answer, strict and lenient parsers, FDE ruler, discriminability ρ = 1 for the oracle, baselines on the smoke corpus, abort after three provider errors with a key-free receipt, strict scoring of a mixed live response, prompts distinct from the caption and vision-bench prompts, FieldLoop stage timing and timeout.
- API and CLI: the bench API is absent from the v1 OpenAPI document, capabilities say `run_enabled: false`, ingest gated and bounded, scorecard validity, CLI round trip with exit codes, exported schemas and OpenAPI match the live code, examples validate.
- Browser: `schedule.test.ts` covers stage expansion, warm-up trimming and payload shape. Live WebGPU capture is a hardware task, not a CI test.

## Out of Scope

- A universal score across families.
- A public run endpoint, a login, an API key, a rate limit, an AI Gateway.
- Changing the vision bench, the caption route, the freeze id or any frozen contract.
- Modifying the shell, the GPU lab components, styles, navigation or the service worker.
- Committing measured results, model receipts or a pinned model id.
- Treating soft-raster frames, synthetic captures or integrated-class results as GPU evidence.
- Native iOS, Azure, Render.

## Further Notes

Design records: `docs/bench/RESEARCH.md` (comparison, hypotheses, threats to validity), `docs/bench/DISCOVERY.md` (inventory), `docs/bench/ARCHITECTURE.md`, `docs/bench/METHODOLOGY.md`, `docs/bench/adr/`. Integration package: `docs/bench/INTEGRATION.md`, `docs/schemas/bench/`, `docs/contracts/bench/`.
