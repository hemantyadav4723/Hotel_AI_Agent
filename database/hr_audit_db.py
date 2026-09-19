import json
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def create_hr_audit_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_audit_log(
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                actor_user_id TEXT,
                actor_username TEXT,
                actor_role TEXT,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hr_audit_hotel_time
            ON hr_audit_log(hotel_id, created_at DESC, audit_id DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hr_audit_target
            ON hr_audit_log(hotel_id, target_type, target_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hr_audit_actor
            ON hr_audit_log(hotel_id, actor_user_id, created_at DESC)
        """)
        connection.commit()
    finally:
        connection.close()


def log_hr_activity(
    connection,
    action,
    target_type,
    target_id=None,
    old_value=None,
    new_value=None,
    reason=None,
):
    """Write one immutable HR activity record using the caller's transaction."""
    hotel_id = get_current_hotel_id()

    from database.user_db import get_current_session
    session = get_current_session() or {}

    actor_user_id = session.get("user_id")
    actor_username = session.get("username")
    actor_role = session.get("role")

    if not actor_user_id:
        actor_user_id = "SYSTEM"
        actor_username = actor_username or "SYSTEM"
        actor_role = actor_role or "SYSTEM"

    action = str(action or "").strip().upper()
    target_type = str(target_type or "").strip()
    if not action:
        raise ValueError("HR audit action is required.")
    if not target_type:
        raise ValueError("HR audit target type is required.")

    created_at = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

    connection.execute("""
        INSERT INTO hr_audit_log(
            hotel_id, actor_user_id, actor_username, actor_role,
            action, target_type, target_id,
            old_value, new_value, reason, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        hotel_id,
        actor_user_id,
        actor_username,
        actor_role,
        action,
        target_type,
        str(target_id) if target_id is not None else None,
        _serialize(old_value),
        _serialize(new_value),
        str(reason).strip() if reason is not None and str(reason).strip() else None,
        created_at,
    ))


def get_hr_audit_history(
    target_type=None,
    target_id=None,
    action=None,
    limit=100,
):
    """Return current-hotel HR audit records with safe filtering."""
    hotel_id = get_current_hotel_id()

    try:
        limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        limit = 100

    connection = get_connection()
    try:
        sql = """
            SELECT audit_id, hotel_id, actor_user_id, actor_username,
                   actor_role, action, target_type, target_id,
                   old_value, new_value, reason, created_at
            FROM hr_audit_log
            WHERE hotel_id = ?
        """
        params = [hotel_id]

        if target_type:
            sql += " AND lower(target_type) = lower(?)"
            params.append(str(target_type).strip())

        if target_id:
            sql += " AND target_id = ?"
            params.append(str(target_id).strip())

        if action:
            sql += " AND lower(action) = lower(?)"
            params.append(str(action).strip())

        sql += " ORDER BY audit_id DESC LIMIT ?"
        params.append(limit)

        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def view_hr_audit_history():
    rows = get_hr_audit_history()

    print("=" * 100)
    print("                         HR AUDIT & ACTIVITY HISTORY")
    print("=" * 100)

    if not rows:
        print("No HR Audit History Found.")
        return

    for row in rows:
        print(f"Audit ID      : {row['audit_id']}")
        print(f"Hotel ID      : {row['hotel_id']}")
        print(f"Who           : {row['actor_user_id']} ({row['actor_username'] or '-'})")
        print(f"Role          : {row['actor_role'] or '-'}")
        print(f"Action        : {row['action']}")
        print(f"Target        : {row['target_type']} / {row['target_id'] or '-'}")
        print(f"Old Value     : {row['old_value'] or '-'}")
        print(f"New Value     : {row['new_value'] or '-'}")
        print(f"Reason        : {row['reason'] or '-'}")
        print(f"When          : {row['created_at']}")
        print("-" * 100)
