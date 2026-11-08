# First measurements (2026-11-07)

Every number here was produced by `scripts/run_bench_suite.sh` and the browser runner on one machine. Read the labels before the numbers.

| | |
| --- | --- |
| Machine | Apple M5, 10 cores (4 performance, 6 efficiency), 16 GiB unified memory, integrated 8-core GPU |
| Hardware class | `integrated`. **Not Ultra evidence.** The Ultra fps fixtures and issue #10 are untouched. |
| Software | Python 3.12.13, NumPy 2.5.4 (Accelerate BLAS), SciPy 1.18.1, torch 2.15.0 (MPS), macOS 25.5, git `7372d31` + this branch |
| Measurement classes | field_compute, render.soft and the browser capture are `measured`; baseline model runs are `synthetic` |
| Protocol | cold run recorded, 1 warm-up, 5 repeats (3 for presets), seeded percentile bootstrap, quantization 1e-4 |

Sealed result files are under `bench_results/` on that machine (gitignored); the integration examples under `docs/contracts/bench/examples/` are smaller runs from the same host.

## Family A: field compute (CPU, NumPy authority)

`field-compute.scaling` (20 steps, seed 1337):

| grid | wall p50 ms | 95% CI of median | CV | cold ms | cell-steps/s | tracemalloc peak | bitwise repeat | locked ref |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 32×32 | 0.64 | 0.63 to 0.65 | 0.016 | 1.68 | 3.2e7 | 0.1 MB | yes | match |
| 64×64 | 1.17 | 1.15 to 1.39 | 0.081 | 1.23 | 7.0e7 | 0.4 MB | yes | match |
| 128×128 | 3.60 | 3.55 to 3.72 | 0.020 | 8.09 | 9.1e7 | 1.3 MB | yes | match |
| 256×256 | 13.20 | 13.14 to 13.33 | 0.006 | 13.59 | 9.9e7 | 5.0 MB | yes | match |

Log-log scaling exponent over this range: **0.73** (R² 0.976). Between 128² and 256² alone it is 0.94. Hypothesis H1 (exponent 1.0 ± 0.1 over 32² to 512²) is **refuted on this machine at the small end**: per-call overhead (array allocation, the box filter, Python dispatch) dominates below 128². The exponent is a characterization, not a pass/fail.

`field-compute.steps` (64×64): 10 steps 0.89 ms, 50 steps 2.26 ms, 200 steps 7.54 ms; exponent 0.71 because normalization and setup are a fixed cost per run; the marginal cost converges to 0.038 ms per step.

`field-compute.sustained` (128×128, 50 steps, 20 s): 736 runs, wall p50 6.73 ms, CV 0.088, drift slope 0.26 ms per 1000 runs, last/first quartile ratio 1.037 (R² 0.008, so no trend to speak of). Peak throughput 1.2e8 cell-steps/s.

`field-compute.presets`: all 23 presets complete through the API-equivalent pipeline, wall p50 1.63 to 2.21 ms at 64×64 × 20, every quantized visualization digest matches its lock.

Determinism: every stage bitwise identical across repeats; 30 of 30 locked references match; zero NaN/Inf.

## Family A: cross-platform determinism (GitHub Actions, Linux x86-64)

Observed by CI on PR #56 (run 42447145978, 2026-11-08), not on this Mac. The locked quantized digests (1e-4) computed on Apple arm64 reproduced on the ubuntu runner for `grid_32x32`, `grid_64x64`, `grid_128x128` and 22 of 23 presets, but not for `grid_256x256` (20 steps) or `preset_2c-e` (64², full pipeline). Exact digests were identical across repeats on both machines. Interpretation: different BLAS/SIMD reduction order produces differences below 1e-4 that cross rounding boundaries once enough elements accumulate. Response: every field-compute lock now carries a continuous summary checked at `reference_atol` 1e-3; the digest stays recorded as platform-class evidence. The summary error on the runner is reported by the CI log of the next run and is not yet recorded here.

## Family A: accelerator port (torch, MPS)

`field-compute.accelerator`, backend `torch-mps`, validated against NumPy per stage:

| grid | wall p50 ms | CV | cell-steps/s | max abs error vs NumPy | within 1e-3 |
| --- | --- | --- | --- | --- | --- |
| 64×64 | 12.70 | 0.102 | 6.5e6 | 7.7e-7 | yes |
| 128×128 | 13.05 | 0.081 | 2.5e7 | 1.3e-6 | yes |
| 256×256 | 11.92 | 0.076 | 1.1e8 | 1.1e-6 | yes |
| 512×512 | 25.86 | 0.135 | 2.0e8 | 1.9e-6 | yes |

