# FieldLoop roadmap and board mapping

Date: 2026-11-07, updated 2026-11-08. Board: Zero-State-LLC project #7 (Psy-Fi). Project #16 is Noema; nothing goes there.

## Done on `main`

| Item | Evidence |
| --- | --- |
| `psyfi_bench` package: schemas, stats, determinism, timing, environment, store, registry, runner | `tests/bench/test_bench_core.py` |
| Family A field_compute with five manifests and locked references | `tests/bench/test_field_compute.py` |
| Family B render: Python soft raster bit-identical to TS goldens, webgpu capture scoring | `tests/bench/test_render_family.py` |
| Family C interpretation: corpus lock, FDE, baselines, providers, receipts | `tests/bench/test_interpretation_and_loop.py`, `test_providers.py` |
| Family D FieldLoop signature workload | `tests/bench/test_interpretation_and_loop.py` |
| Scorecards, reports, CLI, mounted `/api/bench`, exported contracts | `tests/bench/test_api_cli_scoring.py`, `test_bench_contracts.py` |
| Browser runner `/gpu/bench.html` | `src/bench/schedule.test.ts`; live capture pending hardware |
| Simulation orchestration moved to `psyfi_core.simulation` | parity check in `test_field_compute.py` |
| `nvidia-smi` power sampling and `score --format` (#59) | `tests/bench/test_power.py`, `test_score_format.py`; fake `nvidia-smi` only |
| WGSL Kuramoto kernel on the bench page (#60) | `tests/bench/test_webgpu_kernel.py`, `kuramotoKernel.test.ts`; validated live on an Apple GPU |
| `/bench` results and scorecard page (#65) | `tests/test_bench_page.py` |
| Energy per frame from a host power trace (#70, ADR 0011) | `tests/bench/test_power_trace.py`; fake `nvidia-smi` only |

## Shortest path to a first complete FieldLoop result on real hardware

The commands for step 1 are in [`DISCRETE_GPU_HANDOFF.md`](DISCRETE_GPU_HANDOFF.md).

1. A discrete-GPU desktop opens `/gpu/bench.html`, runs, downloads the capture; `psyfi-bench ingest` scores it (hardware task).
2. A person with an `nvidia/` vision model id and key runs `interpretation.fieldread.smoke --provider nvidia --record` and then the full corpus (provider task).
3. `psyfi-bench score` across the baseline results and the live result produces the first scorecard with validity gates.

## Backlog by ownership

### Autonomous backend (agent-ready)

- A `render.soft.scaling` manifest over sizes 64..1024 with raster ms per megapixel fits.
- Receipt-driven regression: a committed replay receipt from a baseline is not evidence, but a CI test could replay a recorded live receipt if a human commits one.

### Hardware-dependent (needs a machine)

Run these from [`DISCRETE_GPU_HANDOFF.md`](DISCRETE_GPU_HANDOFF.md).

- Discrete NVIDIA, AMD, Intel Arc and Apple Pro/Max captures from `/gpu/bench.html`.
- A first `power-trace` plus `ingest --power-trace` run on an NVIDIA host. The code is in ([ADR 0011](adr/0011-host-power-trace-for-browser-captures.md)) and tested only against a fake `nvidia-smi`.
- torch CUDA validation of `field-compute.accelerator` (MPS validated on this Mac when torch is installed).

### Provider-dependent (needs a key or a local server)

- Live runs of `interpretation.fieldread` on at least one local OpenAI-compatible VLM (vLLM, llama.cpp, Ollama) and one remote provider, with receipts recorded.
- Pricing tables per provider supplied at run time for `cost_per_valid_result`.

### Frontend integration (Daniel)

- A link to `/gpu/bench.html` from the GPU lab header, if wanted.

### Needs an accepted intent

- A run endpoint (today `run_enabled: false`).
- Committing any measured result or receipt as a fixture.
