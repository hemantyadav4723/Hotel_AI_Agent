"""Enterprise Reports & Analytics foundation for the hotel system.

All analytics are read-only and scoped to the active hotel.  The module
reuses the existing SQLite tables instead of creating duplicate business
records.  Date filters use the application's DD-MM-YYYY display format.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
import json

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


DATE_FORMAT = "%d-%m-%Y"


def _hotel_id(hotel_id=None):
    return int(get_current_hotel_id() if hotel_id is None else hotel_id)


def _parse_date(value):
    if value is None or not str(value).strip():
        return None
    try:
        return datetime.strptime(str(value).strip(), DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError("Invalid date. Use DD-MM-YYYY.") from exc


def _prompt_date_range():
    print("Date Filter (leave blank for all available data)")
    start = input("From Date (DD-MM-YYYY) : ").strip()
    end = input("To Date (DD-MM-YYYY)   : ").strip()
    start_date = _parse_date(start) if start else None
    end_date = _parse_date(end) if end else None
    if start_date and end_date and start_date > end_date:
        raise ValueError("From Date cannot be after To Date.")
    return start_date, end_date


def _date_text_bounds(start_date, end_date):
    """Return ISO bounds for SQLite dates stored as DD-MM-YYYY/timestamps.

    Queries that need date arithmetic use normalized Python records. This
    helper is used only for columns stored in ISO format (expense recurrence
    fields, created_at where applicable).
    """
    return (
        start_date.isoformat() if start_date else None,
        end_date.isoformat() if end_date else None,
    )


def _in_range(day, start_date, end_date):
    if day is None:
        return False
    return (start_date is None or day >= start_date) and (end_date is None or day <= end_date)


def _parse_flexible_date(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in (
        "%d-%m-%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %I:%M:%S %p",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _month_key(day):
    return day.strftime("%Y-%m") if day else "Unknown"


def _money(value):
    return float(value or 0.0)


def _safe_json_cart(value):
    try:
        return json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _room_bookings(hotel_id):
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT * FROM room_bookings WHERE hotel_id = ? ORDER BY rowid",
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()


def _orders(hotel_id):
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT * FROM orders WHERE hotel_id = ? ORDER BY rowid",
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()


def _expenses(hotel_id):
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT * FROM expenses WHERE hotel_id = ? ORDER BY rowid",
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()


def _room_revenue_rows(hotel_id, start_date=None, end_date=None):
    rows = []
    for row in _room_bookings(hotel_id):
        day = _parse_flexible_date(row["check_in_date"] or row["booking_date"])
        status = (row["booking_status"] or "").strip()
        if status in {"Cancelled", "No-Show"}:
            continue
        if not _in_range(day, start_date, end_date):
            continue
        rows.append(row)
    return rows


def _restaurant_revenue_rows(hotel_id, start_date=None, end_date=None):
    rows = []
    for row in _orders(hotel_id):
        day = _parse_flexible_date(row["order_date"])
        status = (row["order_status"] or "").strip()
        if status == "Cancelled":
            continue
        if not _in_range(day, start_date, end_date):
            continue
        rows.append(row)
    return rows


def _room_nights_for_booking(row, start_date=None, end_date=None):
    check_in = _parse_flexible_date(row["check_in_date"] or row["booking_date"])
    check_out = _parse_flexible_date(row["expected_check_out"])
    if check_in is None:
        return 0
    if check_out is None:
        nights = int(row["nights"] or row["days"] or 0)
        check_out = check_in + timedelta(days=max(nights, 0))
    if check_out <= check_in:
        return 0
    range_start = start_date or check_in
    range_end_exclusive = (end_date + timedelta(days=1)) if end_date else check_out
    overlap_start = max(check_in, range_start)
    overlap_end = min(check_out, range_end_exclusive)
    return max((overlap_end - overlap_start).days, 0)


def _active_room_count(hotel_id):
    connection = get_connection()
    try:
        return int(connection.execute(
            "SELECT COUNT(*) FROM rooms WHERE hotel_id = ? AND COALESCE(is_active, 1) = 1",
            (hotel_id,),
        ).fetchone()[0])
    finally:
        connection.close()


def _print_title(title):
    print("=" * 76)
    print(title.center(76))
    print("=" * 76)


def _print_date_range(start_date, end_date):
    if start_date or end_date:
        print(f"Period              : {start_date or 'Beginning'} to {end_date or 'Today'}")
    else:
        print("Period              : All Available Data")


def _run_report(title, builder):
    try:
        require_current_user_permission("Reports", "Reports")
        start_date, end_date = _prompt_date_range()
        data = builder(_hotel_id(), start_date, end_date)
        _print_title(title)
        _print_date_range(start_date, end_date)
        return data
    except Exception as exc:
        print(f"Error generating report: {exc}")
        return None


def get_revenue_summary(hotel_id=None, start_date=None, end_date=None):
    hotel_id = _hotel_id(hotel_id)
    room = sum(_money(r["grand_total"]) for r in _room_revenue_rows(hotel_id, start_date, end_date))
    restaurant = sum(_money(r["grand_total"]) for r in _restaurant_revenue_rows(hotel_id, start_date, end_date))
    return {"room_revenue": room, "restaurant_revenue": restaurant, "total_revenue": room + restaurant}



def get_dashboard_home_summary(hotel_id):
    """Return today's operational dashboard KPIs scoped to one hotel."""
    from datetime import date as _date
    today = _date.today()
    iso_today = today.isoformat()
    display_today = today.strftime("%d-%m-%Y")
    connection = get_connection()
    try:
        room_revenue = sum(_money(r["grand_total"]) for r in _room_revenue_rows(hotel_id, today, today))
        restaurant_revenue = sum(_money(r["grand_total"]) for r in _restaurant_revenue_rows(hotel_id, today, today))
        room_count = connection.execute("SELECT COUNT(*) FROM rooms WHERE hotel_id = ? AND is_active = 1", (hotel_id,)).fetchone()[0]
        occupied_count = connection.execute("SELECT COUNT(*) FROM rooms WHERE hotel_id = ? AND is_active = 1 AND lower(COALESCE(room_status,'')) = 'occupied'", (hotel_id,)).fetchone()[0]

        bookings = connection.execute(
            """SELECT COUNT(*) FROM room_bookings WHERE hotel_id = ?
               AND (check_in_date IN (?, ?) OR booking_date LIKE ? || '%')
               AND lower(COALESCE(booking_status,'')) NOT IN ('cancelled','no-show')""",
            (hotel_id, iso_today, display_today, iso_today),
        ).fetchone()[0]
        check_ins = connection.execute(
            """SELECT COUNT(*) FROM room_bookings WHERE hotel_id = ?
               AND (check_in_date IN (?, ?) OR booking_date LIKE ? || '%')
               AND lower(COALESCE(booking_status,'')) IN ('checked-in','checked in','occupied')""",
            (hotel_id, iso_today, display_today, iso_today),
        ).fetchone()[0]
        check_outs = connection.execute(
            """SELECT COUNT(*) FROM room_bookings WHERE hotel_id = ?
               AND (expected_check_out IN (?, ?) OR actual_check_out LIKE ? || '%')""",
            (hotel_id, iso_today, display_today, iso_today),
        ).fetchone()[0]
        restaurant_orders = connection.execute(
            "SELECT COUNT(*) FROM orders WHERE hotel_id = ? AND order_date IN (?, ?) AND lower(COALESCE(order_status,'')) <> 'cancelled'",
            (hotel_id, iso_today, display_today),
        ).fetchone()[0]
        pending_payments = connection.execute(
            """SELECT COUNT(*) FROM (
                 SELECT booking_id AS id FROM room_bookings WHERE hotel_id = ? AND lower(COALESCE(payment_status,'pending')) <> 'paid' AND COALESCE(balance_amount,0) > 0
                 UNION ALL
                 SELECT order_id AS id FROM orders WHERE hotel_id = ? AND lower(COALESCE(payment_status,'pending')) <> 'paid' AND COALESCE(balance_amount,0) > 0
               )""",
            (hotel_id, hotel_id),
        ).fetchone()[0]
        low_stock = connection.execute(
            "SELECT COUNT(*) FROM inventory WHERE hotel_id = ? AND COALESCE(quantity,0) <= COALESCE(reorder_level,0)", (hotel_id,)
        ).fetchone()[0]
        pending_issues = connection.execute(
            """SELECT COUNT(*) FROM feedback WHERE hotel_id = ?
               AND COALESCE(complaint,'') <> ''
               AND lower(COALESCE(status,'')) NOT IN ('resolved','closed','completed')""",
            (hotel_id,),
        ).fetchone()[0]
        transportation_requests = connection.execute(
            """SELECT COUNT(*) FROM transportation_requests WHERE hotel_id = ?
               AND lower(COALESCE(status,'')) NOT IN ('completed','cancelled','no-show')""",
            (hotel_id,),
        ).fetchone()[0]
        return {
            "date": iso_today,
            "room_revenue": room_revenue,
            "restaurant_revenue": restaurant_revenue,
            "total_revenue": room_revenue + restaurant_revenue,
            "bookings": bookings,
            "check_ins": check_ins,
            "check_outs": check_outs,
            "occupancy_pct": (occupied_count / room_count * 100) if room_count else 0.0,
            "occupied_rooms": occupied_count,
            "available_rooms": max(room_count - occupied_count, 0),
            "total_rooms": room_count,
            "restaurant_orders": restaurant_orders,
            "pending_payments": pending_payments,
            "low_stock_alerts": low_stock,
            "pending_guest_issues": pending_issues,
            "transportation_requests": transportation_requests,
        }
    finally:
        connection.close()

