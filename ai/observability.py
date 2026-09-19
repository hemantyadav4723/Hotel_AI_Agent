"""AI observability and audit layer for Phase 8.19.

The service keeps a bounded operational history in memory and mirrors important
AI events into the existing hotel-scoped audit system. Payloads are deliberately
sanitized so prompts, responses, credentials, and other sensitive values are not
copied wholesale into audit logs.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
import time
from typing import Any

from ai.context import AIRequestContext
from database.audit_db import get_request_id, log_activity


EVENT_TYPES = (
    "ai_request", "ai_response", "conversation", "tool_execution", "ai_action",
    "handoff", "integration", "error", "performance",
)
MAX_EVENTS = 1000
MAX_TEXT = 500
MAX_VALUE = 200
_SENSITIVE_KEYS = re.compile(r"(password|passwd|secret|token|api[_-]?key|authorization|cookie|cvv|otp|card[_-]?number|credential)", re.I)


@dataclass(frozen=True)
class ObservabilityEvent:
    event_id: str
    event_type: str
    hotel_id: int
    user_id: str | None
    role: str | None
    conversation_id: str | None
    request_id: str | None
    status: str
    duration_ms: float | None
    usage: dict[str, int]
    details: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AIObservabilityService:
    MAX_EVENTS = MAX_EVENTS

    def __init__(self) -> None:
        self._events: list[ObservabilityEvent] = []
        self._sequence = 0

    def registry(self) -> dict[str, Any]:
        return {
            "event_types": list(EVENT_TYPES),
            "hotel_scoped": True,
            "audit_backed": True,
            "request_correlation": True,
            "sensitive_data_protection": True,
            "bounded_history": True,
            "usage_tracking": True,
            "performance_tracking": True,
        }

    def start_timer(self) -> float:
        return time.perf_counter()

    def elapsed_ms(self, started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    def record_request(self, context: AIRequestContext, message: str, conversation_id: str | None = None) -> ObservabilityEvent:
        return self._record(
            context, "ai_request", "INFO", conversation_id,
            details={"message": self._text(message)},
            usage=self._usage(message),
        )

    def record_response(self, context: AIRequestContext, response: Any, duration_ms: float | None = None) -> ObservabilityEvent:
        data = response.to_dict() if hasattr(response, "to_dict") else dict(response or {})
        message = data.get("message", "")
        conversation_id = data.get("conversation_id")
        details = {
            "status": data.get("status"),
            "handled": bool(data.get("handled", False)),
            "intent": data.get("intent"),
            "provider": data.get("provider"),
            "model": data.get("model"),
            "message": self._text(message),
            "tool_count": len(data.get("tool_calls") or []),
        }
        return self._record(context, "ai_response", "SUCCESS", conversation_id, duration_ms, details, self._usage(message))

    def record_conversation(self, context: AIRequestContext, conversation_id: str, action: str) -> ObservabilityEvent:
        return self._record(context, "conversation", "INFO", conversation_id, details={"action": self._text(action, 100)})

    def record_tool(self, context: AIRequestContext, tool_name: str, status: str, duration_ms: float | None = None, conversation_id: str | None = None, error: str | None = None) -> ObservabilityEvent:
        details = {"tool": self._text(tool_name, 100)}
        if error:
            details["error"] = self._text(error)
        return self._record(context, "tool_execution", "SUCCESS" if status == "success" else "FAILED", conversation_id, duration_ms, details)

    def record_action(self, context: AIRequestContext, action: str, status: str = "SUCCESS", conversation_id: str | None = None) -> ObservabilityEvent:
        return self._record(context, "ai_action", status, conversation_id, details={"action": self._text(action, 100)})

    def record_handoff(self, context: AIRequestContext, action: str, conversation_id: str | None = None, status: str = "SUCCESS") -> ObservabilityEvent:
        return self._record(context, "handoff", status, conversation_id, details={"action": self._text(action, 100)})

    def record_integration(self, context: AIRequestContext, integration: str, operation: str, status: str = "SUCCESS", conversation_id: str | None = None, duration_ms: float | None = None) -> ObservabilityEvent:
        return self._record(context, "integration", status, conversation_id, duration_ms, {"integration": self._text(integration, 100), "operation": self._text(operation, 100)})

    def record_error(self, context: AIRequestContext, error_type: str, message: str, conversation_id: str | None = None) -> ObservabilityEvent:
        return self._record(context, "error", "FAILED", conversation_id, details={"error_type": self._text(error_type, 100), "message": self._text(message)})

    def record_performance(self, context: AIRequestContext, operation: str, duration_ms: float, conversation_id: str | None = None) -> ObservabilityEvent:
        return self._record(context, "performance", "SUCCESS", conversation_id, duration_ms, {"operation": self._text(operation, 100)})

    def history(self, context: AIRequestContext, conversation_id: str | None = None, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        try:
            limit = max(1, min(int(limit), 200))
        except (TypeError, ValueError):
            limit = 100
        if event_type and event_type not in EVENT_TYPES:
            raise ValueError("Invalid observability event type.")
        rows = [event for event in reversed(self._events) if event.hotel_id == context.hotel_id]
        if conversation_id:
            rows = [event for event in rows if event.conversation_id == conversation_id]
        if event_type:
            rows = [event for event in rows if event.event_type == event_type]
        return [event.to_dict() for event in rows[:limit]]

    def _record(self, context: AIRequestContext, event_type: str, status: str, conversation_id: str | None = None, duration_ms: float | None = None, details: dict[str, Any] | None = None, usage: dict[str, int] | None = None) -> ObservabilityEvent:
        if event_type not in EVENT_TYPES:
            raise ValueError("Invalid observability event type.")
        self._sequence += 1
        event = ObservabilityEvent(
            event_id=f"aiev_{self._sequence:08d}",
            event_type=event_type,
            hotel_id=int(context.hotel_id),
            user_id=str(context.user_id) if context.user_id is not None else None,
            role=self._text(context.role, 50) if context.role else None,
            conversation_id=self._text(conversation_id, 128) if conversation_id else None,
            request_id=get_request_id(),
            status=status,
            duration_ms=duration_ms,
            usage=usage or {},
            details=self._sanitize(details or {}),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._events.append(event)
        if len(self._events) > self.MAX_EVENTS:
            del self._events[: len(self._events) - self.MAX_EVENTS]
        self._audit(event)
        return event

    def _audit(self, event: ObservabilityEvent) -> None:
        try:
            log_activity(
                module="AI_Observability",
                action="CREATE",
                record_type=event.event_type,
                record_id=event.event_id,
                status=event.status if event.status in {"SUCCESS", "FAILED", "INFO"} else "INFO",
                details=self._text(str({"conversation_id": event.conversation_id, "duration_ms": event.duration_ms, "details": event.details, "usage": event.usage}), 1200),
                actor_user_id=event.user_id,
                actor_role=event.role,
                hotel_id=event.hotel_id,
            )
        except Exception:
            # Observability must never break the underlying hotel operation.
            pass

    def _usage(self, text: Any) -> dict[str, int]:
        value = str(text or "")
        # Provider-neutral usage foundation: exact provider token counts are
        # recorded later when a provider exposes them; character/word counts are
        # deterministic local measurements and are explicitly labelled estimates.
        return {"input_characters": len(value), "input_words": len(value.split()), "estimated": 1}

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                key_text = str(key)
                result[key_text] = "[REDACTED]" if _SENSITIVE_KEYS.search(key_text) else self._sanitize(item)
            return result
        if isinstance(value, list):
            return [self._sanitize(item) for item in value[:20]]
        if isinstance(value, str):
            return self._text(value)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return self._text(str(value))

    @staticmethod
    def _text(value: Any, limit: int = MAX_TEXT) -> str:
        text = " ".join(str(value or "").split())
        return text[:limit]


observability = AIObservabilityService()
