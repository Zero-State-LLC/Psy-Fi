# ADR 0003: Field Displacement Error as the interpretation headline

Status: accepted, 2026-11-07.

## Problem

Mode accuracy and intensity error are label metrics. They do not say whether a wrong reading would change the picture the instrument draws, and they are not on a common scale across modes.

## Decision

The headline metric is FDE: the L1 distance in `ParameterField.parameters` between the oracle field and the field reconstructed from the model's (mode, intensity) through `map_parameters` with the item's substance, seed, phase and tier. The smallest distance to any other mode at the oracle intensity is the ruler (`within_mode_step`). FDE is decomposed into mode-only and intensity-only parts. This generalizes the `field_displacement` idea of the merged vision bench to a locked 96-item corpus, structured inputs, perturbations, repeatability and baselines.

## Alternatives

- Model-as-judge: no deterministic reference, evaluator disagreement, cost.
- Pixel distance between a re-rendered reading and the original: couples the metric to the raster rather than to the field authority.

## Consequences

The oracle scores exactly 0; baselines calibrate the scale; the metric is in the instrument's own units. Mode accuracy and intensity MAE stay as diagnostics.
