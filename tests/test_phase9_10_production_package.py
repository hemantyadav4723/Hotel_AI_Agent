from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from deployment.package_production import build  # noqa: E402


def test_production_package_is_clean(tmp_path: Path) -> None:
    output = tmp_path / "release.zip"
    manifest = build(output)
    assert output.exists()
    assert manifest["file_count"] > 0

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())

    assert "DEPLOYMENT_MANIFEST.json" in names
    assert "requirements.txt" in names
    assert ".env.example" in names
    assert "run_api.py" in names
    assert "DEPLOYMENT.md" in names
    assert "dashboard/dist/index.html" in names
    assert "dashboard/dist/manifest.json" in names

    assert not any(name == ".env" or name.startswith(".git/") for name in names)
    assert not any(name.startswith("tests/") for name in names)
    assert not any(name.startswith("deployment/") for name in names)
    assert not any(name.startswith("data/backups/") for name in names)
    assert not any(name.endswith((".db", ".pyc", ".pyo", ".pyd", ".log")) for name in names)
    assert "requirements-dev.txt" not in names


def test_deployment_documentation_exists() -> None:
    text = (ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")
    for marker in ("Production Deployment Package", "requirements.txt", "secret manager", "DEPLOYMENT_MANIFEST.json"):
        assert marker in text
