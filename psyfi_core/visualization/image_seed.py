"""Two-pass image seed: experience conditioner (Pass 1) → live ParameterField (Pass 2).

Pass 1 reshapes user pixels with experience recipe parameters.
Pass 2 consumes derived master_seed + modulators.image + optional luminance plane.
Raw uploads are processed in-memory only — never persisted.
"""

from __future__ import annotations

import base64
import hashlib
import io
from typing import Any

import numpy as np

from psyfi_core.visualization.spatiotemporal import (
    apply_anchor_drive_bias,
    apply_anchor_hint_bias,
    normalize_anchors,
)

IMAGE_SEED_SCHEMA = "psyfi.image_seed.v1"
_MAX_EDGE = 384
_MAX_BYTES = 12_000_000
# Above this, the decoded RGBA raster is huge next to the 384-edge working image.
_MAX_PIXELS = 25_000_000
_PREVIEW_EDGE = 128
_TEXTURE_EDGE = 256
_SOURCE_EDGE = 64

# Hint deltas stay subtle — SafetyPass / intensity caps still apply in map_parameters.
_HINT_KEYS = (
    "palette_energy",
    "edge_gain",
    "turbulence",
    "pattern_complexity",
    "void_bias",
    "attractor_bias",
    "depth_distortion",
    "bloom",
)


def _clamp01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def decode_image_bytes(data: bytes) -> np.ndarray:
    """Decode PNG/JPEG/WebP bytes → float32 RGBA HxWx4 in [0,1]."""
    from PIL import Image

    if not data:
        raise ValueError("empty image")
    if len(data) > _MAX_BYTES:
        raise ValueError("image too large (max ~12MB)")
    try:
        img = Image.open(io.BytesIO(data))
    except Image.DecompressionBombError as exc:
        raise ValueError("image dimensions too large") from exc
    width, height = img.size
    if width < 1 or height < 1 or width * height > _MAX_PIXELS:
        raise ValueError("image dimensions too large")
    img = img.convert("RGBA")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr


def decode_image_base64(b64: str) -> np.ndarray:
    raw = b64.strip()
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("invalid image_base64") from exc
    return decode_image_bytes(data)


def _resize_max_edge(rgba: np.ndarray, max_edge: int) -> np.ndarray:
    from PIL import Image

    h, w = rgba.shape[:2]
    edge = max(h, w)
    if edge <= max_edge:
        return rgba
    scale = max_edge / float(edge)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    u8 = (np.clip(rgba, 0, 1) * 255.0).astype(np.uint8)
    img = Image.fromarray(u8, mode="RGBA")
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    return np.asarray(img, dtype=np.float32) / 255.0


def analyze_features(rgba: np.ndarray) -> dict[str, Any]:
    rgb = rgba[..., :3]
    gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    mean_rgb = [float(np.mean(rgb[..., c])) for c in range(3)]
    contrast = float(np.std(gray))
    # Cheap edge proxy
    gy, gx = np.gradient(gray)
    edge_density = float(np.mean(np.sqrt(gx * gx + gy * gy)))
    energy = _clamp01(float(np.mean(np.abs(rgb - np.mean(rgb)))) * 3.0)
    warmth = _clamp01(0.5 + (mean_rgb[0] - mean_rgb[2]) * 1.25)
    return {
        "mean_rgb": [round(v, 4) for v in mean_rgb],
        "energy": round(energy, 4),
        "contrast": round(_clamp01(contrast * 2.2), 4),
        "edge_density": round(_clamp01(edge_density * 4.0), 4),
        "warmth": round(warmth, 4),
        "width": int(rgba.shape[1]),
        "height": int(rgba.shape[0]),
    }


