# Spec: MIDI

Status: ready-for-agent. The remaining gap is GitHub issue #21. This file stays the decision record. Do not add a login.
Seam: the MIDI HTTP routes and `MIDIService`.

## Problem Statement

The operator wants a hardware controller or a DAW to move instrument parameters, and wants field metrics to leave as MIDI when an output port is open. That bridge has to be explicit. It must not start itself, and it must not become a second simulation.

## Solution

MIDI is off until a client starts it. One service instance can run. Input maps CC, notes, and program changes onto parameters and presets. Output can emit from the open port. If the MIDI libraries are missing, the routes say so and do not pretend a port is open. Parameter changes still have to pass through the ParameterField. Raw hardware output is a separate, explicit send.

## User Stories

1. As an operator, I want to list input and output ports, so that I can pick a device.
2. As an operator, I want an empty list and a clear unavailable flag when MIDI libraries are missing, so that the UI can hide the control.
3. As an operator, I want to start the service with a chosen input, output, channel, and curve, so that I arm one setup.
4. As an operator, I want a second start refused while one service is running, so that two clients cannot open the same ports.
5. As an operator, I want to stop the service, so that ports close.
6. As an operator, I want status to show whether it is running and which ports are open, so that the panel matches the process.
7. As an operator, I want CC and note sends rejected when no output port is open, so that a send cannot silently vanish.
8. As an operator, I want note, CC, and duration bounds enforced, so that a bad message is a client error.
9. As an operator, I want incoming CC to modulate ParameterField parameters, so that the controller stays inside the instrument.
10. As an operator, I want the service to stay stopped across a normal page load, so that opening the shell does not grab hardware.

## Implementation Decisions

- MIDI libraries are part of the default Python install, not an optional extra. The guide that says to install them separately is stale.
- The service is one process-global instance.
- Start opens the named ports, then marks the service running.
- There is no login on these routes. The trust boundary is whoever can reach the port.
- Field metrics remain Python-authoritative. MIDI output is a translation, not a new metric.

## Testing Decisions

A good test substitutes a fake port and asserts start, double-start, stop, and send rejection. It does not require a physical controller.

Prior art: the MIDI route tests that monkeypatch availability and the service.

## Out of Scope

- A browser Web MIDI implementation that bypasses the Python service.
- Automatic port selection.
- Per-user MIDI sessions on a shared server. This spec assumes one operator per process.

## Further Notes

Because the routes are unauthenticated and the process listens on all interfaces, a second machine that can open the port can start the service and send notes. That matches "one operator per process" only when the port is not exposed. The audit records the exposure.
