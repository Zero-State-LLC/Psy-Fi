from psyfi_core.experiments.replay import replay_run
import pytest

from psyfi_core.experiments.hashing import sha256_digest
from psyfi_core.experiments.models import ExperimentRunReceipt
from psyfi_core.experiments.runner import receipt_output_content, run_experiment
from .test_experiment_spec import valid


def test_replay_passes():
    spec = valid()
    receipt = run_experiment(spec).receipts[0]
    assert replay_run(receipt, spec).status == "PASS"


def test_changed_expected_hash_is_drift():
    spec = valid()
    raw = run_experiment(spec).receipts[0].model_dump()
    raw["observables"]["coherence"] += 0.01
    changed = ExperimentRunReceipt.model_validate(raw)
    raw["output_hash"] = sha256_digest(receipt_output_content(changed))
    report = replay_run(raw, spec)
    assert report.status == "DRIFT" and report.expected_output_hash != report.actual_output_hash


def test_tampered_receipt_output_is_invalid():
    spec = valid()
    raw = run_experiment(spec).receipts[0].model_dump()
    raw["observables"]["coherence"] += 0.01
    assert replay_run(raw, spec).status == "INVALID_RECEIPT"


def test_changed_input_is_invalid():
    spec = valid()
    raw = run_experiment(spec).receipts[0].model_dump()
    raw["input_hash"] = "0" * 64
    assert replay_run(raw, spec).status == "INVALID_RECEIPT"


@pytest.mark.parametrize(
    ("field", "value"),
    [("experiment_id", "forged"), ("seed", 2), ("steps", 3)],
)
def test_forged_receipt_identity_is_invalid(field, value):
    spec = valid()
    raw = run_experiment(spec).receipts[0].model_dump()
    raw[field] = value
    assert replay_run(raw, spec).status == "INVALID_RECEIPT"


def test_forged_receipt_parameters_are_invalid():
    spec = valid()
    raw = run_experiment(spec).receipts[0].model_dump()
    raw["parameters"]["width"] = 9
    assert replay_run(raw, spec).status == "INVALID_RECEIPT"


def test_unsupported_version_is_explicit():
    spec = valid()
    raw = run_experiment(spec).receipts[0].model_dump()
    raw["schema_version"] = "future"
    assert replay_run(raw, spec).status == "UNSUPPORTED_VERSION"


def test_unsupported_engine_version_is_explicit():
    spec = valid()
    raw = run_experiment(spec).receipts[0].model_dump()
    raw["engine_version"] = "future"
    assert replay_run(raw, spec).status == "UNSUPPORTED_VERSION"
