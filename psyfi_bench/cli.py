"""``psyfi-bench`` — headless execution, locking, ingest, scoring, reporting, contract export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from psyfi_bench import BENCH_NAME, BENCH_VERSION, NON_CLAIM


def _parse_kv(items: list[str] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items or []:
        key, _, raw = item.partition("=")
        if not key or not _:
            raise SystemExit(f"--param needs key=value, got {item!r}")
        try:
            out[key] = json.loads(raw)
        except json.JSONDecodeError:
            out[key] = raw
    return out


def cmd_list(args: argparse.Namespace) -> int:
    from psyfi_bench.registry import list_manifests

    rows = [m for m in list_manifests() if not args.family or m.family == args.family]
    if args.json:
        print(json.dumps([m.to_document() for m in rows], indent=2))
        return 0
    print(f"{'id':40s} {'v':>2s} {'family':15s} {'execution':24s} requires")
    for m in rows:
        print(f"{m.id:40s} {m.version:>2d} {m.family:15s} {m.execution:24s} {','.join(m.requires) or '-'}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    from psyfi_bench.registry import load_manifest

    print(json.dumps(load_manifest(args.manifest).to_document(), indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from psyfi_bench.registry import load_manifest
    from psyfi_bench.report import result_markdown
    from psyfi_bench.runner import RunContext, run_workload
    from psyfi_bench.store import ResultStore

    manifest = load_manifest(args.manifest)
    inputs = _parse_kv(args.param)
    if args.capture:
        inputs["capture"] = args.capture
    provider_options: dict[str, Any] = {}
    if args.record:
        provider_options["record"] = True
    if args.pricing:
        provider_options["pricing"] = json.loads(Path(args.pricing).read_text()) if Path(args.pricing).exists() else json.loads(args.pricing)
    store = None if args.no_store else ResultStore(Path(args.out) if args.out else None)
    ctx = RunContext(
        repeats=args.repeats,
        warmup_runs=args.warmup,
        timeout_s=args.timeout,
        min_duration_s=args.min_duration,
        seed=args.seed,
        limit=args.limit,
        provider=args.provider,
        provider_options=provider_options,
        backend=args.backend,
        store=store,
        inputs=inputs,
        command=" ".join(sys.argv),
        notes=[f"cli {BENCH_NAME} {BENCH_VERSION}"],
    )
    result = run_workload(manifest, ctx)
    if args.record and ctx.inputs.get("_receipt"):
        Path(args.record).write_text(json.dumps(ctx.inputs["_receipt"], indent=2) + "\n", encoding="utf-8")
        print(f"receipt written to {args.record}", file=sys.stderr)
    if args.json:
        print(json.dumps(result.model_dump(by_alias=True), indent=2, default=str))
    elif not args.quiet:
        print(result_markdown(result))
    if store is not None:
        print(f"stored: {store.root / str(result.manifest.get('family')) / (result.run_id + '.json')}", file=sys.stderr)
    return 0 if result.status == "complete" else (2 if result.status == "partial" else 1)


def cmd_lock(args: argparse.Namespace) -> int:
    from psyfi_bench.registry import load_manifest, manifest_paths, save_manifest

    ref = args.manifest
    path = next((p for p in manifest_paths() if load_manifest(p).id == ref or p.name == ref or str(p) == ref), None)
    manifest = load_manifest(path or ref)
    import importlib

    module = importlib.import_module(f"psyfi_bench.families.{manifest.family}")
    if not hasattr(module, "lock_references"):
        raise SystemExit(f"family {manifest.family} has no lock_references")
    locked = module.lock_references(manifest)
    print(json.dumps(locked.references, indent=2))
    if args.write:
        if path is None:
            raise SystemExit("cannot write: manifest did not come from the workloads directory")
        save_manifest(locked, path)
        print(f"written {path} hash={locked.manifest_hash}", file=sys.stderr)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from psyfi_bench.families.render import load_capture

    capture = load_capture(args.capture)
    ns = argparse.Namespace(manifest=args.manifest or capture.manifest_id, param=None, capture=args.capture, record=None, pricing=None, no_store=args.no_store, out=args.out, repeats=None, warmup=None, timeout=None, min_duration=None, seed=None, limit=None, provider=None, backend=None, json=args.json, quiet=args.quiet)
    return cmd_run(ns)


def cmd_validate(args: argparse.Namespace) -> int:
    from psyfi_bench.store import ResultStore

    result = ResultStore().load_path(Path(args.result))
    ok = result.verify()
    print(json.dumps({"run_id": result.run_id, "seal_valid": ok, "status": result.status, "measurement_class": result.measurement_class, "manifest_hash": result.manifest_hash, "failures": [f.model_dump() for f in result.failures]}, indent=2))
    return 0 if ok else 1


def cmd_score(args: argparse.Namespace) -> int:
    from psyfi_bench.report import scorecard_markdown
    from psyfi_bench.scoring import build_scorecard
    from psyfi_bench.store import ResultStore

    store = ResultStore()
    results = [store.load_path(Path(p)) for p in args.results]
    labels = args.labels.split(",") if args.labels else None
    card = build_scorecard(results, labels)
    if args.out:
        Path(args.out).write_text(json.dumps(card.model_dump(by_alias=True), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(card.model_dump(by_alias=True), indent=2) if args.json else scorecard_markdown(card))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from psyfi_bench.report import result_markdown
    from psyfi_bench.store import ResultStore

    print(result_markdown(ResultStore().load_path(Path(args.result))))
    return 0


def cmd_results(args: argparse.Namespace) -> int:
    from psyfi_bench.store import ResultStore

    entries = ResultStore(Path(args.out) if args.out else None).list(family=args.family)
    print(json.dumps(entries, indent=2))
    return 0


def cmd_capabilities(_: argparse.Namespace) -> int:
    import asyncio

    from psyfi_bench.api import capabilities

    print(json.dumps(asyncio.run(capabilities()), indent=2, default=str))
    return 0


def cmd_env(_: argparse.Namespace) -> int:
    from psyfi_bench.environment import collect_environment

    print(json.dumps(collect_environment().model_dump(), indent=2))
    return 0


def cmd_export_schemas(args: argparse.Namespace) -> int:
    from psyfi_bench.contracts import export_contracts

    written = export_contracts(Path(args.out) if args.out else None)
    for p in written:
        print(p)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="psyfi-bench", description=f"{BENCH_NAME} benchmark CLI ({BENCH_VERSION}). {NON_CLAIM}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list workload manifests")
    p.add_argument("--family")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("show", help="print one manifest")
    p.add_argument("manifest")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("run", help="run a workload headlessly")
    p.add_argument("manifest", help="id, id@version, or path")
    p.add_argument("--provider", help="oracle|constant|random|heuristic|replay:<f>|nvidia|anthropic:<m>|openai:<base>#<m>")
    p.add_argument("--backend", help="numpy|torch|torch-cuda|torch-mps")
    p.add_argument("--repeats", type=int)
    p.add_argument("--warmup", type=int)
    p.add_argument("--timeout", type=float)
    p.add_argument("--min-duration", type=float)
    p.add_argument("--seed", type=int)
    p.add_argument("--limit", type=int, help="limit stages/items (smoke runs)")
    p.add_argument("--param", action="append", help="override a manifest param: key=json")
    p.add_argument("--capture", help="browser capture JSON for webgpu render workloads")
    p.add_argument("--record", help="write a replayable provider receipt here")
    p.add_argument("--pricing", help="JSON or file: {input_per_million, output_per_million}")
    p.add_argument("--out", help="results directory (default bench_results/)")
    p.add_argument("--no-store", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("lock", help="recompute reference locks for a manifest")
    p.add_argument("manifest")
    p.add_argument("--write", action="store_true")
    p.set_defaults(fn=cmd_lock)

    p = sub.add_parser("ingest", help="score a browser GPU capture")
    p.add_argument("capture")
    p.add_argument("--manifest")
    p.add_argument("--out")
    p.add_argument("--no-store", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("validate", help="verify a result's seal")
    p.add_argument("result")
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("score", help="build a scorecard from result files")
    p.add_argument("results", nargs="+")
    p.add_argument("--labels", help="comma separated labels")
    p.add_argument("--out")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_score)

    p = sub.add_parser("report", help="markdown report of a result file")
    p.add_argument("result")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("results", help="list stored results")
    p.add_argument("--family")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_results)

    sub.add_parser("capabilities", help="capabilities document").set_defaults(fn=cmd_capabilities)
    sub.add_parser("env", help="environment record").set_defaults(fn=cmd_env)

    p = sub.add_parser("export-schemas", help="write JSON schemas, bench OpenAPI and examples")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_export_schemas)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
