"""psyfi_bench core: contracts, statistics, determinism, store, environment."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from psyfi_bench import MANIFEST_SCHEMA, NON_CLAIM, RESULT_SCHEMA
from psyfi_bench.determinism import compare_repeats, exact_digest, max_abs_error, quantized_digest, record_for
from psyfi_bench.environment import collect_environment
from psyfi_bench.registry import list_manifests, load_manifest, manifest_paths
from psyfi_bench.schemas import BenchResult, EnvironmentRecord, WorkloadManifest, export_json_schemas, stable_hash
from psyfi_bench.stats import (
    bootstrap_ci,
    coefficient_of_variation,
    fps_from_frame_ms,
    frame_pacing,
    low_1pct_fps,
    percentile,
    scaling_exponent,
    summarize,
    sustained_drift,
)
from psyfi_bench.store import ResultStore


def test_manifest_hash_is_stable_and_ignores_title() -> None:
    a = WorkloadManifest(id="x.y", version=1, family="field_compute", title="A", params={"k": 1})
    b = WorkloadManifest(id="x.y", version=1, family="field_compute", title="B", params={"k": 1})
    c = WorkloadManifest(id="x.y", version=1, family="field_compute", title="A", params={"k": 2})
    assert a.manifest_hash == b.manifest_hash
    assert a.manifest_hash != c.manifest_hash
    assert a.to_document()["schema"] == MANIFEST_SCHEMA
    assert stable_hash({"b": 1, "a": 2}) == stable_hash({"a": 2, "b": 1})


def test_shipped_manifests_are_valid_unique_and_locked() -> None:
    manifests = list_manifests()
    assert manifests, "no manifests shipped"
    ids = [(m.id, m.version) for m in manifests]
    assert len(ids) == len(set(ids))
    for m in manifests:
        assert m.manifest_hash
        assert m.family in {"field_compute", "render", "interpretation", "fieldloop"}
    for path in manifest_paths():
        doc = json.loads(path.read_text(encoding="utf-8"))
        m = load_manifest(path)
        if "manifest_hash" in doc:
            assert doc["manifest_hash"] == m.manifest_hash, f"{path.name}: on-disk manifest_hash is stale"


def test_statistics_match_numpy_and_bootstrap_is_seeded() -> None:
    vals = [10.0, 12.0, 11.0, 50.0, 9.0, 10.5]
    s = summarize(vals, unit="ms", seed=7)
    assert s.n == 6
    assert s.median == pytest.approx(np.median(vals))
    assert s.p95 == pytest.approx(np.percentile(vals, 95))
    assert s.mad == pytest.approx(np.median(np.abs(np.asarray(vals) - np.median(vals))))
    assert s.cv == pytest.approx(coefficient_of_variation(vals))
    assert s.ci95_mean is not None and s.ci95_mean[0] <= s.mean <= s.ci95_mean[1]
    assert bootstrap_ci(vals, "mean", seed=7) == bootstrap_ci(vals, "mean", seed=7)
    assert bootstrap_ci([1.0], "mean") is None
    assert percentile([], 50) != percentile([], 50)  # NaN
    with pytest.raises(ValueError):
        summarize([])


def test_frame_time_helpers() -> None:
    frames = [16.7] * 95 + [50.0] * 5
    assert fps_from_frame_ms(frames) == pytest.approx(1000.0 / np.mean(frames))
    assert low_1pct_fps(frames) == pytest.approx(1000.0 / np.percentile(frames, 99))
    pacing = frame_pacing(frames)
    assert pacing["stutter_frames"] == 5
    drift = sustained_drift([10.0 + i * 0.01 for i in range(400)])
    assert drift["slope_ms_per_1000_frames"] == pytest.approx(10.0, rel=1e-3)
    assert drift["last_first_quartile_ratio"] > 1.0


def test_scaling_exponent_recovers_linear_and_quadratic() -> None:
    sizes = [1024, 4096, 16384, 65536]
    linear = scaling_exponent(sizes, [s * 2e-3 for s in sizes])
    quad = scaling_exponent(sizes, [(s ** 2) * 1e-7 for s in sizes])
    assert linear["exponent"] == pytest.approx(1.0, abs=1e-9)
    assert quad["exponent"] == pytest.approx(2.0, abs=1e-9)
    assert linear["r2"] == pytest.approx(1.0)


def test_determinism_digests() -> None:
    a = (np.arange(16, dtype=np.float32).reshape(4, 4) / 7.0).astype(np.complex64)
    b = a.copy()
    c = a + np.complex64(3e-6)
    assert exact_digest(a) == exact_digest(b)
    assert exact_digest(a) != exact_digest(c)
    assert quantized_digest(a, 1e-4) == quantized_digest(c, 1e-4)
    assert quantized_digest(a, 1e-7) != quantized_digest(c, 1e-7)
    rec = record_for(np.array([1.0, np.nan, np.inf]))
    assert rec.nan_count == 1 and rec.inf_count == 1
    agg = compare_repeats([record_for(a), record_for(b), record_for(c, quantization=1e-4)])
    assert agg["bitwise_identical_across_repeats"] is False
    assert max_abs_error(a, c) == pytest.approx(3e-6, rel=0.2)


def test_environment_reports_missing_telemetry_instead_of_guessing() -> None:
    env = collect_environment(include_gpu=False)
    assert env.platform["system"]
    assert env.cpu["logical_cores"]
    assert env.software["numpy"]
    assert env.software["bench_version"]
    assert "power" in env.unavailable
    assert env.hostname_hash is None or len(env.hostname_hash) == 12


def test_result_store_round_trip(tmp_path: Path) -> None:
    env = collect_environment(include_gpu=False)
    manifest = WorkloadManifest(id="store.test", version=1, family="field_compute", title="t")
    result = BenchResult(
        run_id="run_test_1",
        created_at="2026-11-07T00:00:00Z",
        manifest=manifest.to_document(),
        manifest_hash=manifest.manifest_hash,
        measurement_class="synthetic",
        environment=env,
        metrics={"x": 1},
        non_claim=NON_CLAIM,
    ).seal()
    assert result.verify()
    store = ResultStore(tmp_path)
    path = store.save(result)
    assert path.exists()
    listed = store.list(family="field_compute")
    assert listed and listed[0]["run_id"] == "run_test_1"
    assert listed[0]["measurement_class"] == "synthetic"
    loaded = store.load("run_test_1")
    assert loaded is not None and loaded.verify()
    loaded.metrics["x"] = 2
    assert not loaded.verify(), "tampering must break the seal"
    assert json.loads(path.read_text())["schema"] == RESULT_SCHEMA


def test_json_schema_export_covers_every_contract() -> None:
    schemas = export_json_schemas()
    assert set(schemas) == {
        "psyfi_bench_manifest.v1.json",
        "psyfi_bench_result.v1.json",
        "psyfi_bench_gpu_capture.v1.json",
        "psyfi_bench_scorecard.v1.json",
        "psyfi_bench_capabilities.v1.json",
    }
    result_schema = schemas["psyfi_bench_result.v1.json"]
    assert "measurement_class" in result_schema["properties"]
    assert set(result_schema["properties"]["measurement_class"]["enum"]) == {"measured", "synthetic", "replay"}


def test_environment_record_rejects_nothing_required_but_keeps_unknowns() -> None:
    rec = EnvironmentRecord(captured_at="2026-11-07T00:00:00Z", extra_field="kept")
    assert rec.model_dump()["extra_field"] == "kept"
