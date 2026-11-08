# Context — Psy-Fi public host

For: Aaron
Date: 2026-11-07
Updated: 2026-11-08, after the share card deploy (#43) and its container rollout
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
| Current version | `3d97825f-cea6-41b5-b50c-4e83659aa723` |
| That version | Deploy of `main` at `bb7ee9a` (share card, #43) with `--containers-rollout immediate --keep-vars`, 2026-11-08T07:31:52.273Z, 100%. `/index.html` was the only static asset uploaded. New container image, built from that tree. |
| Previous versions | `363b5d70-0fca-425a-9a3b-9de45abcbe09`, redeploy of `main` at `c2c534a`, 2026-11-08T03:04:09.557Z. `7f79f732-3b1a-42a7-90a0-239ac1c5483d`, upload of `main` at `7372d31` (shell redesign, #44), 2026-11-08T02:50:04.993Z. `d27e5f06-fc86-432f-9f6b-b1b6815e46f9`, secret change, 2026-11-07T23:50:49.525Z. |
| First upload | `aac88ff4-79a1-4c00-b31e-19b87074b26a` (not the current version) |
| Custom domain | `psy-fi.space` only. Certificate comes from that binding. |
| `workers.dev` | Off. https://psy-fi.zer0state-noema.workers.dev/health returned 404. |
| Preview URLs | Off |
| `www` | Not attached |
| Container | Class `PsyfiApi`, binding `PSYFI_API`, port 8000, `standard-1`, outbound internet, sleeps after 10 minutes idle, one instance |
| Source path | `workers/psyfi/`. The directory name is not the script name. |
| Product line | `1.4.0`. Shell cache `psyfi-shell-v43`; the shell loads `/static/style.css?v=43`. |
| Annotated tag | `v1.4.0` stays on `84334ad`. There is no GitHub Release. |
| Freeze | `psyfi-api-v1-hard-2026-07-25`, `api_version` `v1`, FastAPI `version` `0.1.0`, session `engine_version` default `0.1.0`. Unchanged. |

`NVIDIA_API_KEY` is a secret on Worker `psy-fi`. It is already set. Do not print it, and do not put it again unless you are rotating it.

`NVIDIA_VISION_MODEL` is a plain-text var on that Worker. It is set. Do not commit the id. `NVIDIA_API_BASE` is empty, so image reading calls `https://integrate.api.nvidia.com` directly. This host does not add an AI Gateway.

Deploy checks for `3d97825f`, with a browser user agent (a bare Python client gets Cloudflare 1010):

- `GET /health` — 200, `psyfi-api` `1.4.0`, at 2026-11-08T07:40:10Z.
- `GET /ready` — 200, `gpu_shell_mounted` true, at 2026-11-08T07:40:10Z.
- `GET /` — 200, shell contains "Read image", `v1.4.0` and the front page headline; `GET /static/style.css?v=43` — 200.
- `GET /` head carries the share card: 10 `og:` tags and 5 `twitter:` tags, title "PsyFi, a consciousness field simulator". `GET /static/images/psyfi-hero.jpg` — 200, JPEG.
- `GET /gpu/` — 200, HTML.
- `GET /sw.js` — `CACHE_NAME = 'psyfi-shell-v43'`.
- Version `3d97825f` still binds `NVIDIA_API_KEY` (secret) and `NVIDIA_VISION_MODEL` (plain text). Names were checked; values were not printed.
- No image-reading POST was made on this deploy. That call spends the key.

The same checks, less the share card, answered the same way for `363b5d70` at 2026-11-08T03:05:32Z, for `7f79f732` at 2026-11-08T02:55Z, and for `d27e5f06` on 2026-11-07 with cache `psyfi-shell-v42`.

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

Update, 2026-11-08: `origin/main` is `bb7ee9a` (#43 to #46 merged by admin merges at the operator's request). That tree names the script `psy-fi`. Version `7f79f732` was deployed from `7372d31` with `npx wrangler@4 deploy --keep-vars` (Wrangler 4.152.0); version `363b5d70` redeployed `c2c534a` with `--containers-rollout immediate --keep-vars`; version `3d97825f` deployed `bb7ee9a` the same way (Wrangler 4.158.0). `7f79f732` and `363b5d70` carry container base image `psy-fi-psyfiapi-base` `sha256:89ace427…`; `3d97825f` carries `sha256:68fc9db8…`, because the image copies `psyfi_api/` and the shell template changed. All of them are built from `main`, so the vision-bench modules in the running image are the ones on `main`. The live instance (`npx wrangler containers instances 224374f7189b4e3281bac784426c2f18`) was created 2026-11-08T07:32:16.916Z, 24 seconds after the `3d97825f` deploy, so it runs that image. Container application `psy-fi-psyfiapi` still reports last modified 2026-11-07T23:50:32Z: that field did not move on any of these deploys, so it is not a rollout signal.

The paragraphs below describe the 2026-11-07 handoff.

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
- The macOS case-collision on `.github/PULL_REQUEST_TEMPLATE.md`. Do not commit it.
