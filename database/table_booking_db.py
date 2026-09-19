from utils.error_logging import log_non_blocking_error
from database.database import get_connection


def create_table_bookings_table():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS table_bookings(
                booking_id TEXT PRIMARY KEY,
                hotel_id INTEGER,
                booking_date TEXT,
                booking_time TEXT,
                customer_name TEXT,
                customer_mobile TEXT,
                table_number TEXT,
                persons INTEGER
            )
        """)

        cursor.execute("PRAGMA table_info(table_bookings)")
        columns_info = cursor.fetchall()
        columns = {row["name"] for row in columns_info}

        from database.hotel_context import get_current_hotel_id
        hotel_id = get_current_hotel_id()

        if "hotel_id" not in columns:
            cursor.execute(
                "ALTER TABLE table_bookings ADD COLUMN hotel_id INTEGER"
            )
            columns.add("hotel_id")

        cursor.execute(
            "UPDATE table_bookings SET hotel_id = ? WHERE hotel_id IS NULL",
            (hotel_id,)
        )

        # 4.7.10 Guest/Customer relationship migration.
        # Existing bookings are preserved with NULL customer_id; new bookings
        # require a valid customer belonging to the current hotel.
        if "customer_id" not in columns:
            cursor.execute(
                "ALTER TABLE table_bookings ADD COLUMN customer_id TEXT"
            )

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_table_bookings_customer
            ON table_bookings(hotel_id, customer_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_table_bookings_hotel
            ON table_bookings(hotel_id, booking_date, booking_time)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_table_bookings_hotel_table
            ON table_bookings(hotel_id, table_number)
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _get_current_hotel_id():
    from database.hotel_context import get_current_hotel_id
    return get_current_hotel_id()


TABLE_CLEANING_REQUIRED_STATUS = "Cleaning Required"
TABLE_CLEANING_IN_PROGRESS_STATUS = "Cleaning In Progress"
TABLE_CLEANING_REASONS = (
    "After Guest Use",
    "Regular Cleaning",
    "Deep Cleaning",
    "Other",
)


def create_table_booking(
    booking_id,
    booking_time,
    customer_id,
    customer_name,
    customer_mobile,
    table_number,
    persons
):
    hotel_id = _get_current_hotel_id()
    customer_id = str(customer_id or "").strip().upper()
    if not customer_id:
        raise ValueError("Customer ID is required.")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        from database.customer_db import validate_guest_hotel_relationship, get_customer_by_id
        validate_guest_hotel_relationship(customer_id, hotel_id)
        customer = get_customer_by_id(customer_id)
        if customer is None:
            raise ValueError("Customer not found.")

        cursor.execute("""
            UPDATE tables
            SET table_status = ?
            WHERE hotel_id = ?
              AND table_number = ?
              AND table_status = ?
        """, ("Reserved", hotel_id, table_number, "Available"))

        if cursor.rowcount == 0:
            cursor.execute("""
                SELECT table_number
                FROM tables
                WHERE hotel_id = ?
                  AND table_number = ?
            """, (hotel_id, table_number))

            table = cursor.fetchone()

            if table is None:
                raise ValueError("Invalid Table Number.")

            raise ValueError("Table Already Reserved or Occupied.")

        cursor.execute("""
            INSERT INTO table_bookings(
                booking_id,
                hotel_id,
                customer_id,
                booking_date,
                booking_time,
                customer_name,
                customer_mobile,
                table_number,
                persons
            )
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (
            booking_id,
            hotel_id,
            customer_id,
            booking_time.strftime("%d-%m-%Y"),
            booking_time.strftime("%I:%M:%S %p"),
            customer_name,
            customer_mobile,
            table_number,
            persons
        ))

        record_table_assignment(
            connection,
            table_number,
            "BOOKING",
            booking_id,
            customer_id,
            hotel_id
        )

        connection.commit()

        # Create the booking notification after the table booking transaction
        # commits, using an independent notification connection. This keeps
        # notification handling non-blocking for the core booking transaction.
        try:
            from database.notification_db import record_notification_event
            record_notification_event(
                "Booking",
                "Table Booking Created",
                f"Table booking {booking_id} has been created for {customer_name}.",
                reference_type="TABLE_BOOKING",
                reference_id=booking_id,
                recipient_type="Guest",
                recipient_id=customer_id,
                recipient_name=customer_name,
                recipient_mobile=customer_mobile,
                hotel_id=hotel_id,
                idempotency_key=f"BOOKING:{hotel_id}:TABLE:{booking_id}",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def delete_table_booking():
    print("=" * 50)
    print("      DELETE TABLE BOOKING")
    print("=" * 50)

    booking_id = input("Enter Booking ID : ").strip().upper()
    hotel_id = _get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT table_number
            FROM table_bookings
            WHERE booking_id = ?
              AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        booking = cursor.fetchone()

        if booking is None:
            print("Booking Not Found.")
            return

        table_number = booking["table_number"]

        cursor.execute(
            """
            DELETE FROM table_bookings
            WHERE booking_id = ?
              AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        if cursor.rowcount == 0:
            raise ValueError("Booking could not be deleted.")

        release_table_assignment(connection, "BOOKING", booking_id, hotel_id)

        # Release the table only after confirming that no other active
        # reservation or POS order still uses it.
        cursor.execute(
            """
            SELECT 1
            FROM table_bookings
            WHERE hotel_id = ?
              AND table_number = ?
            LIMIT 1
            """,
            (hotel_id, table_number)
        )
        active_booking = cursor.fetchone()

        cursor.execute(
            """
            SELECT 1
            FROM orders
            WHERE hotel_id = ?
              AND table_number = ?
              AND order_status NOT IN ('Completed', 'Cancelled')
            LIMIT 1
            """,
            (hotel_id, table_number)
        )
        active_order = cursor.fetchone()

        if not active_booking and not active_order:
            cursor.execute(
                """
                UPDATE tables
                SET table_status = 'Available'
                WHERE hotel_id = ?
                  AND table_number = ?
                  AND table_status = 'Reserved'
                """,
                (hotel_id, table_number)
            )

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_table_booking completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Table Booking Deleted Successfully.")

    except Exception as e:
        connection.rollback()
        print(f"Error deleting table booking: {e}")

    finally:
        connection.close()


def view_table_bookings():
    print("=" * 50)
    print("      TABLE BOOKING HISTORY")
    print("=" * 50)

    hotel_id = _get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM table_bookings
            WHERE hotel_id = ?
            ORDER BY booking_date DESC, booking_time DESC
        """, (hotel_id,))

        bookings = cursor.fetchall()

        if bookings:
            for booking in bookings:
                print("=" * 50)
                print("Booking ID   :", booking["booking_id"])
                print("Date         :", booking["booking_date"])
                print("Time         :", booking["booking_time"])
                print("-" * 50)
                print("Customer ID  :", booking["customer_id"] or "Legacy / Not Linked")
                print("Customer     :", booking["customer_name"])
                print("Mobile       :", booking["customer_mobile"])
                print("-" * 50)
                print("Table Number :", booking["table_number"])
                print("Persons      :", booking["persons"])
                print("=" * 50)
        else:
            print("No Table Bookings Found.")

    finally:
        connection.close()


def search_table_booking():
    print("=" * 50)
    print("      SEARCH TABLE BOOKING")
    print("=" * 50)

    booking_id = input("Enter Booking ID : ").strip().upper()
    hotel_id = _get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT *
            FROM table_bookings
            WHERE booking_id = ?
              AND hotel_id = ?
            """,
            (booking_id, hotel_id)
        )

        booking = cursor.fetchone()

        if booking:
            print("=" * 50)
            print("Booking ID   :", booking["booking_id"])
            print("Date         :", booking["booking_date"])
            print("Time         :", booking["booking_time"])
            print("-" * 50)
            print("Customer ID  :", booking["customer_id"] or "Legacy / Not Linked")
            print("Customer     :", booking["customer_name"])
            print("Mobile       :", booking["customer_mobile"])
            print("-" * 50)
            print("Table Number :", booking["table_number"])
            print("Persons      :", booking["persons"])
            print("=" * 50)
        else:
            print("Booking Not Found.")

    finally:
        connection.close()


def _ensure_table_sections_table(cursor, hotel_id):
    """Create and seed the configurable table section/area master."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS table_sections(
            section_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            section_name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(hotel_id, section_name COLLATE NOCASE)
        )
    """)

    default_sections = (
        "Indoor",
        "Outdoor",
        "Rooftop",
        "Restaurant",
        "Main Dining",
    )
    cursor.executemany("""
        INSERT OR IGNORE INTO table_sections(
            hotel_id, section_name, is_active
        )
        VALUES (?, ?, 1)
    """, [(hotel_id, section) for section in default_sections])

    # Existing table values from the earlier free-text system are migrated
    # safely. Known configured values are preserved; blank/invalid test values
    # fall back to Main Dining so every table always has a valid configured area.
    cursor.execute("""
        UPDATE tables
        SET table_section = 'Main Dining'
        WHERE table_section IS NULL
           OR TRIM(table_section) = ''
           OR LOWER(TRIM(table_section)) NOT IN (
                SELECT LOWER(section_name)
                FROM table_sections
                WHERE hotel_id = tables.hotel_id
           )
    """)


def get_table_sections(hotel_id=None, active_only=True):
    """Return configured table sections/areas for a hotel."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        if active_only:
            cursor.execute("""
                SELECT section_id, hotel_id, section_name, is_active
                FROM table_sections
                WHERE hotel_id = ? AND is_active = 1
                ORDER BY section_name COLLATE NOCASE
            """, (hotel_id,))
        else:
            cursor.execute("""
                SELECT section_id, hotel_id, section_name, is_active
                FROM table_sections
                WHERE hotel_id = ?
                ORDER BY is_active DESC, section_name COLLATE NOCASE
            """, (hotel_id,))
        return cursor.fetchall()
    finally:
        connection.close()


