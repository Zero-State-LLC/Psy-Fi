# ADR 0004: Measurement classes and evidence labels

Status: accepted, 2026-11-07.

## Problem

The repository already had a synthetic Ultra fps matrix that documents described as a pass. Benchmark results that mix synthetic stand-ins with measurements mislead.

## Decision

Every result, stage, capture and scorecard subject carries `measurement_class`: `measured`, `synthetic` or `replay`. Baseline providers are `synthetic`; replay receipts are `replay`; live providers, CPU runs and real browser captures are `measured`. The environment records `hardware_class` (`discrete`, `integrated`, `cpu_only`, `remote`, `unknown`) and an `unavailable` map for telemetry that was not collected. Scorecards refuse to compare mixed classes. Integrated-class results are never merged into the Ultra fixtures.

## Alternatives

- A boolean `synthetic` flag: cannot express replay.
- Trusting documentation: the audit showed that fails.

## Consequences

Committed examples include a synthetic capture that says so. Reports and index entries show the class next to every number.
