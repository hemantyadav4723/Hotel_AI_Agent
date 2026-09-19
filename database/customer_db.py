from utils.error_logging import log_non_blocking_error
import json

from database.database import get_connection


# ============================================================
# GUEST MASTER SCHEMA
# ============================================================

def create_customers_table():
    """
    Create the enterprise Guest/Customer Master table.

    This function is migration-safe:
    - New installations get the complete schema.
    - Existing installations keep their existing customer data.
    - Missing columns are added without deleting old records.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (

                customer_id TEXT PRIMARY KEY,

                customer_name TEXT NOT NULL,

                customer_mobile TEXT,

                customer_email TEXT,

                customer_address TEXT,

                customer_city TEXT,

                customer_state TEXT,

                customer_country TEXT DEFAULT 'India',

                customer_pincode TEXT,

                guest_status TEXT NOT NULL DEFAULT 'Active',

                is_active INTEGER NOT NULL DEFAULT 1,

                preferences TEXT,

                special_requests TEXT,

                guest_notes TEXT,

                created_time TEXT,

                updated_time TEXT

            )
        """)

        connection.commit()

        migrate_customers_table(connection)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_customers_name
            ON customers(customer_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_customers_mobile
            ON customers(customer_mobile)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_customers_email
            ON customers(customer_email)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_customers_status
            ON customers(guest_status)
        """)
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def migrate_customers_table(connection=None):
    """
    Safely upgrade an existing customers table.

    No existing customer records are deleted.
    """

    own_connection = False

    if connection is None:
        connection = get_connection()
        own_connection = True

    try:
        cursor = connection.cursor()

        cursor.execute("PRAGMA table_info(customers)")
        existing_columns = {
            row["name"] if isinstance(row, dict) else row[1]
            for row in cursor.fetchall()
        }

        required_columns = {
            "customer_city": "TEXT",
            "customer_state": "TEXT",
            "customer_country": "TEXT DEFAULT 'India'",
            "customer_pincode": "TEXT",
            "guest_status": "TEXT NOT NULL DEFAULT 'Active'",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
            "preferences": "TEXT",
            "special_requests": "TEXT",
            "guest_notes": "TEXT",
            "updated_time": "TEXT",
        }

        for column_name, column_definition in required_columns.items():

            if column_name not in existing_columns:

                cursor.execute(
                    f"""
                    ALTER TABLE customers
                    ADD COLUMN {column_name} {column_definition}
                    """
                )

        # Normalize old records after migration.
        cursor.execute("""
            UPDATE customers
            SET guest_status = 'Active'
            WHERE guest_status IS NULL
               OR TRIM(guest_status) = ''
        """)

        cursor.execute("""
            UPDATE customers
            SET is_active = 1
            WHERE is_active IS NULL
        """)

        cursor.execute("""
            UPDATE customers
            SET customer_country = 'India'
            WHERE customer_country IS NULL
               OR TRIM(customer_country) = ''
        """)

        # Enforce Guest Master identity uniqueness at the database layer.
        # NULL/blank mobiles remain allowed for legacy records, while
        # every real mobile number can belong to only one Guest Master.
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_unique_mobile
            ON customers(customer_mobile)
            WHERE customer_mobile IS NOT NULL
              AND TRIM(customer_mobile) <> ''
        """)

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        if own_connection:
            connection.close()


# ============================================================
# GUEST MASTER CREATE
# ============================================================

def save_customer(
    customer_id,
    customer_name,
    customer_mobile,
    customer_email,
    customer_address,
    created_time,
    customer_city=None,
    customer_state=None,
    customer_country="India",
    customer_pincode=None,
    guest_status="Active",
    is_active=1,
    preferences=None,
    special_requests=None,
    guest_notes=None
):
    """
    Create a Guest/Customer Master record.

    The original six-argument interface remains compatible
    with the existing customer.py module.
    """

    connection = get_connection()

    try:

        # Ensure an older database has the new columns.
        migrate_customers_table(connection)

        cursor = connection.cursor()

        mobile = str(customer_mobile or "").strip() or None
        if mobile:
            cursor.execute("""
                SELECT customer_id
                FROM customers
                WHERE customer_mobile = ?
                LIMIT 1
            """, (mobile,))
            existing_customer = cursor.fetchone()
            if existing_customer is not None:
                raise ValueError(
                    f"Customer with mobile {mobile} already exists (ID: {existing_customer['customer_id']})."
                )

        created_time_value = (
            created_time.strftime("%d-%m-%Y %I:%M:%S %p")
            if hasattr(created_time, "strftime")
            else str(created_time)
        )

        cursor.execute("""
            INSERT INTO customers (
                customer_id,
                customer_name,
                customer_mobile,
                customer_email,
                customer_address,
                customer_city,
                customer_state,
                customer_country,
                customer_pincode,
                guest_status,
                is_active,
                preferences,
                special_requests,
                guest_notes,
                created_time,
                updated_time
            )
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
        """, (
            customer_id,
            customer_name,
            customer_mobile,
            customer_email,
            customer_address,
            customer_city,
            customer_state,
            customer_country,
            customer_pincode,
            guest_status,
            is_active,
            preferences,
            special_requests,
            guest_notes,
            created_time_value,
            created_time_value
        ))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Customer",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_customer completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


# ============================================================
# GUEST MASTER READ
# ============================================================

def get_all_customers():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM customers
            ORDER BY customer_name COLLATE NOCASE ASC
        """)

        return cursor.fetchall()

    finally:

        connection.close()


def get_customer_by_id(customer_id):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM customers
            WHERE customer_id = ?
        """, (str(customer_id or "").strip().upper(),))
        return cursor.fetchone()
    finally:
        connection.close()


def get_customer_by_mobile(customer_mobile):
    """Return the earliest Guest Master record for a mobile number."""

    mobile = str(customer_mobile or "").strip()
    if not mobile:
        return None

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM customers
            WHERE customer_mobile = ?
            ORDER BY created_time ASC, customer_id ASC
            LIMIT 1
        """, (mobile,))
        return cursor.fetchone()
    finally:
        connection.close()



def search_restaurant_guests(search_text=None, hotel_id=None):
    """Return active guests associated with the current hotel for POS selection."""
    from database.hotel_context import get_current_hotel_id

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    search_text = str(search_text or "").strip()
    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                c.customer_id,
                c.customer_name,
                c.customer_mobile,
                c.customer_email,
                c.customer_address,
                c.customer_city,
                c.customer_state,
                c.customer_country,
                c.customer_pincode,
                c.guest_status,
                c.is_active,
                r.is_active AS hotel_relationship_active,
                r.visit_count,
                r.first_visit_at,
                r.last_visit_at
            FROM customers c
            INNER JOIN guest_hotel_relationships r
                ON r.customer_id = c.customer_id
               AND r.hotel_id = ?
            WHERE r.is_active = 1
              AND c.is_active = 1
        """
        params = [hotel_id]

        if search_text:
            value = f"%{search_text}%"
            query += """
                AND (
                    c.customer_id LIKE ?
                    OR c.customer_name LIKE ? COLLATE NOCASE
                    OR c.customer_mobile LIKE ?
                    OR c.customer_email LIKE ? COLLATE NOCASE
                )
            """
            params.extend([value] * 4)

        query += """
            ORDER BY c.customer_name COLLATE NOCASE ASC, c.customer_id ASC
        """

        cursor.execute(query, tuple(params))
        return cursor.fetchall()

    finally:
        connection.close()

