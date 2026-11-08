---
title: A deploy from this Wrangler file updates psy-fi and leaves the older script
author: Daniel
date: 2026-11-07
branch: main
id: l-7dfc51ce
scope: repo
status: active
src: agent
touches:
  - ".github/PULL_REQUEST_TEMPLATE.md"
  - DEPLOYMENT.md
  - README.md
  - docs/CLOUDFLARE.md
  - docs/specs/README.md
  - docs/specs/cloudflare-nvidia.md
  - intent/README.md
  - tests/test_cloudflare_host.py
  - wrangler.jsonc
---

## Decided
- The published Wrangler file names the script `psy-fi` and binds only the custom domain `psy-fi.space`, with workers.dev and preview URLs off.
- A deploy from that file creates or updates Worker `psy-fi`. It does not update the older Worker `psyfi`, and it does not detach `psy-fi.space`.
- Worker source stays in `workers/psyfi/`. The directory name is not the script name.
- A later deploy of either script must pass `--keep-vars` or the same vision-model var. Without `--keep-vars`, Wrangler deletes vars the command does not pass. `--keep-vars` does not copy vars from the other script.
- Leave the API base empty on this host so image reading calls `https://integrate.api.nvidia.com` directly.

## Tried and ruled out
- Attaching `psy-fi.space` to the existing `psyfi` workers.dev Worker. The public name is its own script. The older script stays.

## Watch out
- A checkout that still names the script `psyfi` updates that older Worker and leaves the domain where it is.
- `secret put` does not take `--keep-vars`. After a secret change, confirm the plain-text vision var is still set. Do not print the secret or the model id.
