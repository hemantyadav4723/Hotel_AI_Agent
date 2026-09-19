from pathlib import Path

import pytest

from ai.context import AIRequestContext
from ai.service import AIResponse
from ai.voice import VoiceAIAgent, VoiceRequest, voice_agent

ROOT = Path(__file__).resolve().parents[1]


def context():
    return AIRequestContext(user_id="u1", username="admin", role="Admin", hotel_id=1)


def test_voice_use_cases_match_locked_order():
    assert [item["name"] for item in voice_agent.use_case_registry()] == [
        "Hotel phone reception",
        "Reception desk assistant",
        "Guest-room voice assistant",
        "Staff voice assistant",
    ]
    assert all(item["central_ai_agent"] for item in voice_agent.use_case_registry())


def test_transcript_input_completes_voice_pipeline_to_central_ai(monkeypatch):
    expected = AIResponse(
        status="handled_with_tool",
        handled=True,
        message="Hotel information retrieved.",
        provider="none",
        model=None,
        hotel_id=1,
        conversation_id="conv_voice",
        intent="hotel_information",
    )
    captured = {}

    class TTS:
        name = "test-tts"

        def synthesize(self, text):
            captured["tts_text"] = text
            return "audio://response-1"

    def fake_process(request):
        captured["request"] = request
        return expected

    monkeypatch.setattr("ai.voice.ai_service.process", fake_process)
    agent = VoiceAIAgent(tts_provider=TTS())
    response = agent.process(
        VoiceRequest(
            context(),
            "transcript",
            transcript="tell me hotel information",
            conversation_id="conv_voice",
            use_case="hotel_phone_reception",
        )
    )
    assert response.status == "voice_response_ready"
    assert response.transcript == "tell me hotel information"
    assert response.speech_to_text["status"] == "success"
    assert response.text_to_speech["status"] == "success"
    assert response.text_to_speech["audio_reference"] == "audio://response-1"
    assert captured["request"].conversation_id == "conv_voice"
    assert captured["request"].context.hotel_id == 1
    assert captured["tts_text"] == expected.message


def test_audio_input_uses_speech_to_text_provider():
    class STT:
        name = "test-stt"

        def transcribe(self, audio_reference):
            assert audio_reference == "audio://input-1"
            return "hotel information"

    agent = VoiceAIAgent(stt_provider=STT())
    response = agent.process(VoiceRequest(context(), "audio_reference", audio_reference="audio://input-1"))
    assert response.transcript == "hotel information"
    assert response.speech_to_text["status"] == "success"
    assert response.speech_to_text["provider"] == "test-stt"


def test_unconfigured_speech_to_text_is_safe():
    response = voice_agent.process(VoiceRequest(context(), "audio_reference", audio_reference="audio://input-1"))
    assert response.status == "speech_to_text_unavailable"
    assert response.handled is False
    assert response.text_to_speech["status"] == "not_started"


def test_text_to_speech_unavailable_keeps_text_response():
    class FakeAI:
        def process(self, request):
            return AIResponse("handled_with_tool", True, "Hotel information retrieved.", "none", None, 1, "conv_1", "hotel_information")

    agent = VoiceAIAgent()
    old = __import__("ai.voice", fromlist=["ai_service"]).ai_service
    import ai.voice as voice_module
    voice_module.ai_service = FakeAI()
    try:
        response = agent.process(VoiceRequest(context(), "transcript", transcript="hotel information"))
    finally:
        voice_module.ai_service = old
    assert response.status == "text_response_ready"
    assert response.text_response == "Hotel information retrieved."
    assert response.text_to_speech["status"] == "provider_unavailable"


def test_human_handoff_keyword_is_captured_before_ai_processing(monkeypatch):
    monkeypatch.setattr("ai.voice.ai_service.process", lambda request: pytest.fail("AI should not be called for handoff"))
    class TTS:
        name = "test-tts"
        def synthesize(self, text):
            return "audio://handoff"

    response = VoiceAIAgent(tts_provider=TTS()).process(
        VoiceRequest(context(), "transcript", transcript="please transfer me to a human", conversation_id="conv_h")
    )
    assert response.status == "human_handoff_requested"
    assert response.human_handoff["status"] == "requested"
    assert response.human_handoff["target"] == "human_staff"
    assert response.text_to_speech["status"] == "success"


def test_explicit_handoff_flag_is_supported():
    response = VoiceAIAgent().process(
        VoiceRequest(context(), "transcript", transcript="I need help", handoff_requested=True)
    )
    assert response.status == "human_handoff_requested"
    assert response.human_handoff["target"] == "human_staff"


def test_invalid_use_case_is_rejected():
    with pytest.raises(ValueError, match="Unsupported voice use case"):
        voice_agent.process(VoiceRequest(context(), "transcript", transcript="hotel information", use_case="unknown"))


def test_invalid_input_type_is_rejected():
    with pytest.raises(ValueError, match="Unsupported voice input type"):
        voice_agent.process(VoiceRequest(context(), "wav", transcript="hotel information"))


def test_transcript_is_required_for_transcript_input():
    with pytest.raises(ValueError, match="Transcript is required"):
        voice_agent.process(VoiceRequest(context(), "transcript"))


def test_audio_reference_is_required_for_audio_input():
    with pytest.raises(ValueError, match="Audio reference is required"):
        voice_agent.process(VoiceRequest(context(), "audio_reference"))


def test_voice_layer_has_no_direct_sqlite_access():
    source = (ROOT / "ai" / "voice.py").read_text(encoding="utf-8").lower()
    assert "sqlite3" not in source
    assert "get_connection" not in source
    assert "select " not in source
    assert "insert " not in source


def test_voice_preserves_hotel_context():
    captured = {}
    expected = AIResponse("handled_with_tool", True, "OK", "none", None, 9, "conv_9", "hotel_information")

    def fake_process(request):
        captured["context"] = request.context
        return expected

    import ai.voice as voice_module
    old = voice_module.ai_service.process
    voice_module.ai_service.process = fake_process
    try:
        response = VoiceAIAgent().process(VoiceRequest(
            AIRequestContext("u9", "staff", "Manager", 9),
            "transcript",
            transcript="hotel information",
        ))
    finally:
        voice_module.ai_service.process = old
    assert response.conversation_id == "conv_9"
    assert captured["context"].hotel_id == 9


def test_voice_response_serializes_nested_ai_response():
    expected = AIResponse("handled_with_tool", True, "OK", "none", None, 1, "conv_x", "hotel_information")
    import ai.voice as voice_module
    old = voice_module.ai_service.process
    voice_module.ai_service.process = lambda request: expected
    try:
        payload = VoiceAIAgent().process(VoiceRequest(context(), "transcript", transcript="hotel information")).to_dict()
    finally:
        voice_module.ai_service.process = old
    assert payload["ai_response"]["conversation_id"] == "conv_x"
    assert payload["speech_to_text"]["status"] == "success"


def test_voice_manager_request_triggers_human_handoff():
    from ai.voice import VoiceAIAgent, VoiceRequest
    from ai.context import AIRequestContext
    response = VoiceAIAgent().process(VoiceRequest(
        context=AIRequestContext("ADMIN1001", "admin1001", "Admin", 1),
        input_type="transcript", transcript="I need to speak to the manager",
        conversation_id="voice-manager",
    ))
    assert response.human_handoff is not None
    assert response.human_handoff["status"] == "requested"