def validate_guest_hotel_relationship(customer_id, hotel_id=None, require_active=True):
    """Validate that a guest exists and is linked to the selected hotel."""

    from database.hotel_context import get_current_hotel_id

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    customer_id = _normalize_customer_id(customer_id)
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT customer_id FROM customers WHERE customer_id = ?", (customer_id,))
        if cursor.fetchone() is None:
            raise ValueError("Guest does not exist.")

        cursor.execute("""
            SELECT relationship_id, customer_id, hotel_id, is_active
            FROM guest_hotel_relationships
            WHERE customer_id = ? AND hotel_id = ?
        """, (customer_id, hotel_id))
        relationship = cursor.fetchone()
        if relationship is None:
            raise ValueError("Guest is not associated with the selected hotel.")
        if require_active and int(relationship["is_active"] or 0) != 1:
            raise ValueError("Guest's relationship with the selected hotel is inactive.")
        return relationship
    finally:
        connection.close()


def get_guest_data_integrity_report(hotel_id=None):
    """Return multi-hotel guest integrity checks without modifying data."""

    from database.hotel_context import get_current_hotel_id

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM (
                SELECT customer_mobile
                FROM customers
                WHERE customer_mobile IS NOT NULL AND TRIM(customer_mobile) <> ''
                GROUP BY customer_mobile
                HAVING COUNT(*) > 1
            )
        """)
        duplicate_mobile_groups = int(cursor.fetchone()["total"] or 0)

        checks = {
            "customers_without_hotel_relationship": """
                SELECT COUNT(*) AS total
                FROM customers c
                LEFT JOIN guest_hotel_relationships r
                  ON r.customer_id = c.customer_id
                WHERE r.relationship_id IS NULL
            """,
            "orphan_guest_hotel_relationships": """
                SELECT COUNT(*) AS total
                FROM guest_hotel_relationships r
                LEFT JOIN customers c ON c.customer_id = r.customer_id
                LEFT JOIN hotels h ON h.hotel_id = r.hotel_id
                WHERE c.customer_id IS NULL OR h.hotel_id IS NULL
            """,
            "guest_bookings_missing_hotel_relationship": """
                SELECT COUNT(*) AS total
                FROM room_bookings b
                LEFT JOIN guest_hotel_relationships r
                  ON r.customer_id = b.customer_id AND r.hotel_id = b.hotel_id
                WHERE b.customer_id IS NOT NULL AND TRIM(b.customer_id) <> ''
                  AND r.relationship_id IS NULL
            """,
            "guest_orders_missing_hotel_relationship": """
                SELECT COUNT(*) AS total
                FROM orders o
                LEFT JOIN guest_hotel_relationships r
                  ON r.customer_id = o.customer_id AND r.hotel_id = o.hotel_id
                WHERE o.customer_id IS NOT NULL AND TRIM(o.customer_id) <> ''
                  AND r.relationship_id IS NULL
            """,
            "guest_feedback_missing_hotel_relationship": """
                SELECT COUNT(*) AS total
                FROM feedback f
                LEFT JOIN guest_hotel_relationships r
                  ON r.customer_id = f.customer_id AND r.hotel_id = f.hotel_id
                WHERE f.customer_id IS NOT NULL AND TRIM(f.customer_id) <> ''
                  AND r.relationship_id IS NULL
            """,
        }

        result = {
            "hotel_id": hotel_id,
            "duplicate_mobile_groups": duplicate_mobile_groups,
        }
        for name, query in checks.items():
            cursor.execute(query)
            result[name] = int(cursor.fetchone()["total"] or 0)

        result["is_integrity_ok"] = all(
            value == 0 for key, value in result.items()
            if key != "hotel_id"
        )
        return result
    finally:
        connection.close()


def search_customers(search_text=None, search_field="all", guest_status=None, hotel_id=None):
    """Search/filter guests from the centralized Guest Master."""
    search_text = str(search_text or "").strip()
    search_field = str(search_field or "all").strip().lower()
    guest_status = str(guest_status or "").strip()

    allowed_fields = {
        "id": "customer_id",
        "name": "customer_name",
        "mobile": "customer_mobile",
        "email": "customer_email",
        "city": "customer_city",
        "state": "customer_state",
        "country": "customer_country",
        "pincode": "customer_pincode",
    }

    if search_field not in {"all", *allowed_fields.keys()}:
        raise ValueError("Invalid guest search field.")

    if guest_status and guest_status not in {"Active", "Inactive", "Blacklisted"}:
        raise ValueError("Invalid guest status filter.")

    conditions = []
    params = []

    hotel_join = ""
    if hotel_id is not None:
        hotel_join = """
            INNER JOIN guest_hotel_relationships ghr
                ON ghr.customer_id = customers.customer_id
               AND ghr.hotel_id = ?
               AND ghr.is_active = 1
        """
        params.append(hotel_id)

    if search_text:
        if search_field == "all":
            value = f"%{search_text}%"
            conditions.append("""
                (
                    customer_id LIKE ?
                    OR customer_name LIKE ? COLLATE NOCASE
                    OR customer_mobile LIKE ?
                    OR customer_email LIKE ? COLLATE NOCASE
                    OR customer_city LIKE ? COLLATE NOCASE
                    OR customer_state LIKE ? COLLATE NOCASE
                    OR customer_country LIKE ? COLLATE NOCASE
                    OR customer_pincode LIKE ?
                )
            """)
            params.extend([value] * 8)
        elif search_field == "id":
            conditions.append("customer_id = ?")
            params.append(search_text.upper())
        else:
            column = allowed_fields[search_field]
            conditions.append(f"{column} LIKE ? COLLATE NOCASE")
            params.append(f"%{search_text}%")

    if guest_status:
        conditions.append("guest_status = ?")
        params.append(guest_status)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"""
                SELECT customers.*
                FROM customers
                {hotel_join}
                {where_clause}
                ORDER BY customer_name COLLATE NOCASE ASC, customer_id ASC
            """,
            tuple(params),
        )
        return cursor.fetchall()
    finally:
        connection.close()


def _print_customer_record(customer):
    print(f"Customer ID : {customer['customer_id']}")
    print(f"Name        : {customer['customer_name']}")
    print(f"Mobile      : {customer['customer_mobile']}")
    print(f"Email       : {customer['customer_email']}")
    print(f"Address     : {customer['customer_address']}")

    if "customer_city" in customer.keys():
        print(f"City        : {customer['customer_city']}")
    if "customer_state" in customer.keys():
        print(f"State       : {customer['customer_state']}")
    if "customer_country" in customer.keys():
        print(f"Country     : {customer['customer_country']}")
    if "customer_pincode" in customer.keys():
        print(f"PIN Code    : {customer['customer_pincode']}")
    if "guest_status" in customer.keys():
        print(f"Status      : {customer['guest_status']}")
    if "is_active" in customer.keys():
        print("Active      : " + ("Yes" if customer["is_active"] else "No"))
    if "preferences" in customer.keys():
        print(f"Preferences : {customer['preferences']}")
    if "special_requests" in customer.keys():
        print(f"Special Req.: {customer['special_requests']}")
    if "guest_notes" in customer.keys():
        print(f"Guest Notes : {customer['guest_notes']}")
    print(f"Created     : {customer['created_time']}")
    if "updated_time" in customer.keys():
        print(f"Updated     : {customer['updated_time']}")


def view_customers():
    customers = get_all_customers()
    if not customers:
        print("No Customers Found.")
        return

    print("=" * 70)
    print("                 GUEST / CUSTOMER LIST")
    print("=" * 70)
    for customer in customers:
        _print_customer_record(customer)
        print("-" * 70)


# ============================================================
# GUEST SEARCH / FILTER
# ============================================================

def search_customer():
    print("=" * 70)
    print("               SEARCH / FILTER GUEST")
    print("=" * 70)
    print("1. Customer ID")
    print("2. Name")
    print("3. Mobile")
    print("4. Email")
    print("5. City")
    print("6. State")
    print("7. Country")
    print("8. PIN Code")
    print("9. All Fields")
    print("10. Status Only")
    print("11. Back")

    choice = input("Enter Search Option : ").strip()
    if choice == "11":
        return

    field_map = {
        "1": "id", "2": "name", "3": "mobile", "4": "email",
        "5": "city", "6": "state", "7": "country", "8": "pincode",
        "9": "all",
    }

    if choice == "10":
        search_text = None
        search_field = "all"
    elif choice in field_map:
        search_field = field_map[choice]
        search_text = input("Enter Search Value : ").strip()
        if not search_text:
            print("Search value is required.")
            return
    else:
        print("Invalid Search Option.")
        return

    status = input(
        "Filter Status [All/Active/Inactive/Blacklisted] : "
    ).strip()

    if not status or status.lower() == "all":
        status = None
    else:
        status = {
            "active": "Active",
            "inactive": "Inactive",
            "blacklisted": "Blacklisted",
        }.get(status.lower())
        if status is None:
            print("Invalid status filter.")
            return

    try:
        customers = search_customers(
            search_text=search_text,
            search_field=search_field,
            guest_status=status,
        )
    except ValueError as error:
        print(f"Search Error: {error}")
        return

    print("=" * 70)
    print("                  SEARCH RESULTS")
    print("=" * 70)
    print(f"Total Guests Found : {len(customers)}")

    if not customers:
        print("No Customers Found.")
        return

    print("-" * 70)
    for customer in customers:
        _print_customer_record(customer)
        print("-" * 70)


# GUEST MASTER UPDATE
# ============================================================

def update_customer():

    customer_id = input(
        "Enter Customer ID : "
    ).strip().upper()

    connection = get_connection()

    try:
        migrate_customers_table(connection)

        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM customers
            WHERE customer_id = ?
        """, (customer_id,))

        customer = cursor.fetchone()

        if not customer:
            print("Customer Not Found.")
            return

        from utils.validators import (
            validate_name,
            validate_mobile,
            validate_email,
            validate_address,
            validate_pincode
        )

        current_name = customer["customer_name"] or ""
        current_mobile = customer["customer_mobile"] or ""
        current_email = customer["customer_email"] or ""
        current_address = customer["customer_address"] or ""
        current_city = customer["customer_city"] or ""
        current_state = customer["customer_state"] or ""
        current_country = customer["customer_country"] or "India"
        current_pincode = customer["customer_pincode"] or ""

        print("\nCustomer Found")
        print("Leave a field blank to keep the current value.")

        name_input = input(
            f"Enter New Name [{current_name}] : "
        ).strip()
        if name_input:
            while True:
                if name_input.replace(" ", "").isalpha() and len(name_input.replace(" ", "")) >= 3:
                    name = name_input.title()
                    break
                print("Invalid Name.")
                name_input = input(
                    f"Enter New Name [{current_name}] : "
                ).strip()
                if not name_input:
                    name = current_name
                    break
        else:
            name = current_name

        mobile_input = input(
            f"Enter New Mobile [{current_mobile}] : "
        ).strip()
        if mobile_input:
            if not mobile_input.isdigit() or len(mobile_input) != 10:
                raise ValueError("Invalid Mobile Number. Enter 10 digits.")
            mobile = mobile_input

            cursor.execute("""
                SELECT customer_id
                FROM customers
                WHERE customer_mobile = ?
                  AND customer_id <> ?
                LIMIT 1
            """, (mobile, customer_id))
            duplicate_customer = cursor.fetchone()
            if duplicate_customer is not None:
                raise ValueError(
                    f"Mobile number already belongs to Customer ID: {duplicate_customer['customer_id']}."
                )
        else:
            mobile = current_mobile

        email_input = input(
            f"Enter New Email [{current_email}] : "
        ).strip()
        if email_input:
            import re
            pattern = r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
            if not re.fullmatch(pattern, email_input):
                raise ValueError("Invalid Email Address.")
            email = email_input.lower()
        else:
            email = current_email

        address_input = input(
            f"Enter New Address [{current_address}] : "
        ).strip()
        if address_input:
            if len(address_input) < 5:
                raise ValueError("Address is too short.")
            address = address_input
        else:
            address = current_address

        city_input = input(
            f"Enter City [{current_city}] : "
        ).strip()
        if city_input:
            if not city_input.replace(" ", "").isalpha():
                raise ValueError("City should contain letters and spaces only.")
            city = city_input.title()
        else:
            city = current_city

        state_input = input(
            f"Enter State [{current_state}] : "
        ).strip()
        if state_input:
            if not state_input.replace(" ", "").isalpha():
                raise ValueError("State should contain letters and spaces only.")
            state = state_input.title()
        else:
            state = current_state

        country_input = input(
            f"Enter Country [{current_country}] : "
        ).strip()
        if country_input:
            if not country_input.replace(" ", "").isalpha():
                raise ValueError("Country name should contain letters only.")
            country = country_input.title()
        else:
            country = current_country

        pincode_input = input(
            f"Enter PIN Code [{current_pincode}] : "
        ).strip()
        if pincode_input:
            if not pincode_input.isdigit() or len(pincode_input) != 6:
                raise ValueError("Invalid PIN Code. Enter 6 digits.")
            pincode = pincode_input
        else:
            pincode = current_pincode

        status_input = input(
            f"Enter Guest Status [Active/Inactive/Blacklisted] [{customer['guest_status'] or 'Active'}] : "
        ).strip()
        status = status_input or customer["guest_status"] or "Active"

        if status not in ("Active", "Inactive", "Blacklisted"):
            raise ValueError(
                "Invalid Guest Status. Use Active, Inactive or Blacklisted."
            )

        preferences = input(
            f"Enter Preferences [{customer['preferences'] or ''}] : "
        ).strip() or (customer["preferences"] or "")

        special_requests = input(
            f"Enter Special Requests [{customer['special_requests'] or ''}] : "
        ).strip() or (customer["special_requests"] or "")

        guest_notes = input(
            f"Enter Guest Notes [{customer['guest_notes'] or ''}] : "
        ).strip() or (customer["guest_notes"] or "")

        is_active = 0 if status == "Inactive" else 1

        updated_time = __import__("datetime").datetime.now().strftime(
            "%d-%m-%Y %I:%M:%S %p"
        )

        cursor.execute("""
            UPDATE customers
            SET
                customer_name = ?,
                customer_mobile = ?,
                customer_email = ?,
                customer_address = ?,
                customer_city = ?,
                customer_state = ?,
                customer_country = ?,
                customer_pincode = ?,
                guest_status = ?,
                is_active = ?,
                preferences = ?,
                special_requests = ?,
                guest_notes = ?,
                updated_time = ?
            WHERE customer_id = ?
        """, (
            name,
            mobile,
            email,
            address,
            city,
            state,
            country or "India",
            pincode,
            status,
            is_active,
            preferences,
            special_requests,
            guest_notes,
            updated_time,
            customer_id
        ))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Customer",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_customer completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        print("\nCustomer Updated Successfully.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ============================================================
