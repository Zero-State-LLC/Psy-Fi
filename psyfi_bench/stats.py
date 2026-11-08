"""Statistics for repeated measurements. Pure functions, deterministic bootstrap.

Percentiles use linear interpolation (numpy default). Confidence intervals are
percentile bootstraps with a seeded generator so a report is reproducible.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from psyfi_bench.schemas import Statistics


def _clean(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray([float(v) for v in values], dtype=np.float64)
    return arr[np.isfinite(arr)]


def percentile(values: Sequence[float], p: float) -> float:
    arr = _clean(values)
    if arr.size == 0:
        return float("nan")
    return float(np.percentile(arr, p))


def mad(values: Sequence[float]) -> float:
    """Median absolute deviation (unscaled)."""
    arr = _clean(values)
    if arr.size == 0:
        return float("nan")
    med = np.median(arr)
    return float(np.median(np.abs(arr - med)))


def coefficient_of_variation(values: Sequence[float]) -> float | None:
    arr = _clean(values)
    if arr.size < 2:
        return None
    mean = float(arr.mean())
    if mean <= 0:
        return None
    return float(arr.std(ddof=1) / mean)


def bootstrap_ci(
    values: Sequence[float],
    statistic: str = "mean",
    *,
    resamples: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float] | None:
    """Percentile bootstrap CI. Returns None when fewer than 2 samples."""
    arr = _clean(values)
    if arr.size < 2:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(resamples, arr.size))
    samples = arr[idx]
    if statistic == "mean":
        stats = samples.mean(axis=1)
    elif statistic == "median":
        stats = np.median(samples, axis=1)
    else:
        raise ValueError(f"unknown statistic {statistic!r}")
    alpha = (1.0 - level) / 2.0
    lo = float(np.percentile(stats, 100 * alpha))
    hi = float(np.percentile(stats, 100 * (1 - alpha)))
    return (lo, hi)


def summarize(
    values: Sequence[float],
    *,
    unit: str = "",
    resamples: int = 2000,
    seed: int = 0,
) -> Statistics:
    arr = _clean(values)
    if arr.size == 0:
        raise ValueError("summarize needs at least one finite value")
    std = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
    return Statistics(
        n=int(arr.size),
        unit=unit,
        mean=float(arr.mean()),
        median=float(np.median(arr)),
        min=float(arr.min()),
        max=float(arr.max()),
        std=std,
        cv=coefficient_of_variation(arr),
        mad=mad(arr),
        p50=percentile(arr, 50),
        p90=percentile(arr, 90),
        p95=percentile(arr, 95),
        p99=percentile(arr, 99),
        ci95_mean=bootstrap_ci(arr, "mean", resamples=resamples, seed=seed),
        ci95_median=bootstrap_ci(arr, "median", resamples=resamples, seed=seed),
        bootstrap={"method": "percentile", "resamples": resamples, "seed": seed, "level": 0.95}
        if arr.size > 1
        else None,
    )


# --- frame-time specific -----------------------------------------------------


def fps_from_frame_ms(frame_ms: Sequence[float]) -> float:
    arr = _clean(frame_ms)
    arr = arr[arr > 0]
    if arr.size == 0:
        return 0.0
    return float(1000.0 / arr.mean())


def low_1pct_fps(frame_ms: Sequence[float]) -> float:
    """1% low fps: fps at the 99th percentile of frame time (the slow tail)."""
    arr = _clean(frame_ms)
    arr = arr[arr > 0]
    if arr.size == 0:
        return 0.0
    return float(1000.0 / np.percentile(arr, 99))


def frame_pacing(frame_ms: Sequence[float]) -> dict[str, float]:
    """Pacing quality: jitter (std of successive deltas), stutter count/ratio (frame > 2x median)."""
    arr = _clean(frame_ms)
    if arr.size < 2:
        return {"jitter_ms": 0.0, "stutter_frames": 0, "stutter_ratio": 0.0}
    deltas = np.diff(arr)
    med = float(np.median(arr))
    stutter = int(np.count_nonzero(arr > 2.0 * med))
    return {
        "jitter_ms": float(deltas.std(ddof=1)) if deltas.size > 1 else 0.0,
        "stutter_frames": stutter,
        "stutter_ratio": float(stutter / arr.size),
    }


def sustained_drift(frame_ms: Sequence[float]) -> dict[str, float]:
    """Thermal/sustained drift: least-squares slope (ms per 1000 frames) and last/first quartile ratio."""
    arr = _clean(frame_ms)
    if arr.size < 8:
        return {"slope_ms_per_1000_frames": 0.0, "last_first_quartile_ratio": 1.0, "r2": 0.0}
    x = np.arange(arr.size, dtype=np.float64)
    slope, intercept = np.polyfit(x, arr, 1)
    pred = slope * x + intercept
    ss_res = float(((arr - pred) ** 2).sum())
    ss_tot = float(((arr - arr.mean()) ** 2).sum()) or 1e-12
    q = arr.size // 4
    first = float(arr[:q].mean())
    last = float(arr[-q:].mean())
    return {
        "slope_ms_per_1000_frames": float(slope * 1000.0),
        "last_first_quartile_ratio": float(last / first) if first > 0 else 1.0,
        "r2": float(1.0 - ss_res / ss_tot),
    }


# --- scaling ----------------------------------------------------------------


def scaling_exponent(sizes: Sequence[float], times: Sequence[float]) -> dict[str, float]:
    """Log-log least squares: time ~ size^k. Returns k, intercept, r2."""
    s = np.asarray(sizes, dtype=np.float64)
    t = np.asarray(times, dtype=np.float64)
    mask = (s > 0) & (t > 0) & np.isfinite(s) & np.isfinite(t)
    s, t = s[mask], t[mask]
    if s.size < 2:
        return {"exponent": float("nan"), "r2": float("nan"), "n": int(s.size)}
    ls, lt = np.log(s), np.log(t)
    k, b = np.polyfit(ls, lt, 1)
    pred = k * ls + b
    ss_res = float(((lt - pred) ** 2).sum())
    ss_tot = float(((lt - lt.mean()) ** 2).sum()) or 1e-12
    return {"exponent": float(k), "log_intercept": float(b), "r2": float(1.0 - ss_res / ss_tot), "n": int(s.size)}


def within_tolerance(a: float, b: float, *, rel: float = 0.0, abs_tol: float = 0.0) -> bool:
    if not (math.isfinite(a) and math.isfinite(b)):
        return False
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b)))
