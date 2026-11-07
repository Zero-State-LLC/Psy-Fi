# PsyFi specs

Decision records for the web instrument. Written in the Matt Pocock spec shape: problem, solution, user stories, implementation decisions, testing decisions, out of scope.

These files record decisions the repo already made in `PLANS.md`, `docs/PRODUCTION_READINESS.md`, `docs/CONTINUATION_PLAN.md`, and the contract docs, plus the required production host: Cloudflare, calling the NVIDIA API with one vision-language model.

`docs/specs/AUDIT.md` checks those decisions against the runtime on `main` (`7ca678e0`).

The older boards stay where they are. Tests still assert their headings and phrases. Do not treat a green `tests/test_production_readiness.py` as proof the runtime matches these specs.

## Seams

One seam per spec. Existing seams only.

| Spec | Seam |
| --- | --- |
| [Public API](api-v1.md) | FastAPI app over `/api/v1`, legacy mirrors, and the freeze pack |
| [Simulation and jobs](simulation-and-jobs.md) | `run_simulation` and the in-process job store, through the HTTP job and simulate routes |
| [Live Experience](live-experience.md) | `map_parameters` / timeline / planner / journey builders, then the shell that renders them |
| [Image seed](image-seed.md) | `build_image_seed` and the image-seed HTTP routes |
| [GPU Lab](gpu-lab.md) | `psyfi.scene_snapshot.v1` in, present pipeline out |
| [Shell and PWA](shell-and-pwa.md) | `GET /`, `GET /sw.js`, and the static shell |
| [MIDI](midi.md) | MIDI HTTP routes and `MIDIService` |
| [Telemetry](telemetry.md) | Telemetry routes and the in-process buffer |
| [Deploy and CI](deploy-and-ci.md) | Docker image, Compose, and `.github/workflows/ci.yml` (local seam) |
| [Cloudflare and NVIDIA](cloudflare-nvidia.md) | Worker, static assets, Container, and the NVIDIA API call |

## How this sits in the workflow

`intent/` is stage 0. These specs are the next stage. Tickets, when cut, are disposable slices of a spec. A spec is the decision record.

The issue tracker is GitHub. `docs/agents/` maps the Pocock roles. A spec whose behavior already matches the runtime is marked implemented and is not an agent ticket. A spec with a remaining gap is marked `ready-for-agent` and names the GitHub issue. That issue is the agent contract for the gap. It is not a work order to rebuild the instrument.

## Tickets

The kanban is Zero-State-LLC project **#16**. New issues land in **Todo**. Columns are Backlog, Todo, Ready, In Progress, In review, and Done.

| Issue | Column | Spec |
| --- | --- | --- |
| #10 | Backlog | Hardware Ultra evidence. Not an agent ticket. |
| #16 | Ready | [Deploy and CI](deploy-and-ci.md) |
| #17 | Ready | [Image seed](image-seed.md) |
| #18 | Ready | [Simulation and jobs](simulation-and-jobs.md) |
| #19 | Ready | [Live Experience](live-experience.md) |
| #20 | Ready | [Public API](api-v1.md) |
| #21 | Ready | [MIDI](midi.md) |
| #22 | Ready | [GPU Lab](gpu-lab.md) |
| #23 | Done | [Cloudflare and NVIDIA](cloudflare-nvidia.md). Closed. The branch is in review and is not merged. |
