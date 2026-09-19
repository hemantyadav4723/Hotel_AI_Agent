from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.js"
ROUTES = ROOT / "api" / "routes" / "experience.py"
SCHEMAS = ROOT / "api" / "schemas.py"
DB = ROOT / "database" / "feedback_db.py"


def test_feedback_dashboard_covers_guest_experience_scope():
    text = APP.read_text(encoding="utf-8")
    for token in (
        "Feedback & Guest Experience", "Guest Satisfaction Data", "Complaint Management",
        "Feedback / Reviews", "feedback-category", "feedback-rating", "feedback-status",
        "feedback-complaints", "feedback-follow", "Follow-up Required", "Follow-up Method",
        "Follow-up Status", "Resolution", "Issue",
    ):
        assert token in text


def test_feedback_api_supports_filters_and_complaint_management():
    text = ROUTES.read_text(encoding="utf-8")
    for token in (
        '@router.get("/feedback")', 'search: str | None', 'category: str | None',
        'status: str | None', 'rating: int | None', 'complaint_only: bool',
        'follow_up_required: bool | None', '@router.patch("/feedback/{feedback_id}")',
        'update_feedback_record',
    ):
        assert token in text


def test_feedback_routes_reuse_customer_rbac_and_hotel_scope():
    text = ROUTES.read_text(encoding="utf-8")
    assert 'require_permission("Customers", "View")' in text
    assert 'require_permission("Customers", "Create")' in text
    assert 'require_permission("Customers", "Update")' in text
    assert 'user["hotel_id"]' in text


def test_feedback_update_uses_existing_validation_and_database():
    assert "class FeedbackUpdate" in SCHEMAS.read_text(encoding="utf-8")
    text = DB.read_text(encoding="utf-8")
    assert "def update_feedback_record(" in text
    assert "_validate_feedback_fields(" in text
    assert "WHERE feedback_id=? AND hotel_id=?" in text
