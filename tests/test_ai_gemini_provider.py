from dataclasses import dataclass

import pytest

from ai.providers.gemini import GeminiProvider


def test_gemini_provider_requires_credentials():
    with pytest.raises(ValueError):
        GeminiProvider(api_key="", model="gemini-2.5-flash-lite")
    with pytest.raises(ValueError):
        GeminiProvider(api_key="secret", model="")


def test_gemini_provider_uses_sdk_and_safe_summary(monkeypatch):
    captured = {}

    class FakeResponse:
        text = "Verified hotel information."

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.models = FakeModels()

    class FakeGenAI:
        Client = FakeClient

    monkeypatch.setitem(__import__("sys").modules, "google", type("Google", (), {"genai": FakeGenAI}))

    provider = GeminiProvider(api_key="secret", model="gemini-2.5-flash-lite")
    result = provider.generate_reply(
        user_message="What are the hotel facilities?",
        tool_summaries=["I retrieved the available facilities for YADAV HOTEL."],
        hotel_id=1,
    )

    assert result == "Verified hotel information."
    assert captured["api_key"] == "secret"
    assert captured["model"] == "gemini-2.5-flash-lite"
    assert "I retrieved the available facilities" in captured["contents"]
    assert "hotel_id" not in captured["contents"].lower()
