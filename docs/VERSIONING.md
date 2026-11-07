# Versioning

PsyFi has four version strings. They answer different questions.

| String | Where it lives | Current value | Question it answers |
| --- | --- | --- | --- |
| Product version | `psyfi_core/VERSION` | 1.4.0 | Which build is this? |
| API contract | `api_version` | `v1` | Which HTTP contract is this? |
| OpenAPI document | FastAPI `version=`, `docs/contracts/openapi.json` `info.version` | `0.1.0` | Which frozen document is this? |
| Session engine default | `engine_version` on the session schema | `0.1.0` | What value fills an omitted session field? |

`/health`, `/ready`, `/api/info`, and the shell badge (`title-version`) report the product version. `psyfi_core` and `psyfi_api` both export that string as `__version__`.

The hard freeze id stays `psyfi-api-v1-hard-2026-07-25`. A breaking API change needs a new freeze id. An additive route does not.

`packages/psyfi-gpu-renderer` is a separate package. Its `package.json` version stays `0.1.0` until that package is released on its own.

## Tags

Annotated tags were added on 2026-11-07. Each tag sits on a commit that is already on `main`. The source tree at those commits still contains the string `0.1.0`. The tag is the product version of that commit. History was not rewritten.

`v1.4.0` is the version in this tree. Tag it when this commit is on `main`. A squash merge would need the tag on the squash commit.

| Tag | Commit | Date | What landed since the previous tag |
| --- | --- | --- | --- |
| `v0.1.0` | `48acc6f` | 2025-11-27 | First engine, brand, and PWA shell |
| `v0.2.0` | `30216da` | 2025-11-27 | Style pack and substance presets |
| `v0.3.0` | `959f8b2` | 2025-12-01 | MIDI control and the first deploy configs |
| `v0.4.0` | `6fd80f0` | 2025-12-21 | Health version sync, pure core engines, MIDI activity checks |
| `v0.5.0` | `d296357` | 2026-07-25 | Web-first `/api/v1` and the soft freeze |
| `v1.0.0` | `76f9895` | 2026-07-25 | Hard freeze, Docker-only deploy, GPU through G3 |
| `v1.1.0` | `a3aeead` | 2026-07-25 | G4 scene snapshots, `/gpu/` route, pixel goldens |
| `v1.2.0` | `2f0895b` | 2026-07-25 | Shell and safety passes, two-pass image seed |
| `v1.3.0` | `077ac90` | 2026-08-04 | Instrument I1–I5 |
| `v1.3.1` | `7ca678e` | 2026-10-23 | Org license, CodeQL, project automation, dependency bumps |
| `v1.4.0` | this branch | 2026-11-07 | Cloudflare host, inferred image reading, this version file |

Dates are the committer dates. Commit subjects from 2025 and 2026 that mention a pull request number refer to the archived `scrimshawlife-ctrl/Psy-Fi` repository. Those numbers are not Zero-State-LLC issues.

`1.x` means the frozen `v1` API is the contract this build serves. Open gaps on the tracker are still open. This repo is not deployed by CI.

## Cutting the next version

1. Set `psyfi_core/VERSION` to the next semver.
2. Set the shell badge in `psyfi_api/templates/index.html` to the same number. `tests/test_product_version.py` fails when they differ.
3. Add a section to `CHANGELOG.md`.
4. Leave these alone: freeze id, `api_version`, FastAPI `version=`, `engine_version` defaults, both OpenAPI snapshots, and the session schema default.
5. After the commit is on `main`, add an annotated tag `vX.Y.Z` on that commit and push the tag.
