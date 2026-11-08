# FieldLoop frontend integration package

Audience: Daniel. Date: 2026-11-07. Everything here is additive and versioned. Nothing requires a change to the shell, the GPU lab, or `/api/v1`.

## What exists

| Surface | Where | Contract |
| --- | --- | --- |
| Bench API (read) | `GET /api/bench/v1/...` | [`docs/contracts/bench/openapi.bench.v1.json`](../contracts/bench/openapi.bench.v1.json) |
| Interactive docs | `/api/bench/docs` | served by the sub-application |
| JSON schemas | [`docs/schemas/bench/`](../schemas/bench/) | `psyfi_bench_{manifest,result,gpu_capture,scorecard,capabilities}.v1.json` |
| Example documents | [`docs/contracts/bench/examples/`](../contracts/bench/examples/) | real runs from an integrated-class Mac plus one synthetic capture, all labelled |
| Browser runner | `/gpu/bench.html` | emits `psyfi.bench.gpu_capture.v1`; posts to `POST /api/bench/v1/captures` when ingest is on |
| CLI | `python3 -m psyfi_bench` | the only way to execute a workload |

The bench API is a mounted FastAPI sub-application. It has its own OpenAPI document and does not appear in `/openapi.json` of the main app, so the `/api/v1` hard freeze is unchanged.

## Endpoints

| Method and path | Returns | Notes |
| --- | --- | --- |
| `GET /api/bench/v1/capabilities` | `psyfi.bench.capabilities.v1` | families, workloads with `manifest_hash`, provider specs and whether their env is set, accelerators, environment, `ingest_enabled`, `run_enabled: false` |
| `GET /api/bench/v1/workloads?family=` | `psyfi.bench.workloads.v1` | list of manifest documents |
| `GET /api/bench/v1/workloads/{id}` | `psyfi.bench.manifest.v1` | `id` or `id@version`; 404 otherwise |
| `GET /api/bench/v1/results?family=&manifest_id=&limit=` | `psyfi.bench.index.v1` | newest first; each entry has `run_id`, `measurement_class`, `hardware_class`, `headline`, `path` |
| `GET /api/bench/v1/results/{run_id}` | `psyfi.bench.result.v1` | full sealed result |
| `GET /api/bench/v1/schemas` | `psyfi.bench.schema_index.v1` | schema file names |
| `GET /api/bench/v1/schemas/{name}` | JSON Schema draft-07 | |
| `POST /api/bench/v1/captures` | `psyfi.bench.ingest_receipt.v1` (201) | body is `psyfi.bench.gpu_capture.v1`; 403 unless `PSYFI_BENCH_INGEST=1`; 413 over 8 MB or 20,000 frames; 422 invalid; 409 unknown or non-render manifest |

### Error contract

Every error body is `psyfi.bench.error.v1`:

```json
{"schema": "psyfi.bench.error.v1", "error": {"code": "ingest_disabled", "message": "capture ingest is disabled on this host; download the capture and run `psyfi-bench ingest <file>`", "status": 403}}
```

Codes: `not_found`, `ingest_disabled`, `payload_too_large`, `invalid_capture`, `manifest_mismatch`, `error`.

### Example requests

```bash
curl -s http://localhost:8000/api/bench/v1/capabilities | python3 -m json.tool | head -40
curl -s 'http://localhost:8000/api/bench/v1/results?family=interpretation&limit=5'
curl -s http://localhost:8000/api/bench/v1/results/<run_id>
curl -s -X POST http://localhost:8000/api/bench/v1/captures -H 'Content-Type: application/json' --data @capture.json
```

Example responses are the files under `docs/contracts/bench/examples/`.

## Reading a result

`psyfi.bench.result.v1` fields a UI will want:

