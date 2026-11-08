# FieldLoop methodology and scoring specification

Date: 2026-11-07
Implements: `psyfi_bench/stats.py`, `determinism.py`, `timing.py`, `runner.py`, `families/*.py`, `scoring.py`.
Related: [ARCHITECTURE.md](ARCHITECTURE.md), [RESEARCH.md](RESEARCH.md).

## 1. Experimental protocol

| Element | Rule as implemented |
| --- | --- |
| Workload identity | A manifest has an `id` and an integer `version`. `manifest_hash` covers id, version, family, execution, params, protocol, references and tolerances. A `--param` override is merged into the effective manifest, so the recorded hash changes. |
| Seeds | Every manifest fixes seeds in `params`. `ABXRuntime(seed)` draws phases, then magnitudes. `map_parameters` and `build_scene_snapshot` are seed-deterministic. |
| Fixtures and locks | `field_compute` locks a quantized digest per stage; `render.soft.g4` locks a raster SHA-256 per stage; `interpretation` locks a corpus digest. `reference_match` is None, True or False. Tests reproduce the locks on every run. |
| Cold run | With `cold_start`, the first execution is recorded as `cold_wall_ms` and excluded from the repeats. |
| Warm-up | `warmup_runs` executions are discarded (recorded in `warmup_wall_ms`). The browser runner discards `warmup_frames`. |
| Repeats | `repeats` timed executions after warm-up. Defaults: 5 for CPU timing, 3 for presets, 1 for provider workloads. |
| Sustained | With `min_duration_s`, the stage keeps repeating until that wall time and `repeats` are both reached. `sustained_drift` is computed over the sequence. |
| Memory probe | One extra run under `tracemalloc`; `rss_peak_delta_bytes` from `resource.getrusage` (bytes on every platform). Its timing is never reported. |
| Timing | `time.perf_counter_ns` (wall) and `time.process_time_ns` (CPU). `gc.collect()` before each call. |
| Timeout and cancellation | `Deadline.should_cancel` is passed into the ABX engine and checked between repeats. Tripping gives stage status `timeout` or `cancelled`. |
| Failure classification | `timeout`, `cancelled`, `provider`, `parse`, `validation`, `resource`, `unsupported`, `internal`. A failure is a row, not an abort, except the provider abort policy below. |
| Provenance | Git commit and dirty flag, the command line, bench and psyfi versions, seed, notes. The result is sealed with `result_hash`. |
| Replay | `RecordingProvider` writes a `psyfi.bench.provider_receipt.v1`; `ReplayProvider` replays by request key. Class `replay`. |

### Statistics

All in `psyfi_bench/stats.py`, applied to the per-repeat `wall_ms` and `cpu_ms`, frame times, and latencies.

- Percentiles use linear interpolation (`numpy.percentile`): p50, p90, p95, p99.
- `std` is the sample standard deviation (ddof 1). `cv = std / mean` when mean is positive and n is at least 2. `mad` is the unscaled median absolute deviation.
- Confidence intervals are percentile bootstraps of the mean and of the median at 95 percent, `bootstrap_resamples` (default 2000) resamples, seeded by `bootstrap_seed`. Fewer than two samples give no interval.
- Frame metrics: `fps_avg = 1000 / mean(frame_ms)`; `fps_1pct_low = 1000 / p99(frame_ms)`; pacing jitter is the sample standard deviation of successive frame-time differences; a stutter is a frame longer than twice the median; `stutter_ratio` is stutters over frames.
- Drift: least-squares slope of frame time against frame index, reported as ms per 1000 frames with r squared, plus the ratio of the mean of the last quartile to the mean of the first quartile. Needs at least 8 samples.
- Scaling exponent: least squares on log(time) against log(size), with r squared and n.
- Budget rule for a WebGPU stage (copied from `ultraFpsMatrix.ts`): `fps_avg >= target_fps`, `fps_1pct_low >= 0.9 * target_fps`, `p95 <= 1.15 * target_ms`. Targets default to 8.3 ms ultra, 16.7 ms high and balanced, 33 ms battery and are versioned in the manifest params.

### Determinism

