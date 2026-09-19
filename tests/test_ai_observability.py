from ai.context import AIRequestContext
from ai.observability import AIObservabilityService


def ctx(hotel=1, user="u1"):
    return AIRequestContext(hotel_id=hotel, user_id=user, username="tester", role="Admin")


def test_registry_and_hotel_scope():
    service = AIObservabilityService()
    assert service.registry()["hotel_scoped"] is True
    service.record_request(ctx(1), "hello", "c1")
    service.record_request(ctx(2), "other", "c2")
    assert len(service.history(ctx(1))) == 1


def test_request_response_tool_and_performance():
    service = AIObservabilityService()
    c = ctx()
    service.record_request(c, "room availability", "c1")
    service.record_tool(c, "room_availability", "success", 2.5, "c1")
    service.record_response(c, {"status": "handled_with_tool", "message": "done", "conversation_id": "c1"}, 5.5)
    service.record_performance(c, "ai_agent_process", 5.5, "c1")
    events = service.history(c, "c1")
    assert {e["event_type"] for e in events} == {"ai_request", "tool_execution", "ai_response", "performance"}


def test_sensitive_data_redacted():
    service = AIObservabilityService()
    e = service._record(ctx(), "ai_action", "SUCCESS", details={"api_key": "secret", "safe": "ok"})
    assert e.details["api_key"] == "[REDACTED]"
    assert e.details["safe"] == "ok"


def test_history_filters_and_limits():
    service = AIObservabilityService()
    c = ctx()
    for i in range(5):
        service.record_conversation(c, f"c{i}", "message")
    assert len(service.history(c, event_type="conversation", limit=2)) == 2
    assert service.history(c, conversation_id="c3")[0]["conversation_id"] == "c3"


def test_handoff_and_integration_events_are_recorded():
    service = AIObservabilityService()
    c = ctx()
    service.record_handoff(c, "requested", "c1")
    service.record_integration(c, "email", "send", "SUCCESS", "c1", 3.2)
    events = service.history(c, "c1")
    assert {e["event_type"] for e in events} == {"handoff", "integration"}
