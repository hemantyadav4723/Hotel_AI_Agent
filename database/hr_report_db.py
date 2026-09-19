from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


DATE_FORMAT = "%d-%m-%Y"
PERIOD_FORMAT = "%m-%Y"
ACTIVE_STAFF_STATUSES = ("New", "Active", "On Leave")
SEPARATED_STAFF_STATUSES = ("Inactive", "Resigned", "Terminated")
ATTENDANCE_STATUSES = ("Present", "Absent", "Late", "Half Day", "Leave")


def _parse_period(value):
    value = str(value or "").strip()
    try:
        return datetime.strptime(value, PERIOD_FORMAT)
    except ValueError as exc:
        raise ValueError("Period must be in MM-YYYY format.") from exc


def _print_title(title):
    print("=" * 80)
    print(title.center(80))
    print("=" * 80)


def _print_rows(rows, empty_message="No Records Found."):
    if not rows:
        print(empty_message)
        return
    for row in rows:
        print("-" * 80)
        for key in row.keys():
            print(f"{key.replace('_', ' ').title():<28}: {row[key]}")
    print("-" * 80)


def staff_report():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT staff_id, staff_name, department, designation,
                   mobile, email, joining_date, status
            FROM staff
            WHERE hotel_id = ?
            ORDER BY staff_name COLLATE NOCASE, staff_id
            """,
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()

    _print_title("STAFF REPORT")
    _print_rows(rows, "No Staff Found.")
    if rows:
        print(f"Total Staff: {len(rows)}")


def department_wise_staff_report():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                COALESCE(NULLIF(TRIM(department), ''), 'Unassigned') AS department,
                COUNT(*) AS total_staff,
                SUM(CASE WHEN status IN ('New', 'Active', 'On Leave') THEN 1 ELSE 0 END) AS active_staff,
                SUM(CASE WHEN status IN ('Inactive', 'Resigned', 'Terminated') THEN 1 ELSE 0 END) AS inactive_staff
            FROM staff
            WHERE hotel_id = ?
            GROUP BY COALESCE(NULLIF(TRIM(department), ''), 'Unassigned')
            ORDER BY department COLLATE NOCASE
            """,
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()

    _print_title("DEPARTMENT-WISE STAFF REPORT")
    _print_rows(rows, "No Department Staff Data Found.")


def attendance_report():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                a.staff_id,
                s.staff_name,
                COUNT(*) AS total_records,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_days,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_days,
                SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_days,
                SUM(CASE WHEN a.status = 'Half Day' THEN 1 ELSE 0 END) AS half_days,
                SUM(CASE WHEN a.status = 'Leave' THEN 1 ELSE 0 END) AS leave_days
            FROM attendance a
            INNER JOIN staff s
                ON s.staff_id = a.staff_id
               AND s.hotel_id = a.hotel_id
            WHERE a.hotel_id = ?
            GROUP BY a.staff_id, s.staff_name
            ORDER BY s.staff_name COLLATE NOCASE, a.staff_id
            """,
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()

    _print_title("ATTENDANCE REPORT")
    _print_rows(rows, "No Attendance Records Found.")


def monthly_attendance_report():
    period = input("Enter Month (MM-YYYY) : ").strip()
    try:
        _parse_period(period)
    except ValueError as exc:
        print(exc)
        return

    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                a.staff_id,
                s.staff_name,
                COUNT(*) AS total_records,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_days,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_days,
                SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_days,
                SUM(CASE WHEN a.status = 'Half Day' THEN 1 ELSE 0 END) AS half_days,
                SUM(CASE WHEN a.status = 'Leave' THEN 1 ELSE 0 END) AS leave_days
            FROM attendance a
            INNER JOIN staff s
                ON s.staff_id = a.staff_id
               AND s.hotel_id = a.hotel_id
            WHERE a.hotel_id = ?
              AND substr(a.date, 4, 7) = ?
            GROUP BY a.staff_id, s.staff_name
            ORDER BY s.staff_name COLLATE NOCASE, a.staff_id
            """,
            (hotel_id, period),
        ).fetchall()
    finally:
        connection.close()

    _print_title(f"MONTHLY ATTENDANCE REPORT - {period}")
    _print_rows(rows, "No Attendance Records Found For This Month.")


