---
title: "One pull request template, the lowercase GitHub name"
author: Daniel
date: 2026-11-08
branch: fix/pr-template-case
id: l-783d424f
scope: repo
status: active
src: agent
touches:
  - context.md
  - tests/test_ci_metadata.py
  - ".github/pull_request_template.md"
---

## Decided
- The default pull request template is `.github/pull_request_template.md`. That is the file GitHub documents for a single template.
- The shared template body stays: Summary, related issue, testing, and the Partner Agents checklist.

## Tried and ruled out
- Keeping `.github/PULL_REQUEST_TEMPLATE.md` beside it. GitHub says pull request template filenames are not case sensitive, and `PULL_REQUEST_TEMPLATE/` is a directory for extra templates, not a second default file. On macOS the two index paths are one directory entry, so `git status` stays dirty.

## Watch out
- Remove only the uppercase index path with `git -c core.ignorecase=false rm --cached`. A plain `git rm` on this Mac can fold the two names together.
