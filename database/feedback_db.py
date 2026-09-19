from utils.error_logging import log_non_blocking_error
from datetime import datetime
import sqlite3
import re

from database.database import get_connection


FEEDBACK_CATEGORIES = (
    "General",
    "Room",
    "Restaurant",
    "Cleanliness",
    "Staff",
    "Service",
    "Facilities",
    "Billing",
    "Other",
)

FEEDBACK_STATUSES = (
    "Open",
    "In Progress",
    "Resolved",
    "Closed",
)

FOLLOW_UP_METHODS = (
    "Call",
    "WhatsApp",
    "Email",
)

FOLLOW_UP_STATUSES = (
    "Pending",
    "Completed",
)


def _get_hotel_id(hotel_id=None):
    if hotel_id is not None:
        return int(hotel_id)

    from database.hotel_context import get_current_hotel_id
    return get_current_hotel_id()


def _normalize_optional(value):
    value = str(value or "").strip()
    return value or None


def _validate_category(category):
    value = str(category or "").strip().title()
    if value not in FEEDBACK_CATEGORIES:
        raise ValueError("Invalid feedback category.")
    return value


def _validate_status(status):
    value = str(status or "").strip().title()
    if value not in FEEDBACK_STATUSES:
        raise ValueError("Invalid feedback status.")
    return value


def _validate_follow_up_date(value):
    value = _normalize_optional(value)
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%d-%m-%Y").strftime("%d-%m-%Y")
    except ValueError as exc:
        raise ValueError("Follow-up date must be in DD-MM-YYYY format.") from exc


def _validate_follow_up_method(value):
    value = _normalize_optional(value)
    if value is None:
        return None
    normalized = value.title() if value.lower() != "whatsapp" else "WhatsApp"
    if normalized not in FOLLOW_UP_METHODS:
        raise ValueError("Invalid follow-up method.")
    return normalized


def _validate_follow_up_status(value):
    value = _normalize_optional(value)
    if value is None:
        return None
    normalized = value.title()
    if normalized not in FOLLOW_UP_STATUSES:
        raise ValueError("Invalid follow-up status.")
    return normalized


def _validate_follow_up_fields(required, method, status, notes):
    required = bool(required)
    method = _validate_follow_up_method(method)
    status = _validate_follow_up_status(status)
    notes = _normalize_optional(notes)

    if not required:
        return 0, None, None, None

    if method is None:
        raise ValueError("Follow-up method is required when follow-up is required.")
    if status is None:
        status = "Pending"
    if status == "Completed" and notes is None:
        raise ValueError("Follow-up notes are required when follow-up is completed.")
    return 1, method, status, notes


def _validate_feedback_fields(rating, review, category, complaint, issue, resolution, status, follow_up_date, follow_up_required=0, follow_up_method=None, follow_up_status=None, follow_up_notes=None, allow_pending_complaint=False):
    try:
        rating_value = float(rating)
    except (TypeError, ValueError) as exc:
        raise ValueError("Rating must be between 1 and 5.") from exc

    if not 1 <= rating_value <= 5:
        raise ValueError("Rating must be between 1 and 5.")

    review = str(review or "").strip()
    if len(review) < 10:
        raise ValueError("Review must contain at least 10 characters.")

    category = _validate_category(category)
    complaint_text = _normalize_optional(complaint)
    issue_text = _normalize_optional(issue)
    resolution_text = _normalize_optional(resolution)
    status = _validate_status(status)
    follow_up_date = _validate_follow_up_date(follow_up_date)
    follow_up_required, follow_up_method, follow_up_status, follow_up_notes = _validate_follow_up_fields(
        follow_up_required, follow_up_method, follow_up_status, follow_up_notes, allow_pending_complaint=allow_pending_complaint
    )

    if complaint_text and not issue_text and not (
        allow_pending_complaint and status == "Open"
    ):
        raise ValueError("Issue is required when a complaint is being managed.")

    if not complaint_text:
        issue_text = None
        resolution_text = None
        if status in {"Open", "In Progress", "Resolved"}:
            status = "Closed"
        follow_up_date = None
        follow_up_required = 0
        follow_up_method = None
        follow_up_status = None
        follow_up_notes = None
    elif not follow_up_required:
        follow_up_date = None

    if status in {"Resolved", "Closed"} and complaint_text and not resolution_text:
        raise ValueError("Resolution is required for Resolved/Closed complaints.")

    return (
        rating_value,
        review,
        category,
        complaint_text,
        issue_text,
        resolution_text,
        status,
        follow_up_date,
        follow_up_required,
        follow_up_method,
        follow_up_status,
        follow_up_notes,
    )


