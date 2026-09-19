"""AI memory and context orchestration for Phase 8.15.

Short-term conversation memory is bounded and expires automatically. Hotel and
booking/stay context are resolved through existing AI/business services; no
SQLite or direct database access is performed here. Long-term guest preference
context is read from the existing personalization/CRM layer.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

from ai.context import AIRequestContext
from ai.personalization import personalization_service
from ai.service import AIRequest, service as ai_service


@dataclass(frozen=True)
class MemoryEntry:
    role: str
    content: str
    created_at: str
    expires_at: str


@dataclass(frozen=True)
class AIMemoryResponse:
    status: str
    conversation_id: str
    hotel_id: int
    context: dict[str, Any]
    short_term_memory: list[dict[str, Any]]
    long_term_guest_preferences: dict[str, Any]
    expiration: dict[str, Any]
    ai_response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AIMemoryService:
    """Bounded request-context memory with explicit hotel scoping and expiry."""

    DEFAULT_TTL_MINUTES = 30
    MAX_ENTRIES = 20

    def __init__(self, ttl_minutes: int | None = None):
        self.ttl_minutes = max(1, int(ttl_minutes or self.DEFAULT_TTL_MINUTES))
        self._store: dict[tuple[int, str], list[MemoryEntry]] = {}
        self._lock = RLock()

    @staticmethod
    def _conversation_id(value: str | None) -> str:
        result = str(value or "").strip()
        if not result:
            raise ValueError("Conversation ID is required for memory operations.")
        if len(result) > 128:
            raise ValueError("Conversation ID is too long.")
        return result

    def _purge(self, key: tuple[int, str], now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        entries = self._store.get(key, [])
        active = [entry for entry in entries if datetime.fromisoformat(entry.expires_at) > now]
        if active:
            self._store[key] = active[-self.MAX_ENTRIES :]
        else:
            self._store.pop(key, None)

    def remember(self, context: AIRequestContext, conversation_id: str, role: str, content: str) -> None:
        conversation_id = self._conversation_id(conversation_id)
        role = str(role or "user").strip().lower()
        if role not in {"user", "assistant", "system"}:
            raise ValueError("Unsupported memory role.")
        content = str(content or "").strip()
        if not content:
            raise ValueError("Memory content is required.")
        now = datetime.now(timezone.utc)
        entry = MemoryEntry(
            role=role,
            content=content[:4000],
            created_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=self.ttl_minutes)).isoformat(),
        )
        key = (int(context.hotel_id), conversation_id)
        with self._lock:
            self._purge(key, now)
            self._store.setdefault(key, []).append(entry)
            self._store[key] = self._store[key][-self.MAX_ENTRIES :]

    def get_short_term(self, context: AIRequestContext, conversation_id: str) -> list[dict[str, Any]]:
        conversation_id = self._conversation_id(conversation_id)
        key = (int(context.hotel_id), conversation_id)
        with self._lock:
            self._purge(key)
            return [asdict(entry) for entry in self._store.get(key, [])]

    def clear(self, context: AIRequestContext, conversation_id: str) -> None:
        conversation_id = self._conversation_id(conversation_id)
        with self._lock:
            self._store.pop((int(context.hotel_id), conversation_id), None)

    def build_context(
        self,
        *,
        context: AIRequestContext,
        conversation_id: str,
        customer_id: str | None = None,
    ) -> dict[str, Any]:
        conversation_id = self._conversation_id(conversation_id)
        short_term = self.get_short_term(context, conversation_id)
        payload: dict[str, Any] = {
            "hotel_context": {"hotel_id": int(context.hotel_id)},
            "user_context": context.public_dict(),
            "current_booking_context": {},
            "current_stay_context": {},
            "short_term_conversation_memory": short_term,
        }
        long_term: dict[str, Any] = {}
        if customer_id:
            personalization = personalization_service.build(
                context=context,
                customer_id=customer_id,
            ).to_dict()
            long_term = {
                "guest_preferences": personalization.get("guest_preferences", {}),
                "service_preferences": personalization.get("service_preferences", {}),
                "loyalty_context": personalization.get("loyalty_context", {}),
            }
            payload["current_booking_context"] = {"customer_id": str(customer_id).strip().upper()}
            payload["current_stay_context"] = {
                "stay_history": personalization.get("stay_history", {})
            }
        payload["long_term_guest_preferences"] = long_term
        return payload

    def process(
        self,
        *,
        message: str,
        context: AIRequestContext,
        conversation_id: str | None = None,
        customer_id: str | None = None,
    ) -> AIMemoryResponse:
        text = str(message or "").strip()
        if not text:
            raise ValueError("Memory message is required.")
        cid = self._conversation_id(conversation_id)
        self.remember(context, cid, "user", text)
        context_payload = self.build_context(
            context=context,
            conversation_id=cid,
            customer_id=customer_id,
        )
        response = ai_service.process(AIRequest(message=text, context=context, conversation_id=cid))
        self.remember(context, cid, "assistant", response.message)
        entries = self.get_short_term(context, cid)
        return AIMemoryResponse(
            status="ready",
            conversation_id=cid,
            hotel_id=int(context.hotel_id),
            context=context_payload,
            short_term_memory=entries,
            long_term_guest_preferences=context_payload["long_term_guest_preferences"],
            expiration={
                "ttl_minutes": self.ttl_minutes,
                "expires_at": entries[-1]["expires_at"] if entries else None,
            },
            ai_response=response.to_dict(),
        )


memory_service = AIMemoryService()
