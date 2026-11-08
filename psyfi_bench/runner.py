"""Execution orchestration: protocol, repeats, memory probe, timeouts, failure classification."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from psyfi_bench import NON_CLAIM
from psyfi_bench.determinism import compare_repeats, record_for
from psyfi_bench.environment import collect_environment
from psyfi_bench.registry import get_family_runner
from psyfi_bench.schemas import (
    BenchResult,
    DeterminismRecord,
    EnvironmentRecord,
    FailureRecord,
    MemoryRecord,
    Protocol,
    Provenance,
    StageRecord,
    WorkloadManifest,
)
from psyfi_bench.stats import summarize
from psyfi_bench.store import ResultStore
from psyfi_bench.timing import Deadline, memory_probe, run_id, time_call, utc_now_iso


@dataclass
class RunContext:
    """Per-run overrides and services. ``None`` means "use the manifest protocol"."""

    repeats: int | None = None
    warmup_runs: int | None = None
    timeout_s: float | None = None
    min_duration_s: float | None = None
    seed: int | None = None
    limit: int | None = None
    provider: str | None = None
    provider_options: dict[str, Any] = field(default_factory=dict)
    backend: str | None = None
    store: ResultStore | None = None
    environment: EnvironmentRecord | None = None
    cancel: Callable[[], bool] | None = None
    include_gpu_env: bool = True
    command: str | None = None
    notes: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)

    RESERVED_INPUTS = ("capture", "_receipt")

    def param_overrides(self) -> dict[str, Any]:
        """Inputs that override manifest params (recorded in the result; they change the manifest hash)."""
        return {k: v for k, v in self.inputs.items() if k not in self.RESERVED_INPUTS}

    def effective_manifest(self, manifest: WorkloadManifest) -> WorkloadManifest:
        overrides = self.param_overrides()
        if not overrides:
            return manifest
        return manifest.model_copy(update={"params": {**manifest.params, **overrides}})

    def protocol(self, manifest: WorkloadManifest) -> Protocol:
        p = manifest.protocol.model_copy()
        if self.repeats is not None:
            p.repeats = self.repeats
        if self.warmup_runs is not None:
            p.warmup_runs = self.warmup_runs
        if self.timeout_s is not None:
            p.timeout_s = self.timeout_s
        if self.min_duration_s is not None:
            p.min_duration_s = self.min_duration_s
        return p


@dataclass
class FamilyOutput:
    stages: list[StageRecord]
    metrics: dict[str, Any] = field(default_factory=dict)
    determinism: dict[str, Any] = field(default_factory=dict)
    failures: list[FailureRecord] = field(default_factory=list)
    measurement_class: str = "measured"
    notes: list[str] = field(default_factory=list)


def classify_exception(exc: BaseException) -> str:
    from psyfi_core.abx_core.errors import SimulationCancelled

    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, (InterruptedError, KeyboardInterrupt, SimulationCancelled)):
        return "cancelled"
    if isinstance(exc, MemoryError):
        return "resource"
    if isinstance(exc, (ImportError, NotImplementedError)):
        return "unsupported"
    if isinstance(exc, (ValueError, TypeError, AssertionError)):
        return "validation"
    name = type(exc).__name__.lower()
    if "provider" in name or "http" in name or "connection" in name:
        return "provider"
    if "parse" in name or "json" in name:
        return "parse"
    return "internal"


def _short(exc: BaseException, limit: int = 240) -> str:
    text = f"{type(exc).__name__}: {exc}".replace("\n", " ")
    return text[:limit]


def measure_stage(
    *,
    stage_id: str,
    kind: str,
    params: dict[str, Any],
    fn: Callable[[Callable[[], bool]], Any],
    protocol: Protocol,
    quantization: float,
    reference_digest: str | None = None,
    digest_fn: Callable[[Any], np.ndarray | None] | None = None,
    metrics_fn: Callable[[Any, list[float]], dict[str, Any]] | None = None,
    cancel: Callable[[], bool] | None = None,
    measurement_class: str = "measured",
) -> StageRecord:
    """Run ``fn(should_cancel)`` under the protocol and summarize.

    ``fn`` receives a cooperative cancel callback (deadline + external cancel).
    ``digest_fn`` maps the result to an ndarray for determinism digests.
    """
    stage = StageRecord(id=stage_id, kind=kind, params=params, measurement_class=measurement_class)  # type: ignore[arg-type]
    deadline = Deadline(protocol.timeout_s, cancel)
    determinism: list[DeterminismRecord] = []
    last_result: Any = None
    try:
        warmups = max(protocol.warmup_runs, 1 if protocol.cold_start else 0)
        for i in range(warmups):
            deadline.check()
            t = time_call(lambda: fn(deadline.should_cancel))
            if i == 0 and protocol.cold_start:
                stage.cold_wall_ms = t.wall_ms
            stage.warmup_wall_ms.append(t.wall_ms)
            last_result = t.result

        repeats_done = 0
        import time as _time

        started = _time.perf_counter()
        while True:
            deadline.check()
            t = time_call(lambda: fn(deadline.should_cancel))
            stage.wall_ms.append(t.wall_ms)
            stage.cpu_ms.append(t.cpu_ms)
            last_result = t.result
            if digest_fn is not None:
                arr = digest_fn(t.result)
                if arr is not None:
                    determinism.append(record_for(arr, quantization=quantization, reference=reference_digest))
            repeats_done += 1
            if protocol.min_duration_s is not None:
                if (_time.perf_counter() - started) >= protocol.min_duration_s and repeats_done >= protocol.repeats:
                    break
            elif repeats_done >= protocol.repeats:
                break

        if protocol.memory_probe:
            deadline.check()
            m = memory_probe(lambda: fn(deadline.should_cancel))
            stage.memory = MemoryRecord(
                rss_before_bytes=m.rss_before_bytes,
                rss_peak_delta_bytes=m.rss_peak_delta_bytes,
                tracemalloc_peak_bytes=m.tracemalloc_peak_bytes,
                tracemalloc_current_bytes=m.tracemalloc_current_bytes,
                note="single probe under tracemalloc; its timing is excluded",
            )
        else:
            stage.memory = MemoryRecord(note="memory probe disabled by protocol")

        stage.statistics["wall_ms"] = summarize(
            stage.wall_ms, unit="ms", resamples=protocol.bootstrap_resamples, seed=protocol.bootstrap_seed
        )
        cpu = [c for c in stage.cpu_ms if np.isfinite(c)]
        if cpu:
            stage.statistics["cpu_ms"] = summarize(
                cpu, unit="ms", resamples=protocol.bootstrap_resamples, seed=protocol.bootstrap_seed
            )
        if determinism:
            agg = compare_repeats(determinism)
            rec = determinism[-1].model_copy()
            rec.bitwise_identical_across_repeats = agg["bitwise_identical_across_repeats"]
            rec.quantized_identical_across_repeats = agg["quantized_identical_across_repeats"]
            stage.determinism = rec
        if metrics_fn is not None:
            stage.metrics.update(metrics_fn(last_result, stage.wall_ms))
        stage.status = "ok"
    except BaseException as exc:  # noqa: BLE001 — every failure becomes evidence
        if isinstance(exc, KeyboardInterrupt):
            stage.status = "cancelled"
        else:
            category = classify_exception(exc)
            stage.status = "timeout" if (category == "timeout" or deadline.expired) else (
                "cancelled" if category == "cancelled" else "failed"
            )
        stage.error = _short(exc)
        if stage.wall_ms:
            stage.statistics["wall_ms"] = summarize(stage.wall_ms, unit="ms", seed=protocol.bootstrap_seed)
    return stage


def failures_from_stages(stages: list[StageRecord]) -> list[FailureRecord]:
    out: list[FailureRecord] = []
    for s in stages:
        if s.status == "ok":
            continue
        category = {
            "timeout": "timeout",
            "cancelled": "cancelled",
            "skipped": "unsupported",
        }.get(s.status, "internal")
        if s.status == "failed" and s.error:
            low = s.error.lower()
            if "provider" in low or "http" in low:
                category = "provider"
            elif "parse" in low or "json" in low:
                category = "parse"
            elif "valueerror" in low or "validation" in low:
                category = "validation"
            elif "memoryerror" in low:
                category = "resource"
            elif "import" in low or "not installed" in low or "unsupported" in low:
                category = "unsupported"
        out.append(FailureRecord(stage=s.id, category=category, detail=s.error or s.status))  # type: ignore[arg-type]
    return out


def run_workload(manifest: WorkloadManifest, ctx: RunContext | None = None) -> BenchResult:
    """Execute a manifest end to end and return a sealed result."""
    ctx = ctx or RunContext()
    env = ctx.environment or collect_environment(include_gpu=ctx.include_gpu_env)
    manifest = ctx.effective_manifest(manifest)
    if ctx.param_overrides():
        ctx.notes.append(f"params overridden: {sorted(ctx.param_overrides())}; manifest_hash reflects the effective workload")
    runner = get_family_runner(manifest.family)
    output: FamilyOutput = runner(manifest, ctx, env)

    stages = list(output.stages)
    failures = list(output.failures) + [f for f in failures_from_stages(stages) if f.stage not in {x.stage for x in output.failures}]
    ok = [s for s in stages if s.status == "ok"]
    if stages and not ok:
        status = "failed"
    elif failures or any(s.status != "ok" for s in stages):
        status = "partial"
    else:
        status = "complete"

    git_commit = (env.software or {}).get("git_commit")
    git_dirty = (env.software or {}).get("git_dirty")
    result = BenchResult(
        run_id=run_id(manifest.family.replace("_", "-")),
        created_at=utc_now_iso(),
        manifest=manifest.to_document(),
        manifest_hash=manifest.manifest_hash,
        measurement_class=output.measurement_class,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        environment=env,
        stages=stages,
        metrics=output.metrics,
        determinism=output.determinism,
        failures=failures,
        provenance=Provenance(
            git_commit=git_commit,
            git_dirty=git_dirty,
            command=ctx.command or " ".join(sys.argv[:6]),
            psyfi_version=(env.software or {}).get("psyfi_version"),
            seed=ctx.seed,
            notes=list(ctx.notes) + list(output.notes),
        ),
        non_claim=NON_CLAIM,
    ).seal()
    if ctx.store is not None:
        ctx.store.save(result)
    return result
