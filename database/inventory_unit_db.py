from datetime import datetime
import sqlite3

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


ACTIVE_STATUS = "Active"
INACTIVE_STATUS = "Inactive"


def _current_timestamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _normalize_id(value):
    unit_id = str(value or "").strip().upper()
    if not unit_id:
        raise ValueError("Unit ID cannot be empty.")
    return unit_id


def _normalize_name(value):
    name = " ".join(str(value or "").strip().split())
    if not name:
        raise ValueError("Unit Name cannot be empty.")
    if len(name) < 2:
        raise ValueError("Unit Name must contain at least 2 characters.")
    return name


def _normalize_symbol(value):
    symbol = " ".join(str(value or "").strip().split()).upper()
    if not symbol:
        raise ValueError("Unit Symbol cannot be empty.")
    if len(symbol) > 20:
        raise ValueError("Unit Symbol cannot exceed 20 characters.")
    return symbol


def _table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row["name"] for row in cursor.fetchall()}


def _add_column(cursor, table_name, column_definition):
    column_name = column_definition.split()[0]
    columns = _table_columns(cursor, table_name)
    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"
        )


def _next_unit_id(cursor):
    row = cursor.execute("""
        SELECT unit_id
        FROM inventory_units
        WHERE unit_id LIKE 'UNIT-%'
        ORDER BY CAST(SUBSTR(unit_id, 6) AS INTEGER) DESC
        LIMIT 1
    """).fetchone()

    next_number = 1
    if row:
        try:
            next_number = int(str(row["unit_id"])[5:]) + 1
        except (TypeError, ValueError):
            next_number = 1

    while True:
        unit_id = f"UNIT-{next_number:03d}"
        exists = cursor.execute(
            "SELECT 1 FROM inventory_units WHERE unit_id = ?",
            (unit_id,)
        ).fetchone()
        if exists is None:
            return unit_id
        next_number += 1


def _ensure_unit_for_legacy_value(cursor, hotel_id, unit_value):
    unit_value = _normalize_name(unit_value)
    unit_symbol = _normalize_symbol(unit_value)

    row = cursor.execute("""
        SELECT unit_id
        FROM inventory_units
        WHERE hotel_id = ?
          AND (
                lower(trim(unit_name)) = lower(trim(?))
                OR lower(trim(unit_symbol)) = lower(trim(?))
              )
        LIMIT 1
    """, (hotel_id, unit_value, unit_symbol)).fetchone()

    if row:
        return row["unit_id"]

    unit_id = _next_unit_id(cursor)
    now = _current_timestamp()
    cursor.execute("""
        INSERT INTO inventory_units(
            unit_id,
            hotel_id,
            unit_name,
            unit_symbol,
            status,
            created_at,
            updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?)
    """, (
        unit_id,
        hotel_id,
        unit_value,
        unit_symbol,
        ACTIVE_STATUS,
        now,
        now
    ))
    return unit_id


