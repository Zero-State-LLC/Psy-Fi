"""Host power trace for browser captures (ADR 0011): synthetic captures and traces, a fake nvidia-smi, never the real one."""

from __future__ import annotations

import calendar
import json
import os
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from psyfi_api.main import app
from psyfi_bench import environment as env_mod
from psyfi_bench import power as power_mod
from psyfi_bench.cli import main as cli_main
from psyfi_bench.power import nvidia_smi_stamp_to_epoch_s, parse_stream_line
from psyfi_bench.registry import load_manifest
from psyfi_bench.runner import RunContext, run_workload
from psyfi_bench.schemas import BenchResult, EnvironmentRecord, GpuCapture, PowerTrace

ROOT = Path(__file__).resolve().parents[2]
EPOCH = 1_794_000_000.0
HOST = "abc123def456"
NO_POWER = "no power sampler on this host (nvidia-smi absent or not sampled)"
NVIDIA = {"vendor": "nvidia", "description": "NVIDIA GeForce RTX 4070 SUPER", "architecture": "ada-lovelace"}


def _stage(stage_id: str, window_s: tuple[float, float] | None, frames: int = 120, **extra) -> dict:
    span_s = (window_s[1] - window_s[0]) if window_s else 2.0
    stage = {
        "id": stage_id, "tier": "ultra", "snapshot_key": "lsd_open_42", "requested_frames": frames, "warmup_frames": 60,
        "frames_ms": [span_s * 1000.0 / frames] * frames, "duration_ms": span_s * 1000.0, **extra,
    }
    if window_s is not None:
        stage["window_epoch_ms"] = [(EPOCH + window_s[0]) * 1000.0, (EPOCH + window_s[1]) * 1000.0]
    return stage


def _capture(*stages: dict, adapter: dict | None = NVIDIA, **extra) -> GpuCapture:
    return GpuCapture(captured_at="2026-11-08T00:00:00Z", manifest_id="render.webgpu.tiers", measurement_class="synthetic", browser={"adapter": adapter}, stages=list(stages), **extra)


def _ramp(start_s: float, end_s: float, watts: float = 100.0) -> list[tuple[float, float | None]]:
    """A reading every 100 ms over ``[start_s, end_s]`` (seconds after ``EPOCH``)."""
    count = round((end_s - start_s) * 10)
    return [(start_s + i / 10, watts) for i in range(count + 1)]


def _trace(points: list[tuple[float, float | None]], *, host: str | None = HOST, vendor: str = "nvidia") -> PowerTrace:
    return PowerTrace(
        created_at="2026-11-08T00:00:00Z", source="nvidia-smi", query="timestamp,power.draw.instant,temperature.gpu,clocks.sm", interval_s=0.1,
        gpu_name="NVIDIA GeForce RTX 4070 SUPER", gpu_vendor=vendor, hostname_hash=host, started_epoch_s=EPOCH, stopped_epoch_s=EPOCH + 60.0,
        samples=[{"t_epoch_s": EPOCH + t, "power_w": w} for t, w in points],
    )


def _env() -> EnvironmentRecord:
    return EnvironmentRecord(captured_at="2026-11-08T00:00:00Z", hostname_hash=HOST, unavailable={"power": NO_POWER})


def _score(capture: GpuCapture, trace: PowerTrace | None = None) -> BenchResult:
    return run_workload(load_manifest("render.webgpu.tiers"), RunContext(inputs={"capture": capture.model_dump(by_alias=True)}, environment=_env(), power_trace=trace))


