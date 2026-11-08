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


SUMMARY_BLOCKS = 8


def reference_summary(arr: np.ndarray, blocks: int = SUMMARY_BLOCKS) -> dict[str, Any]:
    """Continuous summary of an output array for tolerance-based cross-platform comparison.

    A quantized digest flips whenever one element straddles a rounding boundary, so it only
    certifies "same floating-point platform". These statistics move smoothly with the data, so a
    different BLAS/SIMD path on another machine produces small errors that a tolerance can judge.
    """
    a = np.ascontiguousarray(arr)
    mag = np.abs(a).astype(np.float64)
    finite = np.isfinite(mag)
    mag_f = mag[finite] if finite.any() else np.zeros(1)
    out: dict[str, Any] = {
        "mean_abs": float(mag_f.mean()),
        "std_abs": float(mag_f.std()),
        "max_abs": float(mag_f.max()),
    }
    if np.iscomplexobj(a):
        nz = a[(mag > 0) & finite]
        out["order_parameter"] = float(np.abs(np.mean(nz / np.abs(nz)))) if nz.size else 0.0
    else:
        real = a.astype(np.float64)
        out["mean"] = float(real[np.isfinite(real)].mean()) if np.isfinite(real).any() else 0.0
    grid = mag if mag.ndim == 2 else mag.reshape(mag.shape[0], -1) if mag.ndim > 2 else mag.reshape(1, -1)
    h, w = grid.shape
    bh, bw = max(1, h // blocks), max(1, w // blocks)
    hh, ww = (h // bh) * bh, (w // bw) * bw
    blk = grid[:hh, :ww].reshape(hh // bh, bh, ww // bw, bw).mean(axis=(1, 3))
    out["block_mean_abs"] = [round(float(v), 9) for v in blk.ravel()]
    out["blocks"] = [int(blk.shape[0]), int(blk.shape[1])]
    return out


def summary_error(summary: dict[str, Any], reference: dict[str, Any]) -> float:
    """Max abs error between two summaries (inf when shapes or keys disagree)."""
    err = 0.0
    for key, ref in reference.items():
        if key == "blocks":
            if list(summary.get("blocks", [])) != list(ref):
                return float("inf")
            continue
        got = summary.get(key)
        if got is None:
            return float("inf")
        a, b = np.asarray(got, dtype=np.float64), np.asarray(ref, dtype=np.float64)
        if a.shape != b.shape:
            return float("inf")
        err = max(err, float(np.max(np.abs(a - b))) if a.size else 0.0)
    return err


def record_for(
    arr: np.ndarray,
    *,
    quantization: float = 1e-5,
    reference: str | None = None,
    reference_summary_lock: dict[str, Any] | None = None,
    reference_atol: float = 1e-3,
) -> DeterminismRecord:
    nan_count, inf_count = nan_inf_counts(arr)
    q = quantized_digest(arr, quantization)
    within: bool | None = None
    max_err: float | None = None
    if reference_summary_lock:
        max_err = summary_error(reference_summary(arr), reference_summary_lock)
        within = bool(max_err <= reference_atol)
    return DeterminismRecord(
        exact_sha256=exact_digest(arr),
        quantized_sha256=q,
        quantization=quantization,
        reference_match=(q == reference) if reference else None,
        reference_within_tolerance=within,
        reference_max_abs_error=max_err,
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
