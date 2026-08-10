"""Consciousness Omega - core field evolution with Kuramoto coupling."""

from collections.abc import Callable
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from psyfi_core.abx_core import ABXRuntime
from psyfi_core.abx_core.errors import SimulationCancelled
from psyfi_core.native.backend import Backend, consciousness_omega as run_omega_backend


class ConsciousnessOmegaParams(BaseModel):
    """Parameters for Consciousness Omega field evolution.

    Attributes:
        coupling_type: Type of coupling between oscillators
        coupling_strength: Strength of coupling (0 = independent, 2 = max coupling)
        natural_freq_base: Base natural frequency for oscillators
        freq_depth_scale: How much depth (y-position) affects frequency
        freq_brightness_scale: How much brightness affects frequency
        steps: Number of evolution steps
        dt: Time step for integration
    """

    coupling_type: Literal["symmetric", "asymmetric"] = Field(default="symmetric")
    # Upper bound matches substance presets / safety defaults (e.g. DMT = 1.2)
    coupling_strength: float = Field(default=0.5, ge=0.0, le=2.0)
    natural_freq_base: float = Field(default=1.0)
    freq_depth_scale: float = Field(default=0.5)
    freq_brightness_scale: float = Field(default=0.1)
    steps: int = Field(default=10, ge=1)
    dt: float = Field(default=0.1, gt=0.0)


def evolve_consciousness_omega(
    field: np.ndarray,
    params: ConsciousnessOmegaParams,
    runtime: ABXRuntime | None = None,
    should_cancel: Callable[[], bool] | None = None,
    backend: Backend = "auto",
) -> np.ndarray:
    """Evolve consciousness field using Kuramoto-like coupling.

    Each point in the field is a phase oscillator with a natural frequency
    that depends on its position (depth) and brightness. Oscillators couple
    to their nearest neighbors.

    Args:
        field: 2D complex field (height, width)
        params: Evolution parameters
        runtime: Optional ABX runtime for metrics tracking
        should_cancel: Optional callback checked each step; when true, raises
            ``SimulationCancelled`` so API jobs can abort promptly.

    Returns:
        Evolved field
    """
    if backend not in {"auto", "reference", "native"}:
        raise ValueError(f"Unsupported consciousness_omega backend: {backend}")
    if backend == "native" and should_cancel is not None:
        raise ValueError(
            "backend='native' cannot preserve per-step cancellation; use 'reference' or 'auto'"
        )
    if backend == "auto" and should_cancel is not None:
        backend = "reference"

    def reference() -> np.ndarray:
        return _evolve_consciousness_omega_reference(
            field,
            params,
            should_cancel,
            on_step=(runtime.metrics.increment_steps if runtime is not None else None),
        )

    result = run_omega_backend(
        field,
        coupling_type=params.coupling_type,
        coupling_strength=params.coupling_strength,
        natural_freq_base=params.natural_freq_base,
        freq_depth_scale=params.freq_depth_scale,
        freq_brightness_scale=params.freq_brightness_scale,
        steps=params.steps,
        dt=params.dt,
        reference=reference,
        backend=backend,
    )

    if runtime is not None:
        if backend == "native":
            runtime.metrics.increment_steps(params.steps)
        runtime.provenance.add_module("consciousness_omega")
        runtime.provenance.add_parameter("coupling_strength", params.coupling_strength)
        runtime.provenance.add_parameter("steps", params.steps)
    return result


def _evolve_consciousness_omega_reference(
    field: np.ndarray,
    params: ConsciousnessOmegaParams,
    should_cancel: Callable[[], bool] | None = None,
    on_step: Callable[[], None] | None = None,
) -> np.ndarray:
    """Canonical semantic reference for the pure numerical evolution."""
    height, width = field.shape

    # Extract initial phases and magnitudes
    phases = np.angle(field)
    magnitudes = np.abs(field)

    # Compute natural frequencies
    # Base frequency modulated by depth (y-position)
    y_coords = np.arange(height).reshape(-1, 1)
    depth_factor = y_coords / height  # 0 at top, 1 at bottom

    # Also modulate by brightness
    normalized_mag = magnitudes / (magnitudes.max() + 1e-8)

    natural_freq = (
        params.natural_freq_base
        + params.freq_depth_scale * depth_factor
        + params.freq_brightness_scale * normalized_mag
    )

    # Evolve using Kuramoto-like dynamics
    current_phases = phases.copy()

    for step in range(params.steps):
        if should_cancel is not None and should_cancel():
            raise SimulationCancelled(
                f"Simulation cancelled after {step}/{params.steps} steps"
            )

        # Compute coupling term from nearest neighbors
        # Simple 4-neighbor coupling (up, down, left, right)

        # Shift phases in each direction
        phase_up = np.roll(current_phases, 1, axis=0)
        phase_down = np.roll(current_phases, -1, axis=0)
        phase_left = np.roll(current_phases, 1, axis=1)
        phase_right = np.roll(current_phases, -1, axis=1)

        if params.coupling_type == "symmetric":
            # Symmetric coupling: average of phase differences
            coupling = (
                np.sin(phase_up - current_phases)
                + np.sin(phase_down - current_phases)
                + np.sin(phase_left - current_phases)
                + np.sin(phase_right - current_phases)
            ) / 4.0
        else:
            # Asymmetric coupling: weighted by magnitude
            mag_up = np.roll(magnitudes, 1, axis=0)
            mag_down = np.roll(magnitudes, -1, axis=0)
            mag_left = np.roll(magnitudes, 1, axis=1)
            mag_right = np.roll(magnitudes, -1, axis=1)

            total_mag = mag_up + mag_down + mag_left + mag_right + 1e-8

            coupling = (
                mag_up * np.sin(phase_up - current_phases)
                + mag_down * np.sin(phase_down - current_phases)
                + mag_left * np.sin(phase_left - current_phases)
                + mag_right * np.sin(phase_right - current_phases)
            ) / total_mag

        # Update phases: dθ/dt = ω + K * coupling
        phase_update = natural_freq + params.coupling_strength * coupling
        current_phases += params.dt * phase_update

        if on_step is not None:
            on_step()

    # Wrap phases to [-π, π]
    current_phases = np.angle(np.exp(1j * current_phases))

    # Reconstruct complex field
    result = magnitudes * np.exp(1j * current_phases)

    return result.astype(np.complex64)
