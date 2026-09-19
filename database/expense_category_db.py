from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


ACTIVE_STATUS = "Active"
INACTIVE_STATUS = "Inactive"


def _current_timestamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _resolve_hotel_id(hotel_id=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    try:
        return int(hotel_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid hotel context.")


def _normalize_name(value):
    name = " ".join(str(value or "").strip().split())
    if not name:
        raise ValueError("Expense Category Name cannot be empty.")
    if len(name) < 2:
        raise ValueError("Expense Category Name must contain at least 2 characters.")
    if len(name) > 100:
        raise ValueError("Expense Category Name cannot exceed 100 characters.")
    return name


def _normalize_id(value):
    category_id = str(value or "").strip().upper()
    if not category_id:
        raise ValueError("Expense Category ID cannot be empty.")
    if len(category_id) > 30:
        raise ValueError("Expense Category ID cannot exceed 30 characters.")
    return category_id


def create_expense_categories_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expense_categories(
                category_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                category_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(hotel_id, category_name)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_expense_categories_hotel_status
            ON expense_categories(hotel_id, status, category_name)
        """)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _next_category_id(cursor):
    rows = cursor.execute("""
        SELECT category_id
        FROM expense_categories
        WHERE category_id LIKE 'EXP-CAT-%'
        ORDER BY category_id DESC
    """).fetchall()

    highest = 0
    for row in rows:
        try:
            number = int(str(row["category_id"]).split("-")[-1])
            highest = max(highest, number)
        except (TypeError, ValueError):
            continue

    candidate = highest + 1
    while True:
        category_id = f"EXP-CAT-{candidate:03d}"
        exists = cursor.execute(
            "SELECT 1 FROM expense_categories WHERE category_id = ?",
            (category_id,)
        ).fetchone()
        if exists is None:
            return category_id
        candidate += 1


def add_expense_category(category_name, hotel_id=None):
    require_current_user_permission("Expenses", "Create")
    hotel_id = _resolve_hotel_id(hotel_id)
    category_name = _normalize_name(category_name)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        duplicate = cursor.execute("""
            SELECT category_id
            FROM expense_categories
            WHERE hotel_id = ?
              AND lower(trim(category_name)) = lower(trim(?))
        """, (hotel_id, category_name)).fetchone()
        if duplicate:
            raise ValueError("Expense Category already exists.")

        category_id = _next_category_id(cursor)
        now = _current_timestamp()
        cursor.execute("""
            INSERT INTO expense_categories(
                category_id, hotel_id, category_name, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            category_id, hotel_id, category_name,
            ACTIVE_STATUS, now, now
        ))
        connection.commit()
        return category_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_expense_categories(hotel_id=None, include_inactive=False):
    require_current_user_permission("Expenses", "View")
    hotel_id = _resolve_hotel_id(hotel_id)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = """
            SELECT category_id, hotel_id, category_name, status,
                   created_at, updated_at
            FROM expense_categories
            WHERE hotel_id = ?
        """
        params = [hotel_id]
        if not include_inactive:
            query += " AND status = ?"
            params.append(ACTIVE_STATUS)
        query += " ORDER BY category_name COLLATE NOCASE"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()



def _ensure_category_for_legacy_value(cursor, hotel_id, category_name):
    """Return/create an expense category while migrating legacy expense data."""
    hotel_id = _resolve_hotel_id(hotel_id)
    category_name = _normalize_name(category_name)

    existing = cursor.execute("""
        SELECT category_id
        FROM expense_categories
        WHERE hotel_id = ?
          AND lower(trim(category_name)) = lower(trim(?))
        LIMIT 1
    """, (hotel_id, category_name)).fetchone()

    if existing:
        return existing["category_id"]

    category_id = _next_category_id(cursor)
    now = _current_timestamp()

    cursor.execute("""
        INSERT INTO expense_categories(
            category_id, hotel_id, category_name, status,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        category_id,
        hotel_id,
        category_name,
        ACTIVE_STATUS,
        now,
        now,
    ))
    return category_id


def get_expense_category(category_id, hotel_id=None, include_inactive=False):
    require_current_user_permission("Expenses", "View")
    hotel_id = _resolve_hotel_id(hotel_id)
    category_id = _normalize_id(category_id)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = """
            SELECT category_id, hotel_id, category_name, status,
                   created_at, updated_at
            FROM expense_categories
            WHERE hotel_id = ? AND category_id = ?
        """
        params = [hotel_id, category_id]
        if not include_inactive:
            query += " AND status = ?"
            params.append(ACTIVE_STATUS)
        return cursor.execute(query, params).fetchone()
    finally:
        connection.close()


def update_expense_category(category_id, category_name, hotel_id=None):
    require_current_user_permission("Expenses", "Update")
    hotel_id = _resolve_hotel_id(hotel_id)
    category_id = _normalize_id(category_id)
    category_name = _normalize_name(category_name)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        current = cursor.execute("""
            SELECT category_name
            FROM expense_categories
            WHERE hotel_id = ? AND category_id = ?
        """, (hotel_id, category_id)).fetchone()
        if current is None:
            raise ValueError("Expense Category not found.")

        duplicate = cursor.execute("""
            SELECT category_id
            FROM expense_categories
            WHERE hotel_id = ?
              AND lower(trim(category_name)) = lower(trim(?))
              AND category_id != ?
        """, (hotel_id, category_name, category_id)).fetchone()
        if duplicate:
            raise ValueError("Expense Category already exists.")

        now = _current_timestamp()
        cursor.execute("""
            UPDATE expense_categories
            SET category_name = ?, updated_at = ?
            WHERE hotel_id = ? AND category_id = ?
        """, (category_name, now, hotel_id, category_id))

        # Keep existing legacy text-based expense records synchronized.
        cursor.execute("""
            UPDATE expenses
            SET category = ?
            WHERE category_id = ?
              AND hotel_id = ?
        """, (category_name, category_id, hotel_id))

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def set_expense_category_status(category_id, status, hotel_id=None):
    require_current_user_permission("Expenses", "Update")
    hotel_id = _resolve_hotel_id(hotel_id)
    category_id = _normalize_id(category_id)
    status = str(status or "").strip().title()
    if status not in (ACTIVE_STATUS, INACTIVE_STATUS):
        raise ValueError("Invalid expense category status.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        if cursor.execute("""
            SELECT 1 FROM expense_categories
            WHERE hotel_id = ? AND category_id = ?
        """, (hotel_id, category_id)).fetchone() is None:
            raise ValueError("Expense Category not found.")

        cursor.execute("""
            UPDATE expense_categories
            SET status = ?, updated_at = ?
            WHERE hotel_id = ? AND category_id = ?
        """, (status, _current_timestamp(), hotel_id, category_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_expense_category(category_id, hotel_id=None):
    require_current_user_permission("Expenses", "Delete")
    hotel_id = _resolve_hotel_id(hotel_id)
    category_id = _normalize_id(category_id)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT category_name
            FROM expense_categories
            WHERE hotel_id = ? AND category_id = ?
        """, (hotel_id, category_id)).fetchone()
        if record is None:
            raise ValueError("Expense Category not found.")

        # Protect category history. The current expense table is legacy text
        # based, so check both future category_id data and existing category text.
        try:
            used = cursor.execute("""
                SELECT 1
                FROM expenses
                WHERE (category_id = ? AND hotel_id = ?)
                   OR (hotel_id = ? AND lower(trim(category)) = lower(trim(?)))
                LIMIT 1
            """, (category_id, hotel_id, hotel_id, record["category_name"])).fetchone()
        except Exception:
            used = cursor.execute("""
                SELECT 1
                FROM expenses
                WHERE lower(trim(category)) = lower(trim(?))
                LIMIT 1
            """, (record["category_name"],)).fetchone()

        if used:
            raise ValueError(
                "Expense Category is already used by an expense and cannot be deleted."
            )

        cursor.execute("""
            DELETE FROM expense_categories
            WHERE hotel_id = ? AND category_id = ?
        """, (hotel_id, category_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def expense_category_management():
    while True:
        print("=" * 60)
        print("        EXPENSE CATEGORY MANAGEMENT")
        print("=" * 60)
        print("1. Add Expense Category")
        print("2. View Expense Categories")
        print("3. Search Expense Category")
        print("4. Update Expense Category")
        print("5. Deactivate Category")
        print("6. Activate Category")
        print("7. Delete Expense Category")
        print("8. Back")

        choice = input("Enter Choice : ").strip()

        try:
            if choice == "1":
                name = input("Category Name : ")
                category_id = add_expense_category(name)
                print(f"Expense Category Added Successfully. ID: {category_id}")
            elif choice == "2":
                records = get_expense_categories(include_inactive=True)
                if not records:
                    print("No Expense Categories Found.")
                for record in records:
                    print("-" * 60)
                    print("Category ID   :", record["category_id"])
                    print("Category Name :", record["category_name"])
                    print("Status        :", record["status"])
            elif choice == "3":
                category_id = input("Enter Category ID : ").strip().upper()
                record = get_expense_category(category_id, include_inactive=True)
                if record is None:
                    print("Expense Category Not Found.")
                else:
                    print("-" * 60)
                    print("Category ID   :", record["category_id"])
                    print("Category Name :", record["category_name"])
                    print("Status        :", record["status"])
            elif choice == "4":
                category_id = input("Enter Category ID : ").strip().upper()
                record = get_expense_category(category_id, include_inactive=True)
                if record is None:
                    print("Expense Category Not Found.")
                    continue
                name = input(
                    f"New Category Name ({record['category_name']}) : "
                ).strip() or record["category_name"]
                update_expense_category(category_id, name)
                print("Expense Category Updated Successfully.")
            elif choice in ("5", "6"):
                category_id = input("Enter Category ID : ").strip().upper()
                status = INACTIVE_STATUS if choice == "5" else ACTIVE_STATUS
                set_expense_category_status(category_id, status)
                print(f"Expense Category {status} Successfully.")
            elif choice == "7":
                category_id = input("Enter Category ID : ").strip().upper()
                delete_expense_category(category_id)
                print("Expense Category Deleted Successfully.")
            elif choice == "8":
                break
            else:
                print("Invalid Choice.")
        except ValueError as exc:
            print(f"Error: {exc}")

        if choice != "8":
            input("\nPress Enter...")


def get_active_expense_category_options(hotel_id=None):
    return get_expense_categories(hotel_id=hotel_id, include_inactive=False)
