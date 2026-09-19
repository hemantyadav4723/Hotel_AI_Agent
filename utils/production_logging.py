"""Central production logging configuration.

Application, API and error logs are separated into rotating files. Secrets and
request bodies are never logged by this layer.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5
_CONFIGURED = False


def configure_production_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").strip().upper(), logging.INFO)
    log_dir = Path(os.getenv("APP_LOG_DIR", "logs"))
    file_logging = os.getenv("APP_FILE_LOGGING", "true").strip().lower() in {"1", "true", "yes", "on"}
    formatter = logging.Formatter(_LOG_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    if file_logging:
        log_dir.mkdir(parents=True, exist_ok=True)
        specs = {
            "yadav_hotel": "application.log",
            "hotel_ai_agent": "application.log",
            "yadav_hotel.api": "api.log",
            "yadav_hotel.error": "error.log",
        }
        for logger_name, filename in specs.items():
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)
            logger.propagate = logger_name == "yadav_hotel"
            if any(isinstance(h, RotatingFileHandler) and Path(getattr(h, "baseFilename", "")).name == filename for h in logger.handlers):
                continue
            handler = RotatingFileHandler(log_dir / filename, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    _CONFIGURED = True


__all__ = ["configure_production_logging"]
