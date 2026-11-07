"""In-process simulation job store for cancellable async runs."""

from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

JobStatus = Literal["queued", "running", "completed", "cancelled", "failed"]

# Bound in-memory retention / concurrency so job spam cannot OOM the process.
MAX_JOBS_RETAINED = 64
MAX_CONCURRENT_JOBS = 4
TERMINAL_STATUSES = frozenset({"completed", "cancelled", "failed"})
CONCURRENT_LIMIT_DETAIL = "Too many concurrent simulation jobs; retry after one completes"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class SimulationJob:
    """Mutable job record shared between API threads."""

    id: str
    status: JobStatus = "queued"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    request: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def touch(self) -> None:
        self.updated_at = _utc_now()

    def request_cancel(self) -> None:
        with self._lock:
            self.cancel_event.set()
            if self.status in {"queued", "running"}:
                self.status = "cancelled"
                self.error = self.error or "Simulation cancelled"
                self.result = None
                self.touch()

    def finalize_after_run(self, result: dict[str, Any]) -> JobStatus:
        """Commit completed vs cancelled under the same lock as request_cancel.

        Prevents a TOCTOU where cancel lands after `cancel_event` was checked
        false but before status is written, which previously left cancelled
        jobs as `completed` with a full result.
        """
        with self._lock:
            if self.cancel_event.is_set():
                self.status = "cancelled"
                self.error = self.error or "Simulation cancelled"
                self.result = None
                self.touch()
                return "cancelled"
            self.result = result
            self.status = "completed"
            self.touch()
            return "completed"


class JobStore:
    """Thread-safe in-memory job registry (single-process deployments)."""

    def __init__(
        self,
        *,
        max_retained: int = MAX_JOBS_RETAINED,
        max_concurrent: int = MAX_CONCURRENT_JOBS,
    ) -> None:
        self._jobs: dict[str, SimulationJob] = {}
        self._lock = threading.Lock()
        self._max_retained = max(8, int(max_retained))
        self._max_concurrent = max(1, int(max_concurrent))
        self._worker_slots = threading.Semaphore(self._max_concurrent)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status in {"queued", "running"})

    def try_acquire_slot(self) -> bool:
        """Non-blocking acquire of a worker slot. Caller must release_slot()."""
        return self._worker_slots.acquire(blocking=False)

    def release_slot(self) -> None:
        self._worker_slots.release()

    def create(self, request: dict[str, Any]) -> SimulationJob:
        job = SimulationJob(id=f"job_{uuid.uuid4().hex[:12]}", request=request)
        with self._lock:
            self._jobs[job.id] = job
            self._evict_locked()
        return job

    def get(self, job_id: str) -> SimulationJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> list[SimulationJob]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return jobs[:limit]

    def _evict_locked(self) -> None:
        """Drop oldest terminal jobs when over retention; drop results of stale terminals."""
        if len(self._jobs) <= self._max_retained:
            return
        terminal = sorted(
            (j for j in self._jobs.values() if j.status in TERMINAL_STATUSES),
            key=lambda j: j.updated_at,
        )
        overflow = len(self._jobs) - self._max_retained
        for job in terminal[:overflow]:
            del self._jobs[job.id]


job_store = JobStore()


class SimulationSlotUnavailable(Exception):
    """The shared four simulation slots are already held."""


@contextmanager
def simulation_slot():
    """Take one shared simulation slot and release it when the run ends."""
    if not job_store.try_acquire_slot():
        raise SimulationSlotUnavailable(CONCURRENT_LIMIT_DETAIL)
    try:
        yield
    finally:
        job_store.release_slot()
