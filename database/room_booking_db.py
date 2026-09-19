from utils.error_logging import log_non_blocking_error
from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from datetime import datetime, timedelta

ROOM_STATUSES = (
    "Available",
    "Reserved",
    "Occupied",
    "Dirty",
    "Cleaning",
    "Maintenance",
    "Out of Service",
)

DEFAULT_ROOM_STATUS = "Available"

BOOKING_STATUSES = (
    "Pending",
    "Confirmed",
    "Cancelled",
    "No-Show",
    "Checked-In",
    "Checked-Out",
)

PAYMENT_STATUSES = (
    "Pending",
    "Partially Paid",
    "Paid",
    "Refunded",
)


def validate_booking_room_consistency(cursor, hotel_id, room_number):
    """
    Ensure that a booking room belongs to the same hotel context.
    """

    cursor.execute(
        """
        SELECT room_number, is_active
        FROM rooms
        WHERE hotel_id = ?
        AND room_number = ?
        """,
        (hotel_id, room_number)
    )

    room = cursor.fetchone()

    if room is None:
        raise ValueError(
            "Booking room does not belong to the current hotel."
        )

    return room

def create_room_bookings_table():

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS room_bookings(

                booking_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL DEFAULT 1,

                booking_date TEXT,
                booking_time TEXT,

                customer_id TEXT,

                customer_name TEXT,
                customer_mobile TEXT,

                room_number TEXT,
                room_type TEXT,
                room_price REAL,

                days INTEGER,
                subtotal REAL,
                gst REAL,
                grand_total REAL,

                check_in_date TEXT,
                expected_check_out TEXT,
                actual_check_in TEXT,
                actual_check_out TEXT,

                adults INTEGER NOT NULL DEFAULT 1,
                children INTEGER NOT NULL DEFAULT 0,

                nights INTEGER,

                room_rate REAL,

                payment_status TEXT NOT NULL DEFAULT 'Pending',

                booking_status TEXT NOT NULL DEFAULT 'Confirmed',

                booking_source TEXT NOT NULL DEFAULT 'Direct',

                advance_amount REAL NOT NULL DEFAULT 0,
                paid_amount REAL NOT NULL DEFAULT 0,
                balance_amount REAL NOT NULL DEFAULT 0,
                payment_method TEXT,

                notes TEXT,

                early_check_in_time TEXT,
                late_check_out_time TEXT,

                cancellation_reason TEXT,
                no_show_reason TEXT,
                
                created_at TEXT,
                updated_at TEXT

            )
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def migrate_room_bookings_schema():

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("PRAGMA table_info(room_bookings)")

        existing_columns = {
            column["name"]
            for column in cursor.fetchall()
        }

        new_columns = {
            "hotel_id": "INTEGER NOT NULL DEFAULT 1",
            "customer_id": "TEXT",
            "check_in_date": "TEXT",
            "expected_check_out": "TEXT",
            "actual_check_in": "TEXT",
            "actual_check_out": "TEXT",
            "adults": "INTEGER NOT NULL DEFAULT 1",
            "children": "INTEGER NOT NULL DEFAULT 0",
            "nights": "INTEGER",
            "room_rate": "REAL",
            "payment_status": "TEXT NOT NULL DEFAULT 'Pending'",
            "booking_status": "TEXT NOT NULL DEFAULT 'Confirmed'",
            "booking_source": "TEXT NOT NULL DEFAULT 'Direct'",
            "advance_amount": "REAL NOT NULL DEFAULT 0",
            "paid_amount": "REAL NOT NULL DEFAULT 0",
            "balance_amount": "REAL NOT NULL DEFAULT 0",
            "payment_method": "TEXT",
            "notes": "TEXT",
            "cancellation_reason": "TEXT",
            "no_show_reason": "TEXT",
            "early_check_in_time": "TEXT",
            "late_check_out_time": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT"
        }

        for column_name, column_definition in new_columns.items():

            if column_name not in existing_columns:

                cursor.execute(
                    f"""
                    ALTER TABLE room_bookings
                    ADD COLUMN {column_name} {column_definition}
                    """
                )

        # Existing bookings ko new schema ke compatible
        # values ke saath normalize karo.
        cursor.execute("""
            UPDATE room_bookings
            SET
                hotel_id = CASE
                    WHEN hotel_id IS NULL
                        THEN 1
                    ELSE hotel_id
                END,
                
                check_in_date = CASE
                    WHEN check_in_date IS NULL
                        THEN booking_date
                    ELSE check_in_date
                END,

                nights = CASE
                    WHEN nights IS NULL
                        THEN days
                    ELSE nights
                END,

                room_rate = CASE
                    WHEN room_rate IS NULL
                        THEN room_price
                    ELSE room_rate
                END,

                adults = CASE
                    WHEN adults IS NULL OR adults < 1
                        THEN 1
                    ELSE adults
                END,

                children = CASE
                    WHEN children IS NULL OR children < 0
                        THEN 0
                    ELSE children
                END,

                payment_status = CASE
                    WHEN payment_status IS NULL
                        THEN 'Pending'
                    ELSE payment_status
                END,

                advance_amount = CASE
                    WHEN advance_amount IS NULL OR advance_amount < 0 THEN 0
                    ELSE advance_amount
                END,

                balance_amount = CASE
                    WHEN balance_amount IS NULL OR balance_amount < 0 THEN COALESCE(grand_total, 0)
                    ELSE balance_amount
                END,

                booking_status = CASE
                    WHEN booking_status IS NULL
                        THEN 'Confirmed'
                    ELSE booking_status
                END,

                booking_source = CASE
                    WHEN booking_source IS NULL
                        THEN 'Direct'
                    ELSE booking_source
                END,

                notes = CASE
                    WHEN notes IS NULL
                        THEN ''
                    ELSE notes
                END,

                created_at = CASE
                    WHEN created_at IS NULL
                        THEN CURRENT_TIMESTAMP
                    ELSE created_at
                END,

                updated_at = CASE
                    WHEN updated_at IS NULL
                        THEN CURRENT_TIMESTAMP
                    ELSE updated_at
                END
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_room_bookings_customer_hotel
            ON room_bookings(customer_id, hotel_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_room_bookings_guest_history
            ON room_bookings(customer_id, hotel_id, booking_status, created_at)
        """)

        cursor.execute("""
            UPDATE room_bookings
            SET paid_amount = CASE
                WHEN paid_amount IS NULL OR paid_amount < 0 THEN COALESCE(advance_amount, 0)
                ELSE paid_amount
            END
        """)

        # Existing legacy bookings ke liye expected checkout
        # booking_date + nights ke basis par calculate karo.
        cursor.execute("""
            SELECT
                booking_id,
                check_in_date,
                nights
            FROM room_bookings
            WHERE expected_check_out IS NULL
               OR expected_check_out = ''
        """)

        bookings = cursor.fetchall()

        from datetime import datetime, timedelta

        for booking in bookings:

            check_in_date = booking["check_in_date"]
            nights = booking["nights"]

            if not check_in_date or not nights:
                continue

            try:
                check_in = datetime.strptime(
                    check_in_date,
                    "%d-%m-%Y"
                )

                expected_checkout = (
                    check_in + timedelta(days=int(nights))
                ).strftime("%d-%m-%Y")

                cursor.execute(
                    """
                    UPDATE room_bookings
                    SET expected_check_out = ?
                    WHERE booking_id = ?
                    """,
                    (
                        expected_checkout,
                        booking["booking_id"]
                    )
                )

            except (ValueError, TypeError):
                # Invalid legacy date ko forcefully modify mat karo.
                continue

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def migrate_room_booking_customer_links():
    from database.customer_db import resolve_guest_for_booking

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                booking_id,
                customer_name,
                customer_mobile,
                customer_id
            FROM room_bookings
            WHERE customer_id IS NULL
               OR TRIM(customer_id) = ''
        """)

        bookings = cursor.fetchall()

    finally:
        connection.close()

    for booking in bookings:
        mobile = str(booking["customer_mobile"] or "").strip()

        if not mobile:
            continue

        customer_id = resolve_guest_for_booking(
            booking["customer_name"],
            mobile
        )

        connection = get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute("""
                UPDATE room_bookings
                SET customer_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE booking_id = ?
                  AND (customer_id IS NULL OR TRIM(customer_id) = '')
            """, (
                customer_id,
                booking["booking_id"]
            ))

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

def create_room_booking_allocations_table():
    """Create date-range room allocation records for reservation conflict control."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS room_booking_allocations(
                allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id TEXT NOT NULL,
                hotel_id INTEGER NOT NULL,
                room_number TEXT NOT NULL,
                check_in_date TEXT NOT NULL,
                expected_check_out TEXT NOT NULL,
                allocation_status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(booking_id, hotel_id, room_number),
                FOREIGN KEY (booking_id) REFERENCES room_bookings(booking_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_room_booking_allocations_lookup
            ON room_booking_allocations(hotel_id, room_number, check_in_date, expected_check_out, allocation_status)
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO room_booking_allocations(
                booking_id, hotel_id, room_number, check_in_date, expected_check_out,
                allocation_status, created_at, updated_at
            )
            SELECT booking_id, hotel_id, room_number, check_in_date, expected_check_out,
                   CASE WHEN booking_status IN ('Cancelled','No-Show','Checked-Out') THEN 'Inactive' ELSE 'Active' END,
                   created_at, updated_at
            FROM room_bookings
            WHERE check_in_date IS NOT NULL
              AND expected_check_out IS NOT NULL
        """)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _parse_booking_date(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.strptime(value.strip(), "%d-%m-%Y")
    raise ValueError("Booking date must be in DD-MM-YYYY format.")


def _validate_date_range(check_in_date, nights):
    check_in = _parse_booking_date(check_in_date)
    nights = int(nights)
    if nights <= 0:
        raise ValueError("Number of nights must be greater than zero.")
    check_out = check_in + timedelta(days=nights)
    return check_in, check_out


def _room_has_date_conflict(cursor, hotel_id, room_number, check_in, check_out, exclude_booking_id=None):
    query = """
        SELECT booking_id
        FROM room_booking_allocations
        WHERE hotel_id = ?
          AND room_number = ?
          AND allocation_status = 'Active'
          AND check_in_date < ?
          AND expected_check_out > ?
    """
    params = [hotel_id, room_number, check_out.strftime("%d-%m-%Y"), check_in.strftime("%d-%m-%Y")]
    # Dates are stored as DD-MM-YYYY, so compare through Python instead of lexical SQL.
    cursor.execute("""
        SELECT booking_id, check_in_date, expected_check_out
        FROM room_booking_allocations
        WHERE hotel_id = ? AND room_number = ? AND allocation_status = 'Active'
    """, (hotel_id, room_number))
    for row in cursor.fetchall():
        if exclude_booking_id and row["booking_id"] == exclude_booking_id:
            continue
        existing_in = _parse_booking_date(row["check_in_date"])
        existing_out = _parse_booking_date(row["expected_check_out"])
        if existing_in < check_out and existing_out > check_in:
            return row["booking_id"]
    return None


def _sync_room_status_for_reservation(cursor, hotel_id, room_number, check_in, check_out):
    """Reserve a room immediately only when the stay starts today; future stays remain inventory-available."""
    today = datetime.now().date()
    if check_in.date() <= today < check_out.date():
        cursor.execute("""
            UPDATE rooms SET room_status='Reserved', updated_at=CURRENT_TIMESTAMP
            WHERE hotel_id=? AND room_number=? AND room_status='Available' AND is_active=1
        """, (hotel_id, room_number))
        if cursor.rowcount != 1:
            raise ValueError("Room is currently unavailable.")


def _reconcile_reserved_room_statuses(cursor, hotel_id):
    """Repair stale Reserved room statuses from the authoritative active allocations."""
    today = datetime.now().date()

    cursor.execute(
        """
        SELECT room_number
        FROM rooms
        WHERE hotel_id = ?
          AND room_status = 'Reserved'
        """,
        (hotel_id,)
    )
    reserved_rooms = [row["room_number"] for row in cursor.fetchall()]

    for room_number in reserved_rooms:
        cursor.execute(
            """
            SELECT
                a.check_in_date,
                a.expected_check_out,
                b.booking_status
            FROM room_booking_allocations AS a
            JOIN room_bookings AS b
              ON b.booking_id = a.booking_id
             AND b.hotel_id = a.hotel_id
            WHERE a.hotel_id = ?
              AND a.room_number = ?
              AND a.allocation_status = 'Active'
              AND b.booking_status IN ('Pending', 'Confirmed', 'Checked-In')
            ORDER BY a.check_in_date
            """,
            (hotel_id, room_number)
        )
        allocations = cursor.fetchall()

        target_status = 'Available'

        for allocation in allocations:
            start = _parse_booking_date(allocation["check_in_date"]).date()
            end = _parse_booking_date(allocation["expected_check_out"]).date()

            if allocation["booking_status"] == 'Checked-In' and start <= today < end:
                target_status = 'Occupied'
                break

            if allocation["booking_status"] in ('Pending', 'Confirmed') and start <= today < end:
                target_status = 'Reserved'
                break

        if target_status != 'Reserved':
            cursor.execute(
                """
                UPDATE rooms
                SET room_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE hotel_id = ?
                  AND room_number = ?
                  AND room_status = 'Reserved'
                """,
                (target_status, hotel_id, room_number)
            )


def reconcile_room_statuses():
    """Synchronize stale Reserved room statuses with active room allocations."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        _reconcile_reserved_room_statuses(cursor, hotel_id)
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation reconcile_room_statuses completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _refresh_payment_fields(cursor, booking_id, hotel_id, paid_amount):
    cursor.execute("SELECT grand_total FROM room_bookings WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Booking not found.")
    total = float(row["grand_total"] or 0)
    paid = round(float(paid_amount or 0), 2)
    if paid < 0 or paid > total:
        raise ValueError("Paid amount must be between 0 and the booking total.")
    balance = round(total - paid, 2)
    status = "Paid" if balance == 0 else ("Partially Paid" if paid > 0 else "Pending")
    cursor.execute("""
        UPDATE room_bookings
        SET paid_amount=?, balance_amount=?, payment_status=?, updated_at=CURRENT_TIMESTAMP
        WHERE booking_id=? AND hotel_id=?
    """, (paid, balance, status, booking_id, hotel_id))


def create_multi_room_reservation(
    booking_id,
    booking_time,
    customer_name,
    customer_mobile,
    room_numbers,
    days,
    booking_source='Direct',
    notes='',
    advance_amount=0,
    payment_method=None,
    check_in_date=None,
    booking_status='Pending',
    adults=1,
    children=0,
    customer_id=None,
    customer_email=None,
    customer_address=None
):
    from database.customer_db import resolve_guest_for_booking
    from database.room_payment_db import get_required_reservation_advance_for_rooms, record_room_payment

    if not room_numbers:
        raise ValueError("At least one room is required.")

    validate_booking_status(booking_status)

    adults = int(adults)
    children = int(children)

    if adults < 1 or children < 0:
        raise ValueError(
            "Adults must be at least 1 and children cannot be negative."
        )

    unique_rooms = list(
        dict.fromkeys(
            str(room).strip()
            for room in room_numbers
            if str(room).strip()
        )
    )

    if not unique_rooms:
        raise ValueError("At least one room is required.")

    hotel_id = get_current_hotel_id()

    if customer_id is None:
        customer_id = resolve_guest_for_booking(
            customer_name=customer_name,
            customer_mobile=customer_mobile,
            customer_email=customer_email,
            customer_address=customer_address,
            hotel_id=hotel_id
        )
    else:
        from database.customer_db import ensure_guest_hotel_relationship
        ensure_guest_hotel_relationship(customer_id, hotel_id)

    check_in = (
        _parse_booking_date(check_in_date)
        if check_in_date
        else booking_time
    )

    check_in, check_out = _validate_date_range(
        check_in,
        days
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        room_rows = []
        subtotal = 0.0

        for room_number in unique_rooms:
            cursor.execute(
                """
                SELECT *
                FROM rooms
                WHERE hotel_id = ?
                  AND room_number = ?
                  AND is_active = 1
                """,
                (hotel_id, room_number)
            )

            room = cursor.fetchone()

            if room is None:
                raise ValueError(
                    f"Room {room_number} not found or inactive."
                )

            if _room_has_date_conflict(
                cursor,
                hotel_id,
                room_number,
                check_in,
                check_out
            ):
                raise ValueError(
                    f"Room {room_number} is unavailable for the selected dates."
                )

            room_rows.append(room)

            subtotal += (
                float(room["room_price"] or 0)
                * int(days)
            )

        gst = round(subtotal * 0.05, 2)
        grand_total = round(subtotal + gst, 2)

        advance = float(advance_amount or 0)
        minimum_advance = get_required_reservation_advance_for_rooms(unique_rooms, hotel_id)

        if advance < minimum_advance:
            raise ValueError(f"Minimum reservation advance for selected rooms is ₹{minimum_advance:.2f}.")
        if advance < 0 or advance > grand_total:
            raise ValueError(
                "Advance payment must be between 0 and the booking total."
            )

        balance = round(
            grand_total - advance,
            2
        )

        payment_status = (
            "Paid"
            if balance == 0
            else (
                "Partially Paid"
                if advance > 0
                else "Pending"
            )
        )

        primary = room_rows[0]

        cursor.execute(
            """
            INSERT INTO room_bookings(
                booking_id,
                hotel_id,
                customer_id,
                booking_date,
                booking_time,
                customer_name,
                customer_mobile,
                room_number,
                room_type,
                room_price,
                days,
                subtotal,
                gst,
                grand_total,
                check_in_date,
                expected_check_out,
                adults,
                children,
                nights,
                room_rate,
                payment_status,
                booking_status,
                booking_source,
                advance_amount,
                paid_amount,
                balance_amount,
                payment_method,
                notes,
                created_at,
                updated_at
            )
            VALUES(
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """,
            (
                booking_id,
                hotel_id,
                customer_id,
                booking_time.strftime("%d-%m-%Y"),
                booking_time.strftime("%I:%M:%S %p"),
                customer_name,
                customer_mobile,
                primary["room_number"],
                primary["room_type"],
                primary["room_price"],
                days,
                subtotal,
                gst,
                grand_total,
                check_in.strftime("%d-%m-%Y"),
                check_out.strftime("%d-%m-%Y"),
                adults,
                children,
                days,
                primary["room_price"],
                payment_status,
                booking_status,
                booking_source,
                advance,
                advance,
                balance,
                payment_method,
                notes
            )
        )

        for room in room_rows:
            cursor.execute(
                """
                INSERT INTO room_booking_allocations(
                    booking_id,
                    hotel_id,
                    room_number,
                    check_in_date,
                    expected_check_out,
                    allocation_status,
                    created_at,
                    updated_at
                )
                VALUES(
                    ?, ?, ?, ?, ?, 'Active',
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    booking_id,
                    hotel_id,
                    room["room_number"],
                    check_in.strftime("%d-%m-%Y"),
                    check_out.strftime("%d-%m-%Y")
                )
            )

            _sync_room_status_for_reservation(
                cursor,
                hotel_id,
                room["room_number"],
                check_in,
                check_out
            )

        if advance > 0:
            record_room_payment(
                booking_id, advance, payment_method,
                transaction_type="ADVANCE",
                notes="Initial reservation advance",
                hotel_id=hotel_id, connection=connection, apply_to_booking=False
            )

        connection.commit()

        # Record the booking notification only after the booking transaction
        # has committed. The notification layer opens its own connection so
        # notification delivery records cannot be lost because of the booking
        # transaction lifecycle. Notification failure must never undo a
        # successfully committed hotel booking.
        try:
            from database.notification_db import record_notification_event
            record_notification_event(
                "Booking",
                "Room Booking Confirmed",
                f"Room booking {booking_id} has been confirmed for {customer_name}.",
                reference_type="ROOM_BOOKING",
                reference_id=booking_id,
                recipient_type="Guest",
                recipient_id=customer_id,
                recipient_name=customer_name,
                recipient_mobile=customer_mobile,
                recipient_email=customer_email,
                hotel_id=hotel_id,
                idempotency_key=f"BOOKING:{hotel_id}:ROOM:{booking_id}",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        return booking_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def modify_reservation(booking_id, customer_name=None, customer_mobile=None, room_number=None,
                       check_in_date=None, nights=None, notes=None, advance_amount=None,
                       payment_method=None, adults=None, children=None):
    """Modify a Pending/Confirmed reservation, including one or multiple rooms."""
    connection = get_connection()
    try:
        cursor = connection.cursor(); hotel_id = get_current_hotel_id()
        cursor.execute("SELECT * FROM room_bookings WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        booking = cursor.fetchone()
        if booking is None:
            raise ValueError("Booking not found.")
        if booking['booking_status'] not in ('Pending', 'Confirmed'):
            raise ValueError("Only Pending or Confirmed reservations can be modified.")

        if room_number:
            target_rooms = list(dict.fromkeys(x.strip() for x in str(room_number).split(',') if x.strip()))
        else:
            cursor.execute("SELECT room_number FROM room_booking_allocations WHERE booking_id=? AND hotel_id=? AND allocation_status='Active' ORDER BY room_number", (booking_id, hotel_id))
            target_rooms = [r['room_number'] for r in cursor.fetchall()]
            if not target_rooms:
                target_rooms = [booking['room_number']]

        start = _parse_booking_date(check_in_date) if check_in_date else _parse_booking_date(booking['check_in_date'])
        stay_nights = int(nights if nights is not None else (booking['nights'] or booking['days'] or 1))
        start, end = _validate_date_range(start, stay_nights)

        cursor.execute("SELECT room_number FROM room_booking_allocations WHERE booking_id=? AND hotel_id=? AND allocation_status='Active'", (booking_id, hotel_id))
        old_allocations = [r['room_number'] for r in cursor.fetchall()]

        room_rows=[]; subtotal=0.0
        for target in target_rooms:
            cursor.execute("SELECT * FROM rooms WHERE hotel_id=? AND room_number=? AND is_active=1", (hotel_id, target))
            room=cursor.fetchone()
            if room is None:
                raise ValueError(f"Room {target} does not exist or is inactive.")
            conflict=_room_has_date_conflict(cursor, hotel_id, target, start, end, exclude_booking_id=booking_id)
            if conflict:
                raise ValueError(f"Room {target} is unavailable for the selected dates.")
            room_rows.append(room); subtotal += float(room['room_price'] or 0) * stay_nights

        gst=round(subtotal*0.05,2); grand=round(subtotal+gst,2)
        paid=float(booking['paid_amount'] or booking['advance_amount'] or 0)
        if paid<0 or paid>grand:
            raise ValueError("Existing room payments cannot exceed the modified booking total.")
        balance=round(grand-paid,2)
        new_adults = int(booking['adults'] or 1) if adults is None else int(adults)
        new_children = int(booking['children'] or 0) if children is None else int(children)
        if new_adults < 1 or new_children < 0:
            raise ValueError("Adults must be at least 1 and children cannot be negative.")
        payment_status='Paid' if balance==0 else ('Partially Paid' if paid>0 else 'Pending')
        advance=float(booking['advance_amount'] or 0)
        payment_method=booking['payment_method']

        for old_room in old_allocations:
            if old_room not in target_rooms:
                cursor.execute("UPDATE rooms SET room_status='Available', updated_at=CURRENT_TIMESTAMP WHERE hotel_id=? AND room_number=? AND room_status='Reserved'", (hotel_id, old_room))

        primary=room_rows[0]
        cursor.execute("""UPDATE room_bookings SET customer_name=?,customer_mobile=?,room_number=?,room_type=?,room_price=?,days=?,subtotal=?,gst=?,grand_total=?,check_in_date=?,expected_check_out=?,nights=?,room_rate=?,adults=?,children=?,payment_status=?,advance_amount=?,paid_amount=?,balance_amount=?,payment_method=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE booking_id=? AND hotel_id=?""",
            (customer_name if customer_name is not None else booking['customer_name'], customer_mobile if customer_mobile is not None else booking['customer_mobile'], primary['room_number'], primary['room_type'], primary['room_price'], stay_nights, subtotal, gst, grand, start.strftime('%d-%m-%Y'), end.strftime('%d-%m-%Y'), stay_nights, primary['room_price'], new_adults, new_children, payment_status, advance, paid, balance, payment_method, notes if notes is not None else booking['notes'], booking_id, hotel_id))
        cursor.execute("DELETE FROM room_booking_allocations WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        for room in room_rows:
            cursor.execute("INSERT INTO room_booking_allocations(booking_id,hotel_id,room_number,check_in_date,expected_check_out,allocation_status,created_at,updated_at) VALUES(?,?,?,?,?,'Active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (booking_id, hotel_id, room['room_number'], start.strftime('%d-%m-%Y'), end.strftime('%d-%m-%Y')))
            _sync_room_status_for_reservation(cursor, hotel_id, room['room_number'], start, end)
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation modify_reservation completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()

def get_available_rooms_for_dates(check_in_date, nights):
    """Return active rooms available for the complete requested date range."""
    check_in, check_out = _validate_date_range(check_in_date, nights)
    connection = get_connection()
    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        _reconcile_reserved_room_statuses(cursor, hotel_id)
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation get_available_rooms_for_dates completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        cursor.execute("SELECT * FROM rooms WHERE hotel_id=? AND is_active=1 ORDER BY room_number", (hotel_id,))
        rooms = []
        for room in cursor.fetchall():
            if room["room_status"] in ("Maintenance", "Out of Service", "Occupied", "Dirty", "Cleaning") and check_in.date() <= datetime.now().date() < check_out.date():
                continue
            if _room_has_date_conflict(cursor, hotel_id, room["room_number"], check_in, check_out):
                continue
            rooms.append(room)
        return rooms
    finally:
        connection.close()


def save_and_book_room(
    booking_id,
    booking_time,
    customer_name,
    customer_mobile,
    room_choice,
    room_type,
    room_price,
    days,
    total,
    gst,
    grand_total,
    check_in_date=None,
    advance_amount=0,
    payment_method=None,
    notes="",
    booking_status="Pending",
    adults=1,
    children=0,
    customer_id=None,
    customer_email=None,
    customer_address=None
):
    from database.customer_db import resolve_guest_for_booking
    from database.room_payment_db import get_required_reservation_advance, record_room_payment

    hotel_id = get_current_hotel_id()

    if customer_id is None:
        customer_id = resolve_guest_for_booking(
            customer_name=customer_name,
            customer_mobile=customer_mobile,
            customer_email=customer_email,
            customer_address=customer_address,
            hotel_id=hotel_id
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        check_in, check_out = _validate_date_range(
            check_in_date or booking_time,
            days
        )

        validate_booking_status(booking_status)

        adults = int(adults)
        children = int(children)

        if adults < 1 or children < 0:
            raise ValueError(
                "Adults must be at least 1 and children cannot be negative."
            )

        cursor.execute(
            """
            SELECT room_type, room_price, room_status, is_active
            FROM rooms
            WHERE hotel_id = ?
              AND room_number = ?
            """,
            (hotel_id, room_choice)
        )

        room = cursor.fetchone()

        if room is None:
            raise ValueError("Invalid Room Number.")

        validate_booking_room_consistency(
            cursor,
            hotel_id,
            room_choice
        )

        if room["is_active"] != 1:
            raise ValueError("Room is inactive.")

        if (
            room["room_status"] != "Available"
            and check_in.date() <= datetime.now().date() < check_out.date()
        ):
            raise ValueError("Room is no longer available.")

        conflict = _room_has_date_conflict(
            cursor,
            hotel_id,
            room_choice,
            check_in,
            check_out
        )

        if conflict:
            raise ValueError(
                "Room is unavailable for the selected dates."
            )

        room_type = room["room_type"]
        room_price = room["room_price"]

        total = round(float(room_price) * int(days), 2)
        gst = round(total * 0.05, 2)
        grand_total = round(total + gst, 2)

        advance = float(advance_amount or 0)
        minimum_advance = get_required_reservation_advance(room_choice, hotel_id)

        if advance < minimum_advance:
            raise ValueError(f"Minimum reservation advance for Room {room_choice} is ₹{minimum_advance:.2f}.")
        if advance < 0 or advance > grand_total:
            raise ValueError(
                "Advance payment must be between 0 and the booking total."
            )

        if (
            check_in.date() <= datetime.now().date() < check_out.date()
        ):
            cursor.execute(
                """
                UPDATE rooms
                SET room_status = 'Reserved',
                    updated_at = CURRENT_TIMESTAMP
                WHERE hotel_id = ?
                  AND room_number = ?
                  AND room_status = 'Available'
                  AND is_active = 1
                """,
                (hotel_id, room_choice)
            )

            if cursor.rowcount == 0:
                raise ValueError("Room is no longer available.")

        booking_status = "Confirmed"

        cursor.execute(
            """
            INSERT INTO room_bookings(
                booking_id,
                hotel_id,
                customer_id,
                booking_date,
                booking_time,
                customer_name,
                customer_mobile,
                room_number,
                room_type,
                room_price,
                days,
                subtotal,
                gst,
                grand_total,
                check_in_date,
                expected_check_out,
                adults,
                children,
                nights,
                room_rate,
                payment_status,
                booking_status,
                booking_source,
                advance_amount,
                paid_amount,
                balance_amount,
                payment_method,
                notes,
                created_at,
                updated_at
            )
            VALUES(
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            (
                booking_id,
                hotel_id,
                customer_id,
                booking_time.strftime("%d-%m-%Y"),
                booking_time.strftime("%I:%M:%S %p"),
                customer_name,
                customer_mobile,
                room_choice,
                room_type,
                room_price,
                days,
                total,
                gst,
                grand_total,
                check_in.strftime("%d-%m-%Y"),
                check_out.strftime("%d-%m-%Y"),
                adults,
                children,
                days,
                room_price,
                "Paid"
                if advance == float(grand_total)
                else (
                    "Partially Paid"
                    if advance > 0
                    else "Pending"
                ),
                booking_status,
                "Direct",
                advance,
                advance,
                round(float(grand_total) - advance, 2),
                payment_method,
                notes
            )
        )

        cursor.execute(
            """
            INSERT INTO room_booking_allocations(
                booking_id,
                hotel_id,
                room_number,
                check_in_date,
                expected_check_out,
                allocation_status,
                created_at,
                updated_at
            )
            VALUES(
                ?, ?, ?, ?, ?, 'Active',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """,
            (
                booking_id,
                hotel_id,
                room_choice,
                check_in.strftime("%d-%m-%Y"),
                check_out.strftime("%d-%m-%Y")
            )
        )

        if advance > 0:
            record_room_payment(
                booking_id, advance, payment_method,
                transaction_type="ADVANCE",
                notes="Initial reservation advance",
                hotel_id=hotel_id, connection=connection, apply_to_booking=False
            )

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_and_book_room completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        # Record the booking notification only after the booking transaction
        # has committed. Use the notification layer's own connection so a
        # notification failure cannot undo a successfully created booking.
        try:
            from database.notification_db import record_notification_event
            record_notification_event(
                "Booking",
                "Room Booking Confirmed",
                f"Room booking {booking_id} has been confirmed for {customer_name}.",
                reference_type="ROOM_BOOKING",
                reference_id=booking_id,
                recipient_type="Guest",
                recipient_id=customer_id,
                recipient_name=customer_name,
                recipient_mobile=customer_mobile,
                recipient_email=customer_email,
                hotel_id=hotel_id,
                idempotency_key=f"BOOKING:{hotel_id}:ROOM:{booking_id}",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        return booking_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def update_stay_options(booking_id, early_check_in_time=None, late_check_out_time=None):
    """Store optional early check-in / late check-out requests for a reservation."""
    connection = get_connection()
    try:
        cursor = connection.cursor(); hotel_id = get_current_hotel_id()
        cursor.execute(
            "SELECT booking_status FROM room_bookings WHERE booking_id=? AND hotel_id=?",
            (booking_id, hotel_id),
        )
        booking = cursor.fetchone()
        if booking is None:
            raise ValueError("Booking not found.")
        if booking["booking_status"] in ("Cancelled", "Checked-Out", "No-Show"):
            raise ValueError("Stay options cannot be changed for a closed reservation.")
        cursor.execute(
            """UPDATE room_bookings
               SET early_check_in_time=?, late_check_out_time=?, updated_at=CURRENT_TIMESTAMP
               WHERE booking_id=? AND hotel_id=?""",
            (early_check_in_time, late_check_out_time, booking_id, hotel_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Stay options could not be updated.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking", action="UPDATE", local_values=locals(),
                details="Stay timing options updated.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()


def get_room_booking_by_id(booking_id):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT *
            FROM room_bookings
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        return cursor.fetchone()

    finally:
        connection.close()

def update_booking_status(booking_id, new_status):

    validate_booking_status(new_status)

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT booking_status, room_number, customer_id, customer_name, customer_mobile
            FROM room_bookings
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        booking = cursor.fetchone()

        if booking is None:
            raise ValueError("Booking not found.")

        validate_booking_room_consistency(
            cursor,
            hotel_id,
            booking["room_number"]
        )

        cursor.execute(
            """
            UPDATE room_bookings
            SET booking_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (new_status, booking_id, hotel_id)
        )

        if cursor.rowcount != 1:
            raise ValueError("Booking status could not be updated.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation update_booking_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def confirm_reservation(booking_id):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT booking_status, room_number
            FROM room_bookings
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        booking = cursor.fetchone()

        if booking is None:
            raise ValueError("Booking not found.")

        if booking["booking_status"] != "Pending":
            raise ValueError("Only Pending bookings can be confirmed.")

        validate_booking_room_consistency(
            cursor, hotel_id, booking["room_number"]
        )
        cursor.execute(
            """
            SELECT booking_id, check_in_date, expected_check_out
            FROM room_booking_allocations
            WHERE booking_id = ? AND hotel_id = ? AND allocation_status = 'Active'
            """,
            (booking_id, hotel_id)
        )
        allocations = cursor.fetchall()
        if not allocations:
            raise ValueError("Reservation has no active room allocation.")
        from database.room_payment_db import get_required_reservation_advance_for_rooms
        required_advance = get_required_reservation_advance_for_rooms(
            [row["room_number"] for row in allocations], hotel_id
        )
        cursor.execute("SELECT paid_amount, advance_amount FROM room_bookings WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        payment_row = cursor.fetchone()
        paid = float(payment_row["paid_amount"] if payment_row["paid_amount"] is not None else payment_row["advance_amount"] or 0)
        if paid < required_advance:
            raise ValueError(f"Minimum reservation advance is ₹{required_advance:.2f}. Payment is required before confirmation.")

        cursor.execute(
            """
            UPDATE room_bookings
            SET booking_status = 'Confirmed', updated_at = CURRENT_TIMESTAMP
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation confirm_reservation completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def cancel_reservation(booking_id, cancellation_reason):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT booking_status, room_number, customer_id, customer_name, customer_mobile
            FROM room_bookings
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        booking = cursor.fetchone()

        if booking is None:
            raise ValueError("Booking not found.")

        if booking["booking_status"] not in ("Pending", "Confirmed"):
            raise ValueError("Only Pending or Confirmed bookings can be cancelled.")

        room_number = booking["room_number"]

        validate_booking_room_consistency(cursor, hotel_id, room_number)

        cursor.execute(
            """
            UPDATE room_bookings
            SET booking_status = 'Cancelled', cancellation_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (cancellation_reason, booking_id, hotel_id)
        )

        cursor.execute(
            """
            UPDATE rooms
            SET room_status = 'Available', updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
              AND room_number IN (
                  SELECT room_number FROM room_booking_allocations
                  WHERE booking_id = ? AND hotel_id = ? AND allocation_status = 'Active'
              )
              AND room_status = 'Reserved'
            """,
            (hotel_id, booking_id, hotel_id)
        )

        cursor.execute(
            """
            UPDATE room_booking_allocations
            SET allocation_status='Inactive', updated_at=CURRENT_TIMESTAMP
            WHERE booking_id=? AND hotel_id=?
            """,
            (booking_id, hotel_id)
        )
        try:
            from database.notification_db import record_notification_event
            record_notification_event(
                "Cancellation",
                "Room Booking Cancelled",
                f"Room booking {booking_id} was cancelled. Reason: {cancellation_reason}.",
                reference_type="ROOM_BOOKING",
                reference_id=booking_id,
                recipient_type="Guest",
                recipient_id=booking["customer_id"],
                recipient_name=booking["customer_name"],
                recipient_mobile=booking["customer_mobile"],
                hotel_id=hotel_id,
                idempotency_key=f"CANCELLATION:{hotel_id}:ROOM:{booking_id}",
                connection=connection,
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CANCEL",
        local_values=locals(),
        details="Business operation cancel_reservation completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def mark_booking_no_show(booking_id, no_show_reason):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        cursor.execute("SELECT booking_status, room_number, check_in_date, nights, days FROM room_bookings WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        booking = cursor.fetchone()
        if booking is None:
            raise ValueError("Booking not found.")
        if booking["booking_status"] != "Confirmed":
            raise ValueError("Only Confirmed bookings can be marked as No-Show.")
        check_in, check_out = _validate_date_range(booking["check_in_date"], booking["nights"] or booking["days"] or 1)
        if datetime.now().date() < check_in.date():
            raise ValueError("A future reservation cannot be marked as No-Show before its check-in date.")
        cursor.execute("SELECT room_number FROM room_booking_allocations WHERE booking_id=? AND hotel_id=? AND allocation_status='Active'", (booking_id, hotel_id))
        allocations = cursor.fetchall()
        if not allocations:
            raise ValueError("Reservation has no active room allocation.")
        cursor.execute("UPDATE room_bookings SET booking_status='No-Show', no_show_reason=?, updated_at=CURRENT_TIMESTAMP WHERE booking_id=? AND hotel_id=?", (no_show_reason, booking_id, hotel_id))
        cursor.execute("UPDATE rooms SET room_status='Available', updated_at=CURRENT_TIMESTAMP WHERE hotel_id=? AND room_number IN (SELECT room_number FROM room_booking_allocations WHERE booking_id=? AND hotel_id=? AND allocation_status='Active') AND room_status='Reserved'", (hotel_id, booking_id, hotel_id))
        cursor.execute("UPDATE room_booking_allocations SET allocation_status='Inactive', updated_at=CURRENT_TIMESTAMP WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation mark_booking_no_show completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()

def transfer_room(booking_id, new_room_number):
    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT booking_status, room_number
            FROM room_bookings
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        booking = cursor.fetchone()

        if booking is None:
            raise ValueError("Booking not found.")

        if booking["booking_status"] != "Checked-In":
            raise ValueError("Only Checked-In bookings can be transferred.")

        old_room_number = booking["room_number"]

        if old_room_number == new_room_number:
            raise ValueError("New room must be different from the current room.")

        cursor.execute(
            """
            SELECT room_number, room_status, is_active
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, new_room_number)
        )

        new_room = cursor.fetchone()

        if new_room is None:
            raise ValueError("New room not found in the current hotel.")
        if new_room["is_active"] != 1:
            raise ValueError("New room is inactive.")
        if new_room["room_status"] != "Available":
            raise ValueError("New room is not available.")

        cursor.execute(
            """
            SELECT room_number
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            AND room_status = 'Occupied'
            """,
            (hotel_id, old_room_number)
        )

        if cursor.fetchone() is None:
            raise ValueError("Current booking room is not consistent with the current hotel.")

        cursor.execute(
            """
            UPDATE rooms
            SET room_status = 'Occupied', updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            AND room_status = 'Available'
            AND is_active = 1
            """,
            (hotel_id, new_room_number)
        )

        if cursor.rowcount != 1:
            raise ValueError("New room could not be occupied.")

        cursor.execute(
            """
            UPDATE rooms
            SET room_status = 'Available', updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            AND room_status = 'Occupied'
            """,
            (hotel_id, old_room_number)
        )

        if cursor.rowcount != 1:
            raise ValueError("Current room could not be released.")

        cursor.execute(
            """
            UPDATE room_bookings
            SET room_number = ?, updated_at = CURRENT_TIMESTAMP
            WHERE booking_id = ?
            AND hotel_id = ?
            AND booking_status = 'Checked-In'
            """,
            (new_room_number, booking_id, hotel_id)
        )

        if cursor.rowcount != 1:
            raise ValueError("Booking room could not be updated.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation transfer_room completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def check_in_guest(booking_id):
    from database.customer_db import (
        get_guest_repeat_recognition,
        record_guest_hotel_visit,
    )

    connection = get_connection()
    try:
        cursor = connection.cursor(); hotel_id = get_current_hotel_id()
        cursor.execute("SELECT * FROM room_bookings WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        booking=cursor.fetchone()
        if booking is None: raise ValueError("Booking not found.")
        if booking["booking_status"] != "Confirmed": raise ValueError("Only Confirmed bookings can be checked in.")
        check_in, check_out = _validate_date_range(booking["check_in_date"], booking["nights"] or booking["days"] or 1)
        today=datetime.now().date()
        if today < check_in.date(): raise ValueError("Guest cannot be checked in before the reservation check-in date.")
        if today >= check_out.date(): raise ValueError("Reservation check-out date has already passed.")
        cursor.execute("SELECT room_number FROM room_booking_allocations WHERE booking_id=? AND hotel_id=? AND allocation_status='Active'", (booking_id, hotel_id))
        allocations=cursor.fetchall()
        if not allocations: raise ValueError("Reservation has no active room allocation.")
        for allocation in allocations:
            cursor.execute("SELECT room_status,is_active FROM rooms WHERE hotel_id=? AND room_number=?", (hotel_id, allocation['room_number']))
            room=cursor.fetchone()
            if room is None or room['is_active'] != 1: raise ValueError(f"Room {allocation['room_number']} is unavailable.")
            if room['room_status'] not in ('Reserved','Available'): raise ValueError(f"Room {allocation['room_number']} is not available for check-in.")
        for allocation in allocations:
            cursor.execute("UPDATE rooms SET room_status='Occupied', updated_at=CURRENT_TIMESTAMP WHERE hotel_id=? AND room_number=? AND room_status IN ('Reserved','Available') AND is_active=1", (hotel_id, allocation['room_number']))
            if cursor.rowcount != 1: raise ValueError(f"Room {allocation['room_number']} could not be occupied.")
        repeat_guest = get_guest_repeat_recognition(
            booking["customer_id"],
            hotel_id
        ) if booking["customer_id"] else None

        cursor.execute("UPDATE room_bookings SET booking_status='Checked-In', actual_check_in=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE booking_id=? AND hotel_id=? AND booking_status='Confirmed'", (booking_id, hotel_id))
        if cursor.rowcount != 1: raise ValueError("Booking could not be checked in.")
        if booking["customer_id"]:
            record_guest_hotel_visit(
                booking["customer_id"],
                hotel_id,
                connection=connection
            )

        try:
            from database.notification_db import record_notification_event
            record_notification_event(
                "Check-in",
                "Guest Checked In",
                f"Guest {booking['customer_name']} has checked in for booking {booking_id}.",
                reference_type="ROOM_BOOKING",
                reference_id=booking_id,
                recipient_type="Guest",
                recipient_id=booking["customer_id"],
                recipient_name=booking["customer_name"],
                recipient_mobile=booking["customer_mobile"],
                hotel_id=hotel_id,
                idempotency_key=f"CHECKIN:{hotel_id}:{booking_id}",
                connection=connection,
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation check_in_guest completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        if repeat_guest and repeat_guest["is_repeat_guest"]:
            print(
                f"Repeat Guest Recognized: {repeat_guest['customer_name']} "
                f"(Previous Visits: {repeat_guest['visit_count']})"
            )
        elif repeat_guest:
            print(
                f"Guest Recognized: {repeat_guest['customer_name']} "
                "(First recorded stay at this hotel)"
            )
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()

def check_out_guest(booking_id):
    connection = get_connection()
    try:
        cursor = connection.cursor(); hotel_id = get_current_hotel_id()
        cursor.execute("SELECT booking_status, customer_id, customer_name, customer_mobile FROM room_bookings WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        booking=cursor.fetchone()
        if booking is None: raise ValueError("Booking not found.")
        if booking['booking_status'] != 'Checked-In': raise ValueError("Only Checked-In bookings can be checked out.")
        cursor.execute("SELECT room_number FROM room_booking_allocations WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        allocations=cursor.fetchall()
        if not allocations: raise ValueError("Reservation has no room allocation.")
        cursor.execute("SELECT COALESCE(balance_amount, 0) AS room_balance FROM room_bookings WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        room_balance = float(cursor.fetchone()["room_balance"] or 0)
        cursor.execute("SELECT COALESCE(SUM(balance_amount),0) AS extra_balance FROM room_extra_charges WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        extra_balance = float(cursor.fetchone()["extra_balance"] or 0)
        total_due = round(room_balance + extra_balance, 2)
        if total_due > 0.01:
            raise ValueError(f"Checkout payment pending. Outstanding amount is ₹{total_due:.2f}.")
        for allocation in allocations:
            cursor.execute("UPDATE rooms SET room_status='Dirty', housekeeping_status='Pending', updated_at=CURRENT_TIMESTAMP WHERE hotel_id=? AND room_number=? AND room_status='Occupied'", (hotel_id, allocation['room_number']))
            if cursor.rowcount == 1:
                from database.cleaning_db import create_cleaning_task
                create_cleaning_task("ROOM", allocation["room_number"], "Checkout Cleaning", hotel_id=hotel_id, connection=connection)
            if cursor.rowcount != 1: raise ValueError(f"Room {allocation['room_number']} is not Occupied.")
        cursor.execute("UPDATE room_bookings SET booking_status='Checked-Out', actual_check_out=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE booking_id=? AND hotel_id=? AND booking_status='Checked-In'", (booking_id, hotel_id))
        if cursor.rowcount != 1: raise ValueError("Booking could not be checked out.")
        cursor.execute("UPDATE room_booking_allocations SET allocation_status='Inactive', updated_at=CURRENT_TIMESTAMP WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        try:
            from database.notification_db import record_notification_event
            record_notification_event(
                "Check-out",
                "Guest Checked Out",
                f"Guest {booking['customer_name']} has checked out from booking {booking_id}.",
                reference_type="ROOM_BOOKING",
                reference_id=booking_id,
                recipient_type="Guest",
                recipient_id=booking["customer_id"],
                recipient_name=booking["customer_name"],
                recipient_mobile=booking["customer_mobile"],
                hotel_id=hotel_id,
                idempotency_key=f"CHECKOUT:{hotel_id}:{booking_id}",
                connection=connection,
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation check_out_guest completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()

def get_reservation_rooms(booking_id):
    connection=get_connection()
    try:
        cursor=connection.cursor(); hotel_id=get_current_hotel_id()
        cursor.execute("SELECT room_number, check_in_date, expected_check_out, allocation_status FROM room_booking_allocations WHERE booking_id=? AND hotel_id=? ORDER BY room_number", (booking_id,hotel_id))
        return cursor.fetchall()
    finally: connection.close()

def view_room_bookings():

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        cursor.execute(
            """
            SELECT *
            FROM room_bookings
            WHERE hotel_id = ?
            ORDER BY created_at DESC, booking_id DESC
            """,
            (hotel_id,)
        )
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Room Bookings Found.")
        return

    print("=" * 50)
    print("      ROOM BOOKING HISTORY")
    print("=" * 50)

    for record in records:
        print(f"Booking ID : {record['booking_id']}")
        print(f"Date : {record['booking_date']}")
        print(f"Time : {record['booking_time']}")
        print("-" * 50)
        print(f"Customer : {record['customer_name']}")
        print(f"Mobile : {record['customer_mobile']}")
        print("-" * 50)
        print(f"Room Number : {record['room_number']}")
        print(f"Room Type : {record['room_type']}")
        print(f"Price/Night : ₹{record['room_price']}")
        print(f"Days : {record['days']}")
        print("-" * 50)
        print(f"Subtotal : ₹{record['subtotal']}")
        print(f"GST : ₹{record['gst']}")
        print(f"Grand Total : ₹{record['grand_total']}")
        print("=" * 50)

def search_room_booking():

    print("=" * 50)
    print("      SEARCH ROOM BOOKING")
    print("=" * 50)

    booking_id = input("Enter Booking ID : ").upper()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        cursor.execute(
            """
            SELECT *
            FROM room_bookings
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )
        record = cursor.fetchone()
    finally:
        connection.close()

    if record:
        print("=" * 50)
        print(f"Booking ID : {record['booking_id']}")
        print(f"Date : {record['booking_date']}")
        print(f"Time : {record['booking_time']}")
        print("-" * 50)
        print(f"Customer : {record['customer_name']}")
        print(f"Mobile : {record['customer_mobile']}")
        print("-" * 50)
        print(f"Room Number : {record['room_number']}")
        print(f"Room Type : {record['room_type']}")
        print(f"Price/Night : ₹{record['room_price']}")
        print(f"Days : {record['days']}")
        print("-" * 50)
        print(f"Subtotal : ₹{record['subtotal']}")
        print(f"GST : ₹{record['gst']}")
        print(f"Grand Total : ₹{record['grand_total']}")
        print("=" * 50)
    else:
        print("Booking Not Found.")

def delete_room_booking():

    print("=" * 50)
    print("      DELETE ROOM BOOKING")
    print("=" * 50)

    booking_id = input("Enter Booking ID : ").strip().upper()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT room_number, booking_status
            FROM room_bookings
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        booking = cursor.fetchone()

        if booking is None:
            print("Booking Not Found.")
            return

        if booking["booking_status"] not in ("Pending", "Confirmed"):
            raise ValueError("Only Pending or Confirmed bookings can be deleted.")
        cursor.execute("SELECT COALESCE(SUM(amount),0) AS paid FROM room_payment_transactions WHERE booking_id=? AND hotel_id=?", (booking_id, hotel_id))
        if float(cursor.fetchone()["paid"] or 0) > 0.01:
            raise ValueError("Booking with recorded payments cannot be deleted. Use cancellation/refund workflow instead.")

        cursor.execute(
            """
            UPDATE rooms
            SET room_status = 'Available', updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
              AND room_number IN (
                  SELECT room_number
                  FROM room_booking_allocations
                  WHERE booking_id = ?
                    AND hotel_id = ?
                    AND allocation_status = 'Active'
              )
              AND room_status = 'Reserved'
            """,
            (hotel_id, booking_id, hotel_id)
        )

        cursor.execute(
            """
            DELETE FROM room_bookings
            WHERE booking_id = ?
            AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        if cursor.rowcount == 0:
            raise ValueError("Booking could not be deleted.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_room_booking completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Room Booking Deleted Successfully.")

    except Exception as e:
        connection.rollback()
        print(f"Error: {e}")

    finally:
        connection.close()

def create_rooms_table():

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rooms(
                hotel_id INTEGER NOT NULL DEFAULT 1,
                room_number TEXT NOT NULL,
                room_type TEXT NOT NULL,
                room_price REAL NOT NULL,
                room_status TEXT NOT NULL,

                floor INTEGER,
                capacity INTEGER,
                amenities TEXT,
                description TEXT,

                housekeeping_status TEXT,
                maintenance_status TEXT,

                is_active INTEGER NOT NULL DEFAULT 1,

                created_at TEXT,
                updated_at TEXT,
                PRIMARY KEY (hotel_id, room_number)

            )
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def migrate_rooms_schema():

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("PRAGMA table_info(rooms)")
        existing_columns = {
            column["name"]
            for column in cursor.fetchall()
        }

        new_columns = {
            "hotel_id": "INTEGER NOT NULL DEFAULT 1",
            "floor": "INTEGER",
            "capacity": "INTEGER",
            "amenities": "TEXT",
            "description": "TEXT",
            "housekeeping_status": "TEXT",
            "maintenance_status": "TEXT",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
            "created_at": "TEXT",
            "updated_at": "TEXT"
        }

        for column_name, column_definition in new_columns.items():

            if column_name not in existing_columns:

                cursor.execute(
                    f"""
                    ALTER TABLE rooms
                    ADD COLUMN {column_name} {column_definition}
                    """
                )

        # Existing rooms ko enterprise defaults ke saath normalize karo.
        cursor.execute("""
            UPDATE rooms
            SET
                floor = CASE
                    WHEN floor IS NULL
                    THEN CAST(SUBSTR(room_number, 1, 1) AS INTEGER)
                    ELSE floor
                END,

                capacity = CASE
                    WHEN capacity IS NOT NULL THEN capacity
                    WHEN room_type = 'Standard' THEN 2
                    WHEN room_type = 'Deluxe' THEN 3
                    WHEN room_type = 'Suite' THEN 4
                    ELSE 2
                END,

                amenities = CASE
                    WHEN amenities IS NULL THEN ''
                    ELSE amenities
                END,

                description = CASE
                    WHEN description IS NULL THEN ''
                    ELSE description
                END,

                housekeeping_status = CASE
                    WHEN housekeeping_status IS NOT NULL
                        THEN housekeeping_status
                    WHEN room_status = 'Available'
                        THEN 'Clean'
                    ELSE 'Pending'
                END,

                maintenance_status = CASE
                    WHEN maintenance_status IS NULL
                        THEN 'Operational'
                    ELSE maintenance_status
                END,

                is_active = CASE
                    WHEN is_active IS NULL THEN 1
                    ELSE is_active
                END,

                created_at = CASE
                    WHEN created_at IS NULL
                        THEN CURRENT_TIMESTAMP
                    ELSE created_at
                END,

                updated_at = CASE
                    WHEN updated_at IS NULL
                        THEN CURRENT_TIMESTAMP
                    ELSE updated_at
                END
        """)

        # Old "Booked" status ko new Room Status architecture
        # ke compatible status me convert karo.
        cursor.execute("""
            UPDATE rooms
            SET room_status = 'Reserved'
            WHERE room_status = 'Booked'
        """)

                # -------------------------------------------------
        # Multi-Hotel Room Identity Migration
        # -------------------------------------------------
        cursor.execute("PRAGMA table_info(rooms)")

        room_columns = cursor.fetchall()

        room_number_is_primary_key = any(
            column["name"] == "room_number"
            and column["pk"] == 1
            for column in room_columns
        )

        if room_number_is_primary_key:

            cursor.execute("""
                CREATE TABLE rooms_new(

                    hotel_id INTEGER NOT NULL DEFAULT 1,
                    room_number TEXT NOT NULL,

                    room_type TEXT NOT NULL,
                    room_price REAL NOT NULL,
                    room_status TEXT NOT NULL,

                    floor INTEGER,
                    capacity INTEGER,
                    amenities TEXT,
                    description TEXT,

                    housekeeping_status TEXT,
                    maintenance_status TEXT,

                    is_active INTEGER NOT NULL DEFAULT 1,

                    created_at TEXT,
                    updated_at TEXT,

                    PRIMARY KEY (hotel_id, room_number)

                )
            """)

            cursor.execute("""
                INSERT INTO rooms_new(
                    hotel_id,
                    room_number,
                    room_type,
                    room_price,
                    room_status,
                    floor,
                    capacity,
                    amenities,
                    description,
                    housekeeping_status,
                    maintenance_status,
                    is_active,
                    created_at,
                    updated_at
                )
                SELECT
                    hotel_id,
                    room_number,
                    room_type,
                    room_price,
                    room_status,
                    floor,
                    capacity,
                    amenities,
                    description,
                    housekeeping_status,
                    maintenance_status,
                    is_active,
                    created_at,
                    updated_at
                FROM rooms
            """)

            cursor.execute("""
                DROP TABLE rooms
            """)

            cursor.execute("""
                ALTER TABLE rooms_new
                RENAME TO rooms
            """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def insert_default_rooms():

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        rooms = [
            ("101", "Standard", 1, 2, 1000, "WiFi, TV, AC", "Standard room suitable for comfortable guest stay."),
            ("102", "Standard", 1, 2, 1000, "WiFi, TV, AC", "Standard room suitable for comfortable guest stay."),
            ("103", "Standard", 1, 2, 1000, "WiFi, TV, AC", "Standard room suitable for comfortable guest stay."),
            ("201", "Deluxe", 2, 3, 1800, "WiFi, TV, AC, Mini Bar", "Deluxe room with enhanced guest facilities."),
            ("202", "Deluxe", 2, 3, 1800, "WiFi, TV, AC, Mini Bar", "Deluxe room with enhanced guest facilities."),
            ("203", "Deluxe", 2, 3, 1800, "WiFi, TV, AC, Mini Bar", "Deluxe room with enhanced guest facilities."),
            ("301", "Suite", 3, 4, 3000, "WiFi, TV, AC, Mini Bar, Living Area", "Premium suite with additional living space."),
            ("302", "Suite", 3, 4, 3000, "WiFi, TV, AC, Mini Bar, Living Area", "Premium suite with additional living space."),
        ]

        cursor.executemany(
            """
            INSERT OR IGNORE INTO rooms(
                hotel_id, room_number, room_type, floor, capacity,
                room_price, amenities, description, room_status,
                housekeeping_status, maintenance_status, is_active,
                created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'Available', 'Clean', 'Operational', 1,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            [
                (hotel_id, room_number, room_type, floor, capacity, price, amenities, description)
                for room_number, room_type, floor, capacity, price, amenities, description in rooms
            ]
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def view_rooms():

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        _reconcile_reserved_room_statuses(cursor, hotel_id)
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation view_rooms completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        cursor.execute(
            """
            SELECT *
            FROM rooms
            WHERE hotel_id = ?
            ORDER BY room_number
            """,
            (hotel_id,)
        )

        rooms = cursor.fetchall()

    finally:
        connection.close()

    print("=" * 65)
    print("                    HOTEL ROOMS")
    print("=" * 65)

    print(
        f"{'Room':<10}"
        f"{'Type':<15}"
        f"{'Price':<15}"
        f"{'Status':<15}"
    )

    print("-" * 65)

    for room in rooms:

        print(
            f"{room['room_number']:<10}"
            f"{room['room_type']:<15}"
            f"₹{room['room_price']:<14}"
            f"{room['room_status']:<15}"
        )

    print("=" * 65)

def check_room_available(room_number):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        _reconcile_reserved_room_statuses(cursor, hotel_id)
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation check_room_available completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        cursor.execute(
            """
            SELECT room_status, is_active
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room is None:
            return False

        return (
            room["is_active"] == 1
            and room["room_status"] == "Available"
        )

    finally:
        connection.close()

def get_all_rooms():

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        _reconcile_reserved_room_statuses(cursor, hotel_id)
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation get_all_rooms completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        cursor.execute(
            """
            SELECT *
            FROM rooms
            WHERE hotel_id = ?
            ORDER BY room_number
            """,
            (hotel_id,)
        )

        return cursor.fetchall()

    finally:
        connection.close()

def get_room_by_number(room_number):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        _reconcile_reserved_room_statuses(cursor, hotel_id)
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation get_room_by_number completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        cursor.execute(
            """
            SELECT *
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        return cursor.fetchone()

    finally:
        connection.close()

def release_room(room_number):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT room_status
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room is None:
            raise ValueError("Room not found.")

        if room["room_status"] not in (
            "Reserved",
            "Occupied"
        ):
            raise ValueError(
                "Room cannot be released from its current status."
            )

        cursor.execute(
            """
            UPDATE rooms
            SET
                room_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (
                "Available",
                hotel_id,
                room_number
            )
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()   

def is_room_booked(room_number):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT room_status
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room and room["room_status"] in (
            "Reserved",
            "Occupied"
        ):
            return True

        return False

    finally:
        connection.close()

def add_room(
    room_number,
    room_type,
    floor,
    capacity,
    room_price,
    amenities="",
    description=""
):
    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        existing_room = cursor.execute(
            """
            SELECT room_number
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        ).fetchone()

        if existing_room:
            raise ValueError("Room number already exists.")

        cursor.execute(
            """
            INSERT INTO rooms(
                hotel_id,
                room_number,
                room_type,
                floor,
                capacity,
                room_price,
                amenities,
                description,
                room_status,
                housekeeping_status,
                maintenance_status,
                is_active,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            (
                hotel_id,
                room_number,
                room_type,
                floor,
                capacity,
                room_price,
                amenities,
                description,
                "Available",
                "Clean",
                "Operational",
                1
            )
        )

        cursor.execute("""
            INSERT OR IGNORE INTO room_reservation_advance_rules(
                hotel_id, room_number, minimum_advance
            ) VALUES(?, ?, ?)
        """, (hotel_id, room_number, round(max(float(room_price) * 0.10, 0.01), 2)))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation add_room completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def update_room(
    room_number,
    room_type,
    floor,
    capacity,
    room_price,
    amenities="",
    description=""
):
    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            UPDATE rooms
            SET
                room_type = ?,
                floor = ?,
                capacity = ?,
                room_price = ?,
                amenities = ?,
                description = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (
                room_type,
                floor,
                capacity,
                room_price,
                amenities,
                description,
                hotel_id,
                room_number
            )
        )

        if cursor.rowcount != 1:
            raise ValueError("Room not found.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_room completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def set_room_active_status(room_number, is_active):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT room_status, is_active
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room is None:
            raise ValueError("Room not found.")

        if not is_active and room["room_status"] in ("Reserved", "Occupied"):
            raise ValueError(
                "Reserved or Occupied rooms cannot be deactivated."
            )

        cursor.execute(
            """
            UPDATE rooms
            SET
                is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (1 if is_active else 0, hotel_id, room_number)
        )

        if cursor.rowcount != 1:
            raise ValueError("Room active status could not be updated.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation set_room_active_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def get_active_rooms():

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        _reconcile_reserved_room_statuses(cursor, hotel_id)
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation get_active_rooms completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        cursor.execute(
            """
            SELECT *
            FROM rooms
            WHERE hotel_id = ?
            AND is_active = 1
            ORDER BY room_number
            """,
            (hotel_id,)
        )

        return cursor.fetchall()

    finally:
        connection.close()

def validate_room_status(room_status):
    if room_status not in ROOM_STATUSES:
        raise ValueError(
            f"Invalid room status. Allowed statuses: "
            f"{', '.join(ROOM_STATUSES)}"
        )

    return room_status

def validate_booking_status(booking_status):
    if booking_status not in BOOKING_STATUSES:
        raise ValueError(
            f"Invalid booking status. Allowed statuses: "
            f"{', '.join(BOOKING_STATUSES)}"
        )

    return booking_status


def validate_payment_status(payment_status):
    if payment_status not in PAYMENT_STATUSES:
        raise ValueError(
            f"Invalid payment status. Allowed statuses: "
            f"{', '.join(PAYMENT_STATUSES)}"
        )

    return payment_status

def update_room_status(room_number, new_status):

    validate_room_status(new_status)

    connection = get_connection()

    allowed_transitions = {
        "Available": {"Dirty", "Maintenance", "Out of Service"},
        "Reserved": {"Available", "Occupied"},
        "Occupied": {"Dirty"},
        "Dirty": {"Cleaning", "Maintenance", "Out of Service"},
        "Cleaning": {"Available", "Maintenance"},
        "Maintenance": {"Available", "Out of Service"},
        "Out of Service": {"Available"},
    }

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT room_status, maintenance_status
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room is None:
            raise ValueError("Room not found.")

        current_status = room["room_status"]

        if new_status == current_status:
            return

        if new_status not in allowed_transitions.get(current_status, set()):
            raise ValueError(
                f"Invalid room status transition: {current_status} -> {new_status}."
            )

        if new_status == "Available" and room["maintenance_status"] != "Operational":
            raise ValueError(
                "Room cannot become Available while maintenance is active."
            )

        cursor.execute(
            """
            UPDATE rooms
            SET room_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            AND room_status = ?
            """,
            (new_status, hotel_id, room_number, current_status)
        )

        if cursor.rowcount != 1:
            raise ValueError("Room status could not be updated.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation update_room_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def start_room_cleaning(room_number):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT
                room_status,
                housekeeping_status
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room is None:
            raise ValueError("Room not found.")

        if room["room_status"] != "Dirty":
            raise ValueError(
                "Only Dirty rooms can start cleaning."
            )

        cursor.execute(
            """
            UPDATE rooms
            SET
                room_status = 'Cleaning',
                housekeeping_status = 'In Progress',
                updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            AND room_status = 'Dirty'
            """,
            (hotel_id, room_number)
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "Room cleaning could not be started."
            )

        from database.cleaning_db import update_cleaning_task_status
        update_cleaning_task_status("ROOM", room_number, "Cleaning In Progress", hotel_id=hotel_id, connection=connection)

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation start_room_cleaning completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def complete_room_cleaning(room_number):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT
                room_status,
                housekeeping_status,
                maintenance_status
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room is None:
            raise ValueError("Room not found.")

        if room["room_status"] != "Cleaning":
            raise ValueError(
                "Only rooms currently being cleaned "
                "can be marked clean."
            )

        if room["maintenance_status"] != "Operational":
            raise ValueError(
                "Room has an active maintenance issue."
            )

        cursor.execute(
            """
            UPDATE rooms
            SET
                room_status = 'Available',
                housekeeping_status = 'Clean',
                updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            AND room_status = 'Cleaning'
            """,
            (hotel_id, room_number)
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "Room could not be marked clean."
            )

        from database.cleaning_db import update_cleaning_task_status
        update_cleaning_task_status("ROOM", room_number, "Completed", hotel_id=hotel_id, connection=connection)

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation complete_room_cleaning completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def mark_room_maintenance_required(room_number):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT room_status, maintenance_status
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room is None:
            raise ValueError("Room not found.")

        if room["room_status"] in ("Reserved", "Occupied"):
            raise ValueError(
                "Reserved or Occupied rooms cannot be sent to maintenance."
            )

        cursor.execute(
            """
            UPDATE rooms
            SET
                room_status = 'Maintenance',
                maintenance_status = 'Required',
                updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "Room maintenance status could not be updated."
            )

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation mark_room_maintenance_required completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def start_room_maintenance(room_number):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT room_status, maintenance_status
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room is None:
            raise ValueError("Room not found.")

        if room["room_status"] != "Maintenance":
            raise ValueError("Room is not in Maintenance status.")

        if room["maintenance_status"] != "Required":
            raise ValueError(
                "Room does not have a pending maintenance requirement."
            )

        cursor.execute(
            """
            UPDATE rooms
            SET
                maintenance_status = 'In Progress',
                updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            AND room_status = 'Maintenance'
            """,
            (hotel_id, room_number)
        )

        if cursor.rowcount != 1:
            raise ValueError("Maintenance could not be started.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation start_room_maintenance completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def complete_room_maintenance(room_number):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()

        cursor.execute(
            """
            SELECT room_status, maintenance_status
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room is None:
            raise ValueError("Room not found.")

        if room["room_status"] != "Maintenance":
            raise ValueError("Room is not in Maintenance status.")

        if room["maintenance_status"] != "In Progress":
            raise ValueError("Maintenance is not currently in progress.")

        cursor.execute(
            """
            UPDATE rooms
            SET
                room_status = 'Available',
                housekeeping_status = 'Clean',
                maintenance_status = 'Operational',
                updated_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
            AND room_number = ?
            AND room_status = 'Maintenance'
            """,
            (hotel_id, room_number)
        )

        if cursor.rowcount != 1:
            raise ValueError(
                "Room maintenance could not be completed."
            )

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Room Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation complete_room_maintenance completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def get_room_status(room_number):

    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        _reconcile_reserved_room_statuses(cursor, hotel_id)
        connection.commit()

        cursor.execute(
            """
            SELECT room_status
            FROM rooms
            WHERE hotel_id = ?
            AND room_number = ?
            """,
            (hotel_id, room_number)
        )

        room = cursor.fetchone()

        if room is None:
            return None

        return room["room_status"]

    finally:
        connection.close()

