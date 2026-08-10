import pytest
from pydantic import ValidationError
from psyfi_core.experiments.models import ExperimentSpec


def valid(**updates):
    data = {
        "experiment_id": "test-v1",
        "seeds": [1],
        "parameters": {"width": {"values": [8]}, "height": {"values": [8]}},
        "steps": 2,
        "observables": ["coherence"],
    }
    data.update(updates)
    return ExperimentSpec.model_validate(data)


def test_valid_spec():
    assert valid().schema_version == "psyfi.experiment.v1"


@pytest.mark.parametrize(
    "updates",
    [
        {"experiment_id": "../bad"},
        {"seeds": [1, 1]},
        {"seeds": []},
        {"parameters": {"unknown": {"values": [1]}}},
        {"observables": ["mysticism"]},
    ],
)
def test_invalid_specs(updates):
    with pytest.raises(ValidationError):
        valid(**updates)


def test_run_count_overflow():
    with pytest.raises(ValidationError):
        valid(seeds=list(range(64)), parameters={"width": {"values": list(range(8, 25))}})


def test_non_finite_rejected():
    with pytest.raises(ValidationError):
        valid(parameters={"dt": {"values": [float("nan")]}})


@pytest.mark.parametrize(
    "parameters",
    [
        {"normalization_P": {"values": [0.0]}},
        {"normalization_V": {"values": [-0.1]}},
    ],
)
def test_invalid_normalization_parameters_are_rejected_in_spec(parameters):
    with pytest.raises(ValidationError):
        valid(parameters=parameters)
