from pathlib import Path

import pytest

from ai.communication import AICommunicationGateway, CommunicationRequest, gateway
from ai.context import AIRequestContext
from ai.service import AIResponse


ROOT = Path(__file__).resolve().parents[1]


def context():
    return AIRequestContext(user_id="u1", username="admin", role="Admin", hotel_id=1)


def test_all_locked_channels_are_registered():
    registry = gateway.channel_registry()
    assert [item["name"] for item in registry] == [
        "Website / Web App",
        "WhatsApp",
        "Mobile App",
        "Social media",
        "Internal hotel system",
        "QR code",
    ]
    assert all(item["central_ai_agent"] is True for item in registry)


def test_channel_aliases_normalize_to_controlled_codes():
    adapter = AICommunicationGateway()
    assert adapter.normalize_channel("Website / Web App") == "website_web_app"
    assert adapter.normalize_channel("whatsapp") == "whatsapp"
    assert adapter.normalize_channel("Mobile") == "mobile_app"
    assert adapter.normalize_channel("Social media") == "social_media"
    assert adapter.normalize_channel("Internal hotel system") == "internal_hotel_system"
    assert adapter.normalize_channel("QR code") == "qr_code"


def test_unknown_channel_is_rejected():
    with pytest.raises(ValueError, match="Unsupported communication channel"):
        gateway.process(CommunicationRequest("hotel information", context(), "email"))


def test_empty_message_is_rejected():
    with pytest.raises(ValueError, match="Communication message is required"):
        gateway.process(CommunicationRequest("   ", context(), "whatsapp"))


def test_channel_routes_to_central_ai_agent(monkeypatch):
    expected = AIResponse(
        status="handled_with_tool",
        handled=True,
        message="Hotel information retrieved.",
        provider="none",
        model=None,
        hotel_id=1,
        conversation_id="conv_123",
        intent="hotel_information",
    )
    captured = {}

    def fake_process(request):
        captured["request"] = request
        return expected

    monkeypatch.setattr("ai.communication.ai_service.process", fake_process)
    response = gateway.process(
        CommunicationRequest("hotel information", context(), "whatsapp", "conv_123")
    )
    assert response.channel == "whatsapp"
    assert response.channel_name == "WhatsApp"
    assert response.channel_status == "integration_pending"
    assert response.conversation_id == "conv_123"
    assert response.ai_response is expected
    assert captured["request"].conversation_id == "conv_123"
    assert captured["request"].context.hotel_id == 1


def test_channel_does_not_directly_access_sqlite():
    source = (ROOT / "ai" / "communication.py").read_text(encoding="utf-8").lower()
    assert "sqlite3" not in source
    assert "get_connection" not in source
    assert "select " not in source


def test_native_and_external_channel_statuses_are_explicit():
    registry = {item["code"]: item["status"] for item in gateway.channel_registry()}
    assert registry["website_web_app"] == "native_api"
    assert registry["mobile_app"] == "native_api"
    assert registry["internal_hotel_system"] == "native_api"
    assert registry["qr_code"] == "entry_point"
    assert registry["whatsapp"] == "integration_pending"
    assert registry["social_media"] == "integration_pending"
