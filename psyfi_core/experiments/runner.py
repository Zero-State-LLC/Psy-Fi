"""Headless deterministic experiment execution through Python simulation authority."""

from __future__ import annotations
import platform, sys
from collections.abc import Callable
from statistics import fmean
from psyfi_core.abx_core.errors import SimulationCancelled
from psyfi_core.simulation import run_simulation
from .expand import expand_runs
from .hashing import sha256_digest
from .models import (
    ENGINE_VERSION,
    ExperimentResult,
    ExperimentRunReceipt,
    ExperimentSpec,
    ExperimentSummary,
    ObservableAggregate,
)
from .observables import get_observable


def receipt_output_content(receipt) -> dict:
    """Return the deterministic subset covered by a receipt output hash."""
    return {
        "run_id": receipt.run_id,
        "observables": receipt.observables,
        "engine_version": receipt.engine_version,
        "observable_versions": receipt.observable_versions,
        "provenance": receipt.provenance,
    }


def _execute(spec: ExperimentSpec, expanded, should_cancel=None) -> ExperimentRunReceipt:
    p = expanded.parameters
    payload = run_simulation(
        width=int(p["width"]),
        height=int(p["height"]),
        steps=expanded.steps,
        seed=expanded.seed,
        coupling_strength=float(p["coupling_strength"]),
        dt=float(p["dt"]),
        normalization_P=float(p["normalization_P"]),
        normalization_V=float(p["normalization_V"]),
        should_cancel=should_cancel,
    )
    observables = {name: get_observable(name).compute(payload) for name in spec.observables}
    versions = {name: get_observable(name).version for name in spec.observables}
    provenance = {
        "engine": "psyfi_core.simulation",
        "engine_version": payload["engine_version"],
        "module_chain": payload["module_chain"],
        "execution_backend": "python-reference",
    }
    receipt = ExperimentRunReceipt(
        experiment_id=spec.experiment_id,
        run_id=expanded.run_id,
        seed=expanded.seed,
        parameters=p,
        engine_version=payload["engine_version"],
        observable_versions=versions,
        input_hash=expanded.input_hash,
        output_hash="0" * 64,
        steps=expanded.steps,
        observables=observables,
        provenance=provenance,
    )
    receipt.output_hash = sha256_digest(receipt_output_content(receipt))
    return receipt


def summarize(receipts: list[ExperimentRunReceipt], names: list[str]) -> ExperimentSummary:
    aggregates = {}
    for name in names:
        values = [
            float(r.observables[name])
            for r in receipts
            if isinstance(r.observables.get(name), (int, float))
        ]
        if values:
            aggregates[name] = ObservableAggregate(
                minimum=min(values), maximum=max(values), mean=fmean(values)
            )
    return ExperimentSummary(
        run_count=len(receipts),
        success_count=len(receipts),
        failure_count=0,
        observable_names=list(names),
        aggregates=aggregates,
    )


def run_experiment(
    spec: ExperimentSpec, should_cancel: Callable[[], bool] | None = None
) -> ExperimentResult:
    receipts = []
    for expanded in expand_runs(spec):
        if should_cancel is not None and should_cancel():
            raise SimulationCancelled("Experiment cancelled at run boundary")
        receipts.append(_execute(spec, expanded, should_cancel))
    provenance = {
        "psyfi_version": ENGINE_VERSION,
        "experiment_schema_version": spec.schema_version,
        "engine_version": ENGINE_VERSION,
        "observable_versions": {n: get_observable(n).version for n in spec.observables},
    }
    environment = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": sys.platform,
    }
    return ExperimentResult(
        experiment_id=spec.experiment_id,
        spec_hash=sha256_digest(spec.model_dump(mode="json")),
        run_count=len(receipts),
        receipts=receipts,
        summary=summarize(receipts, spec.observables),
        provenance=provenance,
        environment=environment,
    )
