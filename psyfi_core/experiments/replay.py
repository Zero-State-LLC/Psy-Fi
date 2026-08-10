"""Receipt replay with explicit drift and version failure states."""

from __future__ import annotations
from pydantic import ValidationError
from .expand import expand_runs
from .models import (
    ENGINE_VERSION,
    ExperimentRunReceipt,
    ExperimentSpec,
    ObservableDifference,
    RECEIPT_SCHEMA_VERSION,
    ReplayResult,
)
from .observables import get_observable
from .hashing import sha256_digest
from .runner import _execute, receipt_output_content


def replay_run(receipt: ExperimentRunReceipt | dict, spec: ExperimentSpec) -> ReplayResult:
    raw = receipt if isinstance(receipt, dict) else receipt.model_dump(mode="json")
    run_id = str(raw.get("run_id", "unknown"))
    if raw.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        return ReplayResult(
            status="UNSUPPORTED_VERSION", run_id=run_id, reason="unsupported receipt schema version"
        )
    try:
        expected = ExperimentRunReceipt.model_validate(raw)
    except ValidationError as exc:
        return ReplayResult(status="INVALID_RECEIPT", run_id=run_id, reason=str(exc))
    supported_versions = {name: get_observable(name).version for name in spec.observables}
    if (
        expected.engine_version != ENGINE_VERSION
        or expected.observable_versions != supported_versions
    ):
        return ReplayResult(
            status="UNSUPPORTED_VERSION",
            run_id=run_id,
            reason="receipt engine or observable versions are not supported",
        )
    if sha256_digest(receipt_output_content(expected)) != expected.output_hash:
        return ReplayResult(
            status="INVALID_RECEIPT",
            run_id=run_id,
            reason="receipt output hash does not cover its stored output",
        )
    expanded = next((run for run in expand_runs(spec) if run.run_id == expected.run_id), None)
    if (
        expanded is None
        or expanded.input_hash != expected.input_hash
        or expected.experiment_id != expanded.experiment_id
        or expected.seed != expanded.seed
        or expected.parameters != expanded.parameters
        or expected.steps != expanded.steps
    ):
        return ReplayResult(
            status="INVALID_RECEIPT",
            run_id=run_id,
            reason="receipt input identity does not match experiment spec",
        )
    actual = _execute(spec, expanded)
    if actual.output_hash == expected.output_hash:
        return ReplayResult(
            status="PASS",
            run_id=run_id,
            expected_output_hash=expected.output_hash,
            actual_output_hash=actual.output_hash,
        )
    names = sorted(set(expected.observables) | set(actual.observables))
    differences = {
        name: ObservableDifference(
            expected=expected.observables.get(name), actual=actual.observables.get(name)
        )
        for name in names
        if expected.observables.get(name) != actual.observables.get(name)
    }
    return ReplayResult(
        status="DRIFT",
        run_id=run_id,
        expected_output_hash=expected.output_hash,
        actual_output_hash=actual.output_hash,
        observable_differences=differences,
    )
