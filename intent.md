# Intent — public host psy-fi.space

Author: Daniel Meyer
Date: 2026-11-07
Status: accepted
Product: PsyFi (`Zero-State-LLC/Psy-Fi`)

This file is the accepted proto-spec for the public hostname. The operator ordered the deploy, and the host is live. The decision record for the gap is [issue #36](https://github.com/Zero-State-LLC/Psy-Fi/issues/36). The operator map is [`context.md`](context.md).

Further change streams still start as `intent/<change-stream>.md`. See [`intent/README.md`](intent/README.md). This file is at the repo root because the handoff asked for `intent.md`.

## Problem

Psy-Fi was reachable on a shared `workers.dev` hostname. The name bought for this product is `psy-fi.space`, and that name had to belong to a Worker that serves only Psy-Fi.

[verified: issue #36, and the zone was already active on the Zer0state account]

## Outcome

A stranger can check these without the chat:

- https://psy-fi.space/health returns HTTP 200 for `psyfi-api` `1.4.0`.
- https://psy-fi.space/ready returns HTTP 200 with the GPU shell mounted.
- https://psy-fi.space/ serves the shell, including "Read image" and `v1.4.0`, and `/sw.js` names the shell cache (`psyfi-shell-v43` since the 2026-11-08 redesign deploy).
- https://psy-fi.space/gpu/ serves the GPU lab HTML.
- https://psy-fi.zer0state-noema.workers.dev/health is not this Worker (`workers.dev` is off).
- https://psyfi.zer0state-noema.workers.dev/health still returns HTTP 200. The older script was not deleted and does not own the domain.
- `wrangler.jsonc` names script `psy-fi`, binds only `psy-fi.space`, and turns `workers.dev` and preview URLs off.
- The vision key and the model id are not in the repo.

## Users / systems

- Users: an operator opening Psy-Fi by the bought name, and a visitor using the shell, the GPU lab, and the API with no login.
- Systems: Cloudflare Worker `psy-fi` on account Zer0state, its container and durable object, static assets, and a direct call to `https://integrate.api.nvidia.com` when image reading is configured. Worker `psyfi` remains a separate script.

## Constraints

Product-true locks:

- The public script is `psy-fi`. Worker source stays in `workers/psyfi/`.
- One custom domain, `psy-fi.space`. No `www`. No `workers.dev` hostname on this script.
- Same path split: `/api`, `/simulate`, `/health`, `/ready`, `/docs`, `/redoc`, and `/openapi.json` go to the container. The shell, `/gpu/`, static files, and the service worker are assets.
- Own container class `PsyfiApi` (port 8000, `standard-1`, outbound internet, 10 minutes idle, one process) and own durable object binding `PSYFI_API`.
- `NVIDIA_API_KEY` is a secret on `psy-fi`. `NVIDIA_VISION_MODEL` is a deploy-time var. `NVIDIA_API_BASE` stays empty. None of those values are committed.
- No login, API-key check, origin allowlist, or rate limit.
- Freeze id, `api_version`, FastAPI `version`, and the session `engine_version` default stay as they are.
- The image-reading request stays `reasoning_effort` `none` with the existing token cap and the not-medical-advice sentence.
- CI tests do not call Cloudflare and do not depend on DNS.

Non-goals:

- Attaching the domain to Worker `psyfi`, or deleting that script.
- `www.psy-fi.space`.
- An AI Gateway, a cached upload, a retry, or a fallback model on this host.
- Catalog reload, a catalog rebuild, or preset writes.
- Hardware Ultra frame times, and hardware-quality scaling.
- A product-version bump, a retag of `v1.4.0`, or a GitHub Release.
- Pinning a model id in git, the image, Compose, the client, or the docs.

## Open questions

Researched 2026-11-08 with a recommendation each: [`docs/specs/OPEN_QUESTIONS.md`](docs/specs/OPEN_QUESTIONS.md).

- Whether a later host should send production vision through an AI Gateway. The live host does not. The Call section of [`docs/specs/cloudflare-nvidia.md`](docs/specs/cloudflare-nvidia.md) records the direct call and leaves the gateway undecided.
- Whether catalog reload stays, is renamed, or is removed. No ticket.
- Hardware Ultra evidence (issue #10) and any later hardware-quality scaling. Not this host.
- A committed vision-bench receipt. The bench is on `main` (pull request #40) and adds no public route. CI scores a receipt only after a person runs capture.

## Verified / assumed

| Claim | Label |
| --- | --- |
| https://psy-fi.space/health, `/ready`, `/`, `/gpu/`, and `/sw.js` answered as the outcome says on 2026-11-07, and again on 2026-11-08 after versions `7f79f732`, `363b5d70`, `3d97825f`, `97b60aaf` and `94e47554` | `[verified: deploy checks against the live host]` |
| Worker `psy-fi` version `94e47554-10d5-4d8e-ab2b-5cf346305857` (2026-11-08, after `97b60aaf`, `3d97825f`, `363b5d70`, `7f79f732` and `d27e5f06`) is the current version, and the secret and the vision var are both set | `[verified: wrangler deployments list and the version's binding names]` |
| Worker `psyfi` still serves its workers.dev health route | `[verified: GET /health 200 at 2026-11-07T23:51:48Z]` |
| A deploy from this `wrangler.jsonc` updates `psy-fi` and does not update `psyfi` | `[verified: the two hostnames after this deploy]` |
| `origin/main` at `bf5953b` names script `psy-fi` and includes the vision bench | `[verified: pull requests #39 and #40 are merged]` |
| The bench modules add no public route | `[verified: pull request #40]` |
| No image-reading POST was made for this deploy | `[verified: that call was not run]` |
| The Call section records a direct call to `https://integrate.api.nvidia.com`. An AI Gateway is not a requirement of this host | `[verified: docs/specs/cloudflare-nvidia.md Call section]` |

## Author / date

Author and date are in the header. Status is accepted because the operator ordered this deploy and the host is live.

## Next

The hostname work is done. Do not implement a new product from this file. Open questions stay open until a human accepts a later intent.
