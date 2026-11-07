---
title: Product version stays apart from the frozen API document
author: Daniel
date: 2026-11-07
branch: spec/cloudflare-nvidia-image-reading
id: l-c04e20db
scope: repo
status: active
src: agent
touches:
  - ".github/PULL_REQUEST_TEMPLATE.md"
  - README.md
  - psyfi_api/__init__.py
  - psyfi_api/main.py
  - psyfi_api/templates/index.html
  - psyfi_core/__init__.py
  - pyproject.toml
  - tests/test_api_routes.py
---

## Decided
- The product version is the single line in psyfi_core/VERSION. /health, /ready, /api/info, and the shell badge report it. pyproject.toml reads that file so the wheel version matches.
- FastAPI's version argument stays 0.1.0. That value is info.version in the hard-frozen OpenAPI document.
- The session engine_version default stays 0.1.0. It is the frozen schema default for an omitted field.
- api_version stays v1. Freeze id stays psyfi-api-v1-hard-2026-07-25.
- Retroactive tags v0.1.0 through v1.3.1 name ship points already on main. Those trees still contain the string 0.1.0. v1.4.0 is tagged only after its commit is on main.
- packages/psyfi-gpu-renderer stays at 0.1.0 until that package is versioned on its own.

## Tried and ruled out
- Bumping FastAPI's version argument with the product version. The live OpenAPI document version would disagree with the hard-frozen snapshot.
- setuptools dynamic attr pointing at psyfi_core.version.__version__. Importing the package pulls numpy, which a build-isolation environment does not have. A VERSION text file avoids that import.
- One tag per commit across the 205-commit history. The tags follow the ship points: first engine, presets, MIDI, the December close, the soft freeze, the hard freeze, G4, image seed, the instrument, and current main.

## Watch out
- Pull request numbers in commit subjects from 2025 and July 2026 belong to the archived scrimshawlife-ctrl repository. They are not the current Zero-State-LLC issue numbers.
- A squash merge of the 1.4.0 branch would leave a tag on the pre-squash commit off main. Tag v1.4.0 after the commit is on main.
