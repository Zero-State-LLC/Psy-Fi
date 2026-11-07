# Vision-model bench

Status: design. Not implemented.
Date: 2026-11-07.

The first bench scores one configured vision model against the field recommendation. GPU frame time is a later spec. The two benches do not share a score, a corpus, or a pass rule.

## Problem

The only vision-model call asks for one short paragraph and stores it as a caption. That caption stays off the field, the seed, and the presets. The field recommendation is `recommend_mode_intensity` in `psyfi_core/visualization/image_seed.py`. It reads pixel features and returns a mode and an intensity. Nothing measures whether a vision model returns that same recommendation.

## Goal

A person runs a local capture against the configured model. The capture stores the model's mode, intensity, and latency for four fixed images. CI rebuilds those images, runs the analyzer, and scores the stored answers. CI does not call the provider. A disagreement is a bench result. It does not fail the build.

## Non-goals

- GPU frame time, Ultra fps capture, and issue #10.
- Hardware detection and quality scaling.
- A change to the caption route, its prompt, or its response.
- A new public HTTP route, a login, a rate limit, an AI Gateway, or a catalog reload.
- A multi-model button, a committed score, or a latency budget.
- A model id constant in source, tests, or this document. The capture copies the id from the environment onto the receipt.
- Writing a reading into presets or the catalog.
- A shared page that shows vision and GPU results together.

## Locked decisions

- The score is mode and intensity. The analyzer keeps the five pixel numbers.
- Caller inputs are frozen at mode `open` and intensity `0.7`.
- The corpus is four generated images, one per branch of the recommendation.
- The bench prompt names the four modes in perceptual language. It does not include the numeric cutoffs or the intensity formula.
- Mode match is exact. Intensity match is a gap of at most `0.05`, owned by the scorer.
- The receipt stores raw answers. The scorer recomputes the match.
- One configured model per run. Comparing models means a second capture and a diff of the two receipts.
- The public worker and the frozen API stay as they are.

## Units

| Unit | Role | Depends on |
| --- | --- | --- |
| Corpus | Builds the four images. | Nothing. |
| Oracle | Runs the existing analyzer and recommendation. | Corpus. `analyze_features`, `recommend_mode_intensity`. |
| Capture | Posts once per image and writes the receipt. | Corpus, oracle lock, the existing one-shot client. |
| Scorer | Compares a receipt to a fresh oracle run and prints a report. | Corpus, oracle, receipt. No network. |

The corpus, the parse rules, the receipt check, and the scorer live in `psyfi_core/visualization/vision_bench.py`. The capture script is `scripts/capture_vision_bench.py`. It calls the existing one-shot client and the existing `nvidia/` model-id check. It does not call `read_image`.

## Corpus

Each image is 64×64, RGBA, alpha `1`, with the same value in R, G, and B. Values are floats from `0` to `1`. The builder is deterministic and uses no random source. Capture and CI both call it.

| Id | Pixels | Oracle mode |
| --- | --- | --- |
| `void` | Every pixel `0.5`. | `void` |
| `power` | Columns `0–31` are `0`. Columns `32–63` are `1`. | `power` |
| `attractor` | Vertical stripes four pixels wide. Columns `0–3` are `0`, columns `4–7` are `1`, and that pair repeats. | `attractor` |
| `caller` | Columns `0–29` are `0.35`. Columns `30–33` are `0.55`. Columns `34–63` are `0.75`. | `open` |

The recommendation checks attractor first (`edge_density > 0.55` and `contrast > 0.45`), then void (`energy < 0.28` and `contrast < 0.3`), then power (`energy > 0.6`). Anything else stays on the caller mode. A one-pixel checker does not reach attractor, because the edge measure is a central difference. The stripe width above is the pattern that does.

The oracle calls `recommend_mode_intensity(features, "open", 0.7)`. This design does not change that function.

## Bench prompt

`prompt_revision` is `1`. The prompt text is:

> Look at this image. Choose one mode: attractor when the picture is full of dense edges, void when it is dim and flat, power when it is bright and strong, open otherwise. Choose an intensity from 0 to 1. Reply with JSON only, with the keys mode and intensity. No other text.

## Capture

Preflight runs before any socket:

- `NVIDIA_API_KEY` is set.
- `NVIDIA_VISION_MODEL` passes the existing check: an `nvidia/` id, and not an `@cf/` id.
- The oracle lock holds: the four images return `void`, `power`, `attractor`, and `open`.

A preflight failure exits non-zero, opens no socket, and leaves an existing receipt in place.

Each image is one POST to `{NVIDIA_API_BASE or https://integrate.api.nvidia.com}/v1/chat/completions`. The body uses the bench prompt, `max_tokens` `256`, and `reasoning_effort` `none`. The timeout is 30 seconds. There is no retry and no second model.

