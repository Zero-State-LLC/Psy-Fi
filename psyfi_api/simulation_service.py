"""Shared simulation runner used by sync and job-based API routes."""

from psyfi_core.simulation import PresetNotFoundError, run_simulation

__all__ = ["PresetNotFoundError", "run_simulation"]