def test_trace_covering_a_stage_gives_energy_per_frame() -> None:
    result = _score(_capture(_stage("a", (0.0, 2.0))), _trace(_ramp(-1.0, 3.0)))
    assert result.status == "complete", result.failures
    p = result.stages[0].power
    assert p is not None and p.work_unit == "frame" and p.work_units == 120.0
    assert p.source == "nvidia-smi" and p.query.startswith("timestamp,power.draw.instant,")
    assert p.window_s == pytest.approx(2.0) and p.sampled_span_s == pytest.approx(2.0, abs=1e-3)
    assert p.energy_j == pytest.approx(200.0, abs=0.1)
    assert p.energy_j_per_work_unit == pytest.approx(200.0 / 120.0, abs=1e-3)
    assert p.unavailable_reason is None
    for phrase in ("board power while the stage rendered", "idle draw", "the compositor", "anything else on the GPU"):
        assert phrase in p.derivation
    assert "power_unavailable" not in result.stages[0].metrics
    assert result.stages[0].metrics["power_window_epoch_ms"] == [EPOCH * 1000.0, (EPOCH + 2.0) * 1000.0]
    assert "power" not in result.environment.unavailable
    assert result.environment.power["source"] == "nvidia-smi"
    assert result.metrics["power_trace"]["stages_with_energy_per_frame"] == 1 and result.metrics["power_trace"]["refused"] is None
    assert result.verify()
    BenchResult.model_validate(result.model_dump(by_alias=True))


def test_trace_under_90_percent_of_the_window_gives_energy_but_no_per_frame_value() -> None:
    result = _score(_capture(_stage("a", (0.0, 2.0))), _trace(_ramp(0.5, 3.0)))
    p = result.stages[0].power
    assert p is not None and p.energy_j == pytest.approx(150.0, abs=0.1)
    assert p.energy_j_per_work_unit is None
    assert "75%" in (p.unavailable_reason or "")
    assert result.metrics["power_trace"]["stages_with_energy_per_frame"] == 0
    assert "power" not in result.environment.unavailable  # energy was measured, so power is not "unavailable"


def test_samples_outside_the_window_are_dropped() -> None:
    points = [(-0.5, 500.0), (-0.1, 500.0), *_ramp(0.0, 2.0), (2.1, 500.0), (2.5, 500.0)]
    p = _score(_capture(_stage("a", (0.0, 2.0))), _trace(points)).stages[0].power
    assert p is not None and p.sample_count == 21 and p.power_w_max == 100.0
    assert p.energy_j == pytest.approx(200.0, abs=0.1)


def test_samples_without_a_power_reading_do_not_stretch_the_coverage() -> None:
    points: list[tuple[float, float | None]] = [(0.0, None), *_ramp(0.5, 1.0), (2.0, None)]
    p = _score(_capture(_stage("a", (0.0, 2.0))), _trace(points)).stages[0].power
    assert p is not None and p.energy_j == pytest.approx(50.0, abs=0.1) and p.energy_j_per_work_unit is None


def test_a_stage_under_a_second_gives_energy_but_no_per_frame_value() -> None:
    p = _score(_capture(_stage("a", (0.0, 0.5), frames=30)), _trace(_ramp(-1.0, 2.0))).stages[0].power
    assert p is not None and p.energy_j == pytest.approx(50.0, abs=0.1)
    assert p.energy_j_per_work_unit is None
    assert "shorter than 1 s" in (p.unavailable_reason or "")


def _assert_refused(result: BenchResult, *phrases: str) -> None:
    for stage in result.stages:
        assert stage.power is None
        for phrase in phrases:
            assert phrase in stage.metrics["power_unavailable"]
    assert result.environment.power is None
    assert result.environment.unavailable["power"].startswith("power trace supplied but not paired with any stage")


def test_different_hostname_hash_gives_no_power_and_a_reason() -> None:
    result = _score(_capture(_stage("a", (0.0, 2.0))), _trace(_ramp(-1.0, 3.0), host="000000000000"))
    _assert_refused(result, "hostname_hash", "000000000000", HOST)
    assert result.metrics["power_trace"]["stages_with_power"] == 0 and "hostname_hash" in result.metrics["power_trace"]["refused"]
    assert result.status == "complete"  # refusing power does not fail the frame scoring


