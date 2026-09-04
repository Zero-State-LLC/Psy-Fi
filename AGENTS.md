# Agent contract — PsyFi

You are working in **PsyFi** (`Zero-State-LLC/Psy-Fi`).
This file is the canonical contract for Cursor, Claude, Codex, Grok, and OpenClaw.
Harness adapters (`CLAUDE.md`) only point here.

## Intent

Non-trivial work starts **intent → spec/plan → code**.
Read the active intent in [`intent/`](intent/) before editing.
Next stage is spec/plan. Do not skip to code.

If the change is non-trivial and no intent exists, draft one from
[`intent/_TEMPLATE.md`](intent/_TEMPLATE.md) and wait for a human to accept it.
Do not invent product work.

## Commands

Commands from this repo's README. Do not invent others.

| Task | Command |
|---|---|
| Tests | `python3 -m pytest tests/ -q` |
| GPU tests | `npm run gpu:test` |
| README lint | `npx hallmark lint README.md` |
| GPU build (optional) | `npm run gpu:build` |

## Invariants

Already locked in [`PROJECT_INDEX.md`](PROJECT_INDEX.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md):

- Simulation truth stays in Python; UI is never authoritative.
- Visual authority is the immutable `PsyFiParameterField` / `scene_snapshot`, then a mandatory safety pass.
- Public browser API is `/api/v1` (hard-frozen). Prefer it for new routes.
- Research/visualization only — not medical, diagnostic, or therapeutic advice.
- Do not put secrets, tokens, or live credentials in the tree.
- Do not invent product behavior the spec does not name.

## Graft and docs

This repo has no `graft/`. Start at [`PROJECT_INDEX.md`](PROJECT_INDEX.md).
Do not copy a code map into this file.

## Escalation

Broken tests are a **defect**. A red honest check is better than a green lie.

If CI, tests, or validators look wrong — missing coverage, silent skips,
green-but-inert checks, or a suite that contradicts the spec:

1. Open a defect issue (this repo's bug template labels `type:bug`).
2. Do **not** reward-hack: do not delete, skip, weaken, or rewrite tests,
   fixtures, or CI solely to force green.
3. Do **not** weaken an assertion to match a broken implementation.

## Team context

Org and partner status is not this repo. When work spans people, agents,
or repos, load [`Zero-State-LLC/agent-context`](https://github.com/Zero-State-LLC/agent-context):

1. `HANDOFF.md`
2. `STATUS.md`
3. `DECISIONS.md` only if a prior choice affects this task

Clone: `gh repo clone Zero-State-LLC/agent-context ~/agent-context`.
Pull `--ff-only` before trusting a local copy.

## Skills

Name only skills that already exist here. Do not invent skills or bots.

- [`.agents/skills/codebase-memory/`](.agents/skills/codebase-memory/)
- [`.agents/skills/codebase-memory-mcp/`](.agents/skills/codebase-memory-mcp/)
- [`.agents/skills/hallmark/`](.agents/skills/hallmark/)

## Size

Keep this file short. Move procedure out, not in.
