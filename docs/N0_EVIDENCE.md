# N0 Native Computational Kernel Evidence

Status: N0 implemented; promotion rejected  
Selected candidate: `psyfi_core.engines.consciousness_omega` numerical evolution loop

## Change map

| candidate | inputs / outputs | side effects | frequency | FFI / opportunity | decision |
| --- | --- | --- | --- | --- | --- |
| Consciousness Omega loop | 2D complex64 + scalars → complex64 | Numeric core is pure; wrapper owns cancellation, metrics, provenance | Production simulation, repeated per step | One array crossing; removes repeated NumPy temporaries | Selected |
| Normalization Nu | 2D complex64 + scalars → complex64 | Pure | Once per simulation | SciPy `uniform_filter` is already native | Rejected |
| Attention Phi | 2D complex64 + scalars → complex64 | Pure | No production call site found | Vectorized NumPy; low call frequency | Rejected |
| Echo Tau | two complex64 arrays → complex64 | Pure | No production call site found | Simple vectorized blend; FFI likely dominates | Rejected |

The Rust crate contains numeric terminology only. Cancellation, runtime metrics, provenance, Pydantic parameters, FastAPI, phenomenology, visualization, scene snapshots, and presentation remain outside Rust.

## Promotion decision

`auto` remains on the Python reference. Explicit `native` is fail-closed when the extension is absent.

```text
N0_PROMOTION = REJECTED
reason = representative and large workloads are slower than NumPy
```

Release-build benchmark on Python 3.12.3, Linux x86_64 under WSL2:

| workload | shape / steps | Python median | Rust median | speedup |
| --- | --- | ---: | ---: | ---: |
| small | 16×16 / 5 | 0.148 ms | 0.022 ms | 6.70× |
| representative | 64×64 / 20 | 1.106 ms | 1.740 ms | 0.64× |
| large | 256×256 / 40 | 19.238 ms | 73.042 ms | 0.26× |

The end-to-end benchmark includes the Python/Rust boundary and result allocation. Rust removes NumPy temporary arrays for tiny inputs but its scalar loop loses to vectorized NumPy as the field grows. The ≥2× representative threshold is not met.

## Parity and behavior

- Fixed shapes from 1×1 through 64×64 cover symmetric and asymmetric coupling.
- Twenty deterministic randomized fixtures compare the Python reference directly with Rust.
- Tolerance: `rtol=2e-5`, `atol=2e-6`, selected for `complex64` trigonometric ordering differences. An additional 100-fixture challenge observed a maximum absolute difference of `9.62688773e-06`.
- Repeated native execution requires exact array equality.
- NaN and infinity are rejected as `ValueError`; invalid dimensions and parameters are bounded in Rust.
- `native` fails clearly when the extension is absent.
- `auto` and all cancellation-enabled calls use the Python reference, preserving per-step cancellation, metrics, provenance, API output, and goldens.

## Security and migration audit

- No unsafe Rust, threads, network access, filesystem access, persistent state, or credentials.
- Allocation is capped at 16,777,216 elements and dimension multiplication is checked.
- Panics are not used for caller-controlled validation paths; errors map to Python exceptions.
- Rust knows only complex arrays, dimensions, coupling mode, and scalar evolution parameters.
- FastAPI, Pydantic, phenomenology, `SafetyPass`, scene snapshots, MIDI, telemetry, PWA, R3F, WebGPU, and WGSL ownership are unchanged.

## Adversarial result

The claim “Rust improves Psy-Fi without changing simulation semantics” is only supported for tiny fields. It is disproved for representative and large current workloads. NumPy is already faster there, and cancellation-compatible native chunking would add more FFI overhead. N0 therefore retains the bounded research seam but rejects default integration and remains at N0 rather than authorizing N1.

## Final report

```text
N0 — Native Computational Kernel
STATUS
PASS
SELECTED KERNEL
psyfi_core.engines.consciousness_omega / pure numerical evolution loop
WHY THIS KERNEL
Production-called, deterministic, repeated per step, one array FFI crossing; competing candidates were already compiled SciPy or unused/simple NumPy paths.
ARCHITECTURE
Python authority: parameters, semantic reference, cancellation, metrics, provenance, orchestration, API and visual contracts
Rust responsibility: optional complex-array evolution only
FFI boundary: one 2D complex64 array plus primitive scalars in; one complex64 array out
FILES CHANGED
native/psyfi-native; psyfi_core/native; consciousness_omega wrapper; native tests/benchmark; CI; roadmap/index/README/evidence
PARITY
tests: 15 native bridge tests plus 100-fixture adversarial drift sample
result: PASS
tolerance: rtol=2e-5, atol=2e-6; observed max absolute difference 9.62688773e-06
DETERMINISM
result: PASS; repeated native calls require exact array equality
BENCHMARK
small: Python 0.148 ms; Rust 0.022 ms; 6.70x
representative: Python 1.106 ms; Rust 1.740 ms; 0.64x
large: Python 19.238 ms; Rust 73.042 ms; 0.26x
speedup: promotion threshold not met
API CONTRACT
PASS; OpenAPI and frozen-contract tests unchanged
GOLDENS
PASS; scene, overlay and G4 golden tests unchanged
CI
PASS locally: fmt, Clippy, Cargo tests, wheel build, pytest, README lint, GPU tests/typecheck/build; remote Actions validates the same gates
SECURITY
findings: bounded allocation, checked multiplication, finite-input validation, explicit Python exceptions, no unsafe/network/filesystem/state authority
ADVERSARIAL RESULT
NumPy wins representative and large workloads; float ordering is tolerance-parity rather than bit parity; cancellation forces the reference path; native absence fails closed.
PROMOTION DECISION
REJECTED
REASON
Representative and large end-to-end workloads are slower than NumPy, so maintenance and semantic risk are not justified for auto execution.
NEXT RECOMMENDED PHASE
remain at N0
```
