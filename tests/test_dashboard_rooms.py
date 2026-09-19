from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_room_dashboard_has_all_reservation_operations():
    js = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
    for marker in ("Room Master", "Available Rooms", "Reservations", "Check-in", "Check-out", "No-show", "Transfer Room", "Early/Late", "Modify Reservation"):
        assert marker in js


def test_room_api_exposes_required_operations():
    src = (ROOT / "api" / "routes" / "operations.py").read_text(encoding="utf-8")
    for marker in ("/room-bookings/{booking_id}", "/cancel", "/no-show", "/check-in", "/check-out", "/transfer", "/stay-options"):
        assert marker in src


def test_room_booking_schema_supports_stay_options():
    src = (ROOT / "database" / "room_booking_db.py").read_text(encoding="utf-8")
    assert "early_check_in_time" in src
    assert "late_check_out_time" in src
