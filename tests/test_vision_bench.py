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
