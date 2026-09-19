from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_ai_tool_registry_covers_locked_82_categories():
    from database.ai_tools_db import get_tool_registry
    names = {tool["name"] for tool in get_tool_registry()}
    expected = {"hotel_information","guest_information","room_availability","room_booking_information","table_information","restaurant_information","billing_information","inventory_information","staff_information","expense_information","feedback_information","notification_information","transportation_information","maps_information","media_information","reports_summary","audit_information"}
    assert expected <= names
    assert len(names) == 17

def test_all_registered_tools_are_contract_and_hotel_scoped():
    from database.ai_tools_db import get_tool_registry
    for tool in get_tool_registry():
        assert tool["read_only"] is True
        assert tool["hotel_scoped"] is True
        assert tool["permission"]["action"] == "View"
        assert tool["version"]

def test_tool_execution_rejects_unknown_arguments():
    from database.ai_tools_db import execute_ai_tool
    try:
        execute_ai_tool("hotel_information", {"unexpected": "value"})
    except ValueError as exc:
        assert "Unknown argument" in str(exc)
    else:
        raise AssertionError("Unknown tool arguments must be rejected")

def test_ai_route_passes_authenticated_user_to_tool_execution():
    source = (ROOT / "api" / "routes" / "ai.py").read_text(encoding="utf-8")
    assert "execute_ai_tool(tool_name, payload.arguments, user=user)" in source
    assert "status_code=403" in source


def test_inventory_ai_tool_uses_explicit_authenticated_context(monkeypatch):
    from database.ai_tools_db import execute_ai_tool
    captured = {}
    monkeypatch.setattr("database.permission_db.has_permission", lambda user_id, module, action: True)
    monkeypatch.setattr("database.inventory_db.get_low_stock_items", lambda **kwargs: captured.setdefault("low", kwargs) or [])
    monkeypatch.setattr("database.inventory_db.get_inventory_valuation", lambda **kwargs: captured.setdefault("valuation", kwargs) or [])
    result = execute_ai_tool(
        "inventory_information",
        {"low_stock_only": True},
        user={"user_id": "ADMIN1001", "hotel_id": 1},
    )
    assert result["hotel_id"] == 1
    assert captured["low"]["user_id"] == "ADMIN1001"
    assert captured["low"]["hotel_id"] == 1
