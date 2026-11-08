# FieldLoop Phase 2: Research and benchmark design

Date: 2026-11-07
Author: Fable, benchmark architecture owner
Companion: [`DISCOVERY.md`](DISCOVERY.md) for what the repository already has
Status: design record. Implementation decisions that bind the code live in `docs/specs/benchmark-platform.md`.

Modeled phenomenology for research and visualization only. The benchmark measures computation, rendering and model readings of a modeled field. It does not measure consciousness, subjective experience, or any phenomenological state. Not medical advice.

## 1. Existing benchmarks compared

Research conducted 2026-11-07 from the sources listed in section 12. Where a detail could not be confirmed from an official page it is marked "per secondary source".

| System | What it measures | Reproducibility | Correctness validation | Normalization | Heterogeneous hardware | What Psy-Fi reuses | Gap Psy-Fi addresses |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MLPerf Inference (v5.x, v6.0) | Throughput and latency of fixed models under LoadGen scenarios: Offline, Server, SingleStream, MultiStream; v6.0 adds a vision-language task (Qwen3-VL 235B A22B product categorization) | Rules document, fixed datasets, LoadGen traffic generator, minimum durations and query counts, early-stopping penalties | Accuracy gate against a reference (per secondary source, 99% or 99.9% of reference metric per task) | Per-benchmark targets; no composite | Submitter declares a system; results are per system, divisions Closed and Open | Scenario vocabulary (single-stream, offline), warm-up and minimum-duration discipline, accuracy gate before a performance number counts | MLPerf fixes the model and varies hardware; FieldLoop fixes the workload source and varies both hardware and model, with ground truth known for every sample |
| Geekbench AI 1.x | Inference throughput on vision and language workloads in FP32, FP16 and INT8 ("Single", "Half", "Quantized") | Fixed models and inputs; three scores | Accuracy against the full-precision CPU reference; accuracy scales the workload score | Geometric mean of workload scores per precision | One device, many frameworks; scores not comparable across frameworks | Accuracy-scaled throughput as a pattern; reporting precision classes separately | Geekbench uses opaque reference predictions; FieldLoop references are the generating parameters themselves |
| 3DMark Steel Nomad | A single DirectX 12, Vulkan or Metal graphics test at 4K; overall score equals the graphics test score | Fixed scene, fixed resolution; a Light variant for weaker hardware that must not be compared with the base | Visual output is not scored | Score derived from frame rate (formula not published in the sources read) | Cross-platform through three APIs; Light versus base kept apart | Fixed-scene discipline, tier variants kept incomparable | No image-quality axis; FieldLoop pairs frame time with same-device tier fidelity |
| Blender Open Data | Cycles samples per minute summed over Classroom, Monster and Junkshop (per secondary source) | Fixed scenes, fixed time window, public CC0 content | A sample is a defined unit of work, so correctness is structural | Sum of per-scene rates | CPU and GPU devices listed per result | Rate of a well-defined work unit; FieldLoop uses cell-steps per second the same way | None needed for compute; FieldLoop adds determinism hashing of the output |
| llama.cpp `llama-bench` | Prompt processing (pp 512) and text generation (tg 128) tokens per second, five repetitions, standard deviation; timing excludes tokenization and sampling | Fixed model file and parameters; JSON output includes per-repetition samples | None (throughput only) | None | Backend and offload layers reported per row | Repetitions with spread reported; per-sample output in JSON | FieldLoop adds a correctness axis for model output and a field-space unit for error |
| vLLM `bench serve` | TTFT, TPOT, ITL, E2EL percentiles, throughput, goodput under SLOs | Fixed dataset and request rate; version-dependent flags | None (serving metrics) | Goodput counts requests meeting every SLO | Server under test is opaque | TTFT and E2EL separation of latency stages; goodput as "valid under constraints" | FieldLoop separates browser, network, provider and model time where observable and scores validity of the answer |
| lm-evaluation-harness | Task accuracy across versioned YAML tasks | Task versioning, `metadata.version` in outputs, seed control; paper documents prompt sensitivity | Deterministic metrics per task (exact match, log-likelihood) | Per task | Not a hardware benchmark | Prompt text and revision in the manifest hash; seeded sampling | Hardware cost and latency are not first-class there |
| NVIDIA `nvidia-smi` and DCGM | Power draw, temperature, clocks, utilization sampled over time | Field names vary by driver branch; `--help-query-gpu` is authoritative | None | None | NVIDIA only | Sampler thread pattern with CSV queries where the tool exists | Explicit `unavailable` for every other vendor; no estimation |
| WebGPU `timestamp-query` | GPU pass durations from a query set resolved into a buffer | Optional adapter feature; Chrome quantizes timers unless the WebGPU Developer Features flag is on | None | None | Chrome desktop, ChromeOS, Android from Chrome 121; others unverified | Feature detection, request, resolve, record quantization state | Wall time stays primary; GPU time is additional when available |
| three.js `WebGPURenderer` timestamps | `trackTimestamp` backend option; `renderer.resolveTimestampsAsync(TimestampQuery.RENDER)`; pool default 256 queries | Opt-in; results written to `renderer.info` | None | None | Depends on the adapter feature above | The bench runner creates its own renderer with tracking on; existing `createWebGPURenderer` untouched | Property path for the resolved value must be checked against the installed three.js version (0.175) |

