import json

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


def _print_records(title, empty_message, records):
    print("=" * 60)
    print(title.center(60))
    print("=" * 60)

    if not records:
        print(empty_message)
        print("=" * 60)
        return

    for record in records:
        print("-" * 60)
        for key in record.keys():
            value = record[key]
            print(f"{key.replace('_', ' ').title()} : {value}")

    print("=" * 60)


def _get_orders():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY rowid DESC")
        return cursor.fetchall()
    finally:
        connection.close()


def _order_total(order):
    """Return the authoritative stored total when available.

    Older databases may not yet have billing-total columns, so calculate
    the value from the serialized cart as a backward-compatible fallback.
    """
    keys = set(order.keys())

    if "grand_total" in keys and order["grand_total"] is not None:
        return float(order["grand_total"])

    try:
        cart = json.loads(order["cart"] or "[]")
        subtotal = sum(float(item.get("subtotal", 0)) for item in cart)
        return subtotal * 1.05
    except (TypeError, ValueError, json.JSONDecodeError):
        return 0.0


def sales_report():
    try:
        orders = _get_orders()

        print("=" * 60)
        print("SALES REPORT".center(60))
        print("=" * 60)

        if not orders:
            print("No Sales Found.")
            print("=" * 60)
            return

        total_sales = 0.0

        for order in orders:
            total = _order_total(order)
            total_sales += total

            print("-" * 60)
            print(f"Order ID     : {order['order_id']}")
            print(f"Date         : {order['order_date']}")
            print(f"Time         : {order['order_time']}")
            print(f"Customer     : {order['customer_name']}")
            print(f"Grand Total  : ₹{total:.2f}")

        print("-" * 60)
        print(f"TOTAL SALES  : ₹{total_sales:.2f}")
        print("=" * 60)

    except Exception as exc:
        print(f"Error generating sales report: {exc}")


def restaurant_report():
    try:
        orders = _get_orders()

        print("=" * 60)
        print("RESTAURANT REPORT".center(60))
        print("=" * 60)

        if not orders:
            print("No Restaurant Orders Found.")
            print("=" * 60)
            return

        for order in orders:
            print("-" * 60)
            print(f"Order ID       : {order['order_id']}")
            print(f"Date           : {order['order_date']}")
            print(f"Time           : {order['order_time']}")
            print(f"Customer Name  : {order['customer_name']}")
            print(f"Mobile         : {order['customer_mobile']}")
            print(f"Table Number   : {order['table_number']}")
            print(f"Grand Total    : ₹{_order_total(order):.2f}")

            try:
                cart = json.loads(order["cart"] or "[]")
                print("Items:")
                for item in cart:
                    print(
                        f"  {item.get('name', 'Unknown')} x{item.get('quantity', 0)} "
                        f"= ₹{item.get('subtotal', 0)}"
                    )
            except (TypeError, ValueError, json.JSONDecodeError):
                print("Items: Unable to read order cart.")

        print("=" * 60)

    except Exception as exc:
        print(f"Error generating restaurant report: {exc}")


def _table_report(table_name, title, empty_message):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rowid DESC")
        records = cursor.fetchall()
    finally:
        connection.close()

    _print_records(title, empty_message, records)


def room_report():
    try:
        _table_report(
            "room_bookings",
            "ROOM BOOKING REPORT",
            "No Room Bookings Found."
        )
    except Exception as exc:
        print(f"Error generating room report: {exc}")


def table_report():
    try:
        _table_report(
            "table_bookings",
            "TABLE BOOKING REPORT",
            "No Table Bookings Found."
        )
    except Exception as exc:
        print(f"Error generating table report: {exc}")


def customer_report():
    try:
        _table_report(
            "customers",
            "CUSTOMER REPORT",
            "No Customers Found."
        )
    except Exception as exc:
        print(f"Error generating customer report: {exc}")


def staff_report():
    try:
        _table_report(
            "staff",
            "STAFF REPORT",
            "No Staff Found."
        )
    except Exception as exc:
        print(f"Error generating staff report: {exc}")


