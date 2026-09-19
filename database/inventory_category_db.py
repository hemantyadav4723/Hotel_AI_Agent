from datetime import datetime
import sqlite3

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


ACTIVE_STATUS = "Active"
INACTIVE_STATUS = "Inactive"


def _current_timestamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _normalize_name(value):
    name = " ".join(str(value or "").strip().split())
    if not name:
        raise ValueError("Category Name cannot be empty.")
    if len(name) < 2:
        raise ValueError("Category Name must contain at least 2 characters.")
    return name


def _normalize_id(value):
    category_id = str(value or "").strip().upper()
    if not category_id:
        raise ValueError("Category ID cannot be empty.")
    return category_id


def _table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row["name"] for row in cursor.fetchall()}


def _next_category_id(cursor):
    row = cursor.execute("""
        SELECT category_id
        FROM inventory_categories
        WHERE category_id LIKE 'CAT-%'
        ORDER BY CAST(SUBSTR(category_id, 5) AS INTEGER) DESC
        LIMIT 1
    """).fetchone()

    next_number = 1
    if row:
        try:
            next_number = int(str(row["category_id"])[4:]) + 1
        except (TypeError, ValueError):
            next_number = 1

    while True:
        category_id = f"CAT-{next_number:03d}"
        exists = cursor.execute(
            "SELECT 1 FROM inventory_categories WHERE category_id = ?",
            (category_id,)
        ).fetchone()
        if exists is None:
            return category_id
        next_number += 1


def _ensure_category_for_legacy_value(cursor, hotel_id, category_name):
    category_name = _normalize_name(category_name)

    row = cursor.execute("""
        SELECT category_id
        FROM inventory_categories
        WHERE hotel_id = ?
          AND lower(trim(category_name)) = lower(trim(?))
        LIMIT 1
    """, (hotel_id, category_name)).fetchone()

    if row:
        return row["category_id"]

    category_id = _next_category_id(cursor)
    now = _current_timestamp()
    cursor.execute("""
        INSERT INTO inventory_categories(
            category_id, hotel_id, category_name, status, created_at, updated_at
        )
        VALUES(?, ?, ?, 'Active', ?, ?)
    """, (category_id, hotel_id, category_name, now, now))
    return category_id


