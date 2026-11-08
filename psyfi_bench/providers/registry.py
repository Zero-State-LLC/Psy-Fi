"""Provider specs → provider objects.

Spec grammar (CLI ``--provider``):
  oracle | constant[:mode:intensity] | random[:seed] | heuristic
  replay:<receipt.json>
  nvidia[:<nvidia/model-id>]
  anthropic:<model-id>
  openai:<base_url>#<model>            e.g. openai:http://localhost:8080#qwen2.5-vl
"""

from __future__ import annotations

import os
from typing import Any

from psyfi_bench.providers.baselines import ConstantProvider, HeuristicProvider, OracleProvider, RandomProvider
from psyfi_bench.providers.http import AnthropicProvider, OpenAICompatProvider, ProviderError, nvidia_provider
from psyfi_bench.providers.replay import ReplayProvider

BASELINES = ("oracle", "constant", "random", "heuristic")


def make_provider(spec: str | None, options: dict[str, Any] | None = None) -> Any:
    options = dict(options or {})
    spec = (spec or "heuristic").strip()
    kind, _, rest = spec.partition(":")
    kind = kind.lower()
    if kind == "oracle":
        return OracleProvider()
    if kind == "constant":
        mode, _, intensity = rest.partition(":") if rest else ("open", "", "0.5")
        return ConstantProvider(mode or "open", float(intensity or 0.5))
    if kind == "random":
        return RandomProvider(int(rest or options.get("seed", 0) or 0))
    if kind == "heuristic":
        return HeuristicProvider()
    if kind == "replay":
        if not rest:
            raise ProviderError("replay needs a receipt path: replay:<file.json>")
        return ReplayProvider(rest)
    if kind == "nvidia":
        return nvidia_provider(rest or None, transport=options.get("transport"))
    if kind == "anthropic":
        model = rest or os.environ.get("ANTHROPIC_MODEL", "")
        return AnthropicProvider(model, transport=options.get("transport"), timeout_s=float(options.get("timeout_s", 60.0)))
    if kind == "openai":
        base, _, model = rest.partition("#")
        if not base or not model:
            raise ProviderError("openai spec is openai:<base_url>#<model>")
        return OpenAICompatProvider(base, model, api_key_env=options.get("api_key_env", "OPENAI_API_KEY"), extra_body=options.get("extra_body"), transport=options.get("transport"), timeout_s=float(options.get("timeout_s", 60.0)))
    raise ProviderError(f"unknown provider spec {spec!r}")


def describe_available() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"spec": b, "locality": "baseline", "available": True} for b in BASELINES]
    out.append({"spec": "replay:<receipt.json>", "locality": "replay", "available": True})
    out.append({"spec": "nvidia", "locality": "remote", "available": bool(os.environ.get("NVIDIA_API_KEY")) and str(os.environ.get("NVIDIA_VISION_MODEL", "")).startswith("nvidia/"), "env": ["NVIDIA_API_KEY", "NVIDIA_VISION_MODEL", "NVIDIA_API_BASE"]})
    out.append({"spec": "anthropic:<model>", "locality": "remote", "available": bool(os.environ.get("ANTHROPIC_API_KEY")), "env": ["ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"]})
    out.append({"spec": "openai:<base_url>#<model>", "locality": "local|remote", "available": True, "env": ["OPENAI_API_KEY (remote only)"], "note": "vLLM, llama.cpp server, Ollama, LM Studio, any OpenAI-compatible endpoint"})
    return out