def create_inventory_units_table():
    """Create the inventory unit master and migrate legacy unit text."""
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_units(
                unit_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                unit_name TEXT NOT NULL,
                unit_symbol TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (hotel_id)
                    REFERENCES hotels(hotel_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            )
        """)

        _add_column(cursor, "inventory_units", "hotel_id INTEGER")
        _add_column(cursor, "inventory_units", "unit_name TEXT")
        _add_column(cursor, "inventory_units", "unit_symbol TEXT")
        _add_column(cursor, "inventory_units", "status TEXT DEFAULT 'Active'")
        _add_column(cursor, "inventory_units", "created_at TEXT")
        _add_column(cursor, "inventory_units", "updated_at TEXT")

        hotel_id = get_current_hotel_id()
        now = _current_timestamp()

        cursor.execute("""
            UPDATE inventory_units
            SET hotel_id = ?
            WHERE hotel_id IS NULL
        """, (hotel_id,))
        cursor.execute("""
            UPDATE inventory_units
            SET status = ?
            WHERE status IS NULL OR TRIM(status) = ''
        """, (ACTIVE_STATUS,))
        cursor.execute("""
            UPDATE inventory_units
            SET created_at = ?
            WHERE created_at IS NULL OR TRIM(created_at) = ''
        """, (now,))
        cursor.execute("""
            UPDATE inventory_units
            SET updated_at = created_at
            WHERE updated_at IS NULL OR TRIM(updated_at) = ''
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_unit_hotel_name
            ON inventory_units(hotel_id, lower(trim(unit_name)))
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_unit_hotel_symbol
            ON inventory_units(hotel_id, lower(trim(unit_symbol)))
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_unit_hotel_status
            ON inventory_units(hotel_id, status, unit_name)
        """)

        # 4.9.1 stored the unit as free text. Preserve that column for
        # compatibility while adding a proper Unit Master relationship.
        inventory_exists = cursor.execute("""
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'inventory'
        """).fetchone()

        if inventory_exists:
            _add_column(cursor, "inventory", "unit_id TEXT")

            legacy_rows = cursor.execute("""
                SELECT DISTINCT hotel_id, TRIM(unit) AS unit_value
                FROM inventory
                WHERE unit IS NOT NULL
                  AND TRIM(unit) <> ''
            """).fetchall()

            for row in legacy_rows:
                legacy_hotel_id = row["hotel_id"] or hotel_id
                unit_value = row["unit_value"]
                unit_id = _ensure_unit_for_legacy_value(
                    cursor,
                    legacy_hotel_id,
                    unit_value
                )

                cursor.execute("""
                    UPDATE inventory
                    SET unit_id = ?
                    WHERE hotel_id = ?
                      AND lower(trim(unit)) = lower(trim(?))
                      AND (unit_id IS NULL OR TRIM(unit_id) = '')
                """, (
                    unit_id,
                    legacy_hotel_id,
                    unit_value
                ))

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_inventory_hotel_unit_id
                ON inventory(hotel_id, unit_id)
            """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_unit(unit_id, unit_name, unit_symbol):
    require_current_user_permission("Inventory", "Create")
    unit_id = _normalize_id(unit_id)
    unit_name = _normalize_name(unit_name)
    unit_symbol = _normalize_symbol(unit_symbol)
    hotel_id = get_current_hotel_id()
    now = _current_timestamp()

    connection = get_connection()
    try:
        cursor = connection.cursor()

        if cursor.execute(
            "SELECT 1 FROM inventory_units WHERE unit_id = ?",
            (unit_id,)
        ).fetchone():
            raise ValueError("Unit ID already exists.")

        if cursor.execute("""
            SELECT 1
            FROM inventory_units
            WHERE hotel_id = ?
              AND lower(trim(unit_name)) = lower(trim(?))
        """, (hotel_id, unit_name)).fetchone():
            raise ValueError("Unit Name already exists for the current hotel.")

        if cursor.execute("""
            SELECT 1
            FROM inventory_units
            WHERE hotel_id = ?
              AND lower(trim(unit_symbol)) = lower(trim(?))
        """, (hotel_id, unit_symbol)).fetchone():
            raise ValueError("Unit Symbol already exists for the current hotel.")

        cursor.execute("""
            INSERT INTO inventory_units(
                unit_id,
                hotel_id,
                unit_name,
                unit_symbol,
                status,
                created_at,
                updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
        """, (
            unit_id,
            hotel_id,
            unit_name,
            unit_symbol,
            ACTIVE_STATUS,
            now,
            now
        ))

        connection.commit()

    except sqlite3.IntegrityError as exc:
        connection.rollback()
        raise ValueError(f"Unable to save unit: {exc}") from exc
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_unit_options(include_inactive=False):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        query = """
            SELECT unit_id, unit_name, unit_symbol, status
            FROM inventory_units
            WHERE hotel_id = ?
        """
        params = [hotel_id]
        if not include_inactive:
            query += " AND status = 'Active'"
        query += " ORDER BY unit_name COLLATE NOCASE, unit_id"
        return connection.execute(query, params).fetchall()
    finally:
        connection.close()


def get_unit(unit_id, include_inactive=False):
    unit_id = _normalize_id(unit_id)
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        query = """
            SELECT unit_id, hotel_id, unit_name, unit_symbol, status,
                   created_at, updated_at
            FROM inventory_units
            WHERE hotel_id = ? AND unit_id = ?
        """
        params = [hotel_id, unit_id]
        if not include_inactive:
            query += " AND status = 'Active'"
        return connection.execute(query, params).fetchone()
    finally:
        connection.close()


def view_units():
    require_current_user_permission("Inventory", "View")
    records = get_unit_options(include_inactive=True)

    print("=" * 72)
    print("                         INVENTORY UNITS")
    print("=" * 72)

    if not records:
        print("No Inventory Units Found.")
        return

    for record in records:
        print("-" * 72)
        print("Unit ID       :", record["unit_id"])
        print("Unit Name     :", record["unit_name"])
        print("Unit Symbol   :", record["unit_symbol"])
        print("Status        :", record["status"])
    print("-" * 72)


def search_unit():
    require_current_user_permission("Inventory", "View")
    unit_id = input("Enter Unit ID : ").strip().upper()
    record = get_unit(unit_id, include_inactive=True)

    if not record:
        print("Unit Not Found.")
        return

    print("=" * 72)
    print("                         UNIT DETAILS")
    print("=" * 72)
    print("Unit ID       :", record["unit_id"])
    print("Unit Name     :", record["unit_name"])
    print("Unit Symbol   :", record["unit_symbol"])
    print("Status        :", record["status"])
    print("Created At    :", record["created_at"] or "N/A")
    print("Updated At    :", record["updated_at"] or "N/A")
    print("=" * 72)


def update_unit():
    require_current_user_permission("Inventory", "Update")
    unit_id = input("Enter Unit ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT *
            FROM inventory_units
            WHERE hotel_id = ? AND unit_id = ?
        """, (hotel_id, unit_id)).fetchone()

        if not record:
            print("Unit Not Found.")
            return

        new_name = _normalize_name(input(
            f"Enter New Unit Name ({record['unit_name']}) : "
        ))
        new_symbol = _normalize_symbol(input(
            f"Enter New Unit Symbol ({record['unit_symbol']}) : "
        ))

        duplicate_name = cursor.execute("""
            SELECT 1
            FROM inventory_units
            WHERE hotel_id = ?
              AND unit_id != ?
              AND lower(trim(unit_name)) = lower(trim(?))
        """, (hotel_id, unit_id, new_name)).fetchone()

        if duplicate_name:
            print("Unit Name already exists for the current hotel.")
            return

        duplicate_symbol = cursor.execute("""
            SELECT 1
            FROM inventory_units
            WHERE hotel_id = ?
              AND unit_id != ?
              AND lower(trim(unit_symbol)) = lower(trim(?))
        """, (hotel_id, unit_id, new_symbol)).fetchone()

        if duplicate_symbol:
            print("Unit Symbol already exists for the current hotel.")
            return

        now = _current_timestamp()
        cursor.execute("""
            UPDATE inventory_units
            SET unit_name = ?, unit_symbol = ?, updated_at = ?
            WHERE hotel_id = ? AND unit_id = ?
        """, (new_name, new_symbol, now, hotel_id, unit_id))

        # Keep the compatibility text field synchronized until the later
        # inventory integrity stage can enforce the relational reference fully.
        cursor.execute("""
            UPDATE inventory
            SET unit = ?, updated_at = ?
            WHERE hotel_id = ? AND unit_id = ?
        """, (new_name, now, hotel_id, unit_id))

        connection.commit()
        print("Unit Updated Successfully.")

    except ValueError as exc:
        connection.rollback()
        print(f"Invalid Unit Data: {exc}")
    except Exception as exc:
        connection.rollback()
        print(f"Error updating unit: {exc}")
    finally:
        connection.close()


def _set_status(status):
    unit_id = input("Enter Unit ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT unit_name, status
            FROM inventory_units
            WHERE hotel_id = ? AND unit_id = ?
        """, (hotel_id, unit_id)).fetchone()

        if not record:
            print("Unit Not Found.")
            return

        if record["status"] == status:
            print(f"Unit is already {status}.")
            return

        cursor.execute("""
            UPDATE inventory_units
            SET status = ?, updated_at = ?
            WHERE hotel_id = ? AND unit_id = ?
        """, (status, _current_timestamp(), hotel_id, unit_id))

        connection.commit()
        print(f"Unit {status} Successfully.")

    except Exception as exc:
        connection.rollback()
        print(f"Error changing unit status: {exc}")
    finally:
        connection.close()


def deactivate_unit():
    require_current_user_permission("Inventory", "Update")
    _set_status(INACTIVE_STATUS)


def activate_unit():
    require_current_user_permission("Inventory", "Update")
    _set_status(ACTIVE_STATUS)


def delete_unit():
    require_current_user_permission("Inventory", "Delete")
    unit_id = input("Enter Unit ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT unit_name
            FROM inventory_units
            WHERE hotel_id = ? AND unit_id = ?
        """, (hotel_id, unit_id)).fetchone()

        if not record:
            print("Unit Not Found.")
            return

        dependency = cursor.execute("""
            SELECT 1
            FROM inventory
            WHERE hotel_id = ?
              AND unit_id = ?
            LIMIT 1
        """, (hotel_id, unit_id)).fetchone()

        if dependency:
            print(
                "Unit is assigned to inventory items and cannot be deleted. "
                "Deactivate it instead to preserve inventory consistency."
            )
            connection.rollback()
            return

        cursor.execute("""
            DELETE FROM inventory_units
            WHERE hotel_id = ? AND unit_id = ?
        """, (hotel_id, unit_id))

        connection.commit()
        print("Unit Deleted Successfully.")

    except Exception as exc:
        connection.rollback()
        print(f"Error deleting unit: {exc}")
    finally:
        connection.close()
