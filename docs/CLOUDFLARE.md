# Cloudflare production host

Production is one Worker hostname: `https://psy-fi.space`. The Worker script name is `psy-fi`. `workers.dev` and preview URLs are off. The only custom domain is `psy-fi.space`. `www` is not a hostname.

The shell and the GPU lab are static assets. The Python API stays in the existing image and is reached only through that Worker. Docker Compose is the local seam, documented in [`../DEPLOYMENT.md`](../DEPLOYMENT.md).

The older Worker script `psyfi` (`https://psyfi.zer0state-noema.workers.dev`) is a different deploy target. It stays. `npx wrangler deploy` from this `wrangler.jsonc` updates `psy-fi` only. It does not update `psyfi` and it does not detach `psy-fi.space`. A checkout whose `wrangler.jsonc` still names `psyfi` updates that older script and leaves the domain where it is.

Worker source stays in `workers/psyfi/`. That directory name is not the script name.

This repo does not deploy from CI. An operator with the Cloudflare account runs the steps below. No model id is pinned in git, and the vision key is not in the tree.

## Routing

`workers/psyfi/src/route.mjs` chooses the target.

| Path | Target |
| --- | --- |
| `/api`, `/api/…` | Container |
| `/simulate`, `/simulate/…` | Container |
| `/health`, `/ready`, `/docs`, `/redoc`, `/openapi.json` | Container |
| `/`, `/static/…`, `/gpu/…`, `/sw.js`, `/assets/icons/…` | Static assets |
| `/privacy`, `/robots.txt`, `/sitemap.xml`, `/favicon.ico` | Static assets |
| Any other path | Static assets: `404.html` with status 404 (`not_found_handling`) |

The Container class is `PsyfiApi`. It listens on port 8000, uses instance type `standard-1`, allows outbound internet so the process can reach the NVIDIA API, and sleeps after 10 minutes idle. The image is the repo `Dockerfile`.

## Assets

The shell, `privacy.html` and `404.html` templates have no template variables. Stage them with the static files, the root files (`sw.js`, `robots.txt`, `sitemap.xml`, `favicon.ico`), icons, and the built GPU lab. `/gpu/` is a static asset, so the container image cannot stand in for a missing build. Staging stops when `packages/psyfi-gpu-renderer/dist/index.html` is absent.

```bash
npm run gpu:build
python3 scripts/stage_cloudflare_assets.py
```

That writes `public/`, which is gitignored. `wrangler.jsonc` serves `public/` with the `ASSETS` binding and runs the Worker first.

## Vision key and model

Set these on the Worker. Wrangler copies only non-empty values into the container when the container starts.

| Name | Where it lives |
| --- | --- |
| `NVIDIA_API_KEY` | Worker secret. Not a var in `wrangler.jsonc`. |
| `NVIDIA_VISION_MODEL` | Worker var. An `nvidia/` vision id from the account catalog at deploy time. |
| `NVIDIA_API_BASE` | Optional Worker var. Leave it empty on this host. An empty value calls `https://integrate.api.nvidia.com` directly. This host does not add an AI Gateway. |

The chat path is `/v1/chat/completions` with a bearer token. The id must start with `nvidia/`. An empty id, a non-`nvidia/` id, and a Workers AI `@cf/` id fail closed and open no socket. Local and CI leave the model unset.

The browser never sees the key. Do not put a key in Compose, the client bundle, or this file.

## Image Reading

`POST /api/v1/visualize/image-reading` accepts a multipart `file`. The API rejects a body over 12 MB before decode, resizes the longest edge to 384, and sends one text part plus one `data:image/png` of that resized source. The request sets `reasoning_effort` to `none`, so the token cap is spent on the caption. The response is `psyfi.image_reading.v1`: authority `INFERRED`, the caption, the model id, and a not-medical-advice sentence. The caption is not a master seed, a hint, a recipe score, planner text, or a preset write.

The provider call runs in a worker thread. The one API process can still answer other requests while NVIDIA responds. A provider error is returned once, as HTTP 502 `vision_provider`. A socket timeout, including a stall after the response headers, is that same error and is not retried. A missing key or a rejected model id is HTTP 503 `vision_unconfigured`.

The shell button is **Read image**. It writes the caption with `textContent` and truncates it.

## Deploy

From a checkout whose `wrangler.jsonc` names `psy-fi`, with Wrangler 4.136 or newer and a Docker engine for the local container build:

```bash
npm run gpu:build
python3 scripts/stage_cloudflare_assets.py
npx wrangler secret put NVIDIA_API_KEY
npx wrangler deploy --keep-vars
```

The secret is already on Worker `psy-fi`. Run `secret put` only when rotating it. Do not pass the key on the command line.

`NVIDIA_VISION_MODEL` is a deploy-time var. It is not in git. The first deploy of a new script has to pass it explicitly (`--var NVIDIA_VISION_MODEL:<nvidia/ vision id>`). `--keep-vars` does not copy vars from Worker `psyfi`. On a later deploy of this same script, `--keep-vars` keeps the var already set. Without `--keep-vars`, Wrangler deletes vars the command does not pass. Leave the var unset and the reading route stays closed.

Leave `NVIDIA_API_BASE` unset on this host. An empty base calls `https://integrate.api.nvidia.com` directly. This host does not add an AI Gateway.

The foreign Noema workflow is not in this repo. This host document does not deploy another product.
