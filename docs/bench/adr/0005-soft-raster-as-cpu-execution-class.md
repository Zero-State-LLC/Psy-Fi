# ADR 0005: The soft raster as the CPU execution class of rendering

Status: accepted, 2026-11-07.

## Problem

Headless CI has no WebGPU. The interpretation and FieldLoop families need deterministic images from scene snapshots without a browser.

## Decision

`psyfi_bench/render/soft_raster.py` is a Python port of `softPresent.ts`: same primitives, order and rounding, vectorized per primitive. It is bit-identical to the three TypeScript G4 pixel goldens (same SHA-256 and histograms), and the render family reports `cross_language_parity`. It is the `soft` execution class and the FieldLoop CPU render stage.

## Alternatives

- Call Node to run the TypeScript raster: adds a runtime dependency to the Python path.
- A new, richer Python renderer: would not be parity-testable against anything.

## Consequences

The soft raster ignores post-processing flags, so ultra, high and balanced raster identically; tier fidelity is meaningful only in the `webgpu` class. The raster is not a WebGPU frame and is labeled as such.