def leave_report():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                l.leave_id,
                l.staff_id,
                s.staff_name,
                l.leave_type,
                l.start_date,
                l.end_date,
                l.status,
                l.approved_by,
                l.approved_at,
                l.decision_reason
            FROM staff_leaves l
            INNER JOIN staff s
                ON s.staff_id = l.staff_id
               AND s.hotel_id = l.hotel_id
            WHERE l.hotel_id = ?
            ORDER BY l.leave_id DESC
            """,
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()

    _print_title("LEAVE REPORT")
    _print_rows(rows, "No Leave Records Found.")


def salary_report():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                salary_id, staff_id, staff_name, department, designation,
                basic_salary, allowances, bonus, deduction, net_salary,
                effective_date
            FROM salary
            WHERE hotel_id = ?
            ORDER BY
                staff_name COLLATE NOCASE,
                date(substr(effective_date, 7, 4) || '-' ||
                     substr(effective_date, 4, 2) || '-' ||
                     substr(effective_date, 1, 2)) DESC,
                salary_id DESC
            """,
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()

    _print_title("SALARY REPORT")
    _print_rows(rows, "No Salary Records Found.")


def payroll_report():
    period = input("Enter Payroll Period (MM-YYYY) : ").strip()
    try:
        _parse_period(period)
    except ValueError as exc:
        print(exc)
        return

    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                payroll_id, staff_id, staff_name, department, designation,
                gross_salary, deduction, attendance_deduction, net_salary,
                payroll_status, payroll_period
            FROM payroll
            WHERE hotel_id = ? AND payroll_period = ?
            ORDER BY staff_name COLLATE NOCASE, staff_id
            """,
            (hotel_id, period),
        ).fetchall()
    finally:
        connection.close()

    _print_title(f"PAYROLL REPORT - {period}")
    if not rows:
        print("No Payroll Found For This Period.")
        return

    total_gross = sum(float(row["gross_salary"] or 0) for row in rows)
    total_deduction = sum(
        float(row["deduction"] or 0) + float(row["attendance_deduction"] or 0)
        for row in rows
    )
    total_net = sum(float(row["net_salary"] or 0) for row in rows)

    _print_rows(rows)
    print(f"Employees        : {len(rows)}")
    print(f"Total Gross      : ₹{total_gross:.2f}")
    print(f"Total Deductions : ₹{total_deduction:.2f}")
    print(f"Total Net Payroll: ₹{total_net:.2f}")


def department_payroll_report():
    period = input("Enter Payroll Period (MM-YYYY) : ").strip()
    try:
        _parse_period(period)
    except ValueError as exc:
        print(exc)
        return

    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                COALESCE(NULLIF(TRIM(department), ''), 'Unassigned') AS department,
                COUNT(*) AS employees,
                ROUND(SUM(gross_salary), 2) AS total_gross,
                ROUND(SUM(deduction + attendance_deduction), 2) AS total_deductions,
                ROUND(SUM(net_salary), 2) AS total_net
            FROM payroll
            WHERE hotel_id = ? AND payroll_period = ?
            GROUP BY COALESCE(NULLIF(TRIM(department), ''), 'Unassigned')
            ORDER BY department COLLATE NOCASE
            """,
            (hotel_id, period),
        ).fetchall()
    finally:
        connection.close()

    _print_title(f"DEPARTMENT PAYROLL REPORT - {period}")
    _print_rows(rows, "No Department Payroll Data Found For This Period.")


def staff_cost_summary():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                COALESCE(NULLIF(TRIM(s.department), ''), 'Unassigned') AS department,
                COUNT(*) AS active_staff,
                ROUND(SUM(COALESCE(s.salary, 0)), 2) AS monthly_staff_cost
            FROM staff s
            WHERE s.hotel_id = ?
              AND s.status IN ('New', 'Active', 'On Leave')
            GROUP BY COALESCE(NULLIF(TRIM(s.department), ''), 'Unassigned')
            ORDER BY department COLLATE NOCASE
            """,
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()

    _print_title("STAFF COST SUMMARY")
    _print_rows(rows, "No Active Staff Cost Data Found.")
    if rows:
        total = sum(float(row["monthly_staff_cost"] or 0) for row in rows)
        count = sum(int(row["active_staff"] or 0) for row in rows)
        print(f"Active Staff    : {count}")
        print(f"Monthly Cost    : ₹{total:.2f}")


def active_inactive_staff_report():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                status,
                COUNT(*) AS staff_count
            FROM staff
            WHERE hotel_id = ?
            GROUP BY status
            ORDER BY
                CASE status
                    WHEN 'New' THEN 1
                    WHEN 'Active' THEN 2
                    WHEN 'On Leave' THEN 3
                    WHEN 'Inactive' THEN 4
                    WHEN 'Resigned' THEN 5
                    WHEN 'Terminated' THEN 6
                    ELSE 7
                END
            """,
            (hotel_id,),
        ).fetchall()
    finally:
        connection.close()

    _print_title("ACTIVE / INACTIVE STAFF REPORT")
    _print_rows(rows, "No Staff Status Data Found.")


