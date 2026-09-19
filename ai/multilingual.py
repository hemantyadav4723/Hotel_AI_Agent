"""Provider-neutral multilingual AI Agent layer for Phase 8.13.

The layer detects or accepts a requested guest language, preserves the existing
central AI Agent/tool architecture, and localizes deterministic agent responses.
External translation providers are intentionally not required; additional
languages can be registered through the configurable registry.
"""

from dataclasses import asdict, dataclass
import re
from typing import Any

from ai.config import settings
from ai.context import AIRequestContext
from ai.service import AIRequest, AIResponse, service as ai_service


LANGUAGES = (
    ("en", "English"),
    ("hi", "Hindi"),
    ("hinglish", "Hinglish"),
)

_LANGUAGE_NAMES = {code: name for code, name in LANGUAGES}
_LANGUAGE_ALIASES = {
    "english": "en",
    "en-us": "en",
    "en-in": "en",
    "hindi": "hi",
    "हिंदी": "hi",
    "hi-in": "hi",
    "hinglish": "hinglish",
    "hi-en": "hinglish",
}

# Common Roman-Hindi signals used only for deterministic Hinglish detection.
_HINGLISH_WORDS = {
    "hai", "hain", "mujhe", "mera", "meri", "mere", "aap", "apko", "kya",
    "chahiye", "batao", "bata", "karna", "karo", "krdo", "kaise", "kitna",
    "kitne", "kab", "kahan", "room", "booking", "chahiye", "please",
}


