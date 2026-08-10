"""Closed, versioned registry of established Psy-Fi scalar measurements."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

ObservableValue = float | int | str | list[Any]


@dataclass(frozen=True)
class ObservableDefinition:
    name: str
    version: str
    input_contract: str
    output_type: str
    deterministic: bool
    compute: Callable[[dict[str, Any]], ObservableValue]


def _metric(name: str) -> Callable[[dict[str, Any]], float]:
    def compute(payload: dict[str, Any]) -> float:
        # Measurement precision is part of observable v1. Six decimal places
        # absorb harmless NumPy/SciPy reduction noise across supported builds
        # without changing the Python simulation result itself.
        return round(float(payload[name]), 6)

    return compute


OBSERVABLES = {
    name: ObservableDefinition(
        name,
        "1",
        "psyfi_core.simulation.run_simulation result",
        "finite float rounded to 6 decimal places",
        True,
        _metric(name),
    )
    for name in ("coherence", "valence", "roughness")
}


def get_observable(name: str) -> ObservableDefinition:
    try:
        return OBSERVABLES[name]
    except KeyError as exc:
        raise ValueError(f"unknown observable: {name}") from exc
