"""Production-readiness boundaries for Phase 8.21.

Provider-neutral controls for configuration validation, bounded retries,
health/readiness reporting, and graceful degradation. No provider SDK or
separate persistence layer is introduced here.
"""
from dataclasses import dataclass
import os
import time
from typing import Any, Callable, TypeVar

from ai.config import settings as ai_settings
from api.config import settings as api_settings
from database.database import get_connection

T = TypeVar("T")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int = 1, maximum: int = 100000) -> int:
    try:
        return max(minimum, min(int(os.getenv(name, str(default))), maximum))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float, minimum: float = 0.1, maximum: float = 300.0) -> float:
    try:
        return max(minimum, min(float(os.getenv(name, str(default))), maximum))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class ProductionSettings:
    environment: str = os.getenv("APP_ENV", "development").strip().lower() or "development"
    log_level: str = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    ai_timeout_seconds: float = _float("AI_AGENT_TIMEOUT_SECONDS", 30.0, 0.5, 300.0)
    ai_max_retries: int = _int("AI_AGENT_MAX_RETRIES", 2, 0, 10)
    ai_retry_backoff_seconds: float = _float("AI_AGENT_RETRY_BACKOFF_SECONDS", 0.25, 0.05, 10.0)
    ai_rate_limit_per_minute: int = _int("API_RATE_LIMIT_PER_MINUTE", 120, 1, 100000)
    max_concurrent_requests: int = _int("AI_MAX_CONCURRENT_REQUESTS", 20, 1, 1000)
    health_timeout_seconds: float = _float("HEALTH_CHECK_TIMEOUT_SECONDS", 5.0, 0.1, 30.0)
    require_secret_in_production: bool = _bool("REQUIRE_PRODUCTION_SECRET", True)

    @property
    def is_production(self) -> bool:
        return self.environment in {"production", "prod"}


production_settings = ProductionSettings()


def validate_production_configuration() -> dict[str, Any]:
    """Return safe configuration readiness information without exposing secrets."""
    issues: list[str] = []
    secret_placeholder = "CHANGE-ME-IN-PRODUCTION-USE-API-SECRET-KEY-32B"
    if production_settings.is_production and production_settings.require_secret_in_production:
        if api_settings.secret_key == secret_placeholder or len(api_settings.secret_key) < 32:
            issues.append("API_SECRET_KEY must be configured with a strong production secret.")
        if "*" in api_settings.cors_origins:
            issues.append("API_CORS_ORIGINS must not use '*' in production.")
    if production_settings.is_production and not ai_settings.enabled:
        issues.append("AI_AGENT_ENABLED is disabled in production.")
    return {
        "environment": production_settings.environment,
        "ready": not issues,
        "issues": issues,
        "secret_configured": api_settings.secret_key != secret_placeholder,
        "ai_enabled": bool(ai_settings.enabled),
        "ai_provider": ai_settings.provider,
        "ai_model_configured": bool(ai_settings.model),
        "rate_limit_per_minute": production_settings.ai_rate_limit_per_minute,
        "max_concurrent_requests": production_settings.max_concurrent_requests,
        "retry_policy": {"max_retries": production_settings.ai_max_retries, "backoff_seconds": production_settings.ai_retry_backoff_seconds},
    }


def database_health() -> dict[str, Any]:
    started = time.perf_counter()
    connection = get_connection()
    try:
        connection.execute("SELECT 1").fetchone()
        return {"status": "ok", "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
    finally:
        connection.close()


def ai_health() -> dict[str, Any]:
    config = validate_production_configuration()
    if production_settings.is_production and not config["ready"]:
        return {"status": "degraded", "configuration": config}
    return {"status": "ok", "configuration": config}


def retry_call(operation: Callable[[], T], retryable: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError, RuntimeError)) -> T:
    """Bounded retry helper for transient provider/service failures."""
    attempts = production_settings.ai_max_retries + 1
    last_error: BaseException | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except retryable as exc:
            last_error = exc
            if attempt >= attempts - 1:
                break
            time.sleep(production_settings.ai_retry_backoff_seconds * (2 ** attempt))
    assert last_error is not None
    raise last_error


def graceful_ai_status(error: Exception | None = None) -> dict[str, Any]:
    if error is None:
        return {"available": True, "status": "ready"}
    return {"available": False, "status": "degraded", "error_type": type(error).__name__}
