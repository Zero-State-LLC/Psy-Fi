# Open questions — register

Researched: 2026-11-08, against `main` at `d81483f` and pull requests #59, #60, #64, #65 and #66, which were open then and merged the same day (`main` `460e891`). Prices and terms were rechecked the same day against official sources where they exist.

This register collects every open question from `intent.md`, `intent/*.md`, `HANDOFF.md` §4, ADR 0011 and the tracker in one place. Each entry gives the evidence and a recommendation. A recommendation is not a decision. Where an entry says "Decides: operator", nothing changes until a human says so in an accepted intent or in the issue. When a question is settled, mark it in its source document and here.

## Summary

| # | Question | Status | Decides |
| --- | --- | --- | --- |
| 1 | [AI Gateway for production vision](#1-ai-gateway-for-production-vision) | Open. Recommend later, not now | Operator |
| 2 | [Catalog reload](#2-catalog-reload) | Open. Recommend keep under this freeze | Operator |
| 3 | [Hardware Ultra evidence (#10)](#3-hardware-ultra-evidence-10) | Open. Needs a physical desktop | Operator, with hardware |
| 4 | [Vision-bench receipt and #49](#4-vision-bench-receipt-and-49) | Open. Needs a person with the key: about 4 posts, then 28 (smoke) or 242 (full) | Operator |
| 5 | [FieldLoop run endpoint (#54)](#5-fieldloop-run-endpoint-54) | Open. Recommend no | Operator |
| 6 | [Discrete GPU, CUDA and power evidence (#48, #53, #50)](#6-discrete-gpu-cuda-and-power-evidence-48-53-50) | Open. Needs a cloud account | Operator |
| 7 | [Per-frame energy (ADR 0011)](#7-per-frame-energy-adr-0011) | Answered. Accepted and built; a real NVIDIA run is entry 6 | — |
| 8 | [Publishing results on psy-fi.space](#8-publishing-results-on-psy-fispace) | Open. Recommend not yet | Operator |
| 9 | [Read-only scorecard endpoint](#9-read-only-scorecard-endpoint) | Open. Tied to 8 | Operator, Fable |
| 10 | [README linter advisories](#10-readme-linter-advisories) | Answered. Switched to `remark-cli` | — |
| 16 | [NVIDIA API terms for the live image reading](#16-nvidia-api-terms-for-the-live-image-reading) | Open. Check before relying on it | Operator |
| 11 | [WGSL kernel worth validating](#11-answered-wgsl-kernel-worth-validating) | Answered (#60) | — |
| 12 | [Where FieldLoop results live](#12-answered-where-fieldloop-results-live) | Answered (#65) | — |
| 13 | [GPU frame-time bench](#13-answered-gpu-frame-time-bench) | Answered (#56) | — |
| 14 | [`design.md` front-page amendment](#14-answered-designmd-front-page-amendment) | Answered (#44) | — |
| 15 | [Refreshing the front-page captures](#15-answered-for-now-refreshing-the-front-page-captures) | Answered for now | — |

## 1. AI Gateway for production vision

Asked in: `intent.md` open questions, `HANDOFF.md` §3 and §4, `docs/specs/cloudflare-nvidia.md` (Call).

**Found.**
- **Support:** NVIDIA is not a native AI Gateway provider. It works as a custom provider with `base_url` `https://integrate.api.nvidia.com`, at `https://gateway.ai.cloudflare.com/v1/<account>/<gateway>/custom-<slug>/v1/chat/completions`.
- **Code impact:** the code already reads `NVIDIA_API_BASE`, and `route.mjs` already forwards it, so the switch is mostly configuration. It would add one gateway token (`cf-aig-authorization`) to send and to redact.
- **Privacy:**
  - logging is on by default and can store request bodies, which would include users' uploaded images;
  - `cf-aig-collect-log-payload: false` keeps metadata only;
  - caching is exact-match on the whole body, so unique uploads never hit;
  - the gateway's retries and fallbacks contradict the code's "post at most once" rule.
- **Cost:** core features are free.
- **Sources:**
  - <https://developers.cloudflare.com/ai-gateway/configuration/custom-providers/>
  - <https://developers.cloudflare.com/ai-gateway/observability/logging/>
  - <https://developers.cloudflare.com/ai-gateway/configuration/caching/>
  - <https://developers.cloudflare.com/ai-gateway/reference/pricing/>

**Recommend.** Later, not now. The gain is usage and cost visibility for a low-volume feature, and the default setup would log user images. If you adopt it:
- an authenticated gateway;
- payload logging off;
- caching off;
- no retries or fallbacks;
- `NVIDIA_API_BASE` set to the gateway URL;
- the gateway token added to the redaction in `_safe_provider_message`.

**Checked later.** A request can carry both the provider's `Authorization: Bearer` and `cf-aig-authorization`; the OpenAI provider page shows the pair (<https://developers.cloudflare.com/ai-gateway/usage/providers/openai/>). Cloudflare publishes no figure for the gateway's own added latency; it gives one only for guardrails, about 500 ms.

**Not verified:** latency overhead; whether a Worker binding can reach a custom provider.

## 2. Catalog reload

Asked in: `intent.md`, `HANDOFF.md` §4, `docs/specs/api-v1.md`, `docs/specs/AUDIT.md`.

**Found.**
- **The route:** `POST /api/v1/experiences/reload-catalog` (`psyfi_api/routers/experiences.py`) clears the catalog cache, rereads it from disk, and returns `status`, `recipe_count` and the catalog's filesystem `path`.
- **The freeze:** the route is in the frozen `openapi.v1.json`. `API_V1_FREEZE.md` forbids rename or removal under freeze id `psyfi-api-v1-hard-2026-07-25`; that needs a new API version or freeze id.
- **Exposure:** on psy-fi.space every `/api/*` path reaches the container, so the route is public and unauthenticated. The catalog is baked into the image, so a reload only costs a little CPU and discloses the container path.
- **Tests:** none exercise it.

**Recommend.** Keep it under this freeze. Name it in the `api-v1.md` route inventory as a dev helper. At the next freeze id, either drop `path` from the response or gate the route behind an operator-only flag.

## 3. Hardware Ultra evidence (#10)

Asked in: `intent.md`, `HANDOFF.md` §4, issue #10 (no activity since 2026-10-06).

**Found.**
- **What "Ultra" means:** `docs/DESKTOP_GPU.md` defines it as a consumer RTX, RX or Arc card on physical silicon.
- **Cloud VMs:**
  - Passthrough datacenter GPUs (AWS g4dn T4, g5 A10G) are discrete, but they're not the parts "Ultra" names.
  - Remote display caps `requestAnimationFrame` at the virtual display's refresh, often 30–60 Hz, below the 8.3 ms Ultra budget.
  - vGPU slices (for example Azure NVadsA10) are time-sliced and are not valid evidence.
- **Apple results:** never Ultra evidence (`docs/bench/MEASUREMENTS.md`).

**Recommend.** Keep it in Backlog. Close it only on a physical consumer desktop with a high-refresh monitor, such as a borrowed gaming PC. A cloud VM can feed #48, but it can't close #10.

## 4. Vision-bench receipt and #49

Asked in: `intent.md`, `HANDOFF.md` §4, issue #49.

**Found.**
- **The vision-bench receipt** (`docs/specs/vision-bench.md`): one local capture of 4 fixed 64×64 images, about 4 posts, plus the oracle check that runs before any post.
- **#49, the full `interpretation.fieldread` workload:**
  - its corpus is 4 substances × 4 modes × 3 intensities × 2 seeds = 96 images;
  - every image is read twice, once as an image read and once as a structured read;
  - 4 perturbations over 8 images and 3 repeats over 6 images come on top;
  - so a successful run is 96 + 96 + 32 + 18 = **242 posts** at `max_tokens` 64 (`run_interpretation` in `psyfi_bench/families/interpretation.py`).
- **The smoke workload, `interpretation.fieldread.smoke`:** 8 images, so 8 + 8 + 8 + 4 = **28 posts**.
- **Offline runs:** CPU-only providers already run both workloads offline (`--provider heuristic`, `oracle`).
- **Both:** they spend the NVIDIA key and must be run by a person.

**Recommend.** Do it in one sitting on the operator's machine, with the live vision-model id.
- Run the vision-bench receipt first (about 4 posts) and commit it as the spec describes.
- Then run the smoke workload (28 posts) for #49, before the full one (242 posts). The workload stops after 3 consecutive provider errors (`abort_after_consecutive_errors`), which bounds a failing run.
- Keep each #49 result as a sealed result file.
- Pace the posts. Users of the hosted API report a default of 1,000 credits and 40 requests per minute; NVIDIA publishes no number and says limits vary per model. At 40 per minute, the full run takes at least 6 minutes.
- Never print the key or the model id.

## 5. FieldLoop run endpoint (#54)

Asked in: `intent/benchmark-platform.md`, issue #54, ADR 0009.

**Found.**
- **Today:** benchmarks run only through the CLI, and `run_enabled` is false. Ingest is off unless `PSYFI_BENCH_INGEST=1`.
- **On the public host,** a run endpoint would turn compute into something anyone can trigger.
- **Existing controls:**
  - the only throttle is the simulation slot cap (`#18`);
  - there is no login or rate limit, and `HANDOFF.md` §3 forbids adding them.

**Recommend.** No for psy-fi.space. If an operator wants a button for local runs later, gate it the way ingest is gated, with an env flag that is off by default. Never call providers from the server.

## 6. Discrete GPU, CUDA and power evidence (#48, #53, #50)

Asked in: issues #48, #53 and #50, and the part of #50 that #59 left open.

**Found.**
- **#53 and #50:** any rented NVIDIA Linux GPU, for example RunPod, vast.ai, Colab or an AWS g4dn Linux box, runs `--backend torch-cuda` in minutes. Check that `nvidia-smi --query-gpu=power.draw.instant` returns a number before paying; vGPU slices return "Not Supported".
- **#48:**
  - Chrome on a Windows AWS g4dn or g5 instance with the NVIDIA gaming or GRID driver is the closest honest setup. It is passthrough and uses D3D12 by default.
  - Linux needs Vulkan flags (`--use-angle=vulkan --enable-features=Vulkan --enable-unsafe-webgpu`), and headless runs have no vsync.
  - Record the refresh rate, the adapter string from `chrome://gpu`, and whether `timestamp-query` was available.
  - Label the result "discrete, datacenter, remote-displayed".
- **AMD and Intel Arc:** there is no realistic hourly cloud option.
- **Sources:**
  - <https://developer.chrome.com/blog/supercharge-web-ai-testing>
  - <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/nvidia-GRID-driver.html>
  - <https://docs.nvidia.com/vgpu/latest/grid-management-sdk-user-guide/manage-vgpus-guest-vm-sdk.html>
- **Prices** (checked 2026-11-08):
  - AWS us-east-1 on-demand, from AWS's public price feed dated 2026-11-07: g4dn.xlarge (T4) $0.526/h Linux, $0.71/h Windows; g5.xlarge (A10G) $1.006/h Linux, $1.19/h Windows.
  - The default quota for "Running On-Demand G and VT instances" is 0, so a new AWS account must request an increase first (<https://docs.aws.amazon.com/ec2/latest/instancetypes/ec2-instance-quotas.html>).
  - RunPod RTX 4090 $0.89/h and L4 $0.59/h (<https://www.runpod.io/pricing>); vast.ai RTX 4090 median $0.47/h and L4 median $0.32/h (<https://vast.ai/pricing>, live marketplace).
  - GitHub's Linux T4 GPU runner costs $0.052 per minute and needs GitHub Team or Enterprise Cloud (<https://docs.github.com/en/billing/reference/actions-runner-pricing>).
  - Not verified on any of these: whether `nvidia-smi` reports `power.draw.instant`.
  - So #53 plus #50 is well under $1 of GPU time, and #48 is a few dollars of g4dn Windows time, plus setup.

**Recommend.** Run #53 and #50 together on a rented Linux NVIDIA box first, since it is cheap and needs no browser. Run #48 on Windows AWS g4dn or g5 with RDP or DCV. Leave the AMD and Arc rows unmeasured.

## 7. Per-frame energy (ADR 0011)

Asked in: ADR 0011 (proposed, merged with #59) and issue #50.

**Found.**
- **What `nvidia-smi` reports:**
  - on Ampere and newer, `power.draw` is the average over the last second;
  - `power.draw.instant` is a short window (25 ms on A100 and H100);
  - the board sensor updates about every 100 ms and samples about 25% of runtime on A100 and H100 (Yang et al., [arXiv:2312.02741](https://arxiv.org/html/2312.02741v2)).
- **What `main` does now** (from #59, commit `1310971`):
  - one `nvidia-smi -lms 100` process reading the instant field;
  - each reading stamped with `nvidia-smi`'s own time;
  - per-unit energy only for stages of at least 1 s.
- **Status of the ADR's three questions:** that settles the interval. The host-match and API-ingest questions remain.

**Recommend.**
- **Host match:** strict, the same `hostname_hash`. Wall-clock alignment only holds on the same machine.
- **Trace:** CLI only, since ingest is off on the public host anyway.
- **Then:** accept the ADR, and the build is a clear agent slice.

**Answered** by the operator on 2026-11-08 ("permission granted where required, continue"): accepted as recommended, with a strict `hostname_hash` match and a CLI-only trace. `psyfi-bench power-trace` and `psyfi-bench ingest --power-trace` implement it. It has run only against synthetic captures and a fake `nvidia-smi`; a real run needs the NVIDIA host in entry 6.

## 8. Publishing results on psy-fi.space

Asked in: `intent/bench-results-page.md` (#65).

**Found.**
- The live container has no results store contents, and run and ingest are off, so `/bench` on psy-fi.space shows the empty state (checked after version `94e47554`, 2026-11-08).
- The only results that exist are integrated-class Apple runs, which are never Ultra evidence.
- Ultra and high WebGPU stages on the M5 were not measured because of #55, which is now fixed and live.

**Recommend.** Not yet. First:
1. Re-run the WebGPU tiers capture on a Mac now that #55 is fixed, to get valid ultra and high stages, labelled integrated.
2. Get one discrete capture (entry 6).

Then publish a small curated set as a static, labelled JSON bundle. That needs no API change and keeps the non-claim on every number.

## 9. Read-only scorecard endpoint

Asked in: `intent/bench-results-page.md` (#65).

**Found.**
- `psyfi_bench.scoring.build_scorecard` exists.
- A `GET /api/bench/v1/scorecard?run_id=…` endpoint would be small, read-only and additive, but it changes Fable's bench API contract and its exported OpenAPI.
- For the local operator, `psyfi-bench score --out` plus the file picker on `/bench` already works.

**Recommend.** Add it only if entry 8 publishes results and the public page should compare runs. Otherwise keep the file flow.

## 10. README linter advisories

Asked in: #66 (merged) and `npm audit`.

**Found.**
- **Remaining findings:** after #66, `npm audit` reports 5 high findings, all from one advisory: `parse-git-config` GHSA-8g77-54rh-46hx. The other 4 packages are flagged only because they depend on it.
- **No fix:** no patched version exists; 3.0.0 is the latest on npm. So no `overrides` entry can fix it.
- **Unreachable in our use, for two reasons:**
  - the vulnerable `expandKeys()` runs only when a caller passes `{expandKeys: true}`, and `remote-origin-url` never does;
  - hallmark reads the repo URL from `package.json` `repository`, which is set, so it never parses `.git/config`.
- **Replacement option:** a `remark-cli` setup (`remark-gfm`, `remark-validate-links` and the same 25 `remark-lint-*` rules), plus the #66-style `glob`/`minimatch` override, gives a clean audit. It flags the same issues on README.md: the same 46 missing-file warnings at the same positions on an unstubbed copy. It drops `hallmark fix` and `remark-github` URL shortening.

**Checked later** (2026-11-08):
- **Upstream will not fix it soon.**
  - `parse-git-config` was last published in 2018. Its prototype-pollution issue (#14, January 2025) is open, and the fix PR (#15, March 2025) was never merged (<https://github.com/jonschlinkert/parse-git-config/issues/14>, <https://github.com/jonschlinkert/parse-git-config/pull/15>).
  - hallmark's last release is 5.0.2, from 2025-10-17, and no hallmark issue mentions the advisory.
  - The only fork on npm that claims a fix, `@keep-lts/parse-git-config`, was created and published in one day by a single anonymous maintainer, so it is not a safe override.
- **The swap is equivalent on the README.**
  - On the real `README.md` with all its real linked files, `npx hallmark lint README.md` and `npx remark README.md --frail --quiet --no-stdout` both exit 0 with no warnings.
  - With three planted defects, both report the same warnings at the same positions: a missing heading in another doc, an unpadded table row, and a `*` bullet.
  - The `remark-cli` setup audits clean, given the same `glob`/`minimatch` override as #66.
- **What a switch touches:**
  - `package.json`: devDependencies, `overrides`, the `test` and `markdown:lint` scripts, and the `hallmark` key;
  - a new `.remarkrc.mjs` with hallmark's rule settings;
  - deleting `.hallmarkrc`;
  - the README step in `.github/workflows/ci.yml`;
  - the assertion in `tests/test_ci_metadata.py` that pins `npx hallmark lint README.md`;
  - the mentions in `README.md`, `AGENTS.md`, `PROJECT_INDEX.md`, `docs/PRODUCTION_READINESS.md`, `docs/bench/DISCOVERY.md` and `docs/specs/AUDIT.md`.
- **What a switch loses:** `hallmark fix`, which has no one-to-one replacement. The unrelated Hallmark design skill under `.agents/skills/hallmark/` stays.

**Recommended.** Switch to `remark-cli`: checked as equivalent on the README, a clean `npm audit`, and upstream shows no sign of a fix.

**Answered** by the operator on 2026-11-08 ("permission granted where required, continue"): switched. `npm test` runs `remark README.md --frail --quiet --no-stdout` with `.remarkrc.mjs`, and `npm audit` reports 0 vulnerabilities. The scoped `glob` and `minimatch` overrides now also cover `unified-engine` and `@npmcli/package-json`. `hallmark fix` has no replacement; fix lint warnings by hand. The Hallmark design skill under `.agents/skills/hallmark/` is unrelated and stays.

## 16. NVIDIA API terms for the live image reading

Asked in: this register, found while checking the cost of entry 4.

**Found.**
- psy-fi.space's public image reading calls NVIDIA's hosted API at `integrate.api.nvidia.com`.
- An NVIDIA staff FAQ post says the free hosted endpoints come with the NVIDIA Developer Program and are licensed for research, development and testing. Production use needs NVIDIA AI Enterprise (90-day trial) or a partner host (<https://forums.developer.nvidia.com/t/nvidia-nim-faq/300317>).
- That is a forum post, not a docs page, and it may not match the account's current terms.

**Recommend.** Before relying on the feature, check the terms of the account the live key belongs to. If the free endpoints are dev and test only, choose one of these:
- keep the feature and present it as a research preview;
- move it to an NVIDIA AI Enterprise or partner-hosted endpoint, which `NVIDIA_API_BASE` already allows;
- switch it off on the public host.

## 11. Answered: WGSL kernel worth validating

Asked in: `intent/benchmark-platform.md`.

**Answered.** Yes. #60 implements it and validated it live on an Apple GPU: max abs error 7.2e-7 against a 1e-3 tolerance, GPU-timed through timestamp-query, scored `ok` with a valid seal. It is merged, and #51 is closed.

## 12. Answered: where FieldLoop results live

Asked in: `intent/benchmark-platform.md`, issue #52.

**Answered** by the operator on 2026-11-08: a shell page at `/bench`, for the local operator first. #65, merged, implements it (`intent/bench-results-page.md`); #52 is closed.

## 13. Answered: GPU frame-time bench

Asked in: `HANDOFF.md` §4.

**Answered.** The FieldLoop `render.webgpu.tiers` workload and `/gpu/bench.html` (#56, under the accepted FieldLoop intent) are that bench. Their scoring is separate from the vision bench's score, corpus and pass rule.

## 14. Answered: `design.md` front-page amendment

Asked in: `intent/shell-front-page-workbench.md`.

**Answered.** `design.md` carries the front-page line ("Front page below the fold: …") since #44.

## 15. Answered for now: refreshing the front-page captures

Asked in: `intent/shell-front-page-workbench.md`.

**Found.** The six captures come from the shell's WebGL path. Nothing in `psyfi_api/static/viz/`, `renderer.js` or `render_worker.js` has changed since they were taken in `db936eb`; #58 changed only the GPU lab.

**Answered.** No refresh is needed now. Refresh them when the shell renderer changes.
