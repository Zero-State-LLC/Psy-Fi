# Spec: Vision bench

Status: implemented. Pull request #40 is merged. A non-finite intensity is a parse failure. This file is not a rebuild order.
Seam: the local capture and the CI scorer. No public route.

## Problem Statement

The caption route tells the operator what a picture shows, and then stops. It does not say whether that reading would move the consciousness field, or whether the catalog would offer a different experience. A mode label and an intensity number are not that distance. The field the instrument already builds is.

## Solution

A person runs one local capture against the one configured vision model and four fixed images. The capture stores each raw mode, intensity, and latency. CI rebuilds the same images, checks the oracle, and scores a stored receipt in field units. The headline number is how far the model's mode and intensity move a ParameterField from the oracle's. Beside it, the report says whether that mode would offer a different catalog experience. Mode match is a diagnostic. CI does not call the provider. A large displacement is a result. It does not fail the build.

## User Stories

1. As an operator, I want four fixed images, so that two runs can be compared.
2. As an operator, I want one image for each recommendation branch, so that void, power, attractor, and the caller case are all represented.
3. As an operator, I want those images generated, so that the bench does not depend on a photograph.
4. As an operator, I want the same pixels in capture and in CI, so that the score is about the model and not a different picture.
5. As an operator, I want the oracle mode recorded for each image, so that I can see what the field's own rule would have chosen.
6. As an operator, I want the oracle to use the existing recommendation, so that the bench does not invent a second classifier.
7. As an operator, I want caller mode and intensity frozen, so that the caller image does not drift between runs.
8. As an operator, I want substance, seed, phase, and quality frozen, so that the two fields differ only by mode and intensity.
9. As an operator, I want a bench prompt in perceptual language, so that the model is not handed the numeric cutoffs.
10. As an operator, I want that prompt to stay different from the caption prompt, so that the bench does not become a caption contest.
11. As an operator, I want one configured model per capture, so that a run names the model that answered.
12. As an operator, I want the model id copied from the environment, so that the repo does not pin one.
13. As an operator, I want capture to refuse an unset key, so that a dry run does not pretend to have called the provider.
14. As an operator, I want capture to refuse an id outside the `nvidia/` namespace, so that a text or Workers AI id cannot be scored as vision.
15. As an operator, I want the oracle checked before any post, so that a broken corpus spends nothing.
16. As an operator, I want one post per image, so that a run has four answers and no retry.
17. As an operator, I want a provider failure kept as a row, so that a timeout is evidence rather than a missing file.
18. As an operator, I want the key stripped from a provider detail, so that a receipt cannot store the secret.
19. As an operator, I want a non-JSON answer kept as a parse failure, so that prose is not treated as a mode.
20. As an operator, I want `Open`, a percent, and a missing field rejected, so that only the four mode names and a unit interval count.
21. As an operator, I want `NaN` and other non-finite intensities rejected, so that a bad number is not scored as a full-strength field.
22. As an operator, I want the receipt written only after the posts were attempted, so that a preflight failure leaves an old receipt in place.
23. As an operator, I want the receipt replaced in one step, so that a crash does not leave a partial file.
24. As an operator, I want CI to score without a network call, so that the build does not spend the key.
25. As an operator, I want CI to skip a missing receipt, so that the bench is green before anyone has captured.
26. As an operator, I want a present, well-formed receipt scored, so that a human capture becomes a checked report.
27. As an operator, I want disagreement to stay green, so that a model that moves the field is a result and not a broken build.
28. As an operator, I want the headline in ParameterField units, so that the number is a distance in the instrument and not a caption grade.
29. As an operator, I want a catalog switch printed beside that distance, so that I can see whether the offered experience changed.
30. As an operator, I want mode match printed as a diagnostic, so that a matching label is not mistaken for a small field change.
31. As an operator, I want image hints left out of the distance, so that the score is not counting pixels twice.
32. As an operator, I want the caption route left as it is, so that Read image still returns an inferred caption and still does not write the field.
33. As a maintainer, I want no new public route, so that the bench cannot be triggered from the website.
34. As a maintainer, I want the report printed and not committed, so that a score is not frozen into git by a test run.