def salary_report():
    try:
        _table_report(
            "salary",
            "SALARY REPORT",
            "No Salary Records Found."
        )
    except Exception as exc:
        print(f"Error generating salary report: {exc}")


def inventory_report():
    try:
        _table_report(
            "inventory",
            "INVENTORY REPORT",
            "No Inventory Records Found."
        )
    except Exception as exc:
        print(f"Error generating inventory report: {exc}")


def expense_report(hotel_id=None):
    """Generate a consolidated expense report for the current hotel."""
    require_current_user_permission("Expenses", "View")
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    try:
        hotel_id = int(hotel_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid hotel context.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        records = cursor.execute(
            """
            SELECT expense_id, expense_date, expense_name, amount, category,
                   vendor_name, payment_method, department_name,
                   approval_status, is_recurring, recurrence_frequency,
                   next_due_date
            FROM expenses
            WHERE hotel_id = ?
            ORDER BY expense_date DESC, expense_id DESC
            """,
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()

    print("=" * 70)
    print("EXPENSE REPORT".center(70))
    print("=" * 70)

    if not records:
        print("No Expense Records Found.")
        print("=" * 70)
        return

    total = sum(float(row["amount"] or 0) for row in records)
    approved_total = sum(float(row["amount"] or 0) for row in records if row["approval_status"] == "Approved")
    pending_total = sum(float(row["amount"] or 0) for row in records if row["approval_status"] == "Pending")
    rejected_total = sum(float(row["amount"] or 0) for row in records if row["approval_status"] == "Rejected")
    recurring_count = sum(1 for row in records if row["is_recurring"])

    print(f"Total Expenses       : ₹{total:.2f}")
    print(f"Approved Expenses    : ₹{approved_total:.2f}")
    print(f"Pending Expenses     : ₹{pending_total:.2f}")
    print(f"Rejected Expenses    : ₹{rejected_total:.2f}")
    print(f"Expense Records      : {len(records)}")
    print(f"Recurring Expenses   : {recurring_count}")

    def grouped_total(field):
        result = {}
        for row in records:
            key = row[field] or "Not Provided"
            result[key] = result.get(key, 0.0) + float(row["amount"] or 0)
        return sorted(result.items(), key=lambda item: (-item[1], str(item[0]).lower()))

    print("-" * 70)
    print("BY CATEGORY")
    for name, amount in grouped_total("category"):
        print(f"{name:<35} : ₹{amount:.2f}")

    print("-" * 70)
    print("BY PAYMENT METHOD")
    for name, amount in grouped_total("payment_method"):
        print(f"{name:<35} : ₹{amount:.2f}")

    print("-" * 70)
    print("BY DEPARTMENT")
    for name, amount in grouped_total("department_name"):
        print(f"{name:<35} : ₹{amount:.2f}")

    print("-" * 70)
    print("EXPENSE DETAILS")
    for row in records:
        print(
            f"{row['expense_id']} | {row['expense_date']} | "
            f"{row['expense_name']} | ₹{float(row['amount'] or 0):.2f} | "
            f"{row['approval_status'] or 'Pending'}"
        )

    print("=" * 70)


def hotel_dashboard():
    """Show dashboard counts from the authoritative SQLite tables."""
    tables = (
        ("Restaurant Orders", "orders"),
        ("Room Bookings", "room_bookings"),
        ("Table Bookings", "table_bookings"),
        ("Customers", "customers"),
        ("Staff", "staff"),
        ("Departments", "department"),  # actual schema is singular
        ("Inventory Items", "inventory"),
        ("Suppliers", "suppliers"),
    )

    connection = get_connection()
    results = []

    try:
        cursor = connection.cursor()

        for title, table_name in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            results.append((title, cursor.fetchone()[0]))

    except Exception as exc:
        print(f"Error generating hotel dashboard: {exc}")
        return

    finally:
        connection.close()

    print("=" * 60)
    print("HOTEL DASHBOARD".center(60))
    print("=" * 60)

    for title, count in results:
        print(f"{title:<25}: {count}")

    print("=" * 60)
