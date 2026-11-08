"""Output integrity: exact and quantized digests, NaN/Inf accounting, cross-run comparison."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

import numpy as np

from psyfi_bench.schemas import DeterminismRecord


def _as_real_stack(arr: np.ndarray) -> np.ndarray:
    a = np.ascontiguousarray(arr)
    if np.iscomplexobj(a):
        return np.ascontiguousarray(np.stack([a.real, a.imag], axis=-1)).astype(np.float64)
    return a.astype(np.float64)


def exact_digest(arr: np.ndarray) -> str:
    """SHA-256 of the raw bytes plus dtype/shape. Same-machine bitwise reproducibility."""
    a = np.ascontiguousarray(arr)
    h = hashlib.sha256()
    h.update(str(a.dtype).encode())
    h.update(str(a.shape).encode())
    h.update(a.tobytes())
    return h.hexdigest()


def quantized_digest(arr: np.ndarray, quantization: float = 1e-5) -> str:
    """SHA-256 after rounding to ``quantization``. Cross-platform reproducibility reference."""
    real = _as_real_stack(arr)
    finite = np.nan_to_num(real, nan=np.float64(1e300), posinf=np.float64(1e300), neginf=np.float64(-1e300))
    q = np.round(np.clip(finite / quantization, -9.0e18, 9.0e18)).astype(np.int64)
    h = hashlib.sha256()
    h.update(str(real.shape).encode())
    h.update(repr(quantization).encode())
    h.update(q.tobytes())
    return h.hexdigest()


def nan_inf_counts(arr: np.ndarray) -> tuple[int, int]:
    real = _as_real_stack(arr)
    return int(np.isnan(real).sum()), int(np.isinf(real).sum())


def record_for(arr: np.ndarray, *, quantization: float = 1e-5, reference: str | None = None) -> DeterminismRecord:
    nan_count, inf_count = nan_inf_counts(arr)
    q = quantized_digest(arr, quantization)
    return DeterminismRecord(
        exact_sha256=exact_digest(arr),
        quantized_sha256=q,
        quantization=quantization,
        reference_match=(q == reference) if reference else None,
        nan_count=nan_count,
        inf_count=inf_count,
    )


def compare_repeats(records: Sequence[DeterminismRecord]) -> dict[str, Any]:
    """Across repeats: were outputs bitwise identical? quantized-identical?"""
    exact = {r.exact_sha256 for r in records if r.exact_sha256}
    quant = {r.quantized_sha256 for r in records if r.quantized_sha256}
    return {
        "repeats": len(records),
        "bitwise_identical_across_repeats": len(exact) <= 1,
        "quantized_identical_across_repeats": len(quant) <= 1,
        "distinct_exact": len(exact),
        "distinct_quantized": len(quant),
    }


def max_abs_error(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = _as_real_stack(a), _as_real_stack(b)
    if ra.shape != rb.shape:
        return float("inf")
    return float(np.max(np.abs(ra - rb))) if ra.size else 0.0
