from pathlib import Path

from ai.context import AIRequestContext
from ai.service import AIAgentCore, AIRequest, AIService

ROOT = Path(__file__).resolve().parents[1]


def context():
    return AIRequestContext(user_id="u1", username="admin", role="Admin", hotel_id=1)


def test_intent_detection_routes_hotel_information():
    decision = AIAgentCore().decide_intent("show hotel information and facilities")
    assert "hotel_information" in decision.tool_names
    assert decision.action_required is False


def test_intent_detection_extracts_booking_id():
    decision = AIAgentCore().decide_intent("show booking ID BK123")
    assert decision.tool_names == ("room_booking_information",)
    assert decision.arguments["booking_id"] == "BK123"


def test_multi_tool_intent_is_bounded():
    decision = AIAgentCore().decide_intent("show hotel information and room availability and restaurant")
    assert decision.intent == "multi_tool"
    assert 1 <= len(decision.tool_names) <= 3


def test_action_intent_is_separated_from_read_execution():
    response = AIAgentCore().process(AIRequest("book a room", context()))
    assert response.status == "confirmation_required"
    assert response.confirmation_required is True
    assert response.handled is False
    assert response.tool_calls == ()


def test_unknown_intent_is_safe():
    response = AIAgentCore().process(AIRequest("tell me something unrelated", context()))
    assert response.status == "unknown_intent"
    assert response.handled is False
    assert response.intent == "unknown"


def test_conversation_id_is_preserved_or_generated():
    core = AIAgentCore()
    supplied = core.process(AIRequest("hotel information", context(), "conv_existing"))
    assert supplied.conversation_id == "conv_existing"
    generated = core.process(AIRequest("hotel information", context()))
    assert generated.conversation_id
    assert generated.conversation_id.startswith("conv_")


def test_tool_argument_contract_filters_unrelated_arguments():
    core = AIAgentCore()
    args = core._tool_arguments("hotel_information", {"booking_id": "BK1", "unexpected": "x"})
    assert args == {}


def test_agent_core_has_no_direct_sql_interface():
    source = (ROOT / "ai" / "service.py").read_text(encoding="utf-8").lower()
    assert "select " not in source
    assert "sqlite3" not in source
    assert "get_connection" not in source


def test_service_delegates_to_agent_core():
    service = AIService(AIAgentCore())
    response = service.process(AIRequest("hotel information", context()))
    assert response.status in {"handled_with_tool", "partially_handled", "tool_execution_failed"}


def test_ai_request_core_does_not_execute_mutation_tools():
    response = AIAgentCore().process(AIRequest("cancel booking BK123", context()))
    assert response.confirmation_required is True
    assert response.tool_calls == ()
