# Spec: Live Experience

Status: implemented. Pull request #29 is merged. This file stays the decision record. Do not rebuild the field.
Seam: parameter mapping, timelines, planner, and journey builders, then the shell that renders their output.

## Problem Statement

The operator needs a visual instrument whose picture follows a declared field, not whatever the canvas last painted. Intensity, motion, and substance choice must stay inside a safety limit. Neutral must actually calm the picture. Notes and plans must stay labeled as inference, not as medical findings.

## Solution

An immutable ParameterField is the visual authority. Substance overlays and experience recipes bias that field. A safety pass clamps flash and luminance. Neutral View rematerializes the field instead of painting a calm label on an expressive one. The instrument adds a non-linear intensity map, hold-and-compare, optional place-and-time anchors, a deterministic planner, and a Journey object the browser can archive locally.

## User Stories

1. As an operator, I want to pick a substance, a recipe, and a mode, so that the picture follows the catalog.
2. As an operator, I want intensity, seed, and a phase timeline, so that I can scrub one run.
3. As an operator, I want Neutral View at any time, so that the field drops to a calm presentation.
4. As an operator, I want Neutral to rebuild every timeline frame, so that expressive engines do not stay on under a calm flag.
5. As an operator, I want Reduce Motion to lower motion cost, so that a vestibular setting changes the field.
6. As an operator, I want the strictest intensity cap among the experience and the overlay, so that a high slider cannot bypass the recipe.
7. As an operator, I want a safety pass on the canvas and WebGL paths, so that flash and luminance stay bounded.
8. As an operator, I want camera, motion, audio, and haptic input to modulate the ParameterField only, so that sensors never become a second simulation.
9. As an operator, I want an instrument map and a station dial for intensity, so that commits land on deliberate steps.
10. As an operator, I want to pin one field and compare it with the live field by wipe, blink, or split, so that I can hold two presentations.
11. As an operator, I want comparisons saved in this browser, so that I can restore a hold later.
12. As an operator, I want optional latitude, longitude, year, hour, and solar elevation, so that lighting can follow a place and time without being required.
13. As an operator, I want a planner that states motifs and lighting from the field, so that I get a deterministic reading.
14. As an operator, I want my notes echoed as notes, so that they do not become authority over the field.
15. As an operator, I want planner text shown as text, so that a note cannot change the page.
16. As an operator, I want a Journey object I can save and restore in this browser, so that a run has a portable local record.
17. As an operator, I want transitions between phase, Neutral, load, and journey to be safety-clamped, and skipped when Reduce Motion or hold-and-compare is on, so that a scene change cannot skip the safety pass or play motion I turned off.
18. As an operator, I want every planner and journey to say it is not medical advice, so that the instrument does not present itself as care.

## Implementation Decisions

- Catalog recipes and substance overlays are data. Mapping them is pure and deterministic for the same inputs.
- Modes differ. Neutral dominates engine choice.
- Solar elevation may bias lighting. It does not replace the field.
- Planner output is inferred. It carries motifs, lighting notes, a hash, and optional operator notes. It is not authoritative.
- Journey output packages the field, the planner, anchors, and a comparison id for the browser archive.
- Anchors are optional. Missing anchors leave the field unchanged.
- The shell is the legacy page at `/`. The GPU lab is a separate route and is specified on its own.
- IndexedDB holds history, comparisons, and journeys on the client. The server does not store them.
- Planner text, operator notes, preset names, history fields, comparison titles, and journey titles are assigned as text. A note that contains a tag stays visible as characters. Pull request #29.

## Testing Decisions

A good test fixes a substance, mode, intensity, and seed, and asserts the field hash, the engine set, or the schema. A good Neutral test shows the engines change, not only a flag.

Prior art: experience catalog tests, overlay golden tests, scene-snapshot Neutral and intensity-cap tests, planner and journey schema tests, and the viz helper numeric tests.

## Out of Scope

- The GPU present stack. That is the GPU lab spec.
- Server-side accounts or a shared journey database.
- Clinical interpretation of valence, coherence, or motifs.

## Further Notes

Shell history, comparison titles, preset names, and planner text are interpolated into HTML. The decision is that planner text is text. The audit records where the shell treats it as HTML.
