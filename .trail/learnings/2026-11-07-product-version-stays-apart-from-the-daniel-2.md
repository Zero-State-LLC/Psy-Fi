---
title: Product version stays apart from the frozen API document
author: Daniel
date: 2026-11-07
branch: spec/cloudflare-nvidia-image-reading
id: l-d01954e5
scope: repo
status: active
replaces: l-c04e20db
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
- Product version is the line in psyfi_core/VERSION. /health, /ready, /api/info, and the shell badge report it.
- FastAPI version= stays 0.1.0. That string is info.version on the hard-frozen OpenAPI document.
- Session engine_version default stays 0.1.0. api_version stays v1. Freeze id stays psyfi-api-v1-hard-2026-07-25.
- Tags v0.1.0 through v1.3.1 name ship points already on main. Those trees still contain 0.1.0. Tag v1.4.0 only after its commit is on main.

## Tried and ruled out
- Raising FastAPI's version with the product version. Live OpenAPI info.version would disagree with the frozen snapshot.
- setuptools attr = psyfi_core.version.__version__. Package init imports numpy, which build isolation does not have. The VERSION file avoids that import.

## Watch out
- Commit subjects from 2025 and July 2026 cite archived scrimshawlife-ctrl pull requests, not current Zero-State-LLC issue numbers.
