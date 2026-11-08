"""Shared simulation runner used by sync and job-based API routes.

The implementation moved to ``psyfi_core.simulation`` so the simulation
authority lives in the core package and the benchmark subsystem can call it
without importing the API. This module keeps the public import path stable.
"""

from __future__ import annotations

from psyfi_core.simulation import PresetNotFoundError, run_simulation

__all__ = ["PresetNotFoundError", "run_simulation"]
