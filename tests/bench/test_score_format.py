"""``psyfi-bench score --format`` renders the same scorecard as markdown (default), csv or json."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from psyfi_bench.cli import main as cli_main
from psyfi_bench.report import SCORECARD_CSV_COLUMNS, scorecard_csv
from psyfi_bench.schemas import ScoreDimension, Scorecard
from tests.bench.test_api_cli_scoring import _two_results


def _card() -> Scorecard:
    dims = {
        "throughput": {
            "a": ScoreDimension(value=1.5, unit="x/s", better="higher", ci95=(1.0, 2.0), source="s1"),
            "b": ScoreDimension(value=None, unit="x/s", better="higher", source="s2", missing_reason="stage failed"),
        }
    }
    return Scorecard(
        generated_at="t", family="field_compute", manifest_id="m", manifest_hash="h",
        subjects=[{"label": "a"}, {"label": "b"}], dimensions=dims, non_claim="n",
    )


def test_scorecard_csv_rows_and_missing_values() -> None:
    rows = list(csv.DictReader(io.StringIO(scorecard_csv(_card()))))
    assert tuple(rows[0]) == SCORECARD_CSV_COLUMNS
    assert rows[0]["label"] == "a" and rows[0]["value"] == "1.5" and rows[0]["ci95_high"] == "2.0"
    assert rows[1]["label"] == "b" and rows[1]["value"] == "" and rows[1]["missing_reason"] == "stage failed"


def _no_stamp(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.startswith("- generated"))


def test_cli_score_formats(tmp_path: Path, capsys) -> None:
    store, a, b = _two_results(tmp_path)
    paths = [str(store.save(r)) for r in (a, b)]
    assert cli_main(["score", *paths, "--labels", "run-a,run-b"]) == 0
    default_out = capsys.readouterr().out
    assert default_out.startswith("# Scorecard")
    assert cli_main(["score", *paths, "--labels", "run-a,run-b", "--format", "markdown"]) == 0
    assert _no_stamp(capsys.readouterr().out) == _no_stamp(default_out)
    assert cli_main(["score", *paths, "--labels", "run-a,run-b", "--format", "csv"]) == 0
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert {r["label"] for r in rows} == {"run-a", "run-b"} and "throughput_cell_steps_per_s" in {r["dimension"] for r in rows}
    assert cli_main(["score", *paths, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["family"] == "field_compute"
    with pytest.raises(SystemExit):
        cli_main(["score", *paths, "--json", "--format", "csv"])
