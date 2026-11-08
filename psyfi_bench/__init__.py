"""psyfi_bench — the Psy-Fi FieldLoop benchmark subsystem.

Independent of the frontend. Depends on ``psyfi_core`` for the simulation
authority (ABX-Core), the ParameterField mapper, and scene snapshots. Never
imports ``psyfi_api``. Research/visualization only; nothing here measures
consciousness or subjective experience.
"""

from __future__ import annotations

BENCH_VERSION = "0.1.0"
BENCH_NAME = "FieldLoop"

SCHEMA_PREFIX = "psyfi.bench"
MANIFEST_SCHEMA = "psyfi.bench.manifest.v1"
RESULT_SCHEMA = "psyfi.bench.result.v1"
CAPTURE_SCHEMA = "psyfi.bench.gpu_capture.v1"
SCORECARD_SCHEMA = "psyfi.bench.scorecard.v1"
CAPABILITIES_SCHEMA = "psyfi.bench.capabilities.v1"
POWER_TRACE_SCHEMA = "psyfi.bench.power_trace.v1"

FAMILIES = ("field_compute", "render", "interpretation", "fieldloop")

NON_CLAIM = (
    "Modeled phenomenology for research and visualization only. The benchmark "
    "measures computation, rendering, and model interpretation of modeled "
    "representations. It does not measure consciousness or subjective experience. "
    "Not medical advice."
)

__all__ = [
    "BENCH_NAME",
    "BENCH_VERSION",
    "CAPABILITIES_SCHEMA",
    "CAPTURE_SCHEMA",
    "FAMILIES",
    "MANIFEST_SCHEMA",
    "NON_CLAIM",
    "POWER_TRACE_SCHEMA",
    "RESULT_SCHEMA",
    "SCHEMA_PREFIX",
    "SCORECARD_SCHEMA",
]
