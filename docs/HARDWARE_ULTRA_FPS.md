# Hardware Ultra FPS Capture

Status: **harness ready** — run on a discrete desktop; CI keeps synthetic stand-in until samples are merged  
Related: [`bench/DISCRETE_GPU_HANDOFF.md`](bench/DISCRETE_GPU_HANDOFF.md), [`DESKTOP_GPU.md`](DESKTOP_GPU.md), [`SIMULATED_ULTRA_QA.md`](SIMULATED_ULTRA_QA.md), [`CONTINUATION_PLAN.md`](CONTINUATION_PLAN.md)

## Goal

Replace synthetic Ultra fps matrix rows with **measured** samples from a real discrete GPU (NVIDIA / AMD / Intel / Apple Pro-Max).

## Quick path (your dGPU)

1. Force Chrome/Edge onto the **discrete** GPU (Windows Graphics settings or vendor panel).
2. Confirm `chrome://gpu` → WebGPU **Hardware accelerated**.
3. Start PsyFi and open the capture URL:

   ```bash
   python3 scripts/run_dev_server.py
   # Chrome/Edge →
   open "http://localhost:8000/gpu/?measure_fps=1&tier=ultra"
   ```

   Or click **Measure Ultra fps** in the `/gpu/` header.

4. Keep the tab focused ~3s (60 warm-up + 180 sample frames). A JSON download starts automatically.
5. Merge into the hardware fixture:

   ```bash
   python3 scripts/merge_ultra_fps_measured.py ~/Downloads/psyfi-ultra-fps-*.json
   # Optional: also promote that id inside the CI synthetic matrix
   python3 scripts/merge_ultra_fps_measured.py ~/Downloads/psyfi-ultra-fps-*.json --promote-synthetic
   ```

6. Verify:

   ```bash
   npm run gpu:test
   ```

7. Update [`BROWSER_CAPABILITY_MATRIX.md`](BROWSER_CAPABILITY_MATRIX.md) Notes from “hardware fps TBD” → measured avg / 1% low / p95 for your adapter.

### Optional measure_id override

If the adapter string does not auto-match a QA target:

```
/gpu/?measure_fps=1&tier=ultra&measure_id=nvidia-rtx-4070
```

Known ids: see `packages/psyfi-gpu-renderer/src/qa/ultraTargets.ts`.

## Artifacts

| File | Role |
| --- | --- |
| `fixtures/qa/ultra_fps_matrix.synthetic.v1.json` | CI stand-in (always present) |
| `fixtures/qa/ultra_fps_matrix.measured.v1.json` | Hardware samples (starts empty) |
| Downloaded `psyfi-ultra-fps-<id>-<date>.json` | Single capture (`psyfi.ultra_fps_sample.v1`) |

## Pass criteria (per sample)

Against the target tier budget (`ultra` ≈ 120 fps / 8.3 ms, `high` ≈ 60 fps / 16.7 ms):

- avg fps ≥ target
- 1% low ≥ 90% of target
- p95 frame ms ≤ targetFrameMs × 1.15

HUD should also show **band ultra** (or high for mid discrete) and tier **ultra** before capture.

## Non-claims

Modeled phenomenology for research/visualization only. Not medical advice.
