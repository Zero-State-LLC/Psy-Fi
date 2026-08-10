"""Versioned experiment specifications, receipts, and results."""

from __future__ import annotations
import math, re
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from .observables import OBSERVABLES

EXPERIMENT_SCHEMA_VERSION = "psyfi.experiment.v1"
RECEIPT_SCHEMA_VERSION = "psyfi.experiment_run_receipt.v1"
RESULT_SCHEMA_VERSION = "psyfi.experiment_result.v1"
ENGINE_VERSION = "0.1.0"
MAX_SEEDS, MAX_PARAMETER_DIMENSIONS, MAX_VALUES_PER_PARAMETER, MAX_TOTAL_RUNS = 64, 8, 32, 1024
ALLOWED_PARAMETERS = {
    "width",
    "height",
    "coupling_strength",
    "dt",
    "normalization_P",
    "normalization_V",
}
Scalar = int | float | str | bool
ObservableValue = float | int | str | list[Any]


class SweepValues(BaseModel):
    values: list[Scalar] = Field(min_length=1, max_length=MAX_VALUES_PER_PARAMETER)

    @field_validator("values")
    @classmethod
    def finite_values(cls, values: list[Scalar]) -> list[Scalar]:
        if any(isinstance(v, float) and not math.isfinite(v) for v in values):
            raise ValueError("parameter values must be finite")
        return values


class ExperimentSpec(BaseModel):
    schema_version: Literal[EXPERIMENT_SCHEMA_VERSION] = EXPERIMENT_SCHEMA_VERSION
    experiment_id: str = Field(min_length=1, max_length=80)
    seeds: list[int] = Field(min_length=1, max_length=MAX_SEEDS)
    parameters: dict[str, SweepValues] = Field(default_factory=dict)
    steps: int = Field(ge=1, le=1000)
    observables: list[str] = Field(min_length=1, max_length=len(OBSERVABLES))
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("experiment_id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value):
            raise ValueError("experiment_id must be a lowercase filesystem-safe identifier")
        return value

    @field_validator("seeds")
    @classmethod
    def valid_seeds(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)):
            raise ValueError("seeds must be unique")
        if any(seed < 0 or seed > 4294967295 for seed in values):
            raise ValueError("seeds must be uint32 values")
        return values

    @field_validator("parameters")
    @classmethod
    def valid_parameters(cls, values: dict[str, SweepValues]) -> dict[str, SweepValues]:
        if len(values) > MAX_PARAMETER_DIMENSIONS:
            raise ValueError("too many parameter dimensions")
        unknown = sorted(set(values) - ALLOWED_PARAMETERS)
        if unknown:
            raise ValueError(f"unknown simulation parameters: {', '.join(unknown)}")
        for name, sweep in values.items():
            for value in sweep.values:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"{name} values must be numeric")
                if name in {"width", "height"} and (
                    not isinstance(value, int) or not 8 <= value <= 512
                ):
                    raise ValueError(f"{name} values must be integers from 8 through 512")
                if name == "coupling_strength" and not 0.0 <= value <= 2.0:
                    raise ValueError("coupling_strength values must be from 0.0 through 2.0")
                if name == "dt" and not 0.0 < value <= 1.0:
                    raise ValueError("dt values must be greater than 0.0 and at most 1.0")
                if name == "normalization_P" and value <= 0.0:
                    raise ValueError("normalization_P values must be greater than 0.0")
                if name == "normalization_V" and value < 0.0:
                    raise ValueError("normalization_V values must be at least 0.0")
        return values

    @field_validator("observables")
    @classmethod
    def valid_observables(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("observables must be unique")
        unknown = sorted(set(values) - set(OBSERVABLES))
        if unknown:
            raise ValueError(f"unknown observables: {', '.join(unknown)}")
        return values

    @field_validator("metadata")
    @classmethod
    def bounded_metadata(cls, values: dict[str, str]) -> dict[str, str]:
        if len(values) > 32 or any(len(k) > 80 or len(v) > 500 for k, v in values.items()):
            raise ValueError("metadata exceeds E0 bounds")
        return values

    @model_validator(mode="after")
    def bounded_run_count(self) -> "ExperimentSpec":
        count = len(self.seeds)
        for sweep in self.parameters.values():
            count *= len(sweep.values)
            if count > MAX_TOTAL_RUNS:
                raise ValueError(f"expanded run count exceeds {MAX_TOTAL_RUNS}")
        return self


class ExpandedRun(BaseModel):
    experiment_id: str
    run_id: str
    seed: int
    parameters: dict[str, Scalar]
    steps: int
    input_hash: str


class ExperimentRunReceipt(BaseModel):
    schema_version: Literal[RECEIPT_SCHEMA_VERSION] = RECEIPT_SCHEMA_VERSION
    experiment_id: str
    run_id: str
    seed: int
    parameters: dict[str, Scalar]
    engine_version: str
    observable_versions: dict[str, str]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    steps: int
    observables: dict[str, ObservableValue]
    provenance: dict[str, Any]


class ObservableAggregate(BaseModel):
    minimum: float
    maximum: float
    mean: float


class ExperimentSummary(BaseModel):
    run_count: int
    success_count: int
    failure_count: int
    observable_names: list[str]
    aggregates: dict[str, ObservableAggregate]


class ExperimentResult(BaseModel):
    schema_version: Literal[RESULT_SCHEMA_VERSION] = RESULT_SCHEMA_VERSION
    experiment_id: str
    spec_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_count: int
    receipts: list[ExperimentRunReceipt]
    summary: ExperimentSummary
    provenance: dict[str, Any]
    environment: dict[str, str]


class ObservableDifference(BaseModel):
    expected: ObservableValue | None = None
    actual: ObservableValue | None = None


class ReplayResult(BaseModel):
    status: Literal["PASS", "DRIFT", "INVALID_RECEIPT", "UNSUPPORTED_VERSION"]
    run_id: str
    expected_output_hash: str | None = None
    actual_output_hash: str | None = None
    observable_differences: dict[str, ObservableDifference] = Field(default_factory=dict)
    reason: str | None = None
