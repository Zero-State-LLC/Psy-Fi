# ADR 0006: The browser GPU bench as an additive page

Status: accepted, 2026-11-07.

## Problem

Measuring the real present path needs the GPU package, which Daniel owns. The runner must not change the lab UI, its components or its behavior.

## Decision

A second Vite page, `packages/psyfi-gpu-renderer/bench.html`, with source under `src/bench/`. It reuses `PsyFiGPUCanvas` and `SceneRoot` unchanged by passing `BenchProbe` as children of the canvas. The only shared-file edit is one `rollupOptions.input` entry in `vite.config.ts`. The probe measures requestAnimationFrame spacing and `renderer.info`, sets `trackTimestamp` and calls `resolveTimestampsAsync` to read GPU time when the adapter exposes timestamp queries, and grabs a 128 px thumbnail by `drawImage` from the WebGPU canvas into a 2D canvas inside a microtask after the frame renders. Scheduling and payload assembly are pure functions with vitest coverage. Python scores the capture.

## Alternatives

- Add a bench mode to `App.tsx`: changes Daniel's component and the lab's behavior.
- A Playwright harness driving `/gpu/`: would still need hooks in the lab code.

## Consequences

The page is served at `/gpu/bench.html` by the existing static mount. Thumbnail readback and GPU timestamps are best effort and reported as unavailable when they fail. Live verification on a discrete GPU is still open.