- `exact_sha256`: SHA-256 of dtype, shape and raw bytes. Identical across repeats on one machine proves bitwise reproducibility there.
- `quantized_sha256`: SHA-256 after rounding to `tolerances.quantization` (1e-4 for field-compute). Identical across machines is the cross-platform reproducibility reference (hypothesis H2). A mismatch is a finding, not an error to hide.
- NaN and Inf counts are recorded per stage.
- Accelerator ports are validated against the NumPy pipeline on the same seeded initial field: `pipeline_max_abs_error <= tolerances.accelerator_atol`, else the stage is `failed` and its timings do not count.

### Identification

`EnvironmentRecord` records platform, CPU brand and cores, memory, GPUs (nvidia-smi, rocm-smi, system_profiler), Python, NumPy, SciPy, BLAS, torch devices, git commit. Browser captures add user agent, adapter description, device pixel ratio, viewport, and whether timestamp queries answered. Anything not collected appears in `unavailable` with a reason (power, thermal, GPU memory on Apple unified memory). Nothing is estimated.

## 2. Comparability rules

1. Compare results only with identical `manifest_hash`. The scorecard marks mixed hashes as not comparable and refuses a ranking.
2. Never compare pixel fidelity across devices. `fidelity_vs_ultra` is computed against the same capture's Ultra stage for the same snapshot key.
3. `measured`, `synthetic` and `replay` results are never ranked together. Synthetic captures and baseline providers are calibration, not evidence.
4. Report `hardware_class`. An integrated-class result is not evidence for a discrete tier target.
5. Model comparisons require the same `prompt_revision` (1), `image_size`, `temperature` (0.0), `max_tokens` (64) and corpus lock.
6. Strict JSON parsing decides `parse_ok`. Lenient recovery (fences, percent strings, case) is counted in `recoverable_format_violations` and its FDE sits under `lenient`; it never enters the headline.
7. Latency for remote providers includes the network; `locality` says local or remote.

## 3. Field Displacement Error

Let an item have substance `s`, oracle mode `m_o`, oracle intensity `i_o`, seed, `phase_t` (0.4) and tier (`balanced`).

- `P_o = map_parameters(substance=s, mode=m_o, intensity=i_o, seed, phase_t, quality_tier).parameters`
- A model reading `(m_m, i_m)` reconstructs `P_m` with the same call.
- `FDE = round(sum_k |P_o[k] - P_m[k]|, 4)` over the union of parameter keys; a key missing on one side counts as 0.
- Mode steps: for each other mode `j`, `S_j = L1(P_o, map_parameters(... mode=j, intensity=i_o))`. `mode_step_min = min_j S_j` is the ruler.
- `fde_normalized = FDE / mode_step_min` (None if the ruler is 0). `within_mode_step = FDE <= mode_step_min`.
- Decomposition: `fde_mode_only` uses `(m_m, i_o)`; `fde_intensity_only` uses `(m_o, i_m)`.
- Diagnostics: `mode_match`, `intensity_abs_error`.
- Discriminability: Spearman rho between pairwise `L1(P_o_a, P_o_b)` and pairwise `L1(P_m_a, P_m_b)` over all item pairs, sampled to at most 600 pairs with a seeded generator. The oracle gives rho 1; a reading that ignores the input gives rho near 0.
- Invariance: for a subset of items rendered under perturbations (noise 0.02, brightness plus or minus 2 percent, horizontal flip), the mean L1 between the reconstructed field of the base image and of the perturbed image. `invariance_to_discriminability_ratio = mean reading distance across distinct fields / mean reading distance under perturbation`; undefined (None) when the denominator is 0, and both inputs are reported.
- Cross-modal agreement: share of items where the image reading and the structured reading agree on mode, plus mean absolute intensity delta and the mean reading distance between them.
- Repeatability: for a subset asked `repeats` times, `exact_agreement_rate` (identical mode and intensity within 1e-9) and `mode_agreement_rate`, plus the mean intensity standard deviation.
- Cost: `cost_per_valid_result = total cost / parsed rows`, computed only when `pricing` (input and output per million tokens) is supplied through the manifest or `--pricing`. Otherwise null.

The baselines fix the scale: oracle FDE 0; constant and random at chance mode accuracy; `heuristic` is the instrument's own photometric recommendation.

## 4. Scoring specification

### Dimensions (from `psyfi_bench/scoring.py`)

field_compute:

