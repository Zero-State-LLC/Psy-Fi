---
title: A deploy does not replace a warm API container; wait out its idle timer before checking new routes
author: Daniel
date: 2026-11-08
branch: docs/merges-2026-11-08
id: l-25733d62
scope: repo
status: active
src: agent
touches:
  - HANDOFF.md
  - context.md
  - docs/specs/OPEN_QUESTIONS.md
  - docs/specs/README.md
  - intent.md
  - workers/psyfi/src/index.mjs
---

## Decided
After a deploy that changes the container image, verify with a route only the new image has, and only after no container route has been called for 10 minutes. Do not treat `--containers-rollout immediate` as proof the new image serves.

## Tried and ruled out
- Probing `/api/bench/v1/results` right after deploying `94e47554` (2026-11-08): FastAPI 404 for over 90 s of retries. Each retry reset the idle timer and kept the pre-deploy container alive.
- `wrangler containers info` and the app's "last modified" field: neither moves on a deploy, so neither shows which image serves.

## Watch out
- The `PsyfiApi` Durable Object starts a container only when none is running, and every request resets a 10-minute inactivity timeout. A container started before the deploy keeps serving the old image until it idles out.
- `/health` and `/ready` answer the same on old and new images (both `1.4.0`), so they cannot tell you which image is live.
- The first request after the idle stop cold-starts the new image and takes about 15 s.

In the code: `workers/psyfi/src/index.mjs` (`startAndWait`: `if (!container.running)` and `setInactivityTimeout(INACTIVITY_TIMEOUT_MS)`). Check `npx wrangler containers instances 224374f7189b4e3281bac784426c2f18`: the instance's created time must be after the deploy.