@pytest.mark.parametrize("trace_host", [None, ""])
def test_a_trace_without_a_hostname_hash_cannot_be_matched(trace_host) -> None:
    _assert_refused(_score(_capture(_stage("a", (0.0, 2.0))), _trace(_ramp(-1.0, 3.0), host=trace_host)), "hostname_hash")


def test_same_gpu_name_on_another_host_is_not_enough() -> None:
    capture = _capture(_stage("a", (0.0, 2.0)), adapter={"vendor": "nvidia", "description": "NVIDIA GeForce RTX 4070 SUPER"})
    assert _score(capture, _trace(_ramp(-1.0, 3.0), host="another-host-0")).stages[0].power is None


@pytest.mark.parametrize("adapter, phrase", [
    ({"vendor": "amd", "description": "AMD Radeon RX 7900 XT"}, "not the capture adapter's vendor amd"),
    ({"vendor": "apple", "architecture": "metal-3"}, "not the capture adapter's vendor apple"),
    ({"vendor": "", "description": ""}, "adapter vendor is unknown"),
    (None, "adapter vendor is unknown"),
])
def test_different_or_unknown_gpu_vendor_gives_no_power_and_a_reason(adapter, phrase) -> None:
    _assert_refused(_score(_capture(_stage("a", (0.0, 2.0)), adapter=adapter), _trace(_ramp(-1.0, 3.0))), phrase)


def test_stage_without_a_window_gives_no_power_while_others_still_pair() -> None:
    result = _score(_capture(_stage("old", None), _stage("new", (0.0, 2.0))), _trace(_ramp(-1.0, 3.0)))
    old = next(s for s in result.stages if s.id == "old")
    assert old.power is None and "no window_epoch_ms" in old.metrics["power_unavailable"]
    new = next(s for s in result.stages if s.id == "new")
    assert new.power is not None and new.power.energy_j_per_work_unit is not None
    assert "power" not in result.environment.unavailable
    assert result.metrics["power_trace"]["stages_refused"] == 1


@pytest.mark.parametrize("points", [
    pytest.param(_ramp(-10.0, -1.0), id="ends-before-the-window"),
    pytest.param(_ramp(5.0, 10.0), id="starts-after-the-window"),
    pytest.param([(-1.0, 100.0), (3.0, 100.0)], id="brackets-the-window-with-no-reading-inside"),
    pytest.param([(0.5, None), (1.0, None)], id="no-power-readings-at-all"),
])
def test_trace_that_does_not_reach_the_window_gives_no_power_and_a_reason(points) -> None:
    result = _score(_capture(_stage("a", (0.0, 2.0))), _trace(points))
    reason = result.stages[0].metrics["power_unavailable"]
    assert result.stages[0].power is None and ("does not reach" in reason or "no samples with a power reading" in reason)
    assert result.environment.unavailable["power"].startswith("power trace supplied")


def test_bad_window_values_are_refused() -> None:
    backwards = _stage("a", None)
    backwards["window_epoch_ms"] = [EPOCH * 1000.0 + 5.0, EPOCH * 1000.0]
    result = _score(_capture(backwards), _trace(_ramp(-1.0, 3.0)))
    assert result.stages[0].power is None and "not a finite, increasing range" in result.stages[0].metrics["power_unavailable"]


def test_failed_stage_gets_no_power() -> None:
    result = _score(_capture(_stage("a", (0.0, 2.0), js_errors=3)), _trace(_ramp(-1.0, 3.0)))
    assert result.stages[0].status == "failed" and result.stages[0].power is None
    assert "did not complete" in result.stages[0].metrics["power_unavailable"]


def test_kernel_stages_are_left_alone() -> None:
    kernel = {"id": "k", "kernel": "kuramoto_symmetric_step", "fixture_id": "f", "fixture_hash": "h", "width": 32, "height": 32, "steps": 1, "status": "unsupported", "unsupported_reason": "no WebGPU"}
    result = _score(_capture(_stage("a", (0.0, 2.0)), kernels=[kernel]), _trace(_ramp(-1.0, 3.0)))
    stage = next(s for s in result.stages if s.kind == "webgpu_kernel")
    assert stage.power is None and "power_unavailable" not in stage.metrics
    assert next(s for s in result.stages if s.id == "a").power is not None


