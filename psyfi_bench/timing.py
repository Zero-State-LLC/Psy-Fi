"""Wall/CPU timing and memory probes for one callable.

Timing repeats never run under tracemalloc (it perturbs allocation cost); the
runner performs one separate memory probe. RSS deltas use ``resource`` and are
reported in bytes on every platform.
"""

from __future__ import annotations

import gc
import platform
import resource
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


def _ru_maxrss_bytes() -> int:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports kilobytes.
    return int(raw) if platform.system() == "Darwin" else int(raw) * 1024


@dataclass
class Timing(Generic[T]):
    wall_ms: float
    cpu_ms: float
    result: T
    rss_before_bytes: int | None = None
    rss_peak_delta_bytes: int | None = None
    tracemalloc_peak_bytes: int | None = None
    tracemalloc_current_bytes: int | None = None


def time_call(fn: Callable[[], T], *, collect_gc: bool = True) -> Timing[T]:
    """Time one call. ``gc.collect`` beforehand reduces GC noise between repeats."""
    if collect_gc:
        gc.collect()
    rss_before = _ru_maxrss_bytes()
    t0_wall = time.perf_counter_ns()
    t0_cpu = time.process_time_ns()
    result = fn()
    cpu_ms = (time.process_time_ns() - t0_cpu) / 1e6
    wall_ms = (time.perf_counter_ns() - t0_wall) / 1e6
    rss_after = _ru_maxrss_bytes()
    return Timing(
        wall_ms=wall_ms,
        cpu_ms=cpu_ms,
        result=result,
        rss_before_bytes=rss_before,
        rss_peak_delta_bytes=max(0, rss_after - rss_before),
    )


def memory_probe(fn: Callable[[], T]) -> Timing[T]:
    """One run under tracemalloc. Timing from this run is NOT representative; report memory only."""
    gc.collect()
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()
    tracemalloc.reset_peak()
    rss_before = _ru_maxrss_bytes()
    t0 = time.perf_counter_ns()
    result = fn()
    wall_ms = (time.perf_counter_ns() - t0) / 1e6
    current, peak = tracemalloc.get_traced_memory()
    if not was_tracing:
        tracemalloc.stop()
    return Timing(
        wall_ms=wall_ms,
        cpu_ms=float("nan"),
        result=result,
        rss_before_bytes=rss_before,
        rss_peak_delta_bytes=max(0, _ru_maxrss_bytes() - rss_before),
        tracemalloc_peak_bytes=int(peak),
        tracemalloc_current_bytes=int(current),
    )


class Deadline:
    """Cooperative timeout. ``should_cancel`` fits the ABX engine's callback contract."""

    def __init__(self, timeout_s: float | None, external_cancel: Callable[[], bool] | None = None) -> None:
        self.timeout_s = timeout_s
        self._start = time.perf_counter()
        self._external = external_cancel
        self.expired = False
        self.cancelled = False

    def should_cancel(self) -> bool:
        if self._external is not None and self._external():
            self.cancelled = True
            return True
        if self.timeout_s is not None and (time.perf_counter() - self._start) > self.timeout_s:
            self.expired = True
            return True
        return False

    def remaining_s(self) -> float | None:
        if self.timeout_s is None:
            return None
        return max(0.0, self.timeout_s - (time.perf_counter() - self._start))

    def check(self) -> None:
        """Raise ``TimeoutError`` or ``InterruptedError`` when the deadline tripped."""
        if self.should_cancel():
            if self.cancelled:
                raise InterruptedError("benchmark cancelled")
            raise TimeoutError(f"benchmark stage exceeded {self.timeout_s}s")


def utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_id(prefix: str = "run") -> str:
    import secrets

    return f"{prefix}_{int(time.time())}_{secrets.token_hex(4)}"


def as_json_safe(value: Any) -> Any:
    """Make numpy scalars/arrays JSON-serializable."""
    import numpy as np

    if isinstance(value, dict):
        return {str(k): as_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value