def _recipe_drive(experience: dict[str, Any] | None, overlay: dict[str, Any] | None) -> dict[str, float]:
    """Collapse recipe + overlay into conditioner drive knobs ∈ [0,1]."""
    recipe = (experience or {}).get("visual_recipe") or {}
    bias = dict((overlay or {}).get("parameter_bias") or {})
    bias.update(recipe.get("parameter_bias") or {})
    engines = {}
    for i, name in enumerate(recipe.get("primary_engines") or []):
        engines[str(name)] = max(engines.get(str(name), 0.0), 0.85 - i * 0.1)
    for i, name in enumerate(recipe.get("secondary_engines") or []):
        engines[str(name)] = max(engines.get(str(name), 0.0), 0.45 - i * 0.08)
    if overlay and overlay.get("engine_weights"):
        for k, v in (overlay.get("engine_weights") or {}).items():
            engines[str(k)] = max(engines.get(str(k), 0.0), _clamp01(float(v)))

    pal = recipe.get("palette") or (overlay or {}).get("palette") or {}
    return {
        "palette_energy": _clamp01(float(bias.get("palette_energy", pal.get("energy", 0.55)))),
        "void_bias": _clamp01(float(bias.get("void_bias", 0.0))),
        "attractor_bias": _clamp01(float(bias.get("attractor_bias", 0.0))),
        "turbulence": _clamp01(float(bias.get("turbulence", 0.25))),
        "pattern_complexity": _clamp01(float(bias.get("pattern_complexity", 0.4))),
        "edge_gain": _clamp01(float(bias.get("edge_gain", 0.4))),
        "bloom": _clamp01(float(bias.get("bloom", 0.25))),
        "kaleidoscope": _clamp01(float(engines.get("kaleidoscope", 0.0))),
        "void_expansion": _clamp01(float(engines.get("void_expansion", 0.0))),
        "organic_bloom": _clamp01(float(engines.get("organic_bloom", 0.0))),
        "recursive_feedback": _clamp01(float(engines.get("recursive_feedback", 0.0))),
    }


def condition_image(
    rgba: np.ndarray,
    *,
    drive: dict[str, float],
    influence: float,
    seed: int,
) -> np.ndarray:
    """Pass 1: reshape pixels using experience drive. influence blends vs original."""
    influence = _clamp01(influence)
    if influence <= 1e-6:
        return rgba.copy()

    out = rgba.copy()
    rgb = out[..., :3]
    gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]

    # Saturation / energy
    sat = 0.55 + 0.9 * drive["palette_energy"]
    mean = np.mean(rgb, axis=2, keepdims=True)
    rgb = mean + (rgb - mean) * (1.0 + (sat - 1.0) * influence)

    # Contrast from edge_gain / pattern_complexity
    contrast = 1.0 + influence * (0.35 * drive["edge_gain"] + 0.25 * drive["pattern_complexity"])
    mid = 0.5
    rgb = mid + (rgb - mid) * contrast

    # Void crush
    void_amt = influence * max(drive["void_bias"], drive["void_expansion"] * 0.7)
    if void_amt > 0:
        rgb = rgb * (1.0 - 0.55 * void_amt) + rgb * rgb * (0.35 * void_amt)

    # Attractor / bloom soft vignette lift
    h, w = rgb.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx / max(1, w - 1)) * 2.0 - 1.0
    ny = (yy / max(1, h - 1)) * 2.0 - 1.0
    r = np.sqrt(nx * nx + ny * ny)
    attr = influence * drive["attractor_bias"]
    if attr > 0:
        lift = np.clip(1.0 - r * (0.55 * attr), 0.35, 1.15)
        rgb = rgb * lift[..., None]
    bloom = influence * drive["bloom"] * 0.25
    if bloom > 0:
        rgb = rgb + bloom * (1.0 - np.clip(r, 0, 1))[..., None] * 0.35

    # Mild deterministic turbulence (not flash strobing)
    turb = influence * drive["turbulence"] * 0.08
    if turb > 0:
        rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
        noise = rng.standard_normal(rgb.shape).astype(np.float32)
        rgb = rgb + noise * turb

    # Kaleidoscope quadrant fold
    kal = influence * drive["kaleidoscope"]
    if kal > 0.15:
        folded = rgb.copy()
        hh, ww = h // 2, w // 2
        if hh > 2 and ww > 2:
            tile = folded[:hh, :ww]
            folded[:hh, :ww] = tile
            folded[:hh, ww : ww * 2] = tile[:, ::-1]
            folded[hh : hh * 2, :ww] = tile[::-1, :]
            folded[hh : hh * 2, ww : ww * 2] = tile[::-1, ::-1]
            rgb = rgb * (1.0 - kal) + folded * kal

    # Organic soft blur-lite via neighbor mix
    org = influence * drive["organic_bloom"] * 0.35
    if org > 0 and h > 2 and w > 2:
        blur = (
            np.roll(rgb, 1, 0) + np.roll(rgb, -1, 0) + np.roll(rgb, 1, 1) + np.roll(rgb, -1, 1)
        ) * 0.25
        rgb = rgb * (1.0 - org) + blur * org

    # Recursive feedback: blend toward slightly zoomed center crop feel
    rec = influence * drive["recursive_feedback"] * 0.4
    if rec > 0 and h > 8 and w > 8:
        y0, y1 = h // 8, h - h // 8
        x0, x1 = w // 8, w - w // 8
        from PIL import Image

        u8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
        crop = Image.fromarray(u8[y0:y1, x0:x1], mode="RGB").resize((w, h), Image.Resampling.BILINEAR)
        zoomed = np.asarray(crop, dtype=np.float32) / 255.0
        rgb = rgb * (1.0 - rec) + zoomed * rec

    out[..., :3] = np.clip(rgb, 0.0, 1.0)
    # Keep alpha; mild safety: never boost flash via alpha tricks
    _ = gray
    return out