# GUEST MASTER DELETE
# ============================================================

def delete_customer():

    customer_id = input(
        "Enter Customer ID : "
    ).strip().upper()

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT *
            FROM customers
            WHERE customer_id = ?
        """, (customer_id,))

        customer = cursor.fetchone()

        if not customer:

            print("Customer Not Found.")
            return

        cursor.execute("""
            DELETE FROM customers
            WHERE customer_id = ?
        """, (customer_id,))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Customer",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_customer completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        print("Customer Deleted Successfully.")

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


# ============================================================
# CUSTOMER HISTORY


def update_customer_record(customer_id, customer_name, customer_mobile, customer_email=None, customer_address=None, customer_city=None, customer_state=None, customer_country="India", customer_pincode=None, guest_status="Active", is_active=1, preferences=None, special_requests=None, guest_notes=None, hotel_id=None):
    """Update a Guest Master record after validating hotel relationship."""
    from database.hotel_context import get_current_hotel_id
    from datetime import datetime
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    customer_id = _normalize_customer_id(customer_id)
    guest_status = str(guest_status or "Active").strip()
    if guest_status not in {"Active", "Inactive", "Blacklisted"}:
        raise ValueError("Invalid guest status.")
    mobile = str(customer_mobile or "").strip() or None
    if not mobile:
        raise ValueError("Guest mobile is required.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""SELECT c.customer_id FROM customers c INNER JOIN guest_hotel_relationships r ON r.customer_id=c.customer_id AND r.hotel_id=? AND r.is_active=1 WHERE c.customer_id=?""", (hotel_id, customer_id))
        if cursor.fetchone() is None:
            raise ValueError("Guest is not associated with the selected hotel.")
        cursor.execute("SELECT customer_id FROM customers WHERE customer_mobile=? AND customer_id<>? LIMIT 1", (mobile, customer_id))
        duplicate = cursor.fetchone()
        if duplicate is not None:
            raise ValueError(f"Mobile number already belongs to Customer ID: {duplicate['customer_id']}.")
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""UPDATE customers SET customer_name=?, customer_mobile=?, customer_email=?, customer_address=?, customer_city=?, customer_state=?, customer_country=?, customer_pincode=?, guest_status=?, is_active=?, preferences=?, special_requests=?, guest_notes=?, updated_time=? WHERE customer_id=?""", (str(customer_name).strip(), mobile, customer_email, customer_address, customer_city, customer_state, customer_country or "India", customer_pincode, guest_status, int(bool(is_active)), preferences, special_requests, guest_notes, now, customer_id))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(module="Customer", action="UPDATE", local_values=locals(), details="Business operation update_customer_record completed successfully.")
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _normalize_customer_id(customer_id):
    customer_id = str(customer_id or "").strip().upper()
    if not customer_id:
        raise ValueError("Customer ID is required.")
    return customer_id


def get_guest_stay_history(customer_id, hotel_id=None):
    from database.hotel_context import get_current_hotel_id

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    customer_id = _normalize_customer_id(customer_id)
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                rb.booking_id,
                rb.hotel_id,
                rb.customer_id,
                rb.customer_name,
                rb.customer_mobile,
                rb.check_in_date,
                rb.expected_check_out,
                rb.actual_check_in,
                rb.actual_check_out,
                rb.booking_status,
                rb.nights,
                rb.adults,
                rb.children,
                rb.grand_total,
                rb.payment_status,
                rb.booking_source,
                rb.notes,
                COALESCE(
                    GROUP_CONCAT(DISTINCT rba.room_number),
                    rb.room_number
                ) AS room_numbers
            FROM room_bookings rb
            LEFT JOIN room_booking_allocations rba
                ON rba.booking_id = rb.booking_id
                AND rba.hotel_id = rb.hotel_id
            WHERE rb.customer_id = ?
              AND rb.hotel_id = ?
              AND rb.booking_status IN ('Checked-In', 'Checked-Out')
            GROUP BY rb.booking_id
            ORDER BY rb.created_at DESC, rb.booking_id DESC
            """,
            (customer_id, hotel_id)
        )
        return cursor.fetchall()
    finally:
        connection.close()


