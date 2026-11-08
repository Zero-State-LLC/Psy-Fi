# PsyFi — Docker image (API + legacy shell + optional GPU dist)
# Applied Alchemy Labs

FROM node:20-bookworm-slim AS gpu-build
WORKDIR /src
COPY package.json package-lock.json ./
COPY packages/psyfi-gpu-renderer/package.json packages/psyfi-gpu-renderer/
RUN npm ci
COPY packages/psyfi-gpu-renderer packages/psyfi-gpu-renderer
RUN npm run gpu:build

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY psyfi_core/ ./psyfi_core/
COPY psyfi_api/ ./psyfi_api/
COPY psyfi_bench/ ./psyfi_bench/
COPY docs/ ./docs/
COPY data/ ./data/
RUN pip install --upgrade pip && \
    pip install -e .
COPY --from=gpu-build /src/packages/psyfi-gpu-renderer/dist ./packages/psyfi-gpu-renderer/dist

RUN useradd -m -u 1000 psyfi && \
    chown -R psyfi:psyfi /app

USER psyfi

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

# One process on purpose. The image does not read a worker count.
CMD ["uvicorn", "psyfi_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
