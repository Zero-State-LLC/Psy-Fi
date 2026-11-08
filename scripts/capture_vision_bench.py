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