A provider failure stores a row with `mode` null, `intensity` null, `parse_ok` false, and `error` `provider`. The detail uses the existing redaction: the key is stripped, newlines become spaces, and the text is capped at 180 characters. The receipt never contains the key, the Authorization header, or the image.

A 200 whose content is not a JSON object, or whose object fails the parse rules, stores `error` `parse`. Markdown fences are not stripped. A percent is not scaled. `Open` is not lowered. Accepted rows have `parse_ok` true and no error. The mode is one of `attractor`, `void`, `power`, `open`. The intensity is a JSON number from `0` to `1` inclusive. Extra keys are ignored.

The script writes all four rows when the posts have been attempted, including failed rows. Row order is `void`, `power`, `attractor`, `caller`. The write is a replace in the same directory, so a crash does not leave a partial file. Tests write to a temporary path. The repo path is created only by a person running the capture. Exit `0` only when all four rows parsed. Any failed row exits non-zero after the write. The script then prints the scorer report. That print is not a file. A preflight failure prints the reason and does not print a report.

## Receipt

Path: `fixtures/qa/vision_bench_capture.v1.json`.
The implementation does not create this file. A person creates it by running the capture. It may be committed later as evidence. The model id on that file is the id from that run.

Schema `psyfi.vision_bench_capture.v1`:

```json
{
  "schema": "psyfi.vision_bench_capture.v1",
  "date": "YYYY-MM-DD",
  "model": "nvidia/bench-test",
  "caller": { "mode": "open", "intensity": 0.7 },
  "prompt_revision": 1,
  "images": [
    {
      "id": "void",
      "mode": "void",
      "intensity": 0.5,
      "latency_ms": 0,
      "parse_ok": true
    }
  ]
}
```

`date` is the UTC calendar date of the capture. `model` is the environment id from that run. The example uses `nvidia/bench-test`, which is the fake id for tests, not a production model. `latency_ms` is the elapsed time of that one post, including a failed post. A failed row uses `"mode": null`, `"intensity": null`, `"parse_ok": false`, and `"error": "provider"` or `"parse"`, plus `"detail"`. The example shows one row and uses sample numbers. A real receipt has four rows, in the order above, and those numbers are not a measured run. The file has no match field.

## Report

The scorer prints schema `psyfi.vision_bench_report.v1`. The report is not committed.

For each image the report carries the oracle mode and intensity, the model's mode and intensity, `mode_match`, `intensity_match`, and `ok`. `mode_match` is exact string equality. `intensity_match` is an absolute gap of at most `0.05`. `ok` requires both, and requires `parse_ok`. The report is ok only when all four rows are ok. Latency is copied through and has no pass rule.

The scorer raises on a machinery failure: the schema is wrong, an id is missing or repeated, the caller mode is not `open`, the caller intensity is not `0.7` within `1e-9`, or `prompt_revision` is not `1`. A disagreement and a well-formed `parse_ok: false` do not raise.

## Testing

CI runs the new tests in the existing pytest job. No test opens a socket. No workflow is added.

1. Oracle lock. The four constructions return the four modes at caller `open` / `0.7`, and each image sits on the correct side of the cutoffs. Intensities are not pinned.
2. Scorer, using an in-memory receipt whose model id is `nvidia/bench-test`. A gap of `0.05` matches. A gap of `0.06` does not. A wrong mode does not match. `parse_ok: false` does not match and does not raise. The report is ok only when all four rows match. Bad schema, wrong caller, wrong revision, or a missing id raises.
3. Parse. A JSON object with one of the four names and a number from `0` to `1` is accepted. Prose, a percent, an unknown mode, `Open`, and a missing field are `parse_ok: false`. A provider detail that contains the key is redacted.
4. Preflight. An unset key, a non-`nvidia/` id, an `@cf/` id, or a broken oracle lock performs no post and does not replace an existing receipt.
5. Write. A finished run replaces the receipt, keeps failed rows, and exits non-zero when a row failed. A clean run exits zero. The file has no key, no image bytes, and no match field.
6. Committed receipt. The test skips when `fixtures/qa/vision_bench_capture.v1.json` is absent. When the file is present and well formed, the test scores it and does not require agreement. A wrong revision fails the build.
7. Caption contract. The existing image-reading tests stay. One new test asserts that the bench prompt and the caption prompt are different strings, and that the public router has no bench route.

No shell change, no service-worker bump, and no GPU fixture.

## Success

A person with `NVIDIA_API_KEY` and `NVIDIA_VISION_MODEL` set can run `scripts/capture_vision_bench.py` and read a receipt plus a printed report. CI is green with no key and with no receipt file. A later change to the recommendation formula fails the oracle-lock test until the corpus or the formula is updated on purpose.
