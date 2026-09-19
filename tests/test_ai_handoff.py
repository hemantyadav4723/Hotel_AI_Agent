import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.context import AIRequestContext
from ai.handoff import HumanHandoffService
from ai.observability import observability


def ctx(hotel_id=1):
    return AIRequestContext(user_id="u1", username="admin", role="Admin", hotel_id=hotel_id)


def test_detect_emergency_and_human_request():
    service = HumanHandoffService()
    assert service.detect("There is a fire, urgent help needed").priority == "urgent"
    assert service.detect("I want to speak to a human", requested=True).should_handoff


def test_handoff_lifecycle_and_context_update(monkeypatch):
    monkeypatch.setattr("ai.handoff.log_activity", lambda **kwargs: 1)
    service = HumanHandoffService()
    record = service.request(ctx(), "conv-1", "complaint", "high", "manager", {"guest": "A"})
    assert record.status == "requested"
    record = service.assign(ctx(), "conv-1", "staff-2")
    assert record.status == "assigned"
    record = service.takeover(ctx(), "conv-1", "staff-2")
    assert record.status == "in_progress" and record.ai_paused
    record = service.resolve(ctx(), "conv-1", "Issue resolved", {"resolution_code": "R1"})
    assert record.status == "resolved" and not record.ai_paused
    assert record.context["resolution_code"] == "R1"


def test_hotel_scope_isolation(monkeypatch):
    monkeypatch.setattr("ai.handoff.log_activity", lambda **kwargs: 1)
    service = HumanHandoffService()
    service.request(ctx(1), "conv-1", "guest request")
    try:
        service.get(ctx(2), "conv-1")
        assert False, "cross-hotel handoff must be blocked"
    except ValueError as exc:
        assert "hotel scope" in str(exc).lower()


def test_context_validation(monkeypatch):
    monkeypatch.setattr("ai.handoff.log_activity", lambda **kwargs: 1)
    service = HumanHandoffService()
    try:
        service.request(ctx(), "conv-1", "reason", handoff_context={"x": []})
        assert False, "non-scalar context must be rejected"
    except ValueError as exc:
        assert "scalar" in str(exc).lower()


def test_handoff_lifecycle_records_observability(monkeypatch):
    monkeypatch.setattr("ai.handoff.log_activity", lambda **kwargs: 1)
    service = HumanHandoffService()
    c = ctx()
    service.request(c, "obs-1", "guest request")
    service.takeover(c, "obs-1", "staff-1")
    service.resolve(c, "obs-1", "resolved")
    actions = [e["details"]["action"] for e in observability.history(c, "obs-1", event_type="handoff")]
    assert actions == ["resolved", "takeover", "requested"]
