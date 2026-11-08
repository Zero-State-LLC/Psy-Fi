# ADR 0011: Energy per frame comes from a host power trace aligned to each browser stage

Status: accepted, 2026-11-08 (operator).

## Problem

Issue #50 asks for energy per frame on WebGPU captures scored on the same host. Field-compute stages get power from a sampler thread around their measured repeats (`psyfi_bench/power.py`). A WebGPU capture runs in a browser outside the Python process, and it is scored later by `psyfi-bench ingest`. At that point there is no sampling window to integrate. No web API exposes GPU power, so the browser cannot measure it. Capture stages record `duration_ms` but no wall-clock start or end, so there is also nothing to line a host trace up against.

## Decision

1. **The browser records each stage's measured window on the wall clock.** `CaptureStage` gains an optional `window_epoch_ms: [start, end]`. It runs from the first to the last measured frame, warm-up excluded, as `performance.timeOrigin + performance.now()`. The field is additive; older captures stay valid.
2. **The host records a power trace while the bench page runs.** `psyfi-bench power-trace --out trace.json` runs the existing `nvidia-smi` stream sampler until stopped: one `nvidia-smi -lms 100` process reading `power.draw.instant` where the driver has it. `power.draw` is a 1 s average on Ampere and newer and the board sensor updates about every 100 ms, so 100 ms is the useful interval (Yang et al., arXiv:2312.02741). It writes samples timestamped on the wall clock (`time.time_ns`), not `perf_counter`, so they share a clock with the browser on the same machine. The trace also carries the `nvidia-smi` query, the GPU name and the same `hostname_hash` that `EnvironmentRecord` uses (never the hostname).
3. **Ingest pairs them per stage.** `psyfi-bench ingest capture.json --power-trace trace.json` applies the field-compute rule to each stage that has a window:
   - keep only the samples inside the window that have a power reading;
   - integrate them with the trapezoid rule;
   - report per-frame energy only when those samples span at least 90% of the window.

   The result is `StageRecord.power` with `work_unit: "frame"` and `work_units` set to the number of measured frames. `build_power_record(..., window_start_s=...)` already does this once the trace timestamps and window are converted to seconds on one clock.
4. **Refuse rather than guess.** No power is written, and the stage notes say why, when any of these hold:
   - the trace's `hostname_hash` differs from the scoring host's;
   - the trace's GPU vendor is not the capture adapter's vendor;
   - a stage has no window;
   - the trace does not reach the window.

   Without `--power-trace`, nothing changes: `environment.unavailable.power` keeps its reason.

## Alternatives

- **Power from the browser:** no API exists.
- **Python drives the browser and samples around each stage** (for example with Playwright): it aligns cleanly, but it adds a browser-automation dependency to `psyfi_bench`, and ADR 0006 makes the runner a page that a person opens and runs. Rejected for now.
- **One power window for the whole capture, divided by all frames:** it mixes loading, warm-up, renderer remounts and different tiers into one number, so it is not per-stage evidence.
- **Board TDP times frame time:** an estimate. Rejected by the "never estimate" rule.

## Consequences

- Per-frame energy is board power while the stage rendered. That includes idle draw, the compositor and anything else on the GPU, and the record's `derivation` says so.
- It exists only on hosts with `nvidia-smi` and a GPU that reports power. Apple and AMD captures stay unavailable, with a reason, and so do vGPU slices, which do not expose board power.
- nvidia-smi's sensor sees only part of each update period (about 25% of runtime on A100 and H100, per arXiv:2312.02741), so per-frame energy needs a stage of at least 1 s, the same rule as field compute.
- Both schema changes are additive: the window on `CaptureStage` and a trace document. A capture without windows scores exactly as today.
- The operator runs two things at once, the trace command and the bench page. `docs/bench/README.md` would gain a three-line recipe.

## Testing decisions

The tests use a synthetic capture with windows and a synthetic trace, and never call `nvidia-smi`. They cover:
- a trace covering a stage, giving a per-frame value;
- a trace covering under 90% of the window, giving energy but no per-frame value;
- samples outside the window, which are dropped;
- a different `hostname_hash` or GPU vendor, giving no power and a reason;
- a stage without a window, giving no power;
- a capture with no `--power-trace`, which is unchanged.

## Decided questions

- The host match is strict: the trace's `hostname_hash` must equal the scoring host's. A matching GPU name is not enough.
- A trace is CLI only: the gated API ingest (`PSYFI_BENCH_INGEST=1`) does not accept one.

Implemented in `psyfi_bench/power_trace.py`, with sample times taken from nvidia-smi's own stamp converted to epoch seconds rather than `time.time_ns` at read time, so pipe delay stays out of them.
