from fastapi.testclient import TestClient
from api.app import app

def test_notification_routes_require_view_permission():
    client = TestClient(app)
    for path in ("/api/v1/notifications", "/api/v1/notifications/channels"):
        assert client.get(path).status_code == 401

def test_notification_read_route_requires_authentication():
    client = TestClient(app)
    assert client.post("/api/v1/notifications/NTFD-INVALID/read", json={}).status_code == 401

def test_notification_dashboard_features_present():
    client = TestClient(app)
    js = client.get("/dashboard/app.js").text
    assert 'notifications:["Reports","View"]' in js
    for field in ("notification-search", "notification-event", "notification-channel", "notification-status", "notification-unread"):
        assert field in js
    for event in ("Booking", "Payment", "Cancellation", "Check-in", "Check-out", "Low Stock", "Feedback", "Transportation"):
        assert event in js
