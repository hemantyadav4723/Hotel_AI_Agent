from datetime import datetime
import re
import sqlite3

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


NOTIFICATION_EVENT_TYPES = (
    "Booking",
    "Payment",
    "Cancellation",
    "Check-in",
    "Check-out",
    "Low Stock",
    "Feedback",
    "Transportation",
)

NOTIFICATION_CHANNELS = (
    ("EMAIL", "Email", "Future Integration"),
    ("SMS", "SMS", "Future Integration"),
    ("WHATSAPP", "WhatsApp", "Future Integration"),
    ("IN_APP", "In-app", "Native Queue"),
    ("VOICE", "Voice", "Future Integration"),
)

DELIVERY_STATUSES = (
    "Queued",
    "Pending Integration",
    "Sent",
    "Failed",
    "Read",
)


def _now():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _normalize_event_type(event_type):
    value = " ".join(str(event_type or "").strip().split())
    mapping = {item.lower(): item for item in NOTIFICATION_EVENT_TYPES}
    normalized = mapping.get(value.lower())
    if normalized is None:
        raise ValueError(
            f"Unsupported notification event. Supported events: "
            f"{', '.join(NOTIFICATION_EVENT_TYPES)}"
        )
    return normalized


def _normalize_channel(channel):
    value = " ".join(str(channel or "").strip().split())
    for code, name, _ in NOTIFICATION_CHANNELS:
        if value.lower() in (code.lower(), name.lower()):
            return code
    raise ValueError(
        f"Unsupported notification channel. Supported channels: "
        f"{', '.join(name for _, name, _ in NOTIFICATION_CHANNELS)}"
    )


