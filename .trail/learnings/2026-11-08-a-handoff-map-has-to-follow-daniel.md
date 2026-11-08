---
title: A handoff map has to follow current main
author: Daniel
date: 2026-11-08
branch: docs/fable-handoff
id: l-5205a424
scope: repo
status: active
src: agent
touches:
  - ".github/pull_request_template.md"
  - HANDOFF.md
  - README.md
  - context.md
  - docs/specs/live-experience.md
  - docs/specs/telemetry.md
  - intent.md
---

## Decided
- The operator map and the accepted host intent have to match current main and the Call section. After the hostname merge and the vision-bench merge, main names Worker psy-fi and includes the bench. The Call section records a direct integrate call. An AI Gateway stays undecided.

## Tried and ruled out
- Leaving the pre-merge operator map in place. It told the next agent that GitHub main still named the older script, that the bench was unpublished, and that the gateway section had not been rewritten. A deploy from that reading would update the wrong Worker and would treat a merged bench as unpublished.

## Watch out
- The historical audit grid still says main has no Worker. Read the Later main note before treating a diverge row as open work.
