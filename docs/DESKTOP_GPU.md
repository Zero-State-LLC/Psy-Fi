# Desktop GPU Integration (WebGPU)

Status: supported for **browser WebGPU** on high-end discrete desktops · Ultra auto-tier live  
Related: [`bench/DISCRETE_GPU_HANDOFF.md`](bench/DISCRETE_GPU_HANDOFF.md), [`NVIDIA_GPU.md`](NVIDIA_GPU.md), [`SIMULATED_ULTRA_QA.md`](SIMULATED_ULTRA_QA.md), [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md), [`rendering/GPU_PERFORMANCE_BUDGET.md`](rendering/GPU_PERFORMANCE_BUDGET.md), `/gpu/`

## How PsyFi uses your GPU

| Layer | Uses vendor CUDA/HIP/oneAPI? | Uses your GPU? |
| --- | --- | --- |
| Python ABX-Core / FastAPI | No | No (CPU) |
| Legacy Live Experience (`/`) | No | Optional via WebGL |
| GPU platform (`/gpu/`) | No | **Yes — WebGPU** (Chrome/Edge → D3D12/Vulkan/Metal) |

PsyFi does **not** require CUDA, ROCm, or oneAPI for the web product. Discrete GPUs accelerate the `/gpu/` present path inside the browser.

## Supported high-end bands → Ultra (auto)

| Vendor | Series (examples) | Default recommended tier |
| --- | --- | --- |
| **NVIDIA** | GeForce **RTX 30 / 40 / 50** (3060…5090, incl. **5060**) | **Ultra** |
| **AMD** | Radeon **RX 6000 / 7000 / 9000** (6800, 7800 XT, 9070 XT, …) | **Ultra** |
| **Intel** | **Arc** discrete (A750/A770, B580, …) | **Ultra** |
| **Apple** | M-series **Pro / Max / Ultra** | **Ultra** |
| Mid discrete | RTX 20, GTX 16, RX 5000, other dGPU | **High** |
| iGPU / unknown | Intel UHD/Iris, etc. | **Balanced** |
| No WebGPU | — | Legacy `/` shell |

You can still override the tier dropdown manually. Battery Saver / low charge clamps Ultra → Balanced.

## Host setup (any vendor)

1. Install current GPU drivers (Game Ready / Adrenalin / Arc / Apple OS updates).
2. Use **Chrome** or **Edge** (recent stable). Check `chrome://gpu` → WebGPU Hardware accelerated.
3. Prefer the **discrete** GPU for the browser:
   - Windows: Settings → System → Display → Graphics → Chrome/Edge → **High performance**
   - Or vendor control panel (NVIDIA / AMD) → High-performance GPU for Chrome/Edge
4. Run PsyFi and open **`/gpu/`**:
   ```bash
   docker compose up -d --build
   # or: python3 scripts/run_dev_server.py
   ```
5. Confirm the HUD shows your adapter string and tier **ultra** on supported high-end cards.

## NVIDIA-only extras

Docker GPU reservation (`--profile nvidia`), `nvidia-smi`, and RTX 50xx driver notes live in [`NVIDIA_GPU.md`](NVIDIA_GPU.md). The API container still does **not** run CUDA kernels; WebGPU runs in the browser.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| HUD says no WebGPU | Update Chrome/Edge; check `chrome://gpu`; update GPU driver |
| Runs on iGPU | Force High-performance GPU for the browser |
| Tier stuck on Balanced | Confirm adapter string matches a Ultra-band series; disable Battery Saver |
| AMD/Intel not Ultra | Confirm description includes RX 6/7/9xxx or Arc A/B series |

## Simulated QA (CI)

A CI stand-in for this checklist lives in [`SIMULATED_ULTRA_QA.md`](SIMULATED_ULTRA_QA.md) (adapter fixtures + API `/gpu/` + Neutral + synthetic Ultra fps matrix). It does **not** replace measured fps on a physical discrete GPU.

Synthetic fps matrix: `packages/psyfi-gpu-renderer/fixtures/qa/ultra_fps_matrix.synthetic.v1.json` (evaluate with `qa/ultraFpsMatrix.ts` against Ultra ~120fps / High ~60fps tier budgets).

## Validation checklist (on real hardware)

After deploy, on each target GPU:

1. Open Chrome/Edge → `http://localhost:8000/gpu/` (or your host URL).
2. HUD shows **adapter** string, **vendor**, **band ultra**, and tier **ultra**.
3. Profiling line shows FPS · avg/p95/max ms vs tier **target** (prefer **ok**, not OVER).
4. Capture a measured sample: `/gpu/?measure_fps=1&tier=ultra` or the **Measure Ultra fps** button — see [`HARDWARE_ULTRA_FPS.md`](HARDWARE_ULTRA_FPS.md).
5. Merge the download: `python3 scripts/merge_ultra_fps_measured.py ~/Downloads/psyfi-ultra-fps-*.json`
6. Toggle Neutral View — safety pass still attenuates; scene stays calm.
7. With Battery Saver / low charge, tier clamps away from Ultra.

Update [`BROWSER_CAPABILITY_MATRIX.md`](BROWSER_CAPABILITY_MATRIX.md) Notes with measured avg / 1% low / p95.

## Recommended engineering follow-ups

See [`CONTINUATION_PLAN.md`](CONTINUATION_PLAN.md) Active queue **E**. Profiling HUD and KTX2/Draco upload bridges are in `/gpu/`.

## Non-claims

Modeled phenomenology for research/visualization only. Not medical advice.
