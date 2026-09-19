"""Provider-neutral external integration hub for Phase 8.17.

The hub is the single application boundary for external providers. It keeps
provider credentials out of application/database records, supports hotel-scoped
configuration in memory, exposes health/webhook contracts, and routes AI
integration requests through registered adapters. Real vendor SDKs can be
attached later without changing the AI/business layers.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from ai.context import AIRequestContext
from ai.service import AIRequest, AIResponse, service as ai_service
from ai.observability import observability


INTEGRATIONS = (
    ("whatsapp", "WhatsApp", "communication"),
    ("email", "Email", "communication"),
    ("sms", "SMS", "communication"),
    ("voice", "Voice Provider", "voice"),
    ("payment_gateway", "Payment Gateway", "payment"),
    ("maps", "Maps", "location"),
    ("ride_provider", "Ride / Transportation Provider", "transportation"),
    ("food_delivery", "Food Delivery", "food"),
)

_STATUSES = {"not_configured", "configured", "healthy", "degraded", "error", "disabled"}


class IntegrationProvider(Protocol):
    name: str

    def health(self) -> dict[str, Any]: ...

    def execute(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class ProviderUnavailable:
    name = "none"

    def health(self) -> dict[str, Any]:
        return {"status": "not_configured", "provider": self.name}

    def execute(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("Integration provider is not configured.")


@dataclass(frozen=True)
class IntegrationConfig:
    hotel_id: int
    integration: str
    provider: str
    enabled: bool
    configured: bool
    credential_reference: str | None = None
    endpoint: str | None = None

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Never expose actual credential material; only a non-secret reference.
        return data


@dataclass(frozen=True)
class WebhookEvent:
    integration: str
    event_type: str
    event_id: str
    received_at: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AIIntegrationResponse:
    integration: str
    operation: str
    status: str
    provider: str
    conversation_id: str | None
    ai_response: AIResponse | None
    provider_result: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.ai_response is not None:
            data["ai_response"] = self.ai_response.to_dict()
        return data


class IntegrationHub:
    """Central registry/configuration/execution boundary for external services."""

    def __init__(self) -> None:
        self._providers: dict[tuple[str, int], IntegrationProvider] = {}
        self._configs: dict[tuple[str, int], IntegrationConfig] = {}

    def integration_registry(self) -> list[dict[str, Any]]:
        return [
            {
                "code": code,
                "name": name,
                "category": category,
                "hotel_scoped": True,
                "credential_safe": True,
                "webhook_supported": True,
            }
            for code, name, category in INTEGRATIONS
        ]

    def _validate_integration(self, integration: str) -> str:
        value = "_".join(str(integration or "").strip().lower().replace("-", " ").split())
        if value not in {code for code, _, _ in INTEGRATIONS}:
            raise ValueError("Unsupported integration.")
        return value

    def configure(
        self,
        context: AIRequestContext,
        integration: str,
        provider: str,
        enabled: bool = True,
        configured: bool = False,
        credential_reference: str | None = None,
        endpoint: str | None = None,
    ) -> IntegrationConfig:
        code = self._validate_integration(integration)
        provider_name = str(provider or "none").strip() or "none"
        reference = str(credential_reference or "").strip() or None
        # credential_reference is intentionally not accepted as a secret value.
        if reference and len(reference) > 200:
            raise ValueError("credential_reference is too long.")
        config = IntegrationConfig(
            hotel_id=context.hotel_id,
            integration=code,
            provider=provider_name,
            enabled=bool(enabled),
            configured=bool(configured),
            credential_reference=reference,
            endpoint=str(endpoint or "").strip() or None,
        )
        self._configs[(context.hotel_id, code)] = config
        return config

    def _config(self, hotel_id: int, integration: str) -> IntegrationConfig:
        return self._configs.get(
            (hotel_id, integration),
            IntegrationConfig(hotel_id, integration, "none", False, False),
        )

    def status(self, context: AIRequestContext, integration: str | None = None) -> list[dict[str, Any]]:
        codes = [self._validate_integration(integration)] if integration else [code for code, _, _ in INTEGRATIONS]
        result = []
        for code in codes:
            config = self._config(context.hotel_id, code)
            provider = self._providers.get((context.hotel_id, code), ProviderUnavailable())
            health = provider.health()
            status = health.get("status", "not_configured")
            if not config.enabled:
                status = "disabled"
            elif not config.configured:
                status = "not_configured"
            result.append({**config.public_dict(), "status": status, "health": health})
        return result

    def register_provider(self, context: AIRequestContext, integration: str, provider: IntegrationProvider) -> None:
        code = self._validate_integration(integration)
        if not getattr(provider, "name", "").strip():
            raise ValueError("Provider name is required.")
        self._providers[(context.hotel_id, code)] = provider

    def webhook(self, context: AIRequestContext, integration: str, event_type: str, event_id: str, payload: dict[str, Any]) -> WebhookEvent:
        code = self._validate_integration(integration)
        event = str(event_type or "").strip()
        identifier = str(event_id or "").strip()
        if not event or not identifier:
            raise ValueError("event_type and event_id are required.")
        if not isinstance(payload, dict):
            raise ValueError("Webhook payload must be an object.")
        # Return a normalized event. Persistence/deduplication is intentionally
        # delegated to the future integration storage layer.
        observability.record_integration(context, code, f"webhook:{event}", "SUCCESS")
        return WebhookEvent(code, event, identifier, datetime.now(timezone.utc).isoformat(), dict(payload))

    def execute(
        self,
        context: AIRequestContext,
        integration: str,
        operation: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        code = self._validate_integration(integration)
        config = self._config(context.hotel_id, code)
        if not config.enabled or not config.configured:
            raise RuntimeError("Integration provider is not configured or enabled.")
        provider = self._providers.get((context.hotel_id, code), ProviderUnavailable())
        if not str(operation or "").strip():
            raise ValueError("Integration operation is required.")
        if not isinstance(payload, dict):
            raise ValueError("Integration payload must be an object.")
        op = str(operation).strip()
        started = observability.start_timer()
        try:
            result = provider.execute(op, dict(payload))
            observability.record_integration(
                context, code, op, "SUCCESS", duration_ms=observability.elapsed_ms(started)
            )
            return result
        except Exception:
            observability.record_integration(
                context, code, op, "FAILED", duration_ms=observability.elapsed_ms(started)
            )
            raise

    def process_ai(
        self,
        context: AIRequestContext,
        integration: str,
        operation: str,
        message: str,
        conversation_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AIIntegrationResponse:
        code = self._validate_integration(integration)
        text = str(message or "").strip()
        if not text:
            raise ValueError("AI integration message is required.")
        ai_response = ai_service.process(
            AIRequest(message=text, context=context, conversation_id=conversation_id)
        )
        provider_result = None
        status = "ai_processed"
        config = self._config(context.hotel_id, code)
        if config.enabled and config.configured:
            try:
                provider_result = self.execute(context, code, operation, payload or {})
                status = "completed"
            except RuntimeError as exc:
                status = "provider_unavailable"
                provider_result = {"status": status, "error": str(exc)}
        return AIIntegrationResponse(
            integration=code,
            operation=str(operation).strip(),
            status=status,
            provider=config.provider,
            conversation_id=ai_response.conversation_id,
            ai_response=ai_response,
            provider_result=provider_result,
        )


integration_hub = IntegrationHub()