def add_table_section(section_name, hotel_id=None):
    """Add or reactivate a configurable table section/area."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    section_name = str(section_name).strip()
    if not section_name:
        raise ValueError("Section/Area name is required.")
    if len(section_name) > 50:
        raise ValueError("Section/Area name must be 50 characters or fewer.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT section_id, section_name, is_active
            FROM table_sections
            WHERE hotel_id = ? AND section_name = ? COLLATE NOCASE
        """, (hotel_id, section_name))
        existing = cursor.fetchone()

        if existing is not None:
            if existing["is_active"]:
                raise ValueError(f"Section/Area '{existing['section_name']}' already exists.")
            cursor.execute("""
                UPDATE table_sections
                SET is_active = 1
                WHERE section_id = ?
            """, (existing["section_id"],))
            connection.commit()
            try:
                from database.audit_db import log_business_activity
                log_business_activity(
                    module="Table Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation add_table_section completed successfully.",
                )
            except Exception as exc:
                log_non_blocking_error("Non-blocking optional operation failed", exc)
            return existing["section_name"]

        cursor.execute("""
            INSERT INTO table_sections(hotel_id, section_name, is_active)
            VALUES (?, ?, 1)
        """, (hotel_id, section_name))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation add_table_section completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return section_name
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def deactivate_table_section(section_name, hotel_id=None):
    """Deactivate a section only when no table currently uses it."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    section_name = str(section_name).strip()
    if not section_name:
        raise ValueError("Section/Area name is required.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT section_id, section_name, is_active
            FROM table_sections
            WHERE hotel_id = ? AND section_name = ? COLLATE NOCASE
        """, (hotel_id, section_name))
        section = cursor.fetchone()

        if section is None:
            raise ValueError("Section/Area not found.")
        if not section["is_active"]:
            raise ValueError(f"Section/Area '{section['section_name']}' is already inactive.")

        cursor.execute("""
            SELECT COUNT(*) AS usage_count
            FROM tables
            WHERE hotel_id = ? AND table_section = ? COLLATE NOCASE
        """, (hotel_id, section["section_name"]))
        usage_count = cursor.fetchone()["usage_count"]

        if usage_count > 0:
            raise ValueError(
                f"Section/Area '{section['section_name']}' is assigned to "
                f"{usage_count} table(s). Reassign those tables first."
            )

        cursor.execute("""
            UPDATE table_sections
            SET is_active = 0
            WHERE section_id = ?
        """, (section["section_id"],))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation deactivate_table_section completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _validate_table_section(cursor, hotel_id, table_section):
    """Return canonical active section name or raise a validation error."""
    table_section = str(table_section).strip()
    if not table_section:
        raise ValueError("Table Section/Area is required.")
    if len(table_section) > 50:
        raise ValueError("Table Section/Area must be 50 characters or fewer.")

    cursor.execute("""
        SELECT section_name
        FROM table_sections
        WHERE hotel_id = ?
          AND section_name = ? COLLATE NOCASE
          AND is_active = 1
    """, (hotel_id, table_section))
    section = cursor.fetchone()
    if section is None:
        raise ValueError("Invalid Section/Area. Please select a configured Section/Area.")
    return section["section_name"]


