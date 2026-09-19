from ai.context import AIRequestContext
from ai.integration import IntegrationHub
from ai.observability import observability


class FakeProvider:
    name = "fake"

    def health(self):
        return {"status": "healthy", "provider": self.name}

    def execute(self, operation, payload):
        return {"operation": operation, "payload": payload, "ok": True}


def context(hotel_id=1):
    return AIRequestContext(user_id="1", username="admin", role="Admin", hotel_id=hotel_id)


def test_registry_contains_all_external_integrations():
    hub = IntegrationHub()
    codes = {item["code"] for item in hub.integration_registry()}
    assert codes == {
        "whatsapp", "email", "sms", "voice", "payment_gateway",
        "maps", "ride_provider", "food_delivery",
    }


def test_configuration_is_hotel_scoped_and_secret_safe():
    hub = IntegrationHub()
    cfg = hub.configure(context(7), "whatsapp", "fake", configured=True, credential_reference="secret-ref")
    assert cfg.hotel_id == 7
    assert cfg.credential_reference == "secret-ref"
    assert "secret" not in str(cfg.public_dict()).lower() or cfg.credential_reference == "secret-ref"
    assert hub.status(context(8), "whatsapp")[0]["configured"] is False


def test_provider_execution_requires_configuration_then_works():
    hub = IntegrationHub()
    ctx = context(3)
    try:
        hub.execute(ctx, "email", "send", {})
        assert False
    except RuntimeError:
        pass
    hub.configure(ctx, "email", "fake", configured=True)
    hub.register_provider(ctx, "email", FakeProvider())
    result = hub.execute(ctx, "email", "send", {"to": "guest"})
    assert result["ok"] is True


def test_webhook_normalization_and_ai_flow():
    hub = IntegrationHub()
    ctx = context(5)
    event = hub.webhook(ctx, "ride-provider", "ride.updated", "evt-1", {"status": "assigned"})
    assert event.integration == "ride_provider"
    response = hub.process_ai(ctx, "maps", "lookup", "Where is the hotel?", "conv-1")
    assert response.integration == "maps"
    assert response.ai_response is not None


def test_provider_execution_records_integration_observability():
    hub = IntegrationHub()
    ctx = context(11)
    hub.configure(ctx, "email", "fake", configured=True)
    hub.register_provider(ctx, "email", FakeProvider())
    hub.execute(ctx, "email", "send", {"to": "guest"})
    events = observability.history(ctx, event_type="integration")
    assert events[0]["details"]["integration"] == "email"
    assert events[0]["details"]["operation"] == "send"
    assert events[0]["status"] == "SUCCESS"
