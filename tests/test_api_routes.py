"""Integration smoke tests to ensure the FastAPI app runs."""

from fastapi.testclient import TestClient

from psyfi_api.main import app
from psyfi_core.version import __version__


def test_root_route_renders_index_template():
    """Root route should return the HTML landing page."""
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "PsyFi" in response.text


def test_health_route_reports_status_payload():
    """Health route should return JSON with basic service metadata."""
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == "psyfi-api"
    assert payload["version"] == __version__
    assert "timestamp" in payload


def test_api_info_route_reports_version():
    """API info route should expose service identity and version."""
    with TestClient(app) as client:
        response = client.get("/api/info")
        v1 = client.get("/api/v1/info")
    assert response.status_code == 200
    payload = response.json()
    assert payload["message"].startswith("PsyFi API")
    assert payload["version"] == __version__
    assert payload["api_version"] == "v1"
    assert v1.status_code == 200
    assert v1.json()["api_version"] == "v1"


def test_root_shell_exposes_install_and_import_controls():
    """Web shell should wire install prompt and session import controls."""
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert 'id="installButton"' in html
    assert 'id="importSessionInput"' in html
    assert 'id="loadingStatus"' in html
    assert "/static/app.js" in html
