"""Centralized communication gateway for Phase 8.7.

All supported communication channels use one controlled AI-agent entry point.
This module defines channel adapters at the application boundary only; external
provider credentials/webhooks are intentionally left for the later integration
layer. No channel adapter talks directly to the database.
"""

from dataclasses import dataclass, asdict

from ai.context import AIRequestContext
from ai.service import AIRequest, AIResponse, service as ai_service


COMMUNICATION_CHANNELS = (
    ("website_web_app", "Website / Web App", "native_api"),
    ("whatsapp", "WhatsApp", "integration_pending"),
    ("mobile_app", "Mobile App", "native_api"),
    ("social_media", "Social media", "integration_pending"),
    ("internal_hotel_system", "Internal hotel system", "native_api"),
    ("qr_code", "QR code", "entry_point"),
)

_CHANNEL_CODES = {code for code, _, _ in COMMUNICATION_CHANNELS}
_CHANNEL_ALIASES = {
    "website": "website_web_app",
    "web": "website_web_app",
    "web_app": "website_web_app",
    "website/web app": "website_web_app",
    "website / web app": "website_web_app",
    "mobile app": "mobile_app",
    "whatsapp": "whatsapp",
    "mobile": "mobile_app",
    "mobile_app": "mobile_app",
    "social": "social_media",
    "social media": "social_media",
    "internal": "internal_hotel_system",
    "internal hotel system": "internal_hotel_system",
    "qr": "qr_code",
    "qr code": "qr_code",
}


@dataclass(frozen=True)
class CommunicationRequest:
    message: str
    context: AIRequestContext
    channel: str
    conversation_id: str | None = None


@dataclass(frozen=True)
class CommunicationResponse:
    channel: str
    channel_name: str
    channel_status: str
    conversation_id: str | None
    ai_response: AIResponse

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["ai_response"] = self.ai_response.to_dict()
        return payload


class AICommunicationGateway:
    """Route every supported communication channel to the central AI agent."""

    def normalize_channel(self, channel: str) -> str:
        value = " ".join(str(channel or "").strip().lower().split())
        normalized = _CHANNEL_ALIASES.get(value, value)
        if normalized not in _CHANNEL_CODES:
            supported = ", ".join(name for _, name, _ in COMMUNICATION_CHANNELS)
            raise ValueError(f"Unsupported communication channel. Supported channels: {supported}")
        return normalized

    def channel_registry(self) -> list[dict]:
        return [
            {
                "code": code,
                "name": name,
                "status": status,
                "central_ai_agent": True,
            }
            for code, name, status in COMMUNICATION_CHANNELS
        ]

    def process(self, request: CommunicationRequest) -> CommunicationResponse:
        message = str(request.message or "").strip()
        if not message:
            raise ValueError("Communication message is required.")
        channel = self.normalize_channel(request.channel)
        channel_name, channel_status = next(
            (name, status)
            for code, name, status in COMMUNICATION_CHANNELS
            if code == channel
        )

        response = ai_service.process(
            AIRequest(
                message=message,
                context=request.context,
                conversation_id=request.conversation_id,
            )
        )
        return CommunicationResponse(
            channel=channel,
            channel_name=channel_name,
            channel_status=channel_status,
            conversation_id=response.conversation_id,
            ai_response=response,
        )


gateway = AICommunicationGateway()
