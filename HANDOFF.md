# HANDOFF — Psy-Fi

**Audience:** Fable, or the next implementation agent.
**Repo:** `Zero-State-LLC/Psy-Fi`
**Product line:** `1.4.0`. Do not bump it, and do not retag `v1.4.0`, unless a human asks.

## 1. Start here

Read in this order before changing behavior:

1. This file.
2. [`AGENTS.md`](AGENTS.md).
3. [`docs/specs/README.md`](docs/specs/README.md), then the one spec for the slice.
4. [`docs/specs/AUDIT.md`](docs/specs/AUDIT.md) only after its "Later main" note. The grid under that note is the 2026-10-24 pass. It is not a work order.
5. [`context.md`](context.md) and [`intent.md`](intent.md) for the public host.
6. [`docs/CLOUDFLARE.md`](docs/CLOUDFLARE.md) before any deploy.

Specs are the decision records. They use the Matt Pocock shape: problem, solution, user stories, implementation decisions, testing decisions, out of scope. An implemented spec is not a rebuild order.

## 2. What is already built

| Spec | State |
| --- | --- |
| Public API, simulation and jobs, Live Experience, image seed, GPU lab, shell and PWA, MIDI, telemetry, deploy and CI | Implemented. Issues #16–#23 and #37 are Done. |
| Cloudflare and NVIDIA | Implemented. Public host is `https://psy-fi.space` on Worker `psy-fi`. Issue #36 is Done. |
| Vision bench | Implemented. Pull request #40 is merged. No public route. No receipt file until a person runs capture. |

The older Worker `psyfi` on workers.dev stays. Do not attach `psy-fi.space` to it, and do not delete it.

## 3. Hard stops

- Do not invent product behavior a spec does not name.
- Do not add a login, an API-key check, an origin allowlist, a rate limit, or an AI Gateway. The gateway is an open question. The live host calls `https://integrate.api.nvidia.com` directly.
- Do not decide catalog reload. The route stays as it is.
- Do not write hardware-quality scaling, and do not record frame times. Issue #10 stays Backlog and is not an agent ticket. This Mac is not Ultra evidence.
- Do not pin a model id or commit a key, a token, or a vision-bench receipt.
- Do not change the freeze id, `api_version`, the FastAPI app version, the session engine default, the image-reading medical sentence, or `reasoning_effort: none`.
- Do not add `www`.
- CI does not deploy. A deploy from `main` updates Worker `psy-fi` only. Pass `--keep-vars` or the same vision-model var.
- Do not force-push `main`.

## 4. Open, and not yours until a human accepts an intent

- Issue #10, hardware Ultra evidence.
- Catalog reload: keep, rename, or remove.
- Whether a later host should use an AI Gateway.
- A GPU frame-time bench. It does not share the vision bench score, corpus, or pass rule.
- A committed vision-bench receipt. A person has to run the capture first.

## 5. If the work is a new slice

1. Draft `intent/<change-stream>.md` from [`intent/_TEMPLATE.md`](intent/_TEMPLATE.md). Leave it `Status: draft` until a human accepts it.
2. Write the spec in `docs/specs/` with the headings in section 1. User stories are numbered and cover the slice. Name one existing seam.
3. Publish a GitHub issue on this repo, label `ready-for-agent`, and put it on org project 7. Project 16 is Noema. Do not file there.
4. Tests at that seam. External behavior. CI must not call Cloudflare or NVIDIA.
5. A pull request into `main`. Do not admin-merge unless a human asks.

A slice is not done because it compiles. The spec's testing decisions have to pass, and the out-of-scope list has to stay out.

## 6. Commands

Use the commands in [`AGENTS.md`](AGENTS.md). Do not invent others.

## 7. When something is ambiguous

Stop and say what is ambiguous. Do not guess a product decision. The specs and this file are the contract. A chat is not.
