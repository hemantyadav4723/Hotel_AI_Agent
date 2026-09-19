from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.js"
AUDIT = ROOT / "database" / "audit_db.py"
ADMIN = ROOT / "api" / "routes" / "admin.py"
API_APP = ROOT / "api" / "app.py"


def test_audit_dashboard_has_locked_sections_and_filters():
    text = APP.read_text(encoding="utf-8")
    for token in (
        "Audit & Activity", "Audit History", "Activity History", "User Activity",
        "Record References", "Request / Correlation Trace", "audit-search",
        "audit-user", "audit-module", "audit-action", "audit-status",
        "audit-start", "audit-end", "audit-request", "data-audit-filter",
        "data-audit-clear", "data-audit-detail",
    ):
        assert token in text


def test_audit_database_supports_request_correlation_and_filters():
    text = AUDIT.read_text(encoding="utf-8")
    for token in (
        "request_id TEXT", "set_request_id", "get_request_id", "idx_audit_request",
        "actor_username", "module", "action", "record_id", "status",
        "date_from", "date_to", "search", "request_id",
    ):
        assert token in text


def test_admin_audit_routes_are_permission_protected_and_filtered():
    text = ADMIN.read_text(encoding="utf-8")
    assert '@router.get("/admin/audit")' in text
    assert '@router.get("/admin/audit/{record_id}")' in text
    assert 'require_permission("Reports", "View")' in text
    for token in ("search", "actor_username", "module", "action", "record_id", "status", "request_id", "date_from", "date_to"):
        assert token in text


def test_request_id_is_connected_to_audit_context():
    text = API_APP.read_text(encoding="utf-8")
    assert "set_request_id(request_id)" in text
    assert "reset_request_id(request_token)" in text
    assert '"X-Request-ID"' in text
