"""Deterministic seed-major Cartesian expansion."""

from __future__ import annotations
from itertools import product
from collections.abc import Iterator
from .hashing import sha256_digest
from .models import ENGINE_VERSION, ExpandedRun, ExperimentSpec
from .observables import get_observable

DEFAULT_PARAMETERS = {
    "width": 64,
    "height": 64,
    "coupling_strength": 0.5,
    "dt": 0.1,
    "normalization_P": 1.0,
    "normalization_V": 1.0,
}


def input_identity(spec: ExperimentSpec, seed: int, parameters: dict) -> dict:
    versions = {name: get_observable(name).version for name in spec.observables}
    return {
        "schema_version": spec.schema_version,
        "experiment_id": spec.experiment_id,
        "seed": seed,
        "parameters": parameters,
        "steps": spec.steps,
        "engine_version": ENGINE_VERSION,
        "observable_versions": versions,
    }


def expand_runs(spec: ExperimentSpec) -> Iterator[ExpandedRun]:
    names = sorted(spec.parameters)
    for seed in spec.seeds:
        combinations = product(*(spec.parameters[name].values for name in names)) if names else [()]
        for values in combinations:
            parameters = dict(DEFAULT_PARAMETERS)
            parameters.update(dict(zip(names, values)))
            identity = input_identity(spec, seed, parameters)
            input_hash = sha256_digest(identity)
            yield ExpandedRun(
                experiment_id=spec.experiment_id,
                run_id=f"run_{input_hash[:24]}",
                seed=seed,
                parameters=parameters,
                steps=spec.steps,
                input_hash=input_hash,
            )
