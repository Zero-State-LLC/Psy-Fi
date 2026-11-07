---
title: Psy-Fi issues stay off the Noema board
author: Daniel
date: 2026-11-07
branch: spec/cloudflare-nvidia-image-reading
id: l-e1fca81b
scope: repo
status: active
src: agent
touches:
  - ".github/PULL_REQUEST_TEMPLATE.md"
  - ".github/workflows/project-collaboration.yml"
  - docs/agents/issue-tracker.md
  - docs/specs/README.md
---

## Decided
- Psy-Fi issues belong on the org project titled Psy-Fi. The collaboration workflow reads PROJECT_NUMBER for that board. New items still land in Todo.

## Tried and ruled out
- Pointing PROJECT_NUMBER at 16. That project is Noema Kanban, so Psy-Fi cards would land on another product.

## In the code
- .github/workflows/project-collaboration.yml

## Watch out
- A Status field edit has to send the existing option ids for Todo, In Progress, and Done. Omitting those ids orphans cards.
