import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from ai.context import AIRequestContext
from ai.guest_service import AIGuestServiceAgent
from api.app import app
from database.database import get_connection
from database.room_booking_db import add_room
from database.guest_service_db import (
    create_guest_service_requests_table,
    get_guest_service_request,
)

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


@pytest.fixture(autouse=True)
def guest_service_test_rooms():
    """Provide isolated room references required by guest-service AI tests."""
    connection = get_connection()
    for room_number in ("101", "102", "103"):
        connection.execute("DELETE FROM room_reservation_advance_rules WHERE hotel_id = ? AND room_number = ?", (1, room_number))
        connection.execute("DELETE FROM rooms WHERE hotel_id = ? AND room_number = ?", (1, room_number))
    connection.commit()
    connection.close()
    for room_number in ("101", "102", "103"):
        add_room(room_number, "Deluxe", 1, 2, 2000, "", "AI guest service test room")
    try:
        yield
    finally:
        connection = get_connection()
        for room_number in ("101", "102", "103"):
            connection.execute("DELETE FROM room_reservation_advance_rules WHERE hotel_id = ? AND room_number = ?", (1, room_number))
            connection.execute("DELETE FROM rooms WHERE hotel_id = ? AND room_number = ?", (1, room_number))
        connection.commit()
        connection.close()


def context():
    return AIRequestContext(user_id="ADMIN1001", username="admin1001", role="Admin", hotel_id=1)


def test_guest_service_covers_locked_service_types():
    agent = AIGuestServiceAgent()
    cases = {
        "housekeeping please": "Housekeeping",
        "send food to my room": "Room Service",
        "the AC is not working": "Maintenance",
        "I need laundry service": "Laundry",
        "please help with my luggage": "Bell/Luggage",
        "I need airport transportation": "Transportation",
        "I have a restaurant service request": "Restaurant",
        "I need some general help": "General",
    }
    for message, expected in cases.items():
        assert agent.detect_service_type(message) == expected


def test_create_request_requires_guest_reference():
    response = AIGuestServiceAgent().process("I need extra towels", context())
    assert response.status == "information_required"
    assert response.handled is True
    assert response.request_id is None


def test_create_and_read_guest_service_request():
    response = AIGuestServiceAgent().process(
        "I need extra towels in room 101",
        context(),
        guest_name="Test Guest",
    )
    assert response.status == "created"
    assert response.request_id.startswith("GSR-")
    row = get_guest_service_request(response.request_id, 1)
    assert row is not None
    assert row["service_type"] == "Housekeeping"
    assert row["room_number"] == "101"
    assert row["request_status"] == "Requested"
    connection = get_connection()
    connection.execute("DELETE FROM guest_service_requests WHERE request_id = ? AND hotel_id = ?", (response.request_id, 1))
    connection.commit()
    connection.close()


def test_request_status_follow_up_and_escalation():
    agent = AIGuestServiceAgent()
    created = agent.process("I need laundry service for room 102", context(), guest_name="Test Guest")
    request_id = created.request_id

    status = agent.process(f"what is the status of {request_id}", context())
    assert status.status == "handled"
    assert status.request_id == request_id
    assert "Requested" in status.message

    follow = agent.process(f"please follow up on {request_id}", context())
    assert follow.status == "handled"
    row = get_guest_service_request(request_id, 1)
    assert row["follow_up_status"] == "Pending"

    escalated = agent.process(f"escalate {request_id} to manager", context())
    assert escalated.status == "escalated"
    row = get_guest_service_request(request_id, 1)
    assert row["request_status"] == "Escalated"
    assert row["escalated"] == 1

    connection = get_connection()
    connection.execute("DELETE FROM guest_service_requests WHERE request_id = ? AND hotel_id = ?", (request_id, 1))
    connection.commit()
    connection.close()


def test_guest_service_hotel_scope_is_enforced():
    agent = AIGuestServiceAgent()
    created = agent.process("I need housekeeping in room 103", context(), guest_name="Test Guest")
    request_id = created.request_id
    assert get_guest_service_request(request_id, 999) is None
    connection = get_connection()
    connection.execute("DELETE FROM guest_service_requests WHERE request_id = ? AND hotel_id = ?", (request_id, 1))
    connection.commit()
    connection.close()


def test_guest_service_api_requires_authentication():
    response = client.post("/api/v1/ai/guest-service", json={"message": "I need housekeeping", "room_number": "101"})
    assert response.status_code == 401


def test_guest_service_api_is_in_openapi():
    document = client.get("/openapi.json").json()
    assert "/api/v1/ai/guest-service" in document["paths"]
    assert "AIGuestServiceRequest" in document["components"]["schemas"]


def test_guest_service_table_exists_after_initialization():
    create_guest_service_requests_table()
    connection = get_connection()
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='guest_service_requests'"
    ).fetchone()
    connection.close()
    assert row is not None


def test_receptionist_delegates_guest_requests_to_guest_service_agent():
    from ai.receptionist import AIHotelReceptionist
    response = AIHotelReceptionist().process("I need housekeeping in room 101", context(), "reception_guest_service")
    assert response.receptionist_intent == "guest_requests"
    assert response.status == "created"
    assert response.core_response["guest_service"]["request_id"].startswith("GSR-")
    request_id = response.core_response["guest_service"]["request_id"]
    connection = get_connection()
    connection.execute("DELETE FROM guest_service_requests WHERE request_id = ? AND hotel_id = ?", (request_id, 1))
    connection.commit()
    connection.close()
