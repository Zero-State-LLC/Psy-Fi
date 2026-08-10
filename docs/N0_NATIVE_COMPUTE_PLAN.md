# N0 Native Computational Kernel Engineering Plan

Status: planned, evidence-gated  
Scope: exactly one deterministic `psyfi_core` numerical kernel  
Technology: stable Rust, PyO3, maturin  
Decision rule: native execution is optional and must earn promotion

## Mission and authority boundary

N0 establishes a small native-compute seam without changing Psy-Fi's observable simulation behavior or ownership model.

```text
Python      domain and simulation authority
Rust        pure deterministic computational substrate
TypeScript  presentation and browser application client
WGSL        rendering computation
```

The existing Python implementation remains the canonical semantic reference. Rust must not own FastAPI routes, Pydantic models, phenomenology, substance definitions, orchestration, API semantics, visualization semantics, `SafetyPass`, `scene_snapshot`, MIDI, telemetry, PWA behavior, R3F, WebGPU, or WGSL shaders. N0 does not compile Rust to WASM and does not create a second browser-side simulation authority.

## Completion contract

N0 is complete only when:

1. A single Rust crate named `psyfi-native` builds successfully and imports in Python through PyO3/maturin.
2. Exactly one justified deterministic kernel is implemented in Rust while its existing Python implementation remains available as the reference.
3. Explicit parity, error, and repeated-execution determinism tests pass.
4. Existing deterministic tests, goldens, `/api/v1`, OpenAPI, and scene-snapshot contracts remain unchanged.
5. A reproducible end-to-end benchmark compares Python reference and Rust native execution at small, representative, and large/batch sizes.
6. The Python adapter has explicit `reference`, `native`, and `auto` behavior. `native` fails clearly when unavailable; `auto` uses Rust only after promotion and otherwise preserves reference semantics.
7. CI builds and tests the Rust/Python bridge without weakening existing Python, README, frontend, or GPU gates.
8. Security, migration, deployment, user-impact, and adversarial findings are recorded with command evidence.
9. No unrelated refactors or compiled native binaries are committed.

If no candidate is justified, record:

```text
N0_RESULT = NOT_COMPUTABLE / NO_JUSTIFIED_NATIVE_KERNEL
```

This is an acceptable N0 outcome. Do not manufacture a Rust use case.

## Stage 1: change-map

Inspect before modifying. At minimum read `CONTEXT.md` when present, `README.md`, `PROJECT_INDEX.md`, `PLANS.md`, this continuation plan, the web/frontend architecture documents, the frozen API contract, `pyproject.toml`, `package.json`, CI, and the deterministic tests and fixtures.

Inventory candidate functions with this table:

| candidate | current module | input types | output types | side effects | deterministic | call frequency | FFI complexity | expected opportunity | migration risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Prefer pure, frequently repeated numerical functions with primitive scalar/array inputs, primitive/array outputs, no I/O, no global state, and no Pydantic or phenomenological coupling. Reject candidates where Python object semantics, NumPy/SciPy performance, conversion cost, or domain meaning makes FFI inappropriate. Select exactly one kernel.

## Stage 2: running baseline

Before edits, run and record:

```bash
python -m pytest tests/ -q
python -m pytest tests/test_openapi_contract.py -q
npm ci
npm test
npm run gpu:test
npm run gpu:typecheck
npm run gpu:build
```

Also run targeted determinism and golden tests discovered during the change-map. Do not change unrelated baseline failures.

## Stage 3: minimal implementation design

Preferred structure:

```text
native/psyfi-native/
  Cargo.toml
  pyproject.toml
  README.md
  src/lib.rs
  src/error.rs
  src/<selected_kernel>.rs
psyfi_core/native/
  __init__.py
  backend.py
```

Use one crate only. Do not create field-sweep, replay, hash, or WASM crates in N0. Avoid unnecessary dependencies and unsafe Rust. Any unavoidable unsafe block is an architectural exception and must document the invariant it protects.

The internal Python adapter should expose explicit backend selection without making public callers understand the implementation:

| mode | required behavior |
| --- | --- |
| `reference` | Always execute the canonical Python implementation. |
| `native` | Require the extension and fail clearly if it is unavailable or rejects the input. |
| `auto` | Use native only after the promotion gate; otherwise execute the reference implementation. |

Never catch a Rust load/runtime error and substitute behavior with different semantics. Map validation and invariant failures to explicit Python exceptions. Rust must reject malformed dimensions, invalid ranges, non-finite values, overflow, unsupported state, huge allocation requests, and internal invariant violations without panicking across FFI.

## Stage 4: parity and determinism

Tests must compare the existing Python function directly against the Rust function, never adapter against adapter. Cover:

- representative fixed fixtures;
- minimum and maximum valid values;
- zero and negative values where valid;
- deterministic seeds where applicable;
- many randomized valid inputs generated from a fixed test seed;
- NaN, infinity, malformed dimensions, overflow, and unsupported states;
- multiple identical Rust executions for the same input.

Use exact equality for integer/discrete output. For floating point, define and justify the tightest tolerance compatible with current Psy-Fi semantics. Do not default to a loose tolerance such as `1e-3`. Investigate ordering or architecture-dependent drift rather than regenerating goldens.

