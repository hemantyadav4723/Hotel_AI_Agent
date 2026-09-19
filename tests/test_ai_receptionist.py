from pathlib import Path

from fastapi.testclient import TestClient

from ai.context import AIRequestContext
from ai.receptionist import AIHotelReceptionist
from api.app import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def context():
    return AIRequestContext(user_id="u1", username="admin", role="Admin", hotel_id=1)


def test_receptionist_covers_locked_intents():
    receptionist = AIHotelReceptionist()
    cases = {
        "hotel information": "hotel_information",
        "room availability": "room_availability",
        "I want to book a room": "room_booking_assistance",
        "reservation status": "reservation_information",
        "check in and check out time": "checkin_checkout_information",
        "restaurant information": "restaurant_information",
        "book a table": "table_booking_assistance",
        "hotel facilities": "hotel_facilities",
        "hotel policies": "policies",
        "hotel location and maps": "location_maps",
        "airport transportation": "transportation",
        "extra towel please": "guest_requests",
        "I have a complaint": "complaint_handling",
        "I want to speak to a human": "human_handoff",
    }
    for message, expected in cases.items():
        assert receptionist.detect_receptionist_intent(message) == expected


def test_room_booking_assistance_does_not_mutate():
    response = AIHotelReceptionist().process("I want to book a room", context())
    assert response.status == "action_assistance"
    assert response.action_required is True
    assert response.handoff_required is False
    assert response.core_response is None


def test_table_booking_assistance_does_not_mutate():
    response = AIHotelReceptionist().process("Please reserve a table", context())
    assert response.status == "action_assistance"
    assert response.action_required is True


def test_guest_request_requires_guest_reference_for_service_agent():
    response = AIHotelReceptionist().process("I need an extra towel", context())
    assert response.status == "information_required"
    assert response.handled is True


def test_complaint_is_handled_safely():
    response = AIHotelReceptionist().process("I have a complaint about my stay", context())
    assert response.receptionist_intent == "complaint_handling"
    assert response.handoff_required is True
    assert "complaint" in response.message.lower()


def test_human_handoff_intent_is_explicit():
    response = AIHotelReceptionist().process("I want to speak to a manager", context())
    assert response.receptionist_intent == "human_handoff"
    assert response.handoff_required is True


def test_information_intent_uses_existing_core():
    response = AIHotelReceptionist().process("show hotel information", context())
    assert response.receptionist_intent == "hotel_information"
    assert response.core_response is not None
    assert response.core_response["hotel_id"] == 1


def test_core_does_not_misread_status_or_transportation_as_ids():
    from ai.service import AIAgentCore
    core = AIAgentCore()
    reservation = core.decide_intent("reservation status")
    transportation = core.decide_intent("airport transportation")
    assert "booking_id" not in reservation.arguments
    assert "request_id" not in transportation.arguments


def test_policies_route_through_existing_hotel_information_tool():
    response = AIHotelReceptionist().process("hotel policies", context())
    assert response.receptionist_intent == "policies"
    assert response.core_response is not None
    assert response.core_response["intent"] == "hotel_information"



def test_checkin_checkout_information_is_not_treated_as_action():
    response = AIHotelReceptionist().process("what time is check-in and check-out", context())
    assert response.receptionist_intent == "checkin_checkout_information"
    assert response.core_response is not None
    assert response.core_response["status"] != "confirmation_required"


def test_reservation_information_without_id_requests_identifier():
    response = AIHotelReceptionist().process("I need my reservation information", context())
    assert response.receptionist_intent == "reservation_information"
    assert response.status == "information_required"
    assert response.handled is True


def test_conversation_id_is_preserved():
    response = AIHotelReceptionist().process("room availability", context(), "reception_existing")
    assert response.conversation_id == "reception_existing"


def test_unknown_request_is_bounded():
    response = AIHotelReceptionist().process("tell me a random joke", context())
    assert response.status == "unknown_intent"
    assert response.handled is False
    assert response.handoff_required is False


def test_receptionist_has_no_direct_sql():
    source = (ROOT / "ai" / "receptionist.py").read_text(encoding="utf-8").lower()
    assert "select " not in source
    assert "sqlite3" not in source
    assert "get_connection" not in source


def test_receptionist_api_requires_authentication():
    response = client.post("/api/v1/ai/receptionist", json={"message": "hotel information"})
    assert response.status_code == 401


def test_receptionist_api_is_in_openapi():
    document = client.get("/openapi.json").json()
    assert "/api/v1/ai/receptionist" in document["paths"]
    assert "AIReceptionistRequest" in document["components"]["schemas"]
