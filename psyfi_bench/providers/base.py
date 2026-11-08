"""Provider protocol. One request, one response, one attempt. Keys stay in the environment."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import numpy as np

Locality = Literal["local", "remote", "baseline", "replay"]


@dataclass
class ModelRequest:
    prompt: str
    images: list[np.ndarray] = field(default_factory=list)
    structured: dict[str, Any] | None = None
    max_tokens: int = 64
    temperature: float = 0.0
    seed: int | None = None
    json_only: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def text(self) -> str:
        """Prompt plus the structured block (when any) as the model sees it."""
        if self.structured is None:
            return self.prompt
        return f"{self.prompt}\n\nSTRUCTURED_INPUT:\n{json.dumps(self.structured, sort_keys=True, separators=(',', ':'))}"

    def key(self) -> str:
        """Stable key for replay: prompt text, image bytes, params."""
        h = hashlib.sha256()
        h.update(self.text().encode("utf-8"))
        for img in self.images:
            h.update(str(img.shape).encode())
            h.update(np.ascontiguousarray(img).tobytes())
        h.update(json.dumps({"max_tokens": self.max_tokens, "temperature": self.temperature, "seed": self.seed, "json_only": self.json_only}, sort_keys=True).encode())
        return h.hexdigest()[:24]


@dataclass
class ModelResponse:
    text: str | None
    latency_ms: float
    provider: str
    model: str
    locality: Locality
    usage: dict[str, int] | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and self.text is not None


class ModelProvider(Protocol):
    name: str
    model: str
    locality: Locality

    def complete(self, request: ModelRequest) -> ModelResponse: ...

    def describe(self) -> dict[str, Any]: ...


def redact(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "[redacted]")
    return text.replace("\n", " ")[:300]
