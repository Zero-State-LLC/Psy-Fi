---
title: "Post effects that sample their input need a texture, or the GPU lab throws every frame"
author: Daniel
date: 2026-11-08
branch: fix/gpu-lab-tier-switch
id: l-d534c7aa
scope: repo
status: active
src: agent
touches:
  - ".github/PULL_REQUEST_TEMPLATE.md"
  - packages/psyfi-gpu-renderer/src/PostProcessing/PresentPipeline.tsx
---

## Decided
SSR and motion blur in the present graph get `convertToTexture(node)`, the way three's own `dof`, `afterImage` and `rgbShift` wrap their inputs. The graph is built by `buildPresentGraph`, outside the React effect, so a test can check what each effect receives.

## Tried and ruled out
- Blaming the dispose order on a tier switch (the issue's first guess). Disposal is fine; the new graph fails its shader build.
- Remounting the canvas per stage (what the bench runner does). The failure is in the graph itself, so a fresh renderer does not avoid it.

## Watch out
- In three 0.175, `ssr()` and `motionBlur()` call `.sample()` on their colour input, and only `TextureNode` has `sample`. An operator node (the AO product) or the DoF node is not a texture, so the build throws `colorNode.sample` / `inputNode.sample is not a function`.
- After a failed build, three's `Nodes.delete` reads `nodeBuilderState.usedTimes` without a guard, throws inside `onDispose`, never removes the render object from its chain map, and repeats on every frame. The `usedTimes` TypeError in #55 is that symptom, not the cause; look for the first error after the switch.
- Screenshots of the WebGPU canvas in the desktop app's browser are often black even when the lab renders (production does the same). Count `window` error events instead.

In the code: packages/psyfi-gpu-renderer/src/PostProcessing/presentGraph.ts, presentGraph.test.ts, PresentPipeline.tsx.
