"""N0 parity and backend-policy tests for the optional Rust kernel."""

import importlib.util

import numpy as np
import pytest

from psyfi_core.engines.consciousness_omega import (
    ConsciousnessOmegaParams,
    _evolve_consciousness_omega_reference,
    evolve_consciousness_omega,
)
from psyfi_core.native import native_available

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("psyfi_native") is None,
    reason="psyfi-native extension is not installed",
)


def field(seed: int, shape: tuple[int, int]) -> np.ndarray:
    rng = np.random.default_rng(seed)
    magnitude = rng.uniform(0.1, 2.0, size=shape)
    phase = rng.uniform(-np.pi, np.pi, size=shape)
    return (magnitude * np.exp(1j * phase)).astype(np.complex64)


@pytest.mark.parametrize("shape", [(1, 1), (2, 3), (16, 16), (64, 64)])
@pytest.mark.parametrize("coupling_type", ["symmetric", "asymmetric"])
def test_native_matches_reference(shape: tuple[int, int], coupling_type: str) -> None:
    values = field(20260810, shape)
    params = ConsciousnessOmegaParams(coupling_type=coupling_type, steps=7, dt=0.05)
    reference = _evolve_consciousness_omega_reference(values, params)
    native = evolve_consciousness_omega(values, params, backend="native")
    np.testing.assert_allclose(native, reference, rtol=2e-5, atol=2e-6)


def test_randomized_parity_and_repeated_determinism() -> None:
    params = ConsciousnessOmegaParams(coupling_type="asymmetric", coupling_strength=1.2, steps=10)
    for seed in range(20):
        values = field(seed, (8 + seed % 5, 7 + seed % 3))
        reference = _evolve_consciousness_omega_reference(values, params)
        first = evolve_consciousness_omega(values, params, backend="native")
        second = evolve_consciousness_omega(values, params, backend="native")
        np.testing.assert_array_equal(first, second)
        np.testing.assert_allclose(first, reference, rtol=2e-5, atol=2e-6)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_native_rejects_non_finite_input(bad: float) -> None:
    values = field(1, (2, 2))
    values[0, 0] = complex(bad, 0.0)
    with pytest.raises(ValueError, match="NonFiniteInput"):
        evolve_consciousness_omega(values, ConsciousnessOmegaParams(), backend="native")


def test_auto_remains_reference_and_cancellation_is_preserved() -> None:
    values = field(1, (4, 4))
    params = ConsciousnessOmegaParams(steps=2)
    expected = _evolve_consciousness_omega_reference(values, params)
    np.testing.assert_array_equal(evolve_consciousness_omega(values, params), expected)


def test_native_is_available_in_native_test_environment() -> None:
    assert native_available()
