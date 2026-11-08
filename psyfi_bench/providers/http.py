"""HTTP providers: OpenAI-compatible chat completions (covers vLLM, llama.cpp server, Ollama,
LM Studio, NVIDIA integrate) and the Anthropic Messages API. One POST per request, no retry.
Keys are read from the environment at call time and redacted from every stored string.
"""

from __future__ import annotations

import base64
import io
import json
import os
import time
from typing import Any

import httpx
import numpy as np

from psyfi_bench.providers.base import ModelRequest, ModelResponse, redact

DEFAULT_TIMEOUT_S = 60.0
LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]", "host.docker.internal")


def png_data_url(rgba: np.ndarray) -> str:
    from PIL import Image

    img = Image.fromarray(np.ascontiguousarray(rgba, dtype=np.uint8), mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def png_base64(rgba: np.ndarray) -> str:
    return png_data_url(rgba).split(",", 1)[1]


def is_local_url(url: str) -> bool:
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    return host in LOCAL_HOSTS or host.endswith(".local") or host.endswith(".localhost")


class ProviderError(RuntimeError):
    pass


class OpenAICompatProvider:
    """``POST {base_url}/v1/chat/completions`` with optional image parts."""

    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key_env: str | None = "OPENAI_API_KEY",
        extra_body: dict[str, Any] | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
        name: str | None = None,
        require_prefix: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.extra_body = dict(extra_body or {})
        self.timeout_s = timeout_s
        self.transport = transport
        if name:
            self.name = name
        if require_prefix and not model.startswith(require_prefix):
            raise ProviderError(f"model id must start with {require_prefix!r}")
        self.locality = "local" if is_local_url(self.base_url) else "remote"

    def _key(self) -> str:
        return (os.environ.get(self.api_key_env) or "").strip() if self.api_key_env else ""

    def body(self, request: ModelRequest) -> dict[str, Any]:
        parts: list[dict[str, Any]] = [{"type": "text", "text": request.text()}]
        for img in request.images:
            parts.append({"type": "image_url", "image_url": {"url": png_data_url(img)}})
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": parts}],
        }
        if request.seed is not None:
            body["seed"] = request.seed
        if request.json_only and self.extra_body.get("response_format", True) is not False:
            body.setdefault("response_format", {"type": "json_object"})
        for k, v in self.extra_body.items():
            if k == "response_format" and v is False:
                body.pop("response_format", None)
                continue
            body[k] = v
        return body

    def complete(self, request: ModelRequest) -> ModelResponse:
        key = self._key()
        if self.api_key_env and not key and self.locality == "remote":
            return ModelResponse(text=None, latency_ms=0.0, provider=self.name, model=self.model, locality=self.locality, error=f"{self.api_key_env} is unset; no socket opened")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        url = f"{self.base_url}/v1/chat/completions"
        body = self.body(request)
        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_s, transport=self.transport) as client:
                resp = client.post(url, headers=headers, content=json.dumps(body).encode())
            latency = (time.perf_counter() - t0) * 1000
            if resp.status_code >= 400:
                return ModelResponse(text=None, latency_ms=latency, provider=self.name, model=self.model, locality=self.locality, error=f"provider HTTP {resp.status_code}: {redact(resp.text, [key])}")
            payload = resp.json()
        except httpx.TimeoutException:
            return ModelResponse(text=None, latency_ms=(time.perf_counter() - t0) * 1000, provider=self.name, model=self.model, locality=self.locality, error="provider timeout")
        except (httpx.HTTPError, ValueError) as exc:
            return ModelResponse(text=None, latency_ms=(time.perf_counter() - t0) * 1000, provider=self.name, model=self.model, locality=self.locality, error=f"provider error: {redact(str(exc), [key])}")
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ModelResponse(text=None, latency_ms=latency, provider=self.name, model=self.model, locality=self.locality, error="provider returned no content", raw=None)
        if isinstance(content, list):
            content = " ".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in content)
        usage = payload.get("usage") or None
        norm_usage = None
        if isinstance(usage, dict):
            norm_usage = {
                "input_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
                "output_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
            }
        timings: dict[str, float] = {}
        # llama.cpp / vLLM expose server-side timings when enabled; keep them when present.
        for k in ("timings",):
            if isinstance(payload.get(k), dict):
                timings = {str(a): float(b) for a, b in payload[k].items() if isinstance(b, (int, float))}
        return ModelResponse(text=str(content).strip(), latency_ms=latency, provider=self.name, model=self.model, locality=self.locality, usage=norm_usage, timings=timings)

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "model": self.model, "locality": self.locality, "base_url": self.base_url, "api_key_env": self.api_key_env, "timeout_s": self.timeout_s}


