from fastapi.testclient import TestClient

from api.app import app


def test_dashboard_route_is_available():
    client = TestClient(app)
    response = client.get("/dashboard/", follow_redirects=True)
    assert response.status_code == 200
    assert "YADAV HOTEL" in response.text


def test_auth_endpoints_are_wired():
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/me" in paths
    assert "/api/v1/auth/change-password" in paths

    response = client.post("/api/v1/auth/login", json={"username":"invalid-user","password":"invalid-password","hotel_id":1})
    assert response.status_code == 401


def test_dashboard_assets_are_available():
    client = TestClient(app)
    css = client.get("/dashboard/styles.css")
    js = client.get("/dashboard/app.js")
    assert css.status_code == 200
    assert js.status_code == 200
