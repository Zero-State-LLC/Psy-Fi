"""Production host is one Worker. The vision key is not in the repo."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_NEEDLE = "nv" + "api-"

_SKIP_DIR_NAMES = {".git", "node_modules", "graft", "public", "__pycache__", "specs"}
_SCAN_ROOTS = (
    "psyfi_api",
    "psyfi_core",
    "packages",
    "workers",
    "scripts",
    "docs",
)


def test_wrangler_names_the_container_and_does_not_pin_a_model() -> None:
    text = (ROOT / "wrangler.jsonc").read_text(encoding="utf-8")
    assert _NEEDLE not in text
    assert "NVIDIA_API_KEY" not in text
    assert "nvidia/" not in text.lower()
    assert "@cf/" not in text
    assert '"dockerfile": "./Dockerfile"' in text
    assert '"name": "PSYFI_API"' in text
    assert '"directory": "./public"' in text
    assert '"run_worker_first": true' in text
    worker = (ROOT / "workers" / "psyfi" / "src" / "index.mjs").read_text(encoding="utf-8")
    assert "enableInternet: true" in worker
    assert "standard-1" in worker
    assert "getTcpPort(PORT)" in worker
    assert _NEEDLE not in worker


def test_staged_shell_is_the_template_without_a_key() -> None:
    from scripts.stage_cloudflare_assets import stage

    public = stage()
    html = (public / "index.html").read_text(encoding="utf-8")
    source = (ROOT / "psyfi_api" / "templates" / "index.html").read_text(encoding="utf-8")
    assert html == source
    assert 'id="imageReading"' in html
    assert (public / "static" / "app.js").is_file()
    assert (public / "sw.js").is_file()
    blob = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in public.rglob("*") if path.is_file())
    assert _NEEDLE not in blob


def test_product_surfaces_have_no_nvidia_key_value() -> None:
    hits: list[str] = []
    for name in _SCAN_ROOTS:
        base = ROOT / name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or any(part in _SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".js", ".mjs", ".html", ".json", ".yml", ".yaml", ".css", ".md"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if _NEEDLE in text:
                hits.append(str(path.relative_to(ROOT)))
    compose = list(ROOT.glob("docker-compose*.yml")) + list(ROOT.glob("compose*.yml"))
    for path in compose:
        if _NEEDLE in path.read_text(encoding="utf-8", errors="replace"):
            hits.append(str(path.relative_to(ROOT)))
    example = ROOT / ".env.example"
    example_text = example.read_text(encoding="utf-8")
    assert _NEEDLE not in example_text
    assert "NVIDIA_API_KEY=" not in example_text
    assert hits == []