def test_no_power_trace_leaves_scoring_unchanged() -> None:
    windowed = _score(_capture(_stage("a", (0.0, 2.0))))
    plain = _score(_capture(_stage("a", None)))
    assert [s.model_dump() for s in windowed.stages] == [s.model_dump() for s in plain.stages]
    assert windowed.metrics == plain.metrics
    assert windowed.stages[0].power is None and "power_unavailable" not in windowed.stages[0].metrics
    assert "power_trace" not in windowed.metrics and windowed.environment.power is None
    assert windowed.environment.unavailable["power"] == NO_POWER


def test_api_ingest_accepts_windows_but_never_a_trace(monkeypatch, tmp_path: Path) -> None:
    client = TestClient(app)
    monkeypatch.setenv("PSYFI_BENCH_INGEST", "1")
    monkeypatch.setenv("PSYFI_BENCH_RESULTS", str(tmp_path))
    payload = _capture(_stage("a", (0.0, 2.0))).model_dump(by_alias=True)
    assert client.post("/api/bench/v1/captures", json={**payload, "power_trace": _trace(_ramp(-1.0, 3.0)).model_dump(by_alias=True)}).status_code == 422
    ok = client.post("/api/bench/v1/captures", json=payload)
    assert ok.status_code == 201, ok.text
    full = client.get(f"/api/bench/v1/results/{ok.json()['run_id']}").json()
    assert full["stages"][0]["power"] is None and "power_trace" not in full["metrics"]
    assert full["environment"]["unavailable"]["power"] == NO_POWER


def test_the_capture_window_is_optional_in_the_exported_schema() -> None:
    from psyfi_bench.schemas import export_json_schemas

    stage = export_json_schemas()["psyfi_bench_gpu_capture.v1.json"]["$defs"]["CaptureStage"]
    assert "window_epoch_ms" in stage["properties"] and "window_epoch_ms" not in stage["required"]


def _write_ingest_inputs(tmp_path: Path, trace: PowerTrace) -> tuple[Path, Path]:
    cap, tr = tmp_path / "capture.json", tmp_path / "trace.json"
    cap.write_text(json.dumps(_capture(_stage("a", (0.0, 2.0))).model_dump(by_alias=True)), encoding="utf-8")
    tr.write_text(json.dumps(trace.model_dump(by_alias=True)), encoding="utf-8")
    return cap, tr


