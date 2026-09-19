from types import SimpleNamespace

import pytest

from ai.memory import AIMemoryService


def ctx(hotel_id=1):
    return SimpleNamespace(user_id=1, username="u", role="Manager", hotel_id=hotel_id, public_dict=lambda: {"user_id": "1", "username": "u", "role": "Manager", "hotel_id": hotel_id})


def test_short_term_memory_is_hotel_scoped():
    service = AIMemoryService(ttl_minutes=30)
    service.remember(ctx(1), "c1", "user", "hello")
    assert len(service.get_short_term(ctx(1), "c1")) == 1
    assert service.get_short_term(ctx(2), "c1") == []


def test_memory_is_bounded():
    service = AIMemoryService()
    for i in range(30):
        service.remember(ctx(), "c1", "user", str(i))
    entries = service.get_short_term(ctx(), "c1")
    assert len(entries) == 20
    assert entries[0]["content"] == "10"


def test_expiration_removes_old_entries(monkeypatch):
    service = AIMemoryService(ttl_minutes=1)
    service.remember(ctx(), "c1", "user", "hello")
    key = (1, "c1")
    entry = service._store[key][0]
    from datetime import datetime, timedelta, timezone
    service._store[key][0] = type(entry)(entry.role, entry.content, entry.created_at, (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat())
    assert service.get_short_term(ctx(), "c1") == []


def test_clear_memory():
    service = AIMemoryService()
    service.remember(ctx(), "c1", "user", "hello")
    service.clear(ctx(), "c1")
    assert service.get_short_term(ctx(), "c1") == []


def test_requires_conversation_id():
    with pytest.raises(ValueError, match="Conversation ID"):
        AIMemoryService().get_short_term(ctx(), "")
