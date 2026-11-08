"""Power sampling: injected fake sampler, no real nvidia-smi, no estimates when absent."""

from __future__ import annotations

import time

import pytest

from psyfi_bench import power as power_mod
from psyfi_bench.power import PowerSample, ThreadedSampler, build_power_record, make_power_sampler
from psyfi_bench.registry import load_manifest
from psyfi_bench.runner import RunContext, run_workload
from psyfi_bench.schemas import BenchResult, Protocol

FAST = Protocol(repeats=2, warmup_runs=0, cold_start=False, memory_probe=False, bootstrap_resamples=100)


class FakeSampler:
    name = "fake-smi"
    interval_s = 0.5

    def __init__(self, samples: list[PowerSample]) -> None:
        self._samples = samples
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> list[PowerSample]:
        self.stopped += 1
        return list(self._samples)


def _run(factory, tmp_name="x"):
    manifest = load_manifest("field-compute.scaling").model_copy(update={"protocol": FAST})
    ctx = RunContext(inputs={"grid_sizes": [8], "steps": 3}, include_gpu_env=False, power_sampler_factory=factory)
    return run_workload(manifest, ctx)


def test_energy_is_trapezoid_of_samples_only() -> None:
    samples = [PowerSample(0.0, 100.0, 50.0, 1000.0), PowerSample(1.0, 200.0, 60.0, 1500.0), PowerSample(3.0, 200.0, 55.0, 1400.0)]
    rec = build_power_record(samples, source="fake", interval_s=1.0, window_s=3.2, work_unit="cell_step", work_units=300.0)
    assert rec.energy_j == pytest.approx(150.0 + 400.0)
    assert rec.energy_j_per_work_unit == pytest.approx(550.0 / 300.0)
    assert rec.sampled_span_s == 3.0 and rec.window_s == 3.2 and rec.sample_count == 3
    assert rec.power_w_mean == pytest.approx(500.0 / 3) and rec.power_w_max == 200.0
    assert rec.temperature_c_max == 60.0 and rec.sm_clock_mhz_max == 1500.0
    assert "no extrapolation" in rec.derivation


def test_too_few_samples_reports_no_energy_and_a_reason() -> None:
    rec = build_power_record([PowerSample(0.0, 120.0)], source="fake", interval_s=1.0, window_s=0.2, work_unit="cell_step", work_units=10.0)
    assert rec.energy_j is None and rec.energy_j_per_work_unit is None
    assert "fewer than 2" in (rec.unavailable_reason or "")
    empty = build_power_record([], source="fake", interval_s=1.0, window_s=0.2)
    assert empty.sample_count == 0 and empty.power_w_mean is None and empty.energy_j is None


def test_field_compute_records_energy_per_cell_step_with_fake_sampler() -> None:
    fake = FakeSampler([PowerSample(0.0, 100.0), PowerSample(2.0, 100.0)])
    result = _run(lambda: fake)
    stage = result.stages[0]
    assert fake.started == 1 and fake.stopped == 1
    p = stage.power
    assert p is not None and p.source == "fake-smi" and p.work_unit == "cell_step"
    assert p.energy_j == pytest.approx(200.0)
    assert p.work_units == 8 * 8 * 3 * len(stage.wall_ms)
    assert p.energy_j_per_work_unit == pytest.approx(200.0 / p.work_units)
    assert "power" not in result.environment.unavailable and result.environment.power["source"] == "fake-smi"
    BenchResult.model_validate(result.model_dump(by_alias=True))


def test_absent_tool_writes_no_power_and_keeps_unavailable_reason(monkeypatch) -> None:
    monkeypatch.setattr(power_mod.shutil, "which", lambda name: None)
    assert make_power_sampler() is None
    result = _run(None)
    assert all(s.power is None for s in result.stages)
    assert result.environment.power is None
    assert result.environment.unavailable["power"] == "no power sampler on this host (nvidia-smi absent or not sampled)"


def test_factory_returning_none_means_no_power() -> None:
    result = _run(lambda: None)
    assert result.stages[0].power is None


def test_threaded_sampler_collects_what_the_reader_returns() -> None:
    ticks = iter(range(1000))
    s = ThreadedSampler(lambda: PowerSample(float(next(ticks)), 10.0), interval_s=0.001)
    s.start()
    out = s.stop()
    assert out and all(x.power_w == 10.0 for x in out)


def test_results_without_power_still_validate() -> None:
    result = _run(lambda: None)
    doc = result.model_dump(by_alias=True)
    for st in doc["stages"]:
        st.pop("power", None)
    BenchResult.model_validate(doc)


def test_per_unit_energy_needs_samples_across_most_of_the_window() -> None:
    samples = [PowerSample(0.0, 100.0), PowerSample(1.0, 100.0)]
    rec = build_power_record(samples, source="fake", interval_s=0.2, window_s=2.0, work_unit="cell_step", work_units=1000.0)
    assert rec.energy_j == pytest.approx(100.0)
    assert rec.energy_j_per_work_unit is None
    assert "50%" in (rec.unavailable_reason or "")


def test_threaded_sampler_takes_a_last_reading_at_stop_and_stops_once() -> None:
    reads: list[float] = []

    def read() -> PowerSample:
        reads.append(1.0)
        return PowerSample(float(len(reads)), 10.0)

    s = ThreadedSampler(read, interval_s=60.0)  # the loop reads once, then waits
    s.start()
    deadline = time.monotonic() + 5.0
    while not reads and time.monotonic() < deadline:  # let the loop take its first reading
        time.sleep(0.001)
    first = s.stop()
    assert len(first) == 2  # the loop's reading plus the final one
    assert s.stop() == first  # a second stop adds nothing
