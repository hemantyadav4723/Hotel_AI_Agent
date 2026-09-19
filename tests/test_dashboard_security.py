from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_security_headers_and_request_correlation():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert response.headers.get("Permissions-Policy")
    assert response.headers.get("Content-Security-Policy-Report-Only")


def test_auth_responses_are_not_cacheable():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers.get("Cache-Control") == "no-store"


def test_oversized_content_length_is_rejected():
    response = client.post("/api/v1/auth/login", headers={"Content-Length": "2000000"}, content=b"{}")
    assert response.status_code == 413


def test_dashboard_token_uses_session_storage():
    from pathlib import Path
    text = Path("dashboard/app.js").read_text()
    assert "sessionStorage" in text
    assert 'localStorage.getItem("yh_access_token")' not in text
    assert 'localStorage.setItem("yh_access_token"' not in text
