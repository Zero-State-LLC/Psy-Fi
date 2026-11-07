"""Vision-bench corpus and field scoring. No network."""

from __future__ import annotations

import json

import numpy as np

from psyfi_core.visualization.image_seed import analyze_features, recommend_mode_intensity

BENCH_PROMPT = (
    "Look at this image. Choose one mode: attractor when the picture is full of "
    "dense edges, void when it is dim and flat, power when it is bright and strong, "
    "open otherwise. Choose an intensity from 0 to 1. Reply with JSON only, with "
    "the keys mode and intensity. No other text."
)
PROMPT_REVISION = 1
CALLER_MODE = "open"
CALLER_INTENSITY = 0.7
IMAGE_ORDER = ("void", "power", "attractor", "caller")
ORACLE_MODE = {
    "void": "void",
    "power": "power",
    "attractor": "attractor",
    "caller": "open",
}


def _rgba(gray: np.ndarray) -> np.ndarray:
    rgba = np.zeros((64, 64, 4), np.float32)
    rgba[..., 0] = gray
    rgba[..., 1] = gray
    rgba[..., 2] = gray
    rgba[..., 3] = 1.0
    return rgba


def build_corpus() -> list[tuple[str, np.ndarray]]:
    void = _rgba(np.full((64, 64), 0.5, np.float32))
    power_gray = np.zeros((64, 64), np.float32)
    power_gray[:, 32:] = 1.0
    columns = np.arange(64, dtype=np.int32)
    attract_row = ((columns // 4) % 2).astype(np.float32)
    attractor = _rgba(np.broadcast_to(attract_row, (64, 64)).copy())
    caller_gray = np.full((64, 64), 0.35, np.float32)
    caller_gray[:, 30:34] = 0.55
    caller_gray[:, 34:] = 0.75
    return [
        ("void", void),
        ("power", _rgba(power_gray)),
        ("attractor", attractor),
        ("caller", _rgba(caller_gray)),
    ]


def oracle_for(rgba: np.ndarray) -> dict[str, float | str]:
    features = analyze_features(rgba)
    recommended = recommend_mode_intensity(features, CALLER_MODE, CALLER_INTENSITY)
    return {"mode": str(recommended["mode"]), "intensity": float(recommended["intensity"])}


def assert_oracle_lock() -> None:
    for image_id, rgba in build_corpus():
        got = str(oracle_for(rgba)["mode"])
        if got != ORACLE_MODE[image_id]:
            raise RuntimeError(f"oracle lock failed: {image_id} returned {got}")


MODES = frozenset({"attractor", "void", "power", "open"})


def _parse_failure() -> dict[str, object]:
    return {"parse_ok": False, "mode": None, "intensity": None, "error": "parse"}


def parse_model_content(text: str) -> dict[str, object]:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return _parse_failure()
    if not isinstance(doc, dict):
        return _parse_failure()
    mode = doc.get("mode")
    intensity = doc.get("intensity")
    if not isinstance(mode, str) or mode not in MODES:
        return _parse_failure()
    if isinstance(intensity, bool) or not isinstance(intensity, (int, float)):
        return _parse_failure()
    value = float(intensity)
    if value < 0.0 or value > 1.0:
        return _parse_failure()
    return {"parse_ok": True, "mode": mode, "intensity": value, "error": None}
