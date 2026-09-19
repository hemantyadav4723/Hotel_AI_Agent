from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.js"
ROUTES = ROOT / "api" / "routes" / "inventory.py"


def test_procurement_routes_cover_supplier_and_procurement_data():
    text = ROUTES.read_text(encoding="utf-8")
    for marker in (
        '"/suppliers"', '"/suppliers/detail"', '"/suppliers/search"',
        '"/procurement/purchase-orders"', '"/procurement/purchase-orders/{po_id}"',
        '"/procurement/receivings"', '"/procurement/purchase-history"',
        '"/procurement/payment-terms"', '"/procurement/outstanding"',
    ):
        assert marker in text


def test_procurement_dashboard_contains_required_views_and_search():
    text = APP.read_text(encoding="utf-8")
    for marker in ("Supplier Overview", "Purchase Orders", "Purchase Receiving", "Supplier Outstanding", "Payment Terms", "supplier-search"):
        assert marker in text
