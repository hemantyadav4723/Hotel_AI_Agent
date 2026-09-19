"""Provider-neutral AI configuration foundation.

No model SDK or provider is required at this stage. Phase 8.1 only defines
configuration boundaries so a real provider can be added later without
coupling the hotel application to one vendor.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AISettings:
    enabled: bool = os.getenv("AI_AGENT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    provider: str = os.getenv("AI_AGENT_PROVIDER", "none").strip() or "none"
    api_key: str = os.getenv("AI_AGENT_API_KEY", "").strip()
    api_secret: str = os.getenv("AI_AGENT_API_SECRET", "").strip()
    model: str = os.getenv("AI_AGENT_MODEL", "").strip()
    request_timeout_seconds: float = float(os.getenv("AI_AGENT_TIMEOUT_SECONDS", "30"))
    max_input_characters: int = int(os.getenv("AI_AGENT_MAX_INPUT_CHARACTERS", "8000"))
    max_retries: int = int(os.getenv("AI_AGENT_MAX_RETRIES", "2"))
    retry_backoff_seconds: float = float(os.getenv("AI_AGENT_RETRY_BACKOFF_SECONDS", "0.25"))


settings = AISettings()
