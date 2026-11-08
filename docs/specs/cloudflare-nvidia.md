# Spec: Cloudflare and NVIDIA

Status: implemented. Pull request #24 is merged. The provider call runs off the event loop, a body timeout is one provider error, and staging refuses a missing GPU lab build. Do not pin a model id or commit a key.
Seam: the public Worker, static assets, the Python Container, and the NVIDIA API call.

## Problem Statement

The operator needs the instrument on Cloudflare, and needs a reading of the picture they upload. The picture today contributes only photometric numbers: mean color, energy, contrast, edge density, warmth, and size. Those numbers cannot say what the picture shows. The planner and the export prompt already say what the field is doing, in deterministic text. A text-only model cannot see the upload. The operator has an NVIDIA API key. Production has to use that key, on Cloudflare, without becoming a second source of truth for the field.

## Solution

Production is one public hostname: a Cloudflare Worker. The shell and the GPU lab are Workers Static Assets. The Python API runs as a Cloudflare Container from the existing image, reachable only through the Worker. Docker Compose stays the local seam.

The only model class is a vision-language model hosted on the operator's NVIDIA API. It reads the resized source image when the operator asks for a reading, and returns a short inferred caption. The caption is labeled inferred, says it is not medical advice, and is rendered as text. The master seed, the hints, the recipe rank, the planner text, the journey prompt, and the safety caps stay exactly the functions they are today.

## User Stories

1. As an operator, I want the instrument served from one Cloudflare hostname, so that the shell, the lab, and the API share one origin.
2. As an operator, I want the shell and `/gpu/` as static assets on that hostname, so that the picture still renders on my own GPU.
3. As an operator, I want the Python field to keep running as Python, so that the simulation I already trust does not get rewritten into a Worker.
4. As an operator, I want local Compose to keep booting the same image, so that I can check the instrument without a Cloudflare account.
5. As an operator, I want a reading of the picture I uploaded, so that the instrument can say what the picture shows.
6. As an operator, I want that reading to look at my picture before the recipe tints it, so that the caption describes the upload.
7. As an operator, I want the reading marked inferred, so that I can tell it from the field.
8. As an operator, I want the reading to say it is not medical advice, so that a caption cannot present itself as care.
9. As an operator, I want the reading shown as text, so that a caption cannot change the page.
10. As an operator, I want the seed, the hints, and the recipe rank to ignore the reading, so that the same image and settings still yield the same field.
11. As an operator, I want a seed when I do not ask for a reading, so that Pass 1 works with the model unset.
12. As an operator, I want a failed or unconfigured reading to leave the seed intact, so that NVIDIA being down does not blank the instrument.
13. As an operator, I want my picture sent only for the reading I asked for, so that an ordinary seed does not leave the process.
14. As an operator, I want the picture forgotten after the call, so that the upload is still memory-only.
15. As an operator, I want the planner text I already have, so that motifs and lighting stay a deterministic reading of the field.
16. As an operator, I want the journey prompt to stay a sidecar I paste elsewhere, so that the instrument does not generate a video.
17. As a maintainer, I want the NVIDIA key only in the Worker secret, so that git, the image, Compose, and the browser never hold it.
18. As a maintainer, I want the model id in config, so that changing the catalog id does not require a commit and does not hide a key.
19. As a maintainer, I want that id to be an NVIDIA-authored vision-language model, so that a text model, or another vendor's model on the same host, cannot accept the call.
20. As a maintainer, I want a non-vision or non-NVIDIA id to fail the reading, so that the call does not continue on a substitute.
21. As a maintainer, I want an empty API base to call `https://integrate.api.nvidia.com` directly, so that the public host does not depend on a gateway that was not built.
22. As a maintainer, I want an AI Gateway left undecided, so that nobody adds one while that question is open.
23. As a maintainer, I want the reading route to be additive under the current freeze id, so that existing clients keep their payloads.
24. As a maintainer, I want production config to name the vision model, so that a deploy that cannot read an image is incomplete.
25. As a maintainer, I want the copied Noema workflow left out of this host, so that this instrument does not deploy that product.
26. As an operator, I want `https://psy-fi.space` served only by Worker `psy-fi`, so that the bought name is not attached to the older workers.dev script.
27. As an operator, I want workers.dev and preview URLs off on that Worker, so that the public name is the only hostname.
28. As an operator, I want `www` left off, so that a second hostname is not part of this host.
29. As a maintainer, I want a later deploy to keep the vision-model var, so that a deploy does not delete it.
30. As an operator, I want the older `psyfi` script left in place, so that this host does not delete the previous deploy.