def dashboard_report():
    def build(hotel_id, start_date, end_date):
        revenue = get_revenue_summary(hotel_id, start_date, end_date)
        room = room_revenue_data(hotel_id, start_date, end_date)
        occupancy = occupancy_data(hotel_id, start_date, end_date)
        adr = adr_data(hotel_id, start_date, end_date)
        revpar = revpar_data(hotel_id, start_date, end_date)
        booking = booking_trends_data(hotel_id, start_date, end_date)
        cancellation = cancellation_data(hotel_id, start_date, end_date)
        no_show = no_show_data(hotel_id, start_date, end_date)
        customers = customer_trends_data(hotel_id, start_date, end_date)
        inventory = inventory_trends_data(hotel_id, start_date, end_date)
        expenses = expense_trends_data(hotel_id, start_date, end_date)
        departments = department_performance_data(hotel_id, start_date, end_date)
        staff = staff_report_data(hotel_id, start_date, end_date)
        profitability = profitability_data(hotel_id, start_date, end_date)
        return locals()

    data = _run_report("PROFESSIONAL HOTEL DASHBOARD", build)
    if not data:
        return
    revenue = data["revenue"]
    print(f"Total Revenue       : ₹{revenue['total_revenue']:.2f}")
    print(f"Room Revenue        : ₹{revenue['room_revenue']:.2f}")
    print(f"Restaurant Revenue  : ₹{revenue['restaurant_revenue']:.2f}")
    print(f"Occupancy           : {data['occupancy']['occupancy_rate']:.2f}%")
    print(f"ADR                 : ₹{data['adr']['adr']:.2f}")
    print(f"RevPAR              : ₹{data['revpar']['revpar']:.2f}")
    print(f"Bookings            : {data['booking']['total_bookings']}")
    print(f"Cancellations       : {data['cancellation']['count']}")
    print(f"No-Shows            : {data['no_show']['count']}")
    print(f"Customer Activity   : {data['customers']['activity_count']}")
    print(f"Inventory Txns      : {data['inventory']['transaction_count']}")
    print(f"Expenses            : ₹{data['expenses']['total_expense']:.2f}")
    print(f"Active Staff        : {data['staff']['active_staff']}")
    print(f"Profitability       : ₹{data['profitability']['profit']:.2f}")
    print("-" * 76)
    print("Department Performance")
    for row in data["departments"]["departments"]:
        print(f"  {row['department']:<25} Staff: {row['staff_count']:<4} Payroll: ₹{row['payroll_cost']:.2f}")


