"""Gemini text provider for the controlled hotel AI response layer.

The provider receives only the user's message and already-summarized results
from the controlled AI tool layer. It never queries SQLite or executes hotel
operations directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai.config import settings


@dataclass(frozen=True)
class GeminiProvider:
    """Small provider adapter around Google's official Gen AI Python SDK."""

    api_key: str
    model: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("Gemini API key is required.")
        if not self.model:
            raise ValueError("Gemini model is required.")

    def generate_reply(
        self,
        *,
        user_message: str,
        tool_summaries: list[str],
        hotel_id: int,
    ) -> str:
        """Generate a concise response from safe, pre-retrieved hotel summaries."""
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "Gemini provider requires the google-genai package."
            ) from exc

        client = genai.Client(api_key=self.api_key)
        summaries = "\n".join(f"- {item}" for item in tool_summaries)
        prompt = (
            "You are the YADAV HOTEL AI assistant. "
            "Answer the guest's request clearly and concisely. "
            "Use ONLY the supplied hotel-information summaries; do not invent "
            "hotel facts, prices, availability, policies, bookings, or actions. "
            "Do not claim that you performed an action. "
            f"Hotel scope ID: {hotel_id}.\n\n"
            f"Guest request: {user_message}\n\n"
            f"Verified tool summaries:\n{summaries}"
        )
        response = client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text


def get_gemini_provider() -> GeminiProvider | None:
    """Return the configured Gemini provider, or None when another provider is set."""
    if settings.provider.strip().lower() != "gemini":
        return None
    return GeminiProvider(
        api_key=settings.api_key,
        model=settings.model,
        timeout_seconds=settings.request_timeout_seconds,
    )