## Implementation Decisions

### Model classes

The surfaces were checked against the model classes a NVIDIA account can call. One class is required.

| Surface | What it already does | Model class |
| --- | --- | --- |
| Image-seed upload | Photometric features, then a conditioned seed. No semantic description. | Vision-language model. This is the required class. |
| Recipe recommendation | Ranks the catalog from those photometric features. | None. A model rank would replace a deterministic score. |
| Planner | Template text from the ParameterField, motifs, lighting, anchors, and notes. | None. The vision caption is a separate field. |
| Export journey | A `prompt_only` sidecar. The package says the instrument does not call a provider. | None. No image model and no video model. |
| Client stills | Pictures the browser already rendered from the field. | None. The planner already describes that field. |
| Scene snapshot and the GPU lab | ParameterField in, WebGPU picture out, safety clamp on the client. | None. |
| Simulation, jobs, metrics | Seeded Python. | None. |
| MIDI | Host control. | None. No speech and no audio model. |
| Telemetry | Optional in-process events. | None. |
| Live sensors | Camera, motion, audio, and haptics modulate the ParameterField only. | None. |
| Substance presets | Authored registry. A distill step can copy a visual signature from recipe averages. | None. Firecrawl is not a preset source. |

A vision-language model already returns text. A second, text-only model is not required. Embeddings, rerankers, speech, audio, image generation, video generation, and a content-safety classifier have no surface.

Substance presets stay the authored registry. The catalog is 70 recipes: 44 authored seeds and 26 derived from 28 local reports by eight keyword channels (geometry, entities, color and light, space and void, body, time, nature, machines). Those channels are what reach a preset visual signature. Crawling more full reports would feed that same count. Ongoing Erowid collection needs their written permission, and the product already refuses to republish full reports. The Image Reading does not write back into the preset registry or the catalog.

### Host

- The Worker is the only public hostname. It routes `/api/` and `/simulate/` to the Container and serves the shell and the GPU build as static assets.
- The Container runs the existing image. Python, NumPy, SciPy, Pillow, and the MIDI library stay there. They do not move into the Worker isolate.
- The Container is not a second public origin.
- Compose remains the local seam. The Compose NVIDIA profile still means a host GPU reservation for that local image. It is not this API call.
- The Noema workflow is the wrong product and stays out.

### Call

