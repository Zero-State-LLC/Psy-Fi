"""Product version stays independent of the frozen API document."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from psyfi_api.main import app
from psyfi_core.models.session import PsyFiSession
from psyfi_core.version import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_version_file_is_the_only_product_version() -> None:
    text = (ROOT / "psyfi_core" / "VERSION").read_text(encoding="utf-8").strip()
    assert text == __version__ == "1.4.0"
    assert __import__("psyfi_api").__version__ == text
    assert __import__("psyfi_core").__version__ == text


def test_pyproject_reads_the_version_file() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in text
    assert 'version = {file = "psyfi_core/VERSION"}' in text
    assert 'version = "0.1.0"' not in text


def test_shell_badge_matches_the_product_version() -> None:
    html = (ROOT / "psyfi_api" / "templates" / "index.html").read_text(encoding="utf-8")
    assert f'class="title-version">v{__version__}<' in html


def test_health_and_info_report_the_product_version() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        info = client.get("/api/v1/info")
    assert health.status_code == 200
    assert health.json()["version"] == __version__
    assert info.status_code == 200
    assert info.json()["version"] == __version__
    assert info.json()["api_version"] == "v1"


def test_frozen_document_version_and_engine_default_stay_0_1_0() -> None:
    assert app.version == "0.1.0"
    frozen = json.loads(
        (ROOT / "docs" / "contracts" / "frozen" / "openapi.v1.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "docs" / "contracts" / "frozen" / "MANIFEST.json").read_text(encoding="utf-8")
    )
    assert frozen["info"]["version"] == "0.1.0"
    assert manifest["freeze_id"] == "psyfi-api-v1-hard-2026-07-25"
    assert manifest["api_version"] == "v1"
    assert PsyFiSession.model_fields["engine_version"].default == "0.1.0"