def hr_dashboard():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        staff_total = connection.execute(
            "SELECT COUNT(*) FROM staff WHERE hotel_id = ?", (hotel_id,)
        ).fetchone()[0]
        active_staff = connection.execute(
            "SELECT COUNT(*) FROM staff WHERE hotel_id = ? AND status IN ('New','Active','On Leave')",
            (hotel_id,),
        ).fetchone()[0]
        inactive_staff = connection.execute(
            "SELECT COUNT(*) FROM staff WHERE hotel_id = ? AND status IN ('Inactive','Resigned','Terminated')",
            (hotel_id,),
        ).fetchone()[0]
        departments = connection.execute(
            "SELECT COUNT(*) FROM department WHERE hotel_id = ? AND status = 'Active'",
            (hotel_id,),
        ).fetchone()[0]
        pending_leave = connection.execute(
            "SELECT COUNT(*) FROM staff_leaves WHERE hotel_id = ? AND status = 'Pending'",
            (hotel_id,),
        ).fetchone()[0]
        approved_leave = connection.execute(
            "SELECT COUNT(*) FROM staff_leaves WHERE hotel_id = ? AND status = 'Approved'",
            (hotel_id,),
        ).fetchone()[0]
        payroll_periods = connection.execute(
            "SELECT COUNT(DISTINCT payroll_period) FROM payroll WHERE hotel_id = ?",
            (hotel_id,),
        ).fetchone()[0]
        salary_cost = connection.execute(
            """
            SELECT COALESCE(SUM(salary), 0)
            FROM staff
            WHERE hotel_id = ? AND status IN ('New','Active','On Leave')
            """,
            (hotel_id,),
        ).fetchone()[0]
    finally:
        connection.close()

    _print_title("HR DASHBOARD")
    print(f"Total Staff             : {staff_total}")
    print(f"Active Staff             : {active_staff}")
    print(f"Inactive/Separated Staff : {inactive_staff}")
    print(f"Active Departments       : {departments}")
    print(f"Pending Leave Requests   : {pending_leave}")
    print(f"Approved Leave Records   : {approved_leave}")
    print(f"Payroll Periods          : {payroll_periods}")
    print(f"Current Monthly Staff Cost: ₹{float(salary_cost or 0):.2f}")
    print("=" * 80)


def hr_analytics_menu():
    actions = {
        "1": ("Staff Report", staff_report),
        "2": ("Department-wise Staff", department_wise_staff_report),
        "3": ("Attendance Report", attendance_report),
        "4": ("Monthly Attendance", monthly_attendance_report),
        "5": ("Leave Report", leave_report),
        "6": ("Salary Report", salary_report),
        "7": ("Payroll Report", payroll_report),
        "8": ("Department Payroll", department_payroll_report),
        "9": ("Staff Cost Summary", staff_cost_summary),
        "10": ("Active / Inactive Staff", active_inactive_staff_report),
        "11": ("HR Dashboard", hr_dashboard),
    }

    while True:
        _print_title("HR & STAFF ANALYTICS")
        for key, (label, _) in actions.items():
            print(f"{key}. {label}")
        print("12. Back")
        print("-" * 80)

        choice = input("Enter Choice : ").strip()
        if choice == "12":
            return

        action = actions.get(choice)
        if not action:
            print("Invalid Choice.")
            continue

        try:
            action[1]()
        except Exception as exc:
            print(f"Error generating HR report: {exc}")

        input("\nPress Enter to continue...")
