# Engineering Receipt — Visual Experiences from Scraped Phenomenology

**Date:** 2026-07-25  
**Scope:** Phase 2 visualization runtime (web-first) + distilled substance visual overlays + P0–P2 hardening  
**Status:** Engines split; WebGL path; phase scrubber; modulators/export/bridge; overlay goldens; README hero

## Delivered

### Data
- `data/phenomenology/positive/` — 20 curated positive/source JSON files
- `data/phenomenology/derived/experience_catalog.v1.json` — **33 recipes**
  - lsd 12, psilocybin 8, dmt 8, 5-meo-dmt 1, mescaline 1, ketamine 1, pcp 2
- `data/phenomenology/derived/substance_visual_overlays.v1.json` — **rich per-substance visual settings**
  - motif means, oscillation style, visual_signature scalars
  - engine_weights, parameter_bias, palette, phase_profile, safety clamps
  - authority labels (`OBSERVED` / `INFERRED`)

### Distillation path
```text
positive JSON reports
  → motif scores + seed recipes
  → experience_catalog.v1.json
  → aggregate per substance
  → substance_visual_overlays.v1.json
  → parameter_mapper (overlay → signature → engines → ParameterField)
  → Live Experience Canvas player
```

Rebuild:
```bash
python3 scripts/build_experience_catalog.py
```

### Core
- `psyfi_core/experiences/catalog.py` — catalog + overlay load
- `psyfi_core/experiences/parameter_mapper.py` — overlays wired into immutable field
- `scripts/build_experience_catalog.py` — richer `build_overlays()`
- `docs/schemas/psyfi_experience_recipe.v1.json`
- `docs/schemas/psyfi_parameter_field.v1.json`

### API
- `GET /api/v1/experiences`, `GET /api/v1/experiences/{id}`
- `GET /api/v1/substances` — returns distilled `visual_signature` + full `overlay`
- `POST /api/v1/visualize/parameter-timeline`
- Legacy `/simulate/` unchanged; jobs/presets remain under `/api/v1`

### Frontend
- `psyfi_api/static/viz/experiencePlayer.js` — multi-engine Canvas field + safety pass
- Live Experience panel alongside simulation workspace
- Service worker precache includes experience player (see `psyfi_api/static/sw.js` `CACHE_NAME`, currently **v44**)

### Tests
```text
pytest tests/ -q
# includes tests/test_experiences.py (overlay + distinct substance engines)
```

### Docs
- `docs/VISUAL_EXPERIENCES.md`
- `docs/PHENOMENOLOGY_PIPELINE.md`
- `docs/CURSOR_PROMPT_VISUAL_EXPERIENCES_FROM_SCRAPED_DATA.md`

## Distilled visual lean (examples)

| Substance | Style | Dominant engines | Mode |
|-----------|-------|------------------|------|
| LSD | geometric | recursive_feedback, kaleidoscope | attractor |
| Psilocybin | organic | organic_bloom, recursive_feedback, flow_field | open |
| DMT | fractal | recursive_feedback, entity_lattice | power |
| 5-MeO-DMT | minimal | void_expansion, organic_bloom | void |
| Mescaline | geometric | kaleidoscope, recursive_feedback | attractor |
| Ketamine | smooth | flow_field, void_expansion | void |

## Non-claims

- Not medical, diagnostic, or therapeutic
- Not asserting intention-altered quantum processes
- Parameters/motifs labeled INFERRED; source presence OBSERVED
- UI does not republish full third-party report text

## Known limitations

- Legacy Live Experience: Canvas + Prefer-WebGL ParameterField with I2 compare + safety transitions
- Modular engines also live under `static/viz/engines/`; player orchestrates present
- 5-MeO / mescaline / ketamine overlays are seed-heavy (few scraped samples)
- PCP recipes intensity-capped; treated experimental
- Native iOS is a separate deferred track

## Next

1. Living device / hardware Ultra fps capture as needed (`HARDWARE_ULTRA_FPS.md`)
2. Optional getUserMedia camera texture input (ParameterField modulators only)
3. More positive source packs for 5-MeO / mescaline / ketamine
4. iOS Metal adapters against the same schemas after web validation (deferred track)