| Field | Meaning |
| --- | --- |
| `measurement_class` | `measured`, `synthetic`, `replay`. Show it next to every number. Synthetic and replay are never hardware or model evidence. |
| `status` | `complete`, `partial`, `failed` |
| `manifest.id`, `manifest.version`, `manifest_hash` | what ran; compare only equal hashes |
| `environment.hardware_class`, `environment.cpu.brand`, `environment.gpus[].name`, `environment.browser.adapter_classified` | where it ran |
| `environment.unavailable` | telemetry that was not collected and why (show, do not hide) |
| `stages[].statistics.wall_ms` (or `frame_ms`, `latency_ms`, `end_to_end_ms`) | `n, mean, median, p50, p90, p95, p99, cv, mad, ci95_mean, ci95_median` |
| `stages[].metrics` | family-specific; see below |
| `metrics` | headline per family |
| `failures[]` | `stage`, `category` (`timeout`, `cancelled`, `provider`, `parse`, `validation`, `resource`, `unsupported`, `internal`), `detail` |
| `result_hash` | seal over everything else; `psyfi-bench validate` checks it |
| `non_claim` | print it on any public page |

Headline metrics by family:

| Family | Keys |
| --- | --- |
| `field_compute` | `peak_cell_steps_per_s`, `scaling.exponent`, `scaling.r2`, `determinism.all_bitwise_identical_across_repeats`, `determinism.reference_matches`, `sustained.slope_ms_per_1000_frames` |
| `render` (soft) | `per_tier[tier].raster_ms_per_megapixel_median`, `cross_language_parity.matched/compared` |
| `render` (webgpu) | `adapter`, `per_tier[tier].fps_avg_median`, `.fps_1pct_low_median`, `.frame_ms_p95_median`, `.budget_ok_all`, `.ssim_vs_ultra_mean`, `sustained`, `warning` when not measured |
| `interpretation` | `fde_mean`, `within_mode_step_rate`, `mode_accuracy`, `parse_rate`, `tasks.image_read.*`, `tasks.structured_read.cross_modal`, `tasks.perturbation.invariance`, `tasks.repeatability.repeatability`, `provider`, `locality` |
| `fieldloop` | `e2e_ms_median`, `fde_median`, `within_mode_step_rate`, `closed/cases`, `stage_share_of_e2e_mean` |

## Browser runner

`/gpu/bench.html` is a separate page in the GPU package. It reuses `PsyFiGPUCanvas` and `SceneRoot` unchanged and adds a probe inside the canvas. Flow: fetch the manifest from `/api/bench/v1/workloads/render.webgpu.tiers` (falls back to a built-in copy), fetch a scene snapshot per stage from `POST /api/v1/visualize/scene-snapshot`, render warm-up plus N frames per stage, take a 128 px thumbnail, then one sustained stage. The page offers Download capture and Post to `/api/bench`. The quick numbers on the page are a sanity check; Python scores the capture.

If you want a link from the GPU lab header or the shell, the URL is `/gpu/bench.html`. That link is yours to add; this package does not touch your components.

## Scorecards

`psyfi-bench score a.json b.json --labels a,b --out card.json` writes `psyfi.bench.scorecard.v1`: `subjects[]`, `dimensions[name][label] = {value, unit, better, ci95, source, missing_reason}`, `composites[label][name] = {formula, inputs, value, sensitivity, missing_data_rule, valid_comparison}`, `validity.comparable` with `reasons`, `recommendations[]`. A UI should refuse to rank when `validity.comparable` is false and should render `missing_reason` instead of a blank.

## Capability metadata

`capabilities.providers[]` says which provider specs are available on the host (`available` is true only when the required env is set; the key itself is never returned). `capabilities.accelerators` lists `numpy: true` and whether `torch` imports. `capabilities.workloads[]` carries each manifest hash so a page can tell whether a stored result matches the current workload.

## Compatibility and migration notes

- `/api/v1` is unchanged. The frozen pack and its tests are untouched.
- `psyfi_api.simulation_service` still exports `run_simulation` and `PresetNotFoundError`; the implementation lives in `psyfi_core.simulation`.
- `packages/psyfi-gpu-renderer/vite.config.ts` gained one rollup input for `bench.html`. `npm run gpu:build` emits both pages into `dist/`, which FastAPI already mounts at `/gpu/`.
- The service worker does not precache `/gpu/bench.html`; it is network-first like the rest of `/gpu/`.
- Nothing here writes to IndexedDB, the shell, or `sw.js`.
- Future additive fields will keep the `v1` schema ids; a breaking change will mint `v2` ids beside them.
