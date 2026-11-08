# Intent — shell front page and workbench redesign

Author: drafted by Claude for the operator
Date: 2026-11-07
Status: accepted (by the operator in chat, 2026-11-07)
Product: PsyFi (`Zero-State-LLC/Psy-Fi`)

This file is a proto-spec. It comes **before** specify / plan.
Next stage is spec/plan. Do not skip to code.

## Problem

A first visit to https://psy-fi.space/ lands on a launch splash that names the product and offers "Enter workspace", but never says what PsyFi does or why someone would open it. Behind it, the workspace is one long column of panels: the field viewport scrolls out of view while its own control rail is still being worked, the substance preset list runs half a panel wide, and every region looks the same.

The shell also carries tells the locked design system refuses: labels in tracked monospace, middle-dot meta strings, colour literals outside the token block, a metric bar that animates `width`, a tooltip hidden at rest, buttons and drawer toggles without the design's focus ring, and a capabilities table that is cut off at 320px.

[verified: live site at 1440 x 900 and 320 x 700 on 2026-11-07; Hallmark sloplint before record of `psyfi_api/templates/index.html` and `psyfi_api/static/style.css`]

## Outcome

Observable done (a stranger can check this without reading the chat):

- https://psy-fi.space/ opens on a front page that says what PsyFi is in one headline and one sentence, shows real field captures from the Live Experience, and keeps "Enter workspace" in view while the page scrolls.
- Every id, link, form field, script tag and test hook in `psyfi_api/templates/index.html` before the change is still present after it.
- At 1440 x 900 in the workspace, the Live Experience field stays in view while its control rail scrolls.
- Simulation and Results sit side by side at desktop width; presets, history and capabilities no longer leave half their panel empty.
- No page-level horizontal scroll from 320 to 1920px, and the capabilities table scrolls inside itself on a phone.
- `python3 -m pytest tests/ -q` passes. The only test edits are the two lines that pin the service-worker cache name, bumped with it.
- `/sw.js` names cache `psyfi-shell-v43`, so returning visitors drop the old shell on the next deploy.
- Hallmark sloplint reports 0 Floor failures on the changed template and stylesheet.

## Users / systems

- Users: a first-time visitor who needs to know what the instrument is before entering it, and a returning operator who works the Live Experience and Simulation tools.
- Systems: the static shell (`psyfi_api/templates/index.html`, `psyfi_api/static/style.css`), the launch splash script, `app.js`, the service worker, and the locked `design.md`.

## Constraints

Product-true locks (do not reopen in implement):

- `design.md` stays the system: palette, Space Grotesk / IBM Plex Sans / IBM Plex Mono, one cyan signal, the core sigil, N9 nav, Ft2 footer, no gradient headlines, no pill navigation, no glow.
- The launch splash still scans before Enter: `#launchEnterBtn` stays disabled until the scan completes, and "Skip scan" still enters at once.
- No change to `app.js`, `viz/*.js`, the API, or any test beyond the cache-name bump below. `sw.js` changes only its cache name.
- Disclaimers stay verbatim: "modeled outputs, not medical findings" and "Not medical advice".
- New front-page copy states only facts already in the README, the control tooltips or the recipe catalog. No invented metric, quote, logo or user count.
- Research and visualization only. Nothing on the page reads as medical, diagnostic or therapeutic advice.

Non-goals:

- New product behaviour, routes, or API calls.
- A new font, palette or brand mark.
- Privacy or terms pages (none exist; a footer link would point nowhere).

## Open questions

- `design.md` says the device scan starts closed on the entry fold. The front page keeps the scan drawer closed in the hero, so this holds; `design.md` gains one line naming the front page sections. Accept that amendment? Answered: `design.md` carries the front-page line since pull request #44.
- Settled 2026-11-07: the operator asked for the cache bump in this change. `sw.js` moves to `psyfi-shell-v43`, and the two tests that pin the name (`tests/test_static_shell_assets.py`, `tests/test_jobs_and_cancel.py`) move with it. `context.md` and the root `intent.md` keep v42 until the host is redeployed, because they record the live host.
- The front-page captures are stills taken from the local app at seed 42. Should they be refreshed when the renderer changes? Answered for now (2026-11-08): the shell renderer has not changed since the captures, so no refresh; refresh them when `psyfi_api/static/viz/` or `renderer.js` changes.

## Verified / assumed

| Claim | Label |
| --- | --- |
| The live page does not scroll sideways at 320px; only `#capabilityTable` overflows (463px) | `[verified: live site, 320 x 700, 2026-11-07]` |
| The core sigil loads on the live site | `[verified: naturalWidth 48 on both <img> tags]` |
| Tests assert ids, script tags and the SW cache name, not layout or class structure beyond `launch-scan-drawer` and `launch-pending` | `[verified: tests/test_static_shell_assets.py]` |
| `launchSplash.js` and `app.js` find elements by id, plus `.preset-btn`, `.substance-card`, `[data-tip]` and `#capabilityTable tbody` | `[verified: grep of the scripts]` |
| The six front-page captures are real Live Experience renders | `[verified: captured from the local shell, seed 42, WebGL path]` |
| "The field is expressive. The instrument is precise." is the owner's own line | `[verified: README.md, Why section]` |

## Author / date

Author and date are in the header. Update the date if the draft is revised.

## Next

Implemented in pull request #44 and live on https://psy-fi.space as Worker version `363b5d70`. This stream is done; a further shell change starts a new intent.
