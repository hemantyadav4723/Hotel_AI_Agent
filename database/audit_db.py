from utils.error_logging import log_non_blocking_error
from datetime import datetime
from contextvars import ContextVar

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


AUDIT_ACTIONS = (
    "LOGIN",
    "LOGOUT",
    "CREATE",
    "UPDATE",
    "DELETE",
    "SEARCH",
    "VIEW",
    "STATUS_CHANGE",
    "APPROVE",
    "CANCEL",
    "PAYMENT",
    "OTHER",
)

AUDIT_STATUSES = ("SUCCESS", "FAILED", "INFO")

_request_id_context: ContextVar[str | None] = ContextVar("audit_request_id", default=None)

def set_request_id(request_id):
    return _request_id_context.set(str(request_id) if request_id else None)

def reset_request_id(token):
    _request_id_context.reset(token)

def get_request_id():
    return _request_id_context.get()


def create_audit_log_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_activity_log(
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                actor_user_id TEXT,
                actor_username TEXT,
                actor_role TEXT,
                module TEXT NOT NULL,
                action TEXT NOT NULL,
                record_type TEXT,
                record_id TEXT,
                status TEXT NOT NULL DEFAULT 'INFO',
                details TEXT,
                request_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_hotel_time "
            "ON audit_activity_log(hotel_id, created_at DESC, audit_id DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_actor "
            "ON audit_activity_log(hotel_id, actor_user_id, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_module_action "
            "ON audit_activity_log(hotel_id, module, action, created_at DESC)"
        )
        # Backward-compatible schema migration: request_id is declared in the
        # CREATE TABLE definition for new databases, but older databases may
        # still need the column added. Never attempt the ALTER when it already
        # exists, otherwise every startup logs a duplicate-column error.
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(audit_activity_log)").fetchall()}
        if "request_id" not in columns:
            try:
                cursor.execute("ALTER TABLE audit_activity_log ADD COLUMN request_id TEXT")
            except Exception as exc:
                log_non_blocking_error("Non-blocking audit schema migration failed", exc)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_request "
            "ON audit_activity_log(hotel_id, request_id, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_record "
            "ON audit_activity_log(hotel_id, record_type, record_id)"
        )
        connection.commit()
    finally:
        connection.close()


def log_activity(
    module,
    action,
    record_type=None,
    record_id=None,
    status="INFO",
    details=None,
    actor_user_id=None,
    actor_username=None,
    actor_role=None,
    hotel_id=None,
):
    if not str(module or "").strip():
        raise ValueError("Audit module is required.")
    action = str(action or "").strip().upper()
    if not action:
        raise ValueError("Audit action is required.")
    status = str(status or "INFO").strip().upper()
    if status not in AUDIT_STATUSES:
        raise ValueError("Invalid audit status.")

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT INTO audit_activity_log(
                hotel_id, actor_user_id, actor_username, actor_role,
                module, action, record_type, record_id,
                status, details, request_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hotel_id,
                actor_user_id,
                actor_username,
                actor_role,
                str(module).strip(),
                action,
                record_type,
                record_id,
                status,
                details,
                get_request_id(),
                created_at,
            ),
        )
        audit_id = cursor.lastrowid
        connection.commit()
        return audit_id
    finally:
        connection.close()


def get_audit_logs(
    hotel_id=None,
    actor_username=None,
    module=None,
    action=None,
    record_id=None,
    status=None,
    search=None,
    request_id=None,
    date_from=None,
    date_to=None,
    limit=100,
):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    try:
        limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        limit = 100

    query = """
        SELECT audit_id, hotel_id, actor_user_id, actor_username, actor_role,
               module, action, record_type, record_id, status, details, request_id, created_at
        FROM audit_activity_log
        WHERE hotel_id = ?
    """
    params = [hotel_id]

    if search is not None and str(search).strip():
        term = f"%{str(search).strip().lower()}%"
        query += " AND (LOWER(COALESCE(actor_username,'')) LIKE ? OR LOWER(COALESCE(module,'')) LIKE ? OR LOWER(COALESCE(action,'')) LIKE ? OR LOWER(COALESCE(record_type,'')) LIKE ? OR LOWER(COALESCE(record_id,'')) LIKE ? OR LOWER(COALESCE(details,'')) LIKE ? OR LOWER(COALESCE(request_id,'')) LIKE ?)"
        params.extend([term] * 7)

    filters = (
        ("actor_username", actor_username),
        ("module", module),
        ("action", action),
        ("record_id", record_id),
        ("status", status),
        ("request_id", request_id),
    )
    for column, value in filters:
        if value is not None and str(value).strip():
            query += f" AND LOWER({column}) = LOWER(?)"
            params.append(str(value).strip())

    if date_from and str(date_from).strip():
        query += " AND substr(created_at, 1, 10) >= ?"
        params.append(str(date_from).strip())
    if date_to and str(date_to).strip():
        query += " AND substr(created_at, 1, 10) <= ?"
        params.append(str(date_to).strip())

    query += " ORDER BY audit_id DESC LIMIT ?"
    params.append(limit)

    connection = get_connection()
    try:
        return connection.execute(query, params).fetchall()
    finally:
        connection.close()


