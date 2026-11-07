# Spec: Image seed

Status: ready-for-agent. The remaining gap is GitHub issue #17. This file stays the decision record. Do not rebuild Pass 1.
Seam: `build_image_seed` and the image-seed HTTP routes.

## Problem Statement

The operator wants a picture they already have to influence the instrument. The picture must not become a second source of truth, must not be kept on the server, and must not skip the safety caps that apply to every other field.

## Solution

Pass 1 conditions the upload with the experience recipe and returns a master seed, hints, and an optional luminance plane. Pass 2 feeds those into the ParameterField. The raw upload is memory-only. A conditioned PNG may ride along as an ephemeral data URL for tint. Recommend-before-condition can rank recipes without rewriting pixels. The one-shot journey route refuses recommend-only, because a journey needs a conditioned seed.

## User Stories

1. As an operator, I want to upload a PNG or JPEG, so that the instrument can derive a seed from it.
2. As an operator, I want a JSON base64 alternate, so that a client without multipart can send the same request.
3. As an operator, I want the same image and settings to yield the same master seed, so that the pass is reproducible.
4. As an operator, I want the conditioned image kept to a maximum edge of 384, so that a large photo does not become the working field.
5. As an operator, I want an empty upload rejected, so that a blank request fails clearly.
6. As an operator, I want an oversized upload rejected, so that the process does not hold an unbounded body.
7. As an operator, I want the server to forget the raw bytes after the response, so that my image is not a stored asset.
8. As an operator, I want a recommendation of recipes from image features, so that I can see a match before conditioning.
9. As an operator, I want recommend-only to skip pixel conditioning, so that a suggestion is cheap.
10. As an operator, I want apply-recommended to set the applied experience, mode, and capped intensity, so that the suggestion I accept is the one that runs.
11. As an operator, I want the top alternatives listed, so that I can pick another recipe.
12. As an operator, I want influence to change the conditioned pixels, so that the control is real.
13. As an operator, I want hints to modulate the live field and still respect caps, so that the image cannot bypass safety.
14. As an operator, I want optional place-and-time anchors echoed on the seed, so that Pass 1 and the planner share them.
15. As an operator, I want one call that conditions, builds a timeline, and returns an export-journey package, so that I do not chain three requests by hand.
16. As an operator, I want that one-shot call to reject recommend-only, so that a journey is never built from an unconditioned suggestion.
17. As an operator, I want a decode failure reported as a client error, so that a bad file is not a server fault.

## Implementation Decisions

- Accepted types are the images the decoder can turn into RGBA. The working copy is resized so its longest edge is at most 384. Preview and texture edges are smaller.
- A byte-size ceiling rejects very large payloads before the response is built.
- Master seed is a hash of the conditioned bytes.
- `apply_recommended` and `recommend_only` ignore the client's experience id and use the catalog pick.
- Conditioned PNG on a scene snapshot is tint, not authority.
- No provider is called for the export package. Stills, when present, are client-supplied.

## Testing Decisions

A good test uses a tiny fixture image, calls the builder or the route, and asserts the seed, the applied experience, or the rejection. It does not snapshot the whole pixel buffer unless a golden already exists for that purpose.

Prior art: image-seed determinism, multipart and JSON route tests, recommend-only, journey rejection, and anchor echo tests.

## Out of Scope

- Persistent user media.
- A generative model that paints or replaces the field. An inferred reading of the upload is specified in [Cloudflare and NVIDIA](cloudflare-nvidia.md). It does not enter this seed.
- Medical reading of the uploaded image.

## Further Notes

The byte ceiling is applied after the multipart body is read into memory, and the full decoded raster is allocated before the 384-edge resize. The decision is a bounded upload and a bounded working image. The audit records the gap between that decision and the current order of operations.
