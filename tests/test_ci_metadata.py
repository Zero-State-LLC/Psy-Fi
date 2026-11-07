"""CI, license metadata, and the local image match the repo that ships."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_ci_runs_pytest_readme_lint_and_gpu_build() -> None:
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "permissions:" in text
    assert "contents: read" in text
    assert 'pip install -e ".[dev]"' in text
    assert "python -m pytest -q" in text
    assert "npx hallmark lint README.md" in text
    assert "npm run gpu:test" in text
    assert "npm run gpu:typecheck" in text
    assert "npm run gpu:build" in text
    assert "wrangler" not in text.lower()
    assert "noema" not in text.lower()


def test_no_workflow_deploys_noema() -> None:
    assert not (WORKFLOWS / "deploy-worker-pin-pr.yml").exists()
    for path in WORKFLOWS.glob("*.yml"):
        body = path.read_text(encoding="utf-8").lower()
        assert "noema.guru" not in body
        assert "workers/noema" not in body
        assert "resend" not in body
        assert "supabase" not in body


def test_readme_badge_and_package_repository_name_this_repo() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    package = (ROOT / "package.json").read_text(encoding="utf-8")
    assert "Zero-State-LLC/Psy-Fi" in readme
    assert "scrimshawlife-ctrl/Psy-Fi" not in readme
    assert "license-MIT" not in readme
    assert "Zero State Proprietary" in readme
    assert "git+https://github.com/Zero-State-LLC/Psy-Fi.git" in package
    license_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'license = {text = "Zero State Proprietary License"}' in license_text


def test_default_compose_does_not_mask_the_image() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    default = compose.split("psyfi-nvidia:", 1)[0]
    assert "./psyfi_api:/app/psyfi_api" not in default
    assert "./psyfi_core:/app/psyfi_core" not in default
    assert "./docs:/app/docs" not in default
    assert "WORKERS=4" not in compose
    assert "WORKERS=4" not in (ROOT / ".env.example").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert 'CMD ["uvicorn", "psyfi_api.main:app", "--host", "0.0.0.0", "--port", "8000"]' in dockerfile
    assert "--workers" not in dockerfile
