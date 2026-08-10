# Deterministic Experiment Engine

E0 adds headless orchestration and measurement around the existing Python simulation. It does not create another simulation authority, change `/api/v1`, invoke rendering, or expand the rejected N0 native promotion.

## Ownership boundary

- Python simulation code owns state evolution and domain semantics.
- `psyfi_core.experiments` owns deterministic sweep expansion, measurement, receipts, hashing, replay, and export.
- The observable registry exposes only established scalar outputs: `coherence`, `valence`, and `roughness`, each at version `1` and recorded to six decimal places so supported NumPy/SciPy builds do not create false drift from insignificant reduction noise.
- TypeScript and WGSL remain presentation and rendering computation authorities.

## Identity and hashing

Specs use `psyfi.experiment.v1`. Expansion is seed-major, then parameter names in lexical order, then values in declared order. Run IDs derive from the SHA-256 input hash. Canonical hashing sorts keys, encodes UTF-8 JSON, tags finite floats using their 17-digit representation, and excludes timestamps, UUIDs, runtime duration, and platform metadata.

`spec_hash` covers the normalized spec. `input_hash` covers schema and experiment identity, seed, resolved parameters, steps, engine version, and observable versions. `output_hash` covers run ID, measured observables, engine and observable versions, and canonical provenance.

## Limits and failures

E0 permits at most 64 unique uint32 seeds, eight parameter dimensions, 32 values per dimension, 1,024 total runs, and 1,000 simulation steps. Width and height retain the existing 8 through 512 bounds. Unknown parameters and observables fail validation. Execution is fail-fast. Cancellation is checked at run boundaries and by the Python simulation. Replay returns `PASS`, `DRIFT`, `INVALID_RECEIPT`, or `UNSUPPORTED_VERSION` and never normalizes drift.

The exported JSON Schema encodes identifier, collection, seed, observable, parameter-name, and metadata bounds. Parameter-specific numeric bounds and the Cartesian total-run limit are enforced by `ExperimentSpec` because those cross-field rules are not represented as standalone JSON Schema expressions.

## Run and replay

```bash
python -m psyfi_core.experiments run experiments/e0_smoke.json --output experiments/output
python -m psyfi_core.experiments replay experiments/output/e0-smoke-v1/experiment.json experiments/output/e0-smoke-v1/runs.jsonl --run-id <run-id>
```

The export contains `experiment.json`, `manifest.json`, `runs.jsonl`, `summary.json`, and `provenance.json`. Environment metadata is recorded separately and does not affect output hashes.

## Non-claims and roadmap

E0 provides reproducible datasets, not novel consciousness metrics, causal claims, renderer correctness, or distributed execution. Later phases are E1 observable expansion, E2 regime and attractor analysis, E3 cross-experiment comparison, E4 scalable sweeps, and E5 external dataset interchange.
