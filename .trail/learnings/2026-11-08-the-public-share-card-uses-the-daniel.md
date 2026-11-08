---
title: The public share card uses the launch image
author: Daniel
date: 2026-11-08
branch: fix/social-preview
id: l-83f36763
scope: repo
status: active
src: agent
touches:
  - ".github/pull_request_template.md"
  - psyfi_api/templates/index.html
  - tests/test_static_shell_assets.py
  - psyfi_api/static/images/psyfi-hero.jpg
---

## Decided
- The homepage share card is Open Graph and a Twitter large-image card in the shell template. The image is the existing launch JPEG, addressed as an absolute URL on https://psy-fi.space. The title and description stay the ones already on the page.

## Tried and ruled out
- Treating the apple-touch icon or the PWA icons as the card. They load, and they are the wrong picture for a link unfurl. A relative image URL is not a share card, because the crawler does not turn it into the public host.

## Watch out
- CI does not deploy. The live card changes when Worker psy-fi is deployed from a tree that contains these tags. Pass --keep-vars.

## In the code
- psyfi_api/templates/index.html holds the og: and twitter: tags. The image file is psyfi_api/static/images/psyfi-hero.jpg. tests/test_static_shell_assets.py checks the absolute URL and the 1400 by 933 size.
