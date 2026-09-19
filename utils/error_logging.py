"""Centralized logging for intentionally non-blocking operations."""

import logging


def log_non_blocking_error(operation: str, exc: Exception) -> None:
    """Record an optional-operation failure without changing the caller flow."""
    logging.getLogger("hotel_ai_agent").warning(
        "%s: %s", operation, exc, exc_info=True
    )
