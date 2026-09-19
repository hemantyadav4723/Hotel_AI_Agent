"""Human handoff boundary for Phase 8.18.

Keeps escalation decisions and handoff state hotel-scoped, transfers the
conversation context supplied by the caller, supports human takeover/AI pause,
and records lifecycle events through the existing audit layer.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import re
import uuid
from typing import Any

from ai.context import AIRequestContext
from database.audit_db import log_activity
from ai.observability import observability


HANDOFF_STATUSES = ("requested", "assigned", "in_progress", "resolved", "cancelled")
PRIORITIES = ("low", "normal", "high", "urgent")
TARGETS = ("reception", "staff", "manager")

_REASON_PATTERNS = (
    ("emergency", re.compile(r"\b(emergency|urgent help|medical emergency|fire|police|danger)\b", re.I)),
    ("complaint", re.compile(r"\b(complaint|complain|manager|very unhappy|not satisfied)\b", re.I)),
    ("sensitive_request", re.compile(r"\b(password|full card number|cvv|otp|sensitive|confidential)\b", re.I)),
    ("human_request", re.compile(r"\b(human|person|staff|receptionist|manager|agent)\b.*\b(talk|speak|connect|transfer)\b", re.I)),
    ("approval_required", re.compile(r"\b(approve|approval|authorize|authorisation|authorization)\b", re.I)),
)


@dataclass(frozen=True)
class HandoffRecord:
    handoff_id: str
    hotel_id: int
    conversation_id: str
    requested_by_user_id: str
    requested_by_role: str
    target: str
    reason: str
    priority: str
    status: str
    created_at: str
    updated_at: str
    human_user_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    resolution: str | None = None
    ai_paused: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HandoffDecision:
    should_handoff: bool
    reason: str
    priority: str
    target: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HumanHandoffService:
    MAX_RECORDS = 1000
    MAX_CONTEXT_ITEMS = 20
    MAX_CONTEXT_VALUE = 4000

    def __init__(self) -> None:
        self._records: dict[tuple[int, str], HandoffRecord] = {}

    def registry(self) -> dict[str, Any]:
        return {
            "targets": list(TARGETS),
            "priorities": list(PRIORITIES),
            "statuses": list(HANDOFF_STATUSES),
            "hotel_scoped": True,
            "context_transfer": True,
            "human_takeover": True,
            "ai_pause": True,
            "audit_enabled": True,
        }

    def detect(self, message: str, requested: bool = False, priority: str = "normal") -> HandoffDecision:
        text = " ".join(str(message or "").strip().split())
        if not text:
            raise ValueError("Message is required for handoff detection.")
        normalized_priority = self._priority(priority)
        if requested:
            return HandoffDecision(True, "human_request", normalized_priority, "reception", "Human assistance was requested.")
        for reason, pattern in _REASON_PATTERNS:
            if pattern.search(text):
                target = "manager" if reason in {"complaint", "approval_required"} else "reception"
                detected_priority = "urgent" if reason == "emergency" else normalized_priority
                return HandoffDecision(True, reason, detected_priority, target, f"Escalation condition detected: {reason.replace('_', ' ')}.")
        return HandoffDecision(False, "none", normalized_priority, "reception", "No human handoff condition detected.")

    def _priority(self, value: str) -> str:
        normalized = str(value or "normal").strip().lower()
        aliases = {"medium": "normal", "critical": "urgent"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in PRIORITIES:
            raise ValueError("Invalid handoff priority.")
        return normalized

    def _target(self, value: str) -> str:
        normalized = str(value or "reception").strip().lower().replace(" ", "_")
        aliases = {"front_desk": "reception", "housekeeping": "staff", "restaurant": "staff"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in TARGETS:
            raise ValueError("Invalid handoff target.")
        return normalized

    def _context(self, value: dict[str, Any] | None) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("Handoff context must be an object.")
        if len(value) > self.MAX_CONTEXT_ITEMS:
            raise ValueError("Handoff context contains too many items.")
        result: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = str(key).strip()
            if not safe_key or len(safe_key) > 100:
                raise ValueError("Invalid handoff context key.")
            if isinstance(item, (str, int, float, bool)) or item is None:
                if isinstance(item, str) and len(item) > self.MAX_CONTEXT_VALUE:
                    raise ValueError("Handoff context value is too long.")
                result[safe_key] = item
            else:
                raise ValueError("Handoff context values must be scalar.")
        return result

    def _record(self, context: AIRequestContext, conversation_id: str) -> HandoffRecord | None:
        return self._records.get((context.hotel_id, conversation_id))

    def request(
        self,
        context: AIRequestContext,
        conversation_id: str,
        reason: str,
        priority: str = "normal",
        target: str = "reception",
        handoff_context: dict[str, Any] | None = None,
    ) -> HandoffRecord:
        cid = str(conversation_id or "").strip()
        if not cid or len(cid) > 128:
            raise ValueError("conversation_id is required.")
        reason_value = str(reason or "").strip()
        if not reason_value or len(reason_value) > 200:
            raise ValueError("Handoff reason is required and must be at most 200 characters.")
        now = datetime.now(timezone.utc).isoformat()
        existing = self._record(context, cid)
        if existing and existing.status in {"requested", "assigned", "in_progress"}:
            return existing
        record = HandoffRecord(
            handoff_id=uuid.uuid4().hex,
            hotel_id=context.hotel_id,
            conversation_id=cid,
            requested_by_user_id=context.user_id,
            requested_by_role=context.role,
            target=self._target(target),
            reason=reason_value,
            priority=self._priority(priority),
            status="requested",
            created_at=now,
            updated_at=now,
            context=self._context(handoff_context),
        )
        self._records[(context.hotel_id, cid)] = record
        self._trim()
        self._audit(context, "CREATE", record, "Handoff requested")
        observability.record_handoff(context, "requested", cid, "SUCCESS")
        return record

    def assign(self, context: AIRequestContext, conversation_id: str, human_user_id: str, target: str | None = None) -> HandoffRecord:
        record = self._require(context, conversation_id)
        human_id = str(human_user_id or "").strip()
        if not human_id:
            raise ValueError("human_user_id is required.")
        updated = self._replace(record, status="assigned", human_user_id=human_id, target=self._target(target or record.target))
        self._save(context, updated, "STATUS_CHANGE", "Handoff assigned to human.")
        observability.record_handoff(context, "assigned", record.conversation_id, "SUCCESS")
        return updated

    def takeover(self, context: AIRequestContext, conversation_id: str, human_user_id: str) -> HandoffRecord:
        record = self._require(context, conversation_id)
        human_id = str(human_user_id or "").strip()
        if not human_id:
            raise ValueError("human_user_id is required.")
        updated = self._replace(record, status="in_progress", human_user_id=human_id, ai_paused=True)
        self._save(context, updated, "STATUS_CHANGE", "Human takeover started; AI paused.")
        observability.record_handoff(context, "takeover", record.conversation_id, "SUCCESS")
        return updated

    def resolve(self, context: AIRequestContext, conversation_id: str, resolution: str, update_context: dict[str, Any] | None = None) -> HandoffRecord:
        record = self._require(context, conversation_id)
        text = str(resolution or "").strip()
        if not text or len(text) > self.MAX_CONTEXT_VALUE:
            raise ValueError("Resolution is required and must be at most 4000 characters.")
        merged = dict(record.context)
        merged.update(self._context(update_context))
        updated = self._replace(record, status="resolved", resolution=text, context=merged, ai_paused=False)
        self._save(context, updated, "STATUS_CHANGE", "Human handoff resolved and AI context updated.")
        observability.record_handoff(context, "resolved", record.conversation_id, "SUCCESS")
        return updated

    def cancel(self, context: AIRequestContext, conversation_id: str) -> HandoffRecord:
        record = self._require(context, conversation_id)
        updated = self._replace(record, status="cancelled", ai_paused=False)
        self._save(context, updated, "CANCEL", "Human handoff cancelled.")
        observability.record_handoff(context, "cancelled", record.conversation_id, "SUCCESS")
        return updated

    def get(self, context: AIRequestContext, conversation_id: str) -> HandoffRecord:
        return self._require(context, conversation_id)

    def _require(self, context: AIRequestContext, conversation_id: str) -> HandoffRecord:
        cid = str(conversation_id or "").strip()
        record = self._record(context, cid)
        if record is None:
            raise ValueError("Handoff not found in this hotel scope.")
        return record

    def _replace(self, record: HandoffRecord, **changes: Any) -> HandoffRecord:
        return HandoffRecord(**{**record.to_dict(), "updated_at": datetime.now(timezone.utc).isoformat(), **changes})

    def _save(self, context: AIRequestContext, record: HandoffRecord, action: str, details: str) -> None:
        self._records[(context.hotel_id, record.conversation_id)] = record
        self._audit(context, action, record, details)

    def _audit(self, context: AIRequestContext, action: str, record: HandoffRecord, details: str) -> None:
        log_activity(
            module="AI_Human_Handoff",
            action=action,
            record_type="handoff",
            record_id=record.handoff_id,
            status="SUCCESS",
            details=f"{details}; reason={record.reason}; priority={record.priority}; target={record.target}; conversation_id={record.conversation_id}",
            actor_user_id=context.user_id,
            actor_username=context.username,
            actor_role=context.role,
            hotel_id=context.hotel_id,
        )

    def _trim(self) -> None:
        if len(self._records) <= self.MAX_RECORDS:
            return
        oldest = sorted(self._records.items(), key=lambda item: item[1].updated_at)[: len(self._records) - self.MAX_RECORDS]
        for key, _ in oldest:
            self._records.pop(key, None)


human_handoff = HumanHandoffService()
