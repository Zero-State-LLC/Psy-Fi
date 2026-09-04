# Intent

Stage-0 proto-specs for this repo. Canonical pack:
[`Zero-State-LLC/agent-context`](https://github.com/Zero-State-LLC/agent-context)
(`templates/intent.md.template`, `templates/sdlc/README.md`).

Non-trivial work starts **intent → spec/plan → code**.
Do not skip to code. Do not invent product work in this folder.

## Files

| File | Role |
|---|---|
| [`_TEMPLATE.md`](_TEMPLATE.md) | Blank intent. Copy this. |
| `<change-stream>.md` | One committed intent per change stream (after a human accepts) |

There is no product intent in this folder until a human accepts one.

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
