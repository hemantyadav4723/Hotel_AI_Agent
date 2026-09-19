"""AI personalization / guest CRM context layer.

Read-only orchestration over the existing Guest/Customer CRM and history services.
No direct database access is performed here.
"""
from dataclasses import asdict, dataclass
import json
from typing import Any

from ai.context import AIRequestContext
from database.customer_db import (
    get_customer_by_id,
    get_guest_booking_summary,
    get_guest_stay_summary,
    get_guest_restaurant_summary,
    get_guest_repeat_recognition,
    validate_guest_hotel_relationship,
)


@dataclass(frozen=True)
class PersonalizationResponse:
    status: str
    customer_id: str
    hotel_id: int
    guest_profile: dict[str, Any]
    guest_preferences: dict[str, Any]
    stay_history: dict[str, Any]
    service_preferences: dict[str, Any]
    loyalty_context: dict[str, Any]
    personalized_recommendations: list[dict[str, Any]]
    special_occasions: list[dict[str, Any]]
    personalized_communication: dict[str, Any]
    context: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


class GuestPersonalizationService:
    """Build hotel-scoped personalization context from existing CRM data."""

    @staticmethod
    def _decode(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        text = str(value or "").strip()
        if not text:
            return {}
        try:
            decoded = json.loads(text)
            return decoded if isinstance(decoded, dict) else {"value": decoded}
        except (TypeError, ValueError):
            return {"text": text}

    @staticmethod
    def _guest_id(customer_id: str) -> str:
        value = str(customer_id or "").strip().upper()
        if not value:
            raise ValueError("Customer ID is required.")
        return value

    def build(
        self,
        *,
        context: AIRequestContext,
        customer_id: str,
        special_occasions: list[dict[str, Any]] | None = None,
        communication_channel: str | None = None,
        communication_purpose: str | None = None,
    ) -> PersonalizationResponse:
        hotel_id = int(context.hotel_id)
        customer_id = self._guest_id(customer_id)

        # Explicit hotel-scope validation is mandatory before reading CRM data.
        validate_guest_hotel_relationship(customer_id, hotel_id=hotel_id, require_active=True)
        customer = get_customer_by_id(customer_id)
        if customer is None:
            raise ValueError("Guest does not exist.")

        booking_summary = get_guest_booking_summary(customer_id, hotel_id)
        stay_summary = get_guest_stay_summary(customer_id, hotel_id)
        restaurant_summary = get_guest_restaurant_summary(customer_id, hotel_id)
        repeat = get_guest_repeat_recognition(customer_id, hotel_id) or {
            "visit_count": 0,
            "is_repeat_guest": False,
        }

        raw_preferences = self._decode(customer["preferences"] if "preferences" in customer.keys() else None)
        raw_special_requests = self._decode(
            customer["special_requests"] if "special_requests" in customer.keys() else None
        )

        guest_profile = {
            "customer_id": customer["customer_id"],
            "name": customer["customer_name"],
            "status": customer["guest_status"],
            "active": bool(customer["is_active"]),
            "city": customer["customer_city"],
            "state": customer["customer_state"],
            "country": customer["customer_country"],
        }

        # Keep service preferences distinct from general guest preferences.
        service_preferences = {
            "special_requests": raw_special_requests,
            "restaurant": {
                "favorite_items": ([restaurant_summary["favorite_item"]] if restaurant_summary.get("favorite_item") else []),
                "total_orders": restaurant_summary.get("total_orders", 0),
            },
        }

        stay_history = {
            "total_stays": booking_summary.get("total_bookings", 0),
            "completed_stays": booking_summary.get("status_counts", {}).get("Checked-In", 0)
            + booking_summary.get("status_counts", {}).get("Checked-Out", 0),
            "total_booking_value": booking_summary.get("total_value", 0),
            "total_nights": stay_summary.get("total_nights", 0),
            "restaurant_orders": restaurant_summary.get("total_orders", 0),
            "restaurant_spend": restaurant_summary.get("total_spend", 0),
        }

        loyalty_context = {
            "visit_count": int(repeat.get("visit_count", 0) or 0),
            "is_repeat_guest": bool(repeat.get("is_repeat_guest", False)),
            "first_visit_at": repeat.get("first_visit_at"),
            "last_visit_at": repeat.get("last_visit_at"),
        }

        recommendations: list[dict[str, Any]] = []
        favorite_items = ([restaurant_summary["favorite_item"]] if restaurant_summary.get("favorite_item") else [])
        if favorite_items:
            recommendations.append({
                "type": "restaurant",
                "reason": "Based on previous restaurant orders.",
                "items": favorite_items[:5],
            })
        if raw_preferences:
            recommendations.append({
                "type": "guest_preference",
                "reason": "Based on the guest's recorded preferences.",
                "preferences": raw_preferences,
            })
        if loyalty_context["is_repeat_guest"]:
            recommendations.append({
                "type": "repeat_guest",
                "reason": "Guest has previous visits at this hotel.",
            })

        occasions = list(special_occasions or [])
        personalized_communication = {
            "channel": communication_channel,
            "purpose": communication_purpose,
            "personalization_available": bool(raw_preferences or favorite_items or loyalty_context["is_repeat_guest"]),
            "guest_name": customer["customer_name"],
            "recommended_context": {
                "preferences": raw_preferences,
                "service_preferences": service_preferences,
                "loyalty": loyalty_context,
                "special_occasions": occasions,
            },
        }

        return PersonalizationResponse(
            status="ready",
            customer_id=customer_id,
            hotel_id=hotel_id,
            guest_profile=guest_profile,
            guest_preferences=raw_preferences,
            stay_history=stay_history,
            service_preferences=service_preferences,
            loyalty_context=loyalty_context,
            personalized_recommendations=recommendations,
            special_occasions=occasions,
            personalized_communication=personalized_communication,
            context={
                "hotel_id": hotel_id,
                "user_id": context.user_id if context.user_id is not None else None,
                "conversation_id": getattr(context, "conversation_id", None),
            },
        )


personalization_service = GuestPersonalizationService()