Two findings shape the design. First, every system above either measures speed with a fixed correctness gate (MLPerf, Geekbench) or measures speed alone (3DMark, Blender, llama-bench, vLLM). None reports error in the units of the thing being rendered or described. Second, the statistics literature on benchmarks (Kalibera and Jones, cited in the 2022 arXiv prioritization study; Barrett et al. 2016) shows that single runs and average-derived rates hide the variance that decides whether two configurations differ. FieldLoop therefore reports distributions and intervals, never a single number without them.

## 2. Psy-Fi differentiation

Psy-Fi has a property the systems above do not: the picture is generated from a small, known, continuous parameter vector. `map_parameters` turns (substance, mode, intensity, seed, phase, tier) into an immutable `ParameterField` with about twenty-two rounded parameters and a hash. `build_scene_snapshot` turns that field into procedural geometry deterministically. The soft raster turns the snapshot into pixels deterministically. Each stage is a pure function of the previous one.

That gives four things no conventional benchmark has together:

1. **Known ground truth for every sample.** A model that reads a rendered field can be scored against the parameters that produced it. No human label, no judge model.
2. **One unit for error: the field itself.** Field Displacement Error (FDE) is the L1 distance in `parameters` space between the oracle field and the field rebuilt from the model's (mode, intensity) answer through the same `map_parameters`. It is an instrument distance, not a label grade. Daniel's vision bench introduced this idea as `field_displacement` for four images; FieldLoop generalizes it to a seed grid, structured inputs, perturbations, repeatability and baselines. The ruler is the mode step: the smallest L1 distance from the oracle field to the same field under another mode at the same intensity. `within_mode_step` is true when FDE is below that ruler, which means the answer stayed closer to the truth than the nearest wrong mode.
3. **One workload source across three domains.** The same seed grid drives the compute family (how fast and how reproducibly a machine evolves the field), the render family (how fast and how faithfully a GPU presents the snapshot) and the interpretation family (how closely a model reads the picture back). Results from the three families are about the same objects.
4. **Fidelity preservation as a measurable property.** Two fields that differ should produce readings that differ; one field presented differently (resolution, noise, flip, brightness) should produce the same reading. The ratio of reading distance across distinct fields to reading distance across presentations of one field is a discriminability-to-invariance ratio. It is computed from the model's answers and the known fields, with no judge.

Baselines turn these metrics into calibrated ones. Every interpretation report runs four providers that need no network: the oracle (returns the generating parameters; FDE 0), a constant (always `open`, 0.5), a seeded random reading, and the photometric heuristic that Psy-Fi already ships (`analyze_features` then `recommend_mode_intensity`). A model's FDE is read against those four lines.

## 3. The central hypothesis, evaluated

The mission asked whether this is scientifically meaningful:

> A controlled, deterministic simulation can generate related computational, visual and interpretive workloads that reveal how different GPUs and AI models preserve fidelity and useful performance as complexity increases.

