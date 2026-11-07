"""Simulation endpoint for consciousness field evolution."""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from psyfi_api.jobs import SimulationSlotUnavailable, simulation_slot
from psyfi_api.simulation_service import PresetNotFoundError, run_simulation
from psyfi_api.telemetry import telemetry
from psyfi_core.abx_core.errors import SimulationCancelled
from psyfi_core.models.session import (
    SESSION_SCHEMA_VERSION,
    PsyFiSession,
    PsyFiVisualization,
)

router = APIRouter(prefix="/simulate", tags=["simulation"])


class SimulateRequest(BaseModel):
    """Request for consciousness field simulation."""

    width: int = Field(default=64, ge=8, le=512)
    height: int = Field(default=64, ge=8, le=512)
    steps: int = Field(default=10, ge=1, le=1000)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    preset: str | None = Field(
        default=None,
        description="Optional substance preset id/alias influencing coupling and normalization.",
    )


class SimulateResponse(BaseModel):
    """Response from consciousness field simulation."""

    width: int
    height: int
    valence: float
    coherence: float
    symmetry: float
    roughness: float
    richness: float
    schema_version: str = SESSION_SCHEMA_VERSION
    engine_version: str = "0.1.0"
    api_version: str = "v1"
    seed: int
    provenance_id: str
    module_chain: list[str]
    preset: str | None = None
    session: PsyFiSession
    visualization: PsyFiVisualization


@router.post("/", response_model=SimulateResponse)
async def simulate_consciousness_field(
    body: SimulateRequest,
    request: Request,
) -> SimulateResponse:
    """Simulate consciousness field evolution (cancellable on disconnect)."""
    cancelled = {"flag": False, "done": False}

    async def _watch_disconnect() -> None:
        while not cancelled["done"]:
            if await request.is_disconnected():
                cancelled["flag"] = True
                return
            await asyncio.sleep(0.05)

    watch_task = asyncio.create_task(_watch_disconnect())
    try:
        try:
            with simulation_slot():
                payload = await asyncio.to_thread(
                    run_simulation,
                    width=body.width,
                    height=body.height,
                    steps=body.steps,
                    seed=body.seed,
                    preset=body.preset,
                    should_cancel=lambda: cancelled["flag"],
                )
        except SimulationSlotUnavailable as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
    except PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SimulationCancelled as exc:
        telemetry.emit("simulate_cancelled", mode="sync", reason=str(exc))
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        cancelled["done"] = True
        watch_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watch_task

    telemetry.emit(
        "simulate_completed",
        mode="sync",
        width=body.width,
        height=body.height,
        steps=body.steps,
        preset=body.preset or "none",
    )
    return SimulateResponse.model_validate(payload)
