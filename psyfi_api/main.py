"""PsyFi API - Main FastAPI application."""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from psyfi_api.routers import experiences, jobs, midi, presets, simulate, telemetry
from psyfi_api.telemetry import TELEMETRY_ENABLED
from psyfi_core.models.substance_preset import get_registry
from psyfi_core.version import __version__

# Initialize FastAPI app.
# version= is the frozen OpenAPI document version (info.version).
# The running build reports __version__ on /health, /ready, and /api/info.
app = FastAPI(
    title="PsyFi API",
    description="Consciousness field simulation engine with ABX-Core v1.3",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup static files and templates
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
# Reuse the existing docs/icons pack for PWA/browser icons.
app.mount(
    "/assets/icons",
    StaticFiles(directory=str(REPO_ROOT / "docs" / "icons")),
    name="icons",
)
# Optional GPU platform build (packages/psyfi-gpu-renderer). Legacy shell stays at /.
_GPU_DIST = REPO_ROOT / "packages" / "psyfi-gpu-renderer" / "dist"
_SERVE_GPU = os.environ.get("PSYFI_SERVE_GPU", "1") != "0"
if _SERVE_GPU and _GPU_DIST.is_dir() and (_GPU_DIST / "index.html").exists():
    app.mount("/gpu", StaticFiles(directory=str(_GPU_DIST), html=True), name="gpu")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Legacy compatibility mounts
app.include_router(simulate.router)  # /simulate/
app.include_router(midi.router, prefix="/api")  # /api/midi
app.include_router(presets.router, prefix="/api")  # /api/presets
app.include_router(jobs.router, prefix="/api")  # /api/jobs
app.include_router(telemetry.router, prefix="/api")  # /api/telemetry

# Versioned public web API (canonical for the browser client)
app.include_router(simulate.router, prefix="/api/v1")  # /api/v1/simulate/
app.include_router(midi.router, prefix="/api/v1")  # /api/v1/midi
app.include_router(presets.router, prefix="/api/v1")  # /api/v1/presets
app.include_router(jobs.router, prefix="/api/v1")  # /api/v1/jobs
app.include_router(telemetry.router, prefix="/api/v1")  # /api/v1/telemetry
# Experiences router already uses /api/v1 prefix internally
app.include_router(experiences.router)


@app.get("/")
async def root(request: Request):
    """Root endpoint - serves the web UI."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/privacy", include_in_schema=False)
async def privacy(request: Request):
    """Privacy policy page. The Worker serves the staged copy on the public host."""
    return templates.TemplateResponse(request, "privacy.html")


@app.get("/robots.txt", include_in_schema=False)
@app.get("/sitemap.xml", include_in_schema=False)
@app.get("/favicon.ico", include_in_schema=False)
async def site_root_file(request: Request) -> FileResponse:
    """Crawler and browser files that must sit at the site root; sources live in static/."""
    return FileResponse(BASE_DIR / "static" / request.url.path.lstrip("/"))


# Paths whose errors stay JSON. Everything else is a site page and gets the branded 404.
_JSON_ERROR_PREFIXES = ("/api", "/simulate", "/health", "/ready", "/docs", "/redoc", "/openapi.json")


@app.exception_handler(StarletteHTTPException)
async def not_found_page(request: Request, exc: StarletteHTTPException):
    """Unknown site paths get the HTML 404 page with a real 404 status; API paths keep JSON."""
    if exc.status_code != 404 or request.url.path.startswith(_JSON_ERROR_PREFIXES):
        return await http_exception_handler(request, exc)
    return templates.TemplateResponse(request, "404.html", status_code=404)


@app.get("/sw.js")
async def service_worker() -> FileResponse:
    """Serve the PWA service worker with a root scope allowlist.

    Scripts under `/static/` default to max scope `/static/`, which cannot
    intercept `/` or `/gpu/` navigations. `Service-Worker-Allowed: /` plus
    registration `{ scope: '/' }` makes the documented offline shell real.
    """
    return FileResponse(
        BASE_DIR / "static" / "sw.js",
        media_type="application/javascript; charset=utf-8",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache",
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check for monitoring and load balancers."""
    from datetime import datetime, timezone

    return {
        "status": "healthy",
        "service": "psyfi-api",
        "version": __version__,
        "abx_core": "1.3",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@app.get("/ready")
@app.get("/api/v1/ready")
async def ready() -> dict:
    """Readiness check: presets and critical static assets must be available."""
    from datetime import datetime, timezone

    checks: dict[str, bool] = {}
    try:
        preset_names = get_registry().list_presets()
        checks["presets_loaded"] = len(preset_names) > 0
    except Exception:  # noqa: BLE001
        checks["presets_loaded"] = False

    checks["session_schema"] = (
        REPO_ROOT / "psyfi_core" / "schemas" / "session.schema.json"
    ).exists()
    checks["icon_192"] = (BASE_DIR / "static" / "icon-192.png").exists()
    checks["icon_512"] = (BASE_DIR / "static" / "icon-512.png").exists()
    checks["renderer_js"] = (BASE_DIR / "static" / "renderer.js").exists()
    checks["experience_player"] = (BASE_DIR / "static" / "viz" / "experiencePlayer.js").exists()
    checks["experience_catalog"] = (
        REPO_ROOT / "data" / "phenomenology" / "derived" / "experience_catalog.v1.json"
    ).exists()
    checks["visual_overlays"] = (
        REPO_ROOT / "data" / "phenomenology" / "derived" / "substance_visual_overlays.v1.json"
    ).exists()
    checks["scene_snapshot_schema"] = (
        REPO_ROOT / "docs" / "schemas" / "psyfi_scene_snapshot.v1.json"
    ).exists()

    ready_ok = all(checks.values())
    return {
        "status": "ready" if ready_ok else "not_ready",
        "service": "psyfi-api",
        "version": __version__,
        "api_version": "v1",
        "checks": checks,
        "gpu_shell_mounted": bool(
            _SERVE_GPU and _GPU_DIST.is_dir() and (_GPU_DIST / "index.html").exists()
        ),
        "telemetry_server_enabled": TELEMETRY_ENABLED,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@app.get("/api/info")
@app.get("/api/v1/info")
async def api_info() -> dict[str, str | bool]:
    """API info endpoint (legacy + v1)."""
    return {
        "message": "PsyFi API - Consciousness Field Simulation",
        "version": __version__,
        "api_version": "v1",
        "abx_core": "1.3",
        "telemetry_server_enabled": TELEMETRY_ENABLED,
    }
