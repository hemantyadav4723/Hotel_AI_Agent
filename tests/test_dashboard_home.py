import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_dashboard_home_endpoint_is_declared():
    text = (ROOT / "api" / "routes" / "reports.py").read_text(encoding="utf-8")
    assert '"/dashboard/home"' in text
    assert 'get_dashboard_home_summary' in text

def test_dashboard_home_renders_required_operational_kpis():
    text = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
    for label in ("Today's Revenue", "Today's Bookings", "Today's Check-ins", "Today's Check-outs", "Occupancy", "Restaurant Orders", "Pending Payments", "Low-stock Alerts", "Guest Issues", "Transportation", "Hotel Overview", "Quick Actions"):
        assert label in text
    assert 'api("/dashboard/home")' in text

def test_dashboard_home_summary_has_hotel_scope():
    text = (ROOT / "database" / "analytics_report_db.py").read_text(encoding="utf-8")
    assert 'get_dashboard_home_summary(hotel_id)' in text
    assert 'WHERE hotel_id = ?' in text
