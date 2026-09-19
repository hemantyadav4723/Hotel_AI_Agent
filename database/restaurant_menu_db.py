from utils.error_logging import log_non_blocking_error
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


# Immutable application defaults used only to seed a hotel-scoped SQLite menu.
# Runtime menu data always comes from restaurant_menu_items.
DEFAULT_RESTAURANT_MENU = (
    ("Veg Thali", 250),
    ("Paneer Butter Masala", 280),
    ("Dal Tadka", 180),
    ("Veg Biryani", 220),
    ("Butter Naan", 40),
    ("Cold Drink", 50),
)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_restaurant_menu_tables():
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS restaurant_menu_categories(
                category_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                category_name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(hotel_id, category_name),
                FOREIGN KEY(hotel_id) REFERENCES hotels(hotel_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS restaurant_menu_items(
                item_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                category_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                price REAL NOT NULL,
                is_available INTEGER NOT NULL DEFAULT 1,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(hotel_id, item_name),
                FOREIGN KEY(hotel_id) REFERENCES hotels(hotel_id),
                FOREIGN KEY(category_id) REFERENCES restaurant_menu_categories(category_id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_restaurant_menu_categories_hotel
            ON restaurant_menu_categories(hotel_id, is_active, category_name)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_restaurant_menu_items_hotel
            ON restaurant_menu_items(hotel_id, is_available, category_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_restaurant_menu_items_name
            ON restaurant_menu_items(hotel_id, item_name)
        """)

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _next_id(cursor, prefix, table, column):
    cursor.execute(
        f"""
        SELECT {column}
        FROM {table}
        WHERE {column} LIKE ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (f"{prefix}%",)
    )
    row = cursor.fetchone()
    if not row:
        return f"{prefix}1001"

    value = str(row[column])
    suffix = value[len(prefix):]
    try:
        number = int(suffix) + 1
    except ValueError:
        number = 1001
    return f"{prefix}{number}"


def _ensure_default_category(cursor, hotel_id):
    cursor.execute("""
        SELECT category_id
        FROM restaurant_menu_categories
        WHERE hotel_id = ?
          AND category_name = 'General'
        LIMIT 1
    """, (hotel_id,))
    row = cursor.fetchone()
    if row:
        return row["category_id"]

    category_id = _next_id(
        cursor,
        "MCAT",
        "restaurant_menu_categories",
        "category_id"
    )
    now = _now()
    cursor.execute("""
        INSERT INTO restaurant_menu_categories(
            category_id, hotel_id, category_name,
            is_active, created_at, updated_at
        )
        VALUES (?, ?, ?, 1, ?, ?)
    """, (category_id, hotel_id, "General", now, now))
    return category_id


def seed_default_restaurant_menu():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        category_id = _ensure_default_category(cursor, hotel_id)

        for item_name, price in DEFAULT_RESTAURANT_MENU:
            cursor.execute("""
                SELECT item_id
                FROM restaurant_menu_items
                WHERE hotel_id = ?
                  AND item_name = ?
                LIMIT 1
            """, (hotel_id, item_name))
            if cursor.fetchone():
                continue

            item_id = _next_id(
                cursor,
                "MENU",
                "restaurant_menu_items",
                "item_id"
            )
            now = _now()
            cursor.execute("""
                INSERT INTO restaurant_menu_items(
                    item_id, hotel_id, category_id, item_name,
                    price, is_available, description,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 1, '', ?, ?)
            """, (
                item_id,
                hotel_id,
                category_id,
                item_name,
                float(price),
                now,
                now
            ))

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_menu_items(available_only=False, category_id=None, hotel_id=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = """
            SELECT
                i.item_id,
                i.hotel_id,
                i.category_id,
                c.category_name,
                i.item_name,
                i.price,
                i.is_available,
                i.description,
                i.created_at,
                i.updated_at
            FROM restaurant_menu_items i
            JOIN restaurant_menu_categories c
              ON c.category_id = i.category_id
             AND c.hotel_id = i.hotel_id
            WHERE i.hotel_id = ?
        """
        params = [hotel_id]

        if available_only:
            query += " AND i.is_available = 1 AND c.is_active = 1"

        if category_id:
            query += " AND i.category_id = ?"
            params.append(category_id)

        query += " ORDER BY c.category_name, i.item_name"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def get_menu_item(item_id, hotel_id=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                i.item_id,
                i.hotel_id,
                i.category_id,
                c.category_name,
                i.item_name,
                i.price,
                i.is_available,
                i.description,
                i.created_at,
                i.updated_at
            FROM restaurant_menu_items i
            JOIN restaurant_menu_categories c
              ON c.category_id = i.category_id
             AND c.hotel_id = i.hotel_id
            WHERE i.item_id = ?
              AND i.hotel_id = ?
        """, (item_id, hotel_id))
        return cursor.fetchone()
    finally:
        connection.close()


def search_menu_items(search_text="", category_id=None, available=None, hotel_id=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    search_text = str(search_text or "").strip().lower()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = """
            SELECT
                i.item_id,
                i.hotel_id,
                i.category_id,
                c.category_name,
                i.item_name,
                i.price,
                i.is_available,
                i.description,
                i.created_at,
                i.updated_at
            FROM restaurant_menu_items i
            JOIN restaurant_menu_categories c
              ON c.category_id = i.category_id
             AND c.hotel_id = i.hotel_id
            WHERE i.hotel_id = ?
        """
        params = [hotel_id]

        if search_text:
            query += """
                AND (
                    LOWER(i.item_name) LIKE ?
                    OR LOWER(COALESCE(i.description, '')) LIKE ?
                    OR LOWER(c.category_name) LIKE ?
                )
            """
            like = f"%{search_text}%"
            params.extend([like, like, like])

        if category_id:
            query += " AND i.category_id = ?"
            params.append(category_id)

        if available is not None:
            query += " AND i.is_available = ?"
            params.append(1 if available else 0)

        query += " ORDER BY c.category_name, i.item_name"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def get_menu_categories(hotel_id=None, active_only=False):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = """
            SELECT category_id, hotel_id, category_name,
                   is_active, created_at, updated_at
            FROM restaurant_menu_categories
            WHERE hotel_id = ?
        """
        params = [hotel_id]
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY category_name"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def add_menu_category(category_name, hotel_id=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    category_name = str(category_name or "").strip()
    if not category_name:
        raise ValueError("Category name is required.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT category_id
            FROM restaurant_menu_categories
            WHERE hotel_id = ?
              AND LOWER(category_name) = LOWER(?)
            LIMIT 1
        """, (hotel_id, category_name))
        if cursor.fetchone():
            raise ValueError("Category already exists.")

        category_id = _next_id(
            cursor,
            "MCAT",
            "restaurant_menu_categories",
            "category_id"
        )
        now = _now()
        cursor.execute("""
            INSERT INTO restaurant_menu_categories(
                category_id, hotel_id, category_name,
                is_active, created_at, updated_at
            )
            VALUES (?, ?, ?, 1, ?, ?)
        """, (category_id, hotel_id, category_name, now, now))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Restaurant Menu",
        action="CREATE",
        local_values=locals(),
        details="Business operation add_menu_category completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return category_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def add_menu_item(item_name, price, category_id, description="", hotel_id=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    item_name = str(item_name or "").strip()
    if not item_name:
        raise ValueError("Menu item name is required.")

    try:
        price = float(price)
    except (TypeError, ValueError):
        raise ValueError("Menu item price must be a valid number.")

    if price < 0:
        raise ValueError("Menu item price cannot be negative.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT category_id
            FROM restaurant_menu_categories
            WHERE category_id = ?
              AND hotel_id = ?
              AND is_active = 1
            LIMIT 1
        """, (category_id, hotel_id))
        if cursor.fetchone() is None:
            raise ValueError("Invalid or inactive menu category.")

        cursor.execute("""
            SELECT item_id
            FROM restaurant_menu_items
            WHERE hotel_id = ?
              AND LOWER(item_name) = LOWER(?)
            LIMIT 1
        """, (hotel_id, item_name))
        if cursor.fetchone():
            raise ValueError("Menu item already exists.")

        item_id = _next_id(
            cursor,
            "MENU",
            "restaurant_menu_items",
            "item_id"
        )
        now = _now()
        cursor.execute("""
            INSERT INTO restaurant_menu_items(
                item_id, hotel_id, category_id, item_name,
                price, is_available, description,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
        """, (
            item_id,
            hotel_id,
            category_id,
            item_name,
            price,
            str(description or "").strip(),
            now,
            now
        ))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Restaurant Menu",
        action="CREATE",
        local_values=locals(),
        details="Business operation add_menu_item completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return item_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_menu_item(item_id, item_name, price, category_id, description="", hotel_id=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    item_name = str(item_name or "").strip()
    if not item_name:
        raise ValueError("Menu item name is required.")

    try:
        price = float(price)
    except (TypeError, ValueError):
        raise ValueError("Menu item price must be a valid number.")

    if price < 0:
        raise ValueError("Menu item price cannot be negative.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT item_id
            FROM restaurant_menu_items
            WHERE item_id = ?
              AND hotel_id = ?
            LIMIT 1
        """, (item_id, hotel_id))
        if cursor.fetchone() is None:
            raise ValueError("Menu item not found.")

        cursor.execute("""
            SELECT category_id
            FROM restaurant_menu_categories
            WHERE category_id = ?
              AND hotel_id = ?
              AND is_active = 1
            LIMIT 1
        """, (category_id, hotel_id))
        if cursor.fetchone() is None:
            raise ValueError("Invalid or inactive menu category.")

        cursor.execute("""
            SELECT item_id
            FROM restaurant_menu_items
            WHERE hotel_id = ?
              AND LOWER(item_name) = LOWER(?)
              AND item_id <> ?
            LIMIT 1
        """, (hotel_id, item_name, item_id))
        if cursor.fetchone():
            raise ValueError("Another menu item with this name already exists.")

        cursor.execute("""
            UPDATE restaurant_menu_items
            SET item_name = ?,
                price = ?,
                category_id = ?,
                description = ?,
                updated_at = ?
            WHERE item_id = ?
              AND hotel_id = ?
        """, (
            item_name,
            price,
            category_id,
            str(description or "").strip(),
            _now(),
            item_id,
            hotel_id
        ))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Restaurant Menu",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_menu_item completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def set_menu_item_availability(item_id, is_available, hotel_id=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE restaurant_menu_items
            SET is_available = ?,
                updated_at = ?
            WHERE item_id = ?
              AND hotel_id = ?
        """, (
            1 if is_available else 0,
            _now(),
            item_id,
            hotel_id
        ))
        if cursor.rowcount == 0:
            raise ValueError("Menu item not found.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Restaurant Menu",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation set_menu_item_availability completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def deactivate_menu_item(item_id, hotel_id=None):
    return set_menu_item_availability(item_id, False, hotel_id)
