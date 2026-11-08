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

See the section appended below after the first browser capture was scored. Frame times from `requestAnimationFrame` are capped by the display's refresh rate (60 Hz here), so a 60 fps reading means "the display is being fed", not "the GPU needs 16.7 ms". GPU timestamp queries are needed for GPU cost; they are recorded when the adapter and browser expose them.
