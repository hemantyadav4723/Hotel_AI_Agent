from utils.error_logging import log_non_blocking_error
import re
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission
from database.expense_category_db import (
    get_expense_category,
    get_active_expense_category_options,
    _ensure_category_for_legacy_value,
)
from database.department_db import get_active_department_options
from utils.validators import validate_positive_number
from database.supplier_db import create_supplier_table


def _current_timestamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _resolve_hotel_id(hotel_id=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    try:
        return int(hotel_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid hotel context.")


def _table_columns(cursor):
    cursor.execute("PRAGMA table_info(expenses)")
    return {row["name"] for row in cursor.fetchall()}


def _migrate_expenses_schema(cursor):
    """Upgrade the existing expense table without dropping legacy data."""
    columns = _table_columns(cursor)

    if "hotel_id" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN hotel_id INTEGER")

    if "category_id" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN category_id TEXT")

    if "vendor_id" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN vendor_id TEXT")

    if "vendor_name" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN vendor_name TEXT")

    if "payment_method" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN payment_method TEXT")
    if "department_id" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN department_id TEXT")
    if "department_name" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN department_name TEXT")
    if "approval_status" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'Pending'")
    if "approved_by" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN approved_by TEXT")
    if "approved_at" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN approved_at TEXT")
    if "approval_note" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN approval_note TEXT")
    if "is_recurring" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN is_recurring INTEGER NOT NULL DEFAULT 0")
    if "recurrence_frequency" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN recurrence_frequency TEXT")
    if "recurrence_start_date" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN recurrence_start_date TEXT")
    if "next_due_date" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN next_due_date TEXT")

    if "receipt_reference" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN receipt_reference TEXT")

    if "created_at" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN created_at TEXT")

    if "updated_at" not in columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN updated_at TEXT")

    hotel_id = _resolve_hotel_id()

    cursor.execute("""
        UPDATE expenses
        SET hotel_id = ?
        WHERE hotel_id IS NULL
    """, (hotel_id,))

    now = _current_timestamp()
    cursor.execute("""
        UPDATE expenses
        SET approval_status = 'Pending'
        WHERE approval_status IS NULL OR TRIM(approval_status) = ''
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_expenses_hotel_approval
        ON expenses(hotel_id, approval_status)
    """)
    cursor.execute("""
        UPDATE expenses
        SET created_at = COALESCE(created_at, ?),
            updated_at = COALESCE(updated_at, ?)
        WHERE created_at IS NULL OR updated_at IS NULL
    """, (now, now))

    # Convert legacy free-text categories into the new category master.
    legacy_categories = cursor.execute("""
        SELECT DISTINCT hotel_id, TRIM(category) AS category_name
        FROM expenses
        WHERE category IS NOT NULL
          AND TRIM(category) <> ''
          AND (category_id IS NULL OR TRIM(category_id) = '')
    """).fetchall()

    for row in legacy_categories:
        legacy_hotel_id = row["hotel_id"] or hotel_id
        category_id = _ensure_category_for_legacy_value(
            cursor,
            int(legacy_hotel_id),
            row["category_name"]
        )
        cursor.execute("""
            UPDATE expenses
            SET category_id = ?
            WHERE hotel_id = ?
              AND lower(trim(category)) = lower(trim(?))
              AND (category_id IS NULL OR TRIM(category_id) = '')
        """, (
            category_id,
            int(legacy_hotel_id),
            row["category_name"]
        ))

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_expenses_hotel_date
        ON expenses(hotel_id, expense_date, expense_time)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_expenses_hotel_category
        ON expenses(hotel_id, category_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_expenses_hotel_vendor
        ON expenses(hotel_id, vendor_id)
    """)


def create_expenses_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                expense_id TEXT PRIMARY KEY,
                expense_date TEXT,
                expense_time TEXT,
                expense_name TEXT,
                amount REAL,
                category TEXT,
                description TEXT,
                is_recurring INTEGER NOT NULL DEFAULT 0,
                recurrence_frequency TEXT,
                recurrence_start_date TEXT,
                next_due_date TEXT
            )""")

        _migrate_expenses_schema(cursor)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def _resolve_category(cursor, category, category_id, hotel_id):
    """Resolve and validate an active expense category."""
    requested_id = str(category_id or category or "").strip().upper()
    if not requested_id:
        raise ValueError("Expense Category is required.")

    record = cursor.execute("""
        SELECT category_id, category_name, status
        FROM expense_categories
        WHERE hotel_id = ?
          AND (
              category_id = ?
              OR lower(trim(category_name)) = lower(trim(?))
          )
        LIMIT 1
    """, (hotel_id, requested_id, str(category or "").strip())).fetchone()

    if record is None:
        raise ValueError("Invalid Expense Category.")

    if record["status"] != "Active":
        raise ValueError("Selected Expense Category is inactive.")

    return record


def _resolve_vendor(cursor, vendor_id, hotel_id):
    """Resolve an active supplier as the expense vendor."""
    vendor_id = str(vendor_id or "").strip().upper()
    if not vendor_id:
        return None

    record = cursor.execute("""
        SELECT supplier_id, supplier_name, status
        FROM suppliers
        WHERE hotel_id = ? AND supplier_id = ?
        LIMIT 1
    """, (hotel_id, vendor_id)).fetchone()

    if record is None:
        raise ValueError("Vendor not found for the current hotel.")

    if str(record["status"] or "").strip().lower() != "active":
        raise ValueError("Selected Vendor is inactive.")

    return record


def _vendor_options(hotel_id):
    connection = get_connection()
    try:
        return connection.execute("""
            SELECT supplier_id, supplier_name
            FROM suppliers
            WHERE hotel_id = ? AND status = 'Active'
            ORDER BY supplier_name COLLATE NOCASE
        """, (hotel_id,)).fetchall()
    finally:
        connection.close()



def _resolve_department(cursor, department_id, hotel_id):
    """Resolve an active department for the current hotel."""
    department_id = str(department_id or "").strip().upper()
    if not department_id:
        return None

    record = cursor.execute(
        """
        SELECT department_id, department_name, status
        FROM department
        WHERE hotel_id = ? AND department_id = ?
        LIMIT 1
        """,
        (hotel_id, department_id),
    ).fetchone()

    if record is None:
        raise ValueError("Department not found for the current hotel.")

    if str(record["status"] or "").strip().lower() != "active":
        raise ValueError("Selected Department is inactive.")

    return record


EXPENSE_RECURRENCE_FREQUENCIES = (
    "Daily",
    "Weekly",
    "Monthly",
    "Quarterly",
    "Yearly",
)


def _validate_recurring_expense(is_recurring, recurrence_frequency, recurrence_start_date):
    """Validate recurring expense configuration."""
    if not is_recurring:
        return 0, None, None

    frequency = str(recurrence_frequency or "").strip().title()
    if frequency not in EXPENSE_RECURRENCE_FREQUENCIES:
        raise ValueError("Invalid recurring expense frequency.")

    start_date = str(recurrence_start_date or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date):
        raise ValueError("Recurring start date must be in YYYY-MM-DD format.")

    return 1, frequency, start_date


def _calculate_next_due_date(start_date, frequency):
    from calendar import monthrange
    from datetime import date, timedelta

    current = date.fromisoformat(start_date)

    if frequency == "Daily":
        return (current + timedelta(days=1)).isoformat()
    if frequency == "Weekly":
        return (current + timedelta(days=7)).isoformat()
    if frequency == "Monthly":
        # Move exactly one calendar month forward while preserving the day
        # when possible (e.g. 2026-09-01 -> 2026-10-01).
        total = current.year * 12 + current.month - 1 + 1
        year, month0 = divmod(total, 12)
        month = month0 + 1
        day = min(current.day, monthrange(year, month)[1])
        return f"{year:04d}-{month:02d}-{day:02d}"
    if frequency == "Quarterly":
        total = current.year * 12 + current.month - 1 + 3
        year, month0 = divmod(total, 12)
        month = month0 + 1
        return f"{year:04d}-{month:02d}-{min(current.day, monthrange(year, month)[1]):02d}"
    if frequency == "Yearly":
        year = current.year + 1
        return f"{year:04d}-{current.month:02d}-{min(current.day, monthrange(year, current.month)[1]):02d}"

    raise ValueError("Invalid recurring expense frequency.")


EXPENSE_PAYMENT_METHODS = (
    "Cash",
    "Card",
    "UPI",
    "Online",
    "Bank Transfer",
    "Cheque",
    "Other",
)


def _normalize_payment_method(payment_method):
    value = " ".join(str(payment_method or "").strip().split())
    if not value:
        raise ValueError("Expense Payment Method is required.")

    for method in EXPENSE_PAYMENT_METHODS:
        if value.lower() == method.lower():
            return method

    raise ValueError("Invalid Expense Payment Method.")


def save_expense(
    expense_id,
    expense_date,
    expense_time,
    expense_name,
    amount,
    category,
    description,
    category_id=None,
    vendor_id=None,
    payment_method=None,
    receipt_reference=None,
    department_id=None,
    is_recurring=False,
    recurrence_frequency=None,
    recurrence_start_date=None,
    hotel_id=None,
):
    require_current_user_permission("Expenses", "Create")
    hotel_id = _resolve_hotel_id(hotel_id)

    expense_id = str(expense_id or "").strip().upper()
    expense_name = str(expense_name or "").strip()
    description = str(description or "").strip()
    receipt_reference = " ".join(str(receipt_reference or "").strip().split()) or None
    if receipt_reference and len(receipt_reference) > 100:
        raise ValueError("Receipt / Reference must be 100 characters or fewer.")

    if not expense_id:
        raise ValueError("Expense ID is required.")
    if not expense_name:
        raise ValueError("Expense Name is required.")
    if amount is None or float(amount) <= 0:
        raise ValueError("Expense amount must be greater than zero.")
    if not expense_date:
        raise ValueError("Expense Date is required.")
    if not expense_time:
        raise ValueError("Expense Time is required.")
    if not description:
        raise ValueError("Expense Description is required.")

    payment_method = _normalize_payment_method(payment_method)

    connection = get_connection()
    try:
        cursor = connection.cursor()

        category_record = _resolve_category(
            cursor, category, category_id, hotel_id
        )
        vendor_record = _resolve_vendor(cursor, vendor_id, hotel_id)
        department_record = _resolve_department(cursor, department_id, hotel_id)

        recurring_flag, recurrence_frequency, recurrence_start_date = _validate_recurring_expense(is_recurring, recurrence_frequency, recurrence_start_date)
        next_due_date = (
            _calculate_next_due_date(recurrence_start_date, recurrence_frequency)
            if recurring_flag else None
        )

        duplicate = cursor.execute("""
            SELECT 1
            FROM expenses
            WHERE expense_id = ?
        """, (expense_id,)).fetchone()
        if duplicate:
            raise ValueError("Expense ID already exists.")

        now = _current_timestamp()
        cursor.execute("""
            INSERT INTO expenses(
                expense_id,
                hotel_id,
                expense_date,
                expense_time,
                expense_name,
                amount,
                category,
                category_id,
                vendor_id,
                vendor_name,
                payment_method,
                receipt_reference,
                department_id,
                department_name,
                approval_status,
                approved_by,
                approved_at,
                approval_note,
                description,
                created_at,
                updated_at,
                is_recurring,
                recurrence_frequency,
                recurrence_start_date,
                next_due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            expense_id,
            hotel_id,
            expense_date,
            expense_time,
            expense_name,
            float(amount),
            category_record["category_name"],
            category_record["category_id"],
            vendor_record["supplier_id"] if vendor_record else None,
            vendor_record["supplier_name"] if vendor_record else None,
            payment_method,
            receipt_reference,
            department_record["department_id"] if department_record else None,
            department_record["department_name"] if department_record else None,
            "Pending",
            None,
            None,
            None,
            description,
            now,
            now,
            recurring_flag,
            recurrence_frequency,
            recurrence_start_date,
            next_due_date,
        ))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Expenses",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_expense completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _print_expense(record):
    print("=" * 60)
    print("Expense ID  :", record["expense_id"])
    print("Date        :", record["expense_date"])
    print("Time        :", record["expense_time"])
    print("-" * 60)
    print("Name        :", record["expense_name"])
    print("Amount      :", record["amount"])
    print("Category ID :", record["category_id"] or "Legacy")
    print("Category    :", record["category"])
    print("Vendor ID   :", record["vendor_id"] or "Not Provided")
    print("Vendor      :", record["vendor_name"] or "Not Provided")
    print("Payment     :", record["payment_method"] or "Not Provided")
    print("Receipt/Ref :", record["receipt_reference"] or "Not Provided")
    print("Department  :", record["department_name"] or "Not Provided")
    print("Recurring   :", "Yes" if record["is_recurring"] else "No")
    if record["is_recurring"]:
        print("Frequency   :", record["recurrence_frequency"] or "Not Provided")
        print("Start Date  :", record["recurrence_start_date"] or "Not Provided")
        print("Next Due    :", record["next_due_date"] or "Not Provided")
    print("Approval    :", record["approval_status"] or "Pending")
    print("Approved By :", record["approved_by"] or "Not Provided")
    print("Approved At :", record["approved_at"] or "Not Provided")
    print("Approval Note:", record["approval_note"] or "Not Provided")
    print("Description :", record["description"])
    print("=" * 60)


def view_expenses(hotel_id=None):
    require_current_user_permission("Expenses", "View")
    hotel_id = _resolve_hotel_id(hotel_id)

    print("=" * 60)
    print("                    EXPENSE HISTORY")
    print("=" * 60)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT expense_id, hotel_id, expense_date, expense_time,
                   expense_name, amount, category, category_id,
                   vendor_id, vendor_name, payment_method, receipt_reference,
                   department_id, department_name,
                   is_recurring, recurrence_frequency, recurrence_start_date, next_due_date,
                   approval_status, approved_by, approved_at, approval_note,
                   description, created_at, updated_at
            FROM expenses
            WHERE hotel_id = ?
            ORDER BY expense_date DESC, expense_time DESC, expense_id DESC
        """, (hotel_id,))
        records = cursor.fetchall()

        if not records:
            print("No Expenses Found.")
            return

        for record in records:
            _print_expense(record)
    finally:
        connection.close()


def search_expense(hotel_id=None):
    require_current_user_permission("Expenses", "View")
    hotel_id = _resolve_hotel_id(hotel_id)

    print("=" * 60)
    print("                    SEARCH EXPENSE")
    print("=" * 60)

    expense_id = input("Enter Expense ID : ").strip().upper()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT expense_id, hotel_id, expense_date, expense_time,
                   expense_name, amount, category, category_id,
                   vendor_id, vendor_name, payment_method, receipt_reference,
                   department_id, department_name,
                   is_recurring, recurrence_frequency, recurrence_start_date, next_due_date,
                   approval_status, approved_by, approved_at, approval_note,
                   description, created_at, updated_at
            FROM expenses
            WHERE hotel_id = ? AND expense_id = ?
        """, (hotel_id, expense_id)).fetchone()

        if record:
            _print_expense(record)
        else:
            print("Expense Not Found.")
    finally:
        connection.close()


def update_expense(hotel_id=None):
    require_current_user_permission("Expenses", "Update")
    hotel_id = _resolve_hotel_id(hotel_id)

    print("=" * 60)
    print("                    UPDATE EXPENSE")
    print("=" * 60)

    expense_id = input("Enter Expense ID : ").strip().upper()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT *
            FROM expenses
            WHERE hotel_id = ? AND expense_id = ?
        """, (hotel_id, expense_id)).fetchone()

        if not record:
            print("Expense Not Found.")
            return

        expense_name = input(
            f"Expense Name ({record['expense_name']}) : "
        ).strip() or record["expense_name"]

        amount_input = input(
            f"Amount ({record['amount']}) : "
        ).strip()

        amount = (
            validate_positive_number("Amount : ")
            if amount_input == ""
            else float(amount_input)
        )
        if amount <= 0:
            raise ValueError("Expense amount must be greater than zero.")

        options = get_active_expense_category_options(hotel_id)
        print("\nActive Expense Categories:")
        for option in options:
            marker = " (Current)" if option["category_id"] == record["category_id"] else ""
            print(
                f"{option['category_id']} - "
                f"{option['category_name']}{marker}"
            )

        category_input = input(
            f"Category ID ({record['category_id'] or record['category']}) : "
        ).strip().upper()

        if category_input:
            category_record = _resolve_category(
                cursor, category_input, category_input, hotel_id
            )
        else:
            category_record = _resolve_category(
                cursor, record["category"], record["category_id"], hotel_id
            )

        payment_input = input(
            f"Payment Method ({record['payment_method'] or 'Not Provided'}) : "
        ).strip()

        payment_method = (
            _normalize_payment_method(payment_input)
            if payment_input
            else _normalize_payment_method(record["payment_method"])
        )

        departments = get_active_department_options()
        selected_department_id = record["department_id"]

        print("\nActive Departments:")
        print("0. Not Provided")
        for index, department in enumerate(departments, start=1):
            print(
                f"{index}. {department['department_id']} - "
                f"{department['department_name']}"
            )

        department_choice = input(
            f"Select Department ({record['department_name'] or 'Not Provided'}) : "
        ).strip()

        if department_choice == "0" or not department_choice:
            selected_department_id = None
        elif department_choice.isdigit() and 1 <= int(department_choice) <= len(departments):
            selected_department_id = departments[int(department_choice) - 1]["department_id"]
        else:
            raise ValueError("Invalid Department selection.")

        receipt_input = input(
            f"Receipt / Reference ({record['receipt_reference'] or 'Not Provided'}) : "
        ).strip()
        receipt_reference = (
            " ".join(receipt_input.split()) or record["receipt_reference"] or None
        )
        if receipt_reference and len(receipt_reference) > 100:
            raise ValueError("Receipt / Reference must be 100 characters or fewer.")

        description = input(
            f"Description ({record['description']}) : "
        ).strip() or record["description"]

        if not description:
            raise ValueError("Expense Description is required.")

        now = _current_timestamp()
        cursor.execute("""
            UPDATE expenses
            SET
                expense_name = ?,
                amount = ?,
                category = ?,
                category_id = ?,
                payment_method = ?,
                receipt_reference = ?,
                department_id = ?,
                department_name = (
                    SELECT department_name
                    FROM department
                    WHERE department_id = ? AND hotel_id = ?
                ),
                approval_status = 'Pending',
                approved_by = NULL,
                approved_at = NULL,
                approval_note = 'Expense updated; approval required again.',
                description = ?,
                updated_at = ?
            WHERE hotel_id = ? AND expense_id = ?
        """, (
            expense_name,
            amount,
            category_record["category_name"],
            category_record["category_id"],
            payment_method,
            receipt_reference,
            selected_department_id,
            selected_department_id,
            hotel_id,
            description,
            now,
            hotel_id,
            expense_id,
        ))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Expenses",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_expense completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Expense Updated Successfully.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def _decide_expense_approval(expense_id, decision, note=None, hotel_id=None):
    """Approve or reject an expense using the existing permission/session engine."""
    require_current_user_permission("Expenses", "Approve")
    hotel_id = _resolve_hotel_id(hotel_id)
    decision = str(decision or "").strip().title()
    if decision not in {"Approved", "Rejected"}:
        raise ValueError("Invalid expense approval decision.")

    expense_id = str(expense_id or "").strip().upper()
    if not expense_id:
        raise ValueError("Expense ID is required.")

    note = " ".join(str(note or "").strip().split()) or None
    if note and len(note) > 250:
        raise ValueError("Approval Note must be 250 characters or fewer.")

    from database.user_db import get_current_session
    session = get_current_session()
    approver = str(session.get("username") or "").strip()
    if not approver:
        raise PermissionError("Logged-in user could not be resolved.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT expense_id, approval_status
            FROM expenses
            WHERE hotel_id = ? AND expense_id = ?
        """, (hotel_id, expense_id)).fetchone()

        if not record:
            raise ValueError("Expense Not Found.")

        if record["approval_status"] != "Pending":
            raise ValueError(
                f"Expense is already {record['approval_status']}."
            )

        now = _current_timestamp()
        cursor.execute("""
            UPDATE expenses
            SET approval_status = ?,
                approved_by = ?,
                approved_at = ?,
                approval_note = ?,
                updated_at = ?
            WHERE hotel_id = ? AND expense_id = ?
        """, (
            decision,
            approver,
            now,
            note,
            now,
            hotel_id,
            expense_id,
        ))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def approve_expense(hotel_id=None):
    print("=" * 60)
    print("                    APPROVE EXPENSE")
    print("=" * 60)
    expense_id = input("Enter Expense ID : ").strip().upper()
    note = input("Approval Note (Optional) : ").strip()
    _decide_expense_approval(expense_id, "Approved", note, hotel_id)
    print("Expense Approved Successfully.")


def reject_expense(hotel_id=None):
    print("=" * 60)
    print("                    REJECT EXPENSE")
    print("=" * 60)
    expense_id = input("Enter Expense ID : ").strip().upper()
    note = input("Rejection Reason (Optional) : ").strip()
    _decide_expense_approval(expense_id, "Rejected", note, hotel_id)
    print("Expense Rejected Successfully.")


def view_pending_expense_approvals(hotel_id=None):
    require_current_user_permission("Expenses", "Approve")
    hotel_id = _resolve_hotel_id(hotel_id)

    connection = get_connection()
    try:
        records = connection.execute("""
            SELECT expense_id, expense_date, expense_name, amount,
                   category, vendor_name, department_name, approval_status
            FROM expenses
            WHERE hotel_id = ? AND approval_status = 'Pending'
            ORDER BY expense_date ASC, expense_id ASC
        """, (hotel_id,)).fetchall()
    finally:
        connection.close()

    print("=" * 60)
    print("                PENDING EXPENSE APPROVALS")
    print("=" * 60)
    if not records:
        print("No Pending Expense Approvals.")
        return

    for record in records:
        print(f"Expense ID  : {record['expense_id']}")
        print(f"Date        : {record['expense_date']}")
        print(f"Name        : {record['expense_name']}")
        print(f"Amount      : {record['amount']}")
        print(f"Category    : {record['category']}")
        print(f"Vendor      : {record['vendor_name'] or 'Not Provided'}")
        print(f"Department  : {record['department_name'] or 'Not Provided'}")
        print(f"Status      : {record['approval_status']}")
        print("-" * 60)


def delete_expense(hotel_id=None):
    require_current_user_permission("Expenses", "Delete")
    hotel_id = _resolve_hotel_id(hotel_id)

    print("=" * 60)
    print("                    DELETE EXPENSE")
    print("=" * 60)

    expense_id = input("Enter Expense ID : ").strip().upper()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        record = cursor.execute("""
            SELECT expense_id
            FROM expenses
            WHERE hotel_id = ? AND expense_id = ?
        """, (hotel_id, expense_id)).fetchone()

        if not record:
            print("Expense Not Found.")
            return

        cursor.execute("""
            DELETE FROM expenses
            WHERE hotel_id = ? AND expense_id = ?
        """, (hotel_id, expense_id))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Expenses",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_expense completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Expense Deleted Successfully.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_expense_payment_methods():
    return EXPENSE_PAYMENT_METHODS