Reading: on this integrated GPU the port is slower than NumPy below 256² (launch and transfer overhead, flat ~12 ms) and faster above it (2.0e8 vs the CPU's best 1.2e8 cell-steps/s). The CPU simulation remains the authority; these timings include the host-to-device copy of the seeded field.

## Family B: render, soft execution class (CPU raster)

`render.soft.g4`, 3 seeds × 4 tiers × 3 sizes, 36 stages, all bitwise identical across repeats, 36 of 36 locked rasters match, cross-language parity **3 of 3** with the TypeScript soft-present goldens (same fixture snapshots, same SHA-256).

| tier | raster ms per megapixel (median over 9 stages) | SSIM vs Ultra (mean) |
| --- | --- | --- |
| ultra | 312 | 1.000 |
| high | 318 | 0.982 |
| balanced | 310 | 0.987 |
| battery | 241 | 0.955 |

At 256 px the lsd_open_42 raster takes 9.6 ms (147 ms/MP). Ultra, high and balanced differ only through the ParameterField's quality-tier hash salting the procedural layout; the soft raster ignores post flags. Battery changes the field itself. This is the CPU picture, not a WebGPU frame.

## Family C: interpretation baselines (96-item corpus, synthetic class)

| provider | parse | mode acc. | intensity MAE | FDE mean (95% CI) | FDE / mode step | within step | discrim. ρ | structured FDE | cross-modal agree | invariance ratio | pert. mode flips | repeat exact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| oracle | 1.00 | 1.000 | 0.000 | 0.000 (0.000 to 0.000) | 0.00 | 1.00 | 1.000 | 0.000 | 1.000 | undefined (0/0) | 0.000 | 1.000 |
| constant open/0.5 | 1.00 | 0.250 | 0.200 | 1.924 (1.729 to 2.124) | 1.03 | 0.54 | 0.132 | 1.924 | 1.000 | undefined (0/0) | 0.000 | 1.000 |
| random (seed 0) | 1.00 | 0.260 | 0.312 | 2.587 (2.337 to 2.834) | 1.48 | 0.24 | 0.095 | 2.595 | 0.260 | 1.015 | 0.781 | 0.000 |
| heuristic (`recommend_mode_intensity`) | 1.00 | 0.271 | 0.267 | 2.892 (2.653 to 3.135) | 1.80 | 0.25 | 0.159 | 2.049 | 0.062 | 2.283 | 0.188 | 1.000 |

Reading: the oracle sets the ceiling; a constant central answer is a strong floor in FDE because it is never far from any field (this is why mode accuracy and FDE are reported side by side); random has an invariance ratio of 1.0 as hypothesis H5 predicts for an input-blind reader; the photometric heuristic is at chance on mode and worse than constant on FDE, so it is a floor, not a competitor. No live model has run yet (issue #49).

## Family D: FieldLoop (CPU loop, 64×64 × 12 simulation, 256 px raster)

| provider | loops closed | end-to-end p50 | FDE median | stage shares: simulate / snapshot / render / interpret / reconstruct |
| --- | --- | --- | --- | --- |
| oracle | 6/6 | 11.3 ms | 0.000 | 0.106 / 0.007 / 0.860 / 0.001 / 0.021 |
| heuristic | 6/6 | 12.4 ms | 3.314 | 0.098 / 0.007 / 0.817 / 0.056 / 0.020 |

On the CPU loop the raster is 82 to 86 % of the end-to-end time; a live remote provider would make interpretation the dominant stage. Cold run 13.3 ms vs steady 11.3 ms.

## Family B: WebGPU capture (browser, this Mac)

Runner: `/gpu/bench.html` in the Claude desktop app's embedded Chromium 152 (WebGPU on Metal 3), viewport 1024×768 at device pixel ratio 2. Adapter string reported by WebGPU: `apple`, architecture `metal-3`, classified `integrated`, perf band `high`. Five captures were taken while the runner was hardened; the cleanest (per-stage renderer remount, warm-up ≥ 120 frames and ≥ 5 s, GPU timestamps off) is `render_1794111319_e35f89b7`.

What the numbers mean here: frame times are `requestAnimationFrame` spacing, capped by the 60 Hz display, so 16.7 ms at p50 means "the display is fed every refresh", not "the GPU needs 16.7 ms". The Ultra budget of 8.3 ms can never be met under a 60 Hz cap, so `budget_ok` is false for every tier except battery by construction on this display. GPU timestamp queries are the right instrument for GPU cost; see the timestamps note below.

| stage (tier) | status | fps avg | 1 % low | p50 ms | p95 ms | max ms | stutters (> 2× median) | draw calls / frame |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lsd_open_42 ultra | failed (241 uncaught errors) | 60.0 | 53.2 | 16.7 | 18.1 | 19.5 | 0 | 8 |
| lsd_open_42 high | failed (241 uncaught errors) | 53.9 | 32.6 | 16.7 | 18.5 | 435.9 | 1 | 12 |
| lsd_open_42 balanced | ok | 58.8 | 30.2 | 16.7 | 18.5 | 48.0 | 3 | 25 |
| lsd_open_42 battery | ok | 60.0 | 53.6 | 16.7 | 18.4 | 21.2 | 0 | 14 |
| psilocybin_attractor_7 ultra | failed | 59.5 | 50.7 | 16.7 | 18.5 | 49.9 | 1 | 8 |
| psilocybin_attractor_7 high | failed | 58.8 | 53.3 | 16.6 | 18.5 | 86.1 | 2 | 12 |
| psilocybin_attractor_7 balanced | ok | 56.5 | 14.5 | 16.6 | 18.4 | 85.0 | 5 | 25 |
| psilocybin_attractor_7 battery | ok | 60.0 | 53.6 | 16.7 | 18.4 | 42.7 | 1 | 14 |
| dmt_void_99 ultra | failed | 60.0 | 52.7 | 16.6 | 18.2 | 19.1 | 0 | 8 |
| dmt_void_99 high | failed | 57.4 | 53.9 | 16.7 | 18.2 | 130.0 | 2 | 12 |
| dmt_void_99 balanced | ok | 60.0 | 54.1 | 16.7 | 18.2 | 18.7 | 0 | 25 |
| dmt_void_99 battery | ok | 60.0 | 54.1 | 16.7 | 18.1 | 18.5 | 0 | 14 |
| sustained lsd_open_42 ultra (1800 frames) | failed | 60.0 | 52.6 | 16.7 | 18.4 | 19.4 | 0 | 8 |

Per tier (valid stages only): balanced fps avg median 58.8, 1 % low median 30.2, p95 18.4 ms; battery 60.0 / 53.6 / 18.4 ms, `budget_ok` true.

Readings:

- Balanced and battery are measured cleanly on this integrated GPU: both feed the 60 Hz display, battery with no stutter, balanced with a few 40 to 85 ms frames (the 1 % low of 14 to 30 fps on two balanced stages is those frames).
- Ultra and high are **not measured** under the runner on this configuration: every frame raised an uncaught error inside the three.js WebGPU backend (`usedTimes` of undefined during object disposal), so the scorer fails those stages by design and their frame numbers are not evidence. The GPU lab's own page renders tier ultra from the query without errors but throws the same error on every frame after a runtime tier change (issue #55). The runner was changed to remount the renderer per stage and to publish the snapshot after an empty-scene mount, and the errors persisted; the remaining difference to the lab page is still open and is part of #55. A discrete-GPU capture (#48) will show whether this is adapter-specific.
- The sustained Ultra stage inherits the same failure, so no drift number is reported for this device.
- Thumbnails read back for balanced and battery only. Tier fidelity needs the Ultra thumbnail as reference, so `ssim_vs_ultra` is null on this device (reported as missing, not as 1.0).

GPU timestamps: with `?timestamps=1` (capture `render_1794110812_5c4d6351`) the adapter exposed `timestamp-query` and three resolved per-frame GPU times: balanced p50 11.7 to 17.4 ms, battery p50 0.5 to 0.9 ms. That capture also showed one ~1 s frame in most stages, which the timestamps-off capture does not have, so per-frame `resolveTimestampsAsync` is itself a measurable disturbance on this adapter; timestamps therefore stay opt-in and the capture records whether they were requested. Chrome quantizes timestamp values unless the WebGPU developer-features flag is on.

Runs in the store on this machine: `render_1794109871_1672195e` (first capture, one renderer across tiers, no error counting: its ultra/high rows are contaminated and should not be read), `render_1794110365_8d3bd334` (error counting on, timestamps on), `render_1794110812_5c4d6351` (per-stage remount, timestamps on), `render_1794111319_e35f89b7` (timestamps off, the table above), and a fifth with two-phase mounts.
