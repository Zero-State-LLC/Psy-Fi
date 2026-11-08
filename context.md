# Context — Psy-Fi public host

For: Aaron
Date: 2026-11-07
Repo: [`Zero-State-LLC/Psy-Fi`](https://github.com/Zero-State-LLC/Psy-Fi)
Intent: [`intent.md`](intent.md)
Host doc: [`docs/CLOUDFLARE.md`](docs/CLOUDFLARE.md)
Issue: [#36](https://github.com/Zero-State-LLC/Psy-Fi/issues/36)

This file is the operator map. It is not a second spec. It does not contain the vision key or the model id.

## What is live

Public site: https://psy-fi.space

| Fact | Value |
| --- | --- |
| Worker script | `psy-fi` |
| Account | Zer0state, `315fb44b61212825452aad0ca566ea42` |
| Current version | `d27e5f06-fc86-432f-9f6b-b1b6815e46f9` |
| That version | Secret change, 2026-11-07T23:50:49.525Z, 100% |
| First upload | `aac88ff4-79a1-4c00-b31e-19b87074b26a` (not the current version) |
| Custom domain | `psy-fi.space` only. Certificate comes from that binding. |
| `workers.dev` | Off. https://psy-fi.zer0state-noema.workers.dev/health returned 404. |
| Preview URLs | Off |
| `www` | Not attached |
| Container | Class `PsyfiApi`, binding `PSYFI_API`, port 8000, `standard-1`, outbound internet, sleeps after 10 minutes idle, one instance |
| Source path | `workers/psyfi/`. The directory name is not the script name. |
| Product line | `1.4.0`. Shell cache `psyfi-shell-v42`. |
| Annotated tag | `v1.4.0` stays on `84334ad`. There is no GitHub Release. |
| Freeze | `psyfi-api-v1-hard-2026-07-25`, `api_version` `v1`, FastAPI `version` `0.1.0`, session `engine_version` default `0.1.0`. Unchanged. |

`NVIDIA_API_KEY` is a secret on Worker `psy-fi`. It is already set. Do not print it, and do not put it again unless you are rotating it.

`NVIDIA_VISION_MODEL` is a plain-text var on that Worker. It is set. Do not commit the id. `NVIDIA_API_BASE` is empty, so image reading calls `https://integrate.api.nvidia.com` directly. This host does not add an AI Gateway.

Deploy checks, with a browser user agent (a bare Python client gets Cloudflare 1010):

- `GET /health` — 200, `psyfi-api` `1.4.0`, at 2026-11-07T23:51:32Z.
- `GET /ready` — 200, `gpu_shell_mounted` true, presets loaded, at 2026-11-07T23:57:53Z.
- `GET /` — 200, shell contains "Read image" and `v1.4.0`.
- `GET /gpu/` — 200, HTML.
- `GET /sw.js` — `CACHE_NAME = 'psyfi-shell-v42'`.
- No image-reading POST was made on this deploy. That call spends the key.

## What stays up beside it

Worker `psyfi` at https://psyfi.zer0state-noema.workers.dev still answered `GET /health` 200 at 2026-11-07T23:51:48Z. This deploy did not update it, delete it, or attach the domain to it. Its last known version before this host was `b066c207-952d-498a-bc74-16e273e87954`.

Do not attach `psy-fi.space` to `psyfi`.

A later deploy of `psyfi` must pass `--keep-vars` or the same vision-model var. Without `--keep-vars`, Wrangler deletes vars the command does not pass. `--keep-vars` does not copy vars from one script to the other.

## How to redeploy the public host

Use a checkout whose `wrangler.jsonc` names `psy-fi`. Confirm the Wrangler account is Zer0state before you deploy.

```bash
npm run gpu:build
python3 scripts/stage_cloudflare_assets.py
npx wrangler deploy --containers-rollout immediate --keep-vars
```

`public/` is gitignored. `/gpu/` is a static asset, so a missing GPU build must stop the stage. The container image cannot stand in for it.

The secret is already on `psy-fi`. Run `npx wrangler secret put NVIDIA_API_KEY` only to rotate it, and pass the value on stdin. `secret put` does not take `--keep-vars`. After a secret change, confirm the plain-text vision var is still present. Do not print either value.

The first deploy of a brand-new script has to pass `--var NVIDIA_VISION_MODEL:<nvidia/ vision id>` itself. Copy the id from the live Worker settings. Do not take it from git.

CI does not call Cloudflare and does not depend on DNS. Live `/health` and shell checks are deploy checks.

## Git, as of this handoff

`origin/main` was `80fcfa2380325e30c84f884f70f98a10210f9670`. That tree names the script `psyfi`. A deploy from GitHub `main` updates Worker `psyfi` and does not move `psy-fi.space`.

The operator's local `main` includes the vision-bench commits through `dece192823a4e110df0718dac880196f0033faad`. Those commits are not on `origin/main`. The handoff branch is cut from `origin/main` and does not include them.

The live container was built from that local tree, so the bench modules are in the running image until the next image build. They add no public route. A redeploy from the handoff branch rebuilds the image without those modules. The public shell, GPU lab, and API stay the product that is already on `origin/main`.

Direct push to `main` is rejected: one code-owner review, and admins are enforced. Do not force-push. Do not admin-merge unless a human asks.

## Leave these alone

- Issue #10, hardware Ultra frame times. It stays Backlog. This Mac is a MacBook Air M4 with 10 GPU cores. Do not record it as Ultra evidence. Do not invent frame times.
- Hardware-quality scaling. It was discussed and not written.
- Catalog reload. The route stays as the app already implements it. No ticket.
- The Call section in [`docs/specs/cloudflare-nvidia.md`](docs/specs/cloudflare-nvidia.md). It still says production vision goes through an AI Gateway custom provider. The live host does not. That section was not rewritten.
- A vision-bench receipt fixture. CI recomputes only after a human runs capture. Do not commit a receipt.
- Login, an API-key check, an origin allowlist, a rate limit, and `www.psy-fi.space`.
- The image-reading request: `reasoning_effort` `none`, `max_tokens` 256, and the not-medical-advice sentence. A reading does not write presets, the catalog, the master seed, hints, recipe rank, or planner text.
- Production-readiness headings. Tests assert them.
- Org project #16 (Noema). The Psy-Fi board is org project #7.
- The pull request template is `.github/pull_request_template.md`. GitHub's default name is that lowercase file. `.github/PULL_REQUEST_TEMPLATE/` is a directory for extra templates, not a second default file.
