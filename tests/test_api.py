from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_root_and_health():
    assert client.get("/").status_code == 200
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_documentation():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert document["info"]["version"] == "1.0.0"
    assert "/api/v1/auth/login" in document["paths"]
    assert "/api/v1/rooms" in document["paths"]
    assert "/api/v1/reports/dashboard" in document["paths"]
    assert "/api/v1/ai/tools" in document["paths"]


def test_protected_route_requires_authentication():
    response = client.get("/api/v1/customers")
    assert response.status_code == 401


def test_invalid_login_is_rejected():
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "__invalid_api_user__", "password": "invalid-password"},
    )
    assert response.status_code == 401
