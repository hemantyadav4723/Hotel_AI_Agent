import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.security import AuthenticationError, decode_access_token
from api.app import app
from api.config import settings


def test_production_trusted_hosts_are_enforced():
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    test_app = FastAPI()
    test_app.add_middleware(TrustedHostMiddleware, allowed_hosts=["allowed.example.com"])
    @test_app.get("/health")
    def health():
        return {"status": "ok"}
    response = TestClient(test_app).get("/health", headers={"host": "blocked.example.com"})
    assert response.status_code == 400


def test_access_token_rejects_invalid_hotel_id(monkeypatch):
    import jwt
    token = jwt.encode({"sub": "ADMIN1001", "username": "admin", "role": "Admin", "hotel_id": 0, "type": "access"}, settings.secret_key, algorithm=settings.algorithm)
    with pytest.raises(AuthenticationError):
        decode_access_token(token)


def test_production_configuration_fails_closed_on_missing_secret(monkeypatch):
    from ai.production import validate_production_configuration, production_settings
    object.__setattr__(production_settings, "environment", "production")
    object.__setattr__(settings, "secret_key", "x" * 8)
    object.__setattr__(settings, "cors_origins", ("https://example.com",))
    object.__setattr__(settings, "trusted_hosts", ("example.com",))
    result = validate_production_configuration()
    assert result["ready"] is False
    assert any("API_SECRET_KEY" in issue for issue in result["issues"])
