# Spec: Deploy and CI

Status: ready-for-agent. The remaining gap is GitHub issue #16. This file stays the decision record. Do not rebuild the image from scratch.
Seam: the image, Compose, and the CI workflow. This seam is files and commands, not the simulation API.

## Problem Statement

A stranger should be able to build one container, open the shell, and trust that the same tests the README names were run on the commit. A green badge that did not run those tests is a false ship gate. A workflow copied from another product must not be able to deploy that product from this repo.

## Solution

Docker Compose is the local seam. It is not the production host. Production is the Cloudflare deploy in [Cloudflare and NVIDIA](cloudflare-nvidia.md). The image still builds the GPU package, installs the Python package, runs as an unprivileged user, and serves the API and the shell on port 8000 for local checks. Health checks use the Python standard library because the base image has no curl. CI on every push and pull request installs dependencies and runs the Python tests, the README lint, and the GPU test, typecheck, and build. Native mobile, Azure, and Render are not ship paths.

## User Stories

1. As an operator, I want `docker compose up -d --build` to serve `/health`, `/ready`, `/`, and `/gpu/` when the image build succeeds, so that one command is the local seam.
2. As an operator, I want the container to run as a normal user, so that the process is not root.
3. As an operator, I want the GPU build baked into the image, so that `/gpu/` does not depend on a laptop build step.
4. As an operator, I want a health check that does not need curl, so that the slim image can report liveness.
5. As an operator, I want an optional nginx profile for a reverse proxy, so that headers and upload size can sit in front of the API.
6. As an operator, I want an optional NVIDIA profile that reserves a GPU for the container, so that host readiness is documented. Browser WebGPU still uses the host browser.
7. As a maintainer, I want CI to run the Python test suite, so that a red test blocks the branch.
8. As a maintainer, I want CI to lint the README, so that the board at the top of the repo stays valid markdown.
9. As a maintainer, I want CI to typecheck, test, and build the GPU package, so that the baked lab matches the source.
10. As a maintainer, I want the CI workflow to declare its permissions, so that the job cannot inherit a broad token by default.
11. As a maintainer, I want the status badge and the package repository URL to point at this repo, so that a reader does not land on the archived fork.
12. As a maintainer, I want license metadata to match the license file, so that the repo does not claim two licenses.
13. As a maintainer, I want no workflow in this repo to deploy another product, so that a manual dispatch cannot target a different production host.
14. As a maintainer, I want production Compose to run the image contents, so that a bind mount cannot silently replace the built tree.

## Implementation Decisions

- The image is multi-stage. Node builds the lab. The Python image copies that output, the API, the core, docs, and data.
- The process command is one Uvicorn worker bound to all interfaces on port 8000. A `WORKERS` environment variable is not part of the command.
- Compose publishes host port 8000. The NVIDIA profile is off unless selected. Nginx is off unless the production profile is selected.
- Nginx, when used, sets a frame ancestor of the same origin, nosniff, a referrer policy, and a content security policy. The upload limit is 10 MB.
- CI is the workflow that runs on push and pull request to the default branch.
- The existing Pages workflow is not the production host. Production is a Worker plus static assets, specified in [Cloudflare and NVIDIA](cloudflare-nvidia.md). There is no `site/` tree.
- Secrets do not belong in the tree. The NVIDIA API key is a Cloudflare secret.

## Testing Decisions

A good test of this spec runs the named commands, or asserts the workflow file contains those commands. A test that only checks that a markdown board contains the word "Docker" does not satisfy the CI stories.

Prior art today is the production-readiness document tests. They are the wrong seam for this spec. The audit says so.

## Out of Scope

- Native iOS.
- Azure and Render one-click.
- Kubernetes.
- A hosted multi-tenant deployment with accounts. The required host is still Cloudflare, for this one instrument.
- Hardware Ultra capture as a CI job. That remains optional living QA.

## Further Notes

This spec states the ship the README and the readiness board claim. Where the workflow, Compose, license badge, or foreign deploy file disagree, the audit is the authority until the files change. Do not edit the readiness board's required phrases just to make the document tests pass.
