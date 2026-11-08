"""Markdown rendering of results and scorecards (printed, never committed by a test run)."""

from __future__ import annotations

from typing import Any

from psyfi_bench.schemas import BenchResult, Scorecard


def _fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        if v != v:
            return "nan"
        return f"{v:.4g}" if abs(v) < 1e5 else f"{v:.3e}"
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
        return f"[{v[0]:.4g}, {v[1]:.4g}]"
    return str(v)


def result_markdown(result: BenchResult) -> str:
    env = result.environment
    m = result.manifest
    lines = [
        f"# {m.get('title', m.get('id'))}",
        "",
        f"- run `{result.run_id}` · {result.created_at} · status **{result.status}** · class **{result.measurement_class}**",
        f"- manifest `{m.get('id')}@{m.get('version')}` hash `{result.manifest_hash}` · bench {result.bench_version}",
        f"- host: {(env.cpu or {}).get('brand') or 'unknown CPU'} · {', '.join(g.name for g in env.gpus) or 'no GPU inventory'} · class {env.hardware_class} · {env.platform.get('system')} {env.platform.get('machine')}",
        f"- software: python {env.software.get('python')} numpy {env.software.get('numpy')} · git {str(env.software.get('git_commit'))[:10]}{' (dirty)' if env.software.get('git_dirty') else ''}",
    ]
    if env.unavailable:
        lines.append("- unavailable telemetry: " + "; ".join(f"{k}: {v}" for k, v in env.unavailable.items()))
    if result.failures:
        lines.append("")
        lines.append("## Failures")
        for f in result.failures:
            lines.append(f"- `{f.stage}` **{f.category}**: {f.detail}")
    lines += ["", "## Stages", "", "| stage | status | n | wall p50 ms | p95 ms | CV | cold ms | key metrics |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in result.stages:
        st = s.statistics.get("wall_ms") or s.statistics.get("frame_ms") or s.statistics.get("latency_ms") or s.statistics.get("end_to_end_ms")
        keys = {k: v for k, v in s.metrics.items() if isinstance(v, (int, float, bool)) and k not in ("cells", "steps", "cell_steps", "pixels")}
        key_text = ", ".join(f"{k}={_fmt(v)}" for k, v in list(keys.items())[:6])
        lines.append(f"| `{s.id}` | {s.status} | {st.n if st else 0} | {_fmt(st.p50) if st else 'n/a'} | {_fmt(st.p95) if st else 'n/a'} | {_fmt(st.cv) if st else 'n/a'} | {_fmt(s.cold_wall_ms)} | {key_text} |")
    lines += ["", "## Headline metrics", ""]
    for k, v in result.metrics.items():
        if isinstance(v, dict):
            flat = {kk: vv for kk, vv in v.items() if isinstance(vv, (int, float, bool, str)) or vv is None}
            if flat:
                lines.append(f"- **{k}**: " + ", ".join(f"{kk}={_fmt(vv)}" for kk, vv in flat.items()))
            else:
                lines.append(f"- **{k}**: (nested)")
        elif isinstance(v, list):
            lines.append(f"- **{k}**: {len(v)} entries")
        else:
            lines.append(f"- **{k}**: {_fmt(v)}")
    lines += ["", f"_{result.non_claim}_", ""]
    return "\n".join(lines)


def scorecard_markdown(card: Scorecard) -> str:
    labels = [s["label"] for s in card.subjects]
    lines = [
        f"# Scorecard · {card.family} · `{card.manifest_id}`",
        "",
        f"- generated {card.generated_at} · manifest hash `{card.manifest_hash}`",
        f"- comparable: **{'yes' if card.validity.get('comparable') else 'no'}**" + (f" ({'; '.join(card.validity.get('reasons', []))})" if card.validity.get("reasons") else ""),
        "",
        "## Subjects",
        "",
        "| label | run | class | status | hardware | cpu | gpus | provider/backend |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in card.subjects:
        lines.append(f"| {s['label']} | `{s['run_id']}` | {s['measurement_class']} | {s['status']} | {s.get('hardware_class')} | {s.get('cpu') or ''} | {', '.join(s.get('gpus') or [])} | {s.get('provider') or s.get('backend') or ''} |")
    lines += ["", "## Dimensions", "", "| dimension | unit | better | " + " | ".join(labels) + " |", "| --- | --- | --- | " + " | ".join("---" for _ in labels) + " |"]
    for name, row in card.dimensions.items():
        any_dim = next(iter(row.values()))
        cells = []
        for label in labels:
            d = row.get(label)
            if d is None or d.value is None:
                cells.append(f"n/a ({(d.missing_reason if d else 'absent')})")
            else:
                cells.append(_fmt(d.value) + (f" CI {_fmt(d.ci95)}" if d.ci95 else ""))
        lines.append(f"| {name} | {any_dim.unit} | {any_dim.better} | " + " | ".join(cells) + " |")
    if card.composites:
        lines += ["", "## Composites (published formulas; null when inputs are missing)", ""]
        for label in labels:
            for name, spec in (card.composites.get(label) or {}).items():
                lines.append(f"- **{label} · {name}** = {_fmt(spec.get('value'))} · `{spec.get('formula')}` · valid: {spec.get('valid_comparison')}")
    if card.recommendations:
        lines += ["", "## Recommendations", ""] + [f"- {r}" for r in card.recommendations]
    lines += ["", f"_{card.non_claim}_", ""]
    return "\n".join(lines)


SCORECARD_CSV_COLUMNS = ("dimension", "unit", "better", "label", "value", "ci95_low", "ci95_high", "source", "missing_reason")


def scorecard_csv(card: Scorecard) -> str:
    """One row per (dimension, subject). Missing values stay empty with ``missing_reason`` set; nothing is imputed."""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(SCORECARD_CSV_COLUMNS)
    for name, row in card.dimensions.items():
        for label, d in row.items():
            lo, hi = d.ci95 if d.ci95 else (None, None)
            writer.writerow(["" if v is None else v for v in (name, d.unit, d.better, label, d.value, lo, hi, d.source, d.missing_reason)])
    return buf.getvalue()