def derive_master_seed(rgba: np.ndarray) -> int:
    u8 = (np.clip(rgba, 0, 1) * 255.0).astype(np.uint8).tobytes()
    digest = hashlib.sha256(u8).digest()
    return int.from_bytes(digest[:4], "big")


def parameter_hints_from_features(
    features: dict[str, Any],
    drive: dict[str, float],
    influence: float,
) -> dict[str, float]:
    """Capped ParameterField nudges for Pass 2 (applied via modulators.image path)."""
    influence = _clamp01(influence)
    energy = float(features.get("energy") or 0.0)
    contrast = float(features.get("contrast") or 0.0)
    edges = float(features.get("edge_density") or 0.0)
    warmth = float(features.get("warmth") or 0.5)
    hints = {
        "palette_energy": round(influence * (0.12 * energy + 0.08 * drive["palette_energy"]), 4),
        "edge_gain": round(influence * (0.14 * edges + 0.06 * contrast), 4),
        "turbulence": round(influence * (0.1 * edges + 0.05 * drive["turbulence"]), 4),
        "pattern_complexity": round(influence * (0.1 * contrast + 0.08 * drive["pattern_complexity"]), 4),
        "void_bias": round(influence * 0.12 * drive["void_bias"], 4),
        "attractor_bias": round(influence * 0.1 * drive["attractor_bias"], 4),
        "depth_distortion": round(influence * (0.08 * contrast + 0.04 * abs(warmth - 0.5)), 4),
        "bloom": round(influence * 0.08 * drive["bloom"], 4),
    }
    return {k: float(hints[k]) for k in _HINT_KEYS if k in hints}


def luminance_source_field(rgba: np.ndarray, edge: int = _SOURCE_EDGE) -> dict[str, Any]:
    """Downsampled luminance grid compatible with Live Experience source plane."""
    small = _resize_max_edge(rgba, edge)
    rgb = small[..., :3]
    gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    h, w = gray.shape
    values = [[round(float(gray[y, x]), 4) for x in range(w)] for y in range(h)]
    return {"width": int(w), "height": int(h), "values": values}


