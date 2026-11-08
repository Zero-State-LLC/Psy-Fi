"""Public site basics: 404, crawler files, favicon set, per-page meta, privacy page."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi.testclient import TestClient

from psyfi_api.main import app

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "psyfi_api" / "static"
TEMPLATES = ROOT / "psyfi_api" / "templates"
SITE = "https://psy-fi.space"

# Every public HTML page the Worker serves from assets, and where its source lives.
PAGES = {
    "/": TEMPLATES / "index.html",
    "/privacy": TEMPLATES / "privacy.html",
    "404": TEMPLATES / "404.html",
    "/gpu/": ROOT / "packages" / "psyfi-gpu-renderer" / "index.html",
}


def _meta(html: str, attr: str, name: str) -> str:
    match = re.search(rf'<meta {attr}="{re.escape(name)}" content="([^"]*)"', html)
    assert match, f"missing <meta {attr}={name!r}>"
    return match.group(1)


def test_every_page_has_a_unique_title_and_description() -> None:
    titles, descriptions = [], []
    for path, source in PAGES.items():
        html = source.read_text(encoding="utf-8")
        title = html.split("<title>", 1)[1].split("</title>", 1)[0].strip()
        description = _meta(html, "name", "description")
        assert title, path
        assert len(description) >= 50, path
        titles.append(title)
        descriptions.append(description)
    assert len(set(titles)) == len(titles)
    assert len(set(descriptions)) == len(descriptions)
    home = PAGES["/"].read_text(encoding="utf-8")
    assert "ABX-Core v1.3" not in _meta(home, "name", "description")


def test_every_page_carries_the_share_card_and_icon_set() -> None:
    from PIL import Image

    for path, source in PAGES.items():
        html = source.read_text(encoding="utf-8")
        assert _meta(html, "property", "og:type") == "website", path
        assert _meta(html, "property", "og:title") == html.split("<title>", 1)[1].split("</title>", 1)[0].strip(), path
        assert _meta(html, "property", "og:description") == _meta(html, "name", "description"), path
        assert _meta(html, "property", "og:url").startswith(f"{SITE}/"), path
        image = _meta(html, "property", "og:image")
        assert image == f"{SITE}/static/images/psyfi-og.jpg", path
        assert _meta(html, "property", "og:image:width") == "1200", path
        assert _meta(html, "property", "og:image:height") == "630", path
        assert _meta(html, "property", "og:image:alt"), path
        assert _meta(html, "name", "twitter:card") == "summary_large_image", path
        assert _meta(html, "name", "twitter:image") == image, path
        assert 'href="/favicon.ico"' in html, path
        assert 'href="/assets/icons/pf-icon-core-sigil-24.svg" type="image/svg+xml"' in html, path
        assert 'rel="apple-touch-icon" href="/static/apple-touch-icon.png"' in html, path
        assert 'rel="manifest" href="/static/manifest.json"' in html, path
    with Image.open(STATIC / "images" / "psyfi-og.jpg") as im:
        assert im.size == (1200, 630)


def test_favicon_set_is_served_and_derived_from_the_sigil_icons() -> None:
    from PIL import Image

    with Image.open(STATIC / "apple-touch-icon.png") as im:
        assert im.size == (180, 180)
    with Image.open(STATIC / "favicon.ico") as im:
        assert im.format == "ICO"
        assert {(16, 16), (32, 32), (48, 48)} <= set(im.info["sizes"])
    manifest = json.loads((STATIC / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["theme_color"]
    sizes = {icon["sizes"] for icon in manifest["icons"] if icon["type"] == "image/png"}
    assert {"192x192", "512x512"} <= sizes
    with TestClient(app) as client:
        res = client.get("/favicon.ico")
        assert res.status_code == 200
        assert res.content[:4] == b"\x00\x00\x01\x00"


def test_robots_allows_the_site_and_disallows_the_api() -> None:
    with TestClient(app) as client:
        res = client.get("/robots.txt")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    lines = res.text.splitlines()
    assert "User-agent: *" in lines
    assert "Allow: /" in lines
    for path in ("/api", "/simulate", "/docs", "/redoc", "/openapi.json", "/health", "/ready"):
        assert f"Disallow: {path}" in lines
    assert f"Sitemap: {SITE}/sitemap.xml" in lines


def test_sitemap_lists_the_public_pages_as_absolute_urls() -> None:
    with TestClient(app) as client:
        res = client.get("/sitemap.xml")
    assert res.status_code == 200
    assert "xml" in res.headers["content-type"]
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [el.text for el in ET.fromstring(res.content).findall("sm:url/sm:loc", ns)]
    assert locs == [f"{SITE}/", f"{SITE}/gpu/", f"{SITE}/privacy"]


def test_unknown_page_gets_the_branded_404_but_api_errors_stay_json() -> None:
    with TestClient(app) as client:
        page = client.get("/no-such-page")
        nested = client.get("/static/no-such-file.js")
        api = client.get("/api/v1/no-such-route")
        preset = client.get("/api/v1/presets/no-such-preset")
    for res in (page, nested):
        assert res.status_code == 404
        assert res.headers["content-type"].startswith("text/html")
        assert "Page not found" in res.text
        assert 'href="/"' in res.text
        assert '<meta name="robots" content="noindex">' in res.text
    assert api.status_code == 404
    assert api.headers["content-type"].startswith("application/json")
    assert api.json() == {"detail": "Not Found"}
    assert preset.status_code == 404
    assert preset.headers["content-type"].startswith("application/json")


def test_privacy_page_is_served_and_linked_from_every_footer() -> None:
    with TestClient(app) as client:
        res = client.get("/privacy")
    assert res.status_code == 200
    html = res.text
    assert "Effective date: 2026-11-08" in html
    assert "Zero State LLC" in html
    assert 'href="https://zer0state.com/privacy.html"' in html
    assert "zer0state@zer0state.com" in html
    assert "Cloudflare Web Analytics" in html
    assert "static.cloudflareinsights.com" in html
    assert "not medical" in html.lower() or "not medical advice" in html.lower()
    for key in ("psyfi-sessions", "psyfi.session.v1.last"):
        assert key in html
    index = PAGES["/"].read_text(encoding="utf-8")
    # The front page footer and the workspace footer.
    assert index.count('href="/privacy"') == 2
    for source in (PAGES["/privacy"], PAGES["404"]):
        assert 'href="/privacy"' in source.read_text(encoding="utf-8")


def test_every_image_tag_has_alt_text() -> None:
    for source in (TEMPLATES / "index.html", TEMPLATES / "privacy.html", TEMPLATES / "404.html"):
        html = source.read_text(encoding="utf-8")
        for tag in re.findall(r"<img\b[^>]*>", html):
            assert re.search(r'\balt="[^"]*"', tag), f"{source.name}: {tag}"


def test_loading_states_are_announced() -> None:
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert 'id="loadingStatus" role="status" aria-live="polite"' in html
    assert 'id="experienceLoadStatus" role="status" aria-live="polite"' in html
    assert 'id="errorMessage" role="alert"' in html
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "setExperienceLoadState('Loading recipes…', true)" in app_js
    assert "Recipes unavailable" in app_js
    assert "readBtn.disabled = true" in app_js


def test_worker_serves_the_404_page_and_stages_the_root_files(tmp_path) -> None:
    wrangler = (ROOT / "wrangler.jsonc").read_text(encoding="utf-8")
    assert '"not_found_handling": "404-page"' in wrangler
    from scripts import stage_cloudflare_assets as staging

    gpu = tmp_path / "dist"
    gpu.mkdir()
    (gpu / "index.html").write_text("<!doctype html><title>gpu lab</title>", encoding="utf-8")
    original = staging.GPU_DIST
    staging.GPU_DIST = gpu
    try:
        public = staging.stage()
    finally:
        staging.GPU_DIST = original
    for name in ("index.html", "privacy.html", "404.html", "robots.txt", "sitemap.xml", "favicon.ico", "sw.js"):
        assert (public / name).is_file(), name
    assert (public / "404.html").read_text(encoding="utf-8") == (TEMPLATES / "404.html").read_text(encoding="utf-8")