def create_inventory_categories_table():
    """Create the inventory category master and migrate legacy text categories."""
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_categories(
                category_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                category_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (hotel_id)
                    REFERENCES hotels(hotel_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            )
        """)

        columns = _table_columns(cursor, "inventory_categories")
        if "hotel_id" not in columns:
            cursor.execute(
                "ALTER TABLE inventory_categories ADD COLUMN hotel_id INTEGER"
            )
        if "status" not in columns:
            cursor.execute(
                "ALTER TABLE inventory_categories ADD COLUMN status TEXT DEFAULT 'Active'"
            )
        if "created_at" not in columns:
            cursor.execute(
                "ALTER TABLE inventory_categories ADD COLUMN created_at TEXT"
            )
        if "updated_at" not in columns:
            cursor.execute(
                "ALTER TABLE inventory_categories ADD COLUMN updated_at TEXT"
            )

        hotel_id = get_current_hotel_id()
        now = _current_timestamp()

        cursor.execute("""
            UPDATE inventory_categories
            SET hotel_id = ?
            WHERE hotel_id IS NULL
        """, (hotel_id,))
        cursor.execute("""
            UPDATE inventory_categories
            SET status = 'Active'
            WHERE status IS NULL OR TRIM(status) = ''
        """)
        cursor.execute("""
            UPDATE inventory_categories
            SET created_at = ?
            WHERE created_at IS NULL OR TRIM(created_at) = ''
        """, (now,))
        cursor.execute("""
            UPDATE inventory_categories
            SET updated_at = created_at
            WHERE updated_at IS NULL OR TRIM(updated_at) = ''
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_category_hotel_name
            ON inventory_categories(hotel_id, lower(trim(category_name)))
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_category_hotel_status
            ON inventory_categories(hotel_id, status, category_name)
        """)

        # 4.9.1 stored category as free text. Keep that field for compatibility,
        # but add a proper master reference so new inventory data is relational.
        inventory_exists = cursor.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'inventory'
        """).fetchone()

        if inventory_exists:
            inventory_columns = _table_columns(cursor, "inventory")
            if "category_id" not in inventory_columns:
                cursor.execute(
                    "ALTER TABLE inventory ADD COLUMN category_id TEXT"
                )

            legacy_rows = cursor.execute("""
                SELECT DISTINCT hotel_id, TRIM(category) AS category_name
                FROM inventory
                WHERE category IS NOT NULL
                  AND TRIM(category) <> ''
            """).fetchall()

            for row in legacy_rows:
                legacy_hotel_id = row["hotel_id"] or hotel_id
                category_name = row["category_name"]
                category_id = _ensure_category_for_legacy_value(
                    cursor,
                    legacy_hotel_id,
                    category_name
                )
                cursor.execute("""
                    UPDATE inventory
                    SET category_id = ?
                    WHERE hotel_id = ?
                      AND lower(trim(category)) = lower(trim(?))
                      AND (category_id IS NULL OR TRIM(category_id) = '')
                """, (
                    category_id,
                    legacy_hotel_id,
                    category_name
                ))

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_inventory_hotel_category_id
                ON inventory(hotel_id, category_id)
            """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_category(category_id, category_name):
    require_current_user_permission("Inventory", "Create")
    category_id = _normalize_id(category_id)
    category_name = _normalize_name(category_name)
    hotel_id = get_current_hotel_id()
    now = _current_timestamp()

    connection = get_connection()
    try:
        cursor = connection.cursor()

        if cursor.execute(
            "SELECT 1 FROM inventory_categories WHERE category_id = ?",
            (category_id,)
        ).fetchone():
            raise ValueError("Category ID already exists.")

        if cursor.execute("""
            SELECT 1
            FROM inventory_categories
            WHERE hotel_id = ?
              AND lower(trim(category_name)) = lower(trim(?))
        """, (hotel_id, category_name)).fetchone():
            raise ValueError("Category Name already exists for the current hotel.")

        cursor.execute("""
            INSERT INTO inventory_categories(
                category_id, hotel_id, category_name, status, created_at, updated_at
            )
            VALUES(?, ?, ?, 'Active', ?, ?)
        """, (category_id, hotel_id, category_name, now, now))

        connection.commit()
    except sqlite3.IntegrityError as exc:
        connection.rollback()
        raise ValueError(f"Unable to save category: {exc}") from exc
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_category_options(include_inactive=False):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        query = """
            SELECT category_id, category_name, status
            FROM inventory_categories
            WHERE hotel_id = ?
        """
        params = [hotel_id]
        if not include_inactive:
            query += " AND status = 'Active'"
        query += " ORDER BY category_name COLLATE NOCASE"
        return connection.execute(query, params).fetchall()
    finally:
        connection.close()


def get_category(category_id, include_inactive=False):
    category_id = _normalize_id(category_id)
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        query = """
            SELECT category_id, hotel_id, category_name, status,
                   created_at, updated_at
            FROM inventory_categories
            WHERE hotel_id = ? AND category_id = ?
        """
        params = [hotel_id, category_id]
        if not include_inactive:
            query += " AND status = 'Active'"
        return connection.execute(query, params).fetchone()
    finally:
        connection.close()


def view_categories():
    require_current_user_permission("Inventory", "View")
    records = get_category_options(include_inactive=True)

    print("=" * 72)
    print("                         INVENTORY CATEGORIES")
    print("=" * 72)

    if not records:
        print("No Inventory Categories Found.")
        return

    for record in records:
        print("-" * 72)
        print("Category ID   :", record["category_id"])
        print("Category Name :", record["category_name"])
        print("Status        :", record["status"])
    print("-" * 72)


def search_category():
    require_current_user_permission("Inventory", "View")
    category_id = input("Enter Category ID : ").strip().upper()
    record = get_category(category_id, include_inactive=True)

    if not record:
        print("Category Not Found.")
        return

    print("=" * 72)
    print("                         CATEGORY DETAILS")
    print("=" * 72)
    print("Category ID   :", record["category_id"])
    print("Category Name :", record["category_name"])
    print("Status        :", record["status"])
    print("Created At    :", record["created_at"] or "N/A")
    print("Updated At    :", record["updated_at"] or "N/A")
    print("=" * 72)


def update_category():
    require_current_user_permission("Inventory", "Update")
    category_id = input("Enter Category ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT *
            FROM inventory_categories
            WHERE hotel_id = ? AND category_id = ?
        """, (hotel_id, category_id)).fetchone()

        if not record:
            print("Category Not Found.")
            return

        new_name = _normalize_name(input(
            f"Enter New Category Name ({record['category_name']}) : "
        ))

        duplicate = cursor.execute("""
            SELECT 1
            FROM inventory_categories
            WHERE hotel_id = ?
              AND category_id != ?
              AND lower(trim(category_name)) = lower(trim(?))
        """, (hotel_id, category_id, new_name)).fetchone()

        if duplicate:
            print("Category Name already exists for the current hotel.")
            return

        old_name = record["category_name"]
        now = _current_timestamp()

        cursor.execute("""
            UPDATE inventory_categories
            SET category_name = ?, updated_at = ?
            WHERE hotel_id = ? AND category_id = ?
        """, (new_name, now, hotel_id, category_id))

        # Keep 4.9.1's legacy text field synchronized until the later
        # integrity/security stage can enforce the relational reference fully.
        cursor.execute("""
            UPDATE inventory
            SET category = ?, updated_at = ?
            WHERE hotel_id = ? AND category_id = ?
        """, (new_name, now, hotel_id, category_id))

        connection.commit()
        print("Category Updated Successfully.")

    except ValueError as exc:
        connection.rollback()
        print(f"Invalid Category Data: {exc}")
    except Exception as exc:
        connection.rollback()
        print(f"Error updating category: {exc}")
    finally:
        connection.close()