| Dimension | Unit | Better |
| --- | --- | --- |
| throughput_cell_steps_per_s | cell-steps/s | higher |
| wall_ms_largest_grid_p50 (with CI) | ms | lower |
| wall_ms_largest_grid_cv | ratio | lower |
| scaling_deviation_from_linear | abs(k minus 1) | lower |
| peak_tracemalloc_bytes_per_cell | bytes/cell | lower |
| bitwise_determinism | 0 or 1 | higher |
| reference_lock_matches | count | higher |
| sustained_drift_ratio (sustained kind) | ratio | lower |

render, soft class: `<tier>.raster_ms_per_megapixel` (ms/MP, lower), `ts_parity_matched` (count, higher).

render, webgpu class, per tier: `fps_avg` (higher), `fps_1pct_low` (higher), `frame_ms_p95` (lower), `budget_ok` (0 or 1, higher), `ssim_vs_ultra` (higher); plus `sustained_drift_ms_per_1000_frames` (lower).

interpretation: `fde_mean` (field L1, lower, with CI), `fde_normalized_mean` (mode steps, lower), `within_mode_step_rate` (higher), `mode_accuracy` (higher), `intensity_mae` (lower), `parse_rate` (higher), `schema_violation_rate` (lower), `discriminability_rho` (higher), `structured_fde_mean` (lower), `cross_modal_mode_agreement` (higher), `invariance_to_discriminability_ratio` (higher), `perturbation_mode_flip_rate` (lower), `repeat_exact_agreement` (higher), `latency_ms_p50` (lower), `cost_per_valid_result` (lower).

fieldloop: `e2e_ms_median` (lower), `fde_median` (lower), `within_mode_step_rate` (higher), `loop_closed_rate` (higher), `interpret_share_of_e2e` (lower).

A dimension with no value carries `missing_reason` instead of a number.

### Primary dimension and gate

| Family | Primary | Gate (must be at least 0.9) |
| --- | --- | --- |
| field_compute | throughput_cell_steps_per_s (higher) | bitwise_determinism |
| render | ultra.fps_1pct_low (higher) | ultra.budget_ok |
| interpretation | fde_mean (lower) | parse_rate |
| fieldloop | e2e_ms_median (lower) | loop_closed_rate |

Recommendations rank subjects by the primary dimension, gated subjects first, and name the unit. A non-comparable card yields no ranking.

### Composites

| Name | Formula | Family |
| --- | --- | --- |
| valid_in_step_per_second | within_mode_step_rate times parse_rate divided by (latency_ms_p50 / 1000) | interpretation |
| fidelity_per_currency | max(0, 1 minus fde_normalized_mean) divided by cost_per_valid_result | interpretation |
| `<tier>`.ssim_per_ms_p95 | ssim_vs_ultra divided by frame_ms_p95, same device only | render (webgpu) |
| closed_loops_in_step_per_second | within_mode_step_rate times loop_closed_rate divided by (e2e_ms_median / 1000) | fieldloop |

Weights: none. Normalization: none; each composite is a ratio of raw units. Sensitivity: each input is moved by plus and minus 10 percent and the composite recomputed (`sensitivity.per_input`). Missing data: the value is null and the spec states the rule; nothing is imputed. Each composite names its valid comparison scope.

### Validity gates

`validity.comparable` is false when families, manifest hashes or measurement classes are mixed. Partial or failed results are flagged but still shown. The rule text is embedded in every card.

### No universal score

There is no single number across families. Compute throughput, frame pacing and model field fidelity have different units, different error structures and different hardware dependencies. A weighted sum would hide the weights' influence and invite ranking on noise. The scorecard answers specific questions (best throughput with determinism, best 1 percent low under budget, lowest FDE with a usable parse rate, fastest closed loop) and publishes every formula it uses.

## 5. What the numbers do not mean

- Nothing here measures consciousness or subjective experience. Fields, snapshots and readings are modeled representations.
- The soft raster is a deterministic CPU picture of the scene description, bit-identical to the TypeScript soft-present goldens. It is not a WebGPU frame and ignores post-processing flags; ultra, high and balanced raster identically.
- A synthetic capture or a baseline provider result is calibration. It is never hardware or model evidence.
- Results from this machine (Apple M5, integrated class) describe this machine. They are not Ultra tier evidence and are never merged into the Ultra fps fixtures.
- `timing_cv_max` and the budget rule are reporting aids. A high CV or a missed budget is reported, not turned into a failed build.
- Frame times in a capture are requestAnimationFrame spacing, capped by the display refresh rate; GPU timestamps, when present, are quantized by Chrome unless developer features are enabled.
