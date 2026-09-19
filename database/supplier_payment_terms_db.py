from datetime import datetime, timedelta

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


def _timestamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def create_supplier_payment_terms_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supplier_payment_terms(
                supplier_id TEXT NOT NULL,
                hotel_id INTEGER NOT NULL,
                payment_type TEXT NOT NULL DEFAULT 'Cash'
                    CHECK(payment_type IN ('Cash', 'Credit')),
                credit_days INTEGER NOT NULL DEFAULT 0
                    CHECK(credit_days >= 0),
                advance_percentage REAL NOT NULL DEFAULT 0
                    CHECK(advance_percentage >= 0 AND advance_percentage <= 100),
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(supplier_id, hotel_id),
                FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id)
                    ON UPDATE CASCADE ON DELETE RESTRICT
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_supplier_payment_terms_hotel "
            "ON supplier_payment_terms(hotel_id)"
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _get_supplier(cursor, supplier_id, hotel_id):
    return cursor.execute(
        "SELECT supplier_id, supplier_name, status FROM suppliers "
        "WHERE supplier_id = ? AND hotel_id = ?",
        (supplier_id, hotel_id)
    ).fetchone()


def get_supplier_payment_terms(supplier_id):
    hotel_id = get_current_hotel_id()
    supplier_id = str(supplier_id or "").strip().upper()
    connection = get_connection()
    try:
        return connection.execute("""
            SELECT s.supplier_id, s.supplier_name, s.status,
                   COALESCE(pt.payment_type, 'Cash') AS payment_type,
                   COALESCE(pt.credit_days, 0) AS credit_days,
                   COALESCE(pt.advance_percentage, 0) AS advance_percentage,
                   pt.notes, pt.created_at, pt.updated_at
            FROM suppliers s
            LEFT JOIN supplier_payment_terms pt
              ON pt.supplier_id = s.supplier_id
             AND pt.hotel_id = s.hotel_id
            WHERE s.supplier_id = ? AND s.hotel_id = ?
        """, (supplier_id, hotel_id)).fetchone()
    finally:
        connection.close()


