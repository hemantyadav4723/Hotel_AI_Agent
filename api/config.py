import os
from dataclasses import dataclass


@dataclass(frozen=True)
class APISettings:
    app_name: str = "YADAV HOTEL AI AGENT PRO API"
    version: str = "1.0.0"
    prefix: str = "/api/v1"
    secret_key: str = os.getenv("API_SECRET_KEY", "CHANGE-ME-IN-PRODUCTION-USE-API-SECRET-KEY-32B")
    algorithm: str = "HS256"
    access_token_minutes: int = int(os.getenv("API_ACCESS_TOKEN_MINUTES", "60"))
    cors_origins: tuple[str, ...] = tuple(
        origin.strip() for origin in os.getenv("API_CORS_ORIGINS", "*").split(",") if origin.strip()
    ) or ("*",)
    rate_limit_per_minute: int = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "120"))
    environment: str = os.getenv("APP_ENV", "development").strip().lower() or "development"
    log_level: str = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"


settings = APISettings()

if settings.secret_key == "CHANGE-ME-IN-PRODUCTION-USE-API-SECRET-KEY-32B":
    # Development convenience only. Production deployment must set a strong
    # API_SECRET_KEY through the environment/secret manager.
    pass
