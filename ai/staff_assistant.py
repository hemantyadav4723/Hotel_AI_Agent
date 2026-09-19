"""Role-aware AI staff assistant for Phase 8.9.

The staff assistant is a controlled internal AI surface. It uses the existing
AI Agent/tool layer for hotel information and does not execute SQL or bypass
existing authorization. Capabilities are constrained by the authenticated
user role before a request reaches the central agent.
"""

from dataclasses import asdict, dataclass
import uuid

from ai.context import AIRequestContext
from ai.service import AIRequest, AIResponse, service as ai_service


ASSISTANT_AREAS = (
    ("reception", "Reception assistant"),
    ("housekeeping", "Housekeeping assistant"),
    ("maintenance", "Maintenance assistant"),
    ("restaurant_kitchen", "Restaurant/kitchen assistant"),
    ("laundry", "Laundry assistant"),
    ("transport_concierge", "Transport/concierge assistant"),
    ("management", "Management assistant"),
)

# Capabilities are intentionally expressed as existing AI tools. This keeps
# the staff assistant on the same controlled business/API path as the guest
# agent and prevents an alternate database/business layer from appearing here.
AREA_TOOLS = {
    "reception": (
        "hotel_information",
        "guest_information",
        "room_availability",
        "room_booking_information",
        "table_information",
        "restaurant_information",
        "transportation_information",
        "maps_information",
        "notification_information",
    ),
    "housekeeping": (
        "hotel_information",
        "room_availability",
        "room_booking_information",
        "notification_information",
    ),
    "maintenance": (
        "hotel_information",
        "room_availability",
        "room_booking_information",
        "notification_information",
    ),
    "restaurant_kitchen": (
        "hotel_information",
        "restaurant_information",
        "table_information",
        "inventory_information",
        "guest_information",
        "notification_information",
    ),
    "laundry": (
        "hotel_information",
        "room_booking_information",
        "notification_information",
    ),
    "transport_concierge": (
        "hotel_information",
        "guest_information",
        "transportation_information",
        "maps_information",
        "notification_information",
    ),
    "management": (
        "hotel_information",
        "guest_information",
        "room_availability",
        "room_booking_information",
        "table_information",
        "restaurant_information",
        "inventory_information",
        "staff_information",
        "expense_information",
        "feedback_information",
        "notification_information",
        "transportation_information",
        "maps_information",
        "reports_summary",
        "audit_information",
    ),
}

# Roles are normalized aliases, not permissions. Final authorization remains
# with the existing permission/tool layer.
ROLE_ALLOWED_AREAS = {
    "admin": set(AREA_TOOLS),
    "manager": set(AREA_TOOLS),
    "general manager": set(AREA_TOOLS),
    "receptionist": {"reception"},
    "front desk": {"reception"},
    "housekeeping": {"housekeeping"},
    "maintenance": {"maintenance"},
    "restaurant": {"restaurant_kitchen"},
    "kitchen": {"restaurant_kitchen"},
    "restaurant kitchen": {"restaurant_kitchen"},
    "laundry": {"laundry"},
    "concierge": {"transport_concierge"},
    "transport": {"transport_concierge"},
    "transportation": {"transport_concierge"},
    "staff": {"reception"},
}

AREA_ALIASES = {
    "reception": "reception",
    "reception assistant": "reception",
    "front desk": "reception",
    "housekeeping": "housekeeping",
    "housekeeping assistant": "housekeeping",
    "maintenance": "maintenance",
    "maintenance assistant": "maintenance",
    "restaurant": "restaurant_kitchen",
    "kitchen": "restaurant_kitchen",
    "restaurant/kitchen": "restaurant_kitchen",
    "restaurant kitchen": "restaurant_kitchen",
    "restaurant/kitchen assistant": "restaurant_kitchen",
    "laundry": "laundry",
    "laundry assistant": "laundry",
    "transport": "transport_concierge",
    "transportation": "transport_concierge",
    "concierge": "transport_concierge",
    "transport/concierge": "transport_concierge",
    "transport concierge": "transport_concierge",
    "management": "management",
    "management assistant": "management",
}


