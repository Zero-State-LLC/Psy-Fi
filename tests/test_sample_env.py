"""The sample environment matches the switches the process actually reads."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from psyfi_api.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_sample_env_does_not_present_unread_switches() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in (
        "ALLOWED_ORIGINS=",
        "API_KEY_REQUIRED=",
        "SECRET_KEY=",
        "RATE_LIMIT_",
        "NVIDIA_API_KEY=",
    ):
        assert key not in text
    assert "does not read an" in text


def test_public_route_needs_no_api_key(monkeypatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with TestClient(app) as client:
        health = client.get("/health")
        presets = client.get("/api/v1/presets/")
    assert health.status_code == 200
    assert presets.status_code == 200
