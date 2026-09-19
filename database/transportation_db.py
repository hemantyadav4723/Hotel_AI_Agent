from utils.error_logging import log_non_blocking_error
from datetime import datetime
import re
import sqlite3

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.notification_db import record_notification_event


TRANSPORTATION_TYPES = (
    "Airport Pickup",
    "Airport Drop",
    "Railway Station Pickup",
    "Railway Station Drop",
    "Local Transportation",
    "Taxi / Cab Request",
)

TRANSPORTATION_STATUSES = (
    "Requested",
    "Confirmed",
    "Assigned",
    "Driver On The Way",
    "In Transit",
    "Completed",
    "Cancelled",
    "No-Show",
)

VEHICLE_STATUSES = ("Active", "Inactive")
DRIVER_STATUSES = ("Active", "Inactive")
INTEGRATION_STATUSES = ("Not Integrated", "Pending Integration", "Integrated", "Failed")


def _now():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _generate_id(cursor, table, column, prefix, hotel_id):
    date_part = datetime.now().strftime("%Y%m%d")
    cursor.execute(
        f"""
        SELECT {column}
        FROM {table}
        WHERE hotel_id = ? AND {column} LIKE ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (hotel_id, f"{prefix}-{date_part}-%"),
    )
    row = cursor.fetchone()
    sequence = 0
    if row and row[column]:
        match = re.search(r"-(\d+)$", str(row[column]))
        if match:
            sequence = int(match.group(1))
    return f"{prefix}-{date_part}-{sequence + 1:05d}"


def create_transportation_tables():
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transportation_vehicles(
                vehicle_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                vehicle_number TEXT NOT NULL,
                vehicle_type TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 4,
                status TEXT NOT NULL DEFAULT 'Active',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(hotel_id, vehicle_number)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transportation_drivers(
                driver_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                driver_name TEXT NOT NULL,
                driver_mobile TEXT,
                license_number TEXT,
                vehicle_type TEXT,
                status TEXT NOT NULL DEFAULT 'Active',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(hotel_id, license_number)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transportation_requests(
                request_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                customer_id TEXT,
                guest_name TEXT,
                guest_mobile TEXT,
                guest_email TEXT,
                transportation_type TEXT NOT NULL,
                pickup_date TEXT NOT NULL,
                pickup_time TEXT NOT NULL,
                pickup_location TEXT NOT NULL,
                drop_location TEXT NOT NULL,
                vehicle_id TEXT,
                vehicle_type TEXT,
                driver_id TEXT,
                driver_name TEXT,
                fare REAL NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'INR',
                status TEXT NOT NULL DEFAULT 'Requested',
                special_request TEXT,
                notes TEXT,
                provider_name TEXT,
                provider_reference TEXT,
                integration_status TEXT NOT NULL DEFAULT 'Not Integrated',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transport_requests_hotel_date ON transportation_requests(hotel_id, pickup_date, pickup_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transport_requests_hotel_status ON transportation_requests(hotel_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transport_requests_customer ON transportation_requests(hotel_id, customer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transport_vehicles_hotel_status ON transportation_vehicles(hotel_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transport_drivers_hotel_status ON transportation_drivers(hotel_id, status)")

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _resolve_customer(cursor, hotel_id, customer_id):
    if not customer_id:
        return None
    customer_id = str(customer_id).strip().upper()
    row = cursor.execute(
        """
        SELECT c.customer_id, c.customer_name, c.customer_mobile, c.customer_email
        FROM customers c
        WHERE c.customer_id = ?
          AND EXISTS (
              SELECT 1 FROM guest_hotel_relationships ghr
              WHERE ghr.customer_id = c.customer_id AND ghr.hotel_id = ?
          )
        """,
        (customer_id, hotel_id),
    ).fetchone()
    if row is None:
        raise ValueError("Customer not found for current hotel.")
    return row


def _validate_vehicle(cursor, hotel_id, vehicle_id):
    if not vehicle_id:
        return None
    row = cursor.execute(
        "SELECT * FROM transportation_vehicles WHERE vehicle_id = ? AND hotel_id = ? AND status = 'Active'",
        (str(vehicle_id).strip().upper(), hotel_id),
    ).fetchone()
    if row is None:
        raise ValueError("Active vehicle not found for current hotel.")
    return row


def _validate_driver(cursor, hotel_id, driver_id):
    if not driver_id:
        return None
    row = cursor.execute(
        "SELECT * FROM transportation_drivers WHERE driver_id = ? AND hotel_id = ? AND status = 'Active'",
        (str(driver_id).strip().upper(), hotel_id),
    ).fetchone()
    if row is None:
        raise ValueError("Active driver not found for current hotel.")
    return row


def create_transportation_request(
    customer_id,
    guest_name,
    guest_mobile,
    guest_email,
    transportation_type,
    pickup_date,
    pickup_time,
    pickup_location,
    drop_location,
    vehicle_id=None,
    vehicle_type=None,
    driver_id=None,
    fare=0,
    special_request=None,
    notes=None,
):
    hotel_id = get_current_hotel_id()
    if transportation_type not in TRANSPORTATION_TYPES:
        raise ValueError("Invalid transportation type.")
    if not str(pickup_location or "").strip() or not str(drop_location or "").strip():
        raise ValueError("Pickup and drop locations are required.")
    try:
        fare = float(fare or 0)
    except (TypeError, ValueError):
        raise ValueError("Fare must be a valid amount.")
    if fare < 0:
        raise ValueError("Fare cannot be negative.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        customer = _resolve_customer(cursor, hotel_id, customer_id)
        vehicle = _validate_vehicle(cursor, hotel_id, vehicle_id)
        driver = _validate_driver(cursor, hotel_id, driver_id)

        if customer:
            customer_id = customer["customer_id"]
            guest_name = customer["customer_name"]
            guest_mobile = customer["customer_mobile"]
            guest_email = customer["customer_email"]
        else:
            customer_id = None
            guest_name = str(guest_name or "").strip() or None
            guest_mobile = str(guest_mobile or "").strip() or None
            guest_email = str(guest_email or "").strip().lower() or None
            if not guest_name:
                raise ValueError("Guest name is required when Customer ID is blank.")

        if vehicle:
            vehicle_id = vehicle["vehicle_id"]
            vehicle_type = vehicle["vehicle_type"]
        else:
            vehicle_id = None
            vehicle_type = str(vehicle_type or "").strip() or None

        if driver:
            driver_id = driver["driver_id"]
            driver_name = driver["driver_name"]
        else:
            driver_id = None
            driver_name = None

        request_id = _generate_id(
            cursor, "transportation_requests", "request_id", "TRN", hotel_id
        )
        now = _now()
        cursor.execute(
            """
            INSERT INTO transportation_requests(
                request_id, hotel_id, customer_id, guest_name, guest_mobile, guest_email,
                transportation_type, pickup_date, pickup_time, pickup_location, drop_location,
                vehicle_id, vehicle_type, driver_id, driver_name, fare, status,
                special_request, notes, provider_name, provider_reference, integration_status,
                created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Requested', ?, ?, NULL, NULL, 'Not Integrated', ?, ?)
            """,
            (
                request_id, hotel_id, customer_id, guest_name, guest_mobile, guest_email,
                transportation_type, pickup_date, pickup_time, pickup_location, drop_location,
                vehicle_id, vehicle_type, driver_id, driver_name, fare,
                special_request, notes, now, now,
            ),
        )
        connection.commit()

        # Notification foundation: keep transportation events in the
        # existing notification system. External channels are handled by
        # the notification delivery layer; this call only records the event.
        try:
            record_notification_event(
                "Transportation",
                "Transportation Request Created",
                (
                    f"Transportation request {request_id} created for "
                    f"{guest_name or 'Guest'}. "
                    f"Status: Requested. "
                    f"Pickup: {pickup_location}. "
                    f"Drop: {drop_location}."
                ),
                reference_type="TRANSPORTATION_REQUEST",
                reference_id=request_id,
                recipient_type="Guest",
                recipient_id=customer_id,
                recipient_name=guest_name,
                recipient_mobile=guest_mobile,
                recipient_email=guest_email,
                hotel_id=hotel_id,
                idempotency_key=f"TRANSPORTATION-CREATED:{hotel_id}:{request_id}",
            )
        except Exception:
            # Transportation data must remain committed even if the
            # notification foundation has a temporary problem.
            pass

        return request_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_transportation_requests(limit=200):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        limit = max(1, min(int(limit), 500))
        return connection.execute(
            """
            SELECT * FROM transportation_requests
            WHERE hotel_id = ?
            ORDER BY pickup_date DESC, pickup_time DESC, created_at DESC
            LIMIT ?
            """,
            (hotel_id, limit),
        ).fetchall()
    finally:
        connection.close()


def search_transportation_requests(term):
    hotel_id = get_current_hotel_id()
    like = f"%{str(term or '').strip()}%"
    connection = get_connection()
    try:
        return connection.execute(
            """
            SELECT * FROM transportation_requests
            WHERE hotel_id = ?
              AND (
                  lower(request_id) LIKE lower(?) OR
                  lower(COALESCE(customer_id, '')) LIKE lower(?) OR
                  lower(COALESCE(guest_name, '')) LIKE lower(?) OR
                  lower(COALESCE(guest_mobile, '')) LIKE lower(?) OR
                  lower(transportation_type) LIKE lower(?) OR
                  lower(pickup_location) LIKE lower(?) OR
                  lower(drop_location) LIKE lower(?) OR
                  lower(COALESCE(vehicle_id, '')) LIKE lower(?) OR
                  lower(COALESCE(driver_name, '')) LIKE lower(?) OR
                  lower(status) LIKE lower(?) OR
                  lower(COALESCE(provider_reference, '')) LIKE lower(?)
              )
            ORDER BY created_at DESC
            LIMIT 200
            """,
            (hotel_id, like, like, like, like, like, like, like, like, like, like, like),
        ).fetchall()
    finally:
        connection.close()


def update_transportation_request(request_id, status, vehicle_id=None, driver_id=None,
                                  fare=None, provider_name=None, provider_reference=None,
                                  integration_status=None, special_request=None, notes=None):
    hotel_id = get_current_hotel_id()
    status = str(status or "").strip()
    if status not in TRANSPORTATION_STATUSES:
        raise ValueError("Invalid transportation status.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        row = cursor.execute(
            "SELECT * FROM transportation_requests WHERE request_id = ? AND hotel_id = ?",
            (str(request_id).strip().upper(), hotel_id),
        ).fetchone()
        if row is None:
            raise ValueError("Transportation request not found.")

        vehicle = _validate_vehicle(cursor, hotel_id, vehicle_id) if vehicle_id else None
        driver = _validate_driver(cursor, hotel_id, driver_id) if driver_id else None

        values = {
            "status": status,
            "vehicle_id": vehicle["vehicle_id"] if vehicle else row["vehicle_id"],
            "vehicle_type": vehicle["vehicle_type"] if vehicle else row["vehicle_type"],
            "driver_id": driver["driver_id"] if driver else row["driver_id"],
            "driver_name": driver["driver_name"] if driver else row["driver_name"],
            "fare": row["fare"] if fare is None else float(fare),
            "provider_name": row["provider_name"] if provider_name is None else (str(provider_name).strip() or None),
            "provider_reference": row["provider_reference"] if provider_reference is None else (str(provider_reference).strip() or None),
            "integration_status": row["integration_status"] if integration_status is None else str(integration_status).strip(),
            "special_request": row["special_request"] if special_request is None else (str(special_request).strip() or None),
            "notes": row["notes"] if notes is None else (str(notes).strip() or None),
            "updated_at": _now(),
        }
        if values["fare"] < 0:
            raise ValueError("Fare cannot be negative.")
        if values["integration_status"] not in INTEGRATION_STATUSES:
            raise ValueError("Invalid integration status.")

        cursor.execute(
            """
            UPDATE transportation_requests
            SET status=?, vehicle_id=?, vehicle_type=?, driver_id=?, driver_name=?,
                fare=?, provider_name=?, provider_reference=?, integration_status=?,
                special_request=?, notes=?, updated_at=?
            WHERE request_id=? AND hotel_id=?
            """,
            (
                values["status"], values["vehicle_id"], values["vehicle_type"],
                values["driver_id"], values["driver_name"], values["fare"],
                values["provider_name"], values["provider_reference"],
                values["integration_status"], values["special_request"],
                values["notes"], values["updated_at"], str(request_id).strip().upper(), hotel_id,
            ),
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Transportation",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_transportation_request completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        # Record a notification only when the request's operational status
        # actually changes. This avoids duplicate notifications when staff
        # saves the same status again.
        if values["status"] != row["status"]:
            try:
                record_notification_event(
                    "Transportation",
                    "Transportation Status Updated",
                    (
                        f"Transportation request {row['request_id']} status "
                        f"changed from {row['status']} to {values['status']}. "
                        f"Driver: {values['driver_name'] or 'Not Assigned'}. "
                        f"Vehicle: {values['vehicle_id'] or 'Not Assigned'}."
                    ),
                    reference_type="TRANSPORTATION_REQUEST",
                    reference_id=row["request_id"],
                    recipient_type="Guest",
                    recipient_id=row["customer_id"],
                    recipient_name=row["guest_name"],
                    recipient_mobile=row["guest_mobile"],
                    recipient_email=row["guest_email"],
                    hotel_id=hotel_id,
                    idempotency_key=(
                        f"TRANSPORTATION-STATUS:{hotel_id}:"
                        f"{row['request_id']}:{values['status']}"
                    ),
                )
            except Exception:
                # Status update must not fail because a notification could
                # not be recorded. The notification layer is non-blocking.
                pass
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def add_vehicle(vehicle_number, vehicle_type, capacity=4, notes=None):
    hotel_id = get_current_hotel_id()
    vehicle_number = str(vehicle_number or "").strip().upper()
    vehicle_type = str(vehicle_type or "").strip()
    if not vehicle_number or not vehicle_type:
        raise ValueError("Vehicle number and vehicle type are required.")
    try:
        capacity = int(capacity)
    except (TypeError, ValueError):
        raise ValueError("Vehicle capacity must be a whole number.")
    if capacity <= 0:
        raise ValueError("Vehicle capacity must be greater than zero.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        vehicle_id = _generate_id(cursor, "transportation_vehicles", "vehicle_id", "VEH", hotel_id)
        now = _now()
        cursor.execute(
            """
            INSERT INTO transportation_vehicles(
                vehicle_id, hotel_id, vehicle_number, vehicle_type, capacity,
                status, notes, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, 'Active', ?, ?, ?)
            """,
            (vehicle_id, hotel_id, vehicle_number, vehicle_type, capacity, notes, now, now),
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Transportation",
        action="CREATE",
        local_values=locals(),
        details="Business operation add_vehicle completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return vehicle_id
    except sqlite3.IntegrityError:
        connection.rollback()
        raise ValueError("Vehicle number already exists for current hotel.")
    finally:
        connection.close()


def get_vehicles(include_inactive=True):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        condition = "" if include_inactive else " AND status='Active'"
        return connection.execute(
            f"SELECT * FROM transportation_vehicles WHERE hotel_id=?{condition} ORDER BY vehicle_number",
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()


def update_vehicle_status(vehicle_id, status):
    hotel_id = get_current_hotel_id()
    if status not in VEHICLE_STATUSES:
        raise ValueError("Invalid vehicle status.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        if cursor.execute(
            "SELECT 1 FROM transportation_vehicles WHERE vehicle_id=? AND hotel_id=?",
            (str(vehicle_id).strip().upper(), hotel_id),
        ).fetchone() is None:
            raise ValueError("Vehicle not found.")
        cursor.execute(
            "UPDATE transportation_vehicles SET status=?, updated_at=? WHERE vehicle_id=? AND hotel_id=?",
            (status, _now(), str(vehicle_id).strip().upper(), hotel_id),
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Transportation",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation update_vehicle_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def add_driver(driver_name, driver_mobile=None, license_number=None, vehicle_type=None, notes=None):
    hotel_id = get_current_hotel_id()
    driver_name = str(driver_name or "").strip()
    if not driver_name:
        raise ValueError("Driver name is required.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        driver_id = _generate_id(cursor, "transportation_drivers", "driver_id", "DRV", hotel_id)
        now = _now()
        cursor.execute(
            """
            INSERT INTO transportation_drivers(
                driver_id, hotel_id, driver_name, driver_mobile, license_number,
                vehicle_type, status, notes, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, 'Active', ?, ?, ?)
            """,
            (driver_id, hotel_id, driver_name,
             str(driver_mobile or '').strip() or None,
             str(license_number or '').strip().upper() or None,
             str(vehicle_type or '').strip() or None,
             str(notes or '').strip() or None, now, now),
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Transportation",
        action="CREATE",
        local_values=locals(),
        details="Business operation add_driver completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return driver_id
    except sqlite3.IntegrityError:
        connection.rollback()
        raise ValueError("Driver license number already exists for current hotel.")
    finally:
        connection.close()


def get_drivers(include_inactive=True):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        condition = "" if include_inactive else " AND status='Active'"
        return connection.execute(
            f"SELECT * FROM transportation_drivers WHERE hotel_id=?{condition} ORDER BY driver_name",
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()


def update_driver_status(driver_id, status):
    hotel_id = get_current_hotel_id()
    if status not in DRIVER_STATUSES:
        raise ValueError("Invalid driver status.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        if cursor.execute(
            "SELECT 1 FROM transportation_drivers WHERE driver_id=? AND hotel_id=?",
            (str(driver_id).strip().upper(), hotel_id),
        ).fetchone() is None:
            raise ValueError("Driver not found.")
        cursor.execute(
            "UPDATE transportation_drivers SET status=?, updated_at=? WHERE driver_id=? AND hotel_id=?",
            (status, _now(), str(driver_id).strip().upper(), hotel_id),
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Transportation",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation update_driver_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
