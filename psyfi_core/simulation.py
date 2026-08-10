"""Python-authoritative deterministic simulation entry point.

This module contains the existing simulation path without HTTP dependencies so
headless experiment orchestration can invoke the same implementation as FastAPI.
"""

from __future__ import annotations

from collections.abc import Callable
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
from psyfi_core.visualization import build_magnitude_visualization


class PresetNotFoundError(ValueError):
    """Raised when a requested substance preset cannot be resolved."""


def run_simulation(
    *,
    width: int,
    height: int,
    steps: int,
    seed: int | None = None,
    preset: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    coupling_strength: float | None = None,
    dt: float = 0.1,
    normalization_P: float | None = None,
    normalization_V: float | None = None,
) -> dict[str, Any]:
    """Execute the canonical deterministic Python simulation.

    Optional scalar overrides are internal headless controls. Existing API
    callers omit them and retain their prior behavior exactly.
    """
    config = PsyFiConfig()
    config.validate_grid_size(width, height)

    effective_seed = config.abx.default_seed if seed is None else seed
    runtime = ABXRuntime(deterministic=True, seed=effective_seed)
    runtime.metrics.set_grid_size(width, height)

    resolved_coupling = 0.5
    resolved_normalization_p = 1.0
    resolved_normalization_v = 1.0

    if preset:
        loaded = load_preset(preset)
        if loaded is None:
            raise PresetNotFoundError(f"Preset '{preset}' not found")
        resolved_coupling = float(loaded.psyfi_params.coupling_strength)
        resolved_normalization_p = float(loaded.psyfi_params.normalization.P)
        resolved_normalization_v = float(loaded.psyfi_params.normalization.V)
        runtime.provenance.add_meta("preset", preset)

    if coupling_strength is not None:
        resolved_coupling = coupling_strength
    if normalization_P is not None:
        resolved_normalization_p = normalization_P
    if normalization_V is not None:
        resolved_normalization_v = normalization_V

    if should_cancel is not None and should_cancel():
        raise SimulationCancelled("Simulation cancelled before start")

    frame = ResonanceFrame.zeros(width, height)
    random_phases = runtime.rng.uniform(-np.pi, np.pi, size=(height, width))
    initial_magnitudes = runtime.rng.uniform(0.5, 1.5, size=(height, width))
    initial_field = (initial_magnitudes * np.exp(1j * random_phases)).astype(np.complex64)
    frame = frame.copy_with_field(initial_field)

    params = ConsciousnessOmegaParams(
        coupling_type="symmetric",
        coupling_strength=resolved_coupling,
        steps=steps,
        dt=dt,
    )
    evolved_field = evolve_consciousness_omega(
        frame.field,
        params,
        runtime,
        should_cancel=should_cancel,
        backend="reference",
    )

    if should_cancel is not None and should_cancel():
        raise SimulationCancelled("Simulation cancelled after evolution")

    norm_params = NormalizationParams(
        P=resolved_normalization_p,
        V=resolved_normalization_v,
        surround_radius=3,
    )
    normalized_field = apply_normalization(evolved_field, norm_params)
    valence_metrics = compute_valence_metrics(normalized_field)

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
        normalized_field,
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