def save_supplier_payment_terms(supplier_id, payment_type, credit_days, advance_percentage, notes=None):
    require_current_user_permission("Inventory", "Update")
    hotel_id = get_current_hotel_id()
    supplier_id = str(supplier_id or "").strip().upper()
    payment_type = str(payment_type or "").strip().title()
    credit_days = int(credit_days)
    advance_percentage = float(advance_percentage)
    if payment_type not in {"Cash", "Credit"}:
        raise ValueError("Payment Type must be Cash or Credit.")
    if credit_days < 0:
        raise ValueError("Credit period cannot be negative.")
    if payment_type == "Cash" and credit_days != 0:
        raise ValueError("Cash payment terms must have 0 credit days.")
    if payment_type == "Credit" and credit_days <= 0:
        raise ValueError("Credit payment terms must have at least 1 credit day.")
    if not 0 <= advance_percentage <= 100:
        raise ValueError("Advance percentage must be between 0 and 100.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        supplier = _get_supplier(cursor, supplier_id, hotel_id)
        if supplier is None:
            raise ValueError("Supplier Not Found for the current hotel.")
        now = _timestamp()
        existing = cursor.execute(
            "SELECT 1 FROM supplier_payment_terms WHERE supplier_id=? AND hotel_id=?",
            (supplier_id, hotel_id)
        ).fetchone()
        if existing:
            cursor.execute("""
                UPDATE supplier_payment_terms
                SET payment_type=?, credit_days=?, advance_percentage=?,
                    notes=?, updated_at=?
                WHERE supplier_id=? AND hotel_id=?
            """, (payment_type, credit_days, advance_percentage, notes, now, supplier_id, hotel_id))
        else:
            cursor.execute("""
                INSERT INTO supplier_payment_terms(
                    supplier_id, hotel_id, payment_type, credit_days,
                    advance_percentage, notes, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """, (supplier_id, hotel_id, payment_type, credit_days, advance_percentage, notes, now, now))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def view_supplier_payment_terms():
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT s.supplier_id, s.supplier_name, s.status,
                   COALESCE(pt.payment_type, 'Cash') AS payment_type,
                   COALESCE(pt.credit_days, 0) AS credit_days,
                   COALESCE(pt.advance_percentage, 0) AS advance_percentage,
                   pt.notes
            FROM suppliers s
            LEFT JOIN supplier_payment_terms pt
              ON pt.supplier_id=s.supplier_id AND pt.hotel_id=s.hotel_id
            WHERE s.hotel_id=?
            ORDER BY s.supplier_name
        """, (hotel_id,)).fetchall()
        if not rows:
            print("No Suppliers Found.")
            return
        for row in rows:
            print("=" * 72)
            print("Supplier ID       :", row["supplier_id"])
            print("Supplier Name     :", row["supplier_name"])
            print("Supplier Status   :", row["status"])
            print("Payment Type      :", row["payment_type"])
            print("Credit Period     :", f'{row["credit_days"]} days')
            print("Advance           :", f'{float(row["advance_percentage"]):.2f}%')
            print("Notes             :", row["notes"] or "-")
        print("=" * 72)
    finally:
        connection.close()


def calculate_supplier_due_date(supplier_id, base_date):
    """Calculate the supplier payment due date from a DD-MM-YYYY base date."""
    terms = get_supplier_payment_terms(supplier_id)
    if terms is None:
        raise ValueError("Supplier Not Found for the current hotel.")
    parsed = datetime.strptime(str(base_date).strip(), "%d-%m-%Y")
    due = parsed + timedelta(days=int(terms["credit_days"] or 0))
    return due.strftime("%d-%m-%Y")


def supplier_payment_terms_management():
    require_current_user_permission("Inventory", "View")
    from utils.validators import validate_menu_choice, validate_non_empty, validate_percentage

    while True:
        print("=" * 72)
        print("                  SUPPLIER PAYMENT TERMS")
        print("=" * 72)
        print("1. View Payment Terms")
        print("2. Set / Update Supplier Payment Terms")
        print("3. Calculate Due Date")
        print("4. Back")
        choice = validate_menu_choice("Enter Your Choice : ", ["1", "2", "3", "4"])
        try:
            if choice == "1":
                view_supplier_payment_terms()
            elif choice == "2":
                require_current_user_permission("Inventory", "Update")
                supplier_id = validate_non_empty("Enter Supplier ID : ").strip().upper()
                current = get_supplier_payment_terms(supplier_id)
                if current is None:
                    raise ValueError("Supplier Not Found for the current hotel.")
                print("1. Cash")
                print("2. Credit")
                payment_choice = validate_menu_choice("Enter Payment Type : ", ["1", "2"])
                payment_type = "Cash" if payment_choice == "1" else "Credit"
                if payment_type == "Cash":
                    credit_days = 0
                else:
                    raw_days = validate_non_empty("Credit Period (days) : ")
                    if not raw_days.isdigit():
                        raise ValueError("Credit period must be a whole number.")
                    credit_days = int(raw_days)
                    if credit_days <= 0:
                        raise ValueError("Credit payment terms must have at least 1 credit day.")
                advance_percentage = validate_percentage("Advance Percentage : ")
                notes = input("Payment Terms Notes (optional) : ").strip() or None
                save_supplier_payment_terms(supplier_id, payment_type, credit_days, advance_percentage, notes)
                print("Supplier Payment Terms Saved Successfully.")
            elif choice == "3":
                supplier_id = validate_non_empty("Enter Supplier ID : ").strip().upper()
                base_date = validate_non_empty("Base Date (DD-MM-YYYY) : ").strip()
                due_date = calculate_supplier_due_date(supplier_id, base_date)
                print("Calculated Due Date :", due_date)
            else:
                break
        except (ValueError, PermissionError) as exc:
            print(f"Error: {exc}")
