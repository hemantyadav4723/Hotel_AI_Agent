from datetime import datetime, timedelta

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


from database.audit_db import log_business_activity
def _timestamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def create_supplier_outstanding_tables():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supplier_payments(
                payment_id TEXT NOT NULL,
                hotel_id INTEGER NOT NULL,
                supplier_id TEXT NOT NULL,
                payment_date TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                payment_method TEXT NOT NULL,
                reference_no TEXT,
                notes TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY(payment_id, hotel_id),
                FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id)
                    ON UPDATE CASCADE ON DELETE RESTRICT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_supplier_payments_hotel_supplier_date
            ON supplier_payments(hotel_id, supplier_id, payment_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_supplier_payments_hotel_reference
            ON supplier_payments(hotel_id, reference_no)
        """)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _parse_date(value, field):
    value = str(value or "").strip()
    try:
        datetime.strptime(value, "%d-%m-%Y")
    except ValueError as exc:
        raise ValueError(f"{field} must be in DD-MM-YYYY format.") from exc
    return value


def _supplier_exists(cursor, supplier_id, hotel_id):
    return cursor.execute(
        "SELECT supplier_id, supplier_name, status FROM suppliers "
        "WHERE supplier_id=? AND hotel_id=?",
        (supplier_id, hotel_id),
    ).fetchone()


def _receiving_rows(cursor, hotel_id, supplier_id=None):
    params = [hotel_id]
    where = "pr.hotel_id = ?"
    if supplier_id:
        where += " AND pr.supplier_id = ?"
        params.append(supplier_id)
    return cursor.execute(
        f"""
        SELECT pr.receiving_id, pr.po_id, pr.supplier_id, s.supplier_name,
               pr.receiving_date, pr.reference_no, pr.total_value
        FROM purchase_receivings pr
        JOIN suppliers s
          ON s.supplier_id = pr.supplier_id
         AND s.hotel_id = pr.hotel_id
        WHERE {where}
        ORDER BY pr.receiving_date DESC, pr.receiving_id DESC
        """,
        params,
    ).fetchall()


def _payment_total(cursor, hotel_id, supplier_id):
    row = cursor.execute(
        "SELECT COALESCE(SUM(amount),0) AS total FROM supplier_payments "
        "WHERE hotel_id=? AND supplier_id=?",
        (hotel_id, supplier_id),
    ).fetchone()
    return float(row["total"] or 0)


def get_supplier_outstanding(supplier_id=None):
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    supplier_id = str(supplier_id or "").strip().upper() or None

    connection = get_connection()
    try:
        cursor = connection.cursor()
        if supplier_id and not _supplier_exists(cursor, supplier_id, hotel_id):
            raise ValueError("Supplier Not Found for the current hotel.")

        receipts = _receiving_rows(cursor, hotel_id, supplier_id)
        payment_rows = cursor.execute(
            """
            SELECT supplier_id, COALESCE(SUM(amount),0) AS paid_amount
            FROM supplier_payments
            WHERE hotel_id=?
            GROUP BY supplier_id
            """,
            (hotel_id,),
        ).fetchall()
        paid_by_supplier = {r["supplier_id"]: float(r["paid_amount"] or 0) for r in payment_rows}

        suppliers = {}
        for r in receipts:
            sid = r["supplier_id"]
            suppliers.setdefault(
                sid,
                {
                    "supplier_id": sid,
                    "supplier_name": r["supplier_name"],
                    "total_purchase": 0.0,
                    "paid_amount": 0.0,
                    "balance": 0.0,
                    "last_receiving_date": None,
                },
            )
            suppliers[sid]["total_purchase"] += float(r["total_value"] or 0)
            suppliers[sid]["last_receiving_date"] = r["receiving_date"]

        for data in suppliers.values():
            data["paid_amount"] = paid_by_supplier.get(data["supplier_id"], 0.0)
            data["balance"] = round(data["total_purchase"] - data["paid_amount"], 2)

        return list(suppliers.values())
    finally:
        connection.close()


def _next_payment_id(cursor, hotel_id):
    rows = cursor.execute(
        "SELECT payment_id FROM supplier_payments "
        "WHERE hotel_id=? AND payment_id LIKE 'SPAY-%' ORDER BY payment_id DESC",
        (hotel_id,),
    ).fetchall()
    maximum = 0
    for row in rows:
        try:
            maximum = max(maximum, int(str(row["payment_id"])[5:]))
        except (ValueError, TypeError):
            continue
    return f"SPAY-{maximum + 1:05d}"


def record_supplier_payment(
    supplier_id,
    payment_date,
    amount,
    payment_method,
    reference_no=None,
    notes=None,
    created_by=None,
):
    require_current_user_permission("Inventory", "Payment")
    hotel_id = get_current_hotel_id()
    supplier_id = str(supplier_id or "").strip().upper()
    payment_date = _parse_date(payment_date, "Payment Date")
    amount = float(amount)
    payment_method = str(payment_method or "").strip().title()

    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")
    if payment_method not in {"Cash", "Bank", "UPI", "Cheque", "Other"}:
        raise ValueError("Invalid payment method.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        supplier = _supplier_exists(cursor, supplier_id, hotel_id)
        if supplier is None:
            raise ValueError("Supplier Not Found for the current hotel.")

        total_purchase = float(
            cursor.execute(
                "SELECT COALESCE(SUM(total_value),0) AS total "
                "FROM purchase_receivings WHERE hotel_id=? AND supplier_id=?",
                (hotel_id, supplier_id),
            ).fetchone()["total"] or 0
        )
        already_paid = _payment_total(cursor, hotel_id, supplier_id)
        balance = round(total_purchase - already_paid, 2)
        if balance <= 0:
            raise ValueError("No outstanding balance exists for this supplier.")
        if amount > balance:
            raise ValueError(
                f"Payment exceeds outstanding balance. Maximum payable: {balance:.2f}."
            )

        payment_id = _next_payment_id(cursor, hotel_id)
        now = _timestamp()
        cursor.execute(
            """
            INSERT INTO supplier_payments(
                payment_id, hotel_id, supplier_id, payment_date, amount,
                payment_method, reference_no, notes, created_by, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                payment_id,
                hotel_id,
                supplier_id,
                payment_date,
                amount,
                payment_method,
                str(reference_no or "").strip() or None,
                str(notes or "").strip() or None,
                created_by,
                now,
            ),
        )
        connection.commit()
        log_business_activity(
            "Supplier Outstanding",
            "PAYMENT",
            local_values={"payment_id": payment_id, "supplier_id": supplier_id},
            details=f"Supplier payment {payment_id} recorded for {supplier_id}.",
        )
        return {
            "payment_id": payment_id,
            "supplier_id": supplier_id,
            "amount": amount,
            "remaining_balance": round(balance - amount, 2),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def view_supplier_outstanding():
    rows = get_supplier_outstanding()
    print("=" * 88)
    print("                         SUPPLIER OUTSTANDING")
    print("=" * 88)
    if not rows:
        print("No Purchase Receiving / Outstanding Records Found.")
        return

    grand_purchase = grand_paid = grand_balance = 0.0
    for row in rows:
        print("-" * 88)
        print("Supplier ID       :", row["supplier_id"])
        print("Supplier Name     :", row["supplier_name"])
        print("Total Purchase    :", f"₹{row['total_purchase']:.2f}")
        print("Paid Amount       :", f"₹{row['paid_amount']:.2f}")
        print("Balance Amount    :", f"₹{row['balance']:.2f}")
        grand_purchase += row["total_purchase"]
        grand_paid += row["paid_amount"]
        grand_balance += row["balance"]

    print("-" * 88)
    print("TOTAL PURCHASE    :", f"₹{grand_purchase:.2f}")
    print("TOTAL PAID        :", f"₹{grand_paid:.2f}")
    print("TOTAL OUTSTANDING :", f"₹{grand_balance:.2f}")
    print("=" * 88)


def view_supplier_outstanding_detail(supplier_id):
    require_current_user_permission("Inventory", "View")
    supplier_id = str(supplier_id or "").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        supplier = _supplier_exists(cursor, supplier_id, hotel_id)
        if supplier is None:
            raise ValueError("Supplier Not Found for the current hotel.")

        terms = cursor.execute(
            """
            SELECT COALESCE(payment_type,'Cash') AS payment_type,
                   COALESCE(credit_days,0) AS credit_days
            FROM supplier_payment_terms
            WHERE supplier_id=? AND hotel_id=?
            """,
            (supplier_id, hotel_id),
        ).fetchone()
        payment_type = terms["payment_type"] if terms else "Cash"
        credit_days = int(terms["credit_days"] or 0) if terms else 0

        print("=" * 88)
        print(f"Supplier: {supplier['supplier_name']} ({supplier_id})")
        print(f"Payment Terms: {payment_type} | Credit Period: {credit_days} days")
        print("=" * 88)

        receipts = _receiving_rows(cursor, hotel_id, supplier_id)
        payments = cursor.execute(
            """
            SELECT payment_id, payment_date, amount, payment_method,
                   reference_no, notes, created_by
            FROM supplier_payments
            WHERE hotel_id=? AND supplier_id=?
            ORDER BY payment_date DESC, payment_id DESC
            """,
            (hotel_id, supplier_id),
        ).fetchall()

        total_purchase = sum(float(r["total_value"] or 0) for r in receipts)
        total_paid = sum(float(p["amount"] or 0) for p in payments)
        balance = round(total_purchase - total_paid, 2)

        if receipts:
            print("PURCHASE RECEIVINGS / PAYABLES")
            for r in receipts:
                base = datetime.strptime(r["receiving_date"], "%d-%m-%Y")
                due = base + timedelta(days=credit_days)
                due_date = due.strftime("%d-%m-%Y")
                amount = float(r["total_value"] or 0)
                print(
                    f"GRN {r['receiving_id']} | PO {r['po_id']} | "
                    f"Date {r['receiving_date']} | Amount ₹{amount:.2f} | "
                    f"Due {due_date}"
                )
        else:
            print("No Purchase Receiving Records Found.")

        if payments:
            print("PAYMENTS")
            for p in payments:
                print(
                    f"{p['payment_id']} | {p['payment_date']} | "
                    f"₹{float(p['amount']):.2f} | {p['payment_method']} | "
                    f"{p['reference_no'] or '-'}"
                )

        print("-" * 88)
        print("Total Purchase    :", f"₹{total_purchase:.2f}")
        print("Total Paid        :", f"₹{total_paid:.2f}")
        print("Outstanding       :", f"₹{balance:.2f}")

        if balance <= 0:
            print("Outstanding Status: CLEARED")
        else:
            today = datetime.now().date()
            overdue = False
            for r in receipts:
                due = datetime.strptime(r["receiving_date"], "%d-%m-%Y").date() + timedelta(days=credit_days)
                if due < today:
                    overdue = True
                    break
            print("Outstanding Status:", "OVERDUE" if overdue else "DUE")

        print("=" * 88)
    finally:
        connection.close()


def supplier_outstanding_management():
    require_current_user_permission("Inventory", "View")
    from utils.validators import (
        validate_menu_choice,
        validate_non_empty,
        validate_positive_number,
        validate_optional_date,
    )

    while True:
        print("=" * 88)
        print("                    SUPPLIER OUTSTANDING TRACKING")
        print("=" * 88)
        print("1. View All Supplier Outstanding")
        print("2. Supplier-wise Outstanding Detail")
        print("3. Record Supplier Payment")
        print("4. Payment History")
        print("5. Back")
        choice = validate_menu_choice("Enter Your Choice : ", ["1", "2", "3", "4", "5"])
        try:
            if choice == "1":
                view_supplier_outstanding()
            elif choice == "2":
                sid = validate_non_empty("Enter Supplier ID : ").strip().upper()
                view_supplier_outstanding_detail(sid)
            elif choice == "3":
                require_current_user_permission("Inventory", "Create")
                sid = validate_non_empty("Enter Supplier ID : ").strip().upper()
                date = validate_optional_date("Payment Date (DD-MM-YYYY, blank=today) : ")
                if not date:
                    date = datetime.now().strftime("%d-%m-%Y")
                amount = validate_positive_number("Payment Amount : ")
                print("1. Cash")
                print("2. Bank")
                print("3. UPI")
                print("4. Cheque")
                print("5. Other")
                method_choice = validate_menu_choice("Payment Method : ", ["1","2","3","4","5"])
                method = {"1":"Cash","2":"Bank","3":"UPI","4":"Cheque","5":"Other"}[method_choice]
                reference = input("Reference No. (optional) : ").strip() or None
                notes = input("Notes (optional) : ").strip() or None
                result = record_supplier_payment(sid, date, amount, method, reference, notes)
                print(
                    f"Supplier Payment Recorded: {result['payment_id']} | "
                    f"Remaining Balance: ₹{result['remaining_balance']:.2f}"
                )
            elif choice == "4":
                sid = input("Supplier ID (blank=all) : ").strip().upper() or None
                connection = get_connection()
                try:
                    rows = connection.execute(
                        """
                        SELECT sp.payment_id, sp.supplier_id, s.supplier_name,
                               sp.payment_date, sp.amount, sp.payment_method,
                               sp.reference_no
                        FROM supplier_payments sp
                        JOIN suppliers s
                          ON s.supplier_id=sp.supplier_id AND s.hotel_id=sp.hotel_id
                        WHERE sp.hotel_id=?
                          AND (? IS NULL OR sp.supplier_id=?)
                        ORDER BY sp.payment_date DESC, sp.payment_id DESC
                        """,
                        (get_current_hotel_id(), sid, sid),
                    ).fetchall()
                finally:
                    connection.close()
                if not rows:
                    print("No Supplier Payment Records Found.")
                else:
                    for row in rows:
                        print(
                            f"{row['payment_id']} | {row['supplier_id']} | "
                            f"{row['supplier_name']} | {row['payment_date']} | "
                            f"₹{float(row['amount']):.2f} | {row['payment_method']} | "
                            f"{row['reference_no'] or '-'}"
                        )
            else:
                break
        except (ValueError, PermissionError) as exc:
            print(f"Error: {exc}")
