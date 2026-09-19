from utils.error_logging import log_non_blocking_error
"""Guest service request persistence for Phase 8.5.

This module is the canonical hotel-scoped business/DB layer for guest service
requests. AI code calls these controlled functions; it never executes SQL.
"""

from datetime import datetime
import re

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


SERVICE_TYPES = (
    "Housekeeping",
    "Room Service",
    "Maintenance",
    "Laundry",
    "Bell/Luggage",
    "Transportation",
    "Restaurant",
    "General",
)

REQUEST_PRIORITIES = ("Low", "Normal", "High", "Urgent")
REQUEST_STATUSES = (
    "Requested",
    "Acknowledged",
    "In Progress",
    "Completed",
    "Cancelled",
    "Escalated",
)
FOLLOW_UP_STATUSES = ("Pending", "Completed", "Not Required")


def _now():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _normalize(value):
    return " ".join(str(value or "").strip().split())


def _generate_request_id(cursor, hotel_id):
    date_part = datetime.now().strftime("%Y%m%d")
    cursor.execute(
        """
        SELECT request_id FROM guest_service_requests
        WHERE hotel_id = ? AND request_id LIKE ?
        ORDER BY rowid DESC LIMIT 1
        """,
        (hotel_id, f"GSR-{date_part}-%"),
    )
    row = cursor.fetchone()
    sequence = 0
    if row and row["request_id"]:
        match = re.search(r"-(\d+)$", str(row["request_id"]))
        if match:
            sequence = int(match.group(1))
    return f"GSR-{date_part}-{sequence + 1:05d}"


