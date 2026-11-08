# Intent

Stage-0 proto-specs for this repo. Canonical pack:
[`Zero-State-LLC/agent-context`](https://github.com/Zero-State-LLC/agent-context)
(`templates/intent.md.template`, `templates/sdlc/README.md`).

Non-trivial work starts **intent → spec/plan → code**.
Do not skip to code. Do not invent product work in this folder.

Accepted product decisions are recorded in [`docs/specs/`](../docs/specs/)
(Matt Pocock spec shape). [`docs/specs/AUDIT.md`](../docs/specs/AUDIT.md)
is the runtime check. Boards under `docs/` stay as evidence. They are
not a second spec.

## Files

| File | Role |
|---|---|
| [`_TEMPLATE.md`](_TEMPLATE.md) | Blank intent. Copy this. |
| `<change-stream>.md` | One committed intent per change stream (after a human accepts) |
| [`../intent.md`](../intent.md) | Accepted public-host intent. The handoff asked for this filename at the repo root. |
| [`../context.md`](../context.md) | Live-host map for the next operator. Not a second spec. |

Further streams still get their own file in this folder. The accepted public-host intent is the root [`intent.md`](../intent.md) because that handoff named the file. Do not treat this folder as empty of product intent while that file is accepted.

## How to start a change

1. Copy `_TEMPLATE.md` to `intent/<change-stream>.md`.
2. Fill Problem, outcome, users/systems, constraints, open questions,
   verified/assumed claims, author, and date.
3. Leave `Status: draft` until a human accepts it.
4. Then specify / plan. Then code.

Trivial typo or docs-only nits that do not change behavior, contracts,
or architecture do not need an intent.

## Team handoff

This folder is **this product**. Org and partner baton lives in
[`Zero-State-LLC/agent-context`](https://github.com/Zero-State-LLC/agent-context)
(`HANDOFF.md`, `STATUS.md`, `DECISIONS.md`). Load that repo when work
spans people, agents, or repos. Do not duplicate team status here.
