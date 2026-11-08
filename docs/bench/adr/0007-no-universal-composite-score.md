# ADR 0007: No universal composite score

Status: accepted, 2026-11-07.

## Problem

A single headline number is attractive and misleading: compute throughput, frame pacing and model field fidelity have different units, noise and hardware dependencies.

## Decision

Scorecards are multidimensional and per family. Each dimension carries unit, direction, source and confidence interval. Named composites exist only within a family, each with a published formula, no weights, no normalization, a plus or minus 10 percent sensitivity sweep, an explicit missing-data rule and a valid-comparison scope. Rankings use one primary dimension per family behind a gate.

## Alternatives

- A weighted geometric mean across families (Geekbench style): hides weight choices and ranks on noise.

## Consequences

Recommendations are specific sentences ("best throughput with determinism", "best 1 percent low under budget", "lowest FDE with a usable parse rate"). A composite with a missing input is null.
