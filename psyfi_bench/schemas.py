"""Versioned, machine-readable benchmark contracts (Pydantic v2).

Every document carries a ``schema`` id. Results are self-describing: they embed
the manifest they ran, the environment they ran in, and a measurement class
that separates measured evidence from synthetic or replayed data.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from psyfi_bench import (
    BENCH_VERSION,
    CAPABILITIES_SCHEMA,
    CAPTURE_SCHEMA,
    MANIFEST_SCHEMA,
    RESULT_SCHEMA,
    SCORECARD_SCHEMA,
)

Family = Literal["field_compute", "render", "interpretation", "fieldloop"]
MeasurementClass = Literal["measured", "synthetic", "replay"]
StageStatus = Literal["ok", "failed", "skipped", "timeout", "cancelled"]
FailureCategory = Literal[
    "timeout",
    "cancelled",
    "provider",
    "parse",
    "validation",
    "resource",
    "unsupported",
    "internal",
]
HardwareClass = Literal["discrete", "integrated", "cpu_only", "remote", "unknown"]


def stable_hash(payload: Any, *, length: int = 16) -> str:
    """SHA-256 of canonical JSON, truncated. Used for manifests and results."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return digest[:length] if length else digest


class Protocol(BaseModel):
    """Experimental protocol for one workload."""

    model_config = ConfigDict(extra="forbid")

    warmup_runs: int = Field(default=1, ge=0, le=100)
    repeats: int = Field(default=5, ge=1, le=10_000)
    cold_start: bool = Field(default=True, description="Record the first (cold) run separately.")
    timeout_s: float = Field(default=120.0, gt=0.0, le=86_400.0)
    min_duration_s: float | None = Field(
        default=None,
        ge=0.0,
        description="For sustained stages: keep repeating until this wall time has elapsed.",
    )
    memory_probe: bool = Field(
        default=True, description="Run one extra repeat under tracemalloc for peak allocation."
    )
    bootstrap_resamples: int = Field(default=2000, ge=100, le=100_000)
    bootstrap_seed: int = Field(default=0, ge=0)


class Tolerances(BaseModel):
    """Reproducibility tolerances the result is checked against."""

    model_config = ConfigDict(extra="allow")

    timing_cv_max: float = Field(default=0.25, ge=0.0, description="Max coefficient of variation for wall time.")
    quantization: float = Field(default=1e-5, gt=0.0, description="Rounding step for the quantized output hash.")
    accelerator_atol: float = Field(default=1e-4, ge=0.0, description="Max abs error of an accelerator vs numpy reference.")
    accelerator_rtol: float = Field(default=1e-4, ge=0.0)
    reference_atol: float = Field(
        default=1e-3, ge=0.0,
        description="Max abs error of the output summary statistics vs the locked reference summary (cross-platform check).",
    )


class WorkloadManifest(BaseModel):
    """Versioned workload definition. ``manifest_hash`` locks params + protocol + references."""

    model_config = ConfigDict(extra="forbid")

    schema_id: str = Field(default=MANIFEST_SCHEMA, alias="schema")
    id: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    version: int = Field(ge=1)
    family: Family
    title: str
    description: str = ""
    execution: Literal["python", "browser", "python+provider", "python+browser+provider"] = "python"
    params: dict[str, Any] = Field(default_factory=dict)
    protocol: Protocol = Field(default_factory=Protocol)
    references: dict[str, Any] = Field(
        default_factory=dict,
        description="Locked reference values (hashes, oracle labels). A mismatch is a lock failure.",
    )
    tolerances: Tolerances = Field(default_factory=Tolerances)
    requires: list[str] = Field(default_factory=list, description="Capabilities needed: webgpu, provider, torch…")
    tags: list[str] = Field(default_factory=list)

    def hash_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "family": self.family,
            "execution": self.execution,
            "params": self.params,
            "protocol": self.protocol.model_dump(),
            "references": self.references,
            "tolerances": self.tolerances.model_dump(),
        }

    @property
    def manifest_hash(self) -> str:
        return stable_hash(self.hash_payload())

    def to_document(self) -> dict[str, Any]:
        doc = self.model_dump(by_alias=True)
        doc["manifest_hash"] = self.manifest_hash
        return doc


class GpuRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    vendor: str = "unknown"
    name: str = ""
    memory_bytes: int | None = None
    driver: str | None = None
    cores: int | None = None
    source: str = Field(description="nvidia-smi | rocm-smi | system_profiler | torch | webgpu | manual")
    hardware_class: HardwareClass = "unknown"


