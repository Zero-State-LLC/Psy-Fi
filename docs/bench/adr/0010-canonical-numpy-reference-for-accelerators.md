# ADR 0010: NumPy is the canonical reference for accelerator ports

Status: accepted, 2026-11-07.

## Problem

The mission allows GPU compute ports of selected simulation steps, but simulation truth must stay in Python and CPU results must never be called GPU results.

## Decision

`psyfi_bench/compute/backends.py` defines `NumpyBackend` (calls the `psyfi_core` engines unchanged, `canonical = True`) and an optional `TorchBackend` (symmetric Kuramoto and divisive normalization in float32 on CUDA, MPS or CPU). Any non-canonical backend is validated on the same seeded initial field against NumPy; a stage whose `pipeline_max_abs_error` exceeds `tolerances.accelerator_atol` is marked failed and its timings do not count. Timings of the port include host to device transfer and are labeled so.

## Alternatives

- Treat the port as a second authority: breaks the project invariant.
- No accelerator path: leaves the "GPU compute" question unanswered.

## Consequences

Torch is optional; without it the `field-compute.accelerator` manifest skips with an explicit reason. A browser WGSL port would follow the same validation rule (not implemented).
