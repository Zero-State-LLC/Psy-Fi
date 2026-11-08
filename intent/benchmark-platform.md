# Intent — FieldLoop benchmark platform

Author: Fable (delegated by Aaron)
Date: 2026-11-07
Status: accepted (delegated by Aaron in the 2026-11-07 benchmark mission brief; frontend stays with Daniel)
Product: PsyFi (`Zero-State-LLC/Psy-Fi`)

This file is a proto-spec. It comes **before** specify / plan.
The spec is [`docs/specs/benchmark-platform.md`](../docs/specs/benchmark-platform.md).

## Problem

PsyFi has a deterministic simulation, an immutable ParameterField, a scene snapshot contract, a WebGPU present path, and one vision-model call, but no way to measure how a GPU, a model, or the pipeline behaves on these workloads. The only performance evidence in the tree is a synthetic Ultra fps matrix whose measured fixture is empty, a profiler that reports rAF spacing as "cpuMs", and tests that assert prose on a readiness board. The vision bench scores one model on four images without baselines.

[verified: `packages/psyfi-gpu-renderer/fixtures/qa/ultra_fps_matrix.measured.v1.json` has `"samples": []`; `src/Profiling/FrameProfiler.ts`; `tests/test_production_readiness.py`; `docs/specs/vision-bench.md`]

## Outcome

Observable done (a stranger can check this without reading the chat):

- `python3 -m psyfi_bench list` prints versioned workload manifests for four families: field_compute, render, interpretation, fieldloop.
- `python3 -m psyfi_bench run field-compute.scaling` runs headlessly on a CPU-only machine and stores a sealed `psyfi.bench.result.v1` document whose output digests match the locked references.
- `python3 -m psyfi_bench run interpretation.fieldread.smoke --provider oracle` scores Field Displacement Error 0 and `--provider heuristic` scores chance-level mode accuracy; both say `measurement_class: synthetic`.
- `GET /api/bench/v1/capabilities` answers on the running API; `GET /openapi.json` on the main app lists no `/api/bench` path and the frozen `/api/v1` tests stay green.
- `/gpu/bench.html` runs the WebGPU stages and produces a `psyfi.bench.gpu_capture.v1` download that `psyfi-bench ingest` scores.
- `python3 -m pytest tests/ -q` and `npm run gpu:test` pass.
- No file under `psyfi_api/static`, `psyfi_api/templates`, or an existing `packages/psyfi-gpu-renderer/src` component changed.

## Users / systems

- Users: an operator comparing GPUs or models on PsyFi workloads; a maintainer checking determinism; Daniel integrating results into the shell later.
- Systems: `psyfi_core` (authority), the new `psyfi_bench` package, `psyfi_api.main` (one mount line), `packages/psyfi-gpu-renderer` (one additive page), org project #7.

## Constraints

Product-true locks (do not reopen in implement):

- Simulation truth stays in Python. Accelerator ports are validated against the NumPy authority and never replace it.
- The `/api/v1` freeze id, `api_version`, FastAPI `version`, engine default, image-reading sentence and `reasoning_effort` do not change.
- No login, API key, rate limit or AI Gateway. No model id pinned in source. No committed vision-bench receipt.
- Synthetic, replayed and baseline results are labelled and are never hardware or model evidence. Results from this integrated-class Mac are not Ultra evidence; issue #10 stays Backlog.
- The vision bench stays as merged. FieldLoop generalizes its field-displacement idea; it does not share its corpus, score or pass rule.
- Daniel's frontend is not modified; new UI is limited to the additive bench page.

Non-goals:

- A universal composite score across families.
- Running benchmarks from the public host.
- Measuring consciousness or subjective experience.
- Native iOS, Azure, Render.

## Open questions

- Whether a run endpoint should exist behind an accepted intent (today: CLI only).
- Whether a WGSL Kuramoto compute kernel in the browser is worth validating against the Python reference (designed, not implemented). Answered 2026-11-08: yes; pull request #60 implements it and validated it on an Apple GPU (max abs error 7.2e-7, tolerance 1e-3).
- Whether Daniel wants results in the shell, the GPU lab, or a new page (integration package ready; UI is his). Answered 2026-11-08: a shell page at `/bench`, for the local operator first ([`intent/bench-results-page.md`](bench-results-page.md), pull request #65).

## Verified / assumed

| Claim | Label |
|---|---|
| HANDOFF.md (PR #42) reserved a GPU frame-time bench and hardware detection for a later human-accepted intent | `[verified: PR #42 diff, HANDOFF.md sections 3 and 4]` |
| Aaron's brief authorizes that work and autonomous implementation | `[verified: mission brief sections 3, 12, 16]` |
| The frozen OpenAPI tests compare the full live path set, so additive /api/v1 routes need a freeze resync | `[verified: tests/test_frozen_contracts.py, tests/test_openapi_contract.py]` |
| A mounted sub-application does not appear in the parent OpenAPI document | `[verified: tests/bench/test_api_cli_scoring.py]` |
| The Python soft raster reproduces the TypeScript soft-present goldens bit for bit | `[verified: tests/bench/test_render_family.py]` |
| This machine is an Apple M5 with an integrated 8-core GPU | `[verified: psyfi_bench.environment on 2026-11-07]` |

## Author / date

Author and date are in the header.

## Next

Spec: `docs/specs/benchmark-platform.md`. Implementation: `psyfi_bench/`. Board: project #7.