def _normalize(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


@dataclass(frozen=True)
class StaffAssistantResponse:
    status: str
    handled: bool
    message: str
    role: str
    assistant_area: str | None
    assistant_area_name: str | None
    allowed_tools: tuple[str, ...]
    conversation_id: str
    ai_response: AIResponse | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        if self.ai_response is not None:
            payload["ai_response"] = self.ai_response.to_dict()
        return payload


class AIStaffAssistant:
    """Provide role-scoped internal staff assistance through the central AI agent."""

    def role_key(self, role: str) -> str:
        return _normalize(role)

    def allowed_areas(self, role: str) -> tuple[str, ...]:
        role_key = self.role_key(role)
        return tuple(area for area, _ in ASSISTANT_AREAS if area in ROLE_ALLOWED_AREAS.get(role_key, set()))

    def normalize_area(self, area: str | None) -> str | None:
        if area is None or not str(area).strip():
            return None
        normalized = _normalize(area)
        return AREA_ALIASES.get(normalized)

    def area_registry(self, role: str) -> list[dict]:
        allowed = set(self.allowed_areas(role))
        return [
            {
                "code": code,
                "name": name,
                "allowed": code in allowed,
                "tools": list(AREA_TOOLS[code]),
            }
            for code, name in ASSISTANT_AREAS
        ]

    def _area_name(self, area: str) -> str:
        return next(name for code, name in ASSISTANT_AREAS if code == area)

    def _restricted(self, context: AIRequestContext, conversation: str, area: str | None, message: str, allowed_tools=()):
        return StaffAssistantResponse(
            status="restricted",
            handled=False,
            message=message,
            role=context.role,
            assistant_area=area,
            assistant_area_name=self._area_name(area) if area else None,
            allowed_tools=tuple(allowed_tools),
            conversation_id=conversation,
        )

    def process(
        self,
        message: str,
        context: AIRequestContext,
        assistant_area: str | None = None,
        conversation_id: str | None = None,
    ) -> StaffAssistantResponse:
        text = str(message or "").strip()
        conversation = conversation_id or f"staff_assistant_{uuid.uuid4().hex}"
        if not text:
            return StaffAssistantResponse(
                "invalid_request", False,
                "Please describe what you need help with.",
                context.role, None, None, (), conversation,
            )

        allowed_areas = set(self.allowed_areas(context.role))
        if not allowed_areas:
            return self._restricted(
                context, conversation, None,
                "Your authenticated staff role does not have a configured AI staff-assistant area.",
            )

        area = self.normalize_area(assistant_area)
        if area is None:
            # For a role with exactly one configured area, infer it from the
            # authenticated role. For multi-area roles, require an explicit area.
            if len(allowed_areas) == 1:
                area = next(iter(allowed_areas))
            else:
                return self._restricted(
                    context, conversation, None,
                    "Please specify the staff-assistant area you want to use.",
                )

        if area not in allowed_areas:
            return self._restricted(
                context, conversation, area,
                "This staff-assistant area is not available for your authenticated role.",
            )

        allowed_tools = AREA_TOOLS[area]
        decision = ai_service.agent.decide_intent(text)
        requested_tools = tuple(decision.tool_names)

        # The central agent must remain inside this role's allow-list. Action
        # intents are also rejected here; action automation belongs to later
        # workflow/safety layers and must never be smuggled through this read
        # assistant endpoint.
        if decision.action_required:
            return self._restricted(
                context, conversation, area,
                "This request requires an operational action. The staff assistant can provide authorized information, but it will not execute that action here.",
                allowed_tools,
            )

        if requested_tools and any(tool not in allowed_tools for tool in requested_tools):
            return self._restricted(
                context, conversation, area,
                "That information is outside the capabilities configured for your staff-assistant role.",
                allowed_tools,
            )

        if not requested_tools:
            return StaffAssistantResponse(
                "unknown_request", False,
                "I could not identify an authorized staff-assistant capability for that request.",
                context.role, area, self._area_name(area), allowed_tools, conversation,
            )

        response = ai_service.process(
            AIRequest(message=text, context=context, conversation_id=conversation)
        )
        return StaffAssistantResponse(
            status=response.status,
            handled=response.handled,
            message=response.message,
            role=context.role,
            assistant_area=area,
            assistant_area_name=self._area_name(area),
            allowed_tools=allowed_tools,
            conversation_id=response.conversation_id or conversation,
            ai_response=response,
        )


staff_assistant = AIStaffAssistant()
