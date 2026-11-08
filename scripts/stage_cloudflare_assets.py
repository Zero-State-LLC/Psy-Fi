"""Copy the shell, site pages, static files, icons, and GPU dist into public/ for the Worker."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
GPU_DIST = ROOT / "packages" / "psyfi-gpu-renderer" / "dist"
# Templates without template variables, staged as-is. The Worker serves bench.html at /bench;
# 404.html is its not_found_handling page.
PAGES = ("index.html", "privacy.html", "bench.html", "404.html")
# Files the site must answer at its root; their sources live in psyfi_api/static/.
ROOT_FILES = ("sw.js", "robots.txt", "sitemap.xml", "favicon.ico")


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def stage() -> Path:
    gpu_index = GPU_DIST / "index.html"
    if not gpu_index.is_file():
        raise FileNotFoundError(
            "GPU lab build is missing. Run npm run gpu:build before staging."
        )
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir()
    for page in PAGES:
        template = ROOT / "psyfi_api" / "templates" / page
        (PUBLIC / page).write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    _copy_tree(ROOT / "psyfi_api" / "static", PUBLIC / "static")
    for name in ROOT_FILES:
        shutil.copy2(ROOT / "psyfi_api" / "static" / name, PUBLIC / name)
    icons = ROOT / "docs" / "icons"
    if icons.is_dir():
        _copy_tree(icons, PUBLIC / "assets" / "icons")
    _copy_tree(GPU_DIST, PUBLIC / "gpu")
    return PUBLIC


if __name__ == "__main__":
    print(stage())