def test_cli_ingest_with_a_power_trace(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(env_mod, "gpu_info", lambda unavailable: [])  # the scoring host's own GPU inventory is not under test
    cap, tr = _write_ingest_inputs(tmp_path, _trace(_ramp(-1.0, 3.0), host=env_mod.hostname_hash()))
    assert cli_main(["ingest", str(cap), "--power-trace", str(tr), "--no-store", "--json"]) == 0
    out = capsys.readouterr().out
    doc = json.loads(out)
    assert doc["stages"][0]["power"]["work_unit"] == "frame" and doc["stages"][0]["power"]["energy_j_per_work_unit"] is not None
    assert "power" not in doc["environment"]["unavailable"]


def test_cli_ingest_without_a_power_trace_keeps_the_unavailable_reason(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(env_mod, "gpu_info", lambda unavailable: [])
    cap, _ = _write_ingest_inputs(tmp_path, _trace(_ramp(-1.0, 3.0)))
    assert cli_main(["ingest", str(cap), "--no-store", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["stages"][0]["power"] is None and doc["environment"]["unavailable"]["power"] == NO_POWER


@pytest.mark.parametrize("contents", [None, "not json", '{"schema": "something else"}'])
def test_cli_ingest_rejects_an_unusable_trace_file(tmp_path: Path, monkeypatch, capsys, contents) -> None:
    monkeypatch.setattr(env_mod, "gpu_info", lambda unavailable: [])
    cap, tr = _write_ingest_inputs(tmp_path, _trace(_ramp(-1.0, 3.0)))
    if contents is None:
        tr.unlink()
    else:
        tr.write_text(contents, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        cli_main(["ingest", str(cap), "--power-trace", str(tr), "--no-store", "--quiet"])
    assert "cannot read power trace" in str(exc.value)


@pytest.fixture
def set_timezone(monkeypatch):
    """POSIX TZ strings, which need no tz database on the machine running the test."""
    if not hasattr(time, "tzset"):
        pytest.skip("no time.tzset on this platform")

    def apply(name: str) -> None:
        monkeypatch.setenv("TZ", name)
        time.tzset()

    yield apply
    monkeypatch.undo()
    time.tzset()


def test_nvidia_smi_stamps_become_epoch_seconds_through_the_host_timezone(set_timezone) -> None:
    utc = calendar.timegm((2026, 11, 8, 15, 0, 0)) + 0.25
    set_timezone("UTC0")
    assert nvidia_smi_stamp_to_epoch_s("2026/11/08 15:00:00.250") == pytest.approx(utc, abs=1e-6)
    set_timezone("EST5EDT,M3.2.0,M11.1.0")  # EST on this date: UTC-5
    assert nvidia_smi_stamp_to_epoch_s("2026/11/08 10:00:00.250") == pytest.approx(utc, abs=1e-6)
    set_timezone("IST-5:30")
    assert nvidia_smi_stamp_to_epoch_s("2026/11/08 20:30:00.250") == pytest.approx(utc, abs=1e-6)
    sample = parse_stream_line("2026/11/08 20:30:00.250, 85.21, 54, 1755", clock_offset_s=0.0)
    assert sample is not None and sample.t_s == pytest.approx(utc, abs=1e-6) and sample.power_w == 85.21
    assert nvidia_smi_stamp_to_epoch_s("not a stamp") is None


def test_the_repeated_hour_at_the_end_of_daylight_saving_follows_the_receive_time(set_timezone) -> None:
    set_timezone("EST5EDT,M3.2.0,M11.1.0")  # 2026-11-01 01:30 local happens twice, an hour apart
    first = float(calendar.timegm((2026, 11, 1, 5, 30, 0)))  # EDT
    second = float(calendar.timegm((2026, 11, 1, 6, 30, 0)))  # EST
    stamp = "2026/11/01 01:30:00.000"
    assert nvidia_smi_stamp_to_epoch_s(stamp) == pytest.approx(first, abs=1e-6)  # no receive time: datetime's default, as a stage sampler has always done
    assert nvidia_smi_stamp_to_epoch_s(stamp, received_epoch_s=first + 2.0) == pytest.approx(first, abs=1e-6)
    assert nvidia_smi_stamp_to_epoch_s(stamp, received_epoch_s=second + 2.0) == pytest.approx(second, abs=1e-6)


FAKE_SMI = """import os, sys, time
args = sys.argv[1:]
query = next(a for a in args if a.startswith("--query-gpu=")).split("=", 1)[1]
if "-lms" not in args:
    print("NVIDIA GeForce RTX 4070 SUPER" if query == "name" else "50.0")
    sys.exit(0)
with open(os.environ["FAKE_SMI_PID_FILE"], "w") as fh:
    fh.write(str(os.getpid()))
period = int(args[args.index("-lms") + 1]) / 1000.0
while True:
    now = time.time()
    stamp = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(now)) + ".%03d" % int((now % 1) * 1000)
    print(f"{stamp}, 50.0, 40, 1500", flush=True)
    time.sleep(period)
"""


def _install_fake_smi(tmp_path: Path) -> dict[str, str]:
    script = tmp_path / "fake_nvidia_smi.py"
    script.write_text(FAKE_SMI, encoding="utf-8")
    smi = tmp_path / "nvidia-smi"  # an sh wrapper: a #! line cannot hold an interpreter path with spaces
    smi.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    smi.chmod(smi.stat().st_mode | stat.S_IXUSR)
    return {"PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}", "FAKE_SMI_PID_FILE": str(tmp_path / "smi.pid")}


def _assert_wall_clock_trace(out: Path, before: float, after: float) -> None:
    trace = PowerTrace.model_validate(json.loads(out.read_text(encoding="utf-8")))
    assert trace.source == "nvidia-smi" and trace.query.startswith("timestamp,power.draw.instant,")
    assert trace.gpu_name == "NVIDIA GeForce RTX 4070 SUPER" and trace.gpu_vendor == "nvidia"
    assert trace.hostname_hash == env_mod.hostname_hash() and trace.clock == "unix_epoch_s" and trace.note is None
    assert len(trace.samples) >= 3 and all(s.power_w == 50.0 for s in trace.samples)
    # The fake stamps samples from time.time() through local time; they come back on that same clock.
    assert before - 0.05 <= trace.samples[0].t_epoch_s and trace.samples[-1].t_epoch_s <= after + 0.05
    assert before <= trace.started_epoch_s <= trace.samples[0].t_epoch_s + 0.05
    assert trace.samples[-1].t_epoch_s - 0.05 <= trace.stopped_epoch_s <= after
    assert all(a.t_epoch_s <= b.t_epoch_s for a, b in zip(trace.samples, trace.samples[1:]))


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT], ids=["sigterm", "sigint"])
def test_power_trace_cli_writes_a_wall_clock_trace_when_stopped(tmp_path: Path, sig: signal.Signals) -> None:
    fake = _install_fake_smi(tmp_path)
    out = tmp_path / "nested" / "trace.json"
    before = time.time()
    proc = subprocess.Popen([sys.executable, "-m", "psyfi_bench", "power-trace", "--out", str(out)], cwd=ROOT, env={**os.environ, **fake}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    watchdog = threading.Timer(30.0, proc.kill)
    watchdog.start()
    try:
        assert proc.stderr is not None
        first = proc.stderr.readline()  # the signal handlers are installed before this is printed
        assert "recording power.draw.instant" in first and "RTX 4070" in first, first
        time.sleep(0.6)
        os.kill(proc.pid, sig)
        _, err = proc.communicate(timeout=20.0)
    finally:
        watchdog.cancel()
    after = time.time()
    assert proc.returncode == 0, err
    assert "samples" in err and str(out) in err
    _assert_wall_clock_trace(out, before, after)
    pid = int((tmp_path / "smi.pid").read_text())
    with pytest.raises(ProcessLookupError):  # its nvidia-smi process is gone too
        os.kill(pid, 0)


def test_power_trace_cli_stops_after_a_duration(tmp_path: Path, monkeypatch, capsys) -> None:
    for key, value in _install_fake_smi(tmp_path).items():
        monkeypatch.setenv(key, value)
    out = tmp_path / "trace.json"
    before = time.time()
    assert cli_main(["power-trace", "--out", str(out), "--duration", "0.6"]) == 0
    _assert_wall_clock_trace(out, before, time.time())
    assert signal.getsignal(signal.SIGTERM) == signal.SIG_DFL  # the handlers are put back


def test_power_trace_cli_without_nvidia_smi_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(power_mod.shutil, "which", lambda name: None)
    out = tmp_path / "trace.json"
    assert cli_main(["power-trace", "--out", str(out), "--duration", "0.1"]) == 1
    assert not out.exists()
    assert "nvidia-smi" in capsys.readouterr().err


def test_power_trace_refuses_a_gpu_that_reports_no_power(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(power_mod.shutil, "which", lambda name: "/fake/nvidia-smi")
    monkeypatch.setattr("psyfi_bench.power_trace.probe_power_field", lambda: None)
    out = tmp_path / "trace.json"
    assert cli_main(["power-trace", "--out", str(out)]) == 1
    assert not out.exists() and "no power reading" in capsys.readouterr().err
