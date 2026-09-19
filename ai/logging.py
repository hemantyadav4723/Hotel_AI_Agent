"""Production-safe AI logging configuration.

Configures the dedicated AI logger without writing credentials or raw prompts to
logs. Operational AI events remain available through the observability/audit layer.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "yadav_hotel.ai"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5


def configure_ai_logging() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").strip().upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    log_dir = os.getenv("AI_LOG_DIR", "logs")
    if os.getenv("AI_FILE_LOGGING", "true").strip().lower() in {"1", "true", "yes", "on"}:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(path / "ai.log", maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def ai_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)