def create_guest_service_requests_table(connection=None):
    owns_connection = connection is None
    if owns_connection:
        connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS guest_service_requests(
                request_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                customer_id TEXT,
                guest_name TEXT,
                room_number TEXT,
                service_type TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Normal',
                request_status TEXT NOT NULL DEFAULT 'Requested',
                assigned_department TEXT,
                assigned_staff_id TEXT,
                follow_up_status TEXT NOT NULL DEFAULT 'Not Required',
                follow_up_at TEXT,
                follow_up_notes TEXT,
                escalated INTEGER NOT NULL DEFAULT 0,
                escalation_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                CHECK(service_type IN ('Housekeeping','Room Service','Maintenance','Laundry','Bell/Luggage','Transportation','Restaurant','General')),
                CHECK(priority IN ('Low','Normal','High','Urgent')),
                CHECK(request_status IN ('Requested','Acknowledged','In Progress','Completed','Cancelled','Escalated')),
                CHECK(follow_up_status IN ('Pending','Completed','Not Required')),
                CHECK(escalated IN (0,1))
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_guest_service_hotel_status ON guest_service_requests(hotel_id, request_status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_guest_service_hotel_guest ON guest_service_requests(hotel_id, customer_id, room_number)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_guest_service_follow_up ON guest_service_requests(hotel_id, follow_up_status, follow_up_at)"
        )
        if owns_connection:
            connection.commit()
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def _validate_service_type(service_type):
    value = _normalize(service_type)
    if value.lower() == "bell/luggage".lower():
        return "Bell/Luggage"
    for item in SERVICE_TYPES:
        if value.lower() == item.lower():
            return item
    raise ValueError(f"Invalid service type. Supported: {', '.join(SERVICE_TYPES)}")


def _validate_priority(priority):
    value = _normalize(priority or "Normal").title()
    if value not in REQUEST_PRIORITIES:
        raise ValueError("Invalid request priority.")
    return value


def _validate_status(status):
    value = _normalize(status)
    for item in REQUEST_STATUSES:
        if value.lower() == item.lower():
            return item
    raise ValueError("Invalid guest service request status.")


def _validate_follow_up_status(status):
    value = _normalize(status)
    for item in FOLLOW_UP_STATUSES:
        if value.lower() == item.lower():
            return item
    raise ValueError("Invalid follow-up status.")


def _validate_guest_reference(cursor, hotel_id, customer_id=None, room_number=None):
    customer_id = _normalize(customer_id).upper() or None
    room_number = _normalize(room_number).upper() or None

    if customer_id:
        row = cursor.execute(
            """
            SELECT 1 FROM guest_hotel_relationships
            WHERE customer_id = ? AND hotel_id = ? AND is_active = 1
            LIMIT 1
            """,
            (customer_id, hotel_id),
        ).fetchone()
        if row is None:
            raise ValueError("Customer is not linked to the current hotel.")

    if room_number:
        row = cursor.execute(
            """
            SELECT 1 FROM rooms
            WHERE hotel_id = ? AND room_number = ? AND is_active = 1
            LIMIT 1
            """,
            (hotel_id, room_number),
        ).fetchone()
        if row is None:
            raise ValueError("Room is not available in the current hotel scope.")

    return customer_id, room_number


def create_guest_service_request(
    service_type,
    description,
    customer_id=None,
    guest_name=None,
    room_number=None,
    priority="Normal",
    hotel_id=None,
):
    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    service_type = _validate_service_type(service_type)
    description = _normalize(description)
    guest_name = _normalize(guest_name) or None
    priority = _validate_priority(priority)
    if not description:
        raise ValueError("Guest service request description is required.")
    if not any((customer_id, guest_name, room_number)):
        raise ValueError("Guest name, customer ID, or room number is required.")

    connection = get_connection()
    try:
        create_guest_service_requests_table(connection)
        cursor = connection.cursor()
        customer_id, room_number = _validate_guest_reference(
            cursor, hotel_id, customer_id, room_number
        )
        request_id = _generate_request_id(cursor, hotel_id)
        now = _now()
        cursor.execute(
            """
            INSERT INTO guest_service_requests(
                request_id, hotel_id, customer_id, guest_name, room_number,
                service_type, description, priority, request_status,
                created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'Requested', ?, ?)
            """,
            (
                request_id, hotel_id, customer_id, guest_name, room_number,
                service_type, description, priority, now, now,
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    try:
        from database.audit_db import log_business_activity
        log_business_activity(
            module="Guest Service",
            action="CREATE",
            local_values={"request_id": request_id},
            details=f"Guest service request {request_id} created for {service_type}.",
        )
    except Exception as exc:
        log_non_blocking_error("Non-blocking optional operation failed", exc)
    return request_id


def get_guest_service_request(request_id, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    request_id = _normalize(request_id).upper()
    if not request_id:
        raise ValueError("Request ID is required.")
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT * FROM guest_service_requests WHERE request_id = ? AND hotel_id = ?",
            (request_id, hotel_id),
        ).fetchone()
    finally:
        connection.close()


def list_guest_service_requests(
    hotel_id=None, status=None, service_type=None, customer_id=None, room_number=None, limit=100
):
    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    connection = get_connection()
    try:
        sql = "SELECT * FROM guest_service_requests WHERE hotel_id = ?"
        params = [hotel_id]
        if status:
            sql += " AND request_status = ?"
            params.append(_validate_status(status))
        if service_type:
            sql += " AND service_type = ?"
            params.append(_validate_service_type(service_type))
        if customer_id:
            sql += " AND customer_id = ?"
            params.append(_normalize(customer_id).upper())
        if room_number:
            sql += " AND room_number = ?"
            params.append(_normalize(room_number).upper())
        sql += " ORDER BY created_at DESC, request_id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def update_guest_service_request_status(request_id, status, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    request_id = _normalize(request_id).upper()
    status = _validate_status(status)
    connection = get_connection()
    try:
        cursor = connection.cursor()
        row = cursor.execute(
            "SELECT request_status FROM guest_service_requests WHERE request_id = ? AND hotel_id = ?",
            (request_id, hotel_id),
        ).fetchone()
        if row is None:
            raise ValueError("Guest service request not found.")
        now = _now()
        completed_at = now if status == "Completed" else None
        cursor.execute(
            """
            UPDATE guest_service_requests
            SET request_status = ?, updated_at = ?, completed_at = COALESCE(?, completed_at)
            WHERE request_id = ? AND hotel_id = ?
            """,
            (status, now, completed_at, request_id, hotel_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    try:
        from database.audit_db import log_business_activity
        log_business_activity(
            module="Guest Service",
            action="UPDATE",
            local_values={"request_id": request_id},
            details=f"Guest service request status changed to {status}.",
        )
    except Exception as exc:
        log_non_blocking_error("Non-blocking optional operation failed", exc)
    return True


def add_guest_service_follow_up(request_id, follow_up_at=None, notes=None, status="Pending", hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    request_id = _normalize(request_id).upper()
    status = _validate_follow_up_status(status)
    notes = _normalize(notes) or None
    if status == "Completed" and not notes:
        raise ValueError("Follow-up notes are required when follow-up is completed.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        row = cursor.execute(
            "SELECT 1 FROM guest_service_requests WHERE request_id = ? AND hotel_id = ?",
            (request_id, hotel_id),
        ).fetchone()
        if row is None:
            raise ValueError("Guest service request not found.")
        now = _now()
        cursor.execute(
            """
            UPDATE guest_service_requests
            SET follow_up_status = ?, follow_up_at = ?, follow_up_notes = ?, updated_at = ?
            WHERE request_id = ? AND hotel_id = ?
            """,
            (status, _normalize(follow_up_at) or None, notes, now, request_id, hotel_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return True


def escalate_guest_service_request(request_id, reason, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    request_id = _normalize(request_id).upper()
    reason = _normalize(reason)
    if not reason:
        raise ValueError("Escalation reason is required.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        row = cursor.execute(
            "SELECT 1 FROM guest_service_requests WHERE request_id = ? AND hotel_id = ?",
            (request_id, hotel_id),
        ).fetchone()
        if row is None:
            raise ValueError("Guest service request not found.")
        now = _now()
        cursor.execute(
            """
            UPDATE guest_service_requests
            SET escalated = 1, escalation_reason = ?, request_status = 'Escalated', updated_at = ?
            WHERE request_id = ? AND hotel_id = ?
            """,
            (reason, now, request_id, hotel_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return True
