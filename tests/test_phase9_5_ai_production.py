import logging

from ai.logging import configure_ai_logging
from ai.production import production_settings, validate_production_configuration
from ai.safety import safety_guardrails
from api.config import settings as api_settings


def test_ai_production_configuration_contract():
    original = {
        "environment": production_settings.environment,
        "enabled": __import__("ai.config", fromlist=["settings"]).settings.enabled,
        "provider": __import__("ai.config", fromlist=["settings"]).settings.provider,
        "model": __import__("ai.config", fromlist=["settings"]).settings.model,
        "api_key": __import__("ai.config", fromlist=["settings"]).settings.api_key,
        "api_secret": __import__("ai.config", fromlist=["settings"]).settings.api_secret,
        "api_secret_key": api_settings.secret_key,
        "cors_origins": api_settings.cors_origins,
        "trusted_hosts": api_settings.trusted_hosts,
    }
    ai_settings = __import__("ai.config", fromlist=["settings"]).settings
    try:
        object.__setattr__(production_settings, "environment", "production")
        object.__setattr__(ai_settings, "enabled", True)
        object.__setattr__(ai_settings, "provider", "test-provider")
        object.__setattr__(ai_settings, "model", "test-model")
        object.__setattr__(ai_settings, "api_key", "x" * 32)
        object.__setattr__(api_settings, "secret_key", "y" * 32)
        object.__setattr__(api_settings, "cors_origins", ["https://example.com"])
        object.__setattr__(api_settings, "trusted_hosts", ["example.com"])
        data = validate_production_configuration()
        assert data["ready"] is True
        assert data["ai_api_key_configured"] is True
        assert "x" * 32 not in str(data)
    finally:
        for key, value in original.items():
            if key == "environment":
                object.__setattr__(production_settings, key, value)
            elif key in {"api_secret_key", "cors_origins", "trusted_hosts"}:
                attr = {"api_secret_key": "secret_key", "cors_origins": "cors_origins", "trusted_hosts": "trusted_hosts"}[key]
                object.__setattr__(api_settings, attr, value)
            else:
                object.__setattr__(ai_settings, key, value)


def test_guardrail_registry_has_production_protections():
    registry = safety_guardrails.registry()
    assert "prompt_injection_detection" in registry["protections"]
    assert "audit_logging" in registry["protections"]
    assert "hotel_scope" in registry["protections"]


def test_ai_logging_configures_dedicated_logger(tmp_path, monkeypatch):
    logger = logging.getLogger("yadav_hotel.ai")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    monkeypatch.setenv("AI_FILE_LOGGING", "true")
    monkeypatch.setenv("AI_LOG_DIR", str(tmp_path))
    configured = configure_ai_logging()
    assert configured.name == "yadav_hotel.ai"
    assert configured.level == logging.INFO
    assert (tmp_path / "ai.log").exists()
