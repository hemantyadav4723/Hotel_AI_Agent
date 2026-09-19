from pathlib import Path


def test_hotel_information_dashboard_sections_are_present():
    js = (Path(__file__).resolve().parents[1] / "dashboard" / "app.js").read_text(encoding="utf-8")
    for section in [
        "Hotel Profile", "Contact Information", "Hotel Facilities", "Hotel Timings",
        "Location", "Hotel Policies", "Guest Services", "Dining Information",
        "Room Information", "Banquet / Events", "Transportation Information",
        "Accessibility", "Safety & Security", "AI-readable Hotel Information"
    ]:
        assert section in js


def test_hotel_dashboard_reuses_existing_hotel_apis():
    js = (Path(__file__).resolve().parents[1] / "dashboard" / "app.js").read_text(encoding="utf-8")
    for endpoint in ["/hotel/profile", "/hotel/context", "/hotel/maps", "/hotel/media", "/hotel/settings"]:
        assert endpoint in js
    assert "No dedicated accessibility fields are exposed" in js
    assert "No dedicated safety/security fields are exposed" in js


def test_hotel_context_is_authenticated_and_ignores_browser_hotel_override():
    from api.security import create_access_token
    from api.app import app
    from fastapi.testclient import TestClient

    token = create_access_token(user_id="ADMIN1001", username="admin1001", role="Admin", hotel_id=1)
    client = TestClient(app)
    response = client.get(
        "/api/v1/hotel/context",
        headers={"Authorization": f"Bearer {token}", "X-Hotel-ID": "999"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["hotel_id"] == 1
    assert data["hotel_code"] == "YADAV-HOTEL"


def test_forged_jwt_hotel_scope_cannot_access_unknown_hotel():
    from api.security import create_access_token
    from api.app import app
    from fastapi.testclient import TestClient

    token = create_access_token(user_id="ADMIN1001", username="admin1001", role="Admin", hotel_id=999)
    client = TestClient(app)
    response = client.get("/api/v1/hotel/context", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_dashboard_stores_and_displays_active_hotel_context():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "dashboard" / "app.js").read_text(encoding="utf-8")
    assert "hotelContext" in js
    assert 'state.hotelContext=(await api("/hotel/context")).data||null' in js
    assert "hotel_name" in js
    assert "hotel_code" in js