**What is meaningful and established.** The compute part is standard performance engineering: fixed inputs, repeated timing, a well-defined work unit, output hashing. The render part is standard graphics benchmarking plus a within-device image comparison, which is how tier and quality-setting studies are normally done. The interpretation part is a controlled perception task with synthetic ground truth, a method with a long record in vision research because it removes label noise.

**What is experimental.** Whether FDE on this particular raster says anything about a model's usefulness on other images is not known. The soft raster carries a bounded amount of information about mode and intensity, and that bound is measured by the baselines rather than assumed. Whether same-device tier fidelity transfers across GPUs is not known; the bench does not compare pixels across devices for that reason. Whether cell-steps per second on the Kuramoto kernel predicts anything about other numerical workloads is not claimed.

**What the bench does not claim.** Nothing here measures consciousness, a psychedelic state, or a subjective experience. The field is a modeled representation. A model that reads it well is good at reading this instrument's pictures. A GPU that renders it fast is fast at this instrument's scene graph. Those are the only claims.

## 4. Benchmark families

### Family A: field-compute

Workloads: `run_simulation`-equivalent bodies over a grid of sizes (32, 64, 128, 256, 512 square) and step counts (10, 50, 200), plus one sustained run (fixed size, many steps, long enough to show thermal or scheduler drift). Each body calls `evolve_consciousness_omega`, `apply_normalization` and `compute_valence_metrics` exactly as the API does.

Metrics: wall ms (`perf_counter`), CPU ms (`process_time`), peak RSS delta (`resource.getrusage`), tracemalloc peak, cell-steps per second (width x height x steps / wall seconds), log-log scaling exponent across sizes, exact SHA-256 of the output complex64 bytes, quantized hash after rounding to 1e-5, NaN and Inf counts, Kuramoto order parameter.

Established: timing, memory, work-unit rate, hashing. Experimental: the scaling exponent as a device characteristic; it is reported with its fit residual.

Accelerator backends: a `ComputeBackend` protocol with the numpy reference as the canonical body. A torch backend (CUDA, MPS) re-implements the Kuramoto step and is validated against the numpy field with a declared tolerance before any of its timings count. A backend that fails validation produces a `validation_failed` result, not a timing. CPU simulation is never labeled GPU compute.

### Family B: render

Two execution classes with separate manifests and separate result sections.

`soft`: a Python port of `softPresent.ts` renders the scene snapshot on the CPU. It exists so the FieldLoop pipeline can run headlessly and so the interpretation corpus is reproducible from a seed. A parity test compares the Python raster to the TypeScript raster for the three G4 pixel-golden snapshots with a tolerance (not SHA equality; JavaScript and numpy differ in rounding of halves and in the last bit of `sin` and `cos`).

`webgpu`: a browser runner page (`bench.html`) in `packages/psyfi-gpu-renderer`. It imports `SceneRoot` and `PsyFiGPUCanvas` unchanged and drives them through a scripted stage list: for each G4 seed and each tier, a warm-up of discarded frames then a fixed count of measured frames; one sustained stage at a fixed tier. It records per-frame wall ms from rAF spacing, GPU pass time when the adapter exposes `timestamp-query` (with the quantization state recorded), renderer draw statistics, adapter info, browser and OS strings, and a 128x128 thumbnail per tier at a fixed phase. The capture (`psyfi.bench.gpu_capture.v1`) is downloaded or posted to the gated ingest route. Python scores it: p50, p95, p99 frame ms, 1% low fps, pacing jitter (MAD of frame ms), sustained drift (slope of frame ms over the sustained stage), and tier fidelity against that device's Ultra thumbnail (RMSE, histogram L1, a structural similarity approximation on 8x8 windows).

Established: frame-time distributions and within-device quality comparison. Experimental: the thumbnail readback path through a WebGPU canvas and the SSIM approximation at 128 pixels. Cross-device comparison is allowed only on identical manifest hash, and only for timing. Pixel fidelity is never compared across devices.

### Family C: interpretation

Corpus: a seed grid manifest (substances x modes x intensities x seeds, phase fixed) rendered through the soft raster at a fixed size, plus a structured variant that gives the model the snapshot's procedural geometry, palette, lighting and post flags with `parameters`, `engines`, `mode` and `intensity` removed. Perturbation variants: resolution change, additive noise, horizontal flip, small brightness change. The corpus is regenerated at run time and locked by a content hash in the manifest.

