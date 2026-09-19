from ai.context import AIRequestContext
from ai.knowledge import KNOWLEDGE_SECTIONS, hotel_knowledge_service


def test_knowledge_registry_covers_locked_sections():
    names = [item["name"] for item in hotel_knowledge_service.section_registry()]
    assert names == list(KNOWLEDGE_SECTIONS)


def test_knowledge_service_uses_ai_tool_layer(monkeypatch):
    calls = []

    def fake_tool(context, name, arguments=None):
        calls.append(name)
        if name == "hotel_information":
            return {"hotel": {"hotel_name": "Test Hotel", "restaurant": "Available", "wifi": "Available"}}
        return {"rooms": []} if name == "room_availability" else {"operational_summary": {}}

    monkeypatch.setattr(hotel_knowledge_service, "_tool", staticmethod(fake_tool))
    response = hotel_knowledge_service.build(
        context=AIRequestContext("1", "manager", "Manager", 1),
        section="hotel_profile",
    )
    assert response.status == "ready"
    assert response.sections["hotel_profile"]["hotel_name"] == "Test Hotel"
    assert response.context["user_id"] == "1"
    assert calls == ["hotel_information"]


def test_all_knowledge_never_invents_unconfigured_sections(monkeypatch):
    def fake_tool(context, name, arguments=None):
        if name == "hotel_information":
            return {"hotel": {"hotel_name": "Test Hotel", "wifi": "Available"}}
        if name == "room_availability":
            return {"rooms": []}
        if name == "restaurant_information":
            return {"operational_summary": {}}
        if name == "maps_information":
            return {"maps": {}}
        if name == "transportation_information":
            return {"transportation": []}
        return {}

    monkeypatch.setattr(hotel_knowledge_service, "_tool", staticmethod(fake_tool))
    response = hotel_knowledge_service.build(
        context=AIRequestContext("1", "manager", "Manager", 1),
        section="all",
    )
    for name in ("policies", "banquet", "services", "faqs"):
        assert response.sections[name]["configured"] is False
        assert response.sections[name]["items"] == []
    assert set(response.unavailable_sections) == {"policies", "banquet", "services", "faqs"}


def test_knowledge_rejects_unknown_section():
    try:
        hotel_knowledge_service.build(
            context=AIRequestContext("1", "manager", "Manager", 1),
            section="unknown",
        )
    except ValueError as exc:
        assert "Unknown hotel knowledge section" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