- Provider base URL is `https://integrate.api.nvidia.com`. The chat path is `/v1/chat/completions`. Auth is a bearer token. The browser never calls that host.
- The accepted public host is Worker `psy-fi` at `https://psy-fi.space`. `workers.dev` and preview URLs are off. `www` is not a hostname. The older Worker `psyfi` stays a separate script and does not receive this domain. Worker source stays under the existing `workers/psyfi` path. That directory name is not the script name.
- `NVIDIA_API_BASE` stays empty on this host, so the call goes directly to the integrate host. An AI Gateway custom provider was an earlier idea. It is not part of this host. Do not add one unless a later accepted intent says so.
- The NVIDIA key is the Cloudflare secret `NVIDIA_API_KEY` on Worker `psy-fi`. The repo, the image, Compose, the client bundle, and this spec do not hold it.
- `NVIDIA_VISION_MODEL` is the model id. It is config, not a secret. It is chosen from the account's live catalog at deploy. The repo does not pin an id.
- The id has to be NVIDIA-authored on that host (the `nvidia/` namespace) and vision-capable. The integrate host also serves other vendors' ids under the same key. Those ids are a failed config.
- Workers AI `@cf/nvidia/nemotron-3-120b-a12b` is text-only and is scheduled to return HTTP 410 on 2026-11-20. It cannot satisfy this spec. A missing vision model is not repaired by substituting another vendor's model.
- The reading request uses a chat content array: one text part, one `image_url` part whose URL is a `data:` image of the resized source. It sets `reasoning_effort` to `none` so a reasoning model spends the token cap on the caption. The upload is not given a public URL. The repo still does not pin the model id.
- The bytes are the source image after the existing size ceiling and after the longest edge is brought down to 384, before the recipe conditions the pixels. WebP and other decoded types are re-encoded to PNG or JPEG for that part. The raw oversized body is not sent.
- The reading route is additive: `POST /api/v1/visualize/image-reading`. Existing image-seed responses stay as they are when the client does not ask. The seed route does not call NVIDIA.
- The response carries the caption, the model id, an inferred label, and the not-medical-advice sentence. It does not carry the key. It is not hashed into the field, the planner, or a golden.
- If the model is unset, the id fails the namespace or vision check, or the provider errors, the reading returns a visible error and no other model is tried. The seed path still returns.
- Completion length is capped. The shell truncates the caption before display and assigns it as text.
- This host does not add a rate limit or a cache. The route is one attempt. A provider error is returned once.
- Telemetry does not record image bytes, the caption, or the key.
- Production config names `NVIDIA_VISION_MODEL`. Local and CI leave it unset and make no network call.

## Testing Decisions

A good test calls the public route with the model unset, or with a stub transport, and asserts the body. It does not call the live NVIDIA API and it does not snapshot a caption.

- Image-seed determinism tests stay the prior art for the seed. A reading must be absent from the master seed, the hints, and the recipe score.
- With the model unset, the reading route returns a config error and opens no socket. The seed route still returns the same payload it returns today.
- A stub transport that receives an image part proves the outbound body is the resized source, a data image, and an `nvidia/` model id. A stub that returns a modality error proves the route surfaces that error and does not retry.
- A config check rejects an id outside the `nvidia/` namespace, a Workers AI `@cf/` id, and an empty id.
- A search of the client bundle, the static shell, Compose, and the docs asserts that no `nvapi-` value and no assigned NVIDIA key are present.
- Planner and journey goldens stay valid without a model response in them.

## Out of Scope

- Pinning a model id in the repo.
- A text-only model, an embedding model, a reranker, speech, audio, image generation, video generation, or a content-safety classifier.
- Letting the reading change the master seed, the hints, the recipe rank, `planner_text`, the journey sidecar, the scene snapshot, or the safety clamp.
- Sending client stills, scene snapshots, MIDI, telemetry, or sensor streams to a model.
- Caching image requests.
- Medical or diagnostic claims about the person in the picture.
- Accounts, and a shared store of readings.
- The host CUDA profile, and running NVIDIA inference inside the API container's GPU.
- Native mobile, Azure, Render, and the existing Pages workflow.
- Recreating the removed Noema deploy workflow.
- Catalog reload. Whether that helper is named or removed is undecided.
- Rebuilding the phenomenology corpus with Firecrawl, or any other fetch of third-party reports.
- Writing an Image Reading, a crawl, or a motif score back into the substance preset registry.

## Further Notes

The image-seed decision already refuses a generative model inside the seed. That refusal stands. This spec adds a caption beside the seed. The two disagree only if a later change writes the caption into the field hash.

The grounding plan allows an optional later language-model path behind an explicit flag, and it keeps the planner deterministic. The flag this spec adds is the image reading. The planner stays the template.

The audit on `7ca678e0` found no Worker. That pass is historical. The Call section above is the current decision: direct integrate on Worker `psy-fi`, issue #36, pull request #39. An AI Gateway is an open question, not an agent task.
