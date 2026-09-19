from types import SimpleNamespace

import pytest

from ai.proactive_notifications import AIProactiveNotificationEngine


def test_available_triggers_contains_all_phase_811_events():
    engine = AIProactiveNotificationEngine()
    names = [item["trigger"] for item in engine.available_triggers()]
    assert names == [
        "booking_created", "check_in", "check_out", "low_inventory",
        "guest_complaint", "transportation_request", "event", "follow_up",
    ]


def test_trigger_requires_confirmation(monkeypatch):
    engine = AIProactiveNotificationEngine()
    monkeypatch.setattr(engine, "_require_permission", lambda user_id: None)
    response = engine.trigger(trigger="booking_created", hotel_id=1, user_id=1, confirm=False)
    assert response.status == "confirmation_required"
    assert response.notification_id is None


def test_trigger_queues_existing_notification_layer(monkeypatch):
    engine = AIProactiveNotificationEngine()
    monkeypatch.setattr(engine, "_require_permission", lambda user_id: None)
    captured = {}

    def fake_record(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return "NTF-TEST-1"

    monkeypatch.setattr("ai.proactive_notifications.record_notification_event", fake_record)
    response = engine.trigger(
        trigger="check_out", hotel_id=7, user_id=3, confirm=True,
        payload={"reference_type": "ROOM_BOOKING", "reference_id": "RB-1", "event_key": "checkout-1"},
    )
    assert response.status == "queued"
    assert response.notification_id == "NTF-TEST-1"
    assert captured["args"][0] == "Check-out"
    assert captured["kwargs"]["hotel_id"] == 7


def test_invalid_trigger_is_rejected():
    with pytest.raises(ValueError):
        AIProactiveNotificationEngine().trigger(trigger="unknown", hotel_id=1, user_id=1)


def test_permission_is_enforced_before_queue(monkeypatch):
    engine = AIProactiveNotificationEngine()
    monkeypatch.setattr("ai.proactive_notifications.has_permission", lambda *args: False)
    with pytest.raises(PermissionError):
        engine.trigger(trigger="guest_complaint", hotel_id=1, user_id=1, confirm=True)


def test_proactive_route_preserves_string_user_id():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "api" / "routes" / "ai.py").read_text(encoding="utf-8")
    assert 'user_id=user["user_id"]' in source
    assert 'user_id=int(user["user_id"])' not in source