def get_guest_stay_summary(customer_id, hotel_id=None):
    stays = get_guest_stay_history(customer_id, hotel_id)
    return {
        "total_stays": len(stays),
        "total_nights": sum(int(stay["nights"] or 0) for stay in stays),
        "total_spend": round(
            sum(float(stay["grand_total"] or 0) for stay in stays),
            2
        )
    }


def get_guest_booking_history(
    customer_id,
    hotel_id=None,
    booking_status=None,
    payment_status=None,
    booking_source=None
):
    """Return the complete room-booking history for one guest."""

    from database.hotel_context import get_current_hotel_id

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    customer_id = _normalize_customer_id(customer_id)

    valid_booking_statuses = (
        "Pending",
        "Confirmed",
        "Cancelled",
        "No-Show",
        "Checked-In",
        "Checked-Out",
    )
    valid_payment_statuses = (
        "Pending",
        "Partially Paid",
        "Paid",
        "Refunded",
    )

    if booking_status and booking_status not in valid_booking_statuses:
        raise ValueError("Invalid booking status filter.")

    if payment_status and payment_status not in valid_payment_statuses:
        raise ValueError("Invalid payment status filter.")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT
                rb.booking_id,
                rb.hotel_id,
                rb.customer_id,
                rb.customer_name,
                rb.customer_mobile,
                rb.booking_date,
                rb.booking_time,
                rb.check_in_date,
                rb.expected_check_out,
                rb.actual_check_in,
                rb.actual_check_out,
                rb.booking_status,
                rb.payment_status,
                rb.booking_source,
                rb.adults,
                rb.children,
                rb.nights,
                rb.room_rate,
                rb.subtotal,
                rb.gst,
                rb.grand_total,
                rb.advance_amount,
                rb.balance_amount,
                rb.payment_method,
                rb.notes,
                rb.cancellation_reason,
                rb.no_show_reason,
                rb.created_at,
                rb.updated_at,
                COALESCE(
                    GROUP_CONCAT(DISTINCT rba.room_number),
                    rb.room_number
                ) AS room_numbers
            FROM room_bookings rb
            LEFT JOIN room_booking_allocations rba
                ON rba.booking_id = rb.booking_id
                AND rba.hotel_id = rb.hotel_id
            WHERE rb.customer_id = ?
              AND rb.hotel_id = ?
        """
        params = [customer_id, hotel_id]

        if booking_status:
            query += " AND rb.booking_status = ?"
            params.append(booking_status)

        if payment_status:
            query += " AND rb.payment_status = ?"
            params.append(payment_status)

        if booking_source:
            query += " AND rb.booking_source = ?"
            params.append(booking_source)

        query += """
            GROUP BY rb.booking_id
            ORDER BY rb.created_at DESC, rb.booking_id DESC
        """

        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def get_guest_booking_summary(customer_id, hotel_id=None):
    bookings = get_guest_booking_history(customer_id, hotel_id)

    status_counts = {
        "Pending": 0,
        "Confirmed": 0,
        "Cancelled": 0,
        "No-Show": 0,
        "Checked-In": 0,
        "Checked-Out": 0,
    }

    total_value = 0.0
    total_advance = 0.0
    total_balance = 0.0

    for booking in bookings:
        status = booking["booking_status"]
        if status in status_counts:
            status_counts[status] += 1
        total_value += float(booking["grand_total"] or 0)
        total_advance += float(booking["advance_amount"] or 0)
        total_balance += float(booking["balance_amount"] or 0)

    return {
        "total_bookings": len(bookings),
        "status_counts": status_counts,
        "total_value": round(total_value, 2),
        "total_advance": round(total_advance, 2),
        "total_balance": round(total_balance, 2),
    }


def customer_history():
    customer_id = input("Enter Customer ID : ").strip().upper()
    customer = get_customer_by_id(customer_id)

    if customer is None:
        print("Customer Not Found.")
        return

    stays = get_guest_stay_history(customer_id)

    print()
    print("=" * 70)
    print("GUEST STAY HISTORY")
    print("=" * 70)
    print("Customer ID :", customer["customer_id"])
    print("Name        :", customer["customer_name"])
    print("Mobile      :", customer["customer_mobile"] or "None")
    print("-" * 70)

    if not stays:
        print("No completed or active stays found.")
        print("=" * 70)
        return

    for index, stay in enumerate(stays, start=1):
        print(f"Stay #{index}")
        print("Booking ID       :", stay["booking_id"])
        print("Rooms            :", stay["room_numbers"] or "None")
        print("Check-In Date    :", stay["check_in_date"] or "None")
        print("Expected Check-Out:", stay["expected_check_out"] or "None")
        print("Actual Check-In  :", stay["actual_check_in"] or "None")
        print("Actual Check-Out :", stay["actual_check_out"] or "None")
        print("Stay Status      :", stay["booking_status"])
        print("Nights           :", stay["nights"] or 0)
        print("Adults           :", stay["adults"] or 0)
        print("Children         :", stay["children"] or 0)
        print("Grand Total      :", f"₹{float(stay['grand_total'] or 0):.2f}")
        print("Payment Status   :", stay["payment_status"] or "None")
        print("Booking Source   :", stay["booking_source"] or "None")
        if stay["notes"]:
            print("Notes            :", stay["notes"])
        if index < len(stays):
            print("-" * 70)

    summary = get_guest_stay_summary(customer_id)
    print("-" * 70)
    print("STAY SUMMARY")
    print("Total Stays      :", summary["total_stays"])
    print("Total Nights     :", summary["total_nights"])
    print("Total Spend      :", f"₹{summary['total_spend']:.2f}")
    print("=" * 70)


def customer_booking_history():
    customer_id = input("Enter Customer ID : ").strip().upper()
    customer = get_customer_by_id(customer_id)

    if customer is None:
        print("Customer Not Found.")
        return

    print()
    print("Booking Status Filter")
    print("1. All")
    print("2. Pending")
    print("3. Confirmed")
    print("4. Cancelled")
    print("5. No-Show")
    print("6. Checked-In")
    print("7. Checked-Out")
    status_choice = input("Enter Choice : ").strip()

    status_map = {
        "1": None,
        "2": "Pending",
        "3": "Confirmed",
        "4": "Cancelled",
        "5": "No-Show",
        "6": "Checked-In",
        "7": "Checked-Out",
    }

    if status_choice not in status_map:
        print("Invalid status filter.")
        return

    bookings = get_guest_booking_history(
        customer_id,
        booking_status=status_map[status_choice]
    )

    print()
    print("=" * 80)
    print("GUEST BOOKING HISTORY")
    print("=" * 80)
    print("Customer ID :", customer["customer_id"])
    print("Name        :", customer["customer_name"])
    print("Mobile      :", customer["customer_mobile"] or "None")
    print("-" * 80)

    if not bookings:
        print("No bookings found for the selected filter.")
        print("=" * 80)
        return

    for index, booking in enumerate(bookings, start=1):
        print(f"Booking #{index}")
        print("Booking ID       :", booking["booking_id"])
        print("Booking Date     :", booking["booking_date"] or "None")
        print("Booking Time     :", booking["booking_time"] or "None")
        print("Rooms            :", booking["room_numbers"] or "None")
        print("Check-In Date    :", booking["check_in_date"] or "None")
        print("Expected Check-Out:", booking["expected_check_out"] or "None")
        print("Actual Check-In  :", booking["actual_check_in"] or "None")
        print("Actual Check-Out :", booking["actual_check_out"] or "None")
        print("Booking Status   :", booking["booking_status"] or "None")
        print("Payment Status   :", booking["payment_status"] or "None")
        print("Booking Source   :", booking["booking_source"] or "None")
        print("Adults           :", booking["adults"] or 0)
        print("Children         :", booking["children"] or 0)
        print("Nights           :", booking["nights"] or 0)
        print("Room Rate        :", f"₹{float(booking['room_rate'] or 0):.2f}")
        print("Subtotal         :", f"₹{float(booking['subtotal'] or 0):.2f}")
        print("GST              :", f"₹{float(booking['gst'] or 0):.2f}")
        print("Grand Total      :", f"₹{float(booking['grand_total'] or 0):.2f}")
        print("Advance Paid     :", f"₹{float(booking['advance_amount'] or 0):.2f}")
        print("Balance Due      :", f"₹{float(booking['balance_amount'] or 0):.2f}")
        print("Payment Method   :", booking["payment_method"] or "None")

        if booking["cancellation_reason"]:
            print("Cancellation     :", booking["cancellation_reason"])
        if booking["no_show_reason"]:
            print("No-Show Reason   :", booking["no_show_reason"])
        if booking["notes"]:
            print("Notes            :", booking["notes"])

        if index < len(bookings):
            print("-" * 80)

    summary = get_guest_booking_summary(customer_id)
    print("-" * 80)
    print("BOOKING SUMMARY")
    print("Total Bookings   :", summary["total_bookings"])
    print("Pending          :", summary["status_counts"]["Pending"])
    print("Confirmed        :", summary["status_counts"]["Confirmed"])
    print("Cancelled        :", summary["status_counts"]["Cancelled"])
    print("No-Show          :", summary["status_counts"]["No-Show"])
    print("Checked-In       :", summary["status_counts"]["Checked-In"])
    print("Checked-Out      :", summary["status_counts"]["Checked-Out"])
    print("Total Booking Value:", f"₹{summary['total_value']:.2f}")
    print("Total Advance    :", f"₹{summary['total_advance']:.2f}")
    print("Total Balance    :", f"₹{summary['total_balance']:.2f}")
    print("=" * 80)


# ============================================================
# GUEST RESTAURANT HISTORY
# ============================================================

def get_guest_restaurant_history(customer_id, hotel_id=None):
    from database.hotel_context import get_current_hotel_id

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    customer_id = _normalize_customer_id(customer_id)
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                order_id,
                hotel_id,
                customer_id,
                order_date,
                order_time,
                customer_name,
                customer_mobile,
                table_number,
                cart,
                subtotal,
                gst,
                grand_total,
                order_status,
                refund_amount
            FROM orders
            WHERE customer_id = ?
              AND hotel_id = ?
            ORDER BY rowid DESC
        """, (customer_id, hotel_id))
        return cursor.fetchall()
    finally:
        connection.close()