def revenue_report():
    def build(hotel_id, start, end):
        return get_revenue_summary(hotel_id, start, end)
    data = _run_report("REVENUE REPORT", build)
    if data:
        print(f"Room Revenue        : ₹{data['room_revenue']:.2f}")
        print(f"Restaurant Revenue  : ₹{data['restaurant_revenue']:.2f}")
        print(f"TOTAL REVENUE       : ₹{data['total_revenue']:.2f}")
        print("Revenue source: non-cancelled room bookings + non-cancelled restaurant orders.")


def room_revenue_data(hotel_id, start=None, end=None):
    rows = _room_revenue_rows(hotel_id, start, end)
    return {"revenue": sum(_money(r["grand_total"]) for r in rows), "bookings": len(rows)}


def room_revenue_report():
    data = _run_report("ROOM REVENUE REPORT", lambda h, s, e: room_revenue_data(h, s, e))
    if data:
        print(f"Room Bookings       : {data['bookings']}")
        print(f"ROOM REVENUE        : ₹{data['revenue']:.2f}")


def restaurant_revenue_data(hotel_id, start=None, end=None):
    rows = _restaurant_revenue_rows(hotel_id, start, end)
    return {"revenue": sum(_money(r["grand_total"]) for r in rows), "orders": len(rows)}


