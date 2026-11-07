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
