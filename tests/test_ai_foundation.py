from fastapi.testclient import TestClient

from ai.context import AIRequestContext
from ai.service import AIRequest, AIService
from api.app import app


client = TestClient(app)


def test_ai_foundation_modules_exist_and_are_provider_neutral():
    context = AIRequestContext(user_id="u1", username="admin", role="Admin", hotel_id=1)
    response = AIService().process(AIRequest(message="Hello", context=context))
    assert response.status == "foundation_ready"
    assert response.handled is False
    assert response.hotel_id == 1


def test_ai_status_requires_authentication():
    response = client.get("/api/v1/ai/status")
    assert response.status_code == 401


def test_ai_context_requires_authentication():
    response = client.get("/api/v1/ai/context")
    assert response.status_code == 401


def test_ai_request_requires_authentication():
    response = client.post("/api/v1/ai/request", json={"message": "hello"})
    assert response.status_code == 401


def test_ai_request_schema_is_exposed_in_openapi():
    document = client.get("/openapi.json").json()
    assert "/api/v1/ai/status" in document["paths"]
    assert "/api/v1/ai/context" in document["paths"]
    assert "/api/v1/ai/request" in document["paths"]
    assert "AIRequest" in document["components"]["schemas"]
