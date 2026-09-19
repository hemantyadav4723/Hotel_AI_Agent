from database.database import get_connection


def create_settings_table():

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings(
                id INTEGER PRIMARY KEY CHECK(id = 1),
                hotel_name TEXT,
                owner_name TEXT,
                gst TEXT,
                phone TEXT,
                email TEXT
            )
        """)

        connection.commit()

    finally:
        connection.close()


def save_settings(
    hotel_name,
    owner_name,
    gst,
    phone,
    email
):

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO settings(
                id,
                hotel_name,
                owner_name,
                gst,
                phone,
                email
            )
            VALUES(1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                hotel_name = excluded.hotel_name,
                owner_name = excluded.owner_name,
                gst = excluded.gst,
                phone = excluded.phone,
                email = excluded.email
        """, (
            hotel_name,
            owner_name,
            gst,
            phone,
            email
        ))

        connection.commit()
        print("Settings Saved Successfully.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def view_settings():

    print("=" * 60)
    print("            HOTEL SETTINGS")
    print("=" * 60)

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM settings WHERE id = 1")
        settings = cursor.fetchone()

    finally:
        connection.close()

    if settings:
        print("Hotel Name :", settings["hotel_name"])
        print("Owner Name :", settings["owner_name"])
        print("GST Number :", settings["gst"])
        print("Phone      :", settings["phone"])
        print("Email      :", settings["email"])
    else:
        print("Settings Not Found.")


# ============================================================
# DISCOUNT RULES
# ============================================================

def create_discount_rules_table():
    """Create the hotel-wise automatic discount rules table."""
    from database.hotel_context import get_current_hotel_id

    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discount_rules(
                discount_rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                rule_name TEXT NOT NULL,
                min_amount REAL NOT NULL CHECK(min_amount >= 0),
                max_amount REAL,
                discount_type TEXT NOT NULL
                    CHECK(discount_type IN ('PERCENTAGE', 'FIXED')),
                discount_value REAL NOT NULL CHECK(discount_value > 0),
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK(is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(hotel_id, rule_name),
                FOREIGN KEY(hotel_id) REFERENCES hotels(hotel_id),
                CHECK(max_amount IS NULL OR max_amount >= min_amount)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_discount_rules_hotel_active
            ON discount_rules(hotel_id, is_active, min_amount, max_amount)
        """)

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _validate_discount_rule_range(
    cursor,
    hotel_id,
    min_amount,
    max_amount,
    exclude_rule_id=None
):
    """Reject overlapping active amount ranges for one hotel."""
    params = [hotel_id, min_amount]
    query = """
        SELECT discount_rule_id, rule_name
        FROM discount_rules
        WHERE hotel_id = ?
          AND is_active = 1
          AND (? IS NULL OR discount_rule_id <> ?)
          AND min_amount <= COALESCE(?, 999999999999999.0)
          AND (max_amount IS NULL OR max_amount >= ?)
        LIMIT 1
    """
    # Rebuild parameters explicitly so the SQL remains readable.
    params = [
        hotel_id,
        exclude_rule_id,
        exclude_rule_id,
        max_amount,
        min_amount,
    ]
    cursor.execute(query, params)
    conflict = cursor.fetchone()

    if conflict is not None:
        raise ValueError(
            f"Discount range overlaps active rule "
            f"'{conflict['rule_name']}'."
        )


def add_discount_rule(
    rule_name,
    min_amount,
    max_amount,
    discount_type,
    discount_value,
    hotel_id=None
):
    from database.hotel_context import get_current_hotel_id
    from datetime import datetime

    hotel_id = int(hotel_id or get_current_hotel_id())
    rule_name = str(rule_name).strip()
    discount_type = str(discount_type).strip().upper()

    try:
        min_amount = round(float(min_amount), 2)
        max_amount = (
            None if max_amount in (None, "") else round(float(max_amount), 2)
        )
        discount_value = round(float(discount_value), 2)
    except (TypeError, ValueError):
        raise ValueError("Invalid discount rule amount.")

    if not rule_name:
        raise ValueError("Discount rule name is required.")
    if min_amount < 0:
        raise ValueError("Minimum amount cannot be negative.")
    if max_amount is not None and max_amount < min_amount:
        raise ValueError("Maximum amount cannot be less than minimum amount.")
    if discount_type not in ("PERCENTAGE", "FIXED"):
        raise ValueError("Discount type must be Percentage or Fixed.")
    if discount_value <= 0:
        raise ValueError("Discount value must be greater than zero.")
    if discount_type == "PERCENTAGE" and discount_value > 100:
        raise ValueError("Percentage discount cannot exceed 100%.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        _validate_discount_rule_range(
            cursor,
            hotel_id,
            min_amount,
            max_amount
        )

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO discount_rules(
                hotel_id, rule_name, min_amount, max_amount,
                discount_type, discount_value,
                is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            hotel_id,
            rule_name,
            min_amount,
            max_amount,
            discount_type,
            discount_value,
            now,
            now
        ))

        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_discount_rules(hotel_id=None, include_inactive=True):
    from database.hotel_context import get_current_hotel_id

    hotel_id = int(hotel_id or get_current_hotel_id())
    connection = get_connection()
    try:
        cursor = connection.cursor()

        query = """
            SELECT *
            FROM discount_rules
            WHERE hotel_id = ?
        """
        params = [hotel_id]

        if not include_inactive:
            query += " AND is_active = 1"

        query += " ORDER BY min_amount ASC, discount_rule_id ASC"

        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def get_automatic_discount(subtotal, hotel_id=None):
    """Return (discount_amount, matching_rule) for the subtotal."""
    from database.hotel_context import get_current_hotel_id

    hotel_id = int(hotel_id or get_current_hotel_id())

    try:
        subtotal = round(float(subtotal), 2)
    except (TypeError, ValueError):
        raise ValueError("Invalid subtotal.")

    if subtotal <= 0:
        return 0.0, None

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM discount_rules
            WHERE hotel_id = ?
              AND is_active = 1
              AND min_amount <= ?
              AND (max_amount IS NULL OR ? <= max_amount)
            ORDER BY min_amount DESC, discount_rule_id DESC
            LIMIT 1
        """, (hotel_id, subtotal, subtotal))

        rule = cursor.fetchone()

        if rule is None:
            return 0.0, None

        if rule["discount_type"] == "PERCENTAGE":
            discount = subtotal * float(rule["discount_value"]) / 100
        else:
            discount = float(rule["discount_value"])

        discount = min(max(round(discount, 2), 0.0), subtotal)
        return discount, rule
    finally:
        connection.close()


def update_discount_rule(
    discount_rule_id,
    rule_name,
    min_amount,
    max_amount,
    discount_type,
    discount_value,
    hotel_id=None
):
    from database.hotel_context import get_current_hotel_id
    from datetime import datetime

    hotel_id = int(hotel_id or get_current_hotel_id())

    try:
        discount_rule_id = int(discount_rule_id)
        min_amount = round(float(min_amount), 2)
        max_amount = (
            None if max_amount in (None, "") else round(float(max_amount), 2)
        )
        discount_value = round(float(discount_value), 2)
    except (TypeError, ValueError):
        raise ValueError("Invalid discount rule.")

    rule_name = str(rule_name).strip()
    discount_type = str(discount_type).strip().upper()

    if not rule_name:
        raise ValueError("Discount rule name is required.")
    if min_amount < 0:
        raise ValueError("Minimum amount cannot be negative.")
    if max_amount is not None and max_amount < min_amount:
        raise ValueError("Maximum amount cannot be less than minimum amount.")
    if discount_type not in ("PERCENTAGE", "FIXED"):
        raise ValueError("Discount type must be Percentage or Fixed.")
    if discount_value <= 0:
        raise ValueError("Discount value must be greater than zero.")
    if discount_type == "PERCENTAGE" and discount_value > 100:
        raise ValueError("Percentage discount cannot exceed 100%.")

    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT 1
            FROM discount_rules
            WHERE discount_rule_id = ?
              AND hotel_id = ?
        """, (discount_rule_id, hotel_id))

        if cursor.fetchone() is None:
            raise ValueError("Discount rule not found.")

        _validate_discount_rule_range(
            cursor,
            hotel_id,
            min_amount,
            max_amount,
            exclude_rule_id=discount_rule_id
        )

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE discount_rules
            SET rule_name = ?,
                min_amount = ?,
                max_amount = ?,
                discount_type = ?,
                discount_value = ?,
                updated_at = ?
            WHERE discount_rule_id = ?
              AND hotel_id = ?
        """, (
            rule_name,
            min_amount,
            max_amount,
            discount_type,
            discount_value,
            now,
            discount_rule_id,
            hotel_id
        ))

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def set_discount_rule_status(discount_rule_id, is_active, hotel_id=None):
    from database.hotel_context import get_current_hotel_id
    from datetime import datetime

    hotel_id = int(hotel_id or get_current_hotel_id())
    is_active = 1 if is_active else 0

    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM discount_rules
            WHERE discount_rule_id = ?
              AND hotel_id = ?
        """, (discount_rule_id, hotel_id))
        rule = cursor.fetchone()

        if rule is None:
            raise ValueError("Discount rule not found.")

        if is_active:
            _validate_discount_rule_range(
                cursor,
                hotel_id,
                rule["min_amount"],
                rule["max_amount"],
                exclude_rule_id=rule["discount_rule_id"]
            )

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE discount_rules
            SET is_active = ?, updated_at = ?
            WHERE discount_rule_id = ?
              AND hotel_id = ?
        """, (
            is_active,
            now,
            discount_rule_id,
            hotel_id
        ))

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
