# Spec: Telemetry

Status: implemented. The process-global opt-in is the decision, and the code matches it. This file is not a rebuild order.
Seam: the telemetry routes and the in-process buffer.

## Problem Statement

The project wants a place to record that a simulation finished or was cancelled, without shipping usage data. A half-finished analytics client would violate that.

## Solution

Telemetry does nothing unless the server flag is on and a client opts in. Events stay in a ring buffer in the process. Opting out clears the buffer. No vendor, disk log, or network sink exists. Production stays dark until a privacy policy and a data map exist.

## User Stories

1. As an operator, I want telemetry off on a default process, so that running the instrument records nothing.
2. As an operator, I want status to show the server flag, the opt-in, whether collection is active, and how many events are buffered, so that I can see whether this process is recording before I read it.
3. As an operator, I want opt-in to do nothing while the server flag is off, so that a browser click cannot enable collection alone.
4. As an operator, I want opt-out to clear the buffer, so that turning it off forgets what was held.
5. As an operator, I want to read the buffer only while I am diagnosing a local process, so that events are not an export.
6. As an operator, I want IP, user agent, email, tokens, authorization, cookies, and field values stripped, so that the buffer is not a secret store.
7. As a maintainer, I want only the named simulation events, so that the stub does not grow a general tracker.
8. As a maintainer, I want the legacy `/api/telemetry` paths to mirror `/api/v1/telemetry`, so that an old client hits the same gate.

## Implementation Decisions

- Server gate is `PSYFI_TELEMETRY_ENABLED`. Default is off.
- Client gate is a boolean on the process buffer, set by the opt-in route.
- Active means both gates are true.
- The buffer is capped. The default cap is 200 events.
- Allowed names are job created, simulate completed, and simulate cancelled.
- Ready responses may report whether the server flag is on. That is a boolean, not the event buffer.

## Testing Decisions

A good test hits status and opt-in on a process with the flag unset and asserts that opt-in does not activate collection.

Prior art: the ready and telemetry gate test.

## Out of Scope

- A hosted analytics sink.
- A privacy policy. Do not enable the flag in a deployed environment until that policy exists.
- Per-browser buffers. The current decision is one buffer per process.

## Further Notes

The opt-in flag is process-global. One caller can set it for every later caller on that process, and any caller can read the buffer. With the server flag off, the buffer stays empty, so the exposure is latent. The audit records it.
