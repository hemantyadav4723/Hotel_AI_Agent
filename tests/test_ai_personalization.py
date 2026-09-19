from types import SimpleNamespace

import pytest

from ai.personalization import GuestPersonalizationService


def ctx(hotel_id=1, user_id=1, conversation_id="c1"):
    return SimpleNamespace(hotel_id=hotel_id, user_id=user_id, conversation_id=conversation_id)


def test_requires_customer_id():
    with pytest.raises(ValueError):
        GuestPersonalizationService().build(context=ctx(), customer_id="")


def test_builds_profile_from_existing_crm(monkeypatch):
    service = GuestPersonalizationService()
    customer = {
        "customer_id": "C001", "customer_name": "Test Guest", "guest_status": "Active",
        "is_active": 1, "customer_city": "Alwar", "customer_state": "Rajasthan",
        "customer_country": "India", "preferences": '{"room":"quiet"}',
        "special_requests": '{"diet":"veg"}'
    }
    monkeypatch.setattr("ai.personalization.validate_guest_hotel_relationship", lambda *a, **k: True)
    monkeypatch.setattr("ai.personalization.get_customer_by_id", lambda x: customer)
    monkeypatch.setattr("ai.personalization.get_guest_booking_summary", lambda *a: {
        "total_bookings": 2, "status_counts": {"Checked-In": 0, "Checked-Out": 2},
        "total_value": 5000
    })
    monkeypatch.setattr("ai.personalization.get_guest_stay_summary", lambda *a: {
        "total_stays": 2, "total_nights": 4, "total_spend": 5000
    })
    monkeypatch.setattr("ai.personalization.get_guest_restaurant_summary", lambda *a: {
        "total_orders": 3, "total_spend": 1200, "favorite_item": "Paneer"
    })
    monkeypatch.setattr("ai.personalization.get_guest_repeat_recognition", lambda *a: {
        "visit_count": 2, "is_repeat_guest": True, "first_visit_at": "x", "last_visit_at": "y"
    })
    result = service.build(
        context=ctx(), customer_id="c001",
        special_occasions=[{"type": "birthday", "date": "2026-10-01"}],
        communication_channel="whatsapp", communication_purpose="welcome"
    )
    assert result.customer_id == "C001"
    assert result.hotel_id == 1
    assert result.guest_preferences["room"] == "quiet"
    assert result.stay_history["total_nights"] == 4
    assert result.service_preferences["restaurant"]["favorite_items"] == ["Paneer"]
    assert result.loyalty_context["is_repeat_guest"] is True
    assert result.special_occasions[0]["type"] == "birthday"
    assert result.personalized_communication["channel"] == "whatsapp"
    assert result.context["user_id"] == 1


def test_hotel_scope_validation_called(monkeypatch):
    calls = []
    monkeypatch.setattr("ai.personalization.validate_guest_hotel_relationship", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr("ai.personalization.get_customer_by_id", lambda x: None)
    with pytest.raises(ValueError, match="Guest does not exist"):
        GuestPersonalizationService().build(context=ctx(hotel_id=7), customer_id="C001")
    assert calls[0][1]["hotel_id"] == 7
    assert calls[0][1]["require_active"] is True
