"""Environment-driven API runtime configuration.

Secrets are never stored in source control. Production values must be
injected through the environment or a secret manager.
"""

import os
from dataclasses import dataclass


SECRET_PLACEHOLDER = "CHANGE-ME-IN-PRODUCTION-USE-API-SECRET-KEY-32B"


def _env_int(name: str, default: int, minimum: int = 1, maximum: int = 100000) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _environment() -> str:
    return os.getenv("APP_ENV", "development").strip().lower() or "development"


def _default_host() -> str:
    return "0.0.0.0" if _environment() in {"production", "prod"} else "127.0.0.1"


@dataclass(frozen=True)
class APISettings:
    app_name: str = "YADAV HOTEL AI AGENT PRO API"
    version: str = "1.0.0"
    prefix: str = "/api/v1"
    environment: str = _environment()
    debug: bool = _env_bool("API_DEBUG", False)
    host: str = os.getenv("API_HOST", _default_host()).strip() or _default_host()
    port: int = _env_int("API_PORT", 8000, 1, 65535)
    workers: int = _env_int("API_WORKERS", 1, 1, 32)
    secret_key: str = os.getenv("API_SECRET_KEY", SECRET_PLACEHOLDER)
    algorithm: str = "HS256"
    access_token_minutes: int = _env_int("API_ACCESS_TOKEN_MINUTES", 60, 1, 1440)
    cors_origins: tuple[str, ...] = tuple(
        origin.strip() for origin in os.getenv("API_CORS_ORIGINS", "*").split(",") if origin.strip()
    ) or ("*",)
    trusted_hosts: tuple[str, ...] = tuple(
        host.strip() for host in os.getenv("API_TRUSTED_HOSTS", "*").split(",") if host.strip()
    ) or ("*",)
    proxy_headers: bool = _env_bool("API_PROXY_HEADERS", False)
    forwarded_allow_ips: str = os.getenv("API_FORWARDED_ALLOW_IPS", "127.0.0.1").strip() or "127.0.0.1"
    access_log: bool = _env_bool("API_ACCESS_LOG", True)
    docs_enabled: bool = _env_bool("API_DOCS_ENABLED", True)
    force_https: bool = _env_bool("API_FORCE_HTTPS", _environment() in {"production", "prod"})
    rate_limit_per_minute: int = _env_int("API_RATE_LIMIT_PER_MINUTE", 120, 1, 100000)
    log_level: str = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

    @property
    def is_production(self) -> bool:
        return self.environment in {"production", "prod"}


settings = APISettings()
