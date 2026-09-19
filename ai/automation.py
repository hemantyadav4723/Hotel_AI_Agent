"""Controlled AI automation engine for Phase 8.10.

The engine orchestrates existing hotel business services. It does not execute
arbitrary SQL or arbitrary Python and defaults to a preview/confirmation gate
for mutating workflows.
"""
from dataclasses import asdict, dataclass
from datetime import datetime
import uuid

from ai.booking import AIBookingAutomation
from ai.context import AIRequestContext
from ai.guest_service import AIGuestServiceAgent
from database.cleaning_db import create_cleaning_task
from database.guest_service_db import add_guest_service_follow_up, escalate_guest_service_request, update_guest_service_request_status
from database.notification_db import record_notification_event
from database.permission_db import has_permission

AUTOMATION_TYPES = (
    "booking",
    "guest_request",
    "notification",
    "follow_up",
    "task",
    "escalation",
    "reminder",
    "status_update",
)

WORKFLOWS = {
    "booking_confirmation": ("booking",),
    "guest_request_follow_up": ("follow_up", "notification"),
    "guest_request_escalation": ("escalation", "notification"),
    "guest_request_completion": ("status_update", "notification"),
    "task_assignment": ("task",),
    "reminder_notification": ("reminder", "notification"),
}


@dataclass(frozen=True)
class AutomationResponse:
    status: str
    handled: bool
    message: str
    automation_id: str
    automation_type: str | None
    conversation_id: str
    confirmation_required: bool = False
    result: dict | None = None

    def to_dict(self):
        return asdict(self)


