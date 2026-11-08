"""Vision-bench corpus and field scoring. No network."""

from __future__ import annotations

import json
import math

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
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        return _parse_failure()
    return {"parse_ok": True, "mode": mode, "intensity": value, "error": None}


from psyfi_core.experiences.parameter_mapper import map_parameters

FIELD_MODES = ("open", "attractor", "void", "power")


def _parameters(mode: str, intensity: float) -> dict[str, float]:
    field = map_parameters(
        substance="lsd",
        mode=mode,
        intensity=float(intensity),
        seed=42,
        phase_t=0.4,
        quality_tier="balanced",
    )
    return dict(field.parameters)


def _displacement(left: dict[str, float], right: dict[str, float]) -> float:
    keys = set(left) | set(right)
    total = 0.0
    for key in keys:
        total += abs(float(left.get(key, 0.0)) - float(right.get(key, 0.0)))
    return round(total, 4)


def field_metrics(
    oracle_mode: str,
    oracle_intensity: float,
    model_mode: str,
    model_intensity: float,
) -> dict[str, object]:
    oracle_field = _parameters(oracle_mode, oracle_intensity)
    model_field = _parameters(model_mode, model_intensity)
    steps = {
        mode: _displacement(oracle_field, _parameters(mode, oracle_intensity))
        for mode in FIELD_MODES
        if mode != oracle_mode
    }
    distance = _displacement(oracle_field, model_field)
    return {
        "field_displacement": distance,
        "mode_steps": steps,
        "within_mode_step": distance <= min(steps.values()),
    }


from psyfi_core.experiences.catalog import load_catalog
from psyfi_core.visualization.image_seed import rank_experiences


def positive_lsd_candidates() -> list[dict]:
    recipes = load_catalog().list(substance="lsd", valence="positive")
    if not recipes:
        raise ValueError("positive LSD catalog is empty")
    return list(recipes)


def _top(features: dict, mode: str, candidates: list[dict]) -> tuple[str, float]:
    ranked = rank_experiences(candidates, features, mode, top_n=1)
    if not ranked:
        raise ValueError("catalog rank is empty")
    return str(ranked[0]["experience_id"]), float(ranked[0]["score"])


def catalog_metrics(
    features: dict,
    oracle_mode: str,
    model_mode: str,
    candidates: list[dict],
) -> dict[str, object]:
    oracle_id, oracle_score = _top(features, oracle_mode, candidates)
    model_id, model_score = _top(features, model_mode, candidates)
    return {
        "catalog_oracle_id": oracle_id,
        "catalog_oracle_score": oracle_score,
        "catalog_model_id": model_id,
        "catalog_model_score": model_score,
        "catalog_switch": oracle_id != model_id,
    }


CAPTURE_SCHEMA = "psyfi.vision_bench_capture.v1"
REPORT_SCHEMA = "psyfi.vision_bench_report.v1"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _check_receipt(receipt: dict) -> list[dict]:
    _require(isinstance(receipt, dict), "receipt must be an object")
    _require(receipt.get("schema") == CAPTURE_SCHEMA, "bad schema")
    caller = receipt.get("caller")
    _require(isinstance(caller, dict), "bad caller")
    _require(caller.get("mode") == CALLER_MODE, "bad caller mode")
    intensity = caller.get("intensity")
    _require(isinstance(intensity, (int, float)) and not isinstance(intensity, bool), "bad caller intensity")
    _require(abs(float(intensity) - CALLER_INTENSITY) < 1e-9, "bad caller intensity")
    _require(receipt.get("prompt_revision") == PROMPT_REVISION, "bad prompt revision")
    images = receipt.get("images")
    _require(isinstance(images, list), "bad images")
    ids = [row.get("id") for row in images if isinstance(row, dict)]
    _require(ids == list(IMAGE_ORDER), "bad image ids")
    return images


def _blank_failure(image_id: str, latency_ms: object) -> dict[str, object]:
    return {
        "id": image_id,
        "oracle_mode": None,
        "oracle_intensity": None,
        "model_mode": None,
        "model_intensity": None,
        "mode_match": False,
        "field_displacement": None,
        "mode_steps": None,
        "within_mode_step": False,
        "catalog_oracle_id": None,
        "catalog_oracle_score": None,
        "catalog_model_id": None,
        "catalog_model_score": None,
        "catalog_switch": False,
        "latency_ms": latency_ms,
        "parse_ok": False,
    }


def score_receipt(receipt: dict, *, candidates: list[dict] | None = None) -> dict:
    images = _check_receipt(receipt)
    if candidates is None:
        candidates = positive_lsd_candidates()
    elif len(candidates) == 0:
        raise ValueError("positive LSD catalog is empty")
    by_id = dict(build_corpus())
    rows: list[dict[str, object]] = []
    for row in images:
        image_id = str(row["id"])
        latency_ms = row.get("latency_ms")
        if row.get("parse_ok") is not True:
            rows.append(_blank_failure(image_id, latency_ms))
            continue
        oracle = oracle_for(by_id[image_id])
        model_mode = str(row["mode"])
        model_intensity = float(row["intensity"])
        distance = field_metrics(
            str(oracle["mode"]),
            float(oracle["intensity"]),
            model_mode,
            model_intensity,
        )
        catalog = catalog_metrics(
            analyze_features(by_id[image_id]),
            str(oracle["mode"]),
            model_mode,
            candidates,
        )
        rows.append(
            {
                "id": image_id,
                "oracle_mode": oracle["mode"],
                "oracle_intensity": oracle["intensity"],
                "model_mode": model_mode,
                "model_intensity": model_intensity,
                "mode_match": model_mode == oracle["mode"],
                "latency_ms": latency_ms,
                "parse_ok": True,
                **distance,
                **catalog,
            }
        )
    complete = all(
        row["parse_ok"] is True and isinstance(row["field_displacement"], float)
        for row in rows
    )
    return {"schema": REPORT_SCHEMA, "complete": complete, "images": rows}