def nvidia_provider(model: str | None = None, *, transport: httpx.BaseTransport | None = None) -> OpenAICompatProvider:
    """NVIDIA integrate host: an ``nvidia/`` id from the environment, key in NVIDIA_API_KEY. Never pinned here."""
    model_id = (model or os.environ.get("NVIDIA_VISION_MODEL") or "").strip()
    if not model_id or model_id.startswith("@cf/") or not model_id.startswith("nvidia/"):
        raise ProviderError("NVIDIA_VISION_MODEL must be an nvidia/ vision model id")
    base = (os.environ.get("NVIDIA_API_BASE") or "").strip() or "https://integrate.api.nvidia.com"
    return OpenAICompatProvider(base, model_id, api_key_env="NVIDIA_API_KEY", extra_body={"reasoning_effort": "none", "response_format": False}, name="nvidia", transport=transport)


class AnthropicProvider:
    """``POST https://api.anthropic.com/v1/messages`` with base64 image blocks."""

    name = "anthropic"
    locality = "remote"

    def __init__(self, model: str, *, api_key_env: str = "ANTHROPIC_API_KEY", base_url: str = "https://api.anthropic.com", timeout_s: float = DEFAULT_TIMEOUT_S, transport: httpx.BaseTransport | None = None) -> None:
        if not model:
            raise ProviderError("anthropic provider needs a model id (--model or ANTHROPIC_MODEL)")
        self.model = model
        self.api_key_env = api_key_env
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.transport = transport

    def body(self, request: ModelRequest) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        for img in request.images:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_base64(img)}})
        content.append({"type": "text", "text": request.text()})
        return {"model": self.model, "max_tokens": request.max_tokens, "temperature": request.temperature, "messages": [{"role": "user", "content": content}]}

    def complete(self, request: ModelRequest) -> ModelResponse:
        key = (os.environ.get(self.api_key_env) or "").strip()
        if not key:
            return ModelResponse(text=None, latency_ms=0.0, provider=self.name, model=self.model, locality=self.locality, error=f"{self.api_key_env} is unset; no socket opened")
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_s, transport=self.transport) as client:
                resp = client.post(f"{self.base_url}/v1/messages", headers=headers, content=json.dumps(self.body(request)).encode())
            latency = (time.perf_counter() - t0) * 1000
            if resp.status_code >= 400:
                return ModelResponse(text=None, latency_ms=latency, provider=self.name, model=self.model, locality=self.locality, error=f"provider HTTP {resp.status_code}: {redact(resp.text, [key])}")
            payload = resp.json()
        except httpx.TimeoutException:
            return ModelResponse(text=None, latency_ms=(time.perf_counter() - t0) * 1000, provider=self.name, model=self.model, locality=self.locality, error="provider timeout")
        except (httpx.HTTPError, ValueError) as exc:
            return ModelResponse(text=None, latency_ms=(time.perf_counter() - t0) * 1000, provider=self.name, model=self.model, locality=self.locality, error=f"provider error: {redact(str(exc), [key])}")
        text = " ".join(str(b.get("text", "")) for b in payload.get("content", []) if isinstance(b, dict) and b.get("type") == "text").strip()
        if not text:
            return ModelResponse(text=None, latency_ms=latency, provider=self.name, model=self.model, locality=self.locality, error="provider returned no text block")
        usage = payload.get("usage") or {}
        return ModelResponse(text=text, latency_ms=latency, provider=self.name, model=self.model, locality=self.locality, usage={"input_tokens": int(usage.get("input_tokens") or 0), "output_tokens": int(usage.get("output_tokens") or 0)})

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "model": self.model, "locality": self.locality, "base_url": self.base_url, "api_key_env": self.api_key_env}
