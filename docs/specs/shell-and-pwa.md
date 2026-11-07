# Spec: Shell and PWA

Status: implemented. The audit finds no code gap for an agent. Device evidence stays human QA. This file is not a rebuild order.
Seam: `GET /`, `GET /sw.js`, and the static shell assets.

## Problem Statement

The operator needs the instrument in a browser, including a phone, without a store install. Offline use must not pretend the Python simulation ran. The GPU route must not be cached as if it were the legacy page.

## Solution

`/` is the product shell. A root-scoped service worker caches the shell and static assets, uses the network for API and simulate calls, and treats `/gpu/` as its own route. History, comparisons, and journeys stay in IndexedDB in this browser. Icons and a manifest make the shell installable. Computation stays online.

## User Stories

1. As an operator, I want `/` to render the instrument, so that one URL is the product.
2. As an operator, I want the service worker registered for the whole origin, so that it can cover `/` and `/gpu/`.
3. As an operator, I want a versioned shell cache, so that an old cache is deleted on activate.
4. As an operator, I want HTML navigations to try the network first and fall back to the shell, so that offline open still shows the app.
5. As an operator, I want API, simulate, health, docs, and OpenAPI requests to skip the cache, so that a cached simulation cannot masquerade as a new run.
6. As an operator, I want `/gpu/` fetched from the network, so that the lab is not replaced by the legacy HTML while online.
7. As an operator, I want an offline GPU navigation to fall back to the shell, so that the failure is the known page.
8. As an operator, I want static files cache-first, so that repeat visits do not redownload the shell.
9. As an operator, I want local history I can restore and clear, so that this browser remembers runs.
10. As an operator, I want install icons and a manifest, so that the browser can offer install.
11. As an operator, I want safe areas and reduced-motion CSS, so that a phone and a vestibular setting are usable.
12. As an operator, I want readiness to fail when icons, the renderer, or the catalog are missing, so that a broken image is not called ready.

## Implementation Decisions

- The worker script is served from `/sw.js` with `Service-Worker-Allowed: /` and `Cache-Control: no-cache`.
- Cache name is the shell version recorded in the worker. Current decision: `psyfi-shell-v42`.
- GPU documents are not precached as shell HTML.
- The shell is zero-build. It is the Jinja page plus static scripts.
- Design tokens stay the existing `--pf-*` set. The lab mirrors neutrals. It does not replace them.

## Testing Decisions

A good test fetches `/sw.js` and asserts scope headers and cache name, and checks that the template wires the renderer, cancel, and install controls. It does not need a device lab for those assertions.

Prior art: service-worker header test, static shell asset tests, and the ready-check test.

## Out of Scope

- Native install binaries.
- Offline simulation.
- Embedding the GPU canvas inside the legacy page.

## Further Notes

Device-matrix rows are evidence the project filled in documents. They are not re-checked by this seam on every run. The audit treats them as unproven on hardware.