class AIAutomationEngine:
    """Deterministic, confirmation-gated automation orchestration."""

    def _conversation(self, value):
        return str(value or f"automation_{uuid.uuid4().hex}").strip()[:128]

    def _id(self):
        return f"AUTO-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]}"

    @staticmethod
    def _permission(context, module, action):
        if not has_permission(context.user_id, module, action):
            raise PermissionError(f"Permission denied: {module} - {action}.")

    @staticmethod
    def detect_type(message, automation_type=None):
        explicit = str(automation_type or "").strip().lower()
        if explicit:
            if explicit not in AUTOMATION_TYPES:
                raise ValueError("Unsupported automation type.")
            return explicit
        text = " ".join(str(message or "").strip().lower().split())
        rules = (
            ("booking", ("book", "reservation", "reserve")),
            ("guest_request", ("guest request", "service request", "housekeeping request")),
            ("follow_up", ("follow up", "follow-up", "followup")),
            ("escalation", ("escalate", "escalation", "urgent")),
            ("reminder", ("remind", "reminder")),
            ("notification", ("notify", "notification", "send message")),
            ("status_update", ("mark completed", "status update", "update status")),
            ("task", ("create task", "assign task", "task")),
        )
        for kind, phrases in rules:
            if any(p in text for p in phrases):
                return kind
        return None

    def process(self, *, message, context, automation_type=None, confirm=False,
                conversation_id=None, workflow=None, payload=None):
        conversation = self._conversation(conversation_id)
        automation_id = self._id()
        payload = dict(payload or {})
        kind = self.detect_type(message, automation_type)

        if workflow:
            workflow = str(workflow).strip().lower()
            if workflow not in WORKFLOWS:
                raise ValueError("Unsupported automation workflow.")
            steps = WORKFLOWS[workflow]
            if len(steps) > 1 and not confirm:
                return AutomationResponse("confirmation_required", True,
                    f"Workflow '{workflow}' requires confirmation before execution.", automation_id, "workflow", conversation, True,
                    {"workflow": workflow, "steps": list(steps)})
            results = []
            for step in steps:
                results.append(self._execute(step, message, context, payload, confirm))
            return AutomationResponse("completed", True, f"Workflow '{workflow}' completed.", automation_id, "workflow", conversation, False, {"workflow": workflow, "steps": results})

        if kind is None:
            return AutomationResponse("unknown_automation", False,
                "Please specify the automation to perform.", automation_id, None, conversation)

        if not confirm:
            return AutomationResponse("confirmation_required", True,
                f"The {kind.replace('_', ' ')} automation is ready. Please confirm before execution.", automation_id, kind, conversation, True,
                {"automation_type": kind, "payload": payload})

        result = self._execute(kind, message, context, payload, True)
        return AutomationResponse("completed", True, f"The {kind.replace('_', ' ')} automation completed.", automation_id, kind, conversation, False, result)

    def _execute(self, kind, message, context, payload, confirm):
        if kind == "booking":
            # The existing booking automation owns the booking-type-specific
            # permission checks (Rooms/Tables/Restaurant/Transportation).
            booking = AIBookingAutomation().process(message, context, payload.get("conversation_id"), confirm=True, **{k: v for k, v in payload.items() if k != "conversation_id"})
            return booking.to_dict()

        if kind == "guest_request":
            self._permission(context, "Hotel", "Create")
            response = AIGuestServiceAgent().process(message, context, payload.get("conversation_id"),
                guest_name=payload.get("guest_name"), customer_id=payload.get("customer_id"), room_number=payload.get("room_number"), priority=payload.get("priority", "Normal"))
            return response.to_dict()

        if kind == "notification":
            self._permission(context, "Hotel", "Create")
            event_id = record_notification_event(
                payload.get("event_type", "Booking"), payload.get("title", "Hotel notification"),
                payload.get("notification_message") or message,
                reference_type=payload.get("reference_type"), reference_id=payload.get("reference_id"),
                recipient_type=payload.get("recipient_type"), recipient_id=payload.get("recipient_id"),
                recipient_name=payload.get("recipient_name"), recipient_mobile=payload.get("recipient_mobile"),
                recipient_email=payload.get("recipient_email"), hotel_id=context.hotel_id,
                idempotency_key=payload.get("idempotency_key"))
            return {"event_id": event_id}

        request_id = payload.get("request_id")
        if kind in {"follow_up", "escalation", "status_update"} and not request_id:
            raise ValueError("request_id is required for this automation.")

        if kind == "follow_up":
            self._permission(context, "Hotel", "Update")
            add_guest_service_follow_up(request_id, follow_up_at=payload.get("follow_up_at"), notes=payload.get("notes") or message, status=payload.get("status", "Pending"), hotel_id=context.hotel_id)
            return {"request_id": request_id, "follow_up_status": "Pending"}

        if kind == "escalation":
            self._permission(context, "Hotel", "Update")
            escalate_guest_service_request(request_id, payload.get("reason") or message, hotel_id=context.hotel_id)
            return {"request_id": request_id, "escalated": True}

        if kind == "status_update":
            self._permission(context, "Hotel", "Update")
            status = str(payload.get("status") or "Completed")
            update_guest_service_request_status(request_id, status, hotel_id=context.hotel_id)
            return {"request_id": request_id, "status": status}

        if kind == "task":
            self._permission(context, "Hotel", "Create")
            entity_type = str(payload.get("entity_type") or "Guest Service")
            entity_id = str(payload.get("entity_id") or payload.get("request_id") or "AI")
            task_id = create_cleaning_task(entity_type, entity_id, payload.get("reason") or message,
                hotel_id=context.hotel_id, assigned_staff_id=payload.get("assigned_staff_id"), notes=payload.get("notes"))
            return {"task_id": task_id, "entity_type": entity_type, "entity_id": entity_id}

        if kind == "reminder":
            self._permission(context, "Hotel", "Create")
            event_id = record_notification_event(
                payload.get("event_type", "Booking"), payload.get("title", "Hotel reminder"),
                payload.get("notification_message") or message,
                reference_type=payload.get("reference_type"), reference_id=payload.get("reference_id"),
                recipient_type=payload.get("recipient_type"), recipient_id=payload.get("recipient_id"),
                recipient_name=payload.get("recipient_name"), recipient_mobile=payload.get("recipient_mobile"),
                recipient_email=payload.get("recipient_email"), hotel_id=context.hotel_id,
                idempotency_key=payload.get("idempotency_key"),)
            return {"event_id": event_id, "reminder_status": "queued"}

        raise ValueError("Unsupported automation type.")


automation_engine = AIAutomationEngine()
