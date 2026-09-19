"""AI Knowledge / Hotel Information Layer for Phase 8.16.

This layer assembles a hotel-scoped, AI-readable knowledge view by reusing the
existing AI business-tool layer. It does not access SQLite directly and does
not create a second hotel-information database.
"""
from dataclasses import asdict, dataclass
from typing import Any

from ai.context import AIRequestContext
from database.ai_tools_db import execute_ai_tool

KNOWLEDGE_SECTIONS = (
    "hotel_profile",
    "facilities",
    "rooms",
    "policies",
    "restaurant",
    "banquet",
    "location",
    "transportation",
    "services",
    "faqs",
    "configurable_hotel_information",
)


@dataclass(frozen=True)
class HotelKnowledgeResponse:
    status: str
    hotel_id: int
    sections: dict[str, Any]
    available_sections: tuple[str, ...]
    unavailable_sections: tuple[str, ...]
    context: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


class HotelKnowledgeService:
    """Build an authoritative hotel knowledge payload from existing tools."""

    @staticmethod
    def _tool(context: AIRequestContext, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = execute_ai_tool(name, arguments or {}, user={
            "user_id": context.user_id,
            "hotel_id": context.hotel_id,
        })
        return result.get("result", {})

    @staticmethod
    def _hotel_profile(raw: dict[str, Any]) -> dict[str, Any]:
        hotel = dict(raw.get("hotel") or {})
        facilities = {
            key: hotel.get(key)
            for key in ("restaurant", "parking", "wifi", "laundry")
            if hotel.get(key) is not None
        }
        return {"profile": hotel, "facilities": facilities}

    def build(self, *, context: AIRequestContext, section: str | None = None) -> HotelKnowledgeResponse:
        hotel_id = int(context.hotel_id)
        requested = str(section or "all").strip().lower()
        if requested not in {"all", *KNOWLEDGE_SECTIONS}:
            raise ValueError("Unknown hotel knowledge section.")

        sections: dict[str, Any] = {}
        unavailable: list[str] = []

        # Hotel master information is the authoritative source for profile,
        # configured facilities and core timing/contact information.
        if requested in {"all", "hotel_profile", "facilities", "configurable_hotel_information"}:
            profile_raw = self._tool(context, "hotel_information")
            profile = self._hotel_profile(profile_raw)
            if requested == "hotel_profile":
                sections[requested] = profile["profile"]
            elif requested == "facilities":
                sections[requested] = profile["facilities"]
            elif requested == "configurable_hotel_information":
                sections[requested] = {
                    "hotel_profile": profile["profile"],
                    "facilities": profile["facilities"],
                    "source": "existing hotel_information master data",
                }
            else:
                sections["hotel_profile"] = profile["profile"]
                sections["facilities"] = profile["facilities"]
                sections["configurable_hotel_information"] = {
                    "hotel_profile": profile["profile"],
                    "facilities": profile["facilities"],
                    "source": "existing hotel_information master data",
                }

        if requested in {"all", "rooms"}:
            sections["rooms"] = self._tool(context, "room_availability")

        if requested in {"all", "restaurant"}:
            sections["restaurant"] = self._tool(context, "restaurant_information")

        if requested in {"all", "location"}:
            sections["location"] = self._tool(context, "maps_information")

        if requested in {"all", "transportation"}:
            sections["transportation"] = self._tool(context, "transportation_information")

        # The current enterprise data model does not expose dedicated
        # policy/banquet/FAQ master records through an AI tool. Never invent
        # content: explicitly report these sections as not configured.
        for name in ("policies", "banquet", "services", "faqs"):
            if requested in {"all", name}:
                sections[name] = {"configured": False, "items": [], "source": None}
                unavailable.append(name)

        if requested != "all" and requested not in sections:
            raise ValueError("Hotel knowledge section is not available.")

        available = tuple(name for name in sections if name not in unavailable)
        return HotelKnowledgeResponse(
            status="ready",
            hotel_id=hotel_id,
            sections=sections,
            available_sections=available,
            unavailable_sections=tuple(unavailable),
            context={
                "hotel_id": hotel_id,
                "user_id": context.user_id if context.user_id is not None else None,
                "conversation_id": getattr(context, "conversation_id", None),
            },
        )

    @staticmethod
    def section_registry() -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "ai_readable": True,
                "hotel_scoped": True,
                "source": "existing hotel master / AI business tools",
            }
            for name in KNOWLEDGE_SECTIONS
        ]


hotel_knowledge_service = HotelKnowledgeService()