## Implementation Decisions

- The seam is one module for the corpus, the oracle lock, the parse, and the score, plus one capture script. The script posts through the existing one-shot client. It does not call the caption route.
- Images are 64×64, RGBA, alpha 1, the same value in R, G, and B. Order is void, power, attractor, caller.
- Void is every pixel 0.5. Power is columns 0–31 at 0 and columns 32–63 at 1. Attractor is vertical stripes four pixels wide. Caller is columns 0–29 at 0.35, 30–33 at 0.55, and 34–63 at 0.75. A one-pixel checker is not the attractor image.
- The oracle calls the existing recommendation with caller mode `open` and intensity `0.7`. Expected modes are void, power, attractor, and open. Intensities are not pinned. The cutoff order stays attractor, then void, then power, otherwise the caller mode.
- Substance is `lsd`, seed is 42, phase is 0.4, quality is balanced, there are no modulators, and there are no image hints. `field_displacement` is the sum of absolute differences of ParameterField `parameters`, rounded to 4 decimals. Hints are excluded.
- `catalog_switch` uses the existing positive LSD list and the existing rank function. The scorer may take an injected list in tests. It does not pin a real catalog id in the spec.
- `prompt_revision` is 1. The prompt is: "Look at this image. Choose one mode: attractor when the picture is full of dense edges, void when it is dim and flat, power when it is bright and strong, open otherwise. Choose an intensity from 0 to 1. Reply with JSON only, with the keys mode and intensity. No other text."
- Each post uses that prompt, `max_tokens` 256, `reasoning_effort` `none`, and a 30 second timeout. There is no retry and no second model.
- Receipt schema is `psyfi.vision_bench_capture.v1`. The repo path is `fixtures/qa/vision_bench_capture.v1.json`. The implementation does not create that file. Report schema is `psyfi.vision_bench_report.v1` and is printed only.
- A parse accepts only the four mode strings and a finite JSON number from 0 to 1. `NaN` is a parse failure. Markdown fences are not stripped.
- A failed row stores null mode and intensity, `parse_ok` false, and `error` `provider` or `parse`. Provider detail is one line, key-stripped, and capped at 180 characters.
- Exit 0 only when all four rows parse. `complete` is true only when every row has a numeric displacement. A large displacement, a catalog switch, and a well-formed parse failure do not raise. A wrong schema, caller, revision, or an empty positive LSD list does raise.

## Testing Decisions

A good test drives the corpus, the parser, and the scorer with in-memory receipts. It does not call NVIDIA and it does not require the model to agree with the field.

- Oracle lock: the four images return the four modes and sit on the stated side of the cutoffs. Intensities stay unpinned.
- Scorer: identical mode and intensity yield displacement 0. A changed mode is scored in field units. An injected two-recipe catalog proves a switch. A parse failure leaves the distances null and does not raise.
- Parser: prose, a percent, `Open`, a missing field, and `NaN` are parse failures. A key inside a provider detail is redacted.
- Capture: unset key, a non-`nvidia/` id, an `@cf/` id, or a broken oracle performs no post and does not replace an existing receipt.
- Receipt file: the test skips when the fixture is absent. When the file is present and well formed, it is scored and disagreement stays green.
- Caption contract: the bench prompt and the caption prompt are different strings, and the public router has no bench route.

Prior art is the image-reading tests and the existing recommendation tests.

## Out of Scope

- GPU frame time, Ultra fps, and issue #10.
- Hardware detection and quality scaling.
- A change to the caption route, its prompt, its medical sentence, or its response.
- A new public HTTP route, a login, a rate limit, an AI Gateway, or a catalog reload.
- A multi-model button, a committed score, or a latency budget.
- A model id constant in source, tests, or this document.
- Writing a reading into presets or the catalog.
- A shared page that shows vision and GPU results together.
- Sharing a score, a corpus, or a pass rule with a later GPU bench.

## Further Notes

The design notes for this bench live beside the plan that implemented it. This file is the decision record. The caption route remains a side reading.

No receipt is in the tree until a person runs the capture. Do not invent one.
