# FieldLoop — the Psy-Fi benchmark

Status: implemented on `bench/fieldloop-foundation`, 2026-11-07. Research and visualization only. The benchmark measures computation, rendering and model interpretation of modeled representations. It does not measure consciousness or subjective experience. Not medical advice.

FieldLoop closes a loop the instrument already contains:

```text
seed ──► ABX simulation ──► ParameterField + scene snapshot ──► render ──► model reading ──► reconstructed field
  │          (A)                      (A, D)                   (B)          (C)                 (C, D)
  └──────────────────────────── Field Displacement Error = L1(generating field, reconstructed field) ───┘
```

| Family | Manifest ids | What it measures | Execution |
| --- | --- | --- | --- |
| A `field_compute` | `field-compute.scaling`, `.steps`, `.sustained`, `.presets`, `.accelerator` | wall/CPU ms, peak memory, cell-steps/s, scaling exponent, drift, exact + quantized digests, accelerator parity | Python (CPU); torch optional |
| B `render` | `render.soft.g4` (CPU), `render.webgpu.tiers` (browser) | raster ms per megapixel; frame p50/p95/p99, 1% low, pacing, drift, GPU timestamps, same-device tier fidelity | Python; `/gpu/bench.html` + ingest |
| C `interpretation` | `interpretation.fieldread`, `.smoke` | FDE, mode accuracy, intensity MAE, schema violations, discriminability, invariance, cross-modal agreement, repeatability, latency, tokens, cost | Python + provider |
| D `fieldloop` | `fieldloop.signature` | per-stage and end-to-end time, loop closure, FDE | Python + provider |

## Start here

| Doc | Purpose |
| --- | --- |
| [`DISCOVERY.md`](DISCOVERY.md) | Phase 1: architecture map, capability inventory, debt, ownership boundaries |
| [`RESEARCH.md`](RESEARCH.md) | Phase 2: benchmark comparison, differentiation, hypotheses H1–H6, threats to validity |
| [`../specs/benchmark-platform.md`](../specs/benchmark-platform.md) | Decision record (Pocock shape) |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Phase 3: domain model, workflows, interfaces, data, security |
| [`METHODOLOGY.md`](METHODOLOGY.md) | Protocol, statistics, FDE definition, scoring specification |
| [`INTEGRATION.md`](INTEGRATION.md) | Phase 7: frontend integration package for Daniel |
| [`ROADMAP.md`](ROADMAP.md) | Prioritized tasks and board mapping |
| [`adr/`](adr/) | Architecture decision records |

## Run it

```bash
pip install -e ".[dev]"            # torch is optional: pip install torch
python3 -m psyfi_bench list
python3 -m psyfi_bench run field-compute.scaling
python3 -m psyfi_bench run render.soft.g4
python3 -m psyfi_bench run interpretation.fieldread.smoke --provider oracle
python3 -m psyfi_bench run interpretation.fieldread.smoke --provider heuristic
python3 -m psyfi_bench run fieldloop.signature --provider heuristic
scripts/run_bench_suite.sh         # everything CPU-only plus the baselines
```

Live model providers (keys stay in the environment; one attempt, no retry):

```bash
python3 -m psyfi_bench run interpretation.fieldread --provider "openai:http://localhost:8080#qwen2.5-vl" --record receipt.json
NVIDIA_VISION_MODEL=nvidia/<id> NVIDIA_API_KEY=... python3 -m psyfi_bench run interpretation.fieldread --provider nvidia --limit 16
ANTHROPIC_API_KEY=... python3 -m psyfi_bench run interpretation.fieldread --provider anthropic:<model> --pricing '{"input_per_million": 3, "output_per_million": 15}'
python3 -m psyfi_bench run interpretation.fieldread --provider replay:receipt.json   # offline re-score, labelled replay
```

Browser GPU bench: start the API, open `http://localhost:8000/gpu/bench.html` in Chrome or Edge, press Run, download the capture, then:

```bash
python3 -m psyfi_bench ingest ~/Downloads/psyfi-fieldloop-gpu-capture-*.json
python3 -m psyfi_bench score bench_results/render/*.json --labels a,b
python3 -m psyfi_bench score bench_results/render/*.json --labels a,b --format csv   # markdown (default), csv, json
```

Results are sealed JSON under `bench_results/` (gitignored). `psyfi-bench validate <file>` checks the seal. `psyfi-bench export-schemas` refreshes the integration package.

## Evidence rules

- `measurement_class` is `measured`, `synthetic` or `replay` on every result and stage. Baselines are synthetic. Receipts replay. Only live compute, live providers and browser captures are measured.
- `environment.hardware_class` is `discrete`, `integrated`, `cpu_only` or `unknown`. A result from an integrated Apple GPU is never Ultra evidence; the Ultra fps fixtures and issue #10 are untouched by this subsystem.
- Compare only identical `manifest_hash`. A `--param` override changes the hash on purpose.
- Pixel fidelity is compared within one device against its own Ultra frame. Never across devices.
- Missing telemetry (power, thermal, GPU memory) is listed under `environment.unavailable` with a reason. Nothing is estimated. When `nvidia-smi` is present, `field_compute` stages also record sampled power and energy per cell-step under `stage.power`; the sampled energy is board power, whichever backend ran.
- The soft raster is a deterministic CPU picture of the scene snapshot and is bit-identical to the TypeScript soft-present goldens. It is not a WebGPU frame.

## Prior art inside the repo

- `docs/specs/vision-bench.md`: Daniel's merged vision bench. Its `field_displacement` idea is the seed of FDE. FieldLoop does not share its corpus, score or pass rule and does not change it.
- `packages/psyfi-gpu-renderer/src/qa/`: the Ultra fps capture and synthetic matrix. FieldLoop reuses its tier budget rule and leaves its fixtures alone.
