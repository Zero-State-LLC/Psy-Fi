"""Compute backends. ``numpy`` is the canonical reference (the psyfi_core engines).

Any accelerator backend is an *experimental port* that must be validated against
the reference with a declared tolerance before its timings are reported. A
backend's result is never a substitute for the Python authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from psyfi_core.engines import (
    ConsciousnessOmegaParams,
    NormalizationParams,
    apply_normalization,
    evolve_consciousness_omega,
)


class ComputeBackend(Protocol):
    name: str
    device: str
    canonical: bool

    def evolve(self, field: np.ndarray, params: ConsciousnessOmegaParams) -> np.ndarray: ...

    def normalize(self, field: np.ndarray, params: NormalizationParams) -> np.ndarray: ...

    def synchronize(self) -> None: ...

    def describe(self) -> dict[str, Any]: ...


@dataclass
class NumpyBackend:
    """The canonical path: calls psyfi_core engines unchanged."""

    name: str = "numpy"
    device: str = "cpu"
    canonical: bool = True

    def evolve(self, field: np.ndarray, params: ConsciousnessOmegaParams) -> np.ndarray:
        return evolve_consciousness_omega(field, params, None)

    def normalize(self, field: np.ndarray, params: NormalizationParams) -> np.ndarray:
        return apply_normalization(field, params)

    def synchronize(self) -> None:
        return None

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "device": self.device, "canonical": True, "dtype": "complex64"}


class BackendUnavailable(ImportError):
    pass


class TorchBackend:
    """Kuramoto evolution + divisive normalization in torch (CUDA, MPS, or CPU).

    Mirrors ``evolve_consciousness_omega`` (symmetric coupling, 4-neighbour
    ``roll``) and ``apply_normalization`` (zero-padded box filter) in float32.
    """

    canonical = False

    def __init__(self, device: str | None = None) -> None:
        try:
            import torch  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise BackendUnavailable("torch is not installed") from exc
        self.torch = torch
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = device
        self.name = f"torch-{device}"

    def _to(self, arr: np.ndarray):
        t = self.torch
        return t.from_numpy(np.ascontiguousarray(arr)).to(self.device)

    def evolve(self, field: np.ndarray, params: ConsciousnessOmegaParams) -> np.ndarray:
        if params.coupling_type != "symmetric":
            raise NotImplementedError("torch backend implements symmetric coupling only")
        t = self.torch
        height, width = field.shape
        phases = self._to(np.angle(field).astype(np.float32))
        magnitudes = self._to(np.abs(field).astype(np.float32))
        y = t.arange(height, device=self.device, dtype=t.float32).reshape(-1, 1)
        depth_factor = y / float(height)
        normalized_mag = magnitudes / (magnitudes.max() + 1e-8)
        natural_freq = (
            float(params.natural_freq_base)
            + float(params.freq_depth_scale) * depth_factor
            + float(params.freq_brightness_scale) * normalized_mag
        )
        cur = phases.clone()
        k = float(params.coupling_strength)
        dt = float(params.dt)
        for _ in range(params.steps):
            coupling = (
                t.sin(t.roll(cur, 1, 0) - cur)
                + t.sin(t.roll(cur, -1, 0) - cur)
                + t.sin(t.roll(cur, 1, 1) - cur)
                + t.sin(t.roll(cur, -1, 1) - cur)
            ) / 4.0
            cur = cur + dt * (natural_freq + k * coupling)
        cur = t.atan2(t.sin(cur), t.cos(cur))
        real = (magnitudes * t.cos(cur)).detach().cpu().numpy()
        imag = (magnitudes * t.sin(cur)).detach().cpu().numpy()
        return (real + 1j * imag).astype(np.complex64)

    def normalize(self, field: np.ndarray, params: NormalizationParams) -> np.ndarray:
        t = self.torch
        F = t.nn.functional
        magnitudes = self._to(np.abs(field).astype(np.float32))
        phases = self._to(np.angle(field).astype(np.float32))
        activation = magnitudes ** float(params.P)
        size = 2 * int(params.surround_radius) + 1
        kernel = t.ones((1, 1, size, size), device=self.device, dtype=t.float32) / float(size * size)
        padded = F.pad(activation[None, None], (params.surround_radius,) * 4, mode="constant", value=0.0)
        surround = F.conv2d(padded, kernel)[0, 0]
        denominator = 1.0 + float(params.V) * (surround ** float(params.P))
        normalized = activation / denominator
        real = (normalized * t.cos(phases)).detach().cpu().numpy()
        imag = (normalized * t.sin(phases)).detach().cpu().numpy()
        return (real + 1j * imag).astype(np.complex64)

    def synchronize(self) -> None:
        t = self.torch
        if self.device == "cuda":
            t.cuda.synchronize()
        elif self.device == "mps" and hasattr(t, "mps"):
            t.mps.synchronize()

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "device": self.device, "canonical": False, "torch": self.torch.__version__, "dtype": "float32"}


def make_backend(name: str = "numpy") -> ComputeBackend:
    name = (name or "numpy").lower()
    if name == "numpy":
        return NumpyBackend()
    if name == "torch":
        return TorchBackend()
    if name.startswith("torch-"):
        return TorchBackend(device=name.split("-", 1)[1])
    raise BackendUnavailable(f"unknown compute backend {name!r}")


def available_backend_names() -> dict[str, bool]:
    out = {"numpy": True}
    try:
        TorchBackend()
        out["torch"] = True
    except BackendUnavailable:
        out["torch"] = False
    return out


def validate_against_reference(
    backend: ComputeBackend,
    field: np.ndarray,
    params: ConsciousnessOmegaParams,
    norm_params: NormalizationParams,
) -> dict[str, Any]:
    """Max abs error of the backend vs the canonical NumPy pipeline on ``field``."""
    from psyfi_bench.determinism import max_abs_error

    ref = NumpyBackend()
    ref_evolved = ref.evolve(field, params)
    ref_norm = ref.normalize(ref_evolved, norm_params)
    got_evolved = backend.evolve(field, params)
    got_norm = backend.normalize(got_evolved, norm_params)
    return {
        "backend": backend.describe(),
        "evolve_max_abs_error": max_abs_error(ref_evolved, got_evolved),
        "normalize_max_abs_error": max_abs_error(ref_norm, got_norm),
        "pipeline_max_abs_error": max_abs_error(ref_norm, backend.normalize(got_evolved, norm_params)),
    }