def _display_feedback(feedback):
    print("=" * 80)
    print("Feedback ID   :", feedback["feedback_id"])
    print("Customer ID   :", feedback["customer_id"] or "N/A")
    print("Customer Name :", feedback["customer_name"] or "N/A")
    print("Mobile        :", feedback["customer_mobile"] or "N/A")
    print("Rating        :", feedback["rating"] if feedback["rating"] is not None else "N/A", "/ 5")
    print("Category      :", feedback["category"] or "General")
    print("Review        :", feedback["feedback"] or "N/A")
    print("Complaint     :", feedback["complaint"] or "No")
    print("Issue         :", feedback["issue"] or "N/A")
    print("Resolution    :", feedback["resolution"] or "N/A")
    print("Status        :", feedback["status"] or "Closed")
    print("Follow-up Date:", feedback["follow_up_date"] or "Not Scheduled")
    print("Follow-up Req :", "Yes" if feedback["follow_up_required"] else "No")
    print("Follow-up Method:", feedback["follow_up_method"] or "N/A")
    print("Follow-up Status:", feedback["follow_up_status"] or "N/A")
    print("Follow-up Notes :", feedback["follow_up_notes"] or "N/A")
    print("Date          :", feedback["feedback_date"] or "N/A")
    print("Time          :", feedback["feedback_time"] or "N/A")
    print("=" * 80)


