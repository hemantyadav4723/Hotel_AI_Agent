from pathlib import Path

from fastapi.testclient import TestClient

from ai.context import AIRequestContext
from ai.staff_assistant import AIStaffAssistant, ASSISTANT_AREAS
from api.app import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def context(role="Receptionist"):
    return AIRequestContext(user_id="ADMIN1001", username="admin1001", role=role, hotel_id=1)


def test_role_area_mapping_covers_locked_staff_assistant_areas():
    agent = AIStaffAssistant()
    assert agent.allowed_areas("Receptionist") == ("reception",)
    assert agent.allowed_areas("Housekeeping") == ("housekeeping",)
    assert agent.allowed_areas("Maintenance") == ("maintenance",)
    assert agent.allowed_areas("Restaurant") == ("restaurant_kitchen",)
    assert agent.allowed_areas("Laundry") == ("laundry",)
    assert agent.allowed_areas("Concierge") == ("transport_concierge",)
    assert set(agent.allowed_areas("Manager")) == {code for code, _ in ASSISTANT_AREAS}


def test_reception_assistant_uses_only_reception_capabilities():
    response = AIStaffAssistant().process("show available rooms", context("Receptionist"))
    assert response.status in {"handled_with_tool", "partially_handled", "tool_execution_failed"}
    assert response.assistant_area == "reception"
    assert "room_availability" in response.allowed_tools


def test_role_cannot_request_management_area():
    response = AIStaffAssistant().process(
        "show today's revenue report",
        context("Housekeeping"),
        assistant_area="management",
    )
    assert response.status == "restricted"
    assert response.handled is False


def test_multi_area_role_requires_area():
    response = AIStaffAssistant().process("show available rooms", context("Manager"))
    assert response.status == "restricted"
    assert "specify" in response.message.lower()


def test_staff_assistant_rejects_action_requests():
    response = AIStaffAssistant().process("book room 101", context("Receptionist"))
    assert response.status == "restricted"
    assert response.handled is False


def test_unknown_request_is_not_executed():
    response = AIStaffAssistant().process("tell me a joke", context("Receptionist"))
    assert response.status == "unknown_request"
    assert response.handled is False


def test_area_registry_is_role_aware():
    registry = AIStaffAssistant().area_registry("Housekeeping")
    areas = {item["code"]: item for item in registry}
    assert areas["housekeeping"]["allowed"] is True
    assert areas["management"]["allowed"] is False


def test_staff_assistant_api_requires_authentication():
    response = client.post("/api/v1/ai/staff-assistant", json={"message": "show available rooms"})
    assert response.status_code == 401


def test_staff_assistant_api_is_in_openapi():
    document = client.get("/openapi.json").json()
    assert "/api/v1/ai/staff-assistant" in document["paths"]
    assert "/api/v1/ai/staff-assistant/areas" in document["paths"]
    assert "AIStaffAssistantRequest" in document["components"]["schemas"]
