#!/usr/bin/env python3
"""Export Pydantic session/visualization schemas beside existing preset schemas."""

from __future__ import annotations

import json
from pathlib import Path

from psyfi_core.models.session import PsyFiSession, PsyFiVisualization
from psyfi_core.experiments.models import (
    ALLOWED_PARAMETERS,
    ExperimentResult,
    ExperimentRunReceipt,
    ExperimentSpec,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "psyfi_core" / "schemas"


def _write(model, filename: str) -> Path:
    path = OUT_DIR / filename
    schema = model.model_json_schema()
    if model is ExperimentSpec:
        properties = schema["properties"]
        properties["experiment_id"]["pattern"] = r"^[a-z0-9][a-z0-9._-]*$"
        properties["seeds"]["uniqueItems"] = True
        properties["seeds"]["items"].update({"minimum": 0, "maximum": 2**32 - 1})
        properties["observables"].update({"uniqueItems": True})
        properties["observables"]["items"] = {
            "enum": ["coherence", "roughness", "valence"],
            "type": "string",
        }
        properties["parameters"].update(
            {
                "maxProperties": 8,
                "propertyNames": {"enum": sorted(ALLOWED_PARAMETERS)},
            }
        )
        properties["metadata"].update(
            {
                "maxProperties": 32,
                "propertyNames": {"maxLength": 80},
                "additionalProperties": {"type": "string", "maxLength": 500},
            }
        )
    # Align with the existing substance_schema.json draft style.
    schema.setdefault("$schema", "http://json-schema.org/draft-07/schema#")
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    """Write machine-readable schemas derived from Pydantic models."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session_path = _write(PsyFiSession, "session.schema.json")
    viz_path = _write(PsyFiVisualization, "visualization.schema.json")
    experiment_path = _write(ExperimentSpec, "experiment.schema.json")
    receipt_path = _write(ExperimentRunReceipt, "experiment_run_receipt.schema.json")
    result_path = _write(ExperimentResult, "experiment_result.schema.json")
    print(f"Wrote {session_path.relative_to(ROOT)}")
    print(f"Wrote {viz_path.relative_to(ROOT)}")
    print(f"Wrote {experiment_path.relative_to(ROOT)}")
    print(f"Wrote {receipt_path.relative_to(ROOT)}")
    print(f"Wrote {result_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