Tasks: mode classification (four classes), intensity regression (unit interval), and the combined reading scored as FDE. Repeatability: the same query sent k times at temperature 0.

Metrics: FDE mean, median and bootstrap CI; `within_mode_step` rate; mode accuracy; intensity MAE; cross-modal agreement (image reading versus structured reading on the same field); invariance (reading spread across perturbations of one field) versus discriminability (reading spread across distinct fields) and their ratio; repeatability agreement; schema violation and parse failure rate; latency p50 and p95; prompt and completion tokens from the provider's usage block; cost per valid result when the manifest supplies a price table (never hard-coded).

Established: synthetic ground truth, deterministic scoring, baselines. Experimental: FDE as a proxy for anything beyond this instrument.

Providers: OpenAI-compatible chat completions (covers vLLM, llama.cpp server, Ollama, LM Studio and the NVIDIA integrate host), Anthropic Messages API, a replay provider over a recorded receipt, and the four baselines. Keys come from the environment on the machine running the CLI. CI never opens a socket.

### Family D: FieldLoop (signature)

One seed in, one error out. Stages: ABX simulation (Family A body, with the simulation's magnitude field attached to the snapshot), scene snapshot build, render (soft locally, or a webgpu capture ingested from a browser), model interpretation (Family C provider), field reconstruction and FDE. Every stage records wall ms, CPU ms, memory, and a determinism hash of its output where the output is deterministic. End-to-end time is the sum of stages; the report also shows the stage breakdown so a slow network is not read as a slow model. Local inference (an OpenAI-compatible server on the same host) and remote inference are labeled by the provider's host class. Browser time is known only from a webgpu capture; network and provider processing time are separated where the provider returns timing headers or usage fields, and marked `unavailable` where it does not.

Why this is the signature benchmark and not a misleading single score: the headline is a pair, end-to-end latency and FDE, with the stage table beside it. There is no formula that folds frame time, cell-steps and FDE into one number, because those units are not commensurable and the mission forbids inventing a universal score.

## 5. Workload methodology

- Every workload is a JSON manifest (`psyfi.bench.manifest.v1`) with id, version, family, execution class, parameters, seeds, references, prompt text and revision where relevant, warm-up and repeat counts, timeouts, and a content hash computed over the canonical JSON. A result records the manifest hash; two results compare only when hashes match.
- Seeds are fixed in the manifest. The corpus and reference outputs are regenerated and checked against locked hashes; nothing invented is stored as a reference.
- Warm-up iterations are discarded. A cold-start run (first iteration in a fresh process) is recorded separately from steady-state iterations. Steady state is not assumed; the report shows the sequence so drift is visible (Barrett et al. 2016).
- Repeats default to five for timing workloads and one for deterministic outputs (which are hashed, not timed).
- Timeouts and cancellation are enforced per stage. A timeout produces a `timeout` failure row, not a missing row. Failure classes: `timeout`, `provider_error`, `parse_error`, `validation_failed`, `unsupported`, `crashed`.
- Environment capture is mandatory: OS, CPU brand and counts, RAM, Python and numpy and scipy versions, BLAS vendor where numpy exposes it, git commit, dirty flag; GPU name, driver and memory where `nvidia-smi` or `system_profiler` exists; browser UA, adapter description and limits, timer quantization state for captures. Missing telemetry is written as `null` with an `unavailable_reason`, never estimated.
- Measurement class is one of `measured`, `synthetic`, `replay` and is printed on every report line. Synthetic results exist only to test the pipeline.
- Model comparisons control the prompt text and revision, temperature, max tokens, image size and encoding, and the reference set. GPU comparisons control resolution scale (from the tier), tier, workload size and frame counts, and record browser and OS.

## 6. Scoring specification summary

- No universal score. Each family has a scorecard (`psyfi.bench.scorecard.v1`) with named metrics, units, direction (lower or higher is better), the statistic (median with bootstrap CI), and a validity gate (matching manifest hash, matching measurement class, comparable hardware class for timing).
- Optional ratios have published formulas: cell-steps per second per watt (only when power was sampled), frame ms versus tier fidelity on one device, FDE per dollar when a price table is supplied. Each ratio lists its inputs, the normalization (none, or min-max within a comparison set), and a sensitivity row showing how the ranking changes when a weight moves by plus or minus 25 percent. A missing input makes the ratio `null`; it never defaults.
- Recommendation statements ("best GPU for sustained rendering of this workload") are generated only from a comparison set where every member shares the manifest hash and the report prints the CI overlap. Overlapping intervals produce "no reliable difference", not a winner.

## 7. Hardware and model compatibility matrix

| Target | Status on 2026-11-07 | Note |
| --- | --- | --- |
| CPU, any OS with Python 3.10+ | Supported | Family A, soft render, interpretation with replay or baselines run with no extra dependency |
| Apple M-series (this machine, M5, 10 cores, integrated GPU) | Measured for CPU work in this session | Labeled integrated-class; not Ultra evidence |
| torch CUDA or MPS backend | Optional, unverified | Imported only when installed; must pass parity before timing |
| NVIDIA discrete (RTX 30/40/50) | Not available here | Adapter class exists in `GpuAdapter.ts`; power sampling via `nvidia-smi` is implemented behind a tool check and untested on hardware |
| AMD RX 6000/7000/9000, Intel Arc | Not available here | Adapter class exists; no vendor telemetry |
| Browser WebGPU, Chrome or Edge desktop | Expected per Chrome release notes; unverified here | `timestamp-query` quantized unless developer flag |
| Safari WebGPU | Unverified | Runner degrades to a capabilities report |
| Firefox | WebGPU off per `docs/BROWSER_CAPABILITY_MATRIX.md` | Runner reports unsupported |
| OpenAI-compatible endpoints (vLLM, llama.cpp server, Ollama, LM Studio, NVIDIA integrate) | Adapter implemented; live call unverified in CI by design | Key and base URL from environment |
| Anthropic Messages API | Adapter implemented; unverified live | Key from environment |
| Replay provider | Supported | Scores a recorded receipt with no network |
| Baselines (oracle, constant, random, photometric) | Supported | Always run beside a model |

## 8. Statistical validation plan

1. Unit tests for percentiles, MAD, CV and the seeded bootstrap against hand-computed values and against known distributions.
2. Determinism tests: two runs of a Family A workload in one process produce identical exact hashes; the quantized hash matches a locked fixture produced on this machine (cross-platform agreement is a hypothesis, section 11).
3. Reproducibility tolerance: for timing workloads the documented tolerance is the bootstrap CI of the median; two runs on one machine must have overlapping CIs for the report to call them consistent.
4. Synthetic validation of the scorer: generated frame-time series with known percentiles, generated captures with known tier fidelity, generated receipts with known FDE.
5. Baseline validation: the oracle provider must score FDE 0 on every sample; the constant provider must score the mode-step distance on every sample whose oracle mode is not `open`.
6. Variance budget: each timing report prints CV; a CV above a manifest threshold marks the run `noisy` and the report says so.

## 9. Threats to validity

| Threat | Type | Mitigation or disclosure |
| --- | --- | --- |
| FDE measures distance in a space the instrument defines; it is not perceptual distance | Construct | Stated on every report; the mode-step ruler is relative to the same space |
| The soft raster may carry little information about intensity | Construct | Baselines reported beside every model; information ceiling visible as the heuristic's FDE |
| Prompt wording moves model answers | Internal | Prompt text and revision are in the manifest hash; one prompt per manifest version |
| Thermal state, background load, power mode | Internal | Cold versus steady recorded; sustained stage shows drift; CV threshold marks noisy runs |
| Browser compositor and rAF cap timing at the display refresh | Internal | Wall ms distribution shown; GPU timestamps recorded when available; refresh rate recorded |
| Chrome timer quantization | Internal | Quantization state recorded; GPU time secondary |
| Small N (180 frames, 5 repeats) | Conclusion | Bootstrap CIs; 1% low reported with its sample count |
| This machine is one integrated GPU | External | Hardware class labeled; no cross-device claim from one device |
| Models seen only through one API shape | External | Provider and host class recorded; local versus remote separated |
| Cross-device pixel comparison | External | Forbidden by the scorer |
| Judge-free scoring assumes the generating parameters are the right answer | Construct | True by construction for this instrument; disclosed as the only claim |

## 10. Methodological contribution, stated once

FieldLoop scores an AI model's reading of a rendered simulation in the simulation's own parameter units, with the generating parameters as ground truth and the nearest wrong mode as the ruler, while the same seed grid drives the compute and render measurements of the hardware that produced the picture. The contribution is the shared workload source and the field-space error unit, not a new statistic.

## 11. Falsifiable hypotheses

| Id | Hypothesis | Measurement that refutes it |
| --- | --- | --- |
| H1 | Wall time per step for the Kuramoto body scales as cells to the power 1.0 plus or minus 0.1 over 32 square to 512 square on a CPU | Log-log fit exponent outside [0.9, 1.1] or fit residual above the manifest threshold |
| H2 | Output fields are bitwise identical across runs on one machine, and quantized (1e-5) hashes are identical across machines and numpy versions | Any exact-hash mismatch within a machine; any quantized-hash mismatch against the locked fixture on another machine |
| H3 | On one device, median frame time decreases monotonically from ultra to battery, and the quality-per-ms curve differs between devices | A tier with higher median frame time than the next heavier tier on the same device; identical curves across devices with different adapters |
| H4 | FDE is lower on structured input than on rendered images for the same fields, and image-versus-structured agreement is below 1 | Median FDE on structured input at or above median FDE on images with non-overlapping CIs; agreement of exactly 1 |
| H5 | A competent model has a discriminability-to-invariance ratio above 1, and the constant and random baselines do not | Ratio at or below 1 for a model that beats the heuristic on FDE; ratio above 1 for the constant baseline |
| H6 | The photometric heuristic is a floor that models beat, and the oracle scores FDE 0 on every sample | A model with median FDE above the heuristic's; any non-zero oracle FDE (which would be a scorer defect) |

## 12. Sources

- [MLPerf inference rules](https://github.com/mlperf/inference_policies/blob/master/inference_rules.adoc)
- [MLPerf LoadGen Python bindings](https://pypi.org/project/mlcommons-loadgen)
- [MLCommons: MLPerf Inference v6.0 vision-language benchmark](https://mlcommons.org/?p=3630)
- [Geekbench AI workloads document](https://geekbench.com/doc/geekbench-ai-workloads.pdf)
- [Signal65: Geekbench AI 1.0 analysis](https://signal65.com/research/ai/new-geekbench-ai-1-0-benchmark-analysis-and-early-results/)
- [UL: how the 3DMark Steel Nomad score is calculated](https://support.benchmarks.ul.com/support/solutions/articles/44002528064-how-is-the-3dmark-steel-nomad-score-calculated-)
- [Microsoft VirtualClient: Blender Benchmark](https://microsoft.github.io/VirtualClient/docs/workloads/blenderbenchmark)
- [SaladCloud: Blender rendering benchmark](https://blog.salad.com/blender-rendering-benchmark/)
- [llama.cpp llama-bench README](https://github.com/ggerganov/llama.cpp/blob/b8c1476e44cc1f3a1811613f65251cf779067636/examples/llama-bench)
- [vLLM benchmarks serve reference](https://docs.vllm.ai/en/v0.10.2/api/vllm/benchmarks/serve.html)
- [lm-evaluation-harness paper (arXiv 2405.14782)](https://www.emergentmind.com/papers/2405.14782)
- [Chrome: new in WebGPU 121](https://developer.chrome.com/blog/new-in-webgpu-121)
- [Chromium intent to ship: WebGPU timestamp queries](https://groups.google.com/a/chromium.org/g/blink-dev/c/dtYJ0MQYMlU)
- [three.js TimestampQueryPool](https://threejs.org/docs/pages/TimestampQueryPool.html)
- [three.js Backend](https://threejs.org/docs/pages/Backend.html)
- [Barrett et al., Virtual machine warmup blows hot and cold (arXiv 1602.00602)](https://arxiv.org/pdf/1602.00602v5)
- [Search-based microbenchmark prioritization, with Kalibera and Jones bootstrap (arXiv 2211.13525)](https://arxiv.org/pdf/2211.13525)
- [CTU benchmarking lecture notes](https://esw.pages.fel.cvut.cz/labs/pdfs/benchmark.pdf)
