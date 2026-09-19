import pytest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.booking import AIBookingAutomation, BookingItem
from ai.context import AIRequestContext
from api.app import app
from database.database import get_connection
from database.room_booking_db import add_room

client = TestClient(app)


@pytest.fixture(autouse=True)
def room_booking_test_data():
    """Provide only the room/payment prerequisites needed by room-booking AI tests."""
    connection = get_connection()
    connection.execute("DELETE FROM room_reservation_advance_rules WHERE hotel_id = ? AND room_number = ?", (1, "101"))
    connection.execute("DELETE FROM rooms WHERE hotel_id = ? AND room_number = ?", (1, "101"))
    connection.commit()
    connection.close()
    add_room("101", "Deluxe", 1, 2, 2000, "", "AI booking test room")
    try:
        yield
    finally:
        connection = get_connection()
        connection.execute("DELETE FROM room_reservation_advance_rules WHERE hotel_id = ? AND room_number = ?", (1, "101"))
        connection.execute("DELETE FROM rooms WHERE hotel_id = ? AND room_number = ?", (1, "101"))
        connection.commit()
        connection.close()


def context():
    return AIRequestContext(user_id="ADMIN1001", username="admin1001", role="Admin", hotel_id=1)


def test_booking_types_are_detected():
    agent = AIBookingAutomation()
    assert agent.detect_booking_type("book a room") == "room"
    assert agent.detect_booking_type("reserve a table") == "table"
    assert agent.detect_booking_type("order food") == "restaurant"
    assert agent.detect_booking_type("airport pickup") == "transportation"


def test_room_workflow_requests_missing_information():
    response = AIBookingAutomation().process("book a room", context())
    assert response.status == "information_required"
    assert "check_in_date" in response.missing_fields
    assert "nights" in response.missing_fields


def test_room_workflow_shows_availability_and_price_before_confirmation():
    fake_rooms = [{"room_number": "101", "room_type": "Deluxe", "room_price": 2000, "room_status": "Available"}]
    with patch("ai.booking.get_available_rooms_for_dates", return_value=fake_rooms):
        response = AIBookingAutomation().process(
            "book a room",
            context(),
            booking_type="room",
            guest_name="Test Guest",
            guest_mobile="9999999999",
            check_in_date=date(2026, 10, 1),
            nights=2,
        )
    assert response.status == "room_selection_required"
    assert response.result["available_rooms"][0]["room_number"] == "101"

    with patch("ai.booking.get_available_rooms_for_dates", return_value=fake_rooms):
        response = AIBookingAutomation().process(
            "book a room",
            context(),
            booking_type="room",
            guest_name="Test Guest",
            guest_mobile="9999999999",
            room_number="101",
            check_in_date=date(2026, 10, 1),
            nights=2,
            confirm=False,
        )
    assert response.status == "confirmation_required"
    assert response.confirmation_required is True
    assert response.quote["grand_total"] == 4200.0


def test_room_confirmation_calls_existing_business_function():
    fake_room = {"room_number": "101", "room_type": "Deluxe", "room_price": 2000, "room_status": "Available"}
    fake_booking = {"booking_id": "AI-ROOM-TEST"}
    with patch("ai.booking.get_available_rooms_for_dates", return_value=[fake_room]), \
         patch("ai.booking.has_permission", return_value=True), \
         patch("ai.booking.save_and_book_room") as save, \
         patch("ai.booking.get_room_booking_by_id", return_value=fake_booking), \
         patch("ai.booking.get_required_reservation_advance", return_value=100.0), \
         patch("ai.booking.resolve_guest_for_booking", return_value="CUS1001"), \
         patch("ai.booking.validate_guest_hotel_relationship"):
        response = AIBookingAutomation().process(
            "book a room",
            context(),
            booking_type="room",
            confirm=True,
            guest_name="Test Guest",
            guest_mobile="9999999999",
            room_number="101",
            check_in_date=date(2026, 10, 1),
            nights=2,
            advance_amount=100,
            payment_method="Cash",
        )
    assert response.status == "booked"
    save.assert_called_once()
    assert response.booking_id.startswith("AI-ROOM-")




def test_room_confirmation_requires_configured_minimum_advance():
    fake_room = {"room_number": "101", "room_type": "Deluxe", "room_price": 2000, "room_status": "Available"}
    with patch("ai.booking.get_available_rooms_for_dates", return_value=[fake_room]), \
         patch("ai.booking.get_required_reservation_advance", return_value=100.0):
        response = AIBookingAutomation().process(
            "book a room", context(), booking_type="room", confirm=True,
            guest_name="Test Guest", guest_mobile="9999999999", room_number="101",
            check_in_date=date(2026, 10, 1), nights=2, advance_amount=0,
        )
    assert response.status == "advance_required"
    assert response.missing_fields == ("advance_amount",)


def test_room_quote_exposes_required_advance_before_confirmation():
    fake_room = {"room_number": "101", "room_type": "Deluxe", "room_price": 2000, "room_status": "Available"}
    with patch("ai.booking.get_available_rooms_for_dates", return_value=[fake_room]), \
         patch("ai.booking.get_required_reservation_advance", return_value=100.0):
        response = AIBookingAutomation().process(
            "book a room", context(), booking_type="room", confirm=False,
            guest_name="Test Guest", guest_mobile="9999999999", room_number="101",
            check_in_date=date(2026, 10, 1), nights=2,
        )
    assert response.quote["minimum_reservation_advance"] == 100.0