def get_guest_restaurant_summary(customer_id, hotel_id=None):
    """
    Return restaurant history metrics for one guest at one hotel.

    Cancelled orders are excluded from order-value and item metrics.
    Refunds are deducted from restaurant spending.
    """
    orders = get_guest_restaurant_history(customer_id, hotel_id)

    total_orders = 0
    cancelled_orders = 0
    total_items = 0
    total_subtotal = 0.0
    total_gst = 0.0
    total_spend = 0.0
    item_totals = {}

    for order in orders:
        status = str(order["order_status"] or "New").strip()
        if status == "Cancelled":
            cancelled_orders += 1
            continue

        total_orders += 1

        try:
            cart = json.loads(order["cart"] or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            cart = []

        for item in cart:
            try:
                quantity = float(item.get("quantity", 0) or 0)
            except (TypeError, ValueError):
                quantity = 0

            if quantity > 0:
                total_items += quantity
                item_name = str(
                    item.get("name") or item.get("item_name") or "Unknown"
                ).strip()
                item_totals[item_name] = (
                    item_totals.get(item_name, 0) + quantity
                )

        total_subtotal += float(order["subtotal"] or 0)
        total_gst += float(order["gst"] or 0)

        grand_total = float(order["grand_total"] or 0)
        refund_amount = float(order["refund_amount"] or 0)
        total_spend += max(grand_total - refund_amount, 0)

    favorite_item = None
    favorite_quantity = 0
    if item_totals:
        favorite_item, favorite_quantity = sorted(
            item_totals.items(),
            key=lambda value: (-value[1], value[0].lower())
        )[0]

    last_order = orders[0] if orders else None

    return {
        "total_orders": total_orders,
        "cancelled_orders": cancelled_orders,
        "total_items": int(total_items) if float(total_items).is_integer() else round(total_items, 2),
        "total_subtotal": round(total_subtotal, 2),
        "total_gst": round(total_gst, 2),
        "total_spend": round(total_spend, 2),
        "favorite_item": favorite_item,
        "favorite_quantity": (
            int(favorite_quantity)
            if float(favorite_quantity).is_integer()
            else round(favorite_quantity, 2)
        ),
        "last_order_id": last_order["order_id"] if last_order else None,
        "last_order_date": last_order["order_date"] if last_order else None,
        "last_order_time": last_order["order_time"] if last_order else None,
        "last_order_status": last_order["order_status"] if last_order else None,
    }



def customer_restaurant_history():
    import json

    customer_id = input("Enter Customer ID : ").strip().upper()
    customer = get_customer_by_id(customer_id)

    if customer is None:
        print("Customer Not Found.")
        return

    orders = get_guest_restaurant_history(customer_id)

    print()
    print("=" * 80)
    print("GUEST RESTAURANT HISTORY")
    print("=" * 80)
    print("Customer ID :", customer["customer_id"])
    print("Name        :", customer["customer_name"])
    print("Mobile      :", customer["customer_mobile"] or "None")
    print("-" * 80)

    if not orders:
        print("No restaurant orders found for this guest.")
        print("=" * 80)
        return

    for index, order in enumerate(orders, start=1):
        print(f"Order #{index}")
        print("Order ID       :", order["order_id"])
        print("Order Date     :", order["order_date"] or "None")
        print("Order Time     :", order["order_time"] or "None")
        print("Table Number   :", order["table_number"] or "None")

        print("Items          :")
        try:
            cart = json.loads(order["cart"] or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            cart = []

        if not cart:
            print("  No item details available.")
        else:
            for item in cart:
                print(
                    f"  {item.get('name', 'Unknown')} x{item.get('quantity', 0)} "
                    f"= ₹{float(item.get('subtotal', 0) or 0):.2f}"
                )

        print("Subtotal       :", f"₹{float(order['subtotal'] or 0):.2f}")
        print("GST            :", f"₹{float(order['gst'] or 0):.2f}")
        print("Grand Total    :", f"₹{float(order['grand_total'] or 0):.2f}")

        if index < len(orders):
            print("-" * 80)

    summary = get_guest_restaurant_summary(customer_id)
    print("-" * 80)
    print("RESTAURANT SUMMARY")
    print("Total Orders    :", summary["total_orders"])
    print("Cancelled Orders:", summary["cancelled_orders"])
    print("Total Items     :", summary["total_items"])
    print("Total Subtotal  :", f"₹{summary['total_subtotal']:.2f}")
    print("Total GST       :", f"₹{summary['total_gst']:.2f}")
    print("Total Spend     :", f"₹{summary['total_spend']:.2f}")
    print(
        "Favourite Item  :",
        (
            f"{summary['favorite_item']} "
            f"(Qty {summary['favorite_quantity']})"
            if summary["favorite_item"]
            else "None"
        )
    )
    print("Last Order ID   :", summary["last_order_id"] or "None")
    print("Last Order Date :", summary["last_order_date"] or "None")
    print("Last Order Time :", summary["last_order_time"] or "None")
    print("Last Order Status:", summary["last_order_status"] or "None")
    print("=" * 80)


# CUSTOMER ID GENERATOR
# ============================================================

def get_next_customer_id():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT customer_id
            FROM customers
            WHERE customer_id LIKE 'CUST%'
            ORDER BY
                CAST(SUBSTR(customer_id, 5) AS INTEGER) DESC
            LIMIT 1
        """)

        record = cursor.fetchone()

        if record is None:

            return "CUST1001"

        last_id = record["customer_id"]

        try:
            last_number = int(last_id[4:])
        except (ValueError, TypeError):
            return "CUST1001"

        return f"CUST{last_number + 1}"

    finally:

        connection.close()

# ============================================================
# 4.5.2 — GUEST ↔ HOTEL RELATIONSHIP
# ============================================================

def create_guest_hotel_relationships_table():
    """
    Create the Guest ↔ Hotel relationship table.

    A guest is a global master record and may be associated
    with multiple hotels.

    This table stores the relationship and hotel-specific
    guest activity information.
    """

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guest_hotel_relationships (

                relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,

                customer_id TEXT NOT NULL,

                hotel_id INTEGER NOT NULL,

                first_visit_at TEXT,

                last_visit_at TEXT,

                visit_count INTEGER NOT NULL DEFAULT 0,

                is_active INTEGER NOT NULL DEFAULT 1,

                created_at TEXT NOT NULL,

                updated_at TEXT NOT NULL,

                UNIQUE(customer_id, hotel_id),

                FOREIGN KEY (customer_id)
                    REFERENCES customers(customer_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT,

                FOREIGN KEY (hotel_id)
                    REFERENCES hotels(hotel_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT

            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_guest_hotel_customer
            ON guest_hotel_relationships(customer_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_guest_hotel_hotel
            ON guest_hotel_relationships(hotel_id)
        """)

                # ====================================================
        # LEGACY GUEST → DEFAULT HOTEL MIGRATION
        # ====================================================
        #
        # Existing guests were created before the
        # Guest ↔ Hotel relationship architecture existed.
        #
        # Preserve them by associating them with the
        # default active hotel.
        #

        cursor.execute("""
            SELECT hotel_id
            FROM hotels
            WHERE hotel_code = ?
              AND is_active = 1
        """, ("YADAV-HOTEL",))

        default_hotel = cursor.fetchone()

        if default_hotel is not None:

            default_hotel_id = default_hotel["hotel_id"]

            cursor.execute("""
                INSERT OR IGNORE INTO guest_hotel_relationships (
                    customer_id,
                    hotel_id,
                    first_visit_at,
                    last_visit_at,
                    visit_count,
                    is_active,
                    created_at,
                    updated_at
                )
                SELECT
                    c.customer_id,
                    ?,
                    NULL,
                    NULL,
                    0,
                    1,
                    COALESCE(
                        c.created_time,
                        datetime('now')
                    ),
                    COALESCE(
                        c.updated_time,
                        c.created_time,
                        datetime('now')
                    )
                FROM customers c
                WHERE c.customer_id IS NOT NULL
            """, (default_hotel_id,))

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


def ensure_guest_hotel_relationship(
    customer_id,
    hotel_id=None
):
    """
    Create the Guest ↔ Hotel relationship if it does not exist.

    If the relationship already exists, the existing record
    is returned.

    This function is intentionally idempotent.
    """

    from database.hotel_context import get_current_hotel_id
    from datetime import datetime

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    connection = get_connection()

    try:

        cursor = connection.cursor()

        # ----------------------------------------------------
        # Validate guest
        # ----------------------------------------------------

        cursor.execute("""
            SELECT customer_id
            FROM customers
            WHERE customer_id = ?
        """, (customer_id,))

        guest = cursor.fetchone()

        if guest is None:
            raise ValueError(
                "Guest does not exist."
            )

        # ----------------------------------------------------
        # Validate active hotel
        # ----------------------------------------------------

        cursor.execute("""
            SELECT hotel_id
            FROM hotels
            WHERE hotel_id = ?
              AND is_active = 1
        """, (hotel_id,))

        hotel = cursor.fetchone()

        if hotel is None:
            raise ValueError(
                "Hotel does not exist or is inactive."
            )

        now = datetime.now().strftime(
            "%d-%m-%Y %I:%M:%S %p"
        )

        # ----------------------------------------------------
        # Existing relationship
        # ----------------------------------------------------

        cursor.execute("""
            SELECT *
            FROM guest_hotel_relationships
            WHERE customer_id = ?
              AND hotel_id = ?
        """, (
            customer_id,
            hotel_id
        ))

        relationship = cursor.fetchone()

        if relationship is not None:
            return relationship

        # ----------------------------------------------------
        # New relationship
        # ----------------------------------------------------

        cursor.execute("""
            INSERT INTO guest_hotel_relationships (
                customer_id,
                hotel_id,
                first_visit_at,
                last_visit_at,
                visit_count,
                is_active,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, NULL, NULL, 0, 1, ?, ?
            )
        """, (
            customer_id,
            hotel_id,
            now,
            now
        ))

        connection.commit()

        cursor.execute("""
            SELECT *
            FROM guest_hotel_relationships
            WHERE customer_id = ?
              AND hotel_id = ?
        """, (
            customer_id,
            hotel_id
        ))

        return cursor.fetchone()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


def get_guest_hotel_relationship(
    customer_id,
    hotel_id=None
):
    """
    Return the relationship between a guest and the
    current/selected hotel.
    """

    from database.hotel_context import get_current_hotel_id

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                r.*,
                h.hotel_code,
                h.hotel_name
            FROM guest_hotel_relationships r
            INNER JOIN hotels h
                ON h.hotel_id = r.hotel_id
            WHERE r.customer_id = ?
              AND r.hotel_id = ?
        """, (
            customer_id,
            hotel_id
        ))

        return cursor.fetchone()

    finally:

        connection.close()


def get_guest_hotels(customer_id):
    """
    Return all hotels associated with a guest.
    """

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                r.relationship_id,
                r.customer_id,
                r.hotel_id,
                h.hotel_code,
                h.hotel_name,
                r.first_visit_at,
                r.last_visit_at,
                r.visit_count,
                r.is_active,
                r.created_at,
                r.updated_at
            FROM guest_hotel_relationships r
            INNER JOIN hotels h
                ON h.hotel_id = r.hotel_id
            WHERE r.customer_id = ?
            ORDER BY h.hotel_name COLLATE NOCASE
        """, (customer_id,))

        return cursor.fetchall()

    finally:

        connection.close()


