"""The /bench results page (#52): served, staged as-is, read only, in the design.md tokens."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from psyfi_api.main import app

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "psyfi_api" / "templates" / "bench.html"
SCRIPT = ROOT / "psyfi_api" / "static" / "bench.js"
STYLE = ROOT / "psyfi_api" / "static" / "bench.css"


def test_bench_page_is_served_with_its_hooks() -> None:
    response = TestClient(app).get("/bench")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    for hook in (
        'id="benchFamily"',
        'id="benchResultsTable"',
        'id="benchResultsEmpty"',
        'id="benchResultsError"',
        'id="benchDetail"',
        'id="benchScorecardFile"',
        'id="benchScorecardBody"',
    ):
        assert hook in html, hook
    assert 'src="/static/bench.js?v=1"' in html
    assert 'name="robots" content="noindex"' in html
    assert "Not medical advice" in html


def test_bench_template_has_no_template_logic_so_staging_can_copy_it() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "{{" not in text and "{%" not in text


def test_bench_page_loads_the_shell_stylesheet_the_service_worker_caches() -> None:
    sw = (ROOT / "psyfi_api" / "static" / "sw.js").read_text(encoding="utf-8")
    cached = re.search(r"/static/style\.css\?v=\d+", sw)
    assert cached is not None
    assert f'href="{cached.group(0)}"' in TEMPLATE.read_text(encoding="utf-8")


def test_bench_script_is_read_only_and_never_injects_html() -> None:
    js = SCRIPT.read_text(encoding="utf-8")
    assert "/api/bench/v1" in js
    sinks = re.findall(r"\.(?:innerHTML|outerHTML)\b|insertAdjacentHTML\s*\(|document\.write(?:ln)?\s*\(", js)
    assert sinks == []
    assert "POST" not in js and "method:" not in js
    # The scorecard is ranked only when the document itself says its subjects are comparable.
    assert "validity.comparable === true" in js


def test_bench_styles_use_the_shell_tokens_only() -> None:
    css = STYLE.read_text(encoding="utf-8")
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", css) is None
    for literal in ("rgb(", "rgba(", "hsl(", "oklch(", "font-family: \"", "transition: all"):
        assert literal not in css, literal
    assert "overflow-x: auto" in css  # the table scrolls inside itself on a phone


def test_workspace_links_to_the_bench_page() -> None:
    html = (ROOT / "psyfi_api" / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'href="/bench"' in html


def test_staging_copies_the_bench_page_and_its_assets(tmp_path) -> None:
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
    assert (public / "bench.html").read_text(encoding="utf-8") == TEMPLATE.read_text(encoding="utf-8")
    assert (public / "static" / "bench.js").is_file()
    assert (public / "static" / "bench.css").is_file()


def test_an_empty_results_store_is_an_empty_list_for_the_empty_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PSYFI_BENCH_RESULTS", str(tmp_path / "results"))
    response = TestClient(app).get("/api/bench/v1/results")
    assert response.status_code == 200
    assert response.json() == {"schema": "psyfi.bench.index.v1", "results": []}
