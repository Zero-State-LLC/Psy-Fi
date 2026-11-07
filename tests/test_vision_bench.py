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
