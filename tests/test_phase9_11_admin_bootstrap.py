from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_admin_bootstrap_is_opt_in_and_requires_credentials(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "true")
    monkeypatch.delenv("BOOTSTRAP_ADMIN_USER_ID", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    from database.user_db import bootstrap_admin_from_environment

    try:
        bootstrap_admin_from_environment()
    except ValueError as exc:
        assert "BOOTSTRAP_ADMIN_USER_ID" in str(exc)
    else:
        raise AssertionError("Missing bootstrap credentials must fail closed")


def test_admin_bootstrap_disabled_is_noop(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "false")

    from database.user_db import bootstrap_admin_from_environment

    assert bootstrap_admin_from_environment() is False


def test_admin_bootstrap_creates_only_when_hotel_has_no_users(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "true")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USER_ID", "USR-ADMIN-001")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Strong-Test-Password-123!")

    import database.user_db as user_db

    class FakeConnection:
        def __init__(self, row):
            self.row = row

        def execute(self, query, params):
            class Result:
                def __init__(self, row):
                    self.row = row

                def fetchone(self):
                    return self.row

            return Result(self.row)

        def close(self):
            pass

    monkeypatch.setattr(user_db, "get_current_hotel_id", lambda: 1)
    monkeypatch.setattr(user_db, "get_connection", lambda: FakeConnection(None))

    calls = []
    monkeypatch.setattr(user_db, "save_user", lambda **kwargs: calls.append(kwargs))

    assert user_db.bootstrap_admin_from_environment() is True
    assert calls == [{
        "user_id": "USR-ADMIN-001",
        "username": "admin",
        "password": "Strong-Test-Password-123!",
        "role": "Admin",
        "staff_id": None,
        "reason": "One-time deployment admin bootstrap.",
    }]


def test_admin_bootstrap_does_not_replace_existing_user(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_ENABLED", "true")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USER_ID", "USR-ADMIN-001")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Strong-Test-Password-123!")

    import database.user_db as user_db

    class FakeConnection:
        def execute(self, query, params):
            class Result:
                def fetchone(self):
                    return {"exists": 1}

            return Result()

        def close(self):
            pass

    monkeypatch.setattr(user_db, "get_current_hotel_id", lambda: 1)
    monkeypatch.setattr(user_db, "get_connection", lambda: FakeConnection())
    monkeypatch.setattr(user_db, "save_user", lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not create a second admin")))

    assert user_db.bootstrap_admin_from_environment() is False
