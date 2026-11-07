# Cloudflare production host

Production is one Worker hostname. The shell and the GPU lab are static assets. The Python API stays in the existing image and is reached only through that Worker. Docker Compose is the local seam, documented in [`../DEPLOYMENT.md`](../DEPLOYMENT.md).

This repo does not deploy from CI. An operator with the Cloudflare account runs the steps below. No model id is pinned in git, and the vision key is not in the tree.

## Routing

`workers/psyfi/src/route.mjs` chooses the target.

| Path | Target |
| --- | --- |
| `/api`, `/api/…` | Container |
| `/simulate`, `/simulate/…` | Container |
| `/health`, `/ready`, `/docs`, `/redoc`, `/openapi.json` | Container |
| `/`, `/static/…`, `/gpu/…`, `/sw.js`, `/assets/icons/…` | Static assets |

The Container class is `PsyfiApi`. It listens on port 8000, uses instance type `standard-1`, allows outbound internet so the process can reach the NVIDIA API, and sleeps after 10 minutes idle. The image is the repo `Dockerfile`.

## Assets

The shell template has no template variables. Stage it with the static files, the service worker, icons, and the GPU `dist/` when that build exists:

```bash
python3 scripts/stage_cloudflare_assets.py
```

That writes `public/`, which is gitignored. `wrangler.jsonc` serves `public/` with the `ASSETS` binding and runs the Worker first.

## Vision key and model

Set these on the Worker. Wrangler copies only non-empty values into the container when the container starts.

| Name | Where it lives |
| --- | --- |
| `NVIDIA_API_KEY` | Worker secret. Not a var in `wrangler.jsonc`. |
| `NVIDIA_VISION_MODEL` | Worker var. An `nvidia/` vision id from the account catalog at deploy time. |
| `NVIDIA_API_BASE` | Optional Worker var. Set this to the AI Gateway URL for that custom provider. When it is empty, the API uses `https://integrate.api.nvidia.com`. |

The chat path is `/v1/chat/completions` with a bearer token. The id must start with `nvidia/`. An empty id, a non-`nvidia/` id, and a Workers AI `@cf/` id fail closed and open no socket. Local and CI leave the model unset.

The browser never sees the key. Do not put a key in Compose, the client bundle, or this file.

## Image Reading

`POST /api/v1/visualize/image-reading` accepts a multipart `file`. The API rejects a body over 12 MB before decode, resizes the longest edge to 384, and sends one text part plus one `data:image/png` of that resized source. The response is `psyfi.image_reading.v1`: authority `INFERRED`, the caption, the model id, and a not-medical-advice sentence. The caption is not a master seed, a hint, a recipe score, planner text, or a preset write.

A provider error is returned once, as HTTP 502 `vision_provider`. A missing key or a rejected model id is HTTP 503 `vision_unconfigured`.

The shell button is **Read image**. It writes the caption with `textContent` and truncates it.

## Deploy

From a checkout that includes `wrangler.jsonc`, with Wrangler 4.136 or newer and a Docker engine for the local container build:

```bash
python3 scripts/stage_cloudflare_assets.py
npx wrangler secret put NVIDIA_API_KEY
npx wrangler deploy
```

Set `NVIDIA_VISION_MODEL` in the Worker configuration before the deploy you want to serve traffic. Leave it unset and the reading route stays closed.

Do not delete the foreign Noema workflow in this step. That cleanup is issue #16.
