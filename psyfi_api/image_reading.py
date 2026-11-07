"""Inferred image caption. Not an input to ParameterField, the seed, or presets."""

from __future__ import annotations

import base64
import io
import json
import os
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

from psyfi_core.visualization.image_seed import _MAX_EDGE, _resize_max_edge, decode_image_bytes

_DEFAULT_BASE = "https://integrate.api.nvidia.com"
_MAX_BYTES = 12_000_000
_MAX_CAPTION = 2000
_DISCLAIMER = (
    "Not medical advice. This caption is inferred and is not a diagnosis. "
    "ParameterField remains visual authority."
)
_PROMPT = (
    "Describe only what is visible in this image. "
    "Do not diagnose, name a substance, or give medical advice. "
    "One short paragraph."
)


class VisionConfigError(Exception):
    """Model id or key is missing or not an nvidia/ id. No socket was opened."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class VisionProviderError(Exception):
    """The provider answered once with a failure. Do not retry or fall back."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def configured_model(raw: str | None) -> str:
    model = (raw or "").strip()
    if not model or model.startswith("@cf/") or not model.startswith("nvidia/"):
        raise VisionConfigError("NVIDIA_VISION_MODEL must be an nvidia/ vision model id")
    return model


def read_image(data: bytes) -> dict[str, str]:
    """Return an inferred caption. Reads env per call and posts at most once."""
    model = configured_model(os.environ.get("NVIDIA_VISION_MODEL"))
    key = (os.environ.get("NVIDIA_API_KEY") or "").strip()
    if not key:
        raise VisionConfigError("NVIDIA_API_KEY is unset")
    if not data:
        raise ValueError("empty image")
    if len(data) > _MAX_BYTES:
        raise ValueError("image too large (max ~12MB)")

    rgba = _resize_max_edge(decode_image_bytes(data), _MAX_EDGE)
    base = (os.environ.get("NVIDIA_API_BASE") or "").strip() or _DEFAULT_BASE
    payload = _post_once(
        base,
        key,
        {
            "model": model,
            "max_tokens": 256,
            "reasoning_effort": "none",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {"type": "image_url", "image_url": {"url": _png_data_url(rgba)}},
                    ],
                }
            ],
        },
    )
    return {
        "schema_version": "psyfi.image_reading.v1",
        "authority": "INFERRED",
        "caption": _caption(payload)[:_MAX_CAPTION],
        "model": model,
        "disclaimer": _DISCLAIMER,
    }


def _png_data_url(rgba: np.ndarray) -> str:
    u8 = (np.clip(rgba, 0, 1) * 255.0).astype(np.uint8)
    img = Image.fromarray(u8, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _post_once(base: str, key: str, body: dict) -> dict:
    url = base.rstrip("/") + "/v1/chat/completions"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            try:
                raw = response.read()
            except TimeoutError as exc:
                raise VisionProviderError("vision provider unreachable") from exc
    except TimeoutError as exc:
        raise VisionProviderError("vision provider unreachable") from exc
    except urllib.error.HTTPError as exc:
        message = _safe_provider_message(exc.read(500), key)
        raise VisionProviderError(message) from exc
    except urllib.error.URLError as exc:
        raise VisionProviderError("vision provider unreachable") from exc
    try:
        parsed = json.loads(raw.decode())
    except json.JSONDecodeError as exc:
        raise VisionProviderError("vision provider returned non-JSON") from exc
    if not isinstance(parsed, dict):
        raise VisionProviderError("vision provider returned non-JSON")
    return parsed


def _safe_provider_message(raw: bytes, key: str) -> str:
    text = raw.decode("utf-8", errors="replace").replace("\n", " ")
    if key:
        text = text.replace(key, "[redacted]")
    text = text.strip()[:180]
    return text or "vision provider rejected the request"


def _caption(payload: dict) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionProviderError("vision provider returned no caption") from exc
    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text") or ""))
        text = " ".join(parts).strip()
    else:
        text = ""
    if not text:
        raise VisionProviderError("vision provider returned an empty caption")
    return text
