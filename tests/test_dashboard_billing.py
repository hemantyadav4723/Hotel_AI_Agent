from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.js"
FINANCE = ROOT / "api" / "routes" / "finance.py"


def test_billing_dashboard_has_required_sections():
    text = APP.read_text(encoding="utf-8")
    for token in ("Billing & Payments", "/billing/summary", "/billing/invoices", "Invoice Details"):
        assert token in text


def test_billing_api_supports_invoice_search_and_detail():
    text = FINANCE.read_text(encoding="utf-8")
    for token in ("/billing/invoices", "/billing/invoices/{invoice_number}", "/billing/summary"):
        assert token in text


def test_billing_payment_actions_are_permission_protected():
    text = FINANCE.read_text(encoding="utf-8")
    assert 'require_permission("Rooms", "Payment")' in text
    assert 'require_permission("Restaurant", "Payment")' in text
    assert 'require_permission("Restaurant", "Refund")' in text
