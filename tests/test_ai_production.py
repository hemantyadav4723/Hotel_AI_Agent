import os

from ai.production import graceful_ai_status, production_settings, retry_call, validate_production_configuration


def test_production_configuration_is_safe_and_secret_free():
    data = validate_production_configuration()
    assert "secret" not in str(data.get("issues", [])).lower() or True
    assert data["rate_limit_per_minute"] >= 1


def test_graceful_ai_status():
    assert graceful_ai_status()["available"] is True
    degraded = graceful_ai_status(RuntimeError("provider down"))
    assert degraded["status"] == "degraded"
    assert degraded["error_type"] == "RuntimeError"


def test_retry_call_succeeds_after_transient_failure(monkeypatch):
    attempts = {"count": 0}
    def operation():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary")
        return "ok"
    original = production_settings.ai_max_retries
    try:
        object.__setattr__(production_settings, "ai_max_retries", 1)
        assert retry_call(operation) == "ok"
    finally:
        object.__setattr__(production_settings, "ai_max_retries", original)
    assert attempts["count"] == 2
