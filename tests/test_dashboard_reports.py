from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reports_dashboard_has_all_locked_sections():
    text = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
    for label in ("Dashboard Analytics", "Revenue", "Room Revenue", "Restaurant Revenue", "Occupancy", "ADR", "RevPAR", "Booking Trends", "Cancellation", "No-show", "Customer Trends", "Inventory Trends", "Expense Trends", "Department Performance", "Staff Reports", "Profitability"):
        # Labels may be rendered from report metadata or KPI cards; the route keys below are the authoritative checks.
        assert label in text or label.lower().replace(" ", "-") in text
    assert '/reports/operational' in text
    assert 'id="report-start"' in text and 'id="report-end"' in text


def test_reports_routes_normalize_dashboard_date_filters():
    text = (ROOT / "api" / "routes" / "reports.py").read_text(encoding="utf-8")
    assert "_parse_date(start_date)" in text
    assert "_parse_date(end_date)" in text
    assert '"/reports/operational"' in text


def test_reports_are_hotel_scoped_and_permission_protected():
    text = (ROOT / "api" / "routes" / "reports.py").read_text(encoding="utf-8")
    assert 'require_permission("Reports", "Reports")' in text
    assert 'user["hotel_id"]' in text


def test_analytics_data_layer_has_locked_metrics():
    text = (ROOT / "database" / "analytics_report_db.py").read_text(encoding="utf-8")
    for fn in ("get_revenue_summary", "room_revenue_data", "restaurant_revenue_data", "occupancy_data", "adr_data", "revpar_data", "booking_trends_data", "cancellation_data", "no_show_data", "customer_trends_data", "inventory_trends_data", "expense_trends_data", "department_performance_data", "staff_report_data", "profitability_data"):
        assert f"def {fn}" in text
    assert 'WHERE hotel_id = ?' in text
