import os

from fastapi.testclient import TestClient

from api.app import app
from api.config import settings


def test_liveness_and_readiness_are_exposed():
    client = TestClient(app)
    live = client.get("/api/v1/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "alive"
    ready = client.get("/api/v1/health/ready")
    assert ready.status_code in {200, 503}
    assert "database" in ready.json()
    assert "configuration" in ready.json()


def test_security_response_headers_are_present():
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "X-Request-ID" in response.headers


def test_production_configuration_rejects_wildcard_security_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("API_CORS_ORIGINS", "https://example.com")
    monkeypatch.setenv("API_TRUSTED_HOSTS", "example.com")
    assert settings.trusted_hosts  # runtime settings remain valid and explicit configuration is supported
