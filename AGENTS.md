# Agent contract — PsyFi

You are working in **PsyFi** (`Zero-State-LLC/Psy-Fi`).
This file is the canonical contract for Cursor, Claude, Codex, Grok, and OpenClaw.
Harness adapters (`CLAUDE.md`) only point here.

## Intent

Non-trivial work starts **intent → spec/plan → code**.
Read the active intent in [`intent/`](intent/) before editing.
Decision records live in [`docs/specs/`](docs/specs/).
Runtime conformance is [`docs/specs/AUDIT.md`](docs/specs/AUDIT.md). Read its "Later main" note first.
A new agent starts at [`HANDOFF.md`](HANDOFF.md).
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

The code map is local. Use the Trail section below. Start prose at [`PROJECT_INDEX.md`](PROJECT_INDEX.md).
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

## Agent skills

### Issue tracker

GitHub issues on this repo. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical role names: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context. See `docs/agents/domain.md`.

## Size

Keep this file short. Move procedure out, not in.

<!-- trail:start -->
## Trail — repo context graph

This repo is indexed in `.trail/cache/`: small linked markdown nodes that explain each
system and carry exact file:line spans, kept in sync with the code through git.

For ANY task here — understanding how something works, finding where code lives,
or scoping a change — get context from the graph before grepping or opening
source files. Re-ask freely (it's cheap) and reuse literal identifiers you
already have (symbol, error string, file name) as the query. New to this repo?
Run `trail map` first — a token-budgeted orientation (dir clusters, hubs,
hotspots), no LLM, no key.

- Run `trail ask "<your question>" --source` → ranked nodes with the relevant
  code spans inlined (each hit's ≤8-line crux by default; `--full` for whole
  definitions when the crux isn't enough). Match the tool to the task shape:
  for understanding or editing, the top node IS the answer — cite its
  `covers:` file:line spans and edit straight from `--source`. For
  exhaustive tasks ("every occurrence / every caller of this pattern"), ranked
  results are top-N, not complete — run `trail grep "<literal>"` instead
  (exhaustive over indexed files, grouped by enclosing symbol), falling back
  to raw `grep -rn` only for unindexed files.
- `trail skeleton <file>` → every definition's signature + span, ~10× cheaper
  than reading the file; use it to skim an API surface.
- `trail callers <symbol>` gives precomputed, exact edges — who calls this.
  Add `--direction out` for what it calls, or `--depth N` to walk
  transitively for the full blast radius. For structural questions, skip
  ranking and use this directly.
- Or browse: `.trail/cache/INDEX.md` lists every node; follow the links.
- Monorepos and folders of multiple repos rank fairly across sub-projects —
  hits carry `[scope/]` labels naming which one they're from. Narrow with
  `trail ask "<task>" --in <scope>/` once you know where you're working.

If a returned span is truncated ("+N more lines"), open the file at that exact
range before finalizing. Only open source files when a node genuinely lacks a
needed detail, and then at the exact file:line the node points to — never
re-read whole files.

After big code changes, refresh the graph with `trail build` (deterministic,
no API key, $0).
<!-- trail:end -->
