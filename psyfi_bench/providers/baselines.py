"""Calibration baselines. A bench score means nothing without them.

* oracle    — answers with the reference label (ceiling, FDE 0).
* constant  — always the same answer (what a model that ignores the input scores).
* random    — seeded uniform mode and intensity.
* heuristic — the instrument's own photometric recommendation (``recommend_mode_intensity``).
"""

from __future__ import annotations

import json
import time
from typing import Any

import numpy as np

from psyfi_bench.providers.base import ModelRequest, ModelResponse
from psyfi_core.visualization.image_seed import analyze_features, recommend_mode_intensity

MODES = ("open", "attractor", "void", "power")


class OracleProvider:
    name = "oracle"
    model = "oracle"
    locality = "baseline"

    def complete(self, request: ModelRequest) -> ModelResponse:
        t0 = time.perf_counter()
        ref = request.metadata.get("reference") or {}
        text = json.dumps({"mode": ref.get("mode", "open"), "intensity": float(ref.get("intensity", 0.5))})
        return ModelResponse(text=text, latency_ms=(time.perf_counter() - t0) * 1000, provider=self.name, model=self.model, locality=self.locality)

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "model": self.model, "locality": self.locality, "note": "reads the reference label; ceiling"}


class ConstantProvider:
    name = "constant"
    locality = "baseline"

    def __init__(self, mode: str = "open", intensity: float = 0.5) -> None:
        self.mode_value = mode
        self.intensity_value = float(intensity)
        self.model = f"constant:{mode}:{intensity}"

    def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(text=json.dumps({"mode": self.mode_value, "intensity": self.intensity_value}), latency_ms=0.0, provider=self.name, model=self.model, locality=self.locality)

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "model": self.model, "locality": self.locality}


class RandomProvider:
    name = "random"
    locality = "baseline"

    def __init__(self, seed: int = 0) -> None:
        self.rng = np.random.default_rng(seed)
        self.model = f"random:{seed}"

    def complete(self, request: ModelRequest) -> ModelResponse:
        mode = MODES[int(self.rng.integers(0, len(MODES)))]
        return ModelResponse(text=json.dumps({"mode": mode, "intensity": round(float(self.rng.uniform(0, 1)), 4)}), latency_ms=0.0, provider=self.name, model=self.model, locality=self.locality)

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "model": self.model, "locality": self.locality}


class HeuristicProvider:
    """Photometric baseline: the existing image-seed recommendation on the rendered pixels."""

    name = "heuristic"
    model = "recommend_mode_intensity"
    locality = "baseline"

    def complete(self, request: ModelRequest) -> ModelResponse:
        t0 = time.perf_counter()
        if not request.images:
            text = json.dumps({"mode": "open", "intensity": 0.7})
        else:
            rgba = request.images[0].astype(np.float32) / 255.0
            features = analyze_features(rgba)
            rec = recommend_mode_intensity(features, "open", 0.7)
            text = json.dumps({"mode": rec["mode"], "intensity": float(rec["intensity"])})
        return ModelResponse(text=text, latency_ms=(time.perf_counter() - t0) * 1000, provider=self.name, model=self.model, locality=self.locality)

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "model": self.model, "locality": self.locality, "note": "psyfi_core.visualization.image_seed.recommend_mode_intensity on the image"}