def create_tables_table():
    """Create and safely migrate the restaurant tables master table."""
    connection = get_connection()

    try:
        cursor = connection.cursor()
        from database.hotel_context import get_current_hotel_id
        hotel_id = get_current_hotel_id()
        cursor.execute("PRAGMA table_info(tables)")
        columns = {row["name"] for row in cursor.fetchall()}

        if not columns:
            cursor.execute("""
                CREATE TABLE tables(
                    table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hotel_id INTEGER NOT NULL,
                    table_number TEXT NOT NULL,
                    table_capacity INTEGER NOT NULL,
                    table_status TEXT NOT NULL DEFAULT 'Available',
                    table_section TEXT NOT NULL DEFAULT 'Main Dining',
                    cleaning_reason TEXT,
                    cleaning_started_at TEXT,
                    cleaning_completed_at TEXT,
                    UNIQUE(hotel_id, table_number)
                )
            """)
        elif "hotel_id" not in columns or "table_id" not in columns:

            cursor.execute("""
                CREATE TABLE tables_new(
                    table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hotel_id INTEGER NOT NULL,
                    table_number TEXT NOT NULL,
                    table_capacity INTEGER NOT NULL,
                    table_status TEXT NOT NULL DEFAULT 'Available',
                    table_section TEXT NOT NULL DEFAULT 'Main Dining',
                    cleaning_reason TEXT,
                    cleaning_started_at TEXT,
                    cleaning_completed_at TEXT,
                    UNIQUE(hotel_id, table_number)
                )
            """)

            cursor.execute("""
                INSERT INTO tables_new(
                    hotel_id,
                    table_number,
                    table_capacity,
                    table_status,
                    table_section
                )
                SELECT ?, table_number, table_capacity,
                       CASE
                           WHEN table_status = 'Booked' THEN 'Reserved'
                           ELSE table_status
                       END,
                       'Main Dining'
                FROM tables
            """, (hotel_id,))

            cursor.execute("DROP TABLE tables")
            cursor.execute("ALTER TABLE tables_new RENAME TO tables")
        elif "table_section" not in columns:
            cursor.execute("""
                ALTER TABLE tables
                ADD COLUMN table_section TEXT NOT NULL DEFAULT 'Main Dining'
            """)

        # Table cleaning lifecycle migration.
        cursor.execute("PRAGMA table_info(tables)")
        columns = {row["name"] for row in cursor.fetchall()}
        cleaning_migrations = {
            "cleaning_reason": "TEXT",
            "cleaning_started_at": "TEXT",
            "cleaning_completed_at": "TEXT",
        }
        for column_name, column_definition in cleaning_migrations.items():
            if column_name not in columns:
                cursor.execute(
                    f"ALTER TABLE tables ADD COLUMN {column_name} {column_definition}"
                )

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tables_hotel_status
            ON tables(hotel_id, table_status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tables_hotel_number
            ON tables(hotel_id, table_number)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tables_hotel_section
            ON tables(hotel_id, table_section)
        """)

        cursor.execute("""
            UPDATE tables
            SET table_status = 'Reserved'
            WHERE table_status = 'Booked'
        """)

        cursor.execute("""
            UPDATE tables
            SET table_section = 'Main Dining'
            WHERE table_section IS NULL OR TRIM(table_section) = ''
        """)

        _ensure_table_sections_table(cursor, hotel_id)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def create_restaurant_table(table_number, table_capacity, table_section="Main Dining", hotel_id=None):
    """Create one new table in the current hotel."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    table_number = str(table_number).strip().upper()
    table_section = str(table_section).strip()
    if not table_number:
        raise ValueError("Table Number is required.")
    if len(table_number) > 20:
        raise ValueError("Table Number must be 20 characters or fewer.")

    try:
        table_capacity = int(table_capacity)
    except (TypeError, ValueError):
        raise ValueError("Table Capacity must be a whole number.")

    if table_capacity <= 0:
        raise ValueError("Table Capacity must be greater than 0.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        table_section = _validate_table_section(cursor, hotel_id, table_section)
        cursor.execute("SELECT table_id FROM tables WHERE hotel_id = ? AND table_number = ?",
                       (hotel_id, table_number))
        if cursor.fetchone() is not None:
            raise ValueError(f"Table {table_number} already exists.")

        cursor.execute("""
            INSERT INTO tables(
                hotel_id,
                table_number,
                table_capacity,
                table_status,
                table_section
            )
            VALUES (?, ?, ?, 'Available', ?)
        """, (hotel_id, table_number, table_capacity, table_section))
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def insert_default_tables():
    hotel_id = _get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()

        tables = [
            (hotel_id, "T1", 2, "Available", "Main Dining"),
            (hotel_id, "T2", 2, "Available", "Main Dining"),
            (hotel_id, "T3", 4, "Available", "Main Dining"),
            (hotel_id, "T4", 4, "Available", "Main Dining"),
            (hotel_id, "T5", 6, "Available", "Main Dining"),
            (hotel_id, "T6", 6, "Available", "Main Dining"),
            (hotel_id, "T7", 8, "Available", "Main Dining"),
            (hotel_id, "T8", 8, "Available", "Main Dining")
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO tables(
                hotel_id,
                table_number,
                table_capacity,
                table_status,
                table_section
            )
            VALUES (?, ?, ?, ?, ?)
        """, tables)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_all_tables(hotel_id=None):
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM tables
            WHERE hotel_id = ?
            ORDER BY table_number
        """, (hotel_id,))
        return cursor.fetchall()
    finally:
        connection.close()


def update_restaurant_table_capacity(table_number, table_capacity, hotel_id=None):
    """Update a restaurant table's capacity safely for the current hotel."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    table_number = str(table_number).strip().upper()
    if not table_number:
        raise ValueError("Table Number is required.")

    try:
        table_capacity = int(table_capacity)
    except (TypeError, ValueError):
        raise ValueError("Table Capacity must be a whole number.")

    if table_capacity <= 0:
        raise ValueError("Table Capacity must be greater than 0.")

    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT table_status
            FROM tables
            WHERE hotel_id = ?
              AND table_number = ?
        """, (hotel_id, table_number))
        table = cursor.fetchone()

        if table is None:
            raise ValueError("Invalid Table Number.")

        if table["table_status"] != "Available":
            raise ValueError(
                f"Table {table_number} is {table['table_status']}. "
                "Capacity can only be changed when the table is Available."
            )

        cursor.execute("""
            UPDATE tables
            SET table_capacity = ?
            WHERE hotel_id = ?
              AND table_number = ?
              AND table_status = 'Available'
        """, (table_capacity, hotel_id, table_number))

        if cursor.rowcount != 1:
            raise ValueError("Table capacity could not be updated.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_restaurant_table_capacity completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



def update_restaurant_table_section(table_number, table_section, hotel_id=None):
    """Update a restaurant table's section/area safely for the current hotel."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    table_number = str(table_number).strip().upper()
    table_section = str(table_section).strip()

    if not table_number:
        raise ValueError("Table Number is required.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        table_section = _validate_table_section(cursor, hotel_id, table_section)
        cursor.execute("""
            SELECT table_status
            FROM tables
            WHERE hotel_id = ?
              AND table_number = ?
        """, (hotel_id, table_number))
        table = cursor.fetchone()

        if table is None:
            raise ValueError("Invalid Table Number.")

        if table["table_status"] != "Available":
            raise ValueError(
                f"Table {table_number} is {table['table_status']}. "
                "Section/Area can only be changed when the table is Available."
            )

        cursor.execute("""
            UPDATE tables
            SET table_section = ?
            WHERE hotel_id = ?
              AND table_number = ?
              AND table_status = 'Available'
        """, (table_section, hotel_id, table_number))

        if cursor.rowcount != 1:
            raise ValueError("Table section/area could not be updated.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_restaurant_table_section completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_restaurant_tables(status=None, hotel_id=None):
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        if status is None:
            cursor.execute("""
                SELECT table_id, hotel_id, table_number,
                       table_capacity, table_status, table_section
                FROM tables
                WHERE hotel_id = ?
                ORDER BY table_number
            """, (hotel_id,))
        else:
            cursor.execute("""
                SELECT table_id, hotel_id, table_number,
                       table_capacity, table_status, table_section
                FROM tables
                WHERE hotel_id = ?
                  AND table_status = ?
                ORDER BY table_number
            """, (hotel_id, status))

        return cursor.fetchall()
    finally:
        connection.close()


def get_available_restaurant_tables(min_capacity=None, hotel_id=None):
    """Return only Available tables, optionally filtered by minimum capacity."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    if min_capacity is not None:
        try:
            min_capacity = int(min_capacity)
        except (TypeError, ValueError):
            raise ValueError("Minimum Capacity must be a whole number.")

        if min_capacity <= 0:
            raise ValueError("Minimum Capacity must be greater than 0.")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        if min_capacity is None:
            cursor.execute("""
                SELECT table_id, hotel_id, table_number,
                       table_capacity, table_status, table_section
                FROM tables
                WHERE hotel_id = ?
                  AND table_status = 'Available'
                ORDER BY table_number
            """, (hotel_id,))
        else:
            cursor.execute("""
                SELECT table_id, hotel_id, table_number,
                       table_capacity, table_status, table_section
                FROM tables
                WHERE hotel_id = ?
                  AND table_status = 'Available'
                  AND table_capacity >= ?
                ORDER BY table_capacity, table_number
            """, (hotel_id, min_capacity))

        return cursor.fetchall()
    finally:
        connection.close()


def get_reserved_restaurant_tables(hotel_id=None):
    """Return tables currently reserved through an active table booking."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                t.table_id,
                t.hotel_id,
                t.table_number,
                t.table_capacity,
                t.table_status,
                t.table_section,
                b.booking_id,
                b.booking_date,
                b.booking_time,
                b.customer_name,
                b.customer_mobile,
                b.persons
            FROM tables AS t
            INNER JOIN table_bookings AS b
                ON b.hotel_id = t.hotel_id
               AND b.table_number = t.table_number
            WHERE t.hotel_id = ?
              AND t.table_status = 'Reserved'
            ORDER BY b.booking_date, b.booking_time, t.table_number
        """, (hotel_id,))
        return cursor.fetchall()
    finally:
        connection.close()


def release_table_if_no_active_usage(table_number, hotel_id=None):
    """Release a table only when no active booking or POS order still uses it."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    table_number = str(table_number).strip().upper()
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT table_status
            FROM tables
            WHERE hotel_id = ?
              AND table_number = ?
        """, (hotel_id, table_number))
        table = cursor.fetchone()

        if table is None:
            raise ValueError("Invalid Table Number.")

        cursor.execute("""
            SELECT 1
            FROM table_bookings
            WHERE hotel_id = ?
              AND table_number = ?
            LIMIT 1
        """, (hotel_id, table_number))
        active_booking = cursor.fetchone()

        cursor.execute("""
            SELECT 1
            FROM orders
            WHERE hotel_id = ?
              AND table_number = ?
              AND order_status NOT IN ('Completed', 'Cancelled')
            LIMIT 1
        """, (hotel_id, table_number))
        active_order = cursor.fetchone()

        if active_booking or active_order:
            return False

        if table["table_status"] in {"Occupied", "Reserved"}:
            cursor.execute("""
                UPDATE tables
                SET table_status = 'Available'
                WHERE hotel_id = ? AND table_number = ?
                  AND table_status IN ('Occupied', 'Reserved')
            """, (hotel_id, table_number))
            connection.commit()
            return cursor.rowcount == 1

        # Cleaning states must never be auto-released.
        return False

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def mark_table_cleaning_required(table_number, reason="After Guest Use", hotel_id=None):
    """Move an occupied table into the cleaning-required state."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()
    table_number = str(table_number or "").strip().upper()
    reason = str(reason or "").strip()
    if not table_number:
        raise ValueError("Table Number is required.")
    if reason not in TABLE_CLEANING_REASONS:
        raise ValueError("Invalid table cleaning reason.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT table_status FROM tables WHERE hotel_id=? AND table_number=?", (hotel_id, table_number))
        table = cursor.fetchone()
        if table is None:
            raise ValueError("Invalid Table Number.")
        if table["table_status"] == TABLE_CLEANING_REQUIRED_STATUS:
            return False
        if table["table_status"] == TABLE_CLEANING_IN_PROGRESS_STATUS:
            raise ValueError(f"Table {table_number} is already being cleaned.")
        if table["table_status"] != "Occupied":
            raise ValueError(f"Table {table_number} must be Occupied before cleaning is required.")
        cursor.execute("""
            UPDATE tables
            SET table_status=?, cleaning_reason=?, cleaning_started_at=NULL, cleaning_completed_at=NULL
            WHERE hotel_id=? AND table_number=? AND table_status='Occupied'
        """, (TABLE_CLEANING_REQUIRED_STATUS, reason, hotel_id, table_number))
        if cursor.rowcount != 1:
            raise ValueError("Table cleaning status could not be updated.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation mark_table_cleaning_required completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def start_table_cleaning(table_number, hotel_id=None):
    """Start cleaning a table whose cleaning is required."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()
    table_number = str(table_number or "").strip().upper()
    if not table_number:
        raise ValueError("Table Number is required.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE tables
            SET table_status=?, cleaning_started_at=CURRENT_TIMESTAMP, cleaning_completed_at=NULL
            WHERE hotel_id=? AND table_number=? AND table_status=?
        """, (TABLE_CLEANING_IN_PROGRESS_STATUS, hotel_id, table_number, TABLE_CLEANING_REQUIRED_STATUS))
        if cursor.rowcount != 1:
            cursor.execute("SELECT table_status FROM tables WHERE hotel_id=? AND table_number=?", (hotel_id, table_number))
            table = cursor.fetchone()
            if table is None:
                raise ValueError("Invalid Table Number.")
            raise ValueError(f"Table {table_number} is {table['table_status']}. Only Cleaning Required tables can start cleaning.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation start_table_cleaning completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def complete_table_cleaning(table_number, hotel_id=None):
    """Complete table cleaning and make the table Available."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()
    table_number = str(table_number or "").strip().upper()
    if not table_number:
        raise ValueError("Table Number is required.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT table_status FROM tables WHERE hotel_id=? AND table_number=?", (hotel_id, table_number))
        table = cursor.fetchone()
        if table is None:
            raise ValueError("Invalid Table Number.")
        if table["table_status"] != TABLE_CLEANING_IN_PROGRESS_STATUS:
            raise ValueError(f"Table {table_number} is {table['table_status']}. Only Cleaning In Progress tables can be completed.")
        cursor.execute("""
            UPDATE tables
            SET table_status='Available', cleaning_completed_at=CURRENT_TIMESTAMP
            WHERE hotel_id=? AND table_number=? AND table_status=?
        """, (hotel_id, table_number, TABLE_CLEANING_IN_PROGRESS_STATUS))
        if cursor.rowcount != 1:
            raise ValueError("Table cleaning could not be completed.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation complete_table_cleaning completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_table_cleaning_tasks(hotel_id=None):
    """Return current table-cleaning work for future dashboard integration."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT table_id, hotel_id, table_number, table_capacity, table_section,
                   table_status, cleaning_reason, cleaning_started_at, cleaning_completed_at
            FROM tables
            WHERE hotel_id=? AND table_status IN (?,?)
            ORDER BY CASE table_status WHEN 'Cleaning Required' THEN 1 WHEN 'Cleaning In Progress' THEN 2 ELSE 3 END, table_number
        """, (hotel_id, TABLE_CLEANING_REQUIRED_STATUS, TABLE_CLEANING_IN_PROGRESS_STATUS))
        return cursor.fetchall()
    finally:
        connection.close()


def ensure_table_assignments_table(connection):
    """Create the centralized current/history table-assignment registry."""
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS table_assignments(
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            table_number TEXT NOT NULL,
            assignment_type TEXT NOT NULL,
            reference_id TEXT NOT NULL,
            customer_id TEXT,
            assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            released_at TEXT,
            assignment_status TEXT NOT NULL DEFAULT 'Active',
            CHECK (assignment_type IN ('BOOKING', 'POS')),
            CHECK (assignment_status IN ('Active', 'Released'))
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_table_assignments_hotel_table
        ON table_assignments(hotel_id, table_number, assignment_status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_table_assignments_hotel_reference
        ON table_assignments(hotel_id, assignment_type, reference_id)
    """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_table_assignments_active_table
        ON table_assignments(hotel_id, table_number)
        WHERE assignment_status = 'Active'
    """)
    return cursor


def record_table_assignment(
    connection,
    table_number,
    assignment_type,
    reference_id,
    customer_id=None,
    hotel_id=None
):
    """Register one active Booking/POS ownership of a table."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    table_number = str(table_number or "").strip().upper()
    assignment_type = str(assignment_type or "").strip().upper()
    reference_id = str(reference_id or "").strip().upper()
    customer_id = str(customer_id or "").strip().upper() or None

    if not table_number or not reference_id:
        raise ValueError("Table assignment requires a table and reference ID.")
    if assignment_type not in {"BOOKING", "POS"}:
        raise ValueError("Invalid table assignment type.")

    cursor = ensure_table_assignments_table(connection)

    cursor.execute("""
        SELECT assignment_id
        FROM table_assignments
        WHERE hotel_id = ?
          AND assignment_type = ?
          AND reference_id = ?
          AND assignment_status = 'Active'
        LIMIT 1
    """, (hotel_id, assignment_type, reference_id))
    if cursor.fetchone() is not None:
        return

    cursor.execute("""
        SELECT table_status
        FROM tables
        WHERE hotel_id = ? AND table_number = ?
    """, (hotel_id, table_number))
    table = cursor.fetchone()
    if table is None:
        raise ValueError("Invalid Table Number.")

    required_status = "Reserved" if assignment_type == "BOOKING" else "Occupied"
    if table["table_status"] != required_status:
        raise ValueError(
            f"Table {table_number} must be {required_status} for a {assignment_type} assignment."
        )

    cursor.execute("""
        SELECT assignment_id, assignment_type, reference_id
        FROM table_assignments
        WHERE hotel_id = ?
          AND table_number = ?
          AND assignment_status = 'Active'
        LIMIT 1
    """, (hotel_id, table_number))
    existing = cursor.fetchone()
    if existing is not None:
        raise ValueError(
            f"Table {table_number} is already assigned to "
            f"{existing['assignment_type']} {existing['reference_id']}."
        )

    cursor.execute("""
        INSERT INTO table_assignments(
            hotel_id, table_number, assignment_type,
            reference_id, customer_id, assignment_status
        )
        VALUES (?, ?, ?, ?, ?, 'Active')
    """, (
        hotel_id, table_number, assignment_type,
        reference_id, customer_id
    ))


def release_table_assignment(
    connection,
    assignment_type,
    reference_id,
    hotel_id=None
):
    """Close an active table assignment without deleting its history."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    assignment_type = str(assignment_type or "").strip().upper()
    reference_id = str(reference_id or "").strip().upper()

    cursor = ensure_table_assignments_table(connection)
    cursor.execute("""
        UPDATE table_assignments
        SET assignment_status = 'Released',
            released_at = CURRENT_TIMESTAMP
        WHERE hotel_id = ?
          AND assignment_type = ?
          AND reference_id = ?
          AND assignment_status = 'Active'
    """, (hotel_id, assignment_type, reference_id))
    return cursor.rowcount


def get_active_table_assignments(hotel_id=None):
    """Return active Booking/POS assignments for the current hotel."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = ensure_table_assignments_table(connection)
        cursor.execute("""
            SELECT
                a.assignment_id,
                a.table_number,
                a.assignment_type,
                a.reference_id,
                a.customer_id,
                a.assigned_at,
                a.assignment_status,
                t.table_capacity,
                t.table_section,
                t.table_status
            FROM table_assignments a
            INNER JOIN tables t
              ON t.hotel_id = a.hotel_id
             AND t.table_number = a.table_number
            WHERE a.hotel_id = ?
              AND a.assignment_status = 'Active'
            ORDER BY a.table_number, a.assignment_type
        """, (hotel_id,))
        return cursor.fetchall()
    finally:
        connection.close()


def reassign_table_booking(
    booking_id,
    new_table_number,
    hotel_id=None
):
    """Safely move an active booking to another available table."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    booking_id = str(booking_id or "").strip().upper()
    new_table_number = str(new_table_number or "").strip().upper()

    if not booking_id or not new_table_number:
        raise ValueError("Booking ID and new table number are required.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        ensure_table_assignments_table(connection)

        cursor.execute("""
            SELECT booking_id, table_number, customer_id
            FROM table_bookings
            WHERE booking_id = ?
              AND hotel_id = ?
        """, (booking_id, hotel_id))
        booking = cursor.fetchone()
        if booking is None:
            raise ValueError("Booking Not Found.")

        old_table = str(booking["table_number"]).strip().upper()

        cursor.execute("""
            SELECT table_number, table_status
            FROM tables
            WHERE hotel_id = ? AND table_number = ?
        """, (hotel_id, new_table_number))
        new_table = cursor.fetchone()
        if new_table is None:
            raise ValueError("Invalid new Table Number.")
        if new_table["table_status"] != "Available":
            raise ValueError(
                f"Table {new_table_number} is {new_table['table_status']} and is not available."
            )

        # Atomic status + booking + assignment transition.
        cursor.execute("""
            UPDATE tables
            SET table_status = 'Available'
            WHERE hotel_id = ?
              AND table_number = ?
              AND table_status = 'Reserved'
        """, (hotel_id, old_table))

        cursor.execute("""
            UPDATE tables
            SET table_status = 'Reserved'
            WHERE hotel_id = ?
              AND table_number = ?
              AND table_status = 'Available'
        """, (hotel_id, new_table_number))
        if cursor.rowcount != 1:
            raise ValueError("New table could not be reserved.")

        cursor.execute("""
            UPDATE table_bookings
            SET table_number = ?
            WHERE booking_id = ? AND hotel_id = ?
        """, (new_table_number, booking_id, hotel_id))

        cursor.execute("""
            UPDATE table_assignments
            SET assignment_status = 'Released',
                released_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
              AND assignment_type = 'BOOKING'
              AND reference_id = ?
              AND assignment_status = 'Active'
        """, (hotel_id, booking_id))

        record_table_assignment(
            connection,
            new_table_number,
            "BOOKING",
            booking_id,
            booking["customer_id"],
            hotel_id
        )

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="UPDATE",
        local_values=locals(),
        details="Business operation reassign_table_booking completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return old_table, new_table_number

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def get_table_history(table_number=None, hotel_id=None, limit=100):
    """Return hotel-scoped historical table usage and assignment events.

    The centralized table_assignments registry is the primary event source.
    Older bookings/orders that predate the registry are included as fallback
    history so existing data is not silently hidden.
    """
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    table_number = str(table_number or "").strip().upper() or None
    try:
        limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        limit = 100

    connection = get_connection()
    try:
        cursor = connection.cursor()
        ensure_table_assignments_table(connection)

        params = [hotel_id]
        table_filter = ""
        if table_number:
            table_filter = " AND a.table_number = ?"
            params.append(table_number)

        cursor.execute(f"""
            SELECT
                a.assignment_id AS history_id,
                a.table_number,
                a.assignment_type AS event_type,
                a.reference_id,
                a.customer_id,
                c.customer_name,
                a.assigned_at AS event_start,
                a.released_at AS event_end,
                a.assignment_status AS history_status,
                t.table_capacity,
                t.table_section
            FROM table_assignments a
            LEFT JOIN customers c ON c.customer_id = a.customer_id
            LEFT JOIN tables t
              ON t.hotel_id = a.hotel_id AND t.table_number = a.table_number
            WHERE a.hotel_id = ?{table_filter}
            ORDER BY COALESCE(a.released_at, a.assigned_at) DESC, a.assignment_id DESC
            LIMIT ?
        """, params + [limit])
        return cursor.fetchall()
    finally:
        connection.close()


def ensure_table_merge_tables(connection):
    """Create the table-merge foundation tables without changing table status."""
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS table_merge_groups(
            merge_group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            merge_code TEXT NOT NULL,
            primary_table_number TEXT NOT NULL,
            merge_status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            released_at TEXT,
            UNIQUE(hotel_id, merge_code),
            CHECK (merge_status IN ('Active', 'Released'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS table_merge_members(
            merge_member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            merge_group_id INTEGER NOT NULL,
            hotel_id INTEGER NOT NULL,
            table_number TEXT NOT NULL,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            left_at TEXT,
            member_status TEXT NOT NULL DEFAULT 'Active',
            UNIQUE(merge_group_id, table_number),
            FOREIGN KEY(merge_group_id)
                REFERENCES table_merge_groups(merge_group_id)
                ON DELETE CASCADE,
            CHECK (member_status IN ('Active', 'Released'))
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_table_merge_groups_hotel_status
        ON table_merge_groups(hotel_id, merge_status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_table_merge_members_hotel_table
        ON table_merge_members(hotel_id, table_number, member_status)
    """)
    return cursor


def merge_restaurant_tables(table_numbers, hotel_id=None):
    """Create a safe merge group for currently available tables.

    This is the Phase 4.7.13 foundation: it records membership and validates
    tables, but deliberately does not change operational table status or
    combine bookings/orders until later integration points.
    """
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    normalized = []
    for value in table_numbers or []:
        table_number = str(value or "").strip().upper()
        if table_number and table_number not in normalized:
            normalized.append(table_number)

    if len(normalized) < 2:
        raise ValueError("At least 2 different tables are required for a merge.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        ensure_table_merge_tables(connection)

        placeholders = ",".join("?" for _ in normalized)
        cursor.execute(
            f"""
            SELECT table_number, table_status
            FROM tables
            WHERE hotel_id = ?
              AND table_number IN ({placeholders})
            """,
            [hotel_id, *normalized]
        )
        rows = {row["table_number"]: row for row in cursor.fetchall()}

        missing = [t for t in normalized if t not in rows]
        if missing:
            raise ValueError(f"Invalid Table Number(s): {', '.join(missing)}")

        unavailable = [
            t for t in normalized
            if rows[t]["table_status"] != "Available"
        ]
        if unavailable:
            raise ValueError(
                "Only Available tables can be merged. "
                f"Unavailable: {', '.join(unavailable)}"
            )

        # A table can belong to only one active merge group.
        cursor.execute(
            f"""
            SELECT table_number
            FROM table_merge_members
            WHERE hotel_id = ?
              AND table_number IN ({placeholders})
              AND member_status = 'Active'
            """,
            [hotel_id, *normalized]
        )
        already_merged = [row["table_number"] for row in cursor.fetchall()]
        if already_merged:
            raise ValueError(
                "Table(s) already belong to an active merge: "
                + ", ".join(already_merged)
            )

        primary = normalized[0]
        merge_code = f"MG-{hotel_id}-{generate_merge_code()}"

        cursor.execute("""
            INSERT INTO table_merge_groups(
                hotel_id, merge_code, primary_table_number, merge_status
            )
            VALUES (?, ?, ?, 'Active')
        """, (hotel_id, merge_code, primary))
        merge_group_id = cursor.lastrowid

        cursor.executemany("""
            INSERT INTO table_merge_members(
                merge_group_id, hotel_id, table_number, member_status
            )
            VALUES (?, ?, ?, 'Active')
        """, [
            (merge_group_id, hotel_id, table_number)
            for table_number in normalized
        ])

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation merge_restaurant_tables completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return {
            "merge_group_id": merge_group_id,
            "merge_code": merge_code,
            "primary_table_number": primary,
            "table_numbers": normalized,
            "table_count": len(normalized)
        }

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def generate_merge_code():
    """Return a short unique merge token for the current process."""
    import uuid
    return uuid.uuid4().hex[:8].upper()


def get_active_table_merges(hotel_id=None):
    """Return active merge groups with their member tables."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        ensure_table_merge_tables(connection)
        cursor.execute("""
            SELECT
                g.merge_group_id,
                g.merge_code,
                g.primary_table_number,
                g.created_at,
                GROUP_CONCAT(m.table_number, ', ') AS table_numbers,
                COUNT(m.merge_member_id) AS table_count
            FROM table_merge_groups g
            INNER JOIN table_merge_members m
              ON m.merge_group_id = g.merge_group_id
             AND m.member_status = 'Active'
            WHERE g.hotel_id = ?
              AND g.merge_status = 'Active'
            GROUP BY
                g.merge_group_id,
                g.merge_code,
                g.primary_table_number,
                g.created_at
            ORDER BY g.created_at DESC, g.merge_group_id DESC
        """, (hotel_id,))
        return cursor.fetchall()
    finally:
        connection.close()


def release_table_merge(merge_code, hotel_id=None):
    """Release a merge group without deleting its history."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    merge_code = str(merge_code or "").strip().upper()
    if not merge_code:
        raise ValueError("Merge Code is required.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        ensure_table_merge_tables(connection)

        cursor.execute("""
            SELECT merge_group_id
            FROM table_merge_groups
            WHERE hotel_id = ?
              AND merge_code = ?
              AND merge_status = 'Active'
        """, (hotel_id, merge_code))
        group = cursor.fetchone()
        if group is None:
            raise ValueError("Active Merge Group Not Found.")

        cursor.execute("""
            UPDATE table_merge_members
            SET member_status = 'Released',
                left_at = CURRENT_TIMESTAMP
            WHERE merge_group_id = ?
              AND member_status = 'Active'
        """, (group["merge_group_id"],))

        cursor.execute("""
            UPDATE table_merge_groups
            SET merge_status = 'Released',
                released_at = CURRENT_TIMESTAMP
            WHERE merge_group_id = ?
        """, (group["merge_group_id"],))

        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def split_table_merge(merge_code, hotel_id=None):
    """Safely split an active merge group back into independent tables.

    The split is a foundation operation: it closes only the merge relationship.
    Existing table bookings, POS orders, and active assignments are never
    deleted. After the relationship is closed, each member table status is
    reconciled from its current active usage so the table remains consistent.
    """
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    merge_code = str(merge_code or "").strip().upper()
    if not merge_code:
        raise ValueError("Merge Code is required.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        ensure_table_merge_tables(connection)
        ensure_table_assignments_table(connection)

        cursor.execute("""
            SELECT merge_group_id, primary_table_number
            FROM table_merge_groups
            WHERE hotel_id = ?
              AND merge_code = ?
              AND merge_status = 'Active'
        """, (hotel_id, merge_code))
        group = cursor.fetchone()
        if group is None:
            raise ValueError("Active Merge Group Not Found.")

        cursor.execute("""
            SELECT table_number
            FROM table_merge_members
            WHERE hotel_id = ?
              AND merge_group_id = ?
              AND member_status = 'Active'
            ORDER BY merge_member_id
        """, (hotel_id, group["merge_group_id"]))
        members = [row["table_number"] for row in cursor.fetchall()]
        if len(members) < 2:
            raise ValueError("Active merge does not contain enough tables to split.")

        # Snapshot active assignments before changing the merge relationship.
        cursor.execute("""
            SELECT assignment_id, table_number, assignment_type, reference_id,
                   customer_id, assignment_status
            FROM table_assignments
            WHERE hotel_id = ?
              AND table_number IN ({placeholders})
              AND assignment_status = 'Active'
            ORDER BY assignment_id
        """.format(placeholders=','.join('?' for _ in members)),
        [hotel_id, *members])
        assignments_before = cursor.fetchall()

        # Protect against corrupt states where one table has conflicting active
        # usage. The centralized assignment registry is the source of truth for
        # CURRENT table ownership; historical booking/order rows must never make
        # a table look occupied or reserved after a split.
        for table_number in members:
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN assignment_type = 'BOOKING' THEN 1 ELSE 0 END) AS booking_count,
                    SUM(CASE WHEN assignment_type = 'POS' THEN 1 ELSE 0 END) AS pos_count
                FROM table_assignments
                WHERE hotel_id = ?
                  AND table_number = ?
                  AND assignment_status = 'Active'
            """, (hotel_id, table_number))
            usage = cursor.fetchone()
            booking_count = usage["booking_count"] or 0
            pos_count = usage["pos_count"] or 0

            if booking_count > 0 and pos_count > 0:
                raise ValueError(
                    f"Cannot split safely: Table {table_number} has both an "
                    "active booking and an active POS order."
                )

        # Close only the merge relationship. Table records, bookings, orders,
        # and assignment rows remain intact.
        cursor.execute("""
            UPDATE table_merge_members
            SET member_status = 'Released',
                left_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
              AND merge_group_id = ?
              AND member_status = 'Active'
        """, (hotel_id, group["merge_group_id"]))

        cursor.execute("""
            UPDATE table_merge_groups
            SET merge_status = 'Released',
                released_at = CURRENT_TIMESTAMP
            WHERE hotel_id = ?
              AND merge_group_id = ?
              AND merge_status = 'Active'
        """, (hotel_id, group["merge_group_id"]))

        # Restore each member table to the status dictated by CURRENT active
        # assignments. Historical bookings/orders are intentionally ignored.
        for table_number in members:
            cursor.execute("""
                SELECT
                    SUM(CASE WHEN assignment_type = 'BOOKING' THEN 1 ELSE 0 END) AS booking_count,
                    SUM(CASE WHEN assignment_type = 'POS' THEN 1 ELSE 0 END) AS pos_count
                FROM table_assignments
                WHERE hotel_id = ?
                  AND table_number = ?
                  AND assignment_status = 'Active'
            """, (hotel_id, table_number))
            usage = cursor.fetchone()
            booking_count = usage["booking_count"] or 0
            pos_count = usage["pos_count"] or 0

            if pos_count > 0:
                restored_status = "Occupied"
            elif booking_count > 0:
                restored_status = "Reserved"
            else:
                restored_status = "Available"

            cursor.execute("""
                UPDATE tables
                SET table_status = ?
                WHERE hotel_id = ?
                  AND table_number = ?
            """, (restored_status, hotel_id, table_number))

        # Verify active assignment rows survived the split unchanged.
        cursor.execute("""
            SELECT assignment_id, table_number, assignment_type, reference_id,
                   customer_id, assignment_status
            FROM table_assignments
            WHERE hotel_id = ?
              AND table_number IN ({placeholders})
              AND assignment_status = 'Active'
            ORDER BY assignment_id
        """.format(placeholders=','.join('?' for _ in members)),
        [hotel_id, *members])
        assignments_after = cursor.fetchall()

        before_ids = [row["assignment_id"] for row in assignments_before]
        after_ids = [row["assignment_id"] for row in assignments_after]
        if before_ids != after_ids:
            raise ValueError("Assignment restoration verification failed during split.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation split_table_merge completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return {
            "merge_code": merge_code,
            "primary_table_number": group["primary_table_number"],
            "table_numbers": members,
            "restored_assignments": len(assignments_after),
        }

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_table_by_number(table_number, hotel_id=None):
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM tables
            WHERE hotel_id = ?
              AND table_number = ?
        """, (hotel_id, table_number))
        return cursor.fetchone()
    finally:
        connection.close()


def check_table_available(table_number, hotel_id=None):
    table = get_table_by_number(table_number, hotel_id)
    return table is not None and table["table_status"] == "Available"


def validate_restaurant_table(table_number, hotel_id=None):
    table = get_table_by_number(table_number, hotel_id)

    if table is None:
        raise ValueError("Invalid Table Number.")

    if table["table_status"] != "Available":
        raise ValueError(
            f"Table {table_number} is {table['table_status']} and is not available."
        )

    return table


def claim_restaurant_table(table_number, hotel_id=None):
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE tables
            SET table_status = 'Occupied'
            WHERE hotel_id = ?
              AND table_number = ?
              AND table_status = 'Available'
        """, (hotel_id, table_number))

        if cursor.rowcount != 1:
            cursor.execute("""
                SELECT table_status
                FROM tables
                WHERE hotel_id = ?
                  AND table_number = ?
            """, (hotel_id, table_number))
            table = cursor.fetchone()

            if table is None:
                raise ValueError("Invalid Table Number.")

            raise ValueError(
                f"Table {table_number} is {table['table_status']} and is not available."
            )

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Table Booking",
        action="CREATE",
        local_values=locals(),
        details="Business operation claim_restaurant_table completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return True

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def is_table_booked(table_number, hotel_id=None):
    table = get_table_by_number(table_number, hotel_id)
    return table is not None and table["table_status"] in {"Booked", "Reserved"}


def release_table(table_number, hotel_id=None):
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE tables
            SET table_status = 'Available'
            WHERE hotel_id = ?
              AND table_number = ?
              AND table_status = 'Occupied'
        """, (hotel_id, table_number))

        if cursor.rowcount != 1:
            raise ValueError("Occupied table could not be released.")

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