def _normalize_language(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip().lower()
    if not value:
        return None
    return _LANGUAGE_ALIASES.get(value, value)


@dataclass(frozen=True)
class MultilingualResponse:
    status: str
    detected_language: str
    response_language: str
    language_name: str
    message: str
    original_message: str
    conversation_id: str | None
    intent: str | None
    handled: bool
    confirmation_required: bool
    provider: str
    model: str | None
    hotel_id: int
    ai_response: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


class MultilingualAgent:
    """Language boundary around the existing central AI Agent."""

    def __init__(self) -> None:
        self._languages: dict[str, str] = dict(_LANGUAGE_NAMES)

    def register_language(self, code: str, name: str) -> None:
        normalized = _normalize_language(code)
        if not normalized or not re.fullmatch(r"[a-z][a-z0-9_-]{1,20}", normalized):
            raise ValueError("Language code must be a short alphanumeric language identifier.")
        if not str(name).strip() or len(str(name).strip()) > 80:
            raise ValueError("Language name is required and must be at most 80 characters.")
        self._languages[normalized] = str(name).strip()

    def language_registry(self) -> list[dict[str, str]]:
        return [
            {"code": code, "name": name, "configurable": code not in {"en", "hi", "hinglish"}}
            for code, name in self._languages.items()
        ]

    def detect_language(self, message: str) -> str:
        text = str(message or "").strip()
        if not text:
            return "en"
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"
        words = {w.lower() for w in re.findall(r"[A-Za-z]+", text)}
        if len(words & _HINGLISH_WORDS) >= 2:
            return "hinglish"
        return "en"

    @staticmethod
    def _localized_message(response: AIResponse, language: str) -> str:
        # Keep factual tool results intact while localizing the agent's stable
        # response envelope/status messages. Unknown future provider text remains
        # unchanged rather than being silently mistranslated.
        if language == "en":
            return response.message

        if language == "hi":
            messages = {
                "unknown_intent": "Main is hotel request ko samajh nahi saka. Kripya batayein ki aapko hotel ki kaunsi information chahiye.",
                "confirmation_required": "Yeh request hotel action kar sakti hai. Maine abhi koi action execute nahi kiya hai; confirmation zaroori hai.",
                "input_rejected": "AI request configured input limit se zyada hai.",
            }
            return messages.get(response.status, _hindi_tool_summary(response.message))

        if language == "hinglish":
            messages = {
                "unknown_intent": "Mujhe ye hotel request clearly samajh nahi aayi. Batao aapko kaunsi hotel information chahiye.",
                "confirmation_required": "Ye request hotel action kar sakti hai. Maine abhi action execute nahi kiya; confirmation required hai.",
                "input_rejected": "AI request configured input limit se zyada hai.",
            }
            return messages.get(response.status, _hinglish_tool_summary(response.message))

        # Configurable languages use the existing agent text until a translation
        # provider is configured. This keeps the language contract honest.
        return response.message

    @staticmethod
    def _agent_message(message: str, language: str) -> str:
        if language != "hi":
            return message
        # Deterministic foundation mapping for common hotel Hindi phrases so
        # Hindi requests can reach the existing intent/tool layer without
        # creating a second agent. Unknown Hindi text is left unchanged.
        phrase_map = (
            ("होटल की जानकारी", "hotel information"),
            ("होटल जानकारी", "hotel information"),
            ("कमरे की उपलब्धता", "room availability"),
            ("कमरे उपलब्ध", "rooms available"),
            ("रूम बुकिंग", "room booking"),
            ("कमरा बुक", "book room"),
            ("रेस्टोरेंट", "restaurant"),
            ("मेन्यू", "menu"),
            ("टेबल बुकिंग", "table booking"),
            ("बिल की जानकारी", "billing information"),
            ("बुकिंग की जानकारी", "booking information"),
            ("बुकिंग स्टेटस", "booking status"),
            ("शिकायत", "complaint"),
            ("फीडबैक", "feedback"),
            ("लोकेशन", "location"),
            ("मैप", "map"),
            ("पार्किंग", "parking"),
            ("वाईफाई", "wifi"),
            ("लॉन्ड्री", "laundry"),
            ("जानकारी चाहिए", "information"),
        )
        normalized = message
        for source, target in phrase_map:
            normalized = normalized.replace(source, target)
        return normalized

    def process(
        self,
        *,
        message: str,
        context: AIRequestContext,
        language: str | None = None,
        conversation_id: str | None = None,
    ) -> MultilingualResponse:
        original = str(message or "").strip()
        if not original:
            raise ValueError("Message is required.")

        requested = _normalize_language(language)
        detected = self.detect_language(original)
        response_language = requested or detected
        if response_language not in self._languages:
            raise ValueError(f"Unsupported language: {response_language}.")

        agent_message = self._agent_message(original, response_language)
        response = ai_service.process(
            AIRequest(message=agent_message, context=context, conversation_id=conversation_id)
        )
        return MultilingualResponse(
            status=response.status,
            detected_language=detected,
            response_language=response_language,
            language_name=self._languages[response_language],
            message=self._localized_message(response, response_language),
            original_message=original,
            conversation_id=response.conversation_id,
            intent=response.intent,
            handled=response.handled,
            confirmation_required=response.confirmation_required,
            provider=response.provider or settings.provider,
            model=response.model or settings.model or None,
            hotel_id=int(context.hotel_id),
            ai_response=response.to_dict(),
        )


def _hindi_tool_summary(message: str) -> str:
    replacements = (
        ("I retrieved the available information for", "Maine available information retrieve ki hai"),
        ("I found", "Maine"),
        ("available room(s)", "available room(s)"),
        ("I retrieved", "Maine information retrieve ki hai"),
        ("information", "information"),
        ("successfully", "successfully"),
    )
    result = message
    for source, target in replacements:
        result = result.replace(source, target)
    return result


def _hinglish_tool_summary(message: str) -> str:
    replacements = (
        ("I retrieved the available information for", "Maine available information retrieve ki hai for"),
        ("I found", "Maine find kiye"),
        ("I retrieved", "Maine information retrieve ki hai"),
        ("successfully", "successfully"),
    )
    result = message
    for source, target in replacements:
        result = result.replace(source, target)
    return result


multilingual_agent = MultilingualAgent()
