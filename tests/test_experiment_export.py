import hashlib, json
from psyfi_core.experiments.export import export_experiment
from psyfi_core.experiments.runner import run_experiment
from .test_experiment_spec import valid


def test_export_file_set_jsonl_and_hashes(tmp_path):
    spec = valid(seeds=[1, 2])
    result = run_experiment(spec)
    target = export_experiment(spec, result, tmp_path)
    assert {p.name for p in target.iterdir()} == {
        "experiment.json",
        "manifest.json",
        "runs.jsonl",
        "summary.json",
        "provenance.json",
    }
    assert len((target / "runs.jsonl").read_text().splitlines()) == 2
    manifest = json.loads((target / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((target / name).read_bytes()).hexdigest() == digest