def _generate_id(cursor, prefix, table, column, hotel_id):
    date_part = datetime.now().strftime("%Y%m%d")
    cursor.execute(
        f"""
        SELECT {column}
        FROM {table}
        WHERE hotel_id = ?
          AND {column} LIKE ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (hotel_id, f"{prefix}-{date_part}-%"),
    )
    row = cursor.fetchone()
    sequence = 0
    if row and row[column]:
        match = re.search(r"-(\d+)$", str(row[column]))
        if match:
            sequence = int(match.group(1))
    return f"{prefix}-{date_part}-{sequence + 1:05d}"


def create_notifications_tables():
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_channels(
                channel_code TEXT PRIMARY KEY,
                channel_name TEXT NOT NULL UNIQUE,
                integration_status TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_events(
                event_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                reference_type TEXT,
                reference_id TEXT,
                recipient_type TEXT,
                recipient_id TEXT,
                recipient_name TEXT,
                recipient_mobile TEXT,
                recipient_email TEXT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_deliveries(
                delivery_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                hotel_id INTEGER NOT NULL,
                channel_code TEXT NOT NULL,
                status TEXT NOT NULL,
                scheduled_at TEXT,
                sent_at TEXT,
                read_at TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(event_id)
                    REFERENCES notification_events(event_id)
                    ON DELETE CASCADE,
                FOREIGN KEY(channel_code)
                    REFERENCES notification_channels(channel_code),
                UNIQUE(event_id, channel_code)
            )
        """)

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_notification_events_hotel "
            "ON notification_events(hotel_id, created_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_notification_events_type "
            "ON notification_events(hotel_id, event_type, created_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_notification_deliveries_hotel "
            "ON notification_deliveries(hotel_id, status, created_at)"
        )

        now = _now()
        for code, name, integration_status in NOTIFICATION_CHANNELS:
            cursor.execute(
                """
                INSERT OR IGNORE INTO notification_channels(
                    channel_code, channel_name, integration_status,
                    is_active, created_at
                )
                VALUES(?, ?, ?, 1, ?)
                """,
                (code, name, integration_status, now),
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _resolve_recipient(cursor, hotel_id, recipient_id=None,
                       recipient_name=None, recipient_mobile=None,
                       recipient_email=None):
    if recipient_id:
        row = cursor.execute(
            """
            SELECT customer_id, customer_name, customer_mobile, customer_email
            FROM customers
            WHERE customer_id = ?
            """,
            (str(recipient_id).strip().upper(),),
        ).fetchone()
        if row:
            return (
                row["customer_id"],
                row["customer_name"],
                row["customer_mobile"],
                row["customer_email"],
            )

    return (
        str(recipient_id).strip().upper() if recipient_id else None,
        str(recipient_name).strip() if recipient_name else None,
        str(recipient_mobile).strip() if recipient_mobile else None,
        str(recipient_email).strip().lower() if recipient_email else None,
    )


def record_notification_event(
    event_type,
    title,
    message,
    reference_type=None,
    reference_id=None,
    recipient_type=None,
    recipient_id=None,
    recipient_name=None,
    recipient_mobile=None,
    recipient_email=None,
    hotel_id=None,
    idempotency_key=None,
    connection=None,
):
    """
    Record one business event and create delivery records for all supported
    communication channels. No external message is sent at this foundation
    stage. In-app is queued locally; external channels remain pending
    integration until provider integrations are added later.
    """
    event_type = _normalize_event_type(event_type)
    title = str(title or "").strip()
    message = str(message or "").strip()
    if not title:
        raise ValueError("Notification title is required.")
    if not message:
        raise ValueError("Notification message is required.")

    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    owns_connection = connection is None
    if owns_connection:
        connection = get_connection()

    try:
        cursor = connection.cursor()

        if idempotency_key:
            existing = cursor.execute(
                """
                SELECT event_id
                FROM notification_events
                WHERE idempotency_key = ?
                """,
                (str(idempotency_key),),
            ).fetchone()
            if existing:
                return existing["event_id"]

        (
            recipient_id,
            recipient_name,
            recipient_mobile,
            recipient_email,
        ) = _resolve_recipient(
            cursor,
            hotel_id,
            recipient_id,
            recipient_name,
            recipient_mobile,
            recipient_email,
        )

        event_id = _generate_id(
            cursor, "NTF", "notification_events", "event_id", hotel_id
        )
        now = _now()

        cursor.execute(
            """
            INSERT INTO notification_events(
                event_id, hotel_id, event_type,
                reference_type, reference_id,
                recipient_type, recipient_id, recipient_name,
                recipient_mobile, recipient_email,
                title, message, idempotency_key, created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                hotel_id,
                event_type,
                reference_type,
                str(reference_id) if reference_id is not None else None,
                recipient_type,
                recipient_id,
                recipient_name,
                recipient_mobile,
                recipient_email,
                title,
                message,
                str(idempotency_key) if idempotency_key else None,
                now,
            ),
        )

        for code, _, integration_status in NOTIFICATION_CHANNELS:
            status = "Queued" if code == "IN_APP" else "Pending Integration"
            delivery_id = _generate_id(
                cursor,
                "NTFD",
                "notification_deliveries",
                "delivery_id",
                hotel_id,
            )
            cursor.execute(
                """
                INSERT INTO notification_deliveries(
                    delivery_id, event_id, hotel_id, channel_code,
                    status, scheduled_at, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delivery_id,
                    event_id,
                    hotel_id,
                    code,
                    status,
                    now,
                    now,
                ),
            )

        if owns_connection:
            connection.commit()
        return event_id
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def record_low_stock_notification_if_needed(
    cursor,
    hotel_id,
    item_id,
    before_quantity,
    after_quantity,
    item_name=None,
    unit=None,
):
    """
    Create a Low Stock event only when stock crosses from above reorder level
    to at/below reorder level. This prevents duplicate alerts on every
    subsequent stock movement while an item remains low.
    """
    item = cursor.execute(
        """
        SELECT item_name, unit, quantity, reorder_level, status
        FROM inventory
        WHERE hotel_id = ? AND item_id = ?
        """,
        (hotel_id, str(item_id).strip().upper()),
    ).fetchone()
    if item is None or item["status"] != "Active":
        return None

    reorder_level = int(item["reorder_level"] or 0)
    before_quantity = int(before_quantity or 0)
    after_quantity = int(after_quantity or 0)

    if not (before_quantity > reorder_level and after_quantity <= reorder_level):
        return None

    name = item_name or item["item_name"]
    item_unit = unit or item["unit"] or "unit"
    title = "Low Stock Alert"
    message = (
        f"Inventory item '{name}' is now low on stock. "
        f"Current quantity: {after_quantity} {item_unit}; "
        f"reorder level: {reorder_level}."
    )
    key = (
        f"LOW-STOCK:{hotel_id}:{str(item_id).strip().upper()}:"
        f"{after_quantity}:{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    )
    return record_notification_event(
        "Low Stock",
        title,
        message,
        reference_type="INVENTORY_ITEM",
        reference_id=str(item_id).strip().upper(),
        recipient_type="Staff",
        hotel_id=hotel_id,
        idempotency_key=key,
        connection=cursor.connection,
    )


def get_notifications(
    hotel_id=None,
    event_type=None,
    channel=None,
    status=None,
    unread_only=False,
    limit=100,
):
    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    connection = get_connection()
    try:
        params = [hotel_id]
        conditions = ["e.hotel_id = ?"]

        if event_type:
            event_type = _normalize_event_type(event_type)
            conditions.append("e.event_type = ?")
            params.append(event_type)

        if channel:
            channel_code = _normalize_channel(channel)
            conditions.append("d.channel_code = ?")
            params.append(channel_code)

        if status:
            conditions.append("d.status = ?")
            params.append(str(status).strip())

        if unread_only:
            conditions.append(
                "d.channel_code = 'IN_APP' AND d.status = 'Queued'"
            )

        try:
            limit = max(1, min(int(limit), 500))
        except (TypeError, ValueError):
            limit = 100

        params.append(limit)

        return connection.execute(
            f"""
            SELECT
                e.event_id,
                e.event_type,
                e.reference_type,
                e.reference_id,
                e.recipient_type,
                e.recipient_id,
                e.recipient_name,
                e.recipient_mobile,
                e.recipient_email,
                e.title,
                e.message,
                e.created_at,
                d.delivery_id,
                d.channel_code,
                c.channel_name,
                c.integration_status,
                d.status,
                d.scheduled_at,
                d.sent_at,
                d.read_at,
                d.error_message
            FROM notification_events e
            INNER JOIN notification_deliveries d
                ON d.event_id = e.event_id
               AND d.hotel_id = e.hotel_id
            INNER JOIN notification_channels c
                ON c.channel_code = d.channel_code
            WHERE {' AND '.join(conditions)}
            ORDER BY e.created_at DESC, d.channel_code
            LIMIT ?
            """,
            params,
        ).fetchall()
    finally:
        connection.close()


def search_notifications(term, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    term = str(term or "").strip()
    like = f"%{term}%"
    connection = get_connection()
    try:
        return connection.execute(
            """
            SELECT
                e.event_id, e.event_type, e.reference_type, e.reference_id,
                e.recipient_name, e.title, e.message, e.created_at,
                d.delivery_id, d.channel_code, c.channel_name,
                c.integration_status, d.status
            FROM notification_events e
            INNER JOIN notification_deliveries d
                ON d.event_id = e.event_id
               AND d.hotel_id = e.hotel_id
            INNER JOIN notification_channels c
                ON c.channel_code = d.channel_code
            WHERE e.hotel_id = ?
              AND (
                  lower(e.event_id) LIKE lower(?)
                  OR lower(e.event_type) LIKE lower(?)
                  OR lower(COALESCE(e.reference_id, '')) LIKE lower(?)
                  OR lower(COALESCE(e.recipient_name, '')) LIKE lower(?)
                  OR lower(e.title) LIKE lower(?)
                  OR lower(e.message) LIKE lower(?)
              )
            ORDER BY e.created_at DESC
            LIMIT 200
            """,
            (hotel_id, like, like, like, like, like, like),
        ).fetchall()
    finally:
        connection.close()


def mark_notification_read(delivery_id, hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    delivery_id = str(delivery_id or "").strip().upper()
    if not delivery_id:
        raise ValueError("Delivery ID is required.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        row = cursor.execute(
            """
            SELECT status
            FROM notification_deliveries
            WHERE delivery_id = ? AND hotel_id = ? AND channel_code = 'IN_APP'
            """,
            (delivery_id, hotel_id),
        ).fetchone()
        if row is None:
            raise ValueError("In-app notification not found.")

        cursor.execute(
            """
            UPDATE notification_deliveries
            SET status = 'Read', read_at = ?
            WHERE delivery_id = ? AND hotel_id = ?
              AND channel_code = 'IN_APP'
            """,
            (_now(), delivery_id, hotel_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_notification_channels(hotel_id=None):
    hotel_id = get_current_hotel_id() if hotel_id is None else int(hotel_id)
    connection = get_connection()
    try:
        return connection.execute(
            """
            SELECT channel_code, channel_name, integration_status, is_active
            FROM notification_channels
            ORDER BY rowid
            """
        ).fetchall()
    finally:
        connection.close()


def print_notification_rows(rows, title="NOTIFICATIONS"):
    print("=" * 90)
    print(f"{title:^90}")
    print("=" * 90)

    if not rows:
        print("No Notifications Found.")
        return

    for row in rows:
        print(f"Event ID       : {row['event_id']}")
        print(f"Event          : {row['event_type']}")
        print(f"Channel        : {row['channel_name']}")
        print(f"Delivery Status: {row['status']}")
        print(f"Integration    : {row['integration_status']}")
        print(f"Recipient      : {row['recipient_name'] or row['recipient_type'] or '-'}")
        print(f"Reference      : {row['reference_type'] or '-'} / {row['reference_id'] or '-'}")
        print(f"Title          : {row['title']}")
        print(f"Message        : {row['message']}")
        print(f"Created        : {row['created_at']}")
        if row["scheduled_at"]:
            print(f"Scheduled      : {row['scheduled_at']}")
        if row["read_at"]:
            print(f"Read           : {row['read_at']}")
        print("-" * 90)


def view_notification_inbox():
    rows = get_notifications(unread_only=True)
    print_notification_rows(rows, "IN-APP NOTIFICATION INBOX")
    if rows:
        delivery_id = input(
            "Enter Delivery ID to mark as Read (blank to keep unread) : "
        ).strip().upper()
        if delivery_id:
            mark_notification_read(delivery_id)
            print("Notification marked as Read successfully.")


def view_notification_history():
    print_notification_rows(get_notifications(), "NOTIFICATION HISTORY")


def search_notification():
    term = input(
        "Search Event ID / Event / Reference / Recipient / Keyword : "
    ).strip()
    print_notification_rows(
        search_notifications(term),
        "NOTIFICATION SEARCH",
    )


def show_notification_channels():
    print("=" * 72)
    print("                 COMMUNICATION CHANNEL FOUNDATION")
    print("=" * 72)
    for code, name, integration_status in NOTIFICATION_CHANNELS:
        print(f"Channel           : {name}")
        print(f"Code              : {code}")
        print(f"Integration       : {integration_status}")
        print("Status            : Active")
        print("-" * 72)


def show_notification_event_types():
    print("=" * 72)
    print("                    NOTIFICATION EVENTS")
    print("=" * 72)
    for index, event_type in enumerate(NOTIFICATION_EVENT_TYPES, start=1):
        print(f"{index}. {event_type}")
    print("-" * 72)


def notifications_management():
    try:
        while True:
            print("=" * 72)
            print("             NOTIFICATIONS & COMMUNICATION")
            print("=" * 72)
            print("1. Notification Inbox")
            print("2. Notification History")
            print("3. Search Notifications")
            print("4. Communication Channels")
            print("5. Notification Events")
            print("6. Back")
            print("-" * 72)

            choice = input("Enter Choice : ").strip()

            if choice == "1":
                view_notification_inbox()
            elif choice == "2":
                view_notification_history()
            elif choice == "3":
                search_notification()
            elif choice == "4":
                show_notification_channels()
            elif choice == "5":
                show_notification_event_types()
            elif choice == "6":
                return
            else:
                print("Invalid Choice.")
                continue

            input("\nPress Enter To Continue...")
    except (KeyboardInterrupt, EOFError):
        print("\nReturning to Main Menu...")
    except Exception as exc:
        print(f"Notification module error: {exc}")
