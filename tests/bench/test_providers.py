"""Providers: baselines, replay/recording, OpenAI-compatible and Anthropic over a mock transport."""

from __future__ import annotations

import json

import httpx
import numpy as np
import pytest

from psyfi_bench.providers.base import ModelRequest
from psyfi_bench.providers.http import AnthropicProvider, OpenAICompatProvider, ProviderError, nvidia_provider
from psyfi_bench.providers.registry import describe_available, make_provider
from psyfi_bench.providers.replay import RECEIPT_SCHEMA, RecordingProvider, ReplayProvider

IMG = (np.random.default_rng(1).uniform(0, 255, (32, 32, 4))).astype(np.uint8)


def test_request_key_depends_on_prompt_images_and_params() -> None:
    a = ModelRequest(prompt="p", images=[IMG])
    b = ModelRequest(prompt="p", images=[IMG])
    c = ModelRequest(prompt="q", images=[IMG])
    d = ModelRequest(prompt="p", images=[IMG], max_tokens=128)
    assert a.key() == b.key() and a.key() != c.key() and a.key() != d.key()
    assert "STRUCTURED_INPUT" in ModelRequest(prompt="p", structured={"a": 1}).text()


def test_baselines_and_registry() -> None:
    oracle = make_provider("oracle").complete(ModelRequest(prompt="x", metadata={"reference": {"mode": "void", "intensity": 0.2}}))
    assert json.loads(oracle.text) == {"mode": "void", "intensity": 0.2}
    const = make_provider("constant:power:0.9").complete(ModelRequest(prompt="x"))
    assert json.loads(const.text) == {"mode": "power", "intensity": 0.9}
    r1 = make_provider("random:5").complete(ModelRequest(prompt="x"))
    r2 = make_provider("random:5").complete(ModelRequest(prompt="x"))
    assert r1.text == r2.text
    heur = make_provider("heuristic").complete(ModelRequest(prompt="x", images=[IMG]))
    assert json.loads(heur.text)["mode"] in {"open", "attractor", "void", "power"}
    assert all(p.locality == "baseline" for p in (make_provider(s) for s in ("oracle", "constant", "random", "heuristic")))
    with pytest.raises(ProviderError):
        make_provider("teleport")
    with pytest.raises(ProviderError):
        make_provider("openai:nobase")
    specs = {d["spec"] for d in describe_available()}
    assert {"oracle", "nvidia"} <= specs


def _openai_handler(seen: list[dict], *, status: int = 200, content="{\"mode\": \"void\", \"intensity\": 0.4}"):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"url": str(request.url), "headers": dict(request.headers), "body": json.loads(request.content)})
        if status != 200:
            return httpx.Response(status, json={"error": "nope secret-key-123"})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 120, "completion_tokens": 12}})

    return handler


def test_openai_compatible_provider_builds_the_request_and_redacts(monkeypatch) -> None:
    seen: list[dict] = []
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key-123")
    provider = OpenAICompatProvider("https://example.invalid", "test-vlm", transport=httpx.MockTransport(_openai_handler(seen)))
    assert provider.locality == "remote"
    resp = provider.complete(ModelRequest(prompt="read", images=[IMG], max_tokens=32, seed=3))
    assert resp.ok and json.loads(resp.text)["mode"] == "void"
    assert resp.usage == {"input_tokens": 120, "output_tokens": 12}
    body = seen[0]["body"]
    assert body["model"] == "test-vlm" and body["max_tokens"] == 32 and body["seed"] == 3
    assert body["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert body["response_format"] == {"type": "json_object"}
    assert seen[0]["headers"]["authorization"] == "Bearer secret-key-123"
    assert seen[0]["url"].endswith("/v1/chat/completions")

    failing = OpenAICompatProvider("https://example.invalid", "test-vlm", transport=httpx.MockTransport(_openai_handler(seen, status=500)))
    bad = failing.complete(ModelRequest(prompt="read"))
    assert not bad.ok and "500" in bad.error and "secret-key-123" not in bad.error and "[redacted]" in bad.error


def test_openai_compatible_local_endpoint_needs_no_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    seen: list[dict] = []
    local = OpenAICompatProvider("http://localhost:8080", "llava", transport=httpx.MockTransport(_openai_handler(seen)))
    assert local.locality == "local"
    assert local.complete(ModelRequest(prompt="x")).ok
    assert "authorization" not in seen[0]["headers"]
    remote = OpenAICompatProvider("https://api.example.invalid", "m", transport=httpx.MockTransport(_openai_handler(seen)))
    unset = remote.complete(ModelRequest(prompt="x"))
    assert unset.error and "unset" in unset.error and len(seen) == 1, "no socket when the key is unset"


def test_nvidia_provider_enforces_namespace_and_reasoning_effort(monkeypatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvkey-xyz")
    monkeypatch.setenv("NVIDIA_VISION_MODEL", "gemma")
    with pytest.raises(ProviderError):
        nvidia_provider()
    monkeypatch.setenv("NVIDIA_VISION_MODEL", "@cf/nvidia/x")
    with pytest.raises(ProviderError):
        nvidia_provider()
    monkeypatch.setenv("NVIDIA_VISION_MODEL", "nvidia/bench-test")
    seen: list[dict] = []
    provider = nvidia_provider(transport=httpx.MockTransport(_openai_handler(seen)))
    assert provider.complete(ModelRequest(prompt="x", images=[IMG])).ok
    assert seen[0]["body"]["reasoning_effort"] == "none"
    assert "response_format" not in seen[0]["body"]
    assert seen[0]["url"].startswith("https://integrate.api.nvidia.com")


def test_anthropic_provider_shape(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-secret")
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"headers": dict(request.headers), "body": json.loads(request.content), "url": str(request.url)})
        return httpx.Response(200, json={"content": [{"type": "text", "text": "{\"mode\": \"open\", \"intensity\": 0.5}"}], "usage": {"input_tokens": 50, "output_tokens": 9}})

    provider = AnthropicProvider("test-model", transport=httpx.MockTransport(handler))
    resp = provider.complete(ModelRequest(prompt="read", images=[IMG]))
    assert resp.ok and resp.usage == {"input_tokens": 50, "output_tokens": 9}
    body = seen[0]["body"]
    assert body["messages"][0]["content"][0]["type"] == "image"
    assert body["messages"][0]["content"][0]["source"]["media_type"] == "image/png"
    assert seen[0]["headers"]["x-api-key"] == "ant-secret"
    assert seen[0]["url"].endswith("/v1/messages")
    with pytest.raises(ProviderError):
        AnthropicProvider("")


def test_recording_then_replay_round_trip(tmp_path) -> None:
    inner = make_provider("constant:void:0.3")
    rec = RecordingProvider(inner)
    req = ModelRequest(prompt="p", images=[IMG])
    first = rec.complete(req)
    receipt = rec.receipt()
    assert receipt["schema"] == RECEIPT_SCHEMA and len(receipt["responses"]) == 1
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    replay = ReplayProvider(path)
    again = replay.complete(req)
    assert again.text == first.text and again.locality == "replay"
    miss = replay.complete(ModelRequest(prompt="other"))
    assert miss.error and "no recorded response" in miss.error
    with pytest.raises(ValueError):
        ReplayProvider({"schema": "wrong"})
