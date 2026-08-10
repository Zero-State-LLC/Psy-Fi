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
        return float(payload[name])

    return compute


OBSERVABLES = {
    name: ObservableDefinition(
        name,
        "1",
        "psyfi_core.simulation.run_simulation result",
        "finite float",
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
