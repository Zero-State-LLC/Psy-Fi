"""Classify a WebGPU adapter description (port of GpuAdapter.ts heuristics) for provenance only."""

from __future__ import annotations

import re
from typing import Any


def classify_vendor(raw: str) -> str:
    s = raw.lower()
    if "nvidia" in s or "geforce" in s or "quadro" in s or re.search(r"\brtx\b", s):
        return "nvidia"
    if "amd" in s or "radeon" in s or "ati " in s:
        return "amd"
    if "intel" in s or "arc" in s:
        return "intel"
    if "apple" in s or "metal" in s or re.search(r"\bm[1-5]\b", s):
        return "apple"
    return "unknown"


def perf_band(vendor: str, description: str) -> str:
    s = description.lower()
    nvidia_hi = bool(re.search(r"\brtx\s*(30|40|50)\d{2}\b", s)) or bool(
        re.search(r"\b(3060|3070|3080|3090|4060|4070|4080|4090|5060|5070|5080|5090)(\s*ti)?\b", s) and re.search(r"geforce|nvidia", s)
    )
    amd_hi = bool(re.search(r"\brx\s*(6|7|9)\d{3}\b", s))
    intel_arc = bool(re.search(r"\barc\s*(a|b)\d{3}\b", s)) or ("arc" in s and bool(re.search(r"\b(a750|a770|b570|b580|a580|a380)\b", s)))
    apple_hi = "apple" in s and bool(re.search(r"\bm[1-5]\b", s)) and bool(re.search(r"\b(pro|max|ultra)\b", s))
    if nvidia_hi or amd_hi or intel_arc or apple_hi:
        return "ultra"
    if vendor in ("nvidia", "amd") or re.search(r"\brtx\s*20\d{2}\b|\bgtx\s*16\d{2}\b|\brx\s*5\d{3}\b", s):
        return "high"
    if vendor == "intel" and re.search(r"uhd|iris|graphics", s) and "arc" not in s:
        return "integrated"
    if vendor == "apple":
        return "high"
    return "unknown"


def classify_adapter(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    description = str(raw.get("description") or raw.get("device") or raw.get("vendor") or "")
    vendor = classify_vendor(f"{raw.get('vendor') or ''} {description} {raw.get('architecture') or ''}")
    band = perf_band(vendor, description or str(raw.get("architecture") or ""))
    if vendor in ("nvidia", "amd") or band == "ultra" and vendor != "apple":
        hardware_class = "discrete"
    elif vendor == "apple" or band == "integrated":
        hardware_class = "integrated"
    else:
        hardware_class = "unknown"
    return {
        "vendor": vendor,
        "description": description,
        "architecture": str(raw.get("architecture") or ""),
        "perf_band": band,
        "hardware_class": hardware_class,
    }
