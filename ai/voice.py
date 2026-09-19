"""Provider-neutral Voice AI Agent foundation for Phase 8.8.

The voice layer owns the voice pipeline boundary only. It does not execute SQL,
implement a vendor SDK, or bypass the central AI agent. Real speech providers
can be attached later through the small STT/TTS adapter contracts defined here.
"""

from dataclasses import asdict, dataclass
from typing import Protocol

from ai.context import AIRequestContext
from ai.service import AIRequest, AIResponse, service as ai_service


VOICE_USE_CASES = (
    ("hotel_phone_reception", "Hotel phone reception"),
    ("reception_desk_assistant", "Reception desk assistant"),
    ("guest_room_voice_assistant", "Guest-room voice assistant"),
    ("staff_voice_assistant", "Staff voice assistant"),
)

VOICE_INPUT_TYPES = {"transcript", "audio_reference"}


class SpeechToTextProvider(Protocol):
    """Provider contract for converting incoming speech to text."""

    name: str

    def transcribe(self, audio_reference: str) -> str: ...


class TextToSpeechProvider(Protocol):
    """Provider contract for converting the agent response to speech."""

    name: str

    def synthesize(self, text: str) -> str: ...


class UnavailableSpeechToText:
    name = "none"

    def transcribe(self, audio_reference: str) -> str:
        raise RuntimeError("Speech-to-text provider is not configured.")


class UnavailableTextToSpeech:
    name = "none"

    def synthesize(self, text: str) -> str:
        raise RuntimeError("Text-to-speech provider is not configured.")


@dataclass(frozen=True)
class VoiceRequest:
    context: AIRequestContext
    input_type: str
    transcript: str | None = None
    audio_reference: str | None = None
    conversation_id: str | None = None
    use_case: str = "hotel_phone_reception"
    handoff_requested: bool = False


@dataclass(frozen=True)
class VoiceResponse:
    status: str
    handled: bool
    use_case: str
    use_case_name: str
    conversation_id: str | None
    transcript: str | None
    text_response: str
    speech_to_text: dict
    text_to_speech: dict
    ai_response: AIResponse | None = None
    human_handoff: dict | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        if self.ai_response is not None:
            payload["ai_response"] = self.ai_response.to_dict()
        return payload


class VoiceAIAgent:
    """Controlled voice pipeline: input -> STT -> AI -> TTS -> response."""

    _HANDOFF_PHRASES = (
        "human",
        "human agent",
        "real person",
        "receptionist",
        "staff member",
        "speak to someone",
        "talk to someone",
        "transfer me",
        "manager",
        "talk to the manager",
        "speak to the manager",
        "human manager",
    )

    def __init__(
        self,
        stt_provider: SpeechToTextProvider | None = None,
        tts_provider: TextToSpeechProvider | None = None,
    ):
        self.stt_provider = stt_provider or UnavailableSpeechToText()
        self.tts_provider = tts_provider or UnavailableTextToSpeech()

    def use_case_registry(self) -> list[dict]:
        return [
            {
                "code": code,
                "name": name,
                "central_ai_agent": True,
                "human_handoff": True,
            }
            for code, name in VOICE_USE_CASES
        ]

    def _normalize_use_case(self, use_case: str) -> tuple[str, str]:
        value = "_".join(str(use_case or "").strip().lower().replace("-", " ").split())
        for code, name in VOICE_USE_CASES:
            if value == code:
                return code, name
        raise ValueError("Unsupported voice use case.")

    def _resolve_transcript(self, request: VoiceRequest) -> tuple[str, dict]:
        if request.input_type not in VOICE_INPUT_TYPES:
            raise ValueError("Unsupported voice input type.")

        if request.input_type == "transcript":
            transcript = str(request.transcript or "").strip()
            if not transcript:
                raise ValueError("Transcript is required for transcript voice input.")
            return transcript, {
                "status": "success",
                "provider": "client_transcript",
                "input_type": "transcript",
            }

        audio_reference = str(request.audio_reference or "").strip()
        if not audio_reference:
            raise ValueError("Audio reference is required for audio voice input.")
        try:
            transcript = str(self.stt_provider.transcribe(audio_reference) or "").strip()
        except RuntimeError as exc:
            return "", {
                "status": "provider_unavailable",
                "provider": getattr(self.stt_provider, "name", "none"),
                "input_type": "audio_reference",
                "error": str(exc),
            }
        if not transcript:
            return "", {
                "status": "empty_transcript",
                "provider": getattr(self.stt_provider, "name", "none"),
                "input_type": "audio_reference",
            }
        return transcript, {
            "status": "success",
            "provider": getattr(self.stt_provider, "name", "none"),
            "input_type": "audio_reference",
        }

    def _handoff(self, conversation_id: str | None, reason: str) -> dict:
        return {
            "status": "requested",
            "conversation_id": conversation_id,
            "reason": reason,
            "target": "human_staff",
            "provider": "internal_handoff_foundation",
        }

    def _synthesize(self, text: str) -> dict:
        try:
            audio_reference = self.tts_provider.synthesize(text)
        except RuntimeError as exc:
            return {
                "status": "provider_unavailable",
                "provider": getattr(self.tts_provider, "name", "none"),
                "audio_reference": None,
                "error": str(exc),
            }
        return {
            "status": "success",
            "provider": getattr(self.tts_provider, "name", "none"),
            "audio_reference": audio_reference,
        }

    def process(self, request: VoiceRequest) -> VoiceResponse:
        use_case, use_case_name = self._normalize_use_case(request.use_case)
        transcript, stt_result = self._resolve_transcript(request)
        conversation_id = request.conversation_id

        if stt_result["status"] != "success":
            return VoiceResponse(
                status="speech_to_text_unavailable",
                handled=False,
                use_case=use_case,
                use_case_name=use_case_name,
                conversation_id=conversation_id,
                transcript=None,
                text_response="Voice input could not be converted to text because the speech-to-text provider is not configured.",
                speech_to_text=stt_result,
                text_to_speech={"status": "not_started"},
            )

        handoff = request.handoff_requested or any(
            phrase in transcript.lower() for phrase in self._HANDOFF_PHRASES
        )
        if handoff:
            handoff_data = self._handoff(conversation_id, "guest_or_staff_requested_human_assistance")
            text_response = "I can transfer this conversation to a human staff member."
            return VoiceResponse(
                status="human_handoff_requested",
                handled=True,
                use_case=use_case,
                use_case_name=use_case_name,
                conversation_id=conversation_id,
                transcript=transcript,
                text_response=text_response,
                speech_to_text=stt_result,
                text_to_speech=self._synthesize(text_response),
                human_handoff=handoff_data,
            )

        ai_response = ai_service.process(
            AIRequest(
                message=transcript,
                context=request.context,
                conversation_id=conversation_id,
            )
        )
        conversation_id = ai_response.conversation_id
        text_response = ai_response.message
        tts_result = self._synthesize(text_response)

        return VoiceResponse(
            status="voice_response_ready" if tts_result["status"] == "success" else "text_response_ready",
            handled=ai_response.handled,
            use_case=use_case,
            use_case_name=use_case_name,
            conversation_id=conversation_id,
            transcript=transcript,
            text_response=text_response,
            speech_to_text=stt_result,
            text_to_speech=tts_result,
            ai_response=ai_response,
        )


voice_agent = VoiceAIAgent()