class EnvironmentRecord(BaseModel):
    """Hardware, software, and provenance of the process that measured."""

    model_config = ConfigDict(extra="allow")

    captured_at: str
    hostname_hash: str | None = Field(default=None, description="SHA-256 prefix of the hostname; never the hostname.")
    platform: dict[str, Any] = Field(default_factory=dict)
    cpu: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    gpus: list[GpuRecord] = Field(default_factory=list)
    software: dict[str, Any] = Field(default_factory=dict)
    browser: dict[str, Any] | None = None
    power: dict[str, Any] | None = None
    hardware_class: HardwareClass = "unknown"
    unavailable: dict[str, str] = Field(
        default_factory=dict,
        description="Telemetry that could not be collected, with the reason. Never estimated silently.",
    )


class Statistics(BaseModel):
    """Summary of a repeated measurement."""

    model_config = ConfigDict(extra="forbid")

    n: int
    unit: str = ""
    mean: float
    median: float
    min: float
    max: float
    std: float
    cv: float | None = Field(default=None, description="std / mean when mean > 0")
    mad: float
    p50: float
    p90: float
    p95: float
    p99: float
    ci95_mean: tuple[float, float] | None = None
    ci95_median: tuple[float, float] | None = None
    bootstrap: dict[str, Any] | None = None


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rss_before_bytes: int | None = None
    rss_peak_delta_bytes: int | None = None
    tracemalloc_peak_bytes: int | None = None
    tracemalloc_current_bytes: int | None = None
    note: str | None = None


class DeterminismRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    exact_sha256: str | None = None
    quantized_sha256: str | None = None
    quantization: float | None = None
    bitwise_identical_across_repeats: bool | None = None
    quantized_identical_across_repeats: bool | None = None
    reference_match: bool | None = Field(
        default=None,
        description="Quantized digest equals the manifest's locked digest (None when no lock). Platform-class evidence: "
        "the same digest means the same floating-point platform; a mismatch alone is not an error.",
    )
    reference_within_tolerance: bool | None = Field(
        default=None,
        description="Output summary statistics are within tolerances.reference_atol of the locked summary "
        "(None when no summary lock). The cross-platform reproducibility check.",
    )
    reference_max_abs_error: float | None = Field(default=None, description="Max abs error of the summary vs the lock.")
    nan_count: int = 0
    inf_count: int = 0


