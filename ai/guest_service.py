"""AI Guest Service Agent for Phase 8.5.

The agent handles the locked guest-service areas through a controlled
hotel-scoped business layer. It does not execute SQL or arbitrary code.
"""

from dataclasses import asdict, dataclass
import re
import uuid

from ai.context import AIRequestContext
from database.guest_service_db import (
    add_guest_service_follow_up,
    create_guest_service_request,
    escalate_guest_service_request,
    get_guest_service_request,
    update_guest_service_request_status,
)
from database.permission_db import has_permission


@dataclass(frozen=True)
class GuestServiceResponse:
    status: str
    handled: bool
    message: str
    service_type: str | None
    conversation_id: str
    request_id: str | None = None
    follow_up_required: bool = False
    escalation_required: bool = False

    def to_dict(self):
        return asdict(self)


class AIGuestServiceAgent:
    SERVICE_PATTERNS = (
        ("Housekeeping", ("housekeeping", "clean my room", "room cleaning", "cleaning my room", "clean room", "towel", "towels", "pillow", "blanket")),
        ("Room Service", ("room service", "food to my room", "send food to room", "in room dining")),
        ("Maintenance", ("maintenance", "repair", "broken", "not working", "fix the", "ac not working", "air conditioner")),
        ("Laundry", ("laundry", "wash clothes", "clothes washing", "dry cleaning")),
        ("Bell/Luggage", ("bell", "luggage", "baggage", "carry my bags", "carry luggage")),
        ("Transportation", ("transportation", "transport", "airport transfer", "airport pickup", "taxi", "cab", "ride")),
        ("Restaurant", ("restaurant request", "restaurant service", "restaurant", "food order", "dining request")),
    )

    def _normalize(self, message):
        return " ".join(str(message or "").strip().lower().split())

    def detect_service_type(self, message):
        text = self._normalize(message)
        for service_type, phrases in self.SERVICE_PATTERNS:
            if any(phrase in text for phrase in phrases):
                return service_type
        return "General"

    @staticmethod
    def _extract_request_id(text):
        match = re.search(r"\bGSR-\d{8}-\d{5}\b", text, re.IGNORECASE)
        return match.group(0).upper() if match else None

    @staticmethod
    def _extract_room_number(text):
        match = re.search(r"\b(?:room|rm)\s*#?\s*([A-Z0-9][A-Z0-9-]{0,9})\b", text, re.IGNORECASE)
        return match.group(1).upper() if match else None

    @staticmethod
    def _permission(context, action):
        if not has_permission(context.user_id, "Hotel", action):
            raise PermissionError(f"Permission denied: Hotel - {action}.")

    def process(
        self,
        message: str,
        context: AIRequestContext,
        conversation_id: str | None = None,
        guest_name: str | None = None,
        customer_id: str | None = None,
        room_number: str | None = None,
        priority: str = "Normal",
    ) -> GuestServiceResponse:
        text = self._normalize(message)
        conversation = conversation_id or f"guest_service_{uuid.uuid4().hex}"
        if not text:
            return GuestServiceResponse("invalid_request", False, "Please describe the guest service you need.", None, conversation)

        request_id = self._extract_request_id(text)

        if request_id and any(token in text for token in ("status", "where is", "update me")):
            self._permission(context, "View")
            row = get_guest_service_request(request_id, context.hotel_id)
            if row is None:
                return GuestServiceResponse("not_found", False, "I could not find that guest service request in this hotel.", None, conversation, request_id=request_id)
            return GuestServiceResponse(
                "handled", True,
                f"Request {request_id} is currently {row['request_status']}.",
                row["service_type"], conversation, request_id=request_id,
                follow_up_required=row["follow_up_status"] == "Pending",
                escalation_required=bool(row["escalated"]),
            )

        if request_id and any(token in text for token in ("follow up", "follow-up", "followup")):
            self._permission(context, "Update")
            add_guest_service_follow_up(request_id, notes=text, status="Pending", hotel_id=context.hotel_id)
            return GuestServiceResponse("handled", True, f"Follow-up has been recorded for request {request_id}.", None, conversation, request_id=request_id, follow_up_required=True)

        if request_id and any(token in text for token in ("escalate", "escalation", "manager", "urgent")):
            self._permission(context, "Update")
            reason = text
            escalate_guest_service_request(request_id, reason, hotel_id=context.hotel_id)
            return GuestServiceResponse("escalated", True, f"Request {request_id} has been escalated to the hotel team.", None, conversation, request_id=request_id, escalation_required=True)

        if request_id and any(token in text for token in ("complete", "completed", "cancel")):
            self._permission(context, "Update")
            status = "Completed" if "complete" in text else "Cancelled"
            update_guest_service_request_status(request_id, status, hotel_id=context.hotel_id)
            return GuestServiceResponse("handled", True, f"Request {request_id} is now {status}.", None, conversation, request_id=request_id)

        service_type = self.detect_service_type(text)
        inferred_room = room_number or self._extract_room_number(text)
        if not any((guest_name, customer_id, inferred_room)):
            return GuestServiceResponse(
                "information_required", True,
                "I can create the guest service request. Please provide the guest name, customer ID, or room number so the request can be routed correctly.",
                service_type, conversation,
            )

        self._permission(context, "Create")
        created_id = create_guest_service_request(
            service_type=service_type,
            description=text,
            customer_id=customer_id,
            guest_name=guest_name,
            room_number=inferred_room,
            priority=priority,
            hotel_id=context.hotel_id,
        )
        return GuestServiceResponse(
            "created", True,
            f"Your {service_type.lower()} request has been recorded as {created_id}. The hotel team can now process it.",
            service_type, conversation, request_id=created_id,
        )


guest_service_agent = AIGuestServiceAgent()
