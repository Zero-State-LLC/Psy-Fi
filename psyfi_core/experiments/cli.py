"""Minimal JSON-based E0 command line interface."""

from __future__ import annotations
import argparse, json
from pathlib import Path
from .export import export_experiment
from .models import ExperimentRunReceipt, ExperimentSpec
from .replay import replay_run
from .runner import run_experiment


def _spec(path: str) -> ExperimentSpec:
    return ExperimentSpec.model_validate_json(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m psyfi_core.experiments")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("spec")
    run.add_argument("--output", default="experiments")
    replay = commands.add_parser("replay")
    replay.add_argument("spec")
    replay.add_argument("runs")
    replay.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    spec = _spec(args.spec)
    if args.command == "run":
        result = run_experiment(spec)
        path = export_experiment(spec, result, args.output)
        print(path)
        return 0
    for line in Path(args.runs).read_text(encoding="utf-8").splitlines():
        raw = json.loads(line)
        if raw.get("run_id") == args.run_id:
            report = replay_run(raw, spec)
            print(report.model_dump_json())
            return 0 if report.status == "PASS" else 1
    parser.error(f"run_id not found: {args.run_id}")
    return 2
