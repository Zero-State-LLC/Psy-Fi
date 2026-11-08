"""Python port of ``packages/psyfi-gpu-renderer/src/goldens/softPresent.ts``.

Same primitives, same order, same rounding (JS ``Math.round`` = floor(x + 0.5)
for the non-negative values used here). Primitive fills are vectorized over
their bounding box; pixels inside one primitive never overlap, so the result
equals the sequential TypeScript loop. Not a stand-in for a WebGPU frame: it is
the CPU execution class of the render family and the FieldLoop CPU path.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

PF_PAPER = "#0a0e14"
PF_CYAN = "#3ee7f2"
PIXEL_GOLDEN_SIZE = 64


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _js_round(x: float) -> int:
    return int(math.floor(x + 0.5))


def parse_hex_color(hex_str: str) -> tuple[int, int, int]:
    s = str(hex_str or "").replace("#", "").strip()
    if len(s) >= 6:
        try:
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        except ValueError:
            pass
    return 99, 243, 232


def _num_or(value: Any, fallback: float) -> float:
    """JS ``Number(v) || fallback``: NaN/0/undefined fall back."""
    try:
        if value is None or isinstance(value, bool):
            return fallback
        f = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(f) or f == 0.0:
        return fallback
    return f


class SoftFrame:
    """RGBA8 canvas with JS-equivalent alpha compositing."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.rgba = np.zeros((size, size, 4), dtype=np.float64)  # kept as float until finish()
        pr, pg, pb = parse_hex_color(PF_PAPER)
        self.rgba[..., 0] = pr
        self.rgba[..., 1] = pg
        self.rgba[..., 2] = pb
        self.rgba[..., 3] = 255

    def _blend(self, ys: np.ndarray, xs: np.ndarray, r: float, g: float, b: float, a: float) -> None:
        if ys.size == 0:
            return
        sr, sg, sb, sa = r / 255.0, g / 255.0, b / 255.0, a / 255.0
        dst = self.rgba[ys, xs]
        dr, dg, db, da = dst[:, 0] / 255.0, dst[:, 1] / 255.0, dst[:, 2] / 255.0, dst[:, 3] / 255.0
        out_a = sa + da * (1.0 - sa)
        keep = out_a > 0
        if not np.any(keep):
            return
        ys, xs = ys[keep], xs[keep]
        dr, dg, db, da, out_a = dr[keep], dg[keep], db[keep], da[keep], out_a[keep]
        nr = np.floor(((sr * sa + dr * da * (1.0 - sa)) / out_a) * 255.0 + 0.5)
        ng = np.floor(((sg * sa + dg * da * (1.0 - sa)) / out_a) * 255.0 + 0.5)
        nb = np.floor(((sb * sa + db * da * (1.0 - sa)) / out_a) * 255.0 + 0.5)
        na = np.floor(out_a * 255.0 + 0.5)
        self.rgba[ys, xs, 0] = nr
        self.rgba[ys, xs, 1] = ng
        self.rgba[ys, xs, 2] = nb
        self.rgba[ys, xs, 3] = na

    def set_px(self, x: int, y: int, r: float, g: float, b: float, a: float = 255) -> None:
        if x < 0 or y < 0 or x >= self.size or y >= self.size:
            return
        self._blend(np.array([y]), np.array([x]), r, g, b, a)

    def fill_circle(self, cx: float, cy: float, radius: float, r: float, g: float, b: float, a: float) -> None:
        r2 = radius * radius
        x0 = int(math.floor(cx - radius))
        x1 = int(math.ceil(cx + radius))
        y0 = int(math.floor(cy - radius))
        y1 = int(math.ceil(cy + radius))
        xs = np.arange(x0, x1 + 1)
        ys = np.arange(y0, y1 + 1)
        if xs.size == 0 or ys.size == 0:
            return
        gx, gy = np.meshgrid(xs, ys)
        dx = gx + 0.5 - cx
        dy = gy + 0.5 - cy
        inside = (dx * dx + dy * dy) <= r2
        inside &= (gx >= 0) & (gy >= 0) & (gx < self.size) & (gy < self.size)
        self._blend(gy[inside], gx[inside], r, g, b, a)

    def stroke_line(self, x0: float, y0: float, x1: float, y1: float, r: float, g: float, b: float, a: float) -> None:
        steps = max(2, int(math.ceil(math.hypot(x1 - x0, y1 - y0))))
        for i in range(steps + 1):
            t = i / steps
            self.fill_circle(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, 1.1, r, g, b, a)

    def finish(self) -> np.ndarray:
        return np.clip(self.rgba, 0, 255).astype(np.uint8)


def project(pos: tuple[float, float, float], w: int) -> tuple[float, float, float]:
    x = (pos[0] * 0.85 + 1) * 0.5 * (w - 1)
    y = (1 - (pos[1] * 1.2 + pos[2] * 0.35 + 1) * 0.5) * (w - 1)
    depth = _clamp01(0.55 + pos[2] * 0.2)
    return x, y, depth


def crystal_items(nodes: list[dict[str, Any]], engines: dict[str, Any]) -> list[tuple[tuple[float, float, float], float]]:
    lattice = float(engines.get("entity_lattice", 0.1) if engines.get("entity_lattice") is not None else 0.1)
    items: list[tuple[tuple[float, float, float], float]] = []
    for ni, n in enumerate(nodes):
        budget = min(48.0, _num_or(n.get("instance_budget"), 32.0))
        seed = _num_or(n.get("seed"), float(ni))
        count = max(4, int(math.floor(budget * (0.25 + lattice))))
        for i in range(count):
            a = seed * 0.01 + i * 1.618
            r = 0.35 + (i % 7) * 0.08
            items.append(((math.cos(a) * r, ((i % 5) - 2) * 0.12, math.sin(a) * r), 0.04 + (i % 3) * 0.015))
    return items