class PowerRecord(BaseModel):
    """Sampled GPU power for one stage. Only what the sampler returned; absent tool means no record."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="Sampler name, e.g. nvidia-smi.")
    query: str = Field(description="Fields requested from the sampler.")
    interval_s: float = Field(description="Requested polling interval; actual spacing is in the sample timestamps.")
    sample_count: int = Field(description="Samples taken inside the measured window; readings after the stage are dropped.")
    window_s: float = Field(description="Wall seconds the sampler was running around the measured repeats.")
    sampled_span_s: float = Field(description="Seconds between the first and last in-window sample with a power reading (energy is integrated over this).")
    power_w_mean: float | None = None
    power_w_max: float | None = None
    temperature_c_max: float | None = None
    sm_clock_mhz_mean: float | None = None
    sm_clock_mhz_max: float | None = None
    energy_j: float | None = Field(default=None, description="Joules from the samples; None with unavailable_reason when under 2 samples.")
    work_unit: str | None = Field(default=None, description="cell_step or frame.")
    work_units: float | None = Field(default=None, description="Work units completed while sampling.")
    energy_j_per_work_unit: float | None = None
    derivation: str
    unavailable_reason: str | None = None


class StageRecord(BaseModel):
    """One measured stage: a workload point, a render pass, a model query batch…"""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    status: StageStatus = "ok"
    measurement_class: MeasurementClass = "measured"
    params: dict[str, Any] = Field(default_factory=dict)
    wall_ms: list[float] = Field(default_factory=list, description="Per-repeat wall time after warm-up.")
    cpu_ms: list[float] = Field(default_factory=list)
    cold_wall_ms: float | None = None
    warmup_wall_ms: list[float] = Field(default_factory=list)
    memory: MemoryRecord | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    statistics: dict[str, Statistics] = Field(default_factory=dict)
    determinism: DeterminismRecord | None = None
    power: PowerRecord | None = Field(default=None, description="Sampled GPU power; omitted when no sampler ran.")
    error: str | None = None


class FailureRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    category: FailureCategory
    detail: str


class Provenance(BaseModel):
    model_config = ConfigDict(extra="allow")

    git_commit: str | None = None
    git_dirty: bool | None = None
    command: str | None = None
    bench_version: str = BENCH_VERSION
    psyfi_version: str | None = None
    seed: int | None = None
    notes: list[str] = Field(default_factory=list)


class BenchResult(BaseModel):
    """Self-describing benchmark result. ``result_hash`` covers everything but itself."""

    model_config = ConfigDict(extra="forbid")

    schema_id: str = Field(default=RESULT_SCHEMA, alias="schema")
    bench_version: str = BENCH_VERSION
    run_id: str
    created_at: str
    manifest: dict[str, Any]
    manifest_hash: str
    measurement_class: MeasurementClass
    status: Literal["complete", "partial", "failed"] = "complete"
    environment: EnvironmentRecord
    stages: list[StageRecord] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict, description="Headline metrics for this family.")
    determinism: dict[str, Any] = Field(default_factory=dict)
    failures: list[FailureRecord] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    non_claim: str
    result_hash: str | None = None

    def compute_hash(self) -> str:
        payload = self.model_dump(by_alias=True, exclude={"result_hash"})
        return stable_hash(payload, length=64)

    def seal(self) -> "BenchResult":
        self.result_hash = self.compute_hash()
        return self

    def verify(self) -> bool:
        return self.result_hash is not None and self.result_hash == self.compute_hash()


class CaptureStage(BaseModel):
    """One browser-side GPU stage: fixed tier, fixed snapshot, N frames."""

    model_config = ConfigDict(extra="forbid")

    id: str
    tier: str
    snapshot_key: str
    requested_frames: int
    warmup_frames: int
    frames_ms: list[float] = Field(description="Wall-clock rAF spacing per frame, warm-up excluded.")
    gpu_ms: list[float] | None = Field(default=None, description="GPU pass time per frame when timestamp-query is available.")
    draw_calls: int | None = None
    triangles: int | None = None
    duration_ms: float
    js_heap_bytes: int | None = None
    thumbnail_png_base64: str | None = Field(default=None, description="128x128 PNG of one presented frame for tier fidelity.")
    snapshot_hash: str | None = None
    js_errors: int = Field(default=0, ge=0, description="Uncaught errors observed during the measured window; non-zero invalidates the stage's frames.")
    note: str | None = None


class GpuCapture(BaseModel):
    """Payload a browser runner posts or downloads. Scored in Python."""

    model_config = ConfigDict(extra="forbid")

    schema_id: str = Field(default=CAPTURE_SCHEMA, alias="schema")
    captured_at: str
    manifest_id: str
    manifest_hash: str | None = None
    measurement_class: MeasurementClass = "measured"
    browser: dict[str, Any] = Field(
        default_factory=dict,
        description="user_agent, adapter {vendor, architecture, device, description}, dpr, viewport, features.",
    )
    stages: list[CaptureStage]
    aborted: bool = False
    note: str | None = None


class ScoreDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float | None
    unit: str
    better: Literal["lower", "higher"]
    ci95: tuple[float, float] | None = None
    source: str = Field(description="Which result/stage the value came from.")
    missing_reason: str | None = None


class Scorecard(BaseModel):
    """Multidimensional scorecard. No universal score."""

    model_config = ConfigDict(extra="forbid")

    schema_id: str = Field(default=SCORECARD_SCHEMA, alias="schema")
    generated_at: str
    family: Family
    manifest_id: str
    manifest_hash: str
    subjects: list[dict[str, Any]] = Field(description="One entry per compared result: run_id, label, hardware_class, model…")
    dimensions: dict[str, dict[str, ScoreDimension]] = Field(
        description="dimension name -> subject label -> ScoreDimension"
    )
    composites: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional named composites with formula, weights, normalization, sensitivity, missing-data rule.",
    )
    validity: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    non_claim: str


class Capabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: str = Field(default=CAPABILITIES_SCHEMA, alias="schema")
    bench_version: str = BENCH_VERSION
    families: list[str]
    workloads: list[dict[str, Any]]
    providers: list[dict[str, Any]]
    accelerators: dict[str, Any]
    environment: EnvironmentRecord
    ingest_enabled: bool
    run_enabled: bool
    non_claim: str


def export_json_schemas() -> dict[str, dict[str, Any]]:
    """JSON Schema documents for the frontend integration package."""
    out: dict[str, dict[str, Any]] = {}
    for name, model in (
        ("psyfi_bench_manifest.v1.json", WorkloadManifest),
        ("psyfi_bench_result.v1.json", BenchResult),
        ("psyfi_bench_gpu_capture.v1.json", GpuCapture),
        ("psyfi_bench_scorecard.v1.json", Scorecard),
        ("psyfi_bench_capabilities.v1.json", Capabilities),
    ):
        schema = model.model_json_schema(by_alias=True)
        schema.setdefault("$schema", "http://json-schema.org/draft-07/schema#")
        out[name] = schema
    return out
