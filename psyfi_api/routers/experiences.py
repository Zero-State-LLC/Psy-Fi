"""Experience catalog and visualization parameter timeline APIs."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from psyfi_api.image_reading import VisionConfigError, VisionProviderError, read_image
from psyfi_api.simulation_service import PresetNotFoundError, run_simulation
from psyfi_core.experiences.catalog import get_default_catalog, load_catalog
from psyfi_core.experiences.parameter_mapper import (
    MODE_BIASES,
    SUBSTANCE_VISUAL_DEFAULTS,
    build_parameter_timeline,
    map_parameters,
)
from psyfi_core.visualization.export_journey import build_export_journey
from psyfi_core.visualization.image_seed import build_image_seed
from psyfi_core.visualization.journey import build_journey
from psyfi_core.visualization.planner import build_planner
from psyfi_core.visualization.scene_snapshot import build_scene_snapshot
from psyfi_core.visualization.spatiotemporal import normalize_anchors

router = APIRouter(prefix="/api/v1", tags=["experiences"])

ModeName = Literal["open", "attractor", "void", "power"]


class SpatiotemporalAnchors(BaseModel):
    """Optional I3 grounding plate — additive, never required or authoritative."""

    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    year: int | None = Field(default=None, ge=1, le=9999)
    hour: float | None = Field(default=None, ge=0.0, le=24.0)
    iso_timestamp: str | None = None
    day_of_year: int | None = Field(default=None, ge=1, le=366)
    solar_elevation_deg: float | None = Field(default=None, ge=-90.0, le=90.0)


class Modulators(BaseModel):
    """Optional progressive enhancers routed only through ParameterField."""

    camera: float = Field(default=0.0, ge=0.0, le=1.0)
    motion: float = Field(default=0.0, ge=0.0, le=1.0)
    midi: float = Field(default=0.0, ge=0.0, le=1.0)
    audio: float = Field(default=0.0, ge=0.0, le=1.0)
    haptics: float = Field(default=0.0, ge=0.0, le=1.0)
    image: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Pass-2 strength for experience-conditioned image seed hints.",
    )
    solar: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Optional solar day factor (0=night, 1=day) from spatiotemporal anchors. "
            "When set, applies a soft lighting plate via ParameterField only."
        ),
    )


class ImageSeedJsonRequest(BaseModel):
    """JSON alternate for Pass-1 image seed (base64). Prefer multipart for large files."""

    image_base64: str
    substance: str = "lsd"
    experience_id: str | None = None
    mode: ModeName = "open"
    intensity: float = Field(default=0.7, ge=0.0, le=1.0)
    influence: float = Field(default=0.65, ge=0.0, le=1.0)
    include_preview: bool = True
    include_source_field: bool = True
    apply_recommended: bool = False
    recommend_only: bool = Field(
        default=False,
        description="Analyze + recommend catalog formula without conditioning pixels.",
    )
    recommend_top_n: int = Field(
        default=5,
        ge=1,
        le=12,
        description="How many ranked formula alternatives to include.",
    )
    spatiotemporal_anchors: SpatiotemporalAnchors | None = None


class TimelineRequest(BaseModel):
    substance: str = "lsd"
    experience_id: str | None = None
    mode: ModeName = "open"
    intensity: float = Field(default=0.7, ge=0.0, le=1.0)
    seed: int = Field(default=42, ge=0)
    steps: int = Field(default=24, ge=2, le=128)
    reduce_motion: bool = False
    dim_flashing: bool = False
    quality_tier: str = "balanced"
    phase_t: float | None = Field(default=None, ge=0.0, le=1.0)
    neutral_view: bool = False
    modulators: Modulators | None = None
    image_hints: dict[str, float] | None = None
    spatiotemporal_anchors: SpatiotemporalAnchors | None = None


class FieldFrameRequest(BaseModel):
    """Bridge: run a bounded Python simulation and return visualizable channels."""

    width: int = Field(default=32, ge=8, le=128)
    height: int = Field(default=32, ge=8, le=128)
    steps: int = Field(default=4, ge=1, le=64)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    preset: str | None = None
    substance: str | None = None
    mode: ModeName = "open"
    intensity: float = Field(default=0.7, ge=0.0, le=1.0)


class SceneSnapshotRequest(BaseModel):
    """Immutable GPU scene snapshot — analysis publish surface for the WebGPU client."""

    substance: str = "lsd"
    experience_id: str | None = None
    mode: ModeName = "open"
    intensity: float = Field(default=0.7, ge=0.0, le=1.0)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    steps: int = Field(default=12, ge=2, le=128)
    quality_tier: str = "balanced"
    reduce_motion: bool = False
    dim_flashing: bool = False
    neutral_view: bool = False
    sequence: int = Field(default=1, ge=1)
    include_simulation: bool = True
    include_fixture_assets: bool = False
    asset_pack_id: str | None = None
    image_hints: dict[str, float] | None = None
    image_seed_png_base64: str | None = Field(
        default=None,
        description="Ephemeral conditioned PNG (base64) attached as assets.images data-URL.",
    )
    width: int = Field(default=32, ge=8, le=128)
    height: int = Field(default=32, ge=8, le=128)
    sim_steps: int = Field(default=4, ge=1, le=64)
    modulators: Modulators | None = None


class ExportJourneyRequest(BaseModel):
    """Package stills + formula prompt for optional external text-to-video."""

    timeline: dict[str, Any]
    stills: list[dict[str, Any]] | None = None
    image_seed: dict[str, Any] | None = None
    experience_id: str | None = None
    t2v_provider: str = "external"
    spatiotemporal_anchors: SpatiotemporalAnchors | None = None
    planner_notes: str | None = Field(
        default=None,
        description="Optional operator notes folded into the deterministic planner (I4).",
    )
    include_planner: bool = True


class PlannerRequest(BaseModel):
    """Deterministic planner from ParameterField + optional anchors (I4)."""

    parameter_field: dict[str, Any] | None = None
    timeline: dict[str, Any] | None = None
    experience_id: str | None = None
    substance: str | None = None
    mode: ModeName | None = None
    intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    seed: int | None = Field(default=None, ge=0)
    spatiotemporal_anchors: SpatiotemporalAnchors | None = None
    notes: str | None = None


class JourneyRequest(BaseModel):
    """Build a portable psyfi.journey.v1 object (I5) — client archives locally."""

    substance: str = "lsd"
    mode: ModeName = "open"
    intensity: float = Field(default=0.7, ge=0.0, le=1.0)
    seed: int = Field(default=42, ge=0)
    experience_id: str | None = None
    timeline: dict[str, Any] | None = None
    parameter_field: dict[str, Any] | None = None
    spatiotemporal_anchors: SpatiotemporalAnchors | None = None
    notes: str | None = None
    comparison_id: str | None = None
    title: str | None = None
    planner_notes: str | None = None


class ImageSeedJourneyJsonRequest(ImageSeedJsonRequest):
    """One-shot: Pass-1 image seed + parameter timeline + export-journey prompt package."""

    steps: int = Field(default=12, ge=2, le=64)
    quality_tier: str = "balanced"
    reduce_motion: bool = False
    dim_flashing: bool = False
    planner_notes: str | None = None


def _anchors_dict(raw: SpatiotemporalAnchors | dict[str, Any] | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, SpatiotemporalAnchors):
        return raw.model_dump(exclude_none=True)
    if isinstance(raw, dict):
        return raw
    return None


def _parse_optional_float(value: str | float | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_optional_int(value: str | int | None) -> int | None:
    n = _parse_optional_float(value)  # type: ignore[arg-type]
    if n is None:
        return None
    return int(round(n))


def _form_anchors(
    *,
    latitude: str | float | None,
    longitude: str | float | None,
    year: str | int | None,
    hour: str | float | None,
    iso_timestamp: str | None,
    solar_elevation_deg: str | float | None,
) -> dict[str, Any] | None:
    return normalize_anchors(
        {
            "latitude": _parse_optional_float(latitude),
            "longitude": _parse_optional_float(longitude),
            "year": _parse_optional_int(year),
            "hour": _parse_optional_float(hour),
            "iso_timestamp": iso_timestamp or None,
            "solar_elevation_deg": _parse_optional_float(solar_elevation_deg),
        }
    )


def _capped_intensity(
    *,
    substance: str,
    intensity: float,
    experience: dict[str, Any] | None,
) -> float:
    """Apply the strictest catalog/experience safety intensity cap.

    Caps must be combined with ``min`` — never ``or``. A recipe that sets
    ``intensity_cap: 1.0`` must not mask a lower substance overlay cap.
    """
    catalog = get_default_catalog()
    overlay = catalog.overlay(substance) or {}
    caps: list[float] = []
    exp_cap = (experience or {}).get("safety", {}).get("intensity_cap")
    if exp_cap is not None:
        caps.append(float(exp_cap))
    overlay_cap = overlay.get("safety", {}).get("intensity_cap")
    if overlay_cap is not None:
        caps.append(float(overlay_cap))
    cap = min(caps) if caps else 1.0
    return min(float(intensity), cap)


def _normalize_substance(value: str) -> str:
    return value.lower().replace("_", "-")


def _assert_experience_substance(
    experience: dict[str, Any] | None,
    substance: str,
) -> None:
    """Reject experience_id / substance pairs that would mix safety envelopes."""
    if not experience:
        return
    exp_sub = experience.get("substance")
    if not exp_sub:
        return
    if _normalize_substance(str(exp_sub)) != _normalize_substance(substance):
        raise HTTPException(
            status_code=400,
            detail=(
                f"experience_id substance '{exp_sub}' does not match "
                f"request substance '{substance}'"
            ),
        )


@router.get("/experiences")
async def list_experiences(
    substance: str | None = None,
    valence: str | None = Query(default="positive"),
    mode: str | None = None,
) -> dict[str, Any]:
    catalog = get_default_catalog()
    recipes = catalog.list(substance=substance, valence=valence, mode=mode)
    # lightweight list payload
    items = [
        {
            "id": r.get("id"),
            "title": r.get("title") or r.get("id"),
            "substance": r.get("substance"),
            "valence": r.get("valence"),
            "mode_default": (r.get("visual_recipe") or {}).get("mode_default", "open"),
            "primary_engines": (r.get("visual_recipe") or {}).get("primary_engines", []),
            "motifs": r.get("motifs", {}),
            "authority": r.get("authority", {}),
        }
        for r in recipes
    ]
    return {
        "schema_version": catalog.schema_version,
        "count": len(items),
        "items": items,
    }


@router.get("/experiences/{experience_id}")
async def get_experience(experience_id: str) -> dict[str, Any]:
    catalog = get_default_catalog()
    recipe = catalog.get(experience_id)
    if not recipe:
        raise HTTPException(status_code=404, detail=f"Experience not found: {experience_id}")
    return {"schema_version": catalog.schema_version, "recipe": recipe}


@router.get("/substances")
async def list_substances() -> dict[str, Any]:
    catalog = get_default_catalog()
    substances = sorted(set(catalog.substances()) | set(SUBSTANCE_VISUAL_DEFAULTS.keys()))
    items = []
    for substance_id in substances:
        overlay = catalog.overlay(substance_id) or {}
        signature = {
            **SUBSTANCE_VISUAL_DEFAULTS.get(substance_id, {}),
            **(overlay.get("visual_signature") or {}),
        }
        items.append(
            {
                "id": substance_id,
                "visual_signature": signature,
                "overlay": overlay or None,
                "recommended_mode": overlay.get("recommended_mode") or "open",
                "recipe_count": len(catalog.list(substance=substance_id, valence=None)),
                "authority": overlay.get("authority")
                or {
                    "motifs": "INFERRED",
                    "parameters": "INFERRED",
                    "source_existence": "OBSERVED",
                },
            }
        )
    return {
        "schema_version": "1.0.0",
        "substances": items,
        "modes": list(MODE_BIASES.keys()),
    }


@router.post("/visualize/parameter-timeline")
async def parameter_timeline(body: TimelineRequest) -> dict[str, Any]:
    catalog = get_default_catalog()
    experience = None
    if body.experience_id:
        experience = catalog.get(body.experience_id)
        if not experience:
            raise HTTPException(status_code=404, detail=f"Experience not found: {body.experience_id}")
        if not body.substance or body.substance == "lsd":
            # prefer recipe substance when client left default-ish
            substance = experience.get("substance") or body.substance
        else:
            substance = body.substance
    else:
        substance = body.substance
    substance = _normalize_substance(substance)
    _assert_experience_substance(experience, substance)

    intensity = _capped_intensity(
        substance=substance,
        intensity=body.intensity,
        experience=experience,
    )
    modulators = body.modulators.model_dump(exclude_none=True) if body.modulators else None
    image_hints = body.image_hints

    if body.phase_t is not None:
        snap = map_parameters(
            substance=substance,
            mode=body.mode,
            intensity=intensity,
            seed=body.seed,
            experience=experience,
            modulators=modulators,
            image_hints=image_hints,
            phase_t=body.phase_t,
            neutral_view=body.neutral_view,
            reduce_motion=body.reduce_motion,
            dim_flashing=body.dim_flashing,
            quality_tier=body.quality_tier,
        )
        return {
            "schema_version": "1.0.0",
            "kind": "snapshot",
            "frame": snap.to_dict(),
        }

    timeline = build_parameter_timeline(
        steps=body.steps,
        substance=substance,
        mode=body.mode,
        intensity=intensity,
        seed=body.seed,
        experience=experience,
        modulators=modulators,
        image_hints=image_hints,
        reduce_motion=body.reduce_motion,
        dim_flashing=body.dim_flashing,
        quality_tier=body.quality_tier,
        neutral_view=body.neutral_view,
    )
    timeline["kind"] = "timeline"
    return timeline


@router.post("/visualize/field-frame")
async def field_frame(body: FieldFrameRequest) -> dict[str, Any]:
    """Run a bounded simulation and pair it with a ParameterField snapshot."""
    substance = (body.substance or body.preset or "lsd").lower().replace("_", "-")
    intensity = _capped_intensity(substance=substance, intensity=body.intensity, experience=None)
    try:
        sim = run_simulation(
            width=body.width,
            height=body.height,
            steps=body.steps,
            seed=body.seed,
            preset=body.preset or (substance if substance != "baseline" else None),
        )
    except PresetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    snap = map_parameters(
        substance=substance,
        mode=body.mode,
        intensity=intensity,
        seed=body.seed,
        phase_t=0.5,
    )
    return {
        "schema_version": "1.0.0",
        "kind": "field_frame",
        "seed": body.seed,
        "substance": substance,
        "simulation": {
            "width": sim.get("width"),
            "height": sim.get("height"),
            "metrics": {
                "valence": sim.get("valence"),
                "coherence": sim.get("coherence"),
                "symmetry": sim.get("symmetry"),
                "roughness": sim.get("roughness"),
                "richness": sim.get("richness"),
            },
            "visualization": sim.get("visualization"),
            "provenance_id": sim.get("provenance_id"),
            "api_version": sim.get("api_version"),
        },
        "parameter_field": snap.to_dict(),
        "note": (
            "Simulation field is authoritative for metrics; "
            "ParameterField is authoritative for Live Experience rendering."
        ),
    }


def _run_image_seed(
    *,
    image: bytes | str,
    substance: str,
    experience_id: str | None,
    mode: str,
    intensity: float,
    influence: float,
    include_preview: bool,
    include_source_field: bool,
    apply_recommended: bool,
    recommend_only: bool = False,
    recommend_top_n: int = 5,
    spatiotemporal_anchors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = get_default_catalog()
    # apply_recommended / recommend_only ignore client experience_id so Pass-1
    # conditioner and applied_* fields share the same catalog pick.
    prefer_rec = bool(apply_recommended) or bool(recommend_only)
    client_experience_id = None if prefer_rec else experience_id
    experience = catalog.get(client_experience_id) if client_experience_id else None
    if client_experience_id and experience is None:
        raise HTTPException(status_code=404, detail=f"Experience not found: {client_experience_id}")
    substance_n = _normalize_substance(substance or (experience or {}).get("substance") or "lsd")
    _assert_experience_substance(experience, substance_n)
    # Cap against overlay first; may re-cap after recommended experience is chosen.
    intensity_c = _capped_intensity(
        substance=substance_n,
        intensity=intensity,
        experience=experience,
    )
    overlay = catalog.overlay(substance_n)
    candidates = catalog.list(substance=substance_n, valence=None) or catalog.list(valence=None)
    try:
        result = build_image_seed(
            image=image,
            experience=experience,
            substance_overlay=overlay,
            substance=substance_n,
            mode=mode,
            intensity=intensity_c,
            influence=influence,
            include_preview=include_preview and not recommend_only,
            include_source_field=include_source_field and not recommend_only,
            recipe_candidates=candidates,
            prefer_recommended_experience=prefer_rec or experience is None,
            recommend_only=bool(recommend_only),
            recommend_top_n=recommend_top_n,
            spatiotemporal_anchors=spatiotemporal_anchors,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"image decode failed: {exc}") from exc

    applied_exp_id = result.get("experience_id")
    applied_exp = catalog.get(applied_exp_id) if applied_exp_id else experience
    if (apply_recommended or recommend_only) and result.get("recommended"):
        result["applied_mode"] = result["recommended"].get("mode")
        # Re-apply strictest intensity cap for the recommended recipe.
        rec_i = float(result["recommended"].get("intensity") or intensity_c)
        result["applied_intensity"] = _capped_intensity(
            substance=substance_n,
            intensity=rec_i,
            experience=applied_exp,
        )
        result["applied_experience_id"] = result["recommended"].get("experience_id") or applied_exp_id
    else:
        result["applied_mode"] = mode
        result["applied_intensity"] = _capped_intensity(
            substance=substance_n,
            intensity=intensity_c,
            experience=applied_exp,
        )
        result["applied_experience_id"] = experience_id or applied_exp_id
    result["kind"] = "image_seed_recommend" if recommend_only else "image_seed"
    return result


@router.post("/visualize/image-reading")
async def image_reading(file: UploadFile = File(...)) -> dict[str, Any]:
    """Inferred caption of the upload. Does not condition the field or write presets."""
    data = await file.read()
    try:
        return read_image(data)
    except VisionConfigError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "vision_unconfigured", "detail": exc.detail},
        ) from exc
    except VisionProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "vision_provider", "detail": exc.detail},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/visualize/image-seed")
async def image_seed_multipart(
    file: UploadFile = File(...),
    substance: str = Form(default="lsd"),
    experience_id: str | None = Form(default=None),
    mode: ModeName = Form(default="open"),
    intensity: float = Form(default=0.7),
    influence: float = Form(default=0.65),
    include_preview: bool = Form(default=True),
    include_source_field: bool = Form(default=True),
    apply_recommended: bool = Form(default=False),
    recommend_only: bool = Form(default=False),
    recommend_top_n: int = Form(default=5),
    latitude: str | None = Form(default=None),
    longitude: str | None = Form(default=None),
    year: str | None = Form(default=None),
    hour: str | None = Form(default=None),
    iso_timestamp: str | None = Form(default=None),
    solar_elevation_deg: str | None = Form(default=None),
) -> dict[str, Any]:
    """Pass 1: experience-condition an uploaded image → master_seed + live hints."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty upload")
    top_n = max(1, min(int(recommend_top_n), 12))
    return _run_image_seed(
        image=data,
        substance=substance,
        experience_id=experience_id or None,
        mode=mode,
        intensity=intensity,
        influence=influence,
        include_preview=include_preview,
        include_source_field=include_source_field,
        apply_recommended=apply_recommended,
        recommend_only=recommend_only,
        recommend_top_n=top_n,
        spatiotemporal_anchors=_form_anchors(
            latitude=latitude,
            longitude=longitude,
            year=year,
            hour=hour,
            iso_timestamp=iso_timestamp,
            solar_elevation_deg=solar_elevation_deg,
        ),
    )


