"""Image Reading is an inferred caption beside the image seed."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from psyfi_api.main import app

client = TestClient(app)


def _png_bytes(size=(32, 24), color=(10, 20, 30, 255)) -> bytes:
    img = Image.new("RGBA", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _Stub:
    def __init__(self, status: int = 200, payload: dict | None = None) -> None:
        self.status = status
        self.payload = payload or {
            "choices": [{"message": {"content": "A blue square on a dark field."}}]
        }
        self.bodies: list[dict] = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def _handler(self):
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                stub.bodies.append(json.loads(raw.decode()))
                data = json.dumps(stub.payload).encode()
                self.send_response(stub.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args) -> None:
                return

        return Handler

    @property
    def base(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}"

    def close(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()


def _post(png: bytes, **env: str):
    keys = ("NVIDIA_API_KEY", "NVIDIA_VISION_MODEL", "NVIDIA_API_BASE")
    saved = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ.pop(key, None)
    os.environ.update(env)
    try:
        return client.post(
            "/api/v1/visualize/image-reading",
            files={"file": ("tiny.png", png, "image/png")},
        )
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_reading_when_model_unset_does_not_call_out() -> None:
    stub = _Stub()
    try:
        response = _post(_png_bytes(), NVIDIA_API_BASE=stub.base, NVIDIA_API_KEY="test-key")
    finally:
        stub.close()
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "vision_unconfigured"
    assert stub.bodies == []


def test_reading_rejects_non_nvidia_model_without_calling_out() -> None:
    stub = _Stub()
    try:
        response = _post(
            _png_bytes(),
            NVIDIA_API_BASE=stub.base,
            NVIDIA_API_KEY="test-key",
            NVIDIA_VISION_MODEL="@cf/nvidia/nemotron-3-120b-a12b",
        )
    finally:
        stub.close()
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "vision_unconfigured"
    assert stub.bodies == []


def test_reading_sends_resized_source_and_returns_inferred_caption() -> None:
    stub = _Stub()
    try:
        response = _post(
            _png_bytes(size=(800, 400)),
            NVIDIA_API_BASE=stub.base,
            NVIDIA_API_KEY="test-key",
            NVIDIA_VISION_MODEL="nvidia/test-vl",
        )
    finally:
        stub.close()
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "psyfi.image_reading.v1"
    assert body["authority"] == "INFERRED"
    assert body["caption"] == "A blue square on a dark field."
    assert body["model"] == "nvidia/test-vl"
    assert "medical" in body["disclaimer"].lower()
    assert "test-key" not in response.text
    assert len(stub.bodies) == 1
    message = stub.bodies[0]["messages"][0]["content"]
    image = next(part for part in message if part["type"] == "image_url")
    assert [part["type"] for part in message] == ["text", "image_url"]
    raw = image["image_url"]["url"].split(",", 1)[1]
    decoded = Image.open(io.BytesIO(base64.b64decode(raw)))
    assert max(decoded.size) <= 384
    assert stub.bodies[0]["model"] == "nvidia/test-vl"


def test_reading_rejects_missing_key_without_calling_out() -> None:
    stub = _Stub()
    try:
        response = _post(
            _png_bytes(),
            NVIDIA_API_BASE=stub.base,
            NVIDIA_VISION_MODEL="nvidia/test-vl",
        )
    finally:
        stub.close()
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "vision_unconfigured"
    assert stub.bodies == []


def test_reading_rejects_oversize_before_calling_out() -> None:
    stub = _Stub()
    blob = b"not-an-image" + (b"x" * 12_000_000)
    try:
        response = _post(
            blob,
            NVIDIA_API_BASE=stub.base,
            NVIDIA_API_KEY="test-key",
            NVIDIA_VISION_MODEL="nvidia/test-vl",
        )
    finally:
        stub.close()
    assert response.status_code == 400
    assert stub.bodies == []


def test_reading_runs_off_the_event_loop() -> None:
    import psyfi_api.routers.experiences as experiences

    seen: dict[str, bool] = {}

    def blocked(data: bytes) -> dict[str, str]:
        del data
        try:
            asyncio.get_running_loop()
            seen["on_loop"] = True
        except RuntimeError:
            seen["on_loop"] = False
        return {
            "schema_version": "psyfi.image_reading.v1",
            "authority": "INFERRED",
            "caption": "held",
            "model": "nvidia/test-vl",
            "disclaimer": "Not medical advice.",
        }

    original = experiences.read_image
    experiences.read_image = blocked  # type: ignore[assignment]
    try:
        response = client.post(
            "/api/v1/visualize/image-reading",
            files={"file": ("tiny.png", _png_bytes(), "image/png")},
        )
    finally:
        experiences.read_image = original
    assert response.status_code == 200
    assert seen["on_loop"] is False


def test_body_timeout_is_a_provider_error(monkeypatch) -> None:
    from psyfi_api.image_reading import VisionProviderError, read_image

    class _Response:
        def read(self) -> bytes:
            raise TimeoutError("timed out")

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *args) -> bool:
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: _Response())
    saved = {key: os.environ.get(key) for key in ("NVIDIA_API_KEY", "NVIDIA_VISION_MODEL", "NVIDIA_API_BASE")}
    os.environ["NVIDIA_API_KEY"] = "test-key"
    os.environ["NVIDIA_VISION_MODEL"] = "nvidia/test-vl"
    os.environ["NVIDIA_API_BASE"] = "http://127.0.0.1:9"
    try:
        try:
            read_image(_png_bytes())
        except VisionProviderError as exc:
            assert exc.detail == "vision provider unreachable"
        else:
            raise AssertionError("body timeout escaped the provider error")
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_provider_error_is_not_retried() -> None:
    stub = _Stub(status=400, payload={"error": {"message": "image modality is not supported"}})
    try:
        response = _post(
            _png_bytes(),
            NVIDIA_API_BASE=stub.base,
            NVIDIA_API_KEY="test-key",
            NVIDIA_VISION_MODEL="nvidia/test-vl",
        )
    finally:
        stub.close()
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "vision_provider"
    assert len(stub.bodies) == 1


def test_image_seed_payload_has_no_reading() -> None:
    png = _png_bytes()
    response = client.post(
        "/api/v1/visualize/image-seed",
        files={"file": ("tiny.png", png, "image/png")},
        data={"recommend_only": "true"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "caption" not in body
    assert "image_reading" not in body
    assert body.get("schema") == "psyfi.image_seed.v1" or "master_seed" in body or "features" in body


def test_shell_renders_image_reading_as_text() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "psyfi_api" / "templates" / "index.html").read_text(encoding="utf-8")
    script = (root / "psyfi_api" / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="imageReading"' in html
    assert "imageReading.textContent" in script
    reading_fn = script.split("async function readImage", 1)[1].split("async function", 1)[0]
    assert "innerHTML" not in reading_fn
    assert "slice(0, 2000)" in reading_fn
