# Image Seed Pipeline (two-pass)

Status: **active** — Pass 1 + Pass 2 + recommend-before-condition + GPU handoff + export-journey sidecar  
Related: [`VISUAL_EXPERIENCES.md`](VISUAL_EXPERIENCES.md), [`rendering/ASSET_STANDARDS.md`](rendering/ASSET_STANDARDS.md), [`CONTINUATION_PLAN.md`](CONTINUATION_PLAN.md)

## Goal

User provides an image. Experience recipe data **first** conditions that image (Pass 1). Live render then modulates the resulting seed through ParameterField + SafetyPass (Pass 2).

```
User image (ephemeral)
    → Pass 1: experience conditioner (recipe params reshape pixels + features)
    → derived master_seed + image_hints + conditioned luminance plane
    → Pass 2: map_parameters + live modulators (incl. modulators.image)
    → Canvas/WebGL / optional /gpu/ scene-snapshot (SafetyPass mandatory)
```

## Authority

| Layer | Authority |
| --- | --- |
| ParameterField | Visual source of truth (unchanged) |
| Experience recipe | Pass-1 seed modulator (not a second field) |
| Conditioned image / luminance plane | Optional source-plane blend + ephemeral `assets.images` |
| SafetyPass / Neutral / intensity caps | Non-bypassable |

Raw uploads are never stored. Conditioned PNG may travel as an ephemeral data-URL on the snapshot for GPU tint only (not authority).

## Pass 1 — Experience conditioner

Module: `psyfi_core/visualization/image_seed.py`

1. Decode PNG/JPEG → RGBA, downscale (max edge 384). An empty upload is a client error. A body over 12 MB, or a raster over 25 million pixels, is rejected before the float32 working image is built. Multipart and JSON use that same ceiling. Raw bytes stay in memory and are not written to disk.
2. Measure features (mean RGB, contrast, edge density, warm/cool, energy).
3. Recommend mode/intensity and best-matching catalog `experience_id` from features.
4. Apply recipe/overlay biases as pixel ops (saturation, void crush, symmetry fold, mild turbulence) scaled by `influence`.
5. Derive `master_seed` from SHA-256 of conditioned bytes.
6. Emit capped `parameter_hints` for live mapping.
7. Emit luminance `source_field` for Live Experience source-plane blend.
8. Optional small PNG preview (base64) for UI — discard after response.
9. Optional conditioned texture PNG (≤256 edge) for GPU `assets.images` data-URL.

## Pass 2 — Live render

- Client writes `seedInput` from Pass 1.
- `modulators.image` ∈ [0,1] = influence strength into `map_parameters`.
- Conditioned luminance → `setSourcePlane` (same path as sim source plane).
- Timeline / field-frame / scene-snapshot proceed as today.

## GPU Lab handoff

- Shell mirrors Pass-1 payload into `sessionStorage` key `psyfi.imageSeed.v1`.
- `/gpu/?image_seed=1` reads handoff → scene-snapshot with `image_hints`, `modulators.image`, and `image_seed_png_base64`.
- `SceneAssetLayer` prefers `assets.images` PNG/data-URL, then KTX2 fixtures.

## Export journey (T2V sidecar)

`POST /api/v1/visualize/export-journey` packages timeline + safety-presented stills + `t2v.prompt`.  
No LLM/video provider is invoked in-app — paste externally.

Optional **I3 spatiotemporal anchors** (`latitude`, `longitude`, `year`, `hour`, `solar_elevation_deg`, …) may be sent on image-seed and export-journey. Solar elevation auto-derives when omitted. Anchors bias Pass-1 lighting slightly and appear in the T2V prompt clause — never authoritative over ParameterField.

Optional **I4 planner** (`planner_notes`, `include_planner`) folds a deterministic `psyfi.planner.v1` packet into export-journey / image-seed-journey T2V sidecars. Live Experience may also apply anchors as a soft `modulators.solar` lighting plate when the opt-in checkbox is on. Seed lock blocks Pass-1 overwrites of the master seed.

## API (additive)

`POST /api/v1/visualize/image-seed`

- Multipart: `file` + form fields (`substance`, `experience_id`, `mode`, `intensity`, `influence`, `apply_recommended`, `recommend_only`, `recommend_top_n`, optional `latitude` / `longitude` / `year` / `hour` / `solar_elevation_deg`, …)
- Or JSON: `{ "image_base64": "...", "spatiotemporal_anchors": { ... }, ... }`
- When `apply_recommended` / `recommend_only` is true, client `experience_id` is ignored; catalog pick drives `applied_*`.
- `recommend_only=true` analyzes features and returns the recommended formula **without** pixel conditioning (Workbench suggest panel).
- `recommend_top_n` (1–12, default 5) fills `recommended_alternatives[]` (rank · id · title · mode_default · score).
- Response schema: `psyfi.image_seed.v1` (recommended may include `experience_id` / `experience_title` / `experience_score`)

`POST /api/v1/visualize/image-reading` → inferred caption beside the seed (`psyfi.image_reading.v1`, authority `INFERRED`). The shell shows it as text. It does not change `master_seed`, hints, recipe score, planner text, the journey sidecar, or the preset registry. An unset model returns 503 and opens no socket. See [`CLOUDFLARE.md`](CLOUDFLARE.md).

`POST /api/v1/visualize/image-seed-journey` → one-shot seed + timeline + `psyfi.export_journey.v1` prompt package (no stills; rejects `recommend_only`; accepts `planner_notes`)

`POST /api/v1/visualize/export-journey` → `psyfi.export_journey.v1` (optional `planner` / `spatiotemporal_anchors`)

`POST /api/v1/visualize/planner` → `psyfi.planner.v1`

`POST /api/v1/visualize/journey` → `psyfi.journey.v1` (client IndexedDB archive; no server storage)

## Non-claims

Modeled phenomenology for research/visualization only. Not medical advice.
