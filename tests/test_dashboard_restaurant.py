from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "api" / "app.py"
DASH = ROOT / "dashboard" / "app.js"

def test_restaurant_dashboard_endpoint_exists():
    text = APP.read_text(encoding="utf-8")
    ops = (ROOT / "api" / "routes" / "operations.py").read_text(encoding="utf-8")
    assert '"/restaurant/dashboard"' in ops
    assert '"/table-bookings"' in ops

def test_restaurant_dashboard_ui_features():
    text = DASH.read_text(encoding="utf-8")
    for marker in ["Restaurant / POS Dashboard", "Menu Management View", "Kitchen Operational View", "Table Status", "Table Bookings", "Pending Payments", "restaurant-order-search"]:
        assert marker in text

def test_restaurant_search_status_controls():
    text = DASH.read_text(encoding="utf-8")
    assert 'data-restaurant-status' in text
    assert '/restaurant/orders' in text

def test_restaurant_order_actions_are_operational():
    text = DASH.read_text(encoding="utf-8")
    assert 'data-restaurant-detail' in text
    assert 'data-restaurant-status' in text
    assert 'PATCH' in text
    assert '/restaurant/orders/' in text
    assert 'order_status' in text
    assert 'Update Restaurant Order Status' in text


def test_restaurant_search_results_keep_actions():
    text = DASH.read_text(encoding="utf-8")
    assert 'data-search-order-detail' in text
    assert 'data-search-order-status' in text
    assert 'table(rows,actions)' in text