## Stage 5: benchmark and promotion gate

Add a reproducible script, preferably `scripts/benchmark_native_kernel.py`. Warm both implementations and report median end-to-end Python call time, input size, iteration count, environment, and speedup for small, representative, and large/batch workloads. Include array conversion/copy overhead experienced by real callers.

Promote Rust for normal `auto` use only when every gate passes:

```text
PARITY = PASS
DETERMINISM = PASS
EXISTING_GOLDENS = PASS
API_FREEZE = PASS
BENCHMARK = MEANINGFUL
MAINTENANCE_COST = ACCEPTABLE
```

The normal performance threshold is at least 2x on a representative workload, or a documented clear throughput advantage for large experiment batches. If the threshold is not met, retain the evidence and record:

```text
N0_PROMOTION = REJECTED
reason = insufficient measured benefit
```

Research-only native execution may remain available if it is useful and does not burden packaging, but `auto` must continue to use the Python reference.

## Stage 6: audits and deployment planning

Record concise findings rather than ceremonial documents.

### Security audit

Check malformed arrays, allocation bounds, integer overflow, panic paths, unbounded loops, FFI exception mapping, non-finite floats, and dependency provenance. The crate receives no network or filesystem authority.

### Migration audit

Verify no ownership moved from Python/FastAPI or from the browser/GPU presentation layers. Rust inputs should be vectors, matrices, scalar parameters, timesteps, indices, or numeric state rather than Psy-Fi domain concepts.

### Deployment and key lifecycle

Confirm editable local installation, Linux CI build, production packaging, and Docker build/smoke behavior. No credentials, signing keys, network services, or persistent native state should be introduced. If production packaging becomes materially worse, reject promotion.

### User impact

Public API responses, errors, deterministic sessions, exports, scene snapshots, visual mappings, and fallback behavior must remain unchanged. Native absence must not silently alter simulation semantics.

## Stage 7: adversarial challenge and repair loop

Attempt to disprove the claim that Rust improves Psy-Fi without changing simulation semantics:

1. Measure whether conversion is slower than computation.
2. Check float ordering and architecture sensitivity.
3. Remove or hide the extension and verify explicit backend behavior.
4. Fuzz malformed inputs for panic and allocation paths.
5. Confirm tests do not compare Rust against itself.
6. Diff API, scene, deterministic, and visual golden artifacts.
7. Confirm Rust contains no domain interpretation.
8. Compare against existing NumPy/SciPy and consider whether vectorization or Numba would solve the same problem with less complexity.
9. Validate that the selected function is actually hot and the benchmark represents real calls.
10. Build and smoke-test Docker when packaging changes affect it.

Triage findings, repair only N0-scoped defects, and repeat verification until the gate is supported or the candidate is rejected. Do not fix unrelated bugs or regenerate changed goldens inside N0.

## Stage 8: CI and verification

Extend CI minimally, preferably with a focused native job or clearly ordered steps:

1. install stable Rust and maturin;
2. run `cargo fmt --check`, Clippy with warnings denied, and Rust tests;
3. build/install the extension;
4. run native parity tests;
5. run all existing Python, OpenAPI, README, frontend, GPU typecheck/test/build gates unchanged.

Final local verification:

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test
python -m pytest <native-parity-tests> -q
python -m pytest tests/ -q
python -m pytest tests/test_openapi_contract.py -q
npm test
npm run gpu:test
npm run gpu:typecheck
npm run gpu:build
python scripts/benchmark_native_kernel.py
```

Run Docker build/smoke tests when production packaging is affected. Inspect the final diff for generated wheels, shared libraries, target directories, changed snapshots, and unrelated edits.

## Stop conditions

Stop and report rather than expanding scope when no meaningful kernel exists, parity fails, deterministic output or goldens change, contracts change, FFI overhead removes the benefit, performance is negligible, deployment materially worsens, Rust requires domain duplication, or the work begins becoming a general Python-to-Rust rewrite.

## Required final report

Use this structure and attach command/test evidence to every readiness claim:

```text
N0 — Native Computational Kernel
STATUS
PASS | PARTIAL | REJECTED
SELECTED KERNEL
<module/function>
WHY THIS KERNEL
<evidence>
ARCHITECTURE
Python authority:
Rust responsibility:
FFI boundary:
FILES CHANGED
...
PARITY
tests:
result:
tolerance:
DETERMINISM
result:
BENCHMARK
small:
representative:
large:
speedup:
API CONTRACT
PASS/FAIL
GOLDENS
PASS/FAIL
CI
PASS/FAIL
SECURITY
findings:
ADVERSARIAL RESULT
...
PROMOTION DECISION
APPROVED | REJECTED
REASON
...
NEXT RECOMMENDED PHASE
N1 | remain at N0
```

## Future phases, documentation only

- N1: deterministic state hashing and replay receipts
- N2: additional field kernels
- N3: batch parameter sweep engine
- N4: deterministic parallel experiment execution
- N5: headless native experiment runner
- N6: reassess WASM only if architecture requires it

N1 through N6 are not authorized by this plan. Their implementation requires N0 evidence and a separate scope decision.