def _set_status(status):
    category_id = input("Enter Category ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT category_name, status
            FROM inventory_categories
            WHERE hotel_id = ? AND category_id = ?
        """, (hotel_id, category_id)).fetchone()

        if not record:
            print("Category Not Found.")
            return

        if record["status"] == status:
            print(f"Category is already {status}.")
            return

        cursor.execute("""
            UPDATE inventory_categories
            SET status = ?, updated_at = ?
            WHERE hotel_id = ? AND category_id = ?
        """, (status, _current_timestamp(), hotel_id, category_id))

        connection.commit()
        print(f"Category {status} Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error changing category status: {exc}")
    finally:
        connection.close()


def deactivate_category():
    require_current_user_permission("Inventory", "Update")
    _set_status(INACTIVE_STATUS)


def activate_category():
    require_current_user_permission("Inventory", "Update")
    _set_status(ACTIVE_STATUS)


def delete_category():
    require_current_user_permission("Inventory", "Delete")
    category_id = input("Enter Category ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT category_name
            FROM inventory_categories
            WHERE hotel_id = ? AND category_id = ?
        """, (hotel_id, category_id)).fetchone()

        if not record:
            print("Category Not Found.")
            return

        dependency = cursor.execute("""
            SELECT 1
            FROM inventory
            WHERE hotel_id = ?
              AND (
                    category_id = ?
                    OR lower(trim(category)) = lower(trim(?))
                  )
            LIMIT 1
        """, (hotel_id, category_id, record["category_name"])).fetchone()

        if dependency:
            print(
                "Category is assigned to inventory items and cannot be deleted. "
                "Deactivate it instead to preserve item history."
            )
            return

        cursor.execute("""
            DELETE FROM inventory_categories
            WHERE hotel_id = ? AND category_id = ?
        """, (hotel_id, category_id))

        connection.commit()
        print("Category Deleted Successfully.")

    except Exception as exc:
        connection.rollback()
        print(f"Error deleting category: {exc}")
    finally:
        connection.close()
