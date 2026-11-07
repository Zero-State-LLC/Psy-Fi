# NVIDIA GPU Integration (WebGPU desktop)

Status: supported for **browser WebGPU** on NVIDIA discrete GPUs (RTX 20/30/40/**50** including **RTX 5060**)  
Multi-vendor peers (AMD RX 6000/7000/9000, Intel Arc, Apple Pro/Max): see [`DESKTOP_GPU.md`](DESKTOP_GPU.md).  
Related: [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md), [`rendering/GPU_PERFORMANCE_BUDGET.md`](rendering/GPU_PERFORMANCE_BUDGET.md), `/gpu/`

## How PsyFi uses your NVIDIA card

| Layer | Uses NVIDIA CUDA? | Uses NVIDIA GPU? |
| --- | --- | --- |
| Python ABX-Core / FastAPI | No | No (CPU) |
| Legacy Live Experience (`/`) | No | Optional via WebGL |
| GPU platform (`/gpu/`) | No | **Yes — WebGPU** (Chrome/Edge → D3D12/Vulkan → your RTX) |

PsyFi does **not** require CUDA toolkit install for the web product. Your **RTX 5060** (and other RTX 30/40/50 cards) accelerates the `/gpu/` WebGPU present path inside the browser.

The image-reading caption is a different NVIDIA path. It is a server call to the operator's NVIDIA API, configured in [`CLOUDFLARE.md`](CLOUDFLARE.md). It does not run CUDA in the API container, and it does not use Workers AI. `docker compose --profile nvidia` only reserves a host GPU for the local image.

## Host setup (Windows + RTX 5060)

1. Install current **NVIDIA Game Ready** or **Studio** drivers (50-series supported).
2. Use **Chrome** or **Edge** (recent stable) — enable WebGPU if prompted (`chrome://gpu` → WebGPU should be Hardware accelerated).
3. Prefer the discrete GPU for the browser:
   - Windows Settings → System → Display → Graphics → set Chrome/Edge to **High performance**
   - Or NVIDIA Control Panel → Manage 3D settings → Program Settings → Chrome/Edge → **High-performance NVIDIA processor**
4. Run PsyFi and open **`/gpu/`**:
   ```bash
   docker compose up -d --build
   # or: python3 scripts/run_dev_server.py
   ```
5. Confirm the HUD shows your adapter (e.g. `NVIDIA GeForce RTX 5060`) and tier **ultra** (auto-selected for RTX 30/40/50).

## Quality tier behavior

| Adapter | Default recommended tier |
| --- | --- |
| High-end NVIDIA (RTX 30/40/**50**, incl. **5060**) | **Ultra** |
| AMD RX 6000/7000/9000 · Intel Arc · Apple Pro/Max | **Ultra** (see [`DESKTOP_GPU.md`](DESKTOP_GPU.md)) |
| Other NVIDIA / mid discrete (RTX 20, GTX 16) | **High** |
| iGPU / unknown | **Balanced** |
| No WebGPU | Legacy `/` shell |

You can still override the tier dropdown manually.

## Docker + NVIDIA Container Toolkit (optional)

The API container does **not** run CUDA kernels today. The Compose **`nvidia` profile** still reserves the host GPU for:

- `nvidia-smi` visibility inside the container (ops / future CUDA workers)
- Documented production host readiness on NVIDIA desktops/servers

### Prerequisites

- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- Working `nvidia-smi` on the host

### Run

```bash
# Host check
./scripts/check_nvidia_host.sh
# or: nvidia-smi

# API with GPU reservation
docker compose --profile nvidia up -d --build

# Verify GPU visible in container
docker compose --profile nvidia exec psyfi-nvidia nvidia-smi || \
  docker compose --profile nvidia exec psyfi-nvidia \
    python -c "import os; print('NVIDIA_VISIBLE_DEVICES=', os.environ.get('NVIDIA_VISIBLE_DEVICES'))"
```

Browse **`http://localhost:8000/gpu/`** from the NVIDIA-equipped machine (WebGPU runs in the **browser**, not inside the Python process).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| HUD says no WebGPU | Update Chrome/Edge; check `chrome://gpu`; update NVIDIA driver |
| Runs on Intel iGPU | Force High-performance GPU for the browser (see above) |
| Tier stuck on Balanced | Confirm adapter string contains `RTX` 30/40/50; disable Battery Saver |
| Docker `nvidia` profile fails | Install Container Toolkit; restart Docker; `nvidia-smi` must work on host |

## Next steps

1. Run the [validation checklist](DESKTOP_GPU.md#validation-checklist-next-human-step) on your RTX card.
2. Engineering queue after hardware QA: [`CONTINUATION_PLAN.md`](CONTINUATION_PLAN.md).

## Non-claims

Modeled phenomenology for research/visualization only. Not medical advice.