def restaurant_revenue_report():
    data = _run_report("RESTAURANT REVENUE REPORT", lambda h, s, e: restaurant_revenue_data(h, s, e))
    if data:
        print(f"Restaurant Orders   : {data['orders']}")
        print(f"RESTAURANT REVENUE  : ₹{data['revenue']:.2f}")


def occupancy_data(hotel_id, start=None, end=None):
    if start is None and end is None:
        all_dates = []
        for row in _room_bookings(hotel_id):
            d1 = _parse_flexible_date(row["check_in_date"] or row["booking_date"])
            d2 = _parse_flexible_date(row["expected_check_out"])
            if d1 and d2 and d2 > d1:
                all_dates.extend([d1, d2 - timedelta(days=1)])
        if all_dates:
            start = min(all_dates)
            end = max(all_dates)
        else:
            today = date.today()
            start = end = today
    if start is None:
        start = end or date.today()
    if end is None:
        end = start
    days = max((end - start).days + 1, 1)
    available_room_nights = _active_room_count(hotel_id) * days
    sold_room_nights = 0
    for row in _room_revenue_rows(hotel_id, start, end):
        sold_room_nights += _room_nights_for_booking(row, start, end)
    rate = (sold_room_nights / available_room_nights * 100) if available_room_nights else 0.0
    return {"sold_room_nights": sold_room_nights, "available_room_nights": available_room_nights, "occupancy_rate": rate, "days": days}


def occupancy_report():
    data = _run_report("OCCUPANCY REPORT", lambda h, s, e: occupancy_data(h, s, e))
    if data:
        print(f"Available Room Nights: {data['available_room_nights']}")
        print(f"Sold Room Nights     : {data['sold_room_nights']}")
        print(f"OCCUPANCY            : {data['occupancy_rate']:.2f}%")


def adr_data(hotel_id, start=None, end=None):
    room = room_revenue_data(hotel_id, start, end)
    occ = occupancy_data(hotel_id, start, end)
    adr = room["revenue"] / occ["sold_room_nights"] if occ["sold_room_nights"] else 0.0
    return {"adr": adr, "room_revenue": room["revenue"], "sold_room_nights": occ["sold_room_nights"]}


def adr_report():
    data = _run_report("ADR REPORT", lambda h, s, e: adr_data(h, s, e))
    if data:
        print(f"Room Revenue        : ₹{data['room_revenue']:.2f}")
        print(f"Sold Room Nights    : {data['sold_room_nights']}")
        print(f"ADR                 : ₹{data['adr']:.2f}")
        print("ADR = Room Revenue / Sold Room Nights")


def revpar_data(hotel_id, start=None, end=None):
    room = room_revenue_data(hotel_id, start, end)
    occ = occupancy_data(hotel_id, start, end)
    revpar = room["revenue"] / occ["available_room_nights"] if occ["available_room_nights"] else 0.0
    return {"revpar": revpar, "room_revenue": room["revenue"], "available_room_nights": occ["available_room_nights"]}


