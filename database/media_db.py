from utils.error_logging import log_non_blocking_error
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


MEDIA_CATEGORIES = (
    "Hotel",
    "Room",
    "Restaurant",
    "Banquet",
    "Facility",
    "Event",
    "Food",
    "Other",
)

MEDIA_TYPES = (
    "Image",
    "Video",
    "Other",
)

SOURCE_TYPES = (
    "Local File",
    "URL",
    "Cloud/CDN",
    "Other",
)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_media_tables():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hotel_media(
                media_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                media_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                media_reference TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'Local File',
                alt_text TEXT,
                display_order INTEGER NOT NULL DEFAULT 1,
                is_guest_visible INTEGER NOT NULL DEFAULT 1
                    CHECK(is_guest_visible IN (0, 1)),
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK(is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(hotel_id) REFERENCES hotels(hotel_id),
                CHECK(category IN (
                    'Hotel', 'Room', 'Restaurant', 'Banquet',
                    'Facility', 'Event', 'Food', 'Other'
                )),
                CHECK(media_type IN ('Image', 'Video', 'Other')),
                CHECK(source_type IN ('Local File', 'URL', 'Cloud/CDN', 'Other')),
                CHECK(display_order >= 1)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hotel_media_hotel_category
            ON hotel_media(hotel_id, category, is_active, display_order)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hotel_media_hotel_visibility
            ON hotel_media(hotel_id, is_guest_visible, is_active)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hotel_media_title
            ON hotel_media(hotel_id, title)
        """)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _next_media_id(cursor, hotel_id):
    prefix = f"MED-{datetime.now().strftime('%Y%m%d')}-"
    cursor.execute("""
        SELECT media_id
        FROM hotel_media
        WHERE hotel_id = ?
          AND media_id LIKE ?
        ORDER BY rowid DESC
        LIMIT 1
    """, (hotel_id, f"{prefix}%"))
    row = cursor.fetchone()
    if not row:
        return f"{prefix}00001"

    try:
        number = int(str(row["media_id"]).split("-")[-1]) + 1
    except (ValueError, IndexError):
        number = 1
    return f"{prefix}{number:05d}"


def _validate_text(value, field_name):
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{field_name} is required.")
    return value


def _validate_choice(value, choices, field_name):
    value = _validate_text(value, field_name)
    if value not in choices:
        raise ValueError(f"Invalid {field_name.lower()}.")
    return value


def _validate_order(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError("Display order must be a whole number.")
    if value < 1:
        raise ValueError("Display order must be at least 1.")
    return value


def add_media(
    category,
    media_type,
    title,
    description,
    media_reference,
    source_type,
    alt_text,
    display_order=1,
    is_guest_visible=True,
    hotel_id=None,
):
    hotel_id = int(hotel_id or get_current_hotel_id())
    category = _validate_choice(category, MEDIA_CATEGORIES, "Category")
    media_type = _validate_choice(media_type, MEDIA_TYPES, "Media type")
    source_type = _validate_choice(source_type, SOURCE_TYPES, "Source type")
    title = _validate_text(title, "Title")
    media_reference = _validate_text(media_reference, "Media reference")
    description = str(description or "").strip()
    alt_text = str(alt_text or "").strip()
    display_order = _validate_order(display_order)
    is_guest_visible = bool(is_guest_visible)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        media_id = _next_media_id(cursor, hotel_id)
        now = _now()
        cursor.execute("""
            INSERT INTO hotel_media(
                media_id, hotel_id, category, media_type, title,
                description, media_reference, source_type, alt_text,
                display_order, is_guest_visible, is_active,
                created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            media_id, hotel_id, category, media_type, title,
            description, media_reference, source_type, alt_text,
            display_order, 1 if is_guest_visible else 0,
            now, now,
        ))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Media",
        action="CREATE",
        local_values=locals(),
        details="Business operation add_media completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return media_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_media(media_id, hotel_id=None):
    hotel_id = int(hotel_id or get_current_hotel_id())
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM hotel_media
            WHERE media_id = ?
              AND hotel_id = ?
            LIMIT 1
        """, (str(media_id).strip(), hotel_id))
        return cursor.fetchone()
    finally:
        connection.close()


def get_media_items(category=None, active_only=False, guest_visible_only=False, hotel_id=None):
    hotel_id = int(hotel_id or get_current_hotel_id())
    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = """
            SELECT *
            FROM hotel_media
            WHERE hotel_id = ?
        """
        params = [hotel_id]
        if category:
            category = _validate_choice(category, MEDIA_CATEGORIES, "Category")
            query += " AND category = ?"
            params.append(category)
        if active_only:
            query += " AND is_active = 1"
        if guest_visible_only:
            query += " AND is_guest_visible = 1"
        query += " ORDER BY category, display_order, created_at, media_id"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def search_media(search_text="", category=None, hotel_id=None):
    hotel_id = int(hotel_id or get_current_hotel_id())
    search_text = str(search_text or "").strip().lower()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = """
            SELECT *
            FROM hotel_media
            WHERE hotel_id = ?
              AND (
                  LOWER(media_id) LIKE ? OR
                  LOWER(title) LIKE ? OR
                  LOWER(description) LIKE ? OR
                  LOWER(category) LIKE ? OR
                  LOWER(media_reference) LIKE ?
              )
        """
        term = f"%{search_text}%"
        params = [hotel_id, term, term, term, term, term]
        if category:
            category = _validate_choice(category, MEDIA_CATEGORIES, "Category")
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY category, display_order, created_at DESC"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def update_media(
    media_id,
    category,
    media_type,
    title,
    description,
    media_reference,
    source_type,
    alt_text,
    display_order,
    is_guest_visible,
    hotel_id=None,
):
    hotel_id = int(hotel_id or get_current_hotel_id())
    category = _validate_choice(category, MEDIA_CATEGORIES, "Category")
    media_type = _validate_choice(media_type, MEDIA_TYPES, "Media type")
    source_type = _validate_choice(source_type, SOURCE_TYPES, "Source type")
    title = _validate_text(title, "Title")
    media_reference = _validate_text(media_reference, "Media reference")
    display_order = _validate_order(display_order)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE hotel_media
            SET category = ?,
                media_type = ?,
                title = ?,
                description = ?,
                media_reference = ?,
                source_type = ?,
                alt_text = ?,
                display_order = ?,
                is_guest_visible = ?,
                updated_at = ?
            WHERE media_id = ?
              AND hotel_id = ?
        """, (
            category, media_type, title, str(description or "").strip(),
            media_reference, source_type, str(alt_text or "").strip(),
            display_order, 1 if is_guest_visible else 0, _now(),
            str(media_id).strip(), hotel_id,
        ))
        if cursor.rowcount == 0:
            raise ValueError("Media record not found.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Media",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_media completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def set_media_status(media_id, is_active, hotel_id=None):
    hotel_id = int(hotel_id or get_current_hotel_id())
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE hotel_media
            SET is_active = ?, updated_at = ?
            WHERE media_id = ?
              AND hotel_id = ?
        """, (1 if is_active else 0, _now(), str(media_id).strip(), hotel_id))
        if cursor.rowcount == 0:
            raise ValueError("Media record not found.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Media",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation set_media_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_media(media_id, hotel_id=None):
    """Remove the database reference without deleting the physical file."""
    hotel_id = int(hotel_id or get_current_hotel_id())
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            DELETE FROM hotel_media
            WHERE media_id = ?
              AND hotel_id = ?
        """, (str(media_id).strip(), hotel_id))
        if cursor.rowcount == 0:
            raise ValueError("Media record not found.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Media",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_media completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
