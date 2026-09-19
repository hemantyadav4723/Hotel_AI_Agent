import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _strong_test_secret():
    from api.config import settings
    original = settings.secret_key
    object.__setattr__(settings, "secret_key", "PHASE9_9_TEST_SECRET_KEY_32_CHARS_MINIMUM")
    yield
    object.__setattr__(settings, "secret_key", original)


def _load_client():
    from api.app import app
    return TestClient(app)


def _login(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin@12345", "hotel_id": 1},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_backend_production_testing():
    with _load_client() as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/version").status_code == 200
        assert client.get("/api/v1/customers").status_code == 401


def test_dashboard_production_testing():
    build_check = subprocess.run(
        [sys.executable, "dashboard/build.py", "--check"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "PASS" in build_check.stdout
    assert (PROJECT_ROOT / "dashboard" / "dist" / "index.html").is_file()
    assert (PROJECT_ROOT / "dashboard" / "dist" / "manifest.json").is_file()
    with _load_client() as client:
        response = client.get("/dashboard/")
        assert response.status_code == 200
        assert "YADAV HOTEL" in response.text


def test_authentication_production_testing():
    with _load_client() as client:
        assert client.get("/api/v1/customers").status_code == 401
        headers = _login(client)
        me = client.get("/api/v1/auth/me", headers=headers)
        permissions = client.get("/api/v1/auth/permissions", headers=headers)
        assert me.status_code == 200
        assert me.json()["data"]["hotel_id"] == 1
        assert permissions.status_code == 200
        assert isinstance(permissions.json()["data"], list)


def test_database_production_testing():
    db_path = PROJECT_ROOT / "data" / "hotel.db"
    assert db_path.is_file()
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    from database.database import get_connection
    with get_connection() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM users WHERE hotel_id = 1").fetchone()[0] >= 1
        assert connection.execute("SELECT COUNT(*) FROM roles").fetchone()[0] >= 1
        assert connection.execute("SELECT COUNT(*) FROM permissions").fetchone()[0] >= 1


def test_ai_production_testing():
    with _load_client() as client:
        headers = _login(client)
        status = client.get("/api/v1/ai/status", headers=headers)
        tools = client.get("/api/v1/ai/tools", headers=headers)
        safety = client.get("/api/v1/ai/safety/registry", headers=headers)
        assert status.status_code == 200
        assert status.json()["data"]["hotel_id"] == 1
        assert tools.status_code == 200
        assert isinstance(tools.json()["data"], list)
        assert safety.status_code == 200
        assert safety.json()["data"]["protections"]


def test_end_to_end_production_flow():
    with _load_client() as client:
        headers = _login(client)
        dashboard = client.get("/dashboard/")
        customer_list = client.get("/api/v1/customers", headers=headers)
        ai_status = client.get("/api/v1/ai/status", headers=headers)
        monitoring = client.get("/api/v1/monitoring")
        assert dashboard.status_code == 200
        assert customer_list.status_code == 200
        assert ai_status.status_code == 200
        assert monitoring.status_code == 200
        assert ai_status.json()["data"]["hotel_id"] == 1


def test_production_like_environment(tmp_path):
    source_db = PROJECT_ROOT / "data" / "hotel.db"
    isolated_db = tmp_path / "production" / "hotel.db"
    isolated_db.parent.mkdir(parents=True)
    shutil.copy2(source_db, isolated_db)
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "production",
            "API_SECRET_KEY": "PRODUCTION-TEST-SECRET-KEY-1234567890-ABCDEF",
            "API_CORS_ORIGINS": "https://testserver",
            "API_TRUSTED_HOSTS": "testserver",
            "API_FORCE_HTTPS": "true",
            "API_DOCS_ENABLED": "false",
            "API_RATE_LIMIT_PER_MINUTE": "120",
            "AI_AGENT_ENABLED": "true",
            "AI_AGENT_PROVIDER": "test-provider",
            "AI_AGENT_MODEL": "test-model",
            "AI_AGENT_API_KEY": "test-ai-key",
            "AI_AGENT_API_SECRET": "test-ai-secret",
            "HOTEL_DATABASE_PATH": str(isolated_db),
            "HOTEL_DATABASE_BACKUP_DIR": str(tmp_path / "production" / "backups"),
        }
    )
    code = r'''
import pytest
from fastapi.testclient import TestClient
from api.app import app
with TestClient(app, base_url="https://testserver") as client:
    checks = {
        "/api/v1/health": 200,
        "/api/v1/health/live": 200,
        "/api/v1/health/ready": 200,
        "/api/v1/health/ai": 200,
        "/api/v1/monitoring": 200,
        "/dashboard/": 200,
        "/docs": 404,
        "/redoc": 404,
        "/openapi.json": 404,
        "/api/v1/customers": 401,
    }
    for path, expected in checks.items():
        response = client.get(path, follow_redirects=False)
        if response.status_code != expected:
            raise SystemExit(f"FAIL {path}: expected {expected}, got {response.status_code}")
    login = client.post("/api/v1/auth/login", json={"username":"admin","password":"Admin@12345","hotel_id":1})
    if login.status_code != 200:
        raise SystemExit(f"FAIL login: {login.status_code} {login.text}")
    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    if me.status_code != 200 or me.json()["data"]["hotel_id"] != 1:
        raise SystemExit("FAIL authenticated hotel context")
print("PRODUCTION_LIKE_TEST=PASS")
'''
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "PRODUCTION_LIKE_TEST=PASS" in result.stdout
