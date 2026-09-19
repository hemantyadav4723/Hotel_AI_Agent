"""AI-driven notification and proactive automation layer for Phase 8.11.

This module evaluates supported hotel events and records notification events
through the existing notification/business layer. It does not send external
messages directly and does not access SQLite directly.
"""
from dataclasses import asdict, dataclass
from datetime import datetime
import uuid

from database.notification_db import get_notifications, record_notification_event
from database.permission_db import has_permission

SUPPORTED_TRIGGERS = (
    "booking_created",
    "check_in",
    "check_out",
    "low_inventory",
    "guest_complaint",
    "transportation_request",
    "event",
    "follow_up",
)

TRIGGER_DEFINITIONS = {
    "booking_created": {
        "event_type": "Booking",
        "title": "Booking Confirmation",
        "message": "Your booking has been created successfully.",
    },
    "check_in": {
        "event_type": "Check-in",
        "title": "Welcome to the Hotel",
        "message": "Welcome. Your check-in has been completed successfully.",
    },
    "check_out": {
        "event_type": "Check-out",
        "title": "Thank You for Staying With Us",
        "message": "Thank you for staying with us. We would appreciate your feedback.",
    },
    "low_inventory": {
        "event_type": "Low Stock",
        "title": "Low Stock Alert",
        "message": "An inventory item has reached its low-stock threshold.",
    },
    "guest_complaint": {
        "event_type": "Feedback",
        "title": "Guest Complaint Escalation",
        "message": "A guest complaint requires staff attention.",
    },
    "transportation_request": {
        "event_type": "Transportation",
        "title": "Transportation Request",
        "message": "A transportation request requires processing.",
    },
    "event": {
        "event_type": "Booking",
        "title": "Hotel Event Notification",
        "message": "A hotel event triggered a proactive notification.",
    },
    "follow_up": {
        "event_type": "Feedback",
        "title": "Guest Follow-up",
        "message": "A guest follow-up notification is due.",
    },
}


@dataclass(frozen=True)
class ProactiveNotificationResponse:
    status: str
    handled: bool
    trigger: str
    message: str
    notification_id: str | None = None
    conversation_id: str | None = None
    result: dict | None = None

    def to_dict(self):
        return asdict(self)


class AIProactiveNotificationEngine:
    """Controlled event-to-notification automation."""

    @staticmethod
    def _conversation(value):
        return str(value or f"proactive_{uuid.uuid4().hex}").strip()[:128]

    @staticmethod
    def _require_permission(user_id):
        if not has_permission(user_id, "Hotel", "Create"):
            raise PermissionError("Permission denied: Hotel - Create.")

    @staticmethod
    def _normalize_trigger(trigger):
        value = "_".join(str(trigger or "").strip().lower().replace("-", " ").split())
        if value not in SUPPORTED_TRIGGERS:
            raise ValueError(
                "Unsupported proactive trigger. Supported triggers: "
                + ", ".join(SUPPORTED_TRIGGERS)
            )
        return value

    def available_triggers(self):
        return [
            {
                "trigger": trigger,
                "event_type": TRIGGER_DEFINITIONS[trigger]["event_type"],
                "description": TRIGGER_DEFINITIONS[trigger]["title"],
            }
            for trigger in SUPPORTED_TRIGGERS
        ]

    def trigger(self, *, trigger, hotel_id, user_id, payload=None, confirm=False,
                conversation_id=None):
        trigger = self._normalize_trigger(trigger)
        payload = dict(payload or {})
        conversation = self._conversation(conversation_id)

        if not confirm:
            return ProactiveNotificationResponse(
                status="confirmation_required",
                handled=True,
                trigger=trigger,
                message=f"The {trigger.replace('_', ' ')} notification is ready. Please confirm before creating it.",
                conversation_id=conversation,
                result={"event_type": TRIGGER_DEFINITIONS[trigger]["event_type"]},
            )

        self._require_permission(user_id)
        definition = TRIGGER_DEFINITIONS[trigger]
        title = str(payload.get("title") or definition["title"]).strip()
        message = str(payload.get("message") or definition["message"]).strip()
        reference_type = payload.get("reference_type")
        reference_id = payload.get("reference_id")
        idempotency_key = payload.get("idempotency_key")
        if not idempotency_key:
            idempotency_key = (
                f"AI-PROACTIVE:{hotel_id}:{trigger}:"
                f"{reference_type or ''}:{reference_id or ''}:"
                f"{payload.get('event_key') or datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            )

        notification_id = record_notification_event(
            definition["event_type"],
            title,
            message,
            reference_type=reference_type,
            reference_id=reference_id,
            recipient_type=payload.get("recipient_type"),
            recipient_id=payload.get("recipient_id"),
            recipient_name=payload.get("recipient_name"),
            recipient_mobile=payload.get("recipient_mobile"),
            recipient_email=payload.get("recipient_email"),
            hotel_id=hotel_id,
            idempotency_key=idempotency_key,
        )
        return ProactiveNotificationResponse(
            status="queued",
            handled=True,
            trigger=trigger,
            message="Proactive notification event queued.",
            notification_id=notification_id,
            conversation_id=conversation,
            result={
                "event_type": definition["event_type"],
                "channels": ["IN_APP", "EMAIL", "SMS", "WHATSAPP", "VOICE"],
                "delivery_model": "existing_notification_layer",
            },
        )

    def status(self, *, hotel_id, event_id=None, reference_id=None, limit=50):
        rows = get_notifications(hotel_id=hotel_id, limit=limit)
        if event_id:
            rows = [row for row in rows if row["event_id"] == str(event_id).strip().upper()]
        if reference_id:
            rows = [row for row in rows if str(row["reference_id"] or "") == str(reference_id)]
        return [dict(row) for row in rows]


proactive_notification_engine = AIProactiveNotificationEngine()
