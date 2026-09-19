from types import SimpleNamespace

import pytest

from ai.multilingual import MultilingualAgent
from ai.service import AIResponse


def ctx():
    return SimpleNamespace(hotel_id=1, user_id=1, username="u", role="Manager", conversation_id="c1")


def fake_ai(monkeypatch, message="I retrieved hotel information successfully."):
    response = AIResponse(
        status="handled", handled=True, message=message, provider="none", model=None,
        hotel_id=1, conversation_id="c1", intent="hotel_information"
    )
    monkeypatch.setattr("ai.multilingual.ai_service.process", lambda request: response)


def test_detects_hindi():
    assert MultilingualAgent().detect_language("मुझे होटल की जानकारी चाहिए") == "hi"


def test_detects_hinglish():
    assert MultilingualAgent().detect_language("mujhe room booking ki information chahiye") == "hinglish"


def test_defaults_to_english():
    assert MultilingualAgent().detect_language("Please show hotel information") == "en"


def test_requested_language_overrides_detection(monkeypatch):
    captured = {}
    response = AIResponse(status="handled", handled=True, message="I retrieved hotel information successfully.", provider="none", model=None, hotel_id=1, conversation_id="c1", intent="hotel_information")
    monkeypatch.setattr("ai.multilingual.ai_service.process", lambda request: (captured.update(message=request.message) or response))
    result = MultilingualAgent().process(message="मुझे होटल की जानकारी चाहिए", context=ctx(), language="hi")
    assert captured["message"] == "मुझे hotel information चाहिए"
    assert result.detected_language == "hi"
    assert result.response_language == "hi"
    assert "Maine" in result.message


def test_unknown_configurable_language_rejected(monkeypatch):
    fake_ai(monkeypatch)
    with pytest.raises(ValueError, match="Unsupported language"):
        MultilingualAgent().process(message="hello", context=ctx(), language="fr")


def test_registers_other_configurable_language(monkeypatch):
    fake_ai(monkeypatch)
    agent = MultilingualAgent()
    agent.register_language("fr", "French")
    result = agent.process(message="hello", context=ctx(), language="fr")
    assert result.language_name == "French"
    assert result.response_language == "fr"
    assert result.message == "I retrieved hotel information successfully."


def test_preserves_central_agent_response_metadata(monkeypatch):
    fake_ai(monkeypatch, "I found 2 available room(s) for the requested stay.")
    result = MultilingualAgent().process(message="room availability", context=ctx(), language="hinglish", conversation_id="custom")
    assert result.conversation_id == "c1"
    assert result.intent == "hotel_information"  # returned by the central-agent stub
    assert result.ai_response["handled"] is True