def get_hotel_guests(hotel_id=None):
    """
    Return guests associated with a hotel.

    When hotel_id is omitted, the current hotel context
    is used.
    """

    from database.hotel_context import get_current_hotel_id

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                c.*,
                r.first_visit_at,
                r.last_visit_at,
                r.visit_count,
                r.is_active AS hotel_guest_active
            FROM guest_hotel_relationships r
            INNER JOIN customers c
                ON c.customer_id = r.customer_id
            WHERE r.hotel_id = ?
            ORDER BY c.customer_name COLLATE NOCASE
        """, (hotel_id,))

        return cursor.fetchall()

    finally:

        connection.close()


def record_guest_hotel_visit(
    customer_id,
    hotel_id=None,
    visit_time=None,
    connection=None
):
    """
    Record a guest visit against the selected hotel.

    The visit counter is maintained per hotel.
    """

    from database.hotel_context import get_current_hotel_id
    from datetime import datetime

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    if visit_time is None:
        visit_time = datetime.now()

    if hasattr(visit_time, "strftime"):
        visit_time = visit_time.strftime(
            "%d-%m-%Y %I:%M:%S %p"
        )
    else:
        visit_time = str(visit_time)

    own_connection = connection is None

    if own_connection:
        connection = get_connection()

    try:

        cursor = connection.cursor()

        # Ensure relationship exists.
        cursor.execute("""
            SELECT relationship_id, visit_count
            FROM guest_hotel_relationships
            WHERE customer_id = ?
              AND hotel_id = ?
        """, (
            customer_id,
            hotel_id
        ))

        relationship = cursor.fetchone()

        if relationship is None:

            cursor.execute("""
                INSERT INTO guest_hotel_relationships (
                    customer_id,
                    hotel_id,
                    first_visit_at,
                    last_visit_at,
                    visit_count,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, 1, 1, ?, ?
                )
            """, (
                customer_id,
                hotel_id,
                visit_time,
                visit_time,
                visit_time,
                visit_time
            ))

        else:

            cursor.execute("""
                UPDATE guest_hotel_relationships
                SET
                    last_visit_at = ?,
                    visit_count = visit_count + 1,
                    is_active = 1,
                    updated_at = ?
                WHERE customer_id = ?
                  AND hotel_id = ?
            """, (
                visit_time,
                visit_time,
                customer_id,
                hotel_id
            ))

        if own_connection:
            connection.commit()

    except Exception:

        if own_connection:
            connection.rollback()
        raise

    finally:

        if own_connection:
            connection.close()


def get_guest_repeat_recognition(customer_id, hotel_id=None):
    """
    Return repeat-guest recognition information for one hotel.

    Recognition is based on the guest's hotel relationship visit_count
    and completed room stays, whichever is greater.
    """

    from database.hotel_context import get_current_hotel_id

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    customer_id = _normalize_customer_id(customer_id)
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                c.customer_id,
                c.customer_name,
                c.customer_mobile,
                COALESCE(r.visit_count, 0) AS visit_count,
                r.first_visit_at,
                r.last_visit_at
            FROM customers c
            LEFT JOIN guest_hotel_relationships r
                ON r.customer_id = c.customer_id
               AND r.hotel_id = ?
            WHERE c.customer_id = ?
            LIMIT 1
        """, (hotel_id, customer_id))

        guest = cursor.fetchone()

        if guest is None:
            return None

        cursor.execute("""
            SELECT COUNT(*) AS completed_stays
            FROM room_bookings
            WHERE customer_id = ?
              AND hotel_id = ?
              AND booking_status IN ('Checked-In', 'Checked-Out')
        """, (customer_id, hotel_id))

        completed_stays = int(cursor.fetchone()["completed_stays"] or 0)
        relationship_visits = int(guest["visit_count"] or 0)
        total_visits = max(relationship_visits, completed_stays)

        return {
            "customer_id": guest["customer_id"],
            "customer_name": guest["customer_name"],
            "customer_mobile": guest["customer_mobile"],
            "hotel_id": hotel_id,
            "visit_count": total_visits,
            "first_visit_at": guest["first_visit_at"],
            "last_visit_at": guest["last_visit_at"],
            "is_repeat_guest": total_visits > 0,
        }

    finally:
        connection.close()



