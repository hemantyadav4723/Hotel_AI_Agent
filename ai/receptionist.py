"""AI Hotel Receptionist layer for Phase 8.4.

This layer provides a controlled receptionist-facing conversation boundary on
 top of the Phase 8.3 agent core. It is intentionally informational/assistive:
booking, table-booking, guest-service, complaint mutation, and human handoff
execution are not performed here. Those actions remain behind later phases and
existing business APIs.
"""

from dataclasses import asdict, dataclass
import re
import uuid

from ai.context import AIRequestContext
from ai.service import AIAgentCore, AIRequest
from ai.guest_service import guest_service_agent


@dataclass(frozen=True)
class ReceptionistResponse:
    status: str
    handled: bool
    message: str
    receptionist_intent: str
    conversation_id: str
    core_response: dict | None = None
    handoff_required: bool = False
    action_required: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class AIHotelReceptionist:
    """Deterministic hotel-receptionist routing built on the existing AI core."""

    _INTENTS = (
        ("human_handoff", ("human", "person", "staff member", "receptionist", "manager", "speak to someone", "talk to someone", "agent")),
        ("complaint_handling", ("complaint", "complain", "problem", "issue", "not satisfied", "unhappy", "bad experience")),
        ("guest_requests", ("guest request", "service request", "extra towel", "towel", "housekeeping", "maintenance", "room service", "wake up call", "pillow", "blanket")),
        ("room_booking_assistance", ("book a room", "book room", "reserve a room", "room reservation", "want to book", "need a room")),
        ("table_booking_assistance", ("book a table", "reserve a table", "table reservation", "want a table", "need a table")),
        ("reservation_information", ("reservation information", "reservation status", "booking information", "booking status", "my reservation", "my booking")),
        ("room_availability", ("room availability", "available room", "rooms available", "vacant room", "vacant rooms")),
        ("checkin_checkout_information", ("check in", "check-in", "check out", "check-out", "checkin", "checkout")),
        ("restaurant_information", ("restaurant", "menu", "food", "dining", "breakfast", "lunch", "dinner")),
        ("hotel_facilities", ("facilities", "facility", "amenities", "amenity", "wifi", "wi-fi", "parking", "laundry", "pool", "gym")),
        ("policies", ("policy", "policies", "cancellation policy", "check in policy", "check out policy", "hotel rules")),
        ("location_maps", ("location", "address", "where is the hotel", "map", "maps", "navigation", "nearby")),
        ("transportation", ("transport", "transportation", "pickup", "drop", "airport transfer", "taxi", "cab", "ride")),
        ("hotel_information", ("hotel information", "hotel info", "about hotel", "contact hotel", "hotel timing", "timings", "opening hours")),
    )

    _CORE_TOOL_BY_INTENT = {
        "hotel_information": "hotel_information",
        "hotel_facilities": "hotel_information",
        "policies": "hotel_information",
        "checkin_checkout_information": "hotel_information",
        "room_availability": "room_availability",
        "reservation_information": "room_booking_information",
        "restaurant_information": "restaurant_information",
        "location_maps": "maps_information",
        "transportation": "transportation_information",
        "complaint_handling": "feedback_information",
    }

    def __init__(self, core: AIAgentCore | None = None):
        self.core = core or AIAgentCore()

    @staticmethod
    def _normalize(message: str) -> str:
        return " ".join(str(message or "").strip().lower().split())

    def detect_receptionist_intent(self, message: str) -> str:
        text = self._normalize(message)
        if not text:
            return "unknown"
        for intent, phrases in self._INTENTS:
            if any(phrase in text for phrase in phrases):
                return intent
        return "unknown"

    def _assist_message(self, intent: str) -> str:
        messages = {
            "room_booking_assistance": "I can help with a room reservation. Please share your check-in date, number of nights, guests, and preferred room type/room number. I will not create the booking without the required confirmation/action flow.",
            "table_booking_assistance": "I can help with a table reservation. Please share the date, time, number of guests, and preferred table if known. I will not create the reservation from this receptionist layer.",
            "guest_requests": "I can understand a guest service request and route it through the hotel service flow. For requests that require staff action, I can prepare the request for the appropriate team rather than performing an unapproved change.",
            "complaint_handling": "I can understand the complaint and retrieve available complaint/feedback context. If the issue needs staff intervention or a resolution action, it should be handed to the hotel team.",
            "human_handoff": "I can route the conversation for human assistance. A hotel staff member should take over when the request needs human judgment, an unavailable capability, or an operational action.",
            "checkin_checkout_information": "I can provide the hotel's available check-in/check-out information and reservation context.",
            "hotel_facilities": "I can provide the hotel's available facilities and amenity information.",
            "policies": "I can provide the hotel's available policy information. If a policy is not present in the configured hotel information, I will not invent it.",
            "location_maps": "I can provide the configured hotel location, map, nearby-place, and navigation information.",
            "transportation": "I can provide configured transportation information and existing transportation request context.",
        }
        return messages.get(intent, "I can help with the hotel's available information and receptionist services.")

    def process(self, message: str, context: AIRequestContext, conversation_id: str | None = None) -> ReceptionistResponse:
        normalized = self._normalize(message)
        conversation = conversation_id or f"reception_{uuid.uuid4().hex}"
        if not normalized:
            return ReceptionistResponse("invalid_request", False, "Please tell me what you need help with at the hotel.", "unknown", conversation)

        intent = self.detect_receptionist_intent(normalized)

        if intent == "human_handoff":
            return ReceptionistResponse(
                status="handoff_ready",
                handled=True,
                message=self._assist_message(intent),
                receptionist_intent=intent,
                conversation_id=conversation,
                handoff_required=True,
            )

        if intent == "guest_requests":
            guest_response = guest_service_agent.process(
                message=normalized,
                context=context,
                conversation_id=conversation,
            )
            return ReceptionistResponse(
                status=guest_response.status,
                handled=guest_response.handled,
                message=guest_response.message,
                receptionist_intent=intent,
                conversation_id=conversation,
                handoff_required=False,
                action_required=guest_response.status == "information_required",
                core_response={"guest_service": guest_response.to_dict()},
            )

        if intent == "reservation_information" and not re.search(
            r"\b(?:booking|reservation)\s*(?:id|no|number)\s*[:#-]?\s*[A-Z0-9][A-Z0-9_-]{2,}\b",
            normalized,
            re.IGNORECASE,
        ):
            return ReceptionistResponse(
                status="information_required",
                handled=True,
                message="I can help with reservation information. Please share your booking or reservation ID so I can retrieve the correct reservation within this hotel.",
                receptionist_intent=intent,
                conversation_id=conversation,
            )

        if intent in {"room_booking_assistance", "table_booking_assistance"}:
            return ReceptionistResponse(
                status="action_assistance",
                handled=True,
                message=self._assist_message(intent),
                receptionist_intent=intent,
                conversation_id=conversation,
                action_required=True,
            )

        tool_name = self._CORE_TOOL_BY_INTENT.get(intent)
        if tool_name:
            core_response = self.core.process(AIRequest(normalized, context, conversation))
            if core_response.handled:
                message_text = core_response.message
                if intent in {"checkin_checkout_information", "hotel_facilities", "policies", "hotel_information"}:
                    message_text = self._assist_message(intent) + " " + message_text
                return ReceptionistResponse(
                    status="handled",
                    handled=True,
                    message=message_text,
                    receptionist_intent=intent,
                    conversation_id=conversation,
                    core_response=core_response.to_dict(),
                )
            return ReceptionistResponse(
                status="handoff_ready" if intent == "complaint_handling" else core_response.status,
                handled=False if intent != "complaint_handling" else True,
                message=self._assist_message(intent),
                receptionist_intent=intent,
                conversation_id=conversation,
                core_response=core_response.to_dict(),
                handoff_required=intent == "complaint_handling",
            )

        # Keep the receptionist bounded: unknown requests do not trigger broad tool execution.
        return ReceptionistResponse(
            status="unknown_intent",
            handled=False,
            message="I can help with hotel information, rooms, reservations, restaurant/table information, facilities, policies, location, transportation, guest requests, complaints, or human assistance. Please tell me what you need.",
            receptionist_intent="unknown",
            conversation_id=conversation,
        )


receptionist = AIHotelReceptionist()