def test_table_workflow_exposes_available_tables_before_selection():
    tables = [{"table_number": "T1", "table_capacity": 4, "table_status": "Available"}]
    with patch("ai.booking.get_available_restaurant_tables", return_value=tables):
        response = AIBookingAutomation().process(
            "reserve a table", context(), booking_type="table",
            guest_name="Test Guest", guest_mobile="9999999999",
            booking_date=date(2026, 10, 1), booking_time="19:00", persons=2,
        )
    assert response.status == "table_selection_required"
    assert response.result["available_tables"][0]["table_number"] == "T1"


def test_table_confirmation_calls_existing_business_function():
    tables = [{"table_number": "T1", "table_capacity": 4, "table_status": "Available"}]
    with patch("ai.booking.get_available_restaurant_tables", return_value=tables), \
         patch("ai.booking.has_permission", return_value=True), \
         patch("ai.booking.resolve_guest_for_booking", return_value="CUS1001"), \
         patch("ai.booking.create_table_booking") as create:
        response = AIBookingAutomation().process(
            "reserve a table", context(), booking_type="table", confirm=True,
            guest_name="Test Guest", guest_mobile="9999999999", table_number="T1",
            booking_date=date(2026, 10, 1), booking_time="19:00", persons=2,
        )
    assert response.status == "booked"
    create.assert_called_once()


def test_restaurant_workflow_provides_menu_and_confirmation():
    menu = [{"item_id": "IT1001", "item_name": "Veg Thali", "price": 250, "is_available": 1}]
    with patch("ai.booking.get_menu_items", return_value=menu):
        response = AIBookingAutomation().process(
            "order food", context(), booking_type="restaurant",
            guest_name="Test Guest", guest_mobile="9999999999", table_number="T1",
        )
    assert response.status == "information_required"
    assert "items" in response.missing_fields
    assert response.result["menu"][0]["item_id"] == "IT1001"

    with patch("ai.booking.get_menu_item", return_value=menu[0]):
        response = AIBookingAutomation().process(
            "order food", context(), booking_type="restaurant",
            guest_name="Test Guest", guest_mobile="9999999999", table_number="T1",
            items=[BookingItem("IT1001", 2)],
        )
    assert response.status == "confirmation_required"
    assert response.quote["grand_total"] == 525.0


def test_restaurant_confirmation_calls_existing_order_business_function():
    menu = {"item_id": "IT1001", "item_name": "Veg Thali", "price": 250, "is_available": 1}
    with patch("ai.booking.get_menu_item", return_value=menu), \
         patch("ai.booking.has_permission", return_value=True), \
         patch("ai.booking.resolve_guest_for_booking", return_value="CUS1001"), \
         patch("ai.booking.save_order") as save, \
         patch("ai.booking.get_order", return_value={"order_id": "AI-ORDER-TEST"}), \
         patch("ai.booking.record_notification_event", create=True):
        response = AIBookingAutomation().process(
            "order food", context(), booking_type="restaurant", confirm=True,
            guest_name="Test Guest", guest_mobile="9999999999", table_number="T1",
            items=[BookingItem("IT1001", 1)],
        )
    assert response.status == "booked"
    save.assert_called_once()


def test_transportation_workflow_requires_confirmation_then_calls_existing_business_function():
    kwargs = dict(
        message="airport pickup", context=context(), booking_type="transportation",
        guest_name="Test Guest", guest_mobile="9999999999",
        transportation_type="Airport Pickup", pickup_date=date(2026, 10, 1), pickup_time="10:00",
        pickup_location="Airport", drop_location="Hotel", fare=500,
    )
    preview = AIBookingAutomation().process(**kwargs)
    assert preview.status == "confirmation_required"
    assert preview.quote["fare"] == 500.0

    with patch("ai.booking.has_permission", return_value=True), \
         patch("ai.booking.create_transportation_request", return_value="TRN-20261001-00001") as create:
        response = AIBookingAutomation().process(**kwargs, confirm=True)
    assert response.status == "booked"
    assert response.reference_id == "TRN-20261001-00001"
    create.assert_called_once()


def test_customer_scope_is_validated_before_automation():
    with patch("ai.booking.validate_guest_hotel_relationship", side_effect=ValueError("Guest does not exist.")):
        try:
            AIBookingAutomation().process("book a room", context(), booking_type="room", customer_id="CUS999")
        except ValueError as exc:
            assert "Guest does not exist" in str(exc)
        else:
            raise AssertionError("Expected guest scope validation failure")


def test_booking_api_requires_authentication():
    response = client.post("/api/v1/ai/booking", json={"message": "book a room"})
    assert response.status_code == 401


def test_booking_api_is_in_openapi():
    document = client.get("/openapi.json").json()
    assert "/api/v1/ai/booking" in document["paths"]
    assert "AIBookingAutomationRequest" in document["components"]["schemas"]


def test_confirmation_gate_prevents_mutation():
    with patch("ai.booking.get_available_rooms_for_dates", return_value=[{"room_number": "101", "room_type": "Deluxe", "room_price": 2000, "room_status": "Available"}]), \
         patch("ai.booking.save_and_book_room") as save:
        response = AIBookingAutomation().process(
            "book a room", context(), booking_type="room", confirm=False,
            guest_name="Test Guest", guest_mobile="9999999999", room_number="101",
            check_in_date=date(2026, 10, 1), nights=1,
        )
    assert response.status == "confirmation_required"
    save.assert_not_called()