def get_customer_lifecycle(customer_id, hotel_id=None):
    """
    Return the lifecycle state and activity summary for one guest.

    Lifecycle stages are derived from the guest's operational status
    and hotel stay history; no duplicate lifecycle status column is stored.
    """

    from database.hotel_context import get_current_hotel_id

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    customer_id = _normalize_customer_id(customer_id)
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                c.customer_id,
                c.customer_name,
                c.customer_mobile,
                c.guest_status,
                c.is_active,
                r.first_visit_at,
                r.last_visit_at,
                COALESCE(r.visit_count, 0) AS visit_count
            FROM customers c
            LEFT JOIN guest_hotel_relationships r
                ON r.customer_id = c.customer_id
               AND r.hotel_id = ?
            WHERE c.customer_id = ?
            LIMIT 1
        """, (hotel_id, customer_id))

        customer = cursor.fetchone()
        if customer is None:
            return None

        cursor.execute("""
            SELECT
                COUNT(*) AS total_bookings,
                SUM(
                    CASE
                        WHEN booking_status IN ('Checked-In', 'Checked-Out')
                        THEN 1 ELSE 0
                    END
                ) AS completed_stays
            FROM room_bookings
            WHERE customer_id = ?
              AND hotel_id = ?
        """, (customer_id, hotel_id))
        booking_stats = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) AS restaurant_orders
            FROM orders
            WHERE customer_id = ?
              AND hotel_id = ?
        """, (customer_id, hotel_id))
        restaurant_orders = cursor.fetchone()["restaurant_orders"] or 0

        cursor.execute("""
            SELECT COUNT(*) AS feedback_count
            FROM feedback
            WHERE customer_id = ?
              AND hotel_id = ?
        """, (customer_id, hotel_id))
        feedback_count = cursor.fetchone()["feedback_count"] or 0

        visit_count = int(customer["visit_count"] or 0)
        completed_stays = int(booking_stats["completed_stays"] or 0)
        effective_visits = max(visit_count, completed_stays)
        guest_status = customer["guest_status"] or "Active"

        if guest_status == "Blacklisted":
            lifecycle_stage = "Blacklisted"
        elif guest_status == "Inactive":
            lifecycle_stage = "Inactive"
        elif effective_visits >= 2:
            lifecycle_stage = "Returning"
        elif effective_visits == 1:
            lifecycle_stage = "Active"
        else:
            lifecycle_stage = "New"

        return {
            "customer_id": customer["customer_id"],
            "customer_name": customer["customer_name"],
            "customer_mobile": customer["customer_mobile"],
            "hotel_id": hotel_id,
            "guest_status": guest_status,
            "is_active": int(customer["is_active"] or 0),
            "lifecycle_stage": lifecycle_stage,
            "visit_count": effective_visits,
            "completed_stays": completed_stays,
            "total_bookings": int(booking_stats["total_bookings"] or 0),
            "restaurant_orders": int(restaurant_orders),
            "feedback_count": int(feedback_count),
            "first_visit_at": customer["first_visit_at"],
            "last_visit_at": customer["last_visit_at"],
        }

    finally:
        connection.close()