def revpar_report():
    data = _run_report("RevPAR REPORT", lambda h, s, e: revpar_data(h, s, e))
    if data:
        print(f"Room Revenue          : ₹{data['room_revenue']:.2f}")
        print(f"Available Room Nights : {data['available_room_nights']}")
        print(f"RevPAR                : ₹{data['revpar']:.2f}")
        print("RevPAR = Room Revenue / Available Room Nights")


def booking_trends_data(hotel_id, start=None, end=None):
    monthly = defaultdict(lambda: {"room": 0, "table": 0, "restaurant_orders": 0})
    room_rows = _room_bookings(hotel_id)
    order_rows = _orders(hotel_id)
    connection = get_connection()
    try:
        table_rows = connection.execute(
            "SELECT booking_date FROM table_bookings WHERE hotel_id = ?",
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()

    for row in room_rows:
        d = _parse_flexible_date(row["booking_date"] or row["check_in_date"])
        if d and _in_range(d, start, end):
            monthly[_month_key(d)]["room"] += 1
    for row in table_rows:
        d = _parse_flexible_date(row["booking_date"])
        if d and _in_range(d, start, end):
            monthly[_month_key(d)]["table"] += 1
    for row in order_rows:
        d = _parse_flexible_date(row["order_date"])
        if d and _in_range(d, start, end):
            monthly[_month_key(d)]["restaurant_orders"] += 1

    total = sum(v["room"] + v["table"] for v in monthly.values())
    return {"total_bookings": total, "monthly": dict(sorted(monthly.items()))}


def booking_trends_report():
    data = _run_report("BOOKING TRENDS", lambda h, s, e: booking_trends_data(h, s, e))
    if data:
        print(f"Room Bookings       : {data['total_bookings']}")
        for month, row in data["monthly"].items():
            print(f"{month} | Room: {row['room']:<5} | Table: {row['table']:<5} | Restaurant Orders: {row['restaurant_orders']}")


def cancellation_data(hotel_id, start=None, end=None):
    rows = []
    for table, date_field in (("room_bookings", "booking_date"), ("orders", "order_date")):
        source = _room_bookings(hotel_id) if table == "room_bookings" else _orders(hotel_id)
        for row in source:
            if (row["booking_status"] if table == "room_bookings" else row["order_status"]) != "Cancelled":
                continue
            d = _parse_flexible_date(row[date_field])
            if _in_range(d, start, end):
                rows.append((table, row))
    return {"count": len(rows), "room": sum(1 for t, _ in rows if t == "room_bookings"), "restaurant": sum(1 for t, _ in rows if t == "orders")}


def cancellation_report():
    data = _run_report("CANCELLATION REPORT", lambda h, s, e: cancellation_data(h, s, e))
    if data:
        print(f"Total Cancellations : {data['count']}")
        print(f"Room Cancellations  : {data['room']}")
        print(f"Restaurant Cancels  : {data['restaurant']}")


def no_show_data(hotel_id, start=None, end=None):
    count = 0
    for row in _room_bookings(hotel_id):
        if (row["booking_status"] or "") != "No-Show":
            continue
        d = _parse_flexible_date(row["booking_date"] or row["check_in_date"])
        if _in_range(d, start, end):
            count += 1
    return {"count": count}


def no_show_report():
    data = _run_report("NO-SHOW REPORT", lambda h, s, e: no_show_data(h, s, e))
    if data:
        print(f"NO-SHOW BOOKINGS    : {data['count']}")


def customer_trends_data(hotel_id, start=None, end=None):
    connection = get_connection()
    try:
        # The current customers table predates multi-hotel isolation and does
        # not contain hotel_id. Scope customers through hotel-owned
        # transactions, which is the authoritative relationship available.
        customer_ids = set()
        for table, date_field in (("room_bookings", "booking_date"), ("orders", "order_date"), ("feedback", "feedback_date")):
            try:
                rows = connection.execute(
                    f"SELECT customer_id, {date_field} FROM {table} WHERE hotel_id = ?",
                    (hotel_id,),
                ).fetchall()
            except Exception:
                rows = []
            for row in rows:
                d = _parse_flexible_date(row[date_field])
                if row["customer_id"] and _in_range(d, start, end):
                    customer_ids.add(row["customer_id"])

        # Table bookings also link to customers.
        try:
            rows = connection.execute(
                "SELECT customer_id, booking_date FROM table_bookings WHERE hotel_id = ?",
                (hotel_id,),
            ).fetchall()
        except Exception:
            rows = []
        for row in rows:
            d = _parse_flexible_date(row["booking_date"])
            if row["customer_id"] and _in_range(d, start, end):
                customer_ids.add(row["customer_id"])

        customers = []
        if customer_ids:
            placeholders = ",".join("?" for _ in customer_ids)
            customers = connection.execute(
                f"SELECT customer_id, created_time FROM customers WHERE customer_id IN ({placeholders})",
                tuple(customer_ids),
            ).fetchall()
    finally:
        connection.close()

    new_customers = sum(
        1 for row in customers if _in_range(_parse_flexible_date(row["created_time"]), start, end)
    )
    return {
        "new_customers": new_customers,
        "active_customers": len(customer_ids),
        "activity_count": len(customer_ids),
    }


def customer_trends_report():
    data = _run_report("CUSTOMER TRENDS", lambda h, s, e: customer_trends_data(h, s, e))
    if data:
        print(f"New Customers       : {data['new_customers']}")
        print(f"Active Customers    : {data['active_customers']}")
        print(f"Customer Activities : {data['activity_count']}")


def inventory_trends_data(hotel_id, start=None, end=None):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT * FROM inventory_transactions WHERE hotel_id = ?", (hotel_id,)).fetchall()
    finally:
        connection.close()
    counts = defaultdict(float)
    values = defaultdict(float)
    for row in rows:
        d = _parse_flexible_date(row["transaction_date"])
        if not _in_range(d, start, end):
            continue
        typ = (row["transaction_type"] or "Other").upper()
        qty = abs(_money(row["quantity"]))
        counts[typ] += qty
        values[typ] += _money(row["total_value"])
    return {"transaction_count": sum(1 for row in rows if _in_range(_parse_flexible_date(row["transaction_date"]), start, end)), "quantities": dict(counts), "values": dict(values)}


def inventory_trends_report():
    data = _run_report("INVENTORY TRENDS", lambda h, s, e: inventory_trends_data(h, s, e))
    if data:
        print(f"Inventory Transactions: {data['transaction_count']}")
        for typ in sorted(data["quantities"]):
            print(f"{typ:<20} Qty: {data['quantities'][typ]:.2f} | Value: ₹{data['values'][typ]:.2f}")


def expense_trends_data(hotel_id, start=None, end=None):
    monthly = defaultdict(float)
    total = 0.0
    for row in _expenses(hotel_id):
        d = _parse_flexible_date(row["expense_date"])
        if not _in_range(d, start, end):
            continue
        amount = _money(row["amount"])
        total += amount
        monthly[_month_key(d)] += amount
    return {"total_expense": total, "monthly": dict(sorted(monthly.items()))}


def expense_trends_report():
    data = _run_report("EXPENSE TRENDS", lambda h, s, e: expense_trends_data(h, s, e))
    if data:
        print(f"TOTAL EXPENSE       : ₹{data['total_expense']:.2f}")
        for month, amount in data["monthly"].items():
            print(f"{month} : ₹{amount:.2f}")


def department_performance_data(hotel_id, start=None, end=None):
    connection = get_connection()
    try:
        staff = connection.execute("SELECT department, status FROM staff WHERE hotel_id = ?", (hotel_id,)).fetchall()
        payroll = connection.execute("SELECT department, net_salary, payroll_period FROM payroll WHERE hotel_id = ?", (hotel_id,)).fetchall()
        expenses = connection.execute("SELECT department_name, amount, expense_date FROM expenses WHERE hotel_id = ?", (hotel_id,)).fetchall()
    finally:
        connection.close()
    result = defaultdict(lambda: {"staff_count": 0, "payroll_cost": 0.0, "expense_cost": 0.0})
    for row in staff:
        dept = row["department"] or "Unassigned"
        if row["status"] in {"Active", "New"}:
            result[dept]["staff_count"] += 1
    for row in payroll:
        # Payroll period is MM-YYYY; if a date filter exists, include periods
        # that overlap the requested months.
        try:
            period = datetime.strptime(str(row["payroll_period"]), "%m-%Y").date()
        except (TypeError, ValueError):
            period = None
        if start and period and period < start.replace(day=1):
            continue
        if end and period and period > end.replace(day=1):
            continue
        result[row["department"] or "Unassigned"]["payroll_cost"] += _money(row["net_salary"])
    for row in expenses:
        d = _parse_flexible_date(row["expense_date"])
        if _in_range(d, start, end):
            result[row["department_name"] or "Unassigned"]["expense_cost"] += _money(row["amount"])
    return {"departments": [dict(department=k, **v) for k, v in sorted(result.items())]}


def department_performance_report():
    data = _run_report("DEPARTMENT PERFORMANCE", lambda h, s, e: department_performance_data(h, s, e))
    if data:
        if not data["departments"]:
            print("No Department Data Found.")
        for row in data["departments"]:
            print(f"{row['department']:<25} Staff: {row['staff_count']:<4} Payroll: ₹{row['payroll_cost']:.2f} | Expenses: ₹{row['expense_cost']:.2f}")


def staff_report_data(hotel_id, start=None, end=None):
    connection = get_connection()
    try:
        staff = connection.execute("SELECT staff_id, staff_name, department, status FROM staff WHERE hotel_id = ?", (hotel_id,)).fetchall()
        payroll = connection.execute("SELECT staff_id, net_salary, payroll_period FROM payroll WHERE hotel_id = ?", (hotel_id,)).fetchall()
        attendance = connection.execute("SELECT staff_id, status, date FROM attendance WHERE hotel_id = ?", (hotel_id,)).fetchall()
    finally:
        connection.close()
    payroll_total = 0.0
    for row in payroll:
        try:
            period = datetime.strptime(str(row["payroll_period"]), "%m-%Y").date()
        except (TypeError, ValueError):
            period = None
        if start and period and period < start.replace(day=1):
            continue
        if end and period and period > end.replace(day=1):
            continue
        payroll_total += _money(row["net_salary"])
    attendance_count = sum(1 for row in attendance if _in_range(_parse_flexible_date(row["date"]), start, end))
    return {"active_staff": sum(1 for row in staff if row["status"] in {"Active", "New"}), "total_staff": len(staff), "payroll_total": payroll_total, "attendance_records": attendance_count}


def staff_reports_report():
    data = _run_report("STAFF REPORTS", lambda h, s, e: staff_report_data(h, s, e))
    if data:
        print(f"Total Staff         : {data['total_staff']}")
        print(f"Active Staff        : {data['active_staff']}")
        print(f"Payroll Cost        : ₹{data['payroll_total']:.2f}")
        print(f"Attendance Records  : {data['attendance_records']}")


def profitability_data(hotel_id, start=None, end=None):
    revenue = get_revenue_summary(hotel_id, start, end)
    expenses = expense_trends_data(hotel_id, start, end)
    profit = revenue["total_revenue"] - expenses["total_expense"]
    margin = (profit / revenue["total_revenue"] * 100) if revenue["total_revenue"] else 0.0
    return {"revenue": revenue["total_revenue"], "expense": expenses["total_expense"], "profit": profit, "margin": margin}


def profitability_report():
    data = _run_report("PROFITABILITY FOUNDATION", lambda h, s, e: profitability_data(h, s, e))
    if data:
        print(f"Total Revenue       : ₹{data['revenue']:.2f}")
        print(f"Total Expenses      : ₹{data['expense']:.2f}")
        print(f"Operating Profit*   : ₹{data['profit']:.2f}")
        print(f"Profit Margin*      : {data['margin']:.2f}%")
        print("* Foundation metric: revenue minus recorded expenses; not a final accounting P&L.")
