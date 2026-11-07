# Spec: Simulation and jobs

Status: implemented. Pull request #27 is merged. This file stays the decision record. Do not rebuild the field solver.
Seam: `run_simulation` and the in-process job store, observed through the simulate and job routes.

## Problem Statement

The operator needs a repeatable field from a seed, a grid, a step count, and an optional substance preset. A long run must be cancellable. A cancelled run must not come back later as a completed result. Unbounded grids or unbounded parallel work must not be the way the process dies.

## Solution

One Python runner serves the synchronous route and the job route. The same seed and preset produce the same metrics. Jobs live in the process, up to four at once, and completed jobs are forgotten after a retention cap. Cancel wins over complete.

## User Stories

1. As an operator, I want a simulation from width, height, steps, seed, and an optional preset, so that I can reproduce a field.
2. As an operator, I want the default seed when I omit one, so that an empty request is still deterministic.
3. As an operator, I want an unknown preset to fail clearly, so that a typo does not silently run the baseline field.
4. As an operator, I want grids outside the allowed range rejected, so that a huge request does not start.
5. As an operator, I want a session document and a provenance id on the result, so that I can store what ran.
6. As an operator, I want disconnect during a synchronous run to cancel it, so that leaving the page stops the work.
7. As an operator, I want to start a background job and read it by id, so that the page can poll.
8. As an operator, I want to cancel a queued or running job, so that I can abandon a run.
9. As an operator, I want a cancel that lands as the result is being saved to stay cancelled, with no result body, so that a race cannot publish a finished field after I cancelled.
10. As an operator, I want a fifth concurrent job refused, so that one browser cannot fill the process with workers.
11. As an operator, I want old finished jobs dropped, so that the in-memory store stays bounded.
12. As an operator, I want job ids unguessable, so that another caller on the same process cannot list my runs by walking integers.
13. As a maintainer, I want preset coupling and normalization to come from the preset registry, so that the runner does not invent substance parameters.

## Implementation Decisions

- Deterministic ABX runtime. The seed is an explicit input.
- Grid bounds match the request model: width and height from 8 to 512, steps from 1 to 1000, seed in the 32-bit unsigned range. The config max grid is 1024×1024 and is checked as well.
- Presets resolve by name or alias from the JSON registry. A missing preset is an error, not a fallback field.
- The job store is single-process. Four worker slots. At most 64 retained jobs. Eviction drops oldest terminal jobs only.
- Synchronous `POST /simulate/` and a scene snapshot that includes a simulation take one of those four slots. The slot stays held until that run returns, including when the request task is cancelled. A snapshot with simulation excluded does not take a slot. `field-frame` does not take a slot. Pull request #27.
- Job ids are random, not sequential.
- There is no job list route.
- Cancel and finalize share one lock. If cancel is set, the stored status is cancelled and the result is cleared.
- Synchronous simulate watches client disconnect and passes that flag into the runner.

## Testing Decisions

A good test is a fixed seed in and a fixed metric or status out, or a slot limit that returns the refusal. Tests should use the public runner and the HTTP routes.

Prior art: engine determinism tests, session seed tests, preset integration tests, and the job create, cancel, slot, and retention tests.

## Out of Scope

- CUDA or HIP for the Python field. Discrete GPUs accelerate the browser lab only.
- A multi-process job queue, Redis, or a database of runs.
- Sharing job results across machines.

## Further Notes

The synchronous route does not take a worker slot. Several overlapping `POST /simulate/` calls can run beside the four jobs. That gap is recorded in the audit. The Compose `WORKERS` value is not read by the process, so the store's single-process assumption still holds in the image as shipped.