def get_record_audit(record_id, record_type=None, hotel_id=None, limit=100):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    query = """
        SELECT audit_id, hotel_id, actor_user_id, actor_username, actor_role,
               module, action, record_type, record_id, status, details, request_id, created_at
        FROM audit_activity_log
        WHERE hotel_id = ? AND record_id = ?
    """
    params = [hotel_id, str(record_id)]
    if record_type and str(record_type).strip():
        query += " AND LOWER(record_type) = LOWER(?)"
        params.append(str(record_type).strip())
    query += " ORDER BY audit_id ASC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))

    connection = get_connection()
    try:
        return connection.execute(query, params).fetchall()
    finally:
        connection.close()



def _get_current_actor():
    """Resolve the current logged-in actor without creating an import cycle."""
    try:
        from database.user_db import get_current_session
        session = get_current_session() or {}
        return (
            session.get("user_id"),
            session.get("username"),
            session.get("role"),
            session.get("hotel_id"),
        )
    except Exception:
        return None, None, None, None


def _infer_record_id(values):
    """Find a useful business record identifier from a function's local variables."""
    preferred = (
        "record_id", "booking_id", "reservation_id", "order_id", "customer_id",
        "staff_id", "user_id", "supplier_id", "purchase_order_id", "po_id",
        "receiving_id", "expense_id", "feedback_id", "transportation_id",
        "request_id", "vehicle_id", "driver_id", "media_id", "route_id",
        "place_id", "room_id", "room_number", "table_id", "table_booking_id",
        "department_id", "designation_id", "attendance_id", "leave_id",
        "payroll_id", "salary_id", "role_id", "permission_id", "item_id",
        "category_id", "unit_id", "menu_item_id", "invoice_number",
    )
    for key in preferred:
        value = values.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def log_business_activity(module, action, local_values=None, details=None, status="SUCCESS"):
    """
    Central helper for business-module audit logging.

    It is intentionally non-blocking: an audit failure must never roll back
    or break an already-committed hotel business transaction.
    """
    values = local_values or {}
    actor_user_id, actor_username, actor_role, session_hotel_id = _get_current_actor()
    hotel_id = session_hotel_id
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    record_id = _infer_record_id(values)
    try:
        return log_activity(
            module=module,
            action=action,
            record_type=str(module).strip(),
            record_id=record_id,
            status=status,
            details=details,
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            actor_role=actor_role,
            hotel_id=hotel_id,
        )
    except Exception:
        return None

def _print_rows(rows, title="AUDIT & ACTIVITY HISTORY"):
    print("=" * 72)
    print(title)
    print("=" * 72)
    if not rows:
        print("No audit/activity records found.")
        print("=" * 72)
        return
    for row in rows:
        print("-" * 72)
        print(f"Audit ID      : {row['audit_id']}")
        print(f"Hotel ID      : {row['hotel_id']}")
        print(f"User ID       : {row['actor_user_id'] or '-'}")
        print(f"Username      : {row['actor_username'] or '-'}")
        print(f"Role          : {row['actor_role'] or '-'}")
        print(f"Module        : {row['module']}")
        print(f"Action        : {row['action']}")
        print(f"Record Type   : {row['record_type'] or '-'}")
        print(f"Record ID     : {row['record_id'] or '-'}")
        print(f"Status        : {row['status']}")
        print(f"Details       : {row['details'] or '-'}")
        print(f"Created       : {row['created_at']}")
    print("=" * 72)


def view_audit_history():
    _print_rows(get_audit_logs(limit=100))


def search_audit_history():
    print("=" * 72)
    print("SEARCH / FILTER AUDIT ACTIVITY")
    print("=" * 72)
    actor = input("Username (optional) : ").strip()
    module = input("Module (optional) : ").strip()
    action = input("Action (optional) : ").strip()
    record_id = input("Record ID (optional) : ").strip()
    status = input("Status (optional) : ").strip()
    date_from = input("Date From YYYY-MM-DD (optional) : ").strip()
    date_to = input("Date To YYYY-MM-DD (optional) : ").strip()

    rows = get_audit_logs(
        actor_username=actor,
        module=module,
        action=action,
        record_id=record_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=100,
    )
    _print_rows(rows, "AUDIT SEARCH RESULTS")


def view_record_audit():
    record_id = input("Record ID : ").strip()
    if not record_id:
        print("Record ID is required.")
        return
    record_type = input("Record Type (optional) : ").strip()
    rows = get_record_audit(record_id, record_type=record_type or None)
    _print_rows(rows, "RECORD ACTIVITY HISTORY")


def audit_activity_management():
    while True:
        print("=" * 72)
        print("                 AUDIT & ACTIVITY SYSTEM")
        print("=" * 72)
        print("1. View Activity History")
        print("2. Search / Filter Audit Logs")
        print("3. Record Activity History")
        print("4. Back")
        print("-" * 72)
        choice = input("Enter Choice : ").strip()
        if choice == "1":
            view_audit_history()
        elif choice == "2":
            search_audit_history()
        elif choice == "3":
            view_record_audit()
        elif choice == "4":
            break
        else:
            print("Invalid Choice.")
        input("\nPress Enter To Continue...")
