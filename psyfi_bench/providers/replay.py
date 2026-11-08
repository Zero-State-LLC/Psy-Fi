"""Replay a recorded receipt: deterministic, offline, never a measurement of a live model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psyfi_bench.providers.base import ModelRequest, ModelResponse

RECEIPT_SCHEMA = "psyfi.bench.provider_receipt.v1"


class ReplayProvider:
    name = "replay"
    locality = "replay"

    def __init__(self, receipt: dict[str, Any] | str | Path) -> None:
        if not isinstance(receipt, dict):
            receipt = json.loads(Path(receipt).read_text(encoding="utf-8"))
        if receipt.get("schema") != RECEIPT_SCHEMA:
            raise ValueError(f"receipt schema must be {RECEIPT_SCHEMA}")
        self.receipt = receipt
        self.model = f"replay:{receipt.get('model', 'unknown')}"
        self.responses: dict[str, dict[str, Any]] = {r["key"]: r for r in receipt.get("responses", [])}

    def complete(self, request: ModelRequest) -> ModelResponse:
        rec = self.responses.get(request.key())
        if rec is None:
            return ModelResponse(text=None, latency_ms=0.0, provider=self.name, model=self.model, locality=self.locality, error="replay: no recorded response for this request key")
        return ModelResponse(
            text=rec.get("text"),
            latency_ms=float(rec.get("latency_ms", 0.0)),
            provider=self.name,
            model=self.model,
            locality=self.locality,
            usage=rec.get("usage"),
            error=rec.get("error"),
        )

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "model": self.model, "locality": self.locality, "recorded": len(self.responses), "source_provider": self.receipt.get("provider")}


class RecordingProvider:
    """Wrap a live provider and record every exchange into a replayable receipt."""

    locality = "remote"

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.name = inner.name
        self.model = inner.model
        self.locality = inner.locality
        self.responses: list[dict[str, Any]] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        resp = self.inner.complete(request)
        self.responses.append(
            {"key": request.key(), "text": resp.text, "latency_ms": resp.latency_ms, "usage": resp.usage, "error": resp.error}
        )
        return resp

    def receipt(self) -> dict[str, Any]:
        from psyfi_bench.timing import utc_now_iso

        return {
            "schema": RECEIPT_SCHEMA,
            "recorded_at": utc_now_iso(),
            "provider": self.inner.name,
            "model": self.inner.model,
            "locality": self.inner.locality,
            "responses": self.responses,
            "note": "Raw model answers. Contains no key. Replaying this receipt is not a live measurement.",
        }

    def describe(self) -> dict[str, Any]:
        d = dict(self.inner.describe())
        d["recording"] = True
        return d