def customer_lifecycle(hotel_id=None):
    """Display the lifecycle and activity summary for one guest."""

    customer_id = input("Enter Customer ID : ").strip().upper()
    if not customer_id:
        print("Customer ID is required.")
        return

    lifecycle = get_customer_lifecycle(customer_id, hotel_id)
    if lifecycle is None:
        print("Customer Not Found.")
        return

    print("=" * 70)
    print("                  CUSTOMER LIFECYCLE")
    print("=" * 70)
    print("Customer ID       :", lifecycle["customer_id"])
    print("Customer Name     :", lifecycle["customer_name"])
    print("Mobile            :", lifecycle["customer_mobile"])
    print("Guest Status      :", lifecycle["guest_status"])
    print("Lifecycle Stage   :", lifecycle["lifecycle_stage"])
    print("Hotel Visits      :", lifecycle["visit_count"])
    print("Completed Stays   :", lifecycle["completed_stays"])
    print("Total Bookings    :", lifecycle["total_bookings"])
    print("Restaurant Orders :", lifecycle["restaurant_orders"])
    print("Feedback Count    :", lifecycle["feedback_count"])
    print("First Visit       :", lifecycle["first_visit_at"] or "N/A")
    print("Last Visit        :", lifecycle["last_visit_at"] or "N/A")
    print("=" * 70)

def deactivate_guest_hotel_relationship(
    customer_id,
    hotel_id=None
):
    """
    Deactivate a guest's relationship with a hotel
    without deleting the relationship or guest master.
    """

    from database.hotel_context import get_current_hotel_id
    from datetime import datetime

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    connection = get_connection()

    try:

        cursor = connection.cursor()

        updated_time = datetime.now().strftime(
            "%d-%m-%Y %I:%M:%S %p"
        )

        cursor.execute("""
            UPDATE guest_hotel_relationships
            SET
                is_active = 0,
                updated_at = ?
            WHERE customer_id = ?
              AND hotel_id = ?
        """, (
            updated_time,
            customer_id,
            hotel_id
        ))

        connection.commit()

        return cursor.rowcount > 0

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()

def resolve_guest_for_booking(
    customer_name,
    customer_mobile,
    customer_email=None,
    customer_address=None,
    hotel_id=None
):
    from database.hotel_context import get_current_hotel_id
    from datetime import datetime

    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    mobile = str(customer_mobile or "").strip()

    if not mobile:
        raise ValueError("Guest mobile number is required for booking.")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT customer_id
            FROM customers
            WHERE customer_mobile = ?
            ORDER BY created_time ASC
            LIMIT 1
        """, (mobile,))

        customer = cursor.fetchone()

    finally:
        connection.close()

    if customer:
        customer_id = customer["customer_id"]
    else:
        customer_id = get_next_customer_id()

        save_customer(
            customer_id,
            str(customer_name or "").strip(),
            mobile,
            str(customer_email or "").strip() or None,
            str(customer_address or "").strip() or None,
            datetime.now()
        )

    ensure_guest_hotel_relationship(
        customer_id,
        hotel_id
    )

    return customer_id