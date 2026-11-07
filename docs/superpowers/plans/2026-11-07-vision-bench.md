# Vision-model bench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture one configured vision model's mode and intensity on four synthetic images, then score how far that reading moves a `ParameterField` and whether it would offer a different catalog experience.

**Architecture:** Pure corpus, parse, field distance, catalog rank, and receipt scoring live in `psyfi_core/visualization/vision_bench.py`. A local script posts once per image through the existing one-shot client and writes a raw receipt. CI recomputes the report and never calls the provider.

**Tech Stack:** Python 3.10+, NumPy, the existing `map_parameters` and `load_catalog`, pytest. No new dependency. No new HTTP route.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-11-07-vision-bench-design.md`. Do not implement GPU frame time, hardware scaling, a public route, login, a rate limit, an AI Gateway, or a catalog reload.
- Do not change `read_image`, the caption prompt, `psyfi_api/routers/experiences.py`, the service worker, or the frozen API ids.
- Do not create `fixtures/qa/vision_bench_capture.v1.json` in the implementation. A person creates it by running the script.
- No model-id literal in `vision_bench.py` or `scripts/capture_vision_bench.py`. Tests may use `nvidia/bench-test`.
- No API key in source, receipts, or stdout.
- `prompt_revision` is `1`. Bench prompt text is exactly: `Look at this image. Choose one mode: attractor when the picture is full of dense edges, void when it is dim and flat, power when it is bright and strong, open otherwise. Choose an intensity from 0 to 1. Reply with JSON only, with the keys mode and intensity. No other text.`
- Caller mode `open`, caller intensity `0.7`. Substance `lsd`. Field seed `42`. `phase_t` `0.4`. Quality tier `balanced`.
- Headline metric is `field_displacement`. `catalog_switch` sits beside it. `mode_match` is diagnostic. There is no intensity band. Disagreement does not fail CI.
- Image order is `void`, `power`, `attractor`, `caller`.
- Leave `.github/PULL_REQUEST_TEMPLATE.md` unstaged. It is a macOS case collision. Do not commit `.trail/cache/` or `graft/`.
- Run tests from the repository root with the package importable: `python -m pytest -q tests/test_vision_bench.py`.

## File structure

- Create `psyfi_core/visualization/vision_bench.py`. Corpus, oracle, parse, field metrics, catalog metrics, receipt check, report. No HTTP.
- Create `scripts/capture_vision_bench.py`. Preflight, four posts, atomic receipt write, printed report. Thin `main`.
- Create `tests/test_vision_bench.py`. All bench tests.
- Do not modify the caption route or add a fixture file.

---

### Task 1: Corpus and oracle lock

**Files:**
- Create: `psyfi_core/visualization/vision_bench.py`
- Test: `tests/test_vision_bench.py`

**Interfaces:**
- Consumes: `analyze_features` and `recommend_mode_intensity` from `psyfi_core.visualization.image_seed`.
- Produces:
  - `BENCH_PROMPT: str`
  - `PROMPT_REVISION: int` = `1`
  - `CALLER_MODE: str` = `"open"`
  - `CALLER_INTENSITY: float` = `0.7`
  - `IMAGE_ORDER: tuple[str, ...]` = `("void", "power", "attractor", "caller")`
  - `ORACLE_MODE: dict[str, str]` = `{"void": "void", "power": "power", "attractor": "attractor", "caller": "open"}`
  - `build_corpus() -> list[tuple[str, numpy.ndarray]]` in that id order. Each array is float32 `64×64×4`, alpha `1`.
  - `oracle_for(rgba: numpy.ndarray) -> dict` with keys `mode: str` and `intensity: float`.
  - `assert_oracle_lock() -> None`. Raises `RuntimeError` whose message starts with `oracle lock failed:` when a mode is wrong.

- [ ] **Step 1: Write the failing test**

Create `tests/test_vision_bench.py`:

```python
"""Vision-bench corpus, field distance, and local capture."""

from __future__ import annotations

import numpy as np

from psyfi_core.visualization.image_seed import analyze_features
from psyfi_core.visualization.vision_bench import (
    BENCH_PROMPT,
    IMAGE_ORDER,
    ORACLE_MODE,
    PROMPT_REVISION,
    assert_oracle_lock,
    build_corpus,
    oracle_for,
)


def test_oracle_lock_matches_the_four_branches() -> None:
    corpus = build_corpus()
    assert [image_id for image_id, _ in corpus] == list(IMAGE_ORDER)
    assert PROMPT_REVISION == 1
    assert BENCH_PROMPT.startswith("Look at this image.")
    assert "0.55" not in BENCH_PROMPT
    for image_id, rgba in corpus:
        assert rgba.shape == (64, 64, 4)
        assert rgba.dtype == np.float32
        features = analyze_features(rgba)
        energy = float(features["energy"])
        contrast = float(features["contrast"])
        edges = float(features["edge_density"])
        attractor = edges > 0.55 and contrast > 0.45
        void = energy < 0.28 and contrast < 0.3
        power = energy > 0.6
        if image_id == "attractor":
            assert attractor
        elif image_id == "void":
            assert void and not attractor
        elif image_id == "power":
            assert power and not attractor
        else:
            assert image_id == "caller"
            assert not attractor and not void and not power
        assert oracle_for(rgba)["mode"] == ORACLE_MODE[image_id]
    assert_oracle_lock()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_vision_bench.py::test_oracle_lock_matches_the_four_branches -v`

Expected: FAIL with `ModuleNotFoundError` for `psyfi_core.visualization.vision_bench`.

- [ ] **Step 3: Write minimal implementation**

Create `psyfi_core/visualization/vision_bench.py`:

```python
"""Vision-bench corpus and field scoring. No network."""

from __future__ import annotations

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_vision_bench.py::test_oracle_lock_matches_the_four_branches -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add psyfi_core/visualization/vision_bench.py tests/test_vision_bench.py
git commit -m "Lock the vision-bench corpus to the four field modes."
```

---

### Task 2: Parse the model reply

**Files:**
- Modify: `psyfi_core/visualization/vision_bench.py`
- Test: `tests/test_vision_bench.py`

**Interfaces:**
- Consumes: nothing from Task 1 beyond the module.
- Produces: `parse_model_content(text: str) -> dict` with keys `parse_ok: bool`, `mode: str | None`, `intensity: float | None`, `error: str | None`. Success has `error` None. Failure has `error` `"parse"`, `mode` None, and `intensity` None.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_vision_bench.py`:

```python
from psyfi_core.visualization.vision_bench import parse_model_content


def test_parse_accepts_only_the_four_modes_and_a_unit_interval() -> None:
    good = parse_model_content('{"mode": "void", "intensity": 0.5, "extra": 1}')
    assert good == {"parse_ok": True, "mode": "void", "intensity": 0.5, "error": None}
    assert parse_model_content('{"mode": "open", "intensity": 0}')["parse_ok"] is True
    assert parse_model_content('{"mode": "power", "intensity": 1}')["parse_ok"] is True
    for text in (
        "a dim field",
        "```json\n{\"mode\": \"void\", \"intensity\": 0.5}\n```",
        '{"mode": "Open", "intensity": 0.5}',
        '{"mode": "void", "intensity": "0.5"}',
        '{"mode": "void", "intensity": 70}',
        '{"mode": "void"}',
        '{"intensity": 0.5}',
        "[]",
    ):
        parsed = parse_model_content(text)
        assert parsed["parse_ok"] is False
        assert parsed["mode"] is None
        assert parsed["intensity"] is None
        assert parsed["error"] == "parse"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_vision_bench.py::test_parse_accepts_only_the_four_modes_and_a_unit_interval -v`

Expected: FAIL with `ImportError` for `parse_model_content`.

- [ ] **Step 3: Write minimal implementation**

Append to `psyfi_core/visualization/vision_bench.py`:

```python
import json

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
```

Put `import json` with the other imports. Do not accept a JSON string intensity. Do not strip markdown fences. Do not lowercase `Open`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_vision_bench.py::test_parse_accepts_only_the_four_modes_and_a_unit_interval -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add psyfi_core/visualization/vision_bench.py tests/test_vision_bench.py
git commit -m "Parse the vision-bench reply as mode and intensity."
```

---

### Task 3: Field displacement

**Files:**
- Modify: `psyfi_core/visualization/vision_bench.py`
- Test: `tests/test_vision_bench.py`

**Interfaces:**
- Consumes: `build_corpus`, `oracle_for`.
- Produces: `field_metrics(oracle_mode: str, oracle_intensity: float, model_mode: str, model_intensity: float) -> dict` with `field_displacement: float`, `mode_steps: dict[str, float]`, `within_mode_step: bool`.
- Field inputs, every call: `map_parameters(substance="lsd", seed=42, phase_t=0.4, quality_tier="balanced")`. Do not pass `experience`, `image_hints`, or `modulators`.
- Distance is `round(sum of absolute differences of field.parameters, 4)`. A missing key counts as `0.0`. Palette, engines, safety, and hash are not in the sum.
- `mode_steps` has the three modes other than `oracle_mode`. Each step uses `oracle_intensity`.

- [ ] **Step 1: Write the failing test**

Append:

```python
from psyfi_core.visualization.vision_bench import field_metrics


def test_field_displacement_uses_mode_steps_as_the_ruler() -> None:
    rgba = dict(build_corpus())["void"]
    oracle = oracle_for(rgba)
    same = field_metrics(
        str(oracle["mode"]),
        float(oracle["intensity"]),
        str(oracle["mode"]),
        float(oracle["intensity"]),
    )
    assert same["field_displacement"] == 0.0
    assert same["within_mode_step"] is True
    assert set(same["mode_steps"]) == {"open", "attractor", "power"}
    moved = field_metrics(
        str(oracle["mode"]),
        float(oracle["intensity"]),
        "power",
        float(oracle["intensity"]),
    )
    assert moved["field_displacement"] == moved["mode_steps"]["power"]
    assert moved["field_displacement"] > 0.0
    assert moved["within_mode_step"] is (
        moved["field_displacement"] <= min(moved["mode_steps"].values())
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_vision_bench.py::test_field_displacement_uses_mode_steps_as_the_ruler -v`

Expected: FAIL with `ImportError` for `field_metrics`.

- [ ] **Step 3: Write minimal implementation**

Append, importing `map_parameters` from `psyfi_core.experiences.parameter_mapper`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_vision_bench.py::test_field_displacement_uses_mode_steps_as_the_ruler -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add psyfi_core/visualization/vision_bench.py tests/test_vision_bench.py
git commit -m "Measure vision-bench answers as field displacement."
```

---

### Task 4: Catalog switch

**Files:**
- Modify: `psyfi_core/visualization/vision_bench.py`
- Test: `tests/test_vision_bench.py`

**Interfaces:**
- Consumes: `analyze_features`, `rank_experiences` from `psyfi_core.visualization.image_seed`, `load_catalog` from `psyfi_core.experiences.catalog`.
- Produces:
  - `positive_lsd_candidates() -> list[dict]`. Calls `load_catalog().list(substance="lsd", valence="positive")`. Raises `ValueError` with message `positive LSD catalog is empty` when that list is empty.
  - `catalog_metrics(features: dict, oracle_mode: str, model_mode: str, candidates: list[dict]) -> dict` with `catalog_oracle_id`, `catalog_oracle_score`, `catalog_model_id`, `catalog_model_score`, `catalog_switch: bool`.
  - Raises `ValueError` `catalog rank is empty` when `rank_experiences` returns no row.

- [ ] **Step 1: Write the failing test**

Append:

```python
from psyfi_core.visualization.vision_bench import catalog_metrics, positive_lsd_candidates


def _pair() -> list[dict]:
    return [
        {
            "id": "exp_void",
            "title": "Void Soft",
            "modes": ["void"],
            "visual_recipe": {
                "mode_default": "void",
                "primary_engines": ["void_expansion"],
                "parameter_bias": {"void_bias": 0.9, "pattern_complexity": 0.1},
                "palette": {"energy": 0.15},
            },
        },
        {
            "id": "exp_attractor",
            "title": "Attractor",
            "modes": ["attractor"],
            "visual_recipe": {
                "mode_default": "attractor",
                "primary_engines": ["kaleidoscope"],
                "parameter_bias": {"pattern_complexity": 0.7, "attractor_bias": 0.8},
                "palette": {"energy": 0.7},
            },
        },
    ]


