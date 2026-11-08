"""Image fidelity metrics between two RGBA8 frames (same device, different tiers / sizes)."""

from __future__ import annotations

import base64
import io
from typing import Any

import numpy as np


def to_gray(rgba: np.ndarray) -> np.ndarray:
    rgb = rgba[..., :3].astype(np.float64) / 255.0
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def block_resize(rgba: np.ndarray, size: int) -> np.ndarray:
    """Area-average resize to size x size (uint8). Exact when the ratio is an integer."""
    h, w = rgba.shape[:2]
    if h == size and w == size:
        return rgba
    ys = np.linspace(0, h, size + 1).astype(int)
    xs = np.linspace(0, w, size + 1).astype(int)
    out = np.zeros((size, size, rgba.shape[2]), dtype=np.float64)
    for i in range(size):
        for j in range(size):
            block = rgba[ys[i] : max(ys[i] + 1, ys[i + 1]), xs[j] : max(xs[j] + 1, xs[j + 1])]
            out[i, j] = block.reshape(-1, rgba.shape[2]).mean(axis=0)
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    fa = a[..., :3].astype(np.float64) / 255.0
    fb = b[..., :3].astype(np.float64) / 255.0
    return float(np.sqrt(np.mean((fa - fb) ** 2)))


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    e = rmse(a, b)
    if e <= 0:
        return float("inf")
    return float(20.0 * np.log10(1.0 / e))


def histogram_l1(a: np.ndarray, b: np.ndarray, bins: int = 16) -> float:
    """Normalized L1 between per-channel 16-bin histograms (0 = identical, 2 = disjoint per channel)."""
    total = 0.0
    n = a.shape[0] * a.shape[1]
    for c in range(3):
        ha = np.bincount(np.minimum(a[..., c].astype(np.int64).ravel() >> 4, bins - 1), minlength=bins) / n
        hb = np.bincount(np.minimum(b[..., c].astype(np.int64).ravel() >> 4, bins - 1), minlength=bins) / n
        total += float(np.abs(ha - hb).sum())
    return total / 3.0


def ssim(a: np.ndarray, b: np.ndarray, *, window: int = 7) -> float:
    """Mean SSIM on luminance with a uniform window (Wang et al. 2004 constants)."""
    from scipy.ndimage import uniform_filter

    x = to_gray(a)
    y = to_gray(b)
    c1 = (0.01) ** 2
    c2 = (0.03) ** 2
    mu_x = uniform_filter(x, window)
    mu_y = uniform_filter(y, window)
    sxx = uniform_filter(x * x, window) - mu_x**2
    syy = uniform_filter(y * y, window) - mu_y**2
    sxy = uniform_filter(x * y, window) - mu_x * mu_y
    num = (2 * mu_x * mu_y + c1) * (2 * sxy + c2)
    den = (mu_x**2 + mu_y**2 + c1) * (sxx + syy + c2)
    return float(np.mean(num / den))


def compare(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    """All fidelity metrics; ``b`` is resized to ``a`` when sizes differ."""
    if a.shape[:2] != b.shape[:2]:
        b = block_resize(b, a.shape[0])
    return {
        "rmse": rmse(a, b),
        "psnr_db": psnr(a, b),
        "ssim": ssim(a, b),
        "histogram_l1": histogram_l1(a, b),
        "mean_rgb_delta": float(np.abs(a[..., :3].astype(np.float64).mean(axis=(0, 1)) - b[..., :3].astype(np.float64).mean(axis=(0, 1))).mean()),
    }


def decode_png_base64(data: str) -> np.ndarray:
    from PIL import Image

    raw = base64.b64decode(data.split(",", 1)[-1])
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    return np.asarray(img, dtype=np.uint8)


def encode_png_base64(rgba: np.ndarray) -> str:
    from PIL import Image

    img = Image.fromarray(np.ascontiguousarray(rgba, dtype=np.uint8), mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def perturb(rgba: np.ndarray, kind: str, *, seed: int = 0, amount: float = 0.02) -> np.ndarray:
    """Presentation perturbations that preserve the field: noise, brightness, flip, resize."""
    rng = np.random.default_rng(seed)
    out = rgba.astype(np.float64)
    if kind == "noise":
        out[..., :3] += rng.normal(0.0, amount * 255.0, size=out[..., :3].shape)
    elif kind == "brightness_up":
        out[..., :3] *= 1.0 + amount
    elif kind == "brightness_down":
        out[..., :3] *= 1.0 - amount
    elif kind == "flip_h":
        out = out[:, ::-1]
    elif kind == "flip_v":
        out = out[::-1, :]
    elif kind == "identity":
        pass
    else:
        raise ValueError(f"unknown perturbation {kind!r}")
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def summarize_frame(rgba: np.ndarray) -> dict[str, Any]:
    from psyfi_bench.render.soft_raster import mean_rgb, rgba_histogram, sha256_rgba

    return {
        "sha256": sha256_rgba(rgba),
        "mean_rgb": list(mean_rgb(rgba)),
        "histogram": rgba_histogram(rgba),
        "width": int(rgba.shape[1]),
        "height": int(rgba.shape[0]),
    }