@router.post("/visualize/image-seed/json")
async def image_seed_json(body: ImageSeedJsonRequest) -> dict[str, Any]:
    """Pass 1 JSON alternate (base64 image)."""
    return _run_image_seed(
        image=body.image_base64,
        substance=body.substance,
        experience_id=body.experience_id,
        mode=body.mode,
        intensity=body.intensity,
        influence=body.influence,
        include_preview=body.include_preview,
        include_source_field=body.include_source_field,
        apply_recommended=body.apply_recommended,
        recommend_only=body.recommend_only,
        recommend_top_n=body.recommend_top_n,
        spatiotemporal_anchors=_anchors_dict(body.spatiotemporal_anchors),
    )


@router.post("/visualize/image-seed-journey")
async def image_seed_journey_json(body: ImageSeedJourneyJsonRequest) -> dict[str, Any]:
    """One-shot: condition image → timeline → export-journey prompt package (no stills)."""
    if body.recommend_only:
        raise HTTPException(
            status_code=400,
            detail="image-seed-journey requires conditioning; set recommend_only=false",
        )
    anchors = _anchors_dict(body.spatiotemporal_anchors)
    seed_result = _run_image_seed(
        image=body.image_base64,
        substance=body.substance,
        experience_id=body.experience_id,
        mode=body.mode,
        intensity=body.intensity,
        influence=body.influence,
        include_preview=body.include_preview,
        include_source_field=body.include_source_field,
        apply_recommended=body.apply_recommended,
        recommend_only=False,
        recommend_top_n=body.recommend_top_n,
        spatiotemporal_anchors=anchors,
    )
    catalog = get_default_catalog()
    exp_id = seed_result.get("applied_experience_id") or seed_result.get("experience_id")
    experience = catalog.get(exp_id) if exp_id else None
    substance_n = _normalize_substance(seed_result.get("substance") or body.substance)
    mode_n = seed_result.get("applied_mode") or body.mode
    intensity_n = float(seed_result.get("applied_intensity") or body.intensity)
    modulators = {"image": float(seed_result.get("influence") or 0.0)}
    timeline = build_parameter_timeline(
        steps=body.steps,
        substance=substance_n,
        mode=mode_n,
        intensity=intensity_n,
        seed=int(seed_result["master_seed"]),
        experience=experience,
        modulators=modulators,
        image_hints=seed_result.get("parameter_hints"),
        reduce_motion=body.reduce_motion,
        dim_flashing=body.dim_flashing,
        quality_tier=body.quality_tier,
        neutral_view=False,
    )
    timeline["kind"] = "timeline"
    journey = build_export_journey(
        timeline=timeline,
        stills=None,
        image_seed=seed_result,
        experience=experience,
        t2v_provider="external",
        spatiotemporal_anchors=anchors or seed_result.get("spatiotemporal_anchors"),
        planner_notes=body.planner_notes,
    )
    journey["kind"] = "export_journey"
    return {
        "schema": "psyfi.image_seed_journey.v1",
        "kind": "image_seed_journey",
        "image_seed": seed_result,
        "timeline": timeline,
        "journey": journey,
        "note": (
            "One-shot Pass-1 seed + Pass-2 timeline + T2V prompt package. "
            "Capture viewport stills client-side if needed. Not medical advice."
        ),
    }


