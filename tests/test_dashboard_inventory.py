from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.js"
ROUTE = ROOT / "api" / "routes" / "inventory.py"
DB = ROOT / "database" / "inventory_db.py"

def test_inventory_dashboard_features():
    s=APP.read_text(encoding="utf-8")
    for term in ["Inventory Items","Low Stock / Reorder","Batch / Lot & Expiry","Stock History","inventory-search"]: assert term in s

def test_inventory_operational_endpoints_and_permissions():
    s=ROUTE.read_text(encoding="utf-8")
    for term in ["/inventory/history","/inventory/batches","/inventory/stock-in","/inventory/stock-out","/inventory/adjustment","/inventory/damaged","/inventory/reorder-level","/inventory/expiry"]: assert term in s
    assert 'require_permission("Inventory", "Create")' in s and 'require_permission("Inventory", "Update")' in s

def test_expiry_business_helper_exists():
    assert "def set_expiry_date(" in DB.read_text(encoding="utf-8")
