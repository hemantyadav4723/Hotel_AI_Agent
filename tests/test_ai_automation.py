import pytest

from ai.automation import AIAutomationEngine


def test_detects_automation_types():
    engine = AIAutomationEngine()
    assert engine.detect_type("send a notification") == "notification"
    assert engine.detect_type("create task for room 101") == "task"
    assert engine.detect_type("remind guest tomorrow") == "reminder"
    assert engine.detect_type("escalate request") == "escalation"


def test_confirmation_gate():
    engine = AIAutomationEngine()
    context = type("C", (), {"user_id": "U", "hotel_id": 1})()
    result = engine.process(message="send notification", context=context, automation_type="notification", confirm=False)
    assert result.status == "confirmation_required"
    assert result.confirmation_required is True


def test_unknown_automation():
    engine = AIAutomationEngine()
    context = type("C", (), {"user_id": "U", "hotel_id": 1})()
    result = engine.process(message="hello", context=context)
    assert result.status == "unknown_automation"


def test_unknown_workflow_rejected():
    engine = AIAutomationEngine()
    context = type("C", (), {"user_id": "U", "hotel_id": 1})()
    with pytest.raises(ValueError, match="Unsupported automation workflow"):
        engine.process(message="run", context=context, workflow="not_real")
