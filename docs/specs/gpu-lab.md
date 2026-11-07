# Spec: GPU Lab

Status: in review. Pull request #25 implements issue #22. This file stays the decision record. Do not rewrite the present path.
Seam: a `psyfi.scene_snapshot.v1` document in, the present pipeline out.

## Problem Statement

The legacy shell cannot host the heavier desktop picture without becoming the simulation. The operator still needs one optional WebGPU view that obeys the same field, the same safety limits, and an explicit fallback when the browser has no WebGPU.

## Solution

GPU Lab is a separate route. FastAPI serves the built package at `/gpu/` when the build output is present. The lab's only render input is a scene snapshot from the public API. Python does not render on the GPU. The present path is scene, ambient occlusion, reflections, bloom, depth of field, motion blur, chroma, temporal accumulate, grade, then a mandatory safety attenuator. Neutral collapses the heavy post. Missing WebGPU leaves the operator on the legacy shell. Product asset packs stay deferred. Fixture KTX2 is opt-in.

## User Stories

1. As an operator, I want `/gpu/` separate from `/`, so that the installable shell stays the compatibility path.
2. As an operator, I want the lab to open from the shell with substance, mode, intensity, seed, and tier in the query, so that I do not retype the run.
3. As an operator, I want the picture to follow the scene snapshot, so that the lab cannot invent a different field.
4. As an operator, I want a safety attenuator on every presented frame, so that a post effect cannot show a raw buffer.
5. As an operator, I want Neutral to collapse the post stack, so that the calm field stays calm in the lab.
6. As an operator, I want Ultra, desktop, and battery tiers, so that a laptop can drop cost.
7. As an operator, I want bloom, grade, exposure, temporal accumulate, ambient occlusion, screen-space reflections, fog, depth of field, motion blur, and chroma on the desktop tier, so that the lab matches the G3 decision.
8. As an operator, I want a frame readout of FPS, average, and p95 against the budget, so that I can see when the tier is too heavy.
9. As an operator, I want Draco and KTX2 decode available, so that a fixture asset can upload.
10. As an operator, I want fixture assets off unless I ask, so that the procedural scene stays the default.
11. As an operator, I want an unknown asset pack to leave the procedural scene alone, so that a bad id does not swap the picture.
12. As an operator, I want the lab omitted when the package was not built, so that a Python-only run still serves `/`.
13. As an operator, I want Firefox without WebGPU to stay on the legacy shell, so that the failure is explicit.
14. As a maintainer, I want scene-snapshot goldens for the canonical seeds, so that a mapping change is visible.
15. As a maintainer, I want soft-present pixel goldens, so that the present path has a fixture even before a GPU runner locks full stills.
16. As a maintainer, I want present resources disposed, so that leaving the lab does not leak GPU objects.

## Implementation Decisions

- The lab is a workspace package built with the JS toolchain. The image build runs that step and copies the output into the Python image.
- Serving is on by default and can be disabled. The mount exists only when `index.html` is in the build output.
- Present effects are the engine node's post graph, not the WGSL files under the shader tree. Those WGSL files are stubs except the safety-clamp sketch.
- The live safety pass is a peak luminance scale, then the attenuator uniform, then a small mix toward a dark floor. It runs even when attenuation is 1.
- The safety note component renders nothing. It documents the pass. The pass itself is in the present pipeline.
- Simulated Ultra QA is a synthetic frame-time matrix. Hardware capture is optional and does not gate the freeze.
- Full R3F still hashes on a GPU CI runner are optional. The API for capture exists.

## Testing Decisions

A good test builds a snapshot and asserts tier, safety flags, asset refs, or a golden hash. A GPU test that needs a real device must say so and must not be replaced by a document that claims the device was measured.

Prior art: scene-snapshot tests, G4 golden tests, pixel-golden fixtures, asset-pack tests, and the GPU package tests for decode, present dispose, and temporal accumulate.

## Out of Scope

- Replacing `/` with the lab.
- CUDA workers inside the API container.
- Shipping a product asset pack.
- Native iOS.
- Treating simulated frame times as measured desktop Ultra numbers.

## Further Notes

`docs/FRONTEND_BOUNDARY.md` still says the Ultra post stack is only scaffolded. That sentence is stale against this spec. The WGSL bloom, SSAO, SSR, and material files are still stubs. The running present path is the TypeScript post graph.