@router.post("/visualize/scene-snapshot")
async def scene_snapshot(body: SceneSnapshotRequest) -> dict[str, Any]:
    """Publish an immutable GPU scene snapshot (analysis → renderer contract)."""
    substance = _normalize_substance(body.substance)
    catalog = get_default_catalog()
    experience = catalog.get(body.experience_id) if body.experience_id else None
    if body.experience_id and experience is None:
        raise HTTPException(status_code=404, detail=f"Experience not found: {body.experience_id}")
    _assert_experience_substance(experience, substance)
    modulators = body.modulators.model_dump(exclude_none=True) if body.modulators else None
    image_hints = body.image_hints
    intensity = _capped_intensity(
        substance=substance,
        intensity=body.intensity,
        experience=experience,
    )
    timeline = build_parameter_timeline(
        substance=substance,
        mode=body.mode,
        intensity=intensity,
        seed=body.seed,
        steps=body.steps,
        experience=experience,
        modulators=modulators,
        image_hints=image_hints,
        reduce_motion=body.reduce_motion,
        dim_flashing=body.dim_flashing,
        quality_tier=body.quality_tier,
        neutral_view=body.neutral_view,
    )
    frames = timeline.get("frames") or []
    # Rematerialize through map_parameters when Neutral is requested. A flag-only
    # overwrite left expressive engines/params in place and bypassed calm policy.
    if body.neutral_view:
        phase_t = 0.5
        if frames:
            phase_t = float(frames[len(frames) // 2].get("phase_t", 0.5))
        parameter_field = map_parameters(
            substance=substance,
            mode=body.mode,
            intensity=intensity,
            seed=body.seed,
            phase_t=phase_t,
            experience=experience,
            modulators=modulators,
            image_hints=image_hints,
            reduce_motion=body.reduce_motion,
            dim_flashing=body.dim_flashing,
            quality_tier=body.quality_tier,
            neutral_view=True,
        ).to_dict()
    elif frames:
        parameter_field = dict(frames[len(frames) // 2])
    else:
        parameter_field = map_parameters(
            substance=substance,
            mode=body.mode,
            intensity=intensity,
            seed=body.seed,
            phase_t=0.5,
            experience=experience,
            modulators=modulators,
            image_hints=image_hints,
            reduce_motion=body.reduce_motion,
            dim_flashing=body.dim_flashing,
            quality_tier=body.quality_tier,
            neutral_view=False,
        ).to_dict()

    simulation = None
    if body.include_simulation:
        try:
            sim = run_simulation(
                width=body.width,
                height=body.height,
                steps=body.sim_steps,
                seed=body.seed,
                preset=substance if substance != "baseline" else None,
            )
        except PresetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        simulation = {
            "width": sim.get("width"),
            "height": sim.get("height"),
            "metrics": {
                "valence": sim.get("valence"),
                "coherence": sim.get("coherence"),
                "symmetry": sim.get("symmetry"),
                "roughness": sim.get("roughness"),
                "richness": sim.get("richness"),
            },
            "visualization": sim.get("visualization"),
            "provenance_id": sim.get("provenance_id"),
            "api_version": sim.get("api_version"),
        }

    snap = build_scene_snapshot(
        parameter_field=parameter_field,
        simulation=simulation,
        quality_tier=body.quality_tier,
        sequence=body.sequence,
        include_fixture_assets=body.include_fixture_assets,
        asset_pack_id=body.asset_pack_id,
        image_seed_png_base64=body.image_seed_png_base64,
    )
    snap["kind"] = "scene_snapshot"
    snap["substance"] = substance
    snap["experience_id"] = body.experience_id
    snap["timeline_hash"] = timeline.get("timeline_hash")
    return snap


@router.post("/visualize/export-journey")
async def export_journey(body: ExportJourneyRequest) -> dict[str, Any]:
    """Build an export-journey package (stills + T2V prompt sidecar). No provider call."""
    catalog = get_default_catalog()
    experience = catalog.get(body.experience_id) if body.experience_id else None
    if body.experience_id and experience is None:
        # Fall back to timeline experience_id when present.
        tid = (body.timeline or {}).get("experience_id")
        experience = catalog.get(tid) if tid else None
    package = build_export_journey(
        timeline=body.timeline,
        stills=body.stills,
        image_seed=body.image_seed,
        experience=experience,
        t2v_provider=body.t2v_provider or "external",
        spatiotemporal_anchors=_anchors_dict(body.spatiotemporal_anchors),
        planner_notes=body.planner_notes,
        include_planner=body.include_planner,
    )
    package["kind"] = "export_journey"
    return package


@router.post("/visualize/planner")
async def visualize_planner(body: PlannerRequest) -> dict[str, Any]:
    """Deterministic I4 planner from ParameterField / timeline + optional anchors."""
    catalog = get_default_catalog()
    experience = catalog.get(body.experience_id) if body.experience_id else None
    if body.experience_id and experience is None:
        raise HTTPException(status_code=404, detail=f"Experience not found: {body.experience_id}")

    field = body.parameter_field
    if field is None and body.substance and body.mode is not None:
        substance = _normalize_substance(body.substance)
        _assert_experience_substance(experience, substance)
        intensity = _capped_intensity(
            substance=substance,
            intensity=float(body.intensity if body.intensity is not None else 0.7),
            experience=experience,
        )
        snap = map_parameters(
            substance=substance,
            mode=body.mode,
            intensity=intensity,
            seed=int(body.seed if body.seed is not None else 42),
            experience=experience,
        )
        field = snap.to_dict()

    if field is None and not body.timeline:
        raise HTTPException(
            status_code=400,
            detail="planner requires parameter_field, timeline, or substance+mode",
        )

    plan = build_planner(
        parameter_field=field,
        spatiotemporal_anchors=_anchors_dict(body.spatiotemporal_anchors),
        notes=body.notes,
        experience=experience,
        timeline=body.timeline,
    )
    plan["kind"] = "planner"
    return plan


@router.post("/visualize/journey")
async def visualize_journey(body: JourneyRequest) -> dict[str, Any]:
    """Build a portable Journey object (I5) for client-side IndexedDB archive."""
    catalog = get_default_catalog()
    experience = catalog.get(body.experience_id) if body.experience_id else None
    if body.experience_id and experience is None:
        raise HTTPException(status_code=404, detail=f"Experience not found: {body.experience_id}")
    substance = _normalize_substance(body.substance or (experience or {}).get("substance") or "lsd")
    _assert_experience_substance(experience, substance)
    intensity = _capped_intensity(
        substance=substance,
        intensity=body.intensity,
        experience=experience,
    )
    planner = build_planner(
        parameter_field=body.parameter_field,
        spatiotemporal_anchors=_anchors_dict(body.spatiotemporal_anchors),
        notes=body.planner_notes or body.notes,
        experience=experience,
        timeline=body.timeline,
    )
    packet = build_journey(
        substance=substance,
        mode=body.mode,
        intensity=intensity,
        seed=body.seed,
        experience_id=body.experience_id or (experience or {}).get("id"),
        timeline=body.timeline,
        parameter_field=body.parameter_field,
        spatiotemporal_anchors=_anchors_dict(body.spatiotemporal_anchors),
        planner=planner,
        comparison_id=body.comparison_id,
        notes=body.notes,
        experience=experience,
        title=body.title,
    )
    packet["kind"] = "journey"
    return packet


@router.post("/experiences/reload-catalog")
async def reload_catalog() -> dict[str, Any]:
    """Reload catalog from disk (dev helper)."""
    from psyfi_core.experiences import catalog as catalog_mod

    catalog_mod.get_default_catalog.cache_clear()
    c = catalog_mod.get_default_catalog()
    return {
        "status": "reloaded",
        "recipe_count": len(c.recipes),
        "path": str(c.path) if c.path else None,
    }