def soft_present_snapshot(snapshot: dict[str, Any], size: int = PIXEL_GOLDEN_SIZE) -> np.ndarray:
    """Raster one ``psyfi.scene_snapshot.v1`` document to an (size, size, 4) uint8 array."""
    frame = SoftFrame(size)
    pf = snapshot.get("parameter_field") or {}
    palette = pf.get("palette") or {}
    pr, pg, pb = parse_hex_color(str(palette.get("tracers") or PF_CYAN))
    intensity = pf.get("intensity")
    intensity = 0.5 if intensity is None else float(intensity)
    neutral = bool(pf.get("neutral_view"))
    safety = snapshot.get("safety") or pf.get("safety") or {}
    atten_raw = safety.get("attenuator", safety.get("max_flash_strength", 0.35))
    try:
        atten = _clamp01(float(atten_raw))
    except (TypeError, ValueError):
        atten = 0.35

    mix = 0.72 if neutral else 0.25 + atten * 0.45
    grey = 110
    pr = _js_round(pr * (1 - mix) + grey * mix)
    pg = _js_round(pg * (1 - mix) + grey * mix)
    pb = _js_round(pb * (1 - mix) + grey * mix)

    engines = pf.get("engines") or {}
    assets = snapshot.get("assets") or {}
    has_ktx2 = len(assets.get("ktx2") or []) > 0 or len(assets.get("images") or []) > 0
    procedural = snapshot.get("procedural") or {}

    if has_ktx2 and not neutral:
        y0 = int(math.floor(size * 0.78))
        xs = np.arange(size)
        for y in range(y0, size):
            t = (y - y0) / max(1, size - y0)
            frame._blend(np.full(size, y), xs, min(255, pr + 20), min(255, pg + 10), max(0, pb - 10), _js_round(55 + t * 70))

    if not neutral:
        for pos, scale in crystal_items(procedural.get("crystals") or [], engines):
            x, y, depth = project(pos, size)
            rad = max(1.2, scale * size * 2.8)
            a = _js_round((140 + intensity * 80) * depth)
            frame.fill_circle(x, y, rad, pr, pg, pb, a)

        for i, m in enumerate(procedural.get("metaballs") or []):
            seed = _num_or(m.get("seed"), float(i))
            cx = ((math.sin(seed * 0.41) + 1) * 0.5) * (size - 1)
            cy = ((math.cos(seed * 0.27) + 1) * 0.5) * (size - 1)
            rad = 2.2 + _num_or(m.get("radius"), 0.2) * size * 0.08
            frame.fill_circle(cx, cy, rad, max(0, pr - 30), pg, min(255, pb + 35), 110)

        for i, rb in enumerate(procedural.get("ribbons") or []):
            seed = _num_or(rb.get("seed"), float(i))
            x0 = ((math.sin(seed * 0.13) + 1) * 0.5) * (size - 1)
            y0 = ((math.cos(seed * 0.17) + 1) * 0.5) * (size - 1)
            x1 = ((math.sin(seed * 0.29 + 1.7) + 1) * 0.5) * (size - 1)
            y1 = ((math.cos(seed * 0.23 + 0.9) + 1) * 0.5) * (size - 1)
            frame.stroke_line(x0, y0, x1, y1, pr, min(255, pg + 40), pb, 150)

        flow = engines.get("flow_field")
        flow = 0.0 if flow is None else float(flow)
        if flow > 0.05:
            n = min(24, max(4, int(math.floor(flow * 28))))
            for i in range(n):
                a = i * 2.399 + intensity
                rr = 0.15 + (i % 5) * 0.06
                x, y, _ = project((math.cos(a) * rr, (i % 4) * 0.05, math.sin(a) * rr), size)
                frame.fill_circle(x, y, 0.9, pr, pg, pb, 160)

        for i, g in enumerate(procedural.get("glyphs") or []):
            seed = _num_or(g.get("seed"), float(i))
            x = ((math.sin(seed * 0.37) + 1) * 0.5) * (size - 1)
            y = ((math.cos(seed * 0.19) + 1) * 0.5) * (size - 1)
            frame.fill_circle(x, y, 1.6, min(255, pr + 40), pg, max(0, pb - 20), 200)
    else:
        ys, xs = np.mgrid[0:size, 0:size]
        dx = (xs / size - 0.5) * 2
        dy = (ys / size - 0.5) * 2
        v = np.clip(1 - np.sqrt(dx * dx + dy * dy), 0, 1)
        alpha = np.floor(40 * v + 0.5)
        # Per-pixel alpha varies, so blend pixel groups by alpha value (order within a group is irrelevant).
        for a_val in np.unique(alpha):
            mask = alpha == a_val
            frame._blend(ys[mask], xs[mask], 40, 44, 48, float(a_val))

    return frame.finish()


def rgba_histogram(rgba: np.ndarray, bins: int = 16) -> list[int]:
    """16 bins per channel for R, G, B (length 48), matching pixelMetrics.ts."""
    out: list[int] = []
    for c in range(3):
        channel = rgba[..., c].astype(np.int64) >> 4
        out.extend(int(v) for v in np.bincount(np.minimum(channel.ravel(), bins - 1), minlength=bins))
    return out


def mean_rgb(rgba: np.ndarray) -> tuple[float, float, float]:
    flat = rgba.reshape(-1, 4).astype(np.float64)
    return float(flat[:, 0].mean()), float(flat[:, 1].mean()), float(flat[:, 2].mean())


def sha256_rgba(rgba: np.ndarray) -> str:
    import hashlib

    return hashlib.sha256(np.ascontiguousarray(rgba, dtype=np.uint8).tobytes()).hexdigest()
