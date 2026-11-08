"""Tests for interruptible simulation and job cancellation."""

import time

from fastapi.testclient import TestClient

from psyfi_api.jobs import SimulationJob
from psyfi_api.main import app
from psyfi_core.abx_core.errors import SimulationCancelled
from psyfi_core.engines import ConsciousnessOmegaParams, evolve_consciousness_omega
import numpy as np


def test_evolve_respects_should_cancel() -> None:
    field = np.ones((8, 8), dtype=np.complex64)
    params = ConsciousnessOmegaParams(steps=50, dt=0.1)
    calls = {"n": 0}

    def should_cancel() -> bool:
        calls["n"] += 1
        return calls["n"] > 3

    try:
        evolve_consciousness_omega(field, params, should_cancel=should_cancel)
        assert False, "expected SimulationCancelled"
    except SimulationCancelled as exc:
        assert "cancelled" in str(exc).lower()


def test_job_create_complete_and_cancel() -> None:
    with TestClient(app) as client:
        # Canonical v1 job path
        created = client.post(
            "/api/v1/jobs/simulate",
            json={"width": 24, "height": 24, "steps": 8, "seed": 3},
        )
        assert created.status_code == 200
        job_id = created.json()["id"]

        deadline = time.time() + 5
        final = None
        while time.time() < deadline:
            poll = client.get(f"/api/v1/jobs/{job_id}")
            assert poll.status_code == 200
            final = poll.json()
            if final["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.05)

        assert final is not None
        assert final["status"] == "completed"
        assert final["result"]["seed"] == 3
        assert final["result"]["api_version"] == "v1"

        # Legacy mirror still works for cancel flows
        long_job = client.post(
            "/api/jobs/simulate",
            json={"width": 64, "height": 64, "steps": 400, "seed": 1},
        )
        long_id = long_job.json()["id"]
        cancelled = client.delete(f"/api/jobs/{long_id}")
        assert cancelled.status_code == 200

        deadline = time.time() + 5
        status = None
        while time.time() < deadline:
            status = client.get(f"/api/jobs/{long_id}").json()["status"]
            if status in {"cancelled", "completed", "failed"}:
                break
            time.sleep(0.05)
        assert status == "cancelled"


def test_finalize_after_run_prefers_cancel_over_completed() -> None:
    """Cancel that lands after the worker returns must not publish completed."""
    job = SimulationJob(id="job_race", status="running", request={"width": 8})
    job.cancel_event.set()
    outcome = job.finalize_after_run({"seed": 1, "valence": 0.1})
    assert outcome == "cancelled"
    assert job.status == "cancelled"
    assert job.result is None


def test_job_create_rejects_when_concurrent_slots_exhausted() -> None:
    from psyfi_api.jobs import JobStore

    store = JobStore(max_retained=16, max_concurrent=1)
    assert store.try_acquire_slot() is True
    assert store.try_acquire_slot() is False
    store.release_slot()
    assert store.try_acquire_slot() is True
    store.release_slot()


def test_job_store_evicts_terminal_jobs_over_retention() -> None:
    from psyfi_api.jobs import JobStore

    store = JobStore(max_retained=8, max_concurrent=4)
    for i in range(12):
        job = store.create({"width": 8, "height": 8, "steps": 1, "n": i})
        with job._lock:
            job.status = "completed"
            job.result = {"n": i}
            job.touch()
    assert len(store.list_recent(limit=50)) <= 8


def test_service_worker_root_scope_headers() -> None:
    with TestClient(app) as client:
        res = client.get("/sw.js")
        assert res.status_code == 200
        assert res.headers.get("service-worker-allowed") == "/"
        assert "psyfi-shell-v44" in res.text
        assert "isGpuRoute" in res.text


def test_ready_and_telemetry_gates() -> None:
    with TestClient(app) as client:
        ready = client.get("/ready")
        assert ready.status_code == 200
        payload = ready.json()
        assert payload["status"] == "ready"
        assert payload["api_version"] == "v1"
        assert payload["checks"]["presets_loaded"] is True
        assert payload["checks"]["icon_192"] is True

        assert client.get("/api/v1/ready").status_code == 200

        status = client.get("/api/v1/telemetry/status").json()
        assert status["server_enabled"] is False
        assert status["active"] is False

        opted = client.post("/api/v1/telemetry/opt-in", json={"opt_in": True}).json()
        assert opted["client_opt_in"] is True
        assert opted["active"] is False  # server flag still off

        # Legacy telemetry mirror remains available
        legacy = client.get("/api/telemetry/status")
        assert legacy.status_code == 200
