from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontdesk_dashboard_contains_required_operational_views():
    js = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
    for marker in (
        "Today's Arrivals",
        "Today's Departures",
        "Current Guests",
        "Available Rooms",
        "Occupied Rooms",
        "Pending Check-ins",
        "Pending Check-outs",
        "Guest Lookup",
        "Reservation Search",
        "Quick Check-in",
        "Quick Check-out",
        "Front Desk Actions",
    ):
        assert marker in js


def test_frontdesk_api_provides_scoped_summary_and_lookup():
    src = (ROOT / "api" / "routes" / "operations.py").read_text(encoding="utf-8")
    for marker in (
        '@router.get("/frontdesk")',
        '@router.get("/frontdesk/guest-lookup")',
        '"arrivals"',
        '"departures"',
        '"current_guests"',
        '"pending_checkins"',
        '"pending_checkouts"',
        '"available_rooms"',
        '"occupied_rooms"',
        '"reservation_results"',
    ):
        assert marker in src
    assert 'WHERE hotel_id = ?' in src


def test_frontdesk_uses_existing_room_booking_actions():
    js = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
    assert '/room-bookings/${id}/check-in' in js
    assert '/room-bookings/${id}/check-out' in js
    assert 'reservationDetail' in js