def create_feedback_table():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback(
                feedback_id TEXT PRIMARY KEY,
                customer_id TEXT,
                hotel_id INTEGER,
                customer_name TEXT,
                customer_mobile TEXT,
                rating INTEGER,
                feedback TEXT,
                feedback_date TEXT,
                feedback_time TEXT,
                category TEXT NOT NULL DEFAULT 'General',
                complaint TEXT,
                issue TEXT,
                resolution TEXT,
                status TEXT NOT NULL DEFAULT 'Closed',
                follow_up_date TEXT,
                follow_up_required INTEGER NOT NULL DEFAULT 0,
                follow_up_method TEXT,
                follow_up_status TEXT,
                follow_up_notes TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_id_sequences(
                hotel_id INTEGER PRIMARY KEY,
                next_number INTEGER NOT NULL
            )
        """)

        cursor.execute("PRAGMA table_info(feedback)")
        columns = {row["name"] for row in cursor.fetchall()}

        migrations = {
            "customer_id": "ALTER TABLE feedback ADD COLUMN customer_id TEXT",
            "hotel_id": "ALTER TABLE feedback ADD COLUMN hotel_id INTEGER",
            "category": "ALTER TABLE feedback ADD COLUMN category TEXT NOT NULL DEFAULT 'General'",
            "complaint": "ALTER TABLE feedback ADD COLUMN complaint TEXT",
            "issue": "ALTER TABLE feedback ADD COLUMN issue TEXT",
            "resolution": "ALTER TABLE feedback ADD COLUMN resolution TEXT",
            "status": "ALTER TABLE feedback ADD COLUMN status TEXT NOT NULL DEFAULT 'Closed'",
            "follow_up_date": "ALTER TABLE feedback ADD COLUMN follow_up_date TEXT",
            "follow_up_required": "ALTER TABLE feedback ADD COLUMN follow_up_required INTEGER NOT NULL DEFAULT 0",
            "follow_up_method": "ALTER TABLE feedback ADD COLUMN follow_up_method TEXT",
            "follow_up_status": "ALTER TABLE feedback ADD COLUMN follow_up_status TEXT",
            "follow_up_notes": "ALTER TABLE feedback ADD COLUMN follow_up_notes TEXT",
        }
        for column, statement in migrations.items():
            if column not in columns:
                cursor.execute(statement)

        cursor.execute("""
            UPDATE feedback
            SET
                follow_up_required = CASE
                    WHEN follow_up_date IS NOT NULL AND TRIM(follow_up_date) <> '' THEN 1
                    ELSE 0
                END,
                follow_up_status = CASE
                    WHEN follow_up_date IS NOT NULL AND TRIM(follow_up_date) <> ''
                        THEN COALESCE(NULLIF(TRIM(follow_up_status), ''), 'Pending')
                    ELSE NULL
                END
            WHERE follow_up_date IS NOT NULL AND TRIM(follow_up_date) <> ''
              AND (follow_up_required = 0 OR follow_up_status IS NULL OR TRIM(follow_up_status) = '')
        """)

        hotel_id = _get_hotel_id()
        cursor.execute("""
            UPDATE feedback
            SET hotel_id = ?
            WHERE hotel_id IS NULL
        """, (hotel_id,))

        cursor.execute("""
            UPDATE feedback
            SET customer_id = (
                SELECT c.customer_id
                FROM customers c
                WHERE c.customer_mobile = feedback.customer_mobile
                ORDER BY c.created_time ASC
                LIMIT 1
            )
            WHERE (customer_id IS NULL OR TRIM(customer_id) = '')
              AND customer_mobile IS NOT NULL
              AND TRIM(customer_mobile) <> ''
        """)

        cursor.execute("""
            UPDATE feedback
            SET category = 'General'
            WHERE category IS NULL OR TRIM(category) = ''
        """)
        cursor.execute("""
            UPDATE feedback
            SET status = CASE
                WHEN complaint IS NOT NULL AND TRIM(complaint) <> '' THEN 'Open'
                ELSE 'Closed'
            END
            WHERE status IS NULL OR TRIM(status) = ''
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_customer
            ON feedback(customer_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_hotel
            ON feedback(hotel_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_hotel_customer
            ON feedback(hotel_id, customer_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_hotel_status
            ON feedback(hotel_id, status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_hotel_category
            ON feedback(hotel_id, category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feedback_follow_up
            ON feedback(hotel_id, follow_up_date)
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _generate_feedback_id(cursor, hotel_id):
    """Generate the next unique feedback ID for the current hotel."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback_id_sequences(
            hotel_id INTEGER PRIMARY KEY,
            next_number INTEGER NOT NULL
        )
    """)

    row = cursor.execute("""
        SELECT next_number
        FROM feedback_id_sequences
        WHERE hotel_id = ?
    """, (hotel_id,)).fetchone()

    if row is None:
        max_number = 0
        existing_ids = cursor.execute("""
            SELECT feedback_id
            FROM feedback
            WHERE feedback_id LIKE 'FD-%'
        """).fetchall()

        for existing in existing_ids:
            match = re.fullmatch(
                r"FD-(\d+)",
                str(existing["feedback_id"] or "").strip().upper()
            )
            if match:
                max_number = max(max_number, int(match.group(1)))

        next_number = max_number + 1
        cursor.execute("""
            INSERT INTO feedback_id_sequences(hotel_id, next_number)
            VALUES(?, ?)
        """, (hotel_id, next_number + 1))
    else:
        next_number = int(row["next_number"])
        cursor.execute("""
            UPDATE feedback_id_sequences
            SET next_number = ?
            WHERE hotel_id = ?
        """, (next_number + 1, hotel_id))

    return f"FD-{next_number:03d}"


def resolve_customer_for_feedback(
    customer_id=None,
    customer_name=None,
    customer_mobile=None,
    hotel_id=None
):
    hotel_id = _get_hotel_id(hotel_id)
    customer_id = str(customer_id or "").strip().upper()
    mobile = str(customer_mobile or "").strip()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        if customer_id:
            cursor.execute("""
                SELECT c.customer_id, c.customer_name, c.customer_mobile
                FROM customers c
                JOIN guest_hotel_relationships ghr
                  ON ghr.customer_id = c.customer_id
                 AND ghr.hotel_id = ?
                 AND ghr.is_active = 1
                WHERE c.customer_id = ?
            """, (hotel_id, customer_id))
            customer = cursor.fetchone()
        elif mobile:
            cursor.execute("""
                SELECT c.customer_id, c.customer_name, c.customer_mobile
                FROM customers c
                JOIN guest_hotel_relationships ghr
                  ON ghr.customer_id = c.customer_id
                 AND ghr.hotel_id = ?
                 AND ghr.is_active = 1
                WHERE c.customer_mobile = ?
                ORDER BY c.created_time ASC
                LIMIT 1
            """, (hotel_id, mobile))
            customer = cursor.fetchone()
        else:
            customer = None

    finally:
        connection.close()

    if customer:
        return customer["customer_id"], customer["customer_name"], customer["customer_mobile"]

    if customer_id:
        raise ValueError("Customer not found for the current hotel.")

    if not mobile:
        raise ValueError("Customer ID or mobile number is required.")

    from database.customer_db import get_next_customer_id, save_customer, ensure_guest_hotel_relationship

    new_customer_id = get_next_customer_id()
    now = datetime.now()

    save_customer(
        new_customer_id,
        str(customer_name or "Guest").strip() or "Guest",
        mobile,
        None,
        None,
        now
    )

    ensure_guest_hotel_relationship(new_customer_id, hotel_id)

    return new_customer_id, str(customer_name or "Guest").strip() or "Guest", mobile


def save_feedback(
    feedback_id,
    customer_name,
    mobile,
    rating,
    review,
    customer_id=None,
    category="General",
    complaint=None,
    issue=None,
    resolution=None,
    status="Closed",
    follow_up_date=None,
    follow_up_required=0,
    follow_up_method=None,
    follow_up_status=None,
    follow_up_notes=None,
    hotel_id=None,
    allow_pending_complaint=False
):
    hotel_id = _get_hotel_id(hotel_id)
    feedback_id = str(feedback_id or "").strip().upper()
    auto_generate_id = not feedback_id

    fields = _validate_feedback_fields(
        rating, review, category, complaint, issue, resolution, status, follow_up_date,
        follow_up_required, follow_up_method, follow_up_status, follow_up_notes,
        allow_pending_complaint=allow_pending_complaint
    )
    (
        rating,
        review,
        category,
        complaint,
        issue,
        resolution,
        status,
        follow_up_date,
        follow_up_required,
        follow_up_method,
        follow_up_status,
        follow_up_notes,
    ) = fields

    customer_id, customer_name, mobile = resolve_customer_for_feedback(
        customer_id,
        customer_name,
        mobile,
        hotel_id
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        if auto_generate_id:
            feedback_id = _generate_feedback_id(cursor, hotel_id)

        existing = cursor.execute(
            "SELECT 1 FROM feedback WHERE feedback_id = ? LIMIT 1",
            (feedback_id,)
        ).fetchone()
        if existing:
            raise ValueError("Feedback ID already exists.")

        now = datetime.now()

        cursor.execute("""
            INSERT INTO feedback(
                feedback_id,
                customer_id,
                hotel_id,
                customer_name,
                customer_mobile,
                rating,
                feedback,
                feedback_date,
                feedback_time,
                category,
                complaint,
                issue,
                resolution,
                status,
                follow_up_date,
                follow_up_required,
                follow_up_method,
                follow_up_status,
                follow_up_notes
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback_id,
            customer_id,
            hotel_id,
            customer_name,
            mobile,
            int(rating) if float(rating).is_integer() else rating,
            review,
            now.strftime("%d-%m-%Y"),
            now.strftime("%I:%M:%S %p"),
            category,
            complaint,
            issue,
            resolution,
            status,
            follow_up_date,
            follow_up_required,
            follow_up_method,
            follow_up_status,
            follow_up_notes,
        ))

        try:
            from database.notification_db import record_notification_event
            event_title = "Guest Feedback Received"
            if complaint:
                event_title = "Guest Complaint Received"
            event_message = (
                f"Feedback {feedback_id} received from {customer_name}. "
                f"Rating: {rating}/5. Category: {category}."
            )
            if complaint:
                event_message += f" Complaint: {complaint}."
            record_notification_event(
                "Feedback",
                event_title,
                event_message,
                reference_type="FEEDBACK",
                reference_id=feedback_id,
                recipient_type="Staff",
                recipient_id=None,
                recipient_name=None,
                recipient_mobile=None,
                hotel_id=hotel_id,
                idempotency_key=f"FEEDBACK:{hotel_id}:{feedback_id}",
                connection=connection,
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Feedback",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_feedback completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return feedback_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _get_feedback_by_id(cursor, feedback_id, hotel_id):
    return cursor.execute("""
        SELECT *
        FROM feedback
        WHERE feedback_id = ?
          AND hotel_id = ?
    """, (feedback_id, hotel_id)).fetchone()


def update_feedback_record(feedback_id, *, rating, review, category="General", complaint=None, issue=None, resolution=None, status="Closed", follow_up_date=None, follow_up_required=0, follow_up_method=None, follow_up_status=None, follow_up_notes=None, allow_pending_complaint=False, hotel_id=None):
    """Update guest-experience fields while preserving the existing validation and hotel boundary."""
    hotel_id = _get_hotel_id(hotel_id)
    feedback_id = str(feedback_id or "").strip().upper()
    fields = _validate_feedback_fields(
        rating, review, category, complaint, issue, resolution, status, follow_up_date,
        follow_up_required, follow_up_method, follow_up_status, follow_up_notes
    )
    (rating, review, category, complaint, issue, resolution, status, follow_up_date,
     follow_up_required, follow_up_method, follow_up_status, follow_up_notes) = fields
    connection = get_connection()
    try:
        cursor = connection.cursor()
        if not _get_feedback_by_id(cursor, feedback_id, hotel_id):
            return False
        cursor.execute("""
            UPDATE feedback SET rating=?, feedback=?, category=?, complaint=?, issue=?,
                resolution=?, status=?, follow_up_date=?, follow_up_required=?,
                follow_up_method=?, follow_up_status=?, follow_up_notes=?
            WHERE feedback_id=? AND hotel_id=?
        """, (int(rating) if float(rating).is_integer() else rating, review, category, complaint, issue,
              resolution, status, follow_up_date, follow_up_required, follow_up_method,
              follow_up_status, follow_up_notes, feedback_id, hotel_id))
        connection.commit()
        return cursor.rowcount > 0
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def view_feedback():
    print("=" * 80)
    print("                    FEEDBACK HISTORY")
    print("=" * 80)

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM feedback
            WHERE hotel_id = ?
            ORDER BY rowid DESC
        """, (_get_hotel_id(),))
        feedbacks = cursor.fetchall()
    finally:
        connection.close()

    if not feedbacks:
        print("No Feedback Found.")
        return

    for feedback in feedbacks:
        _display_feedback(feedback)


def search_feedback():
    print("=" * 80)
    print("                   SEARCH FEEDBACK")
    print("=" * 80)

    term = input("Search Feedback ID / Customer / Category / Status / Follow-up / Keyword : ").strip()
    if not term:
        print("Search value cannot be empty.")
        return

    connection = get_connection()

    try:
        cursor = connection.cursor()
        like_term = f"%{term}%"
        cursor.execute("""
            SELECT *
            FROM feedback
            WHERE hotel_id = ?
              AND (
                    feedback_id LIKE ?
                    OR customer_id LIKE ?
                    OR customer_name LIKE ?
                    OR customer_mobile LIKE ?
                    OR category LIKE ?
                    OR complaint LIKE ?
                    OR issue LIKE ?
                    OR resolution LIKE ?
                    OR status LIKE ?
                    OR feedback LIKE ?
                    OR follow_up_date LIKE ?
                    OR follow_up_method LIKE ?
                    OR follow_up_status LIKE ?
                    OR follow_up_notes LIKE ?
                  )
            ORDER BY rowid DESC
        """, (
            _get_hotel_id(),
            like_term, like_term, like_term, like_term,
            like_term, like_term, like_term, like_term,
            like_term, like_term, like_term, like_term,
            like_term, like_term
        ))
        feedbacks = cursor.fetchall()
    finally:
        connection.close()

    if not feedbacks:
        print("Feedback Not Found.")
        return

    for feedback in feedbacks:
        _display_feedback(feedback)


def update_feedback():
    print("=" * 80)
    print("                   UPDATE FEEDBACK")
    print("=" * 80)

    feedback_id = input("Enter Feedback ID : ").strip().upper()
    hotel_id = _get_hotel_id()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        feedback = _get_feedback_by_id(cursor, feedback_id, hotel_id)

        if not feedback:
            print("Feedback Not Found.")
            return

        customer_id = input(
            f"Customer ID ({feedback['customer_id'] or 'N/A'}) : "
        ).strip().upper() or feedback["customer_id"]

        customer_name = input(
            f"Customer Name ({feedback['customer_name']}) : "
        ).strip() or feedback["customer_name"]

        customer_mobile = input(
            f"Mobile ({feedback['customer_mobile']}) : "
        ).strip() or feedback["customer_mobile"]

        try:
            rating = float(input(
                f"Rating ({feedback['rating']}) : "
            ).strip() or feedback["rating"])
        except ValueError as exc:
            raise ValueError("Rating must be between 1 and 5.") from exc

        review = input(
            f"Review ({feedback['feedback']}) : "
        ).strip() or feedback["feedback"]

        print("Categories:")
        for index, item in enumerate(FEEDBACK_CATEGORIES, start=1):
            print(f"{index}. {item}")
        category_choice = input(
            f"Category ({feedback['category'] or 'General'}) : "
        ).strip()
        if category_choice.isdigit() and 1 <= int(category_choice) <= len(FEEDBACK_CATEGORIES):
            category = FEEDBACK_CATEGORIES[int(category_choice) - 1]
        else:
            category = category_choice or feedback["category"] or "General"

        complaint_choice = input(
            f"Complaint? (Y/N) ({'Y' if feedback['complaint'] else 'N'}) : "
        ).strip().upper()
        complaint_exists = bool(feedback["complaint"]) if not complaint_choice else complaint_choice == "Y"

        complaint = feedback["complaint"]
        issue = feedback["issue"]
        resolution = feedback["resolution"]
        status = feedback["status"] or ("Open" if complaint_exists else "Closed")
        follow_up_date = feedback["follow_up_date"]
        follow_up_required = int(feedback["follow_up_required"] or 0)
        follow_up_method = feedback["follow_up_method"]
        follow_up_status = feedback["follow_up_status"]
        follow_up_notes = feedback["follow_up_notes"]

        if complaint_exists:
            complaint = input(
                f"Complaint ({feedback['complaint'] or 'Enter complaint'}) : "
            ).strip() or feedback["complaint"]
            issue = input(
                f"Issue ({feedback['issue'] or 'Enter issue'}) : "
            ).strip() or feedback["issue"]
            resolution = input(
                f"Resolution ({feedback['resolution'] or 'Not provided'}) : "
            ).strip() or feedback["resolution"]

            print("Statuses:")
            for index, item in enumerate(FEEDBACK_STATUSES, start=1):
                print(f"{index}. {item}")
            status_choice = input(
                f"Status ({status}) : "
            ).strip()
            if status_choice.isdigit() and 1 <= int(status_choice) <= len(FEEDBACK_STATUSES):
                status = FEEDBACK_STATUSES[int(status_choice) - 1]
            elif status_choice:
                status = status_choice

            follow_up_date = input(
                f"Follow-up Date ({feedback['follow_up_date'] or 'Not Scheduled'}) : "
            ).strip() or feedback["follow_up_date"]

            follow_up_choice = input(
                f"Follow-up Required? (Y/N) ({'Y' if follow_up_required else 'N'}) : "
            ).strip().upper()
            follow_up_required = 0 if follow_up_choice == "N" else 1

            if follow_up_required:
                method_choice = input(
                    f"Follow-up Method (Call/WhatsApp/Email) ({follow_up_method or 'Call'}) : "
                ).strip() or (follow_up_method or "Call")
                follow_up_method = method_choice
                status_choice = input(
                    f"Follow-up Status (Pending/Completed) ({follow_up_status or 'Pending'}) : "
                ).strip() or (follow_up_status or "Pending")
                follow_up_status = status_choice
                follow_up_notes = input(
                    f"Follow-up Notes ({follow_up_notes or 'Not provided'}) : "
                ).strip() or follow_up_notes
            else:
                follow_up_method = None
                follow_up_status = None
                follow_up_notes = None
        else:
            complaint = None
            issue = None
            resolution = None
            status = "Closed"
            follow_up_date = None
            follow_up_required = 0
            follow_up_method = None
            follow_up_status = None
            follow_up_notes = None

        (
            rating,
            review,
            category,
            complaint,
            issue,
            resolution,
            status,
            follow_up_date,
            follow_up_required,
            follow_up_method,
            follow_up_status,
            follow_up_notes,
        ) = _validate_feedback_fields(
            rating, review, category, complaint, issue, resolution, status, follow_up_date,
            follow_up_required, follow_up_method, follow_up_status, follow_up_notes
        )

        if customer_id:
            cursor.execute("""
                SELECT c.customer_id, c.customer_name, c.customer_mobile
                FROM customers c
                JOIN guest_hotel_relationships ghr
                  ON ghr.customer_id = c.customer_id
                 AND ghr.hotel_id = ?
                 AND ghr.is_active = 1
                WHERE c.customer_id = ?
            """, (hotel_id, customer_id))
            customer = cursor.fetchone()
            if not customer:
                raise ValueError("Customer Not Found for the current hotel.")
            customer_name = customer["customer_name"]
            customer_mobile = customer["customer_mobile"]

        cursor.execute("""
            UPDATE feedback
            SET
                customer_id = ?,
                customer_name = ?,
                customer_mobile = ?,
                rating = ?,
                feedback = ?,
                category = ?,
                complaint = ?,
                issue = ?,
                resolution = ?,
                status = ?,
                follow_up_date = ?,
                follow_up_required = ?,
                follow_up_method = ?,
                follow_up_status = ?,
                follow_up_notes = ?
            WHERE feedback_id = ?
              AND hotel_id = ?
        """, (
            customer_id,
            customer_name,
            customer_mobile,
            int(rating) if float(rating).is_integer() else rating,
            review,
            category,
            complaint,
            issue,
            resolution,
            status,
            follow_up_date,
            follow_up_required,
            follow_up_method,
            follow_up_status,
            follow_up_notes,
            feedback_id,
            hotel_id
        ))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Feedback",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_feedback completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Feedback Updated Successfully.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def delete_feedback():
    print("=" * 80)
    print("                   DELETE FEEDBACK")
    print("=" * 80)

    feedback_id = input("Enter Feedback ID : ").strip().upper()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            DELETE FROM feedback
            WHERE feedback_id = ?
              AND hotel_id = ?
        """, (feedback_id, _get_hotel_id()))

        if cursor.rowcount == 0:
            connection.rollback()
            print("Feedback Not Found.")
            return

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Feedback",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_feedback completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Feedback Deleted Successfully.")

    except Exception as exc:
        connection.rollback()
        print(f"Error deleting feedback: {exc}")

    finally:
        connection.close()


def get_guest_feedback_history(customer_id, hotel_id=None):
    hotel_id = _get_hotel_id(hotel_id)
    customer_id = str(customer_id or "").strip().upper()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                feedback_id,
                customer_id,
                hotel_id,
                customer_name,
                customer_mobile,
                rating,
                feedback,
                feedback_date,
                feedback_time,
                category,
                complaint,
                issue,
                resolution,
                status,
                follow_up_date,
                follow_up_required,
                follow_up_method,
                follow_up_status,
                follow_up_notes
            FROM feedback
            WHERE customer_id = ?
              AND hotel_id = ?
            ORDER BY rowid DESC
        """, (customer_id, hotel_id))
        return cursor.fetchall()
    finally:
        connection.close()


def get_guest_feedback_summary(customer_id, hotel_id=None):
    feedbacks = get_guest_feedback_history(customer_id, hotel_id)

    ratings = [float(item["rating"]) for item in feedbacks if item["rating"] is not None]
    average_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    complaint_records = [item for item in feedbacks if item["complaint"]]
    resolved_records = [item for item in complaint_records if item["status"] in {"Resolved", "Closed"}]

    return {
        "total_feedback": len(feedbacks),
        "average_rating": average_rating,
        "five_star": sum(1 for rating in ratings if rating == 5),
        "four_star": sum(1 for rating in ratings if rating == 4),
        "three_star": sum(1 for rating in ratings if rating == 3),
        "two_star": sum(1 for rating in ratings if rating == 2),
        "one_star": sum(1 for rating in ratings if rating == 1),
        "complaints": len(complaint_records),
        "resolved_complaints": len(resolved_records),
        "open_complaints": len(complaint_records) - len(resolved_records),
        "follow_ups": sum(1 for item in feedbacks if item["follow_up_required"]),
        "pending_follow_ups": sum(1 for item in feedbacks if item["follow_up_status"] == "Pending"),
        "completed_follow_ups": sum(1 for item in feedbacks if item["follow_up_status"] == "Completed"),
    }


def get_guest_satisfaction_report(hotel_id=None):
    hotel_id = _get_hotel_id(hotel_id)
    connection = get_connection()

    try:
        cursor = connection.cursor()
        overall = cursor.execute("""
            SELECT
                COUNT(*) AS total_feedback,
                COALESCE(AVG(rating), 0) AS average_rating,
                SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) AS five_star,
                SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) AS four_star,
                SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) AS three_star,
                SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) AS two_star,
                SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS one_star,
                SUM(CASE WHEN complaint IS NOT NULL AND TRIM(complaint) <> '' THEN 1 ELSE 0 END) AS complaints,
                SUM(CASE WHEN complaint IS NOT NULL AND TRIM(complaint) <> '' AND status IN ('Resolved', 'Closed') THEN 1 ELSE 0 END) AS resolved_complaints,
                SUM(CASE WHEN complaint IS NOT NULL AND TRIM(complaint) <> '' AND status IN ('Open', 'In Progress') THEN 1 ELSE 0 END) AS open_complaints,
                SUM(CASE WHEN follow_up_required = 1 THEN 1 ELSE 0 END) AS follow_ups,
                 SUM(CASE WHEN follow_up_required = 1 AND follow_up_status = 'Pending' THEN 1 ELSE 0 END) AS pending_follow_ups,
                 SUM(CASE WHEN follow_up_required = 1 AND follow_up_status = 'Completed' THEN 1 ELSE 0 END) AS completed_follow_ups
            FROM feedback
            WHERE hotel_id = ?
        """, (hotel_id,)).fetchone()

        categories = cursor.execute("""
            SELECT category, COUNT(*) AS feedback_count, ROUND(AVG(rating), 2) AS average_rating
            FROM feedback
            WHERE hotel_id = ?
            GROUP BY category
            ORDER BY feedback_count DESC, category
        """, (hotel_id,)).fetchall()

        statuses = cursor.execute("""
            SELECT status, COUNT(*) AS feedback_count
            FROM feedback
            WHERE hotel_id = ?
            GROUP BY status
            ORDER BY feedback_count DESC, status
        """, (hotel_id,)).fetchall()

        return {
            "hotel_id": hotel_id,
            "total_feedback": int(overall["total_feedback"] or 0),
            "average_rating": round(float(overall["average_rating"] or 0), 2),
            "five_star": int(overall["five_star"] or 0),
            "four_star": int(overall["four_star"] or 0),
            "three_star": int(overall["three_star"] or 0),
            "two_star": int(overall["two_star"] or 0),
            "one_star": int(overall["one_star"] or 0),
            "complaints": int(overall["complaints"] or 0),
            "resolved_complaints": int(overall["resolved_complaints"] or 0),
            "open_complaints": int(overall["open_complaints"] or 0),
            "follow_ups": int(overall["follow_ups"] or 0),
            "pending_follow_ups": int(overall["pending_follow_ups"] or 0),
            "completed_follow_ups": int(overall["completed_follow_ups"] or 0),
            "categories": categories,
            "statuses": statuses,
        }
    finally:
        connection.close()


def print_guest_satisfaction_report(hotel_id=None):
    report = get_guest_satisfaction_report(hotel_id)

    print("=" * 80)
    print("                 GUEST SATISFACTION SUMMARY")
    print("=" * 80)
    print("Hotel ID             :", report["hotel_id"])
    print("Total Feedback       :", report["total_feedback"])
    print("Average Rating       :", f"{report['average_rating']:.2f} / 5")
    print("5 Star               :", report["five_star"])
    print("4 Star               :", report["four_star"])
    print("3 Star               :", report["three_star"])
    print("2 Star               :", report["two_star"])
    print("1 Star               :", report["one_star"])
    print("Total Complaints     :", report["complaints"])
    print("Resolved Complaints  :", report["resolved_complaints"])
    print("Open Complaints      :", report["open_complaints"])
    print("Follow-ups Required  :", report["follow_ups"])
    print("Follow-ups Pending   :", report["pending_follow_ups"])
    print("Follow-ups Completed :", report["completed_follow_ups"])

    print("-" * 80)
    print("CATEGORY-WISE SATISFACTION")
    if not report["categories"]:
        print("No category data found.")
    else:
        for row in report["categories"]:
            print(
                f"{row['category']} | Feedback: {row['feedback_count']} | "
                f"Avg Rating: {float(row['average_rating'] or 0):.2f}"
            )

    print("-" * 80)
    print("STATUS-WISE FEEDBACK")
    if not report["statuses"]:
        print("No status data found.")
    else:
        for row in report["statuses"]:
            print(f"{row['status']} | {row['feedback_count']}")

    print("=" * 80)


def customer_feedback_history(customer_id):
    from database.customer_db import get_customer_by_id

    customer_id = str(customer_id or "").strip().upper()
    customer = get_customer_by_id(customer_id)

    if customer is None:
        print("Customer Not Found.")
        return

    feedbacks = get_guest_feedback_history(customer_id)

    print()
    print("=" * 80)
    print("GUEST FEEDBACK HISTORY")
    print("=" * 80)
    print("Customer ID :", customer["customer_id"])
    print("Name        :", customer["customer_name"])
    print("Mobile      :", customer["customer_mobile"] or "None")
    print("-" * 80)

    if not feedbacks:
        print("No feedback found for this guest.")
        print("=" * 80)
        return

    for index, feedback in enumerate(feedbacks, start=1):
        print(f"Feedback #{index}")
        print("Feedback ID :", feedback["feedback_id"])
        print("Rating      :", feedback["rating"])
        print("Category    :", feedback["category"] or "General")
        print("Review      :", feedback["feedback"] or "N/A")
        print("Complaint   :", feedback["complaint"] or "No")
        print("Issue       :", feedback["issue"] or "N/A")
        print("Resolution  :", feedback["resolution"] or "N/A")
        print("Status      :", feedback["status"] or "Closed")
        print("Follow-up Date:", feedback["follow_up_date"] or "Not Scheduled")
        print("Follow-up Req :", "Yes" if feedback["follow_up_required"] else "No")
        print("Follow-up Method:", feedback["follow_up_method"] or "N/A")
        print("Follow-up Status:", feedback["follow_up_status"] or "N/A")
        print("Follow-up Notes :", feedback["follow_up_notes"] or "N/A")
        print("Date        :", feedback["feedback_date"] or "N/A")
        print("Time        :", feedback["feedback_time"] or "N/A")
        if index < len(feedbacks):
            print("-" * 80)

    summary = get_guest_feedback_summary(customer_id)
    print("-" * 80)
    print("FEEDBACK SUMMARY")
    print("Total Feedback     :", summary["total_feedback"])
    print("Average Rating     :", f"{summary['average_rating']:.2f} / 5")
    print("Complaints         :", summary["complaints"])
    print("Resolved Complaints:", summary["resolved_complaints"])
    print("Open Complaints    :", summary["open_complaints"])
    print("Follow-ups Required :", summary["follow_ups"])
    print("Follow-ups Pending  :", summary["pending_follow_ups"])
    print("Follow-ups Complete :", summary["completed_follow_ups"])
    print("5 Star             :", summary["five_star"])
    print("4 Star             :", summary["four_star"])
    print("3 Star             :", summary["three_star"])
    print("2 Star             :", summary["two_star"])
    print("1 Star             :", summary["one_star"])
    print("=" * 80)
