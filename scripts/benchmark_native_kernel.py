#!/usr/bin/env python3
"""End-to-end benchmark for the N0 consciousness-omega kernel."""

from __future__ import annotations

import platform
import statistics
import time

import numpy as np

from psyfi_core.engines.consciousness_omega import ConsciousnessOmegaParams, evolve_consciousness_omega


def measure(field: np.ndarray, params: ConsciousnessOmegaParams, backend: str, iterations: int) -> float:
    for _ in range(3):
        evolve_consciousness_omega(field, params, backend=backend)  # type: ignore[arg-type]
    samples = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        evolve_consciousness_omega(field, params, backend=backend)  # type: ignore[arg-type]
        samples.append((time.perf_counter_ns() - start) / 1_000_000)
    return statistics.median(samples)


def main() -> None:
    rng = np.random.default_rng(20260810)
    cases = [("small", 16, 5, 100), ("representative", 64, 20, 30), ("large", 256, 40, 8)]
    print("Kernel: psyfi_core.engines.consciousness_omega")
    print(f"Environment: Python {platform.python_version()} | {platform.platform()}")
    for label, size, steps, iterations in cases:
        phase = rng.uniform(-np.pi, np.pi, size=(size, size))
        magnitude = rng.uniform(0.5, 1.5, size=(size, size))
        values = (magnitude * np.exp(1j * phase)).astype(np.complex64)
        params = ConsciousnessOmegaParams(steps=steps, coupling_strength=0.8)
        python_ms = measure(values, params, "reference", iterations)
        rust_ms = measure(values, params, "native", iterations)
        print(f"{label}: size={size}x{size} steps={steps} iterations={iterations}")
        print(f"  Python {python_ms:.3f} ms")
        print(f"  Rust   {rust_ms:.3f} ms")
        print(f"  Speedup {python_ms / rust_ms:.2f}x")


if __name__ == "__main__":
    main()
