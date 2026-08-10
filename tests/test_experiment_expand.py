from psyfi_core.experiments.expand import expand_runs
from psyfi_core.experiments.hashing import sha256_digest
from .test_experiment_spec import valid


def test_seed_major_sorted_parameter_expansion_is_stable():
    spec = valid(
        seeds=[2, 1],
        parameters={
            "width": {"values": [8, 9]},
            "coupling_strength": {"values": [0.2, 0.4]},
            "height": {"values": [8]},
        },
    )
    first = list(expand_runs(spec))
    second = list(expand_runs(spec))
    assert first == second
    assert [(r.seed, r.parameters["coupling_strength"], r.parameters["width"]) for r in first] == [
        (2, 0.2, 8),
        (2, 0.2, 9),
        (2, 0.4, 8),
        (2, 0.4, 9),
        (1, 0.2, 8),
        (1, 0.2, 9),
        (1, 0.4, 8),
        (1, 0.4, 9),
    ]


def test_run_identity_changes_with_parameter():
    runs = list(
        expand_runs(valid(parameters={"width": {"values": [8, 9]}, "height": {"values": [8]}}))
    )
    assert runs[0].run_id != runs[1].run_id


def test_canonical_hash_ignores_dictionary_order():
    assert sha256_digest({"a": 1, "b": 0.1}) == sha256_digest({"b": 0.1, "a": 1})