def encode_preview_png_base64(rgba: np.ndarray, edge: int = _PREVIEW_EDGE) -> str:
    from PIL import Image

    small = _resize_max_edge(rgba, edge)
    u8 = (np.clip(small, 0, 1) * 255.0).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(u8, mode="RGBA").save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def texture_asset_ref(png_b64: str | None, *, asset_id: str = "image_seed") -> dict[str, str] | None:
    """Ephemeral data-URL asset ref for GPU SceneAssetLayer (PNG, not KTX2)."""
    if not png_b64:
        return None
    return {
        "id": asset_id,
        "url": f"data:image/png;base64,{png_b64}",
        "role": "image_seed",
    }


def attach_image_seed_texture(
    assets: dict[str, list[dict[str, str]]] | None,
    png_b64: str | None,
) -> dict[str, list[dict[str, str]]]:
    """Merge conditioned PNG into snapshot assets.images (additive; procedural stays authority)."""
    base = {
        "gltf": list((assets or {}).get("gltf") or []),
        "ktx2": list((assets or {}).get("ktx2") or []),
        "splats": list((assets or {}).get("splats") or []),
        "images": list((assets or {}).get("images") or []),
    }
    ref = texture_asset_ref(png_b64)
    if not ref:
        return base
    if not any(r.get("id") == ref["id"] for r in base["images"]):
        base["images"].append(ref)
    return base


def recommend_mode_intensity(features: dict[str, Any], mode: str, intensity: float) -> dict[str, Any]:
    """Soft recommendation — client may keep user overrides."""
    edges = float(features.get("edge_density") or 0.0)
    energy = float(features.get("energy") or 0.0)
    contrast = float(features.get("contrast") or 0.0)
    suggested = mode
    if edges > 0.55 and contrast > 0.45:
        suggested = "attractor"
    elif energy < 0.28 and contrast < 0.3:
        suggested = "void"
    elif energy > 0.6:
        suggested = "power"
    # Nudge intensity gently toward image energy; keep caller intensity as base.
    suggested_i = _clamp01(0.55 * intensity + 0.45 * (0.35 + 0.55 * energy))
    return {"mode": suggested, "intensity": round(suggested_i, 4)}


def score_experience_for_features(
    recipe: dict[str, Any],
    features: dict[str, Any],
    suggested_mode: str,
) -> float:
    """Higher is better match between image features and a catalog recipe."""
    vr = recipe.get("visual_recipe") or {}
    bias = vr.get("parameter_bias") or {}
    pal = vr.get("palette") or {}
    mode_default = str(vr.get("mode_default") or "open")
    modes = set(recipe.get("modes") or [])
    score = 0.0
    if mode_default == suggested_mode:
        score += 3.0
    elif suggested_mode in modes:
        score += 1.5
    energy = float(features.get("energy") or 0.0)
    contrast = float(features.get("contrast") or 0.0)
    edges = float(features.get("edge_density") or 0.0)
    warmth = float(features.get("warmth") or 0.5)
    pal_e = float(pal.get("energy", bias.get("palette_energy", 0.5)) or 0.5)
    score += 1.5 * (1.0 - abs(pal_e - energy))
    complexity = float(bias.get("pattern_complexity", 0.4) or 0.4)
    score += 1.2 * (1.0 - abs(complexity - max(contrast, edges)))
    void_b = float(bias.get("void_bias", 0.0) or 0.0)
    if suggested_mode == "void":
        score += 0.8 * void_b + 0.4 * (1.0 - energy)
    attract = float(bias.get("attractor_bias", 0.0) or 0.0)
    if suggested_mode == "attractor":
        score += 0.8 * max(attract, float(bias.get("symmetry_order", 0.0) or 0.0))
    # Warm images prefer higher bloom / organic secondaries
    engines = list(vr.get("primary_engines") or []) + list(vr.get("secondary_engines") or [])
    if warmth > 0.55 and "organic_bloom" in engines:
        score += 0.4
    if edges > 0.5 and "kaleidoscope" in engines:
        score += 0.5
    if energy > 0.55 and "recursive_feedback" in engines:
        score += 0.35
    return round(score, 4)


