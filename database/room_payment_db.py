from utils.error_logging import log_non_blocking_error
from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from datetime import datetime

PAYMENT_METHODS = ("Cash", "UPI", "Card", "Other")
PAYMENT_STATUSES = ("Pending", "Partially Paid", "Paid")
CHARGE_STATUSES = ("Pending", "Partially Paid", "Paid")


def create_room_payment_tables():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS room_reservation_advance_rules(
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                room_number TEXT NOT NULL,
                minimum_advance REAL NOT NULL CHECK(minimum_advance > 0),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(hotel_id, room_number)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS room_payment_transactions(
                transaction_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                booking_id TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                payment_method TEXT,
                amount REAL NOT NULL CHECK(amount > 0),
                extra_charge_id TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(booking_id) REFERENCES room_bookings(booking_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS room_extra_charges(
                charge_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                booking_id TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                paid_amount REAL NOT NULL DEFAULT 0,
                balance_amount REAL NOT NULL DEFAULT 0,
                payment_status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(booking_id) REFERENCES room_bookings(booking_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_room_payment_booking ON room_payment_transactions(hotel_id, booking_id, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_room_charges_booking ON room_extra_charges(hotel_id, booking_id, created_at)")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def seed_room_reservation_advance_rules():
    """Create an editable default minimum advance equal to 10% of one-night room rate."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        cursor.execute("SELECT room_number, room_price FROM rooms WHERE hotel_id=? AND is_active=1", (hotel_id,))
        rows = cursor.fetchall()
        for row in rows:
            minimum = round(max(float(row["room_price"] or 0) * 0.10, 0.01), 2)
            cursor.execute("""
                INSERT OR IGNORE INTO room_reservation_advance_rules(
                    hotel_id, room_number, minimum_advance
                ) VALUES(?, ?, ?)
            """, (hotel_id, row["room_number"], minimum))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _validate_payment_method(payment_method):
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("Invalid payment method.")


def _new_transaction_id(prefix="RPT"):
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def _new_charge_id():
    return f"RC{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def get_room_advance_rules(include_inactive=True):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        query = "SELECT * FROM room_reservation_advance_rules WHERE hotel_id=?"
        params = [hotel_id]
        if not include_inactive:
            query += " AND is_active=1"
        query += " ORDER BY room_number"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def get_required_reservation_advance(room_number, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else hotel_id
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT minimum_advance
            FROM room_reservation_advance_rules
            WHERE hotel_id=? AND room_number=? AND is_active=1
        """, (hotel_id, room_number))
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Reservation advance is not configured for Room {room_number}.")
        return float(row["minimum_advance"])
    finally:
        connection.close()


def set_room_reservation_advance(room_number, minimum_advance, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else hotel_id
    amount = round(float(minimum_advance), 2)
    if amount <= 0:
        raise ValueError("Minimum reservation advance must be greater than ₹0.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM rooms WHERE hotel_id=? AND room_number=? AND is_active=1", (hotel_id, room_number))
        room_row = cursor.fetchone()
        if room_row is None:
            raise ValueError("Room not found or inactive.")
        cursor.execute("SELECT room_price FROM rooms WHERE hotel_id=? AND room_number=?", (hotel_id, room_number))
        room_price = float(cursor.fetchone()["room_price"] or 0)
        if amount > room_price:
            raise ValueError("Minimum reservation advance cannot exceed the room's one-night rate.")
        cursor.execute("""
            INSERT INTO room_reservation_advance_rules(hotel_id, room_number, minimum_advance)
            VALUES(?, ?, ?)
            ON CONFLICT(hotel_id, room_number) DO UPDATE SET
                minimum_advance=excluded.minimum_advance,
                is_active=1,
                updated_at=CURRENT_TIMESTAMP
        """, (hotel_id, room_number, amount))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Payment",
        action="UPDATE",
        local_values=locals(),
        details="Business operation set_room_reservation_advance completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def set_room_reservation_advance_status(room_number, active, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else hotel_id
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE room_reservation_advance_rules SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE hotel_id=? AND room_number=?", (1 if active else 0, hotel_id, room_number))
        if cursor.rowcount != 1:
            raise ValueError("Reservation advance rule not found.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Payment",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation set_room_reservation_advance_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()


def get_required_reservation_advance_for_rooms(room_numbers, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else hotel_id
    return round(sum(get_required_reservation_advance(room, hotel_id) for room in room_numbers), 2)


def record_room_payment(booking_id, amount, payment_method, transaction_type="ROOM_PAYMENT", notes=None, extra_charge_id=None, hotel_id=None, connection=None, apply_to_booking=True):
    hotel_id = get_current_hotel_id() if hotel_id is None else hotel_id
    amount = round(float(amount), 2)
    if amount <= 0:
        raise ValueError("Payment amount must be greater than ₹0.")
    _validate_payment_method(payment_method)
    owns_connection = connection is None
    if owns_connection:
        connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT grand_total, advance_amount, paid_amount, balance_amount, booking_status FROM room_bookings WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        booking = cursor.fetchone()
        if booking is None:
            raise ValueError("Booking not found.")
        if booking["booking_status"] in ("Cancelled", "No-Show"):
            raise ValueError("Payment cannot be added to a cancelled or no-show booking.")

        if extra_charge_id:
            cursor.execute("SELECT amount, paid_amount, balance_amount, payment_status FROM room_extra_charges WHERE charge_id=? AND booking_id=? AND hotel_id=?", (extra_charge_id, booking_id, hotel_id))
            charge = cursor.fetchone()
            if charge is None:
                raise ValueError("Extra charge not found.")
            balance = round(float(charge["balance_amount"]), 2)
            if amount > balance:
                raise ValueError("Payment cannot exceed extra charge balance.")
            new_paid = round(float(charge["paid_amount"]) + amount, 2)
            new_balance = round(float(charge["amount"]) - new_paid, 2)
            status = "Paid" if new_balance == 0 else "Partially Paid"
            cursor.execute("UPDATE room_extra_charges SET paid_amount=?, balance_amount=?, payment_status=?, updated_at=CURRENT_TIMESTAMP WHERE charge_id=? AND hotel_id=?", (new_paid, new_balance, status, extra_charge_id, hotel_id))
        else:
            balance = max(float(booking["balance_amount"] or 0), 0)
            if apply_to_booking and amount > balance:
                raise ValueError("Payment cannot exceed room balance.")
            if not apply_to_booking and amount > float(booking["grand_total"] or 0):
                raise ValueError("Payment cannot exceed room grand total.")
            if apply_to_booking:
                new_paid = round(float(booking["paid_amount"] or booking["advance_amount"] or 0) + amount, 2)
                new_balance = round(float(booking["grand_total"] or 0) - new_paid, 2)
                status = "Paid" if new_balance == 0 else ("Partially Paid" if new_paid > 0 else "Pending")
                cursor.execute("UPDATE room_bookings SET paid_amount=?, balance_amount=?, payment_status=?, payment_method=?, updated_at=CURRENT_TIMESTAMP WHERE booking_id=? AND hotel_id=?", (new_paid, new_balance, status, payment_method, booking_id, hotel_id))

        transaction_id = _new_transaction_id()
        cursor.execute("""
            INSERT INTO room_payment_transactions(
                transaction_id, hotel_id, booking_id, transaction_type,
                payment_method, amount, extra_charge_id, notes
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """, (transaction_id, hotel_id, booking_id, transaction_type, payment_method, amount, extra_charge_id, notes))
        try:
            from database.notification_db import record_notification_event
            customer = cursor.execute(
                """
                SELECT customer_id, customer_name, customer_mobile
                FROM room_bookings
                WHERE booking_id = ? AND hotel_id = ?
                """,
                (booking_id, hotel_id),
            ).fetchone()
            record_notification_event(
                "Payment",
                "Room Payment Recorded",
                f"Payment of ₹{amount:.2f} was recorded for room booking {booking_id}.",
                reference_type="ROOM_PAYMENT",
                reference_id=transaction_id,
                recipient_type="Guest",
                recipient_id=customer["customer_id"] if customer else None,
                recipient_name=customer["customer_name"] if customer else None,
                recipient_mobile=customer["customer_mobile"] if customer else None,
                hotel_id=hotel_id,
                idempotency_key=f"PAYMENT:{hotel_id}:ROOM:{transaction_id}",
                connection=connection,
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        if owns_connection:
            connection.commit()
            try:
                from database.audit_db import log_business_activity
                log_business_activity(
                    module="Room Payment",
        action="PAYMENT",
        local_values=locals(),
        details="Business operation record_room_payment completed successfully.",
                )
            except Exception as exc:
                log_non_blocking_error("Non-blocking optional operation failed", exc)
        return transaction_id
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def add_room_extra_charge(booking_id, description, amount, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else hotel_id
    description = str(description or "").strip()
    amount = round(float(amount), 2)
    if not description:
        raise ValueError("Charge description is required.")
    if amount <= 0:
        raise ValueError("Extra charge must be greater than ₹0.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT booking_status FROM room_bookings WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        booking = cursor.fetchone()
        if booking is None:
            raise ValueError("Booking not found.")
        if booking["booking_status"] in ("Cancelled", "No-Show", "Checked-Out"):
            raise ValueError("Extra charges cannot be added to this booking.")
        charge_id = _new_charge_id()
        cursor.execute("""
            INSERT INTO room_extra_charges(charge_id, hotel_id, booking_id, description, amount, paid_amount, balance_amount, payment_status)
            VALUES(?, ?, ?, ?, ?, 0, ?, 'Pending')
        """, (charge_id, hotel_id, booking_id, description, amount, amount))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Payment",
        action="CREATE",
        local_values=locals(),
        details="Business operation add_room_extra_charge completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return charge_id
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()


def get_room_extra_charges(booking_id, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else hotel_id
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM room_extra_charges WHERE booking_id=? AND hotel_id=? ORDER BY created_at DESC", (booking_id, hotel_id))
        return cursor.fetchall()
    finally:
        connection.close()


def get_room_payment_transactions(booking_id, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else hotel_id
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM room_payment_transactions WHERE booking_id=? AND hotel_id=? ORDER BY created_at DESC", (booking_id, hotel_id))
        return cursor.fetchall()
    finally:
        connection.close()


def get_room_folio_summary(booking_id, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else hotel_id
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT grand_total, advance_amount, paid_amount, balance_amount, payment_status FROM room_bookings WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        booking = cursor.fetchone()
        if booking is None:
            raise ValueError("Booking not found.")
        cursor.execute("SELECT COALESCE(SUM(amount),0) AS total, COALESCE(SUM(paid_amount),0) AS paid, COALESCE(SUM(balance_amount),0) AS balance FROM room_extra_charges WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        charges = cursor.fetchone()
        return {
            "room_total": float(booking["grand_total"] or 0),
            "room_paid": float(booking["paid_amount"] if booking["paid_amount"] is not None else (booking["advance_amount"] or 0)),
            "room_balance": float(booking["balance_amount"] or 0),
            "extra_total": float(charges["total"] or 0),
            "extra_paid": float(charges["paid"] or 0),
            "extra_balance": float(charges["balance"] or 0),
            "total_due": round(float(booking["balance_amount"] or 0) + float(charges["balance"] or 0), 2),
            "payment_status": booking["payment_status"]
        }
    finally:
        connection.close()
