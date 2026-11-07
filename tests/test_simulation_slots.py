"""Sync simulation and scene snapshots share the in-process job slots."""

from __future__ import annotations

import asyncio
import threading
import time

import anyio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from psyfi_api.jobs import job_store
from psyfi_api.main import app
from psyfi_api.simulation_service import run_simulation

_SIM = {"width": 8, "height": 8, "steps": 1, "seed": 5}
_SNAP = {
    "substance": "lsd",
    "mode": "open",
    "intensity": 0.4,
    "seed": 5,
    "steps": 2,
    "include_simulation": True,
    "sim_steps": 1,
    "width": 8,
    "height": 8,
}


def _hold(count: int) -> int:
    held = 0
    for _ in range(count):
        if not job_store.try_acquire_slot():
            break
        held += 1
    return held


def _release(count: int) -> None:
    for _ in range(count):
        job_store.release_slot()


def _free_slots() -> int:
    held = _hold(8)
    _release(held)
    return held


def test_same_seed_returns_the_same_metrics() -> None:
    body = {"width": 16, "height": 16, "steps": 2, "seed": 11}
    with TestClient(app) as client:
        first = client.post("/api/v1/simulate/", json=body)
        second = client.post("/api/v1/simulate/", json=body)
    assert first.status_code == 200
    assert second.status_code == 200
    for key in ("valence", "coherence", "symmetry", "roughness", "richness"):
        assert first.json()[key] == second.json()[key]
    assert _free_slots() == 4


def test_fifth_overlapping_sync_simulation_is_refused() -> None:
    entered: list[int] = []
    refusals: list[int] = []
    release = threading.Event()
    lock = threading.Lock()
    real_acquire = job_store.try_acquire_slot

    def counting_acquire() -> bool:
        ok = real_acquire()
        if not ok:
            with lock:
                refusals.append(1)
        return ok

    def blocking(**kwargs):
        with lock:
            entered.append(1)
        assert release.wait(timeout=5)
        return run_simulation(**kwargs)

    def release_after_refusal() -> None:
        deadline = time.time() + 4
        while time.time() < deadline:
            with lock:
                refused = len(refusals) >= 1
            if refused:
                release.set()
                return
        release.set()

    import psyfi_api.routers.simulate as simulate_router

    original = simulate_router.run_simulation
    job_store.try_acquire_slot = counting_acquire  # type: ignore[method-assign]
    simulate_router.run_simulation = blocking  # type: ignore[assignment]
    watcher = threading.Thread(target=release_after_refusal, daemon=True)
    watcher.start()
    try:

        async def _five() -> list[int]:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                responses = await asyncio.gather(
                    *[client.post("/api/v1/simulate/", json=_SIM) for _ in range(5)]
                )
            return [response.status_code for response in responses]

        codes = anyio.run(_five)
    finally:
        simulate_router.run_simulation = original
        job_store.try_acquire_slot = real_acquire  # type: ignore[method-assign]
        release.set()
        watcher.join(timeout=2)

    assert codes.count(200) == 4
    assert codes.count(429) == 1
    assert len(entered) == 4
    assert _free_slots() == 4


def test_full_slots_refuse_sync_snapshot_and_job() -> None:
    held = _hold(4)
    assert held == 4
    try:
        with TestClient(app) as client:
            sync = client.post("/simulate/", json=_SIM)
            snapshot = client.post("/api/v1/visualize/scene-snapshot", json=_SNAP)
            quiet = client.post(
                "/api/v1/visualize/scene-snapshot",
                json={**_SNAP, "include_simulation": False},
            )
            job = client.post("/api/v1/jobs/simulate", json=_SIM)
        assert sync.status_code == 429
        assert snapshot.status_code == 429
        assert quiet.status_code == 200
        assert job.status_code == 429
        detail = "Too many concurrent simulation jobs; retry after one completes"
        assert sync.json()["detail"] == detail
        assert snapshot.json()["detail"] == detail
        assert job.json()["detail"] == detail
    finally:
        _release(held)

    with TestClient(app) as client:
        opened = client.post("/api/v1/visualize/scene-snapshot", json=_SNAP)
    assert opened.status_code == 200
    assert _free_slots() == 4