def rank_experiences(
    candidates: list[dict[str, Any]] | None,
    features: dict[str, Any],
    suggested_mode: str,
    *,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """Rank catalog recipes for image features. Includes ``recipe`` for Pass-1 use."""
    if not candidates:
        return []
    n = max(1, min(int(top_n), 12))
    ranked: list[tuple[float, dict[str, Any]]] = []
    for recipe in candidates:
        if not isinstance(recipe, dict) or not recipe.get("id"):
            continue
        ranked.append((score_experience_for_features(recipe, features, suggested_mode), recipe))
    if not ranked:
        return []
    ranked.sort(key=lambda pair: (-pair[0], str(pair[1].get("id"))))
    out: list[dict[str, Any]] = []
    for i, (score, recipe) in enumerate(ranked[:n]):
        out.append(
            {
                "rank": i + 1,
                "experience_id": recipe.get("id"),
                "title": recipe.get("title") or recipe.get("name"),
                "mode_default": (
                    (recipe.get("visual_recipe") or {}).get("mode_default") or suggested_mode
                ),
                "score": score,
                "recipe": recipe,
            }
        )
    return out


def recommend_experience(
    candidates: list[dict[str, Any]] | None,
    features: dict[str, Any],
    suggested_mode: str,
    *,
    top_n: int = 1,
) -> dict[str, Any] | None:
    """Pick best catalog recipe for image features. Returns summary or None."""
    ranked = rank_experiences(candidates, features, suggested_mode, top_n=max(1, top_n))
    return ranked[0] if ranked else None


def _public_alternative(entry: dict[str, Any]) -> dict[str, Any]:
    """Strip internal recipe object from a ranked entry for API payloads."""
    return {
        "rank": entry.get("rank"),
        "experience_id": entry.get("experience_id"),
        "title": entry.get("title"),
        "mode_default": entry.get("mode_default"),
        "score": entry.get("score"),
    }


def build_image_seed(
    *,
    image: np.ndarray | bytes | str,
    experience: dict[str, Any] | None = None,
    substance_overlay: dict[str, Any] | None = None,
    substance: str = "lsd",
    mode: str = "open",
    intensity: float = 0.7,
    influence: float = 0.65,
    include_preview: bool = True,
    include_source_field: bool = True,
    include_texture: bool = True,
    recipe_candidates: list[dict[str, Any]] | None = None,
    prefer_recommended_experience: bool = False,
    recommend_only: bool = False,
    recommend_top_n: int = 5,
    spatiotemporal_anchors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run Pass 1 and return psyfi.image_seed.v1 payload.

    When ``recommend_only`` is true, skip pixel conditioning and return features +
    catalog recommendation so the client can confirm formula before Pass 1 mutates.
    Optional ``spatiotemporal_anchors`` (I3) bias conditioner drive / hints and are
    echoed in the provenance packet — never authoritative over ParameterField.
    """
    if isinstance(image, (bytes, bytearray)):
        rgba = decode_image_bytes(bytes(image))
    elif isinstance(image, str):
        rgba = decode_image_base64(image)
    else:
        rgba = np.asarray(image, dtype=np.float32)
        if rgba.ndim != 3 or rgba.shape[2] < 3:
            raise ValueError("image array must be HxWx3/4")
        if rgba.shape[2] == 3:
            a = np.ones((*rgba.shape[:2], 1), dtype=np.float32)
            rgba = np.concatenate([rgba, a], axis=2)
        if float(np.max(rgba)) > 1.5:
            rgba = rgba / 255.0

    rgba = _resize_max_edge(rgba, _MAX_EDGE)
    features = analyze_features(rgba)
    recommended = recommend_mode_intensity(features, mode, intensity)
    suggested_mode = str(recommended.get("mode") or mode)
    ranked = rank_experiences(
        recipe_candidates,
        features,
        suggested_mode,
        top_n=recommend_top_n,
    )
    rec_exp = ranked[0] if ranked else None
    alternatives = [_public_alternative(entry) for entry in ranked]
    # Condition with explicit experience, else recommended (when preferred / missing).
    use_experience = experience
    if prefer_recommended_experience and rec_exp and rec_exp.get("recipe"):
        use_experience = rec_exp["recipe"]
    elif use_experience is None and rec_exp and rec_exp.get("recipe"):
        use_experience = rec_exp["recipe"]

    if rec_exp:
        recommended = {
            **recommended,
            "experience_id": rec_exp.get("experience_id"),
            "experience_title": rec_exp.get("title"),
            "experience_score": rec_exp.get("score"),
        }

    anchors = normalize_anchors(spatiotemporal_anchors)
    # Recipe defaults may optionally declare anchors when the client sends none.
    if anchors is None and isinstance(use_experience, dict):
        anchors = normalize_anchors(use_experience.get("spatiotemporal_anchors"))

    drive = apply_anchor_drive_bias(_recipe_drive(use_experience, substance_overlay), anchors)
    pre_seed = derive_master_seed(rgba)

    if recommend_only:
        # Provisional seed from the original image; Pass 1 conditioner not run.
        hints = apply_anchor_hint_bias(
            parameter_hints_from_features(features, drive, influence),
            anchors,
        )
        return {
            "schema": IMAGE_SEED_SCHEMA,
            "master_seed": int(pre_seed),
            "influence": round(_clamp01(influence), 4),
            "substance": substance,
            "experience_id": (use_experience or {}).get("id") or (experience or {}).get("id"),
            "mode": mode,
            "features": features,
            "parameter_hints": hints,
            "spatiotemporal_anchors": anchors,
            "source_field": None,
            "conditioned_preview_png_base64": None,
            "conditioned_texture_png_base64": None,
            "texture_asset": None,
            "recommended": recommended,
            "recommended_alternatives": alternatives,
            "recommend_only": True,
            "note": (
                "Recommend-only Pass-1 preview (no pixel conditioning). "
                "Confirm formula, then re-call without recommend_only for the conditioned seed. "
                "Modeled phenomenology for research/visualization only — not medical advice. "
                "Image bytes are not stored."
            ),
        }

    conditioned = condition_image(rgba, drive=drive, influence=influence, seed=pre_seed)
    master_seed = derive_master_seed(conditioned)
    hints = apply_anchor_hint_bias(
        parameter_hints_from_features(features, drive, influence),
        anchors,
    )
    tex_b64 = encode_preview_png_base64(conditioned, edge=_TEXTURE_EDGE) if include_texture else None

    return {
        "schema": IMAGE_SEED_SCHEMA,
        "master_seed": int(master_seed),
        "influence": round(_clamp01(influence), 4),
        "substance": substance,
        "experience_id": (use_experience or {}).get("id") or (experience or {}).get("id"),
        "mode": mode,
        "features": features,
        "parameter_hints": hints,
        "spatiotemporal_anchors": anchors,
        "source_field": luminance_source_field(conditioned) if include_source_field else None,
        "conditioned_preview_png_base64": (
            encode_preview_png_base64(conditioned) if include_preview else None
        ),
        "conditioned_texture_png_base64": tex_b64,
        "texture_asset": texture_asset_ref(tex_b64),
        "recommended": recommended,
        "recommended_alternatives": alternatives,
        "recommend_only": False,
        "note": (
            "Pass-1 experience-conditioned image seed. "
            "Use master_seed + modulators.image for Pass-2 live ParameterField present. "
            "Optional conditioned_texture attaches as ephemeral assets.images data-URL. "
            "Modeled phenomenology for research/visualization only — not medical advice. "
            "Image bytes are not stored."
        ),
    }
