"""Deterministic simulation orchestration. The canonical pipeline lives here.

``psyfi_api.simulation_service`` re-exports ``run_simulation`` and
``PresetNotFoundError`` so the HTTP layer and older imports keep working. The
benchmark subsystem (``psyfi_bench``) calls ``simulate_field`` directly so it
never depends on the API package.

Pipeline (order is part of the contract; the RNG draw order fixes the output):

1. ``ABXRuntime(seed)``, grid size recorded on metrics.
2. Optional substance preset → coupling strength and normalization P/V.
3. Initial field: uniform phases in [-π, π], then uniform magnitudes in [0.5, 1.5].
4. Kuramoto evolution (``evolve_consciousness_omega``).
5. Divisive normalization (``apply_normalization``).
6. Valence metrics (``compute_valence_metrics``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from psyfi_core import ABXRuntime, PsyFiConfig
from psyfi_core.abx_core.errors import SimulationCancelled
from psyfi_core.engines import (
    ConsciousnessOmegaParams,
    NormalizationParams,
    apply_normalization,
    compute_valence_metrics,
    evolve_consciousness_omega,
)
from psyfi_core.models import ResonanceFrame
from psyfi_core.models.session import PsyFiSession, SessionMetrics
from psyfi_core.models.substance_preset import load_preset
from psyfi_core.models.valence_metrics import ValenceMetrics
from psyfi_core.visualization import build_magnitude_visualization


class PresetNotFoundError(ValueError):
    """Raised when a requested substance preset cannot be resolved."""


@dataclass(frozen=True)
class SimulationSettings:
    """Engine parameters that a preset may override."""

    coupling_strength: float = 0.5
    normalization_P: float = 1.0
    normalization_V: float = 1.0
    dt: float = 0.1
    surround_radius: int = 3
    coupling_type: str = "symmetric"


def resolve_preset_settings(preset: str | None) -> SimulationSettings:
    """Settings for a preset name; defaults when ``preset`` is falsy."""
    if not preset:
        return SimulationSettings()
    loaded = load_preset(preset)
    if loaded is None:
        raise PresetNotFoundError(f"Preset '{preset}' not found")
    return SimulationSettings(
        coupling_strength=float(loaded.psyfi_params.coupling_strength),
        normalization_P=float(loaded.psyfi_params.normalization.P),
        normalization_V=float(loaded.psyfi_params.normalization.V),
    )


def initial_field(runtime: ABXRuntime, width: int, height: int) -> np.ndarray:
    """Seeded initial complex field. Draw order: phases, then magnitudes."""
    frame = ResonanceFrame.zeros(width, height)
    random_phases = runtime.rng.uniform(-np.pi, np.pi, size=(height, width))
    initial_magnitudes = runtime.rng.uniform(0.5, 1.5, size=(height, width))
    field = (initial_magnitudes * np.exp(1j * random_phases)).astype(np.complex64)
    return frame.copy_with_field(field).field


@dataclass
class SimulationOutcome:
    runtime: ABXRuntime
    settings: SimulationSettings
    params: ConsciousnessOmegaParams
    norm_params: NormalizationParams
    evolved_field: np.ndarray
    normalized_field: np.ndarray
    valence: ValenceMetrics | None


def simulate_field(
    *,
    width: int,
    height: int,
    steps: int,
    seed: int,
    settings: SimulationSettings | None = None,
    should_cancel: Callable[[], bool] | None = None,
    runtime: ABXRuntime | None = None,
    compute_valence: bool = True,
) -> SimulationOutcome:
    """Run the canonical field pipeline and return every intermediate array."""
    config = PsyFiConfig()
    config.validate_grid_size(width, height)
    settings = settings or SimulationSettings()
    if runtime is None:
        runtime = ABXRuntime(deterministic=True, seed=seed)
    runtime.metrics.set_grid_size(width, height)

    if should_cancel is not None and should_cancel():
        raise SimulationCancelled("Simulation cancelled before start")

    field = initial_field(runtime, width, height)

    params = ConsciousnessOmegaParams(
        coupling_type=settings.coupling_type,  # type: ignore[arg-type]
        coupling_strength=settings.coupling_strength,
        steps=steps,
        dt=settings.dt,
    )
    evolved = evolve_consciousness_omega(field, params, runtime, should_cancel=should_cancel)

    if should_cancel is not None and should_cancel():
        raise SimulationCancelled("Simulation cancelled after evolution")

    norm_params = NormalizationParams(
        P=settings.normalization_P,
        V=settings.normalization_V,
        surround_radius=settings.surround_radius,
    )
    normalized = apply_normalization(evolved, norm_params)
    valence = compute_valence_metrics(normalized) if compute_valence else None
    return SimulationOutcome(
        runtime=runtime,
        settings=settings,
        params=params,
        norm_params=norm_params,
        evolved_field=evolved,
        normalized_field=normalized,
        valence=valence,
    )


def run_simulation(
    *,
    width: int,
    height: int,
    steps: int,
    seed: int | None = None,
    preset: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Execute a deterministic simulation and return a JSON-ready payload."""
    config = PsyFiConfig()
    config.validate_grid_size(width, height)

    effective_seed = config.abx.default_seed if seed is None else seed
    runtime = ABXRuntime(deterministic=True, seed=effective_seed)
    runtime.metrics.set_grid_size(width, height)

    settings = resolve_preset_settings(preset)
    if preset:
        runtime.provenance.add_meta("preset", preset)

    outcome = simulate_field(
        width=width,
        height=height,
        steps=steps,
        seed=effective_seed,
        settings=settings,
        should_cancel=should_cancel,
        runtime=runtime,
    )
    assert outcome.valence is not None
    valence_metrics = outcome.valence
    params = outcome.params
    norm_params = outcome.norm_params

    for module_name in ("normalization_nu", "valence_kappa"):
        if module_name not in runtime.provenance.module_chain:
            runtime.provenance.add_module(module_name)
    runtime.provenance.add_parameter("width", width)
    runtime.provenance.add_parameter("height", height)
    runtime.provenance.add_parameter("steps", steps)
    runtime.provenance.add_parameter("seed", effective_seed)
    if preset:
        runtime.provenance.add_parameter("preset", preset)

    metrics = SessionMetrics(
        valence=valence_metrics.valence_score,
        coherence=valence_metrics.coherence_score,
        symmetry=valence_metrics.symmetry_score,
        roughness=valence_metrics.roughness_score,
        richness=valence_metrics.richness_score,
    )
    session = PsyFiSession.from_simulation(
        seed=effective_seed,
        width=width,
        height=height,
        steps=steps,
        metrics=metrics,
        module_chain=list(runtime.provenance.module_chain),
        provenance_parameters=dict(runtime.provenance.parameters),
        provenance_meta=dict(runtime.provenance.meta),
        coupling_strength=params.coupling_strength,
        normalization_P=norm_params.P,
        normalization_V=norm_params.V,
    )
    if preset:
        session.preset = preset

    visualization = build_magnitude_visualization(
        outcome.normalized_field,
        session.provenance.id,
        max_dim=64,
        valence=metrics.valence,
        coherence=metrics.coherence,
    )
    if session.result is not None:
        session.result.visualization_ref = visualization.schema_version

    return {
        "width": width,
        "height": height,
        "valence": metrics.valence,
        "coherence": metrics.coherence,
        "symmetry": metrics.symmetry,
        "roughness": metrics.roughness,
        "richness": metrics.richness,
        "schema_version": session.schema_version,
        "engine_version": session.engine_version,
        "api_version": "v1",
        "seed": effective_seed,
        "provenance_id": session.provenance.id,
        "module_chain": session.provenance.module_chain,
        "preset": preset,
        "session": session.model_dump(),
        "visualization": visualization.model_dump(),
    }


__all__ = [
    "PresetNotFoundError",
    "SimulationOutcome",
    "SimulationSettings",
    "initial_field",
    "resolve_preset_settings",
    "run_simulation",
    "simulate_field",
]
