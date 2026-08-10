"""Explicit backend policy for parity-proven native kernels."""

from collections.abc import Callable
from typing import Literal

import numpy as np

Backend = Literal["auto", "reference", "native"]


class NativeBackendUnavailable(RuntimeError):
    """Raised when native execution was explicitly required but is unavailable."""


def _load_native() -> Callable[..., np.ndarray] | None:
    try:
        from psyfi_native import consciousness_omega as native_kernel
    except ImportError:
        return None
    return native_kernel


def native_available() -> bool:
    return _load_native() is not None


def consciousness_omega(
    field: np.ndarray,
    *,
    coupling_type: str,
    coupling_strength: float,
    natural_freq_base: float,
    freq_depth_scale: float,
    freq_brightness_scale: float,
    steps: int,
    dt: float,
    reference: Callable[[], np.ndarray],
    backend: Backend = "auto",
) -> np.ndarray:
    if backend not in {"auto", "reference", "native"}:
        raise ValueError(f"Unsupported consciousness_omega backend: {backend}")
    # N0 promotion is deliberately rejected until exact protected-output parity
    # and the benchmark gate have both been demonstrated.
    if backend in {"auto", "reference"}:
        return reference()
    kernel = _load_native()
    if kernel is None:
        raise NativeBackendUnavailable(
            "psyfi-native is not installed; use backend='reference' or install it with maturin"
        )
    return kernel(
        field,
        coupling_type,
        coupling_strength,
        natural_freq_base,
        freq_depth_scale,
        freq_brightness_scale,
        steps,
        dt,
    )
