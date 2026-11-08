# Intent — public site basics checklist

Author: drafted by an agent for the owner
Date: 2026-11-08
Status: accepted (owner request, 2026-11-08: "Make sure all of our websites have all of this.")
Product: PsyFi (`Zero-State-LLC/Psy-Fi`)

This file is a proto-spec. It comes **before** specify / plan.
Next stage is spec/plan. Do not skip to code.

## Problem

Zero State LLC asked that every one of its websites carry the same twelve basics: a branded 404, a call to action above the fold, a title and description per page, a 1200 x 630 share image, a full favicon set, `robots.txt`, `sitemap.xml`, alt text, honest loading states, a privacy policy, and disclosed analytics.

https://psy-fi.space has some of these. Unknown paths return the Worker's bare 404, there is no `robots.txt`, `sitemap.xml`, `favicon.ico` or privacy page, the share image is 1400 x 933, the home description is engine jargon, and the Live Experience says "Field idle" while the API container cold-starts or after it fails.

[verified: `wrangler.jsonc` has no `not_found_handling`; `scripts/stage_cloudflare_assets.py` stages only the shell, `static/`, `sw.js`, icons and the GPU build; `psyfi-hero.jpg` is 1400 x 933; `app.js` catches a failed recipe load with `console.error` only]

## Outcome

Observable done (a stranger can check this without reading the chat):

- An unknown path such as `/no-such-page` answers HTTP 404 with a PsyFi page that links home; an unknown `/api/…` path still answers JSON.
- `/robots.txt` allows the site, disallows the API and probe paths, and names `https://psy-fi.space/sitemap.xml`.
- `/sitemap.xml` lists `/`, `/gpu/` and `/privacy` as absolute `https://psy-fi.space` URLs.
- `/favicon.ico` is served. Every page links the ICO, the SVG sigil, the 180 x 180 touch icon and the manifest.
- `/`, `/gpu/`, `/privacy` and the 404 page each carry a unique title and description, and the full Open Graph and Twitter card set pointing at a 1200 x 630 image.
- `/privacy` exists, says Zero State LLC operates the site, links the parent policy, shows "Effective date: 2026-11-08", and is linked from every shell footer.
- The Live Experience, a simulation run and Read image announce pending and failed states to assistive tech and cannot be double-submitted.
- `python3 -m pytest tests/ -q` passes.

## Users / systems

- Users: a first-time visitor, a search crawler, a link preview, and a returning operator.
- Systems: the shell template, two new static pages, `app.js`, the service worker, the FastAPI app (local and Docker parity), the Worker asset config and the staging script, and the GPU lab entry HTML.

## Constraints

Product-true locks (do not reopen in implement):

- `/api/v1` stays hard-frozen. New FastAPI routes stay out of the OpenAPI schema.
- Research and visualization only. The privacy page and every description keep the not-medical-advice framing.
- The privacy page states only behavior the code shows, plus the Cloudflare hosting and Cloudflare Web Analytics facts the owner gave. It is flagged for owner review.
- Descriptions reuse wording from `README.md` and `PROJECT_INDEX.md`. No new product claim.
- Icons and the share image are derived from existing art (`icon-512.png`, `psyfi-hero.jpg`). No new mark.
- No second analytics tool. No change to GPU lab code.
- `app.js` changes, so the shell cache moves to `psyfi-shell-v44` and the tests that pin the cache name move with it, as in the 2026-11-07 stream.

Non-goals:

- A redesign of any page.
- Changing FastAPI's generated `/docs` and `/redoc` pages.
- Deploying. The live host changes only when an operator deploys.

## Open questions

- The GPU lab (`/gpu/`) has no footer, and its status line and Publish button live in GPU code. A privacy link and a busy state there need a GPU change. Owner decision.
- Owner review of the privacy page text.

## Verified / assumed

| Claim | Label |
|---|---|
| `env.ASSETS.fetch` applies `not_found_handling` when the Worker runs first | `[verified: Cloudflare docs, Workers static assets binding]` |
| Home CTA "Enter workspace" sits in the fixed front bar, inside the viewport at 390 x 844 and 1440 x 900 | `[verified: Playwright against the local dev server, 2026-11-08]` |
| The share image is a centre crop of `psyfi-hero.jpg` resized to 1200 x 630 with Pillow | `[verified: generated in this change]` |
| `favicon.ico` holds 16, 32 and 48 px renders of `icon-512.png` | `[verified: generated in this change]` |
| No Worker, FastAPI or nginx header blocks `static.cloudflareinsights.com` | `[verified: grep; nginx CSP allows any https: source]` |

## Author / date

Author and date are in the header. Update the date if the draft is revised.

## Next

The owner's request is the acceptance. The change is implemented on a working branch and is not deployed. The live host changes only when an operator stages `public/` and deploys Worker `psy-fi`.
