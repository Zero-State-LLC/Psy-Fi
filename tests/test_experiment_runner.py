import pytest
import json
from pathlib import Path
from psyfi_core.abx_core.errors import SimulationCancelled
from psyfi_core.experiments.observables import OBSERVABLES, get_observable
from psyfi_core.experiments.runner import run_experiment
from .test_experiment_spec import valid


def test_known_fixture_is_deterministic_and_python_authoritative():
    spec = valid(
        seeds=[1, 2],
        parameters={
            "width": {"values": [8]},
            "height": {"values": [8]},
            "coupling_strength": {"values": [0.25, 0.5]},
        },
    )
    a = run_experiment(spec)
    b = run_experiment(spec)
    assert [r.model_dump() for r in a.receipts] == [r.model_dump() for r in b.receipts]
    assert a.spec_hash == b.spec_hash and a.summary == b.summary and a.run_count == 4
    assert all(r.provenance["execution_backend"] == "python-reference" for r in a.receipts)


def test_registry_records_versions():
    assert set(OBSERVABLES) == {"coherence", "valence", "roughness"}
    assert get_observable("coherence").version == "1"


def test_cancellation_at_boundary():
    with pytest.raises(SimulationCancelled):
        run_experiment(valid(), should_cancel=lambda: True)


def test_committed_e0_golden_is_unchanged():
    fixture = Path(__file__).parent / "fixtures" / "experiments" / "e0_smoke"
    spec = valid(
        experiment_id="e0-smoke-v1",
        seeds=[1, 2],
        parameters={
            "coupling_strength": {"values": [0.25, 0.5]},
            "height": {"values": [8]},
            "width": {"values": [8]},
        },
        steps=4,
        observables=["coherence", "valence"],
        metadata={"purpose": "E0 deterministic smoke fixture"},
    )
    result = run_experiment(spec)
    expected_runs = [json.loads(line) for line in (fixture / "runs.jsonl").read_text().splitlines()]
    assert spec.model_dump(mode="json") == json.loads((fixture / "experiment.json").read_text())
    assert [receipt.model_dump(mode="json") for receipt in result.receipts] == expected_runs
    assert result.summary.model_dump(mode="json") == json.loads(
        (fixture / "summary.json").read_text()
    )