def test_catalog_switch_follows_the_mode() -> None:
    features = analyze_features(dict(build_corpus())["void"])
    same = catalog_metrics(features, "void", "void", _pair())
    assert same["catalog_switch"] is False
    assert same["catalog_oracle_id"] == same["catalog_model_id"] == "exp_void"
    swapped = catalog_metrics(features, "void", "attractor", _pair())
    assert swapped["catalog_oracle_id"] == "exp_void"
    assert swapped["catalog_model_id"] == "exp_attractor"
    assert swapped["catalog_switch"] is True


def test_positive_lsd_catalog_is_loaded() -> None:
    recipes = positive_lsd_candidates()
    assert recipes
    assert all(recipe.get("id") for recipe in recipes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_vision_bench.py::test_catalog_switch_follows_the_mode tests/test_vision_bench.py::test_positive_lsd_catalog_is_loaded -v`

Expected: FAIL with `ImportError` for `catalog_metrics`.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_vision_bench.py::test_catalog_switch_follows_the_mode tests/test_vision_bench.py::test_positive_lsd_catalog_is_loaded -v`

Expected: PASS. On the void image, suggested mode `void` ranks `exp_void` and suggested mode `attractor` ranks `exp_attractor`. Do not change `rank_experiences`.

- [ ] **Step 5: Commit**

```bash
git add psyfi_core/visualization/vision_bench.py tests/test_vision_bench.py
git commit -m "Report whether a vision-bench mode changes the catalog pick."
```

---

### Task 5: Score a receipt

**Files:**
- Modify: `psyfi_core/visualization/vision_bench.py`
- Test: `tests/test_vision_bench.py`

**Interfaces:**
- Consumes: `build_corpus`, `oracle_for`, `field_metrics`, `catalog_metrics`, `positive_lsd_candidates`, `CAPTURE` constants below.
- Produces:
  - `CAPTURE_SCHEMA = "psyfi.vision_bench_capture.v1"`
  - `REPORT_SCHEMA = "psyfi.vision_bench_report.v1"`
  - `score_receipt(receipt: dict, *, candidates: list[dict] | None = None) -> dict`
  - When `candidates` is None, use `positive_lsd_candidates()`.
  - Raises `ValueError` for a bad schema, an id missing or out of order, caller mode other than `open`, caller intensity farther than `1e-9` from `0.7`, or `prompt_revision` other than `1`.
  - A `parse_ok` false row does not raise. Its `field_displacement`, `mode_steps`, and catalog ids are None. `within_mode_step` and `catalog_switch` are false. `mode_match` is false.
  - `complete` is true only when every row has `parse_ok` true and a numeric `field_displacement`.

- [ ] **Step 1: Write the failing test**

Append:

```python
import pytest

from psyfi_core.visualization.vision_bench import CAPTURE_SCHEMA, REPORT_SCHEMA, score_receipt


def _receipt(images: list[dict]) -> dict:
    return {
        "schema": CAPTURE_SCHEMA,
        "date": "2026-11-07",
        "model": "nvidia/bench-test",
        "caller": {"mode": "open", "intensity": 0.7},
        "prompt_revision": 1,
        "images": images,
    }


def _matched_images() -> list[dict]:
    rows = []
    for image_id, rgba in build_corpus():
        oracle = oracle_for(rgba)
        rows.append(
            {
                "id": image_id,
                "mode": oracle["mode"],
                "intensity": oracle["intensity"],
                "latency_ms": 3,
                "parse_ok": True,
            }
        )
    return rows


def test_score_receipt_reports_zero_distance_for_the_oracle() -> None:
    report = score_receipt(_receipt(_matched_images()), candidates=_pair())
    assert report["schema"] == REPORT_SCHEMA
    assert report["complete"] is True
    assert [row["id"] for row in report["images"]] == list(IMAGE_ORDER)
    assert all(row["field_displacement"] == 0.0 for row in report["images"])
    assert all(row["mode_match"] is True for row in report["images"])


def test_score_receipt_keeps_a_parse_failure_as_a_result() -> None:
    rows = _matched_images()
    rows[0] = {
        "id": "void",
        "mode": None,
        "intensity": None,
        "latency_ms": 3,
        "parse_ok": False,
        "error": "parse",
    }
    report = score_receipt(_receipt(rows), candidates=_pair())
    assert report["complete"] is False
    failed = report["images"][0]
    assert failed["field_displacement"] is None
    assert failed["catalog_oracle_id"] is None
    assert failed["within_mode_step"] is False
    assert failed["catalog_switch"] is False


def test_score_receipt_rejects_machinery_errors() -> None:
    good = _receipt(_matched_images())
    bad_schema = dict(good, schema="other")
    bad_caller = dict(good, caller={"mode": "void", "intensity": 0.7})
    bad_intensity = dict(good, caller={"mode": "open", "intensity": 0.7 + 1e-6})
    bad_revision = dict(good, prompt_revision=2)
    bad_ids = _receipt(list(reversed(_matched_images())))
    for receipt in (bad_schema, bad_caller, bad_intensity, bad_revision, bad_ids):
        with pytest.raises(ValueError):
            score_receipt(receipt, candidates=_pair())
    with pytest.raises(ValueError, match="positive LSD catalog is empty"):
        score_receipt(good, candidates=[])
```

`candidates=[]` must take the empty-catalog path. Implement that as: if `candidates` is None, call `positive_lsd_candidates()`; if `candidates` is an empty list, raise `ValueError("positive LSD catalog is empty")`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_vision_bench.py::test_score_receipt_reports_zero_distance_for_the_oracle -v`

Expected: FAIL with `ImportError` for `score_receipt`.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

`field_displacement` of `0.0` is a float. `complete` must treat `0.0` as present. `isinstance(0.0, float)` is true.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_vision_bench.py -v`

Expected: PASS, including the earlier tests.

- [ ] **Step 5: Commit**

```bash
git add psyfi_core/visualization/vision_bench.py tests/test_vision_bench.py
git commit -m "Score a vision-bench receipt into a field report."
```

---

### Task 6: Local capture

**Files:**
- Create: `scripts/capture_vision_bench.py`
- Test: `tests/test_vision_bench.py`

**Interfaces:**
- Consumes: `BENCH_PROMPT`, `PROMPT_REVISION`, `CAPTURE_SCHEMA`, `CALLER_MODE`, `CALLER_INTENSITY`, `assert_oracle_lock`, `parse_model_content`, `score_receipt`, `IMAGE_ORDER`.
- Consumes from `psyfi_api.image_reading`: `configured_model`, `VisionConfigError`, `VisionProviderError`, `_caption`, `_post_once`, `_safe_provider_message`.
- Produces: `run_capture(*, dest: Path, environ: Mapping[str, str], post: Callable, today: str) -> tuple[int, str]`.
- `post(base: str, key: str, body: dict) -> dict`. The script's `main` passes `_post_once`.
- Default dest is `fixtures/qa/vision_bench_capture.v1.json`. `main` reads `os.environ` and today's UTC date.
- Preflight order: key set, `configured_model`, `assert_oracle_lock`. Failure returns non-zero, does not call `post`, does not replace `dest`, and the text is the reason. It does not include a report schema.
- One post per image. Body `model`, `max_tokens` `256`, `reasoning_effort` `"none"`, and `BENCH_PROMPT`. Timeout stays inside `_post_once` at 30 seconds. No retry.
- Provider failures store `error` `"provider"` and a detail from `_safe_provider_message`. Parse failures store `error` `"parse"`.
- Write by replace in the same directory. Exit `0` only when all four rows parsed. Otherwise exit `1` after the write. The text is the report JSON.

- [ ] **Step 1: Write the failing test**

Append:

```python
import importlib.util
import json
from pathlib import Path

from psyfi_api.image_reading import VisionProviderError, _PROMPT as CAPTION_PROMPT


def _load_capture():
    path = Path("scripts/capture_vision_bench.py")
    spec = importlib.util.spec_from_file_location("capture_vision_bench", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_preflight_does_not_touch_an_existing_receipt(tmp_path: Path) -> None:
    dest = tmp_path / "receipt.json"
    dest.write_text('{"keep": true}', encoding="utf-8")
    capture = _load_capture()
    calls = {"n": 0}

    def post(base: str, key: str, body: dict) -> dict:
        calls["n"] += 1
        return {}

    code, text = capture.run_capture(
        dest=dest,
        environ={},
        post=post,
        today="2026-11-07",
    )
    assert code == 1
    assert calls["n"] == 0
    assert dest.read_text(encoding="utf-8") == '{"keep": true}'
    assert "NVIDIA_API_KEY is unset" in text
    assert REPORT_SCHEMA not in text
    for model in ("@cf/nvidia/foo", "gemma"):
        code, text = capture.run_capture(
            dest=dest,
            environ={"NVIDIA_API_KEY": "test-key-value", "NVIDIA_VISION_MODEL": model},
            post=post,
            today="2026-11-07",
        )
        assert code == 1
        assert calls["n"] == 0
        assert dest.read_text(encoding="utf-8") == '{"keep": true}'
        assert "NVIDIA_VISION_MODEL must be an nvidia/ vision model id" in text


def test_capture_writes_four_rows_and_redacts_the_key(tmp_path: Path) -> None:
    dest = tmp_path / "receipt.json"
    capture = _load_capture()
    key = "test-key-value"
    bodies: list[dict] = []

    def post(base: str, key_arg: str, body: dict) -> dict:
        bodies.append(body)
        if len(bodies) == 2:
            raise VisionProviderError(f"failure {key}\nsecond line")
        image_id = IMAGE_ORDER[len(bodies) - 1]
        mode = ORACLE_MODE[image_id]
        return {"choices": [{"message": {"content": json.dumps({"mode": mode, "intensity": 0.5})}}]}

    code, text = capture.run_capture(
        dest=dest,
        environ={"NVIDIA_API_KEY": key, "NVIDIA_VISION_MODEL": "nvidia/bench-test"},
        post=post,
        today="2026-11-07",
    )
    assert code == 1
    assert len(bodies) == 4
    assert all(body["max_tokens"] == 256 for body in bodies)
    assert all(body["reasoning_effort"] == "none" for body in bodies)
    assert all(body["messages"][0]["content"][0]["text"] == BENCH_PROMPT for body in bodies)
    assert CAPTION_PROMPT not in json.dumps(bodies)
    saved = json.loads(dest.read_text(encoding="utf-8"))
    raw = dest.read_text(encoding="utf-8")
    assert key not in raw
    assert key not in text
    assert "data:image" not in raw
    assert "field_displacement" not in raw
    assert [row["id"] for row in saved["images"]] == list(IMAGE_ORDER)
    assert all(isinstance(row["latency_ms"], int) for row in saved["images"])
    assert saved["images"][1]["parse_ok"] is False
    assert saved["images"][1]["error"] == "provider"
    assert "\n" not in saved["images"][1]["detail"]
    assert len(saved["images"][1]["detail"]) <= 180
    assert REPORT_SCHEMA in text


def test_capture_exits_zero_when_every_row_parses(tmp_path: Path) -> None:
    dest = tmp_path / "receipt.json"
    capture = _load_capture()

    def post(base: str, key_arg: str, body: dict) -> dict:
        return {
            "choices": [
                {"message": {"content": json.dumps({"mode": "open", "intensity": 0.7})}}
            ]
        }

    code, text = capture.run_capture(
        dest=dest,
        environ={"NVIDIA_API_KEY": "test-key-value", "NVIDIA_VISION_MODEL": "nvidia/bench-test"},
        post=post,
        today="2026-11-07",
    )
    assert code == 0
    report = json.loads(text)
    assert report["complete"] is True
    assert report["schema"] == REPORT_SCHEMA


def test_broken_oracle_lock_does_not_post(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / "receipt.json"
    dest.write_text("keep", encoding="utf-8")
    capture = _load_capture()

    def broken() -> None:
        raise RuntimeError("oracle lock failed: void returned open")

    monkeypatch.setattr(capture, "assert_oracle_lock", broken)
    calls = {"n": 0}

    def post(base: str, key: str, body: dict) -> dict:
        calls["n"] += 1
        return {}

    code, text = capture.run_capture(
        dest=dest,
        environ={"NVIDIA_API_KEY": "test-key-value", "NVIDIA_VISION_MODEL": "nvidia/bench-test"},
        post=post,
        today="2026-11-07",
    )
    assert code == 1
    assert calls["n"] == 0
    assert dest.read_text(encoding="utf-8") == "keep"
    assert text.startswith("oracle lock failed:")
```

Import `BENCH_PROMPT`, `IMAGE_ORDER`, `ORACLE_MODE`, and `REPORT_SCHEMA` in the test module if they are not already imported.

The provider-failure post counts `len(bodies)` after append, so the second call raises. That is the `power` row. The preflight test also rejects `@cf/nvidia/foo` and `gemma` with zero posts.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_vision_bench.py::test_preflight_does_not_touch_an_existing_receipt -v`

Expected: FAIL because `scripts/capture_vision_bench.py` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `scripts/capture_vision_bench.py`:

```python
"""Capture one vision-bench receipt. A person runs this. CI does not."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path

from psyfi_api.image_reading import (
    VisionConfigError,
    VisionProviderError,
    _caption,
    _post_once,
    _safe_provider_message,
    configured_model,
)
from psyfi_core.visualization.vision_bench import (
    BENCH_PROMPT,
    CALLER_INTENSITY,
    CALLER_MODE,
    CAPTURE_SCHEMA,
    PROMPT_REVISION,
    assert_oracle_lock,
    build_corpus,
    parse_model_content,
    score_receipt,
)

DEFAULT_RECEIPT = Path("fixtures/qa/vision_bench_capture.v1.json")
DEFAULT_BASE = "https://integrate.api.nvidia.com"
Post = Callable[[str, str, dict], dict]


def _row_from_post(image_id: str, base: str, key: str, model: str, rgba, post: Post) -> dict:
    from psyfi_api.image_reading import _png_data_url

    body = {
        "model": model,
        "max_tokens": 256,
        "reasoning_effort": "none",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": BENCH_PROMPT},
                    {"type": "image_url", "image_url": {"url": _png_data_url(rgba)}},
                ],
            }
        ],
    }
    started = time.perf_counter()
    try:
        payload = post(base, key, body)
    except VisionProviderError as exc:
        elapsed = int(round((time.perf_counter() - started) * 1000))
        detail = _safe_provider_message(str(exc).encode(), key)
        return {
            "id": image_id,
            "mode": None,
            "intensity": None,
            "latency_ms": elapsed,
            "parse_ok": False,
            "error": "provider",
            "detail": detail,
        }
    elapsed = int(round((time.perf_counter() - started) * 1000))
    try:
        text = _caption(payload)
    except VisionProviderError as exc:
        detail = _safe_provider_message(str(exc).encode(), key)
        return {
            "id": image_id,
            "mode": None,
            "intensity": None,
            "latency_ms": elapsed,
            "parse_ok": False,
            "error": "provider",
            "detail": detail,
        }
    parsed = parse_model_content(text)
    if not parsed["parse_ok"]:
        detail = _safe_provider_message(text.encode(), key)
        return {
            "id": image_id,
            "mode": None,
            "intensity": None,
            "latency_ms": elapsed,
            "parse_ok": False,
            "error": "parse",
            "detail": detail,
        }
    return {
        "id": image_id,
        "mode": parsed["mode"],
        "intensity": parsed["intensity"],
        "latency_ms": elapsed,
        "parse_ok": True,
    }


def run_capture(*, dest: Path, environ: Mapping[str, str], post: Post, today: str) -> tuple[int, str]:
    key = (environ.get("NVIDIA_API_KEY") or "").strip()
    if not key:
        return 1, "NVIDIA_API_KEY is unset\n"
    try:
        model = configured_model(environ.get("NVIDIA_VISION_MODEL"))
    except VisionConfigError as exc:
        return 1, f"{exc.detail}\n"
    try:
        assert_oracle_lock()
    except RuntimeError as exc:
        return 1, f"{exc}\n"
    base = (environ.get("NVIDIA_API_BASE") or "").strip() or DEFAULT_BASE
    rows = [
        _row_from_post(image_id, base, key, model, rgba, post)
        for image_id, rgba in build_corpus()
    ]
    receipt = {
        "schema": CAPTURE_SCHEMA,
        "date": today,
        "model": model,
        "caller": {"mode": CALLER_MODE, "intensity": CALLER_INTENSITY},
        "prompt_revision": PROMPT_REVISION,
        "images": rows,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_name(dest.name + ".tmp")
    temporary.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    temporary.replace(dest)
    report = score_receipt(receipt)
    code = 0 if report["complete"] else 1
    return code, json.dumps(report, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture a vision-bench receipt.")
    parser.add_argument("--dest", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args(argv)
    today = datetime.now(timezone.utc).date().isoformat()
    code, text = run_capture(dest=args.dest, environ=os.environ, post=_post_once, today=today)
    sys.stdout.write(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
```

`_png_data_url` expects an RGBA float array in `0..1`, which `build_corpus` returns. Do not add a model-id default.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_vision_bench.py -v`

Expected: PASS. Also confirm the fixture was not created:

Run: `test ! -e fixtures/qa/vision_bench_capture.v1.json`

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/capture_vision_bench.py tests/test_vision_bench.py
git commit -m "Capture a vision-bench receipt with one post per image."
```

---

### Task 7: Caption contract and absent receipt

**Files:**
- Modify: `tests/test_vision_bench.py`

**Interfaces:**
- Consumes: `BENCH_PROMPT`, `score_receipt`, `app` from `psyfi_api.main`, caption `_PROMPT`.
- Produces: no new production function. The public router gains no bench path. A missing receipt file skips rather than fails.

- [ ] **Step 1: Write the failing test**

Append:

```python
from psyfi_api.main import app


def test_caption_route_is_unchanged() -> None:
    assert BENCH_PROMPT != CAPTION_PROMPT
    paths = [getattr(route, "path", "") for route in app.routes]
    assert "/api/v1/visualize/image-reading" in paths
    assert not any("vision-bench" in path or "vision_bench" in path for path in paths)


def test_committed_receipt_is_optional() -> None:
    path = Path("fixtures/qa/vision_bench_capture.v1.json")
    if not path.exists():
        pytest.skip("no measured vision bench receipt")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    report = score_receipt(receipt)
    assert report["schema"] == REPORT_SCHEMA
```

This test passes as soon as it is collected, because the file is absent and the route was never added. Write it after Task 6 so the imports exist. Run it to confirm the skip.

- [ ] **Step 2: Run the test**

Run: `python -m pytest -q tests/test_vision_bench.py::test_caption_route_is_unchanged tests/test_vision_bench.py::test_committed_receipt_is_optional -v`

Expected: `test_caption_route_is_unchanged` PASS. `test_committed_receipt_is_optional` SKIPPED with `no measured vision bench receipt`.

- [ ] **Step 3: No production code**

Do not add a route. Do not create the fixture. Do not change the caption prompt.

- [ ] **Step 4: Run the whole file**

Run: `python -m pytest -q tests/test_vision_bench.py tests/test_image_reading.py -v`

Expected: vision-bench tests PASS except the optional receipt skip. Image-reading tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_vision_bench.py
git commit -m "Keep the caption route off the vision bench."
```

---

## Spec coverage

- Corpus constructions, oracle lock, and cutoff sides: Task 1.
- Bench prompt text, revision, no numeric cutoffs: Task 1 constant, Task 6 body assert.
- Parse rules, fences, `Open`, percents, unit interval: Task 2.
- Field displacement, mode steps, `within_mode_step`, frozen `map_parameters` inputs, hints excluded: Task 3.
- Catalog switch on an injected pair, real positive LSD list: Task 4.
- Receipt schema check, report shape, `complete`, parse failure stays a result, empty catalog raises: Task 5.
- Preflight, one post, redaction, atomic replace, exit codes, no key and no score in the receipt: Task 6.
- No public route, caption prompt unchanged, absent receipt skips: Task 7.
- GPU bench, hardware scaling, and a committed measured receipt are out of this plan.

## Execution note

Implement on branch `spec/vision-bench`. The spec commits are `e295745` and `de8c36e`. Do not stage the pull-request template or `.trail/cache/`.
