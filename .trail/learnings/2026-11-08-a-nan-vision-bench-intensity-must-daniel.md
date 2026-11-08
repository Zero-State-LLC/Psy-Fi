---
title: A NaN vision-bench intensity must fail the parse
author: Daniel
date: 2026-11-08
branch: spec/vision-bench
id: l-c72e6021
scope: repo
status: active
src: agent
touches:
  - ".github/PULL_REQUEST_TEMPLATE.md"
  - psyfi_core/visualization/vision_bench.py
  - tests/test_vision_bench.py
---

## Decided
- `parse_model_content` rejects a non-finite intensity. `math.isfinite` is required before the 0-to-1 range check.

## Tried and ruled out
- Relying on `value < 0` and `value > 1`. Both comparisons are false for NaN, so the parser was marking the row as a success.

## Watch out
- `json.loads` accepts the `NaN` token and returns a float. Infinity is already outside the range. NaN is the value that slips through.
