from pathlib import Path
import json
import subprocess
import sys

from fastapi.testclient import TestClient

from api.app import app

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


def test_dashboard_production_build_check():
    result = subprocess.run(
        [sys.executable, str(DASHBOARD / "build.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "PASS" in result.stdout


def test_dashboard_production_build_creates_verified_artifact():
    result = subprocess.run(
        [sys.executable, str(DASHBOARD / "build.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    dist = DASHBOARD / "dist"
    assert dist.is_dir()
    manifest = json.loads((dist / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["assets"]) == {"index.html", "config.js", "app.js", "styles.css"}
    for name, meta in manifest["assets"].items():
        path = dist / name
        assert path.is_file()
        assert path.stat().st_size == meta["size"]
        assert len(meta["sha256"]) == 64


def test_dashboard_assets_and_auth_permission_contracts():
    client = TestClient(app)
    assert client.get("/dashboard/").status_code == 200
    html = client.get("/dashboard/").text
    assert "/dashboard/config.js" in html
    assert "/dashboard/app.js" in html
    js = client.get("/dashboard/app.js").text
    config = client.get("/dashboard/config.js").text
    assert "Authorization" in js
    assert "hasPermission" in js
    assert "isActionAllowed" in js
    assert "YH_API_BASE" in config


def test_dashboard_protected_api_boundary_remains_active():
    client = TestClient(app)
    assert client.get("/api/v1/customers").status_code == 401
    assert client.get("/api/v1/auth/permissions").status_code == 401


def test_production_docs_flag_is_honored():
    script = """
import os
os.environ["APP_ENV"] = "production"
os.environ["API_SECRET_KEY"] = "x" * 40
os.environ["API_CORS_ORIGINS"] = "https://example.com"
os.environ["API_TRUSTED_HOSTS"] = "testserver"
os.environ["API_DOCS_ENABLED"] = "false"
from fastapi.testclient import TestClient
from api.app import app
client = TestClient(app)
assert client.get("/docs").status_code == 404
assert client.get("/redoc").status_code == 404
assert client.get("/openapi.json").status_code == 404
assert client.get("/dashboard/").status_code == 200
assert client.get("/api/v1/health").status_code == 200
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
