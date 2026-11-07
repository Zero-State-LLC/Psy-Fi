# PsyFi Deployment Guide

Production is one Cloudflare Worker: static shell and GPU lab, Python API in the existing image behind that Worker. The steps are in [`docs/CLOUDFLARE.md`](docs/CLOUDFLARE.md). CI does not deploy.

Docker Compose is the local seam. Azure, Render, and the Pages workflow are not ship paths.

## Local development

```bash
git clone https://github.com/Zero-State-LLC/Psy-Fi.git
cd Psy-Fi
pip install -e ".[dev]"
cp .env.example .env
python3 scripts/run_dev_server.py
# → http://localhost:8000
```

## Docker (local seam)

### Single container

```bash
docker build -t psyfi:latest .
docker run -d --name psyfi -p 8000:8000 -e ENVIRONMENT=production psyfi:latest
docker logs -f psyfi
curl -s http://localhost:8000/health
```

### Docker Compose

```bash
# API only
docker compose up -d --build

# API + nginx reverse proxy
docker compose --profile production up -d --build
```

Helper script (local / Docker / Compose / production checks):

```bash
./scripts/deploy.sh
```

## Local image checklist

1. Copy `.env.example` → `.env`. Leave the vision model unset. Do not put an API key in `.env`.
2. `python3 -m pytest tests/ -q`
3. `docker build -t psyfi:latest .`
4. For a local TLS proxy, use the Compose `production` profile with `nginx.conf`, or your own reverse proxy. That profile is not the Cloudflare host.
5. Confirm `/health` and `/ready`.

The production hostname is the Worker in [`docs/CLOUDFLARE.md`](docs/CLOUDFLARE.md).

## GPU shell in the image

The multi-stage `Dockerfile` runs `npm run gpu:build` and copies `packages/psyfi-gpu-renderer/dist` into the image. FastAPI serves it at `/gpu/` when present.

Local iteration without rebuilding the image:

```bash
npm ci
npm run gpu:build
python3 scripts/run_dev_server.py
# → http://localhost:8000/gpu/
```

### Desktop GPUs (NVIDIA / AMD / Intel / Apple)

`/gpu/` uses **browser WebGPU** on your discrete GPU (not CUDA/HIP in Python). Ultra auto-tier covers NVIDIA RTX **30/40/50**, AMD RX **6000/7000/9000**, Intel **Arc**, and Apple Pro/Max.

```bash
# Then open Chrome/Edge → http://localhost:8000/gpu/
# Force High-performance discrete GPU for the browser if hybrid graphics.

# NVIDIA host check + optional Compose GPU reservation
./scripts/check_nvidia_host.sh
docker compose --profile nvidia up -d --build
```

Guides: [`docs/DESKTOP_GPU.md`](docs/DESKTOP_GPU.md) · NVIDIA Compose: [`docs/NVIDIA_GPU.md`](docs/NVIDIA_GPU.md).

See [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md) for the ship board and next steps.

## Health

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
```

## Related

- `Dockerfile`, `docker-compose.yml`, `nginx.conf`
- `QUICK_DEPLOY.md` — short command reference
- `MOBILE_PWA_GUIDE.md` — PWA notes after the API is reachable
