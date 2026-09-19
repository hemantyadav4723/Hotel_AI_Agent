from utils.error_logging import log_non_blocking_error
from calendar import monthrange
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.salary_db import get_current_salary_for_date


PAYROLL_PERIOD_FORMAT = "%m-%Y"
ATTENDANCE_STATUS_PAID = {"Present", "Late", "Leave"}
ACTIVE_STAFF_STATUSES = {"New", "Active"}


def create_payroll_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payroll(
                payroll_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                staff_id TEXT NOT NULL,
                staff_name TEXT NOT NULL,
                department TEXT,
                designation TEXT,
                salary_id INTEGER,
                basic_salary REAL NOT NULL DEFAULT 0,
                allowances REAL NOT NULL DEFAULT 0,
                bonus REAL NOT NULL DEFAULT 0,
                deduction REAL NOT NULL DEFAULT 0,
                gross_salary REAL NOT NULL DEFAULT 0,
                attendance_present_days REAL NOT NULL DEFAULT 0,
                late_days REAL NOT NULL DEFAULT 0,
                half_days REAL NOT NULL DEFAULT 0,
                absent_days REAL NOT NULL DEFAULT 0,
                leave_days REAL NOT NULL DEFAULT 0,
                payable_days REAL NOT NULL DEFAULT 0,
                attendance_deduction REAL NOT NULL DEFAULT 0,
                net_salary REAL NOT NULL DEFAULT 0,
                payroll_status TEXT NOT NULL DEFAULT 'Generated',
                payroll_period TEXT NOT NULL,
                correction_reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(payroll)").fetchall()
        }

        additions = {
            "hotel_id": "INTEGER NOT NULL DEFAULT 1",
            "designation": "TEXT",
            "salary_id": "INTEGER",
            "allowances": "REAL NOT NULL DEFAULT 0",
            "gross_salary": "REAL NOT NULL DEFAULT 0",
            "attendance_present_days": "REAL NOT NULL DEFAULT 0",
            "late_days": "REAL NOT NULL DEFAULT 0",
            "half_days": "REAL NOT NULL DEFAULT 0",
            "absent_days": "REAL NOT NULL DEFAULT 0",
            "leave_days": "REAL NOT NULL DEFAULT 0",
            "payable_days": "REAL NOT NULL DEFAULT 0",
            "attendance_deduction": "REAL NOT NULL DEFAULT 0",
            "payroll_period": "TEXT",
            "correction_reason": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }

        for column, definition in additions.items():
            if column not in columns:
                cursor.execute(
                    f"ALTER TABLE payroll ADD COLUMN {column} {definition}"
                )

        cursor.execute("UPDATE payroll SET hotel_id = 1 WHERE hotel_id IS NULL")
        cursor.execute("UPDATE payroll SET allowances = 0 WHERE allowances IS NULL")
        cursor.execute(
            "UPDATE payroll SET gross_salary = COALESCE(basic_salary, 0) + "
            "COALESCE(allowances, 0) + COALESCE(bonus, 0) "
            "WHERE gross_salary IS NULL OR gross_salary = 0"
        )
        cursor.execute(
            "UPDATE payroll SET attendance_present_days = 0 "
            "WHERE attendance_present_days IS NULL"
        )
        cursor.execute(
            "UPDATE payroll SET late_days = 0 WHERE late_days IS NULL"
        )
        cursor.execute(
            "UPDATE payroll SET half_days = 0 WHERE half_days IS NULL"
        )
        cursor.execute(
            "UPDATE payroll SET absent_days = 0 WHERE absent_days IS NULL"
        )
        cursor.execute(
            "UPDATE payroll SET leave_days = 0 WHERE leave_days IS NULL"
        )
        cursor.execute(
            "UPDATE payroll SET payable_days = 0 WHERE payable_days IS NULL"
        )
        cursor.execute(
            "UPDATE payroll SET attendance_deduction = 0 "
            "WHERE attendance_deduction IS NULL"
        )
        cursor.execute(
            "UPDATE payroll SET payroll_period = "
            "strftime('%m-%Y', 'now') "
            "WHERE payroll_period IS NULL OR TRIM(payroll_period) = ''"
        )
        cursor.execute(
            "UPDATE payroll SET created_at = CURRENT_TIMESTAMP "
            "WHERE created_at IS NULL OR TRIM(created_at) = ''"
        )
        cursor.execute(
            "UPDATE payroll SET updated_at = created_at "
            "WHERE updated_at IS NULL OR TRIM(updated_at) = ''"
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_payroll_hotel_staff "
            "ON payroll(hotel_id, staff_id, payroll_id DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_payroll_hotel_period "
            "ON payroll(hotel_id, payroll_period)"
        )

        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_payroll_hotel_staff_period
                ON payroll(hotel_id, staff_id, payroll_period)
            """)
        except Exception:
            # Preserve existing legacy data if duplicate historical periods
            # prevent creation of the unique index. Application validation
            # still prevents new duplicates.
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payroll_correction_history(
                correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                payroll_id INTEGER NOT NULL,
                staff_id TEXT NOT NULL,
                old_bonus REAL NOT NULL,
                new_bonus REAL NOT NULL,
                old_deduction REAL NOT NULL,
                new_deduction REAL NOT NULL,
                old_attendance_deduction REAL NOT NULL,
                new_attendance_deduction REAL NOT NULL,
                old_net_salary REAL NOT NULL,
                new_net_salary REAL NOT NULL,
                reason TEXT NOT NULL,
                corrected_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payroll_correction_staff
            ON payroll_correction_history(hotel_id, staff_id, correction_id DESC)
        """)

        connection.commit()
    finally:
        connection.close()


def _parse_period(value):
    value = str(value).strip()
    try:
        return datetime.strptime(value, PAYROLL_PERIOD_FORMAT)
    except ValueError as exc:
        raise ValueError("Payroll period must be in MM-YYYY format.") from exc


def _period_bounds(period):
    period_date = _parse_period(period)
    year = period_date.year
    month = period_date.month
    last_day = monthrange(year, month)[1]
    return (
        f"{year:04d}-{month:02d}-01",
        f"{year:04d}-{month:02d}-{last_day:02d}",
        last_day,
    )


def _date_key(value):
    return datetime.strptime(value, "%d-%m-%Y").date()


def _approved_leave_dates(cursor, hotel_id, staff_id, year, month):
    first_date = f"{year:04d}-{month:02d}-01"
    last_day = monthrange(year, month)[1]
    last_date = f"{year:04d}-{month:02d}-{last_day:02d}"

    cursor.execute("""
        SELECT start_date, end_date
        FROM staff_leaves
        WHERE hotel_id = ?
          AND staff_id = ?
          AND status = 'Approved'
          AND date(substr(end_date, 7, 4) || '-' ||
                   substr(end_date, 4, 2) || '-' ||
                   substr(end_date, 1, 2)) >= date(?)
          AND date(substr(start_date, 7, 4) || '-' ||
                   substr(start_date, 4, 2) || '-' ||
                   substr(start_date, 1, 2)) <= date(?)
    """, (hotel_id, staff_id, first_date, last_date))

    dates = set()
    for row in cursor.fetchall():
        start = max(_date_key(row["start_date"]), datetime(year, month, 1).date())
        end = min(
            _date_key(row["end_date"]),
            datetime(year, month, last_day).date(),
        )
        current = start
        while current <= end:
            dates.add(current)
            current = current.fromordinal(current.toordinal() + 1)
    return dates


def _attendance_summary(cursor, hotel_id, staff_id, year, month, approved_leave_dates):
    first_date = f"{year:04d}-{month:02d}-01"
    last_day = monthrange(year, month)[1]
    last_date = f"{year:04d}-{month:02d}-{last_day:02d}"

    cursor.execute("""
        SELECT date, status
        FROM attendance
        WHERE hotel_id = ?
          AND staff_id = ?
          AND date(substr(date, 7, 4) || '-' ||
                   substr(date, 4, 2) || '-' ||
                   substr(date, 1, 2)) BETWEEN date(?) AND date(?)
    """, (hotel_id, staff_id, first_date, last_date))

    summary = {
        "Present": 0.0,
        "Late": 0.0,
        "Half Day": 0.0,
        "Absent": 0.0,
        "Leave": 0.0,
    }
    recorded_dates = set()

    for row in cursor.fetchall():
        attendance_date = _date_key(row["date"])
        if attendance_date in approved_leave_dates:
            # Approved leave has priority over an accidental attendance status.
            continue
        status = row["status"]
        if status in summary:
            summary[status] += 1
            recorded_dates.add(attendance_date)

    # Approved leave is treated as paid leave even when attendance has no
    # separate record for that date.
    summary["Leave"] = float(len(approved_leave_dates))
    return summary


def _calculate_payroll(salary, summary, days_in_month):
    basic_salary = float(salary["basic_salary"] or 0)
    allowances = float(salary["allowances"] or 0)
    bonus = float(salary["bonus"] or 0)
    deduction = float(salary["deduction"] or 0)

    half_day_unpaid = summary["Half Day"] * 0.5
    unpaid_days = summary["Absent"] + half_day_unpaid
    attendance_deduction = round(
        (basic_salary / days_in_month) * unpaid_days, 2
    )

    payable_days = (
        summary["Present"]
        + summary["Late"]
        + summary["Leave"]
        + half_day_unpaid
    )
    gross_salary = round(basic_salary + allowances + bonus, 2)
    net_salary = round(
        gross_salary - deduction - attendance_deduction,
        2,
    )

    if net_salary < 0:
        raise ValueError("Calculated net salary cannot be negative.")

    return {
        "basic_salary": round(basic_salary, 2),
        "allowances": round(allowances, 2),
        "bonus": round(bonus, 2),
        "deduction": round(deduction, 2),
        "gross_salary": gross_salary,
        "attendance_present_days": summary["Present"],
        "late_days": summary["Late"],
        "half_days": summary["Half Day"],
        "absent_days": summary["Absent"],
        "leave_days": summary["Leave"],
        "payable_days": round(payable_days, 2),
        "attendance_deduction": attendance_deduction,
        "net_salary": net_salary,
    }


def _get_payroll_calculation(cursor, hotel_id, staff_id, period):
    period_date = _parse_period(period)
    year = period_date.year
    month = period_date.month
    days_in_month = monthrange(year, month)[1]

    cursor.execute("""
        SELECT staff_id, staff_name, department, designation, status
        FROM staff
        WHERE staff_id = ? AND hotel_id = ?
    """, (staff_id, hotel_id))
    staff = cursor.fetchone()
    if staff is None:
        raise ValueError("Staff Not Found for the current hotel.")

    if staff["status"] not in ACTIVE_STAFF_STATUSES:
        raise ValueError(
            f"Staff status is '{staff['status']}'. Payroll cannot be generated."
        )

    period_end = f"{year:04d}-{month:02d}-{days_in_month:02d}"
    salary = get_current_salary_for_date(staff_id, period_end, hotel_id)
    if salary is None:
        raise ValueError("Salary record is not available for this payroll period.")

    approved_leave_dates = _approved_leave_dates(
        cursor, hotel_id, staff_id, year, month
    )
    summary = _attendance_summary(
        cursor, hotel_id, staff_id, year, month, approved_leave_dates
    )
    values = _calculate_payroll(salary, summary, days_in_month)

    return staff, salary, values


def generate_payroll(reason=None):
    from database.permission_db import require_hr_authorization
    require_hr_authorization("payroll_generation")

    hotel_id = get_current_hotel_id()
    if reason is not None and not str(reason).strip():
        raise ValueError("Reason is required for payroll generation.")
    staff_id = input("Enter Staff ID : ").strip().upper()
    payroll_period = input("Enter Payroll Period (MM-YYYY) : ").strip()

    _parse_period(payroll_period)

    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT payroll_id
            FROM payroll
            WHERE hotel_id = ? AND staff_id = ? AND payroll_period = ?
            LIMIT 1
        """, (hotel_id, staff_id, payroll_period))
        if cursor.fetchone():
            print("Payroll already generated for this staff and period.")
            return

        staff, salary, values = _get_payroll_calculation(
            cursor, hotel_id, staff_id, payroll_period
        )

        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

        cursor.execute("""
            INSERT INTO payroll(
                hotel_id, staff_id, staff_name, department, designation, salary_id,
                basic_salary, allowances, bonus, deduction, gross_salary,
                attendance_present_days, late_days, half_days, absent_days,
                leave_days, payable_days, attendance_deduction, net_salary,
                payroll_status, payroll_period, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Generated', ?, ?, ?)
        """, (
            hotel_id,
            staff["staff_id"],
            staff["staff_name"],
            staff["department"],
            staff["designation"],
            salary["salary_id"],
            values["basic_salary"],
            values["allowances"],
            values["bonus"],
            values["deduction"],
            values["gross_salary"],
            values["attendance_present_days"],
            values["late_days"],
            values["half_days"],
            values["absent_days"],
            values["leave_days"],
            values["payable_days"],
            values["attendance_deduction"],
            values["net_salary"],
            payroll_period,
            now,
            now,
        ))

        payroll_id = cursor.lastrowid
        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="PAYROLL_GENERATED",
            target_type="PAYROLL",
            target_id=payroll_id,
            old_value=None,
            new_value={
                "staff_id": staff_id,
                "payroll_period": payroll_period,
                "net_salary": values["net_salary"],
                "status": "Generated",
            },
            reason=reason or "Payroll generated.",
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Payroll",
        action="CREATE",
        local_values=locals(),
        details="Business operation generate_payroll completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("\nPayroll Generated Successfully.")
        _print_payroll_record(cursor.execute(
            "SELECT * FROM payroll WHERE payroll_id = ?",
            (cursor.lastrowid,)
        ).fetchone())
    except Exception as exc:
        connection.rollback()
        print(f"Error generating payroll: {exc}")
    finally:
        connection.close()


def _print_payroll_record(record):
    print("=" * 70)
    print(f"Payroll ID            : {record['payroll_id']}")
    print(f"Staff ID              : {record['staff_id']}")
    print(f"Name                  : {record['staff_name']}")
    print(f"Department            : {record['department'] or '-'}")
    print(f"Designation           : {record['designation'] or '-'}")
    print(f"Payroll Period        : {record['payroll_period'] or '-'}")
    print(f"Basic Salary          : {record['basic_salary']:.2f}")
    print(f"Allowances            : {record['allowances']:.2f}")
    print(f"Bonus                 : {record['bonus']:.2f}")
    print(f"Gross Salary          : {record['gross_salary']:.2f}")
    print(f"Present Days          : {record['attendance_present_days']:.1f}")
    print(f"Late Days             : {record['late_days']:.1f}")
    print(f"Half Days             : {record['half_days']:.1f}")
    print(f"Absent Days           : {record['absent_days']:.1f}")
    print(f"Leave Days            : {record['leave_days']:.1f}")
    print(f"Payable Days          : {record['payable_days']:.1f}")
    print(f"Attendance Deduction  : {record['attendance_deduction']:.2f}")
    print(f"Other Deduction       : {record['deduction']:.2f}")
    print(f"Net Salary            : {record['net_salary']:.2f}")
    print(f"Status                : {record['payroll_status']}")
    print(f"Correction Reason     : {record['correction_reason'] or '-'}")
    print(f"Created At            : {record['created_at']}")
    print(f"Updated At             : {record['updated_at']}")
    print("=" * 70)


def view_payroll():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM payroll
            WHERE hotel_id = ?
            ORDER BY
                substr(payroll_period, 4, 4) DESC,
                substr(payroll_period, 1, 2) DESC,
                payroll_id DESC
        """, (hotel_id,))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Payroll Found.")
        return

    for record in records:
        _print_payroll_record(record)


def search_payroll():
    hotel_id = get_current_hotel_id()
    staff_id = input("Enter Staff ID : ").strip().upper()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM payroll
            WHERE hotel_id = ? AND staff_id = ?
            ORDER BY payroll_id DESC
        """, (hotel_id, staff_id))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("Payroll Not Found.")
        return

    for record in records:
        _print_payroll_record(record)


def correct_payroll():
    from database.permission_db import require_hr_authorization
    require_hr_authorization("payroll_correction")

    hotel_id = get_current_hotel_id()
    payroll_id = input("Enter Payroll ID : ").strip()
    if not payroll_id.isdigit():
        print("Invalid Payroll ID.")
        return

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM payroll
            WHERE payroll_id = ? AND hotel_id = ?
        """, (int(payroll_id), hotel_id))
        record = cursor.fetchone()
        if record is None:
            print("Payroll Record Not Found.")
            return

        print(f"Current Bonus    : {record['bonus']:.2f}")
        print(f"Current Deduction : {record['deduction']:.2f}")

        try:
            new_bonus = float(input("New Bonus : ").strip())
            new_deduction = float(input("New Deduction : ").strip())
        except ValueError:
            print("Bonus and Deduction must be valid numbers.")
            return

        if new_bonus < 0 or new_deduction < 0:
            print("Bonus and Deduction cannot be negative.")
            return

        reason = input("Correction Reason : ").strip()
        if not reason:
            print("Correction Reason is required.")
            return

        old_bonus = float(record["bonus"] or 0)
        old_deduction = float(record["deduction"] or 0)
        old_attendance_deduction = float(record["attendance_deduction"] or 0)
        old_net = float(record["net_salary"] or 0)

        gross_salary = round(
            float(record["basic_salary"] or 0)
            + float(record["allowances"] or 0)
            + new_bonus,
            2,
        )
        new_net = round(
            gross_salary
            - new_deduction
            - old_attendance_deduction,
            2,
        )
        if new_net < 0:
            print("Corrected net salary cannot be negative.")
            return

        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

        cursor.execute("""
            UPDATE payroll
            SET bonus = ?,
                deduction = ?,
                gross_salary = ?,
                net_salary = ?,
                payroll_status = 'Corrected',
                correction_reason = ?,
                updated_at = ?
            WHERE payroll_id = ? AND hotel_id = ?
        """, (
            new_bonus,
            new_deduction,
            gross_salary,
            new_net,
            reason,
            now,
            int(payroll_id),
            hotel_id,
        ))

        cursor.execute("""
            INSERT INTO payroll_correction_history(
                hotel_id, payroll_id, staff_id,
                old_bonus, new_bonus,
                old_deduction, new_deduction,
                old_attendance_deduction, new_attendance_deduction,
                old_net_salary, new_net_salary,
                reason, corrected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hotel_id,
            int(payroll_id),
            record["staff_id"],
            old_bonus,
            new_bonus,
            old_deduction,
            new_deduction,
            old_attendance_deduction,
            old_attendance_deduction,
            old_net,
            new_net,
            reason,
            now,
        ))

        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="PAYROLL_CORRECTED",
            target_type="PAYROLL",
            target_id=payroll_id,
            old_value={
                "bonus": old_bonus,
                "deduction": old_deduction,
                "net_salary": old_net,
            },
            new_value={
                "bonus": new_bonus,
                "deduction": new_deduction,
                "net_salary": new_net,
            },
            reason=reason,
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Payroll",
        action="UPDATE",
        local_values=locals(),
        details="Business operation correct_payroll completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("\nPayroll Corrected Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error correcting payroll: {exc}")
    finally:
        connection.close()


def view_payroll_correction_history():
    hotel_id = get_current_hotel_id()
    staff_id = input("Enter Staff ID : ").strip().upper()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM payroll_correction_history
            WHERE hotel_id = ? AND staff_id = ?
            ORDER BY correction_id DESC
        """, (hotel_id, staff_id))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("Payroll Correction History Not Found.")
        return

    print("=" * 70)
    print("              PAYROLL CORRECTION HISTORY")
    print("=" * 70)
    for record in records:
        print(f"Correction ID        : {record['correction_id']}")
        print(f"Payroll ID           : {record['payroll_id']}")
        print(f"Staff ID             : {record['staff_id']}")
        print(f"Bonus                : {record['old_bonus']:.2f} -> {record['new_bonus']:.2f}")
        print(f"Deduction            : {record['old_deduction']:.2f} -> {record['new_deduction']:.2f}")
        print(
            "Attendance Deduction : "
            f"{record['old_attendance_deduction']:.2f} -> "
            f"{record['new_attendance_deduction']:.2f}"
        )
        print(f"Net Salary           : {record['old_net_salary']:.2f} -> {record['new_net_salary']:.2f}")
        print(f"Reason               : {record['reason']}")
        print(f"Corrected At         : {record['corrected_at']}")
        print("-" * 70)


def monthly_payroll_report():
    hotel_id = get_current_hotel_id()
    payroll_period = input("Enter Payroll Period (MM-YYYY) : ").strip()
    _parse_period(payroll_period)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM payroll
            WHERE hotel_id = ? AND payroll_period = ?
            ORDER BY staff_name COLLATE NOCASE, staff_id
        """, (hotel_id, payroll_period))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Payroll Found For This Period.")
        return

    total_gross = sum(float(row["gross_salary"] or 0) for row in records)
    total_deduction = sum(
        float(row["deduction"] or 0) + float(row["attendance_deduction"] or 0)
        for row in records
    )
    total_net = sum(float(row["net_salary"] or 0) for row in records)

    print("=" * 80)
    print(f"                 PAYROLL REPORT - {payroll_period}")
    print("=" * 80)
    for record in records:
        print(
            f"{record['staff_id']} | "
            f"{record['staff_name']} | "
            f"Gross: {record['gross_salary']:.2f} | "
            f"Deduction: {(record['deduction'] + record['attendance_deduction']):.2f} | "
            f"Net: {record['net_salary']:.2f} | "
            f"{record['payroll_status']}"
        )
    print("-" * 80)
    print(f"Employees        : {len(records)}")
    print(f"Total Gross      : {total_gross:.2f}")
    print(f"Total Deductions : {total_deduction:.2f}")
    print(f"Total Net Payroll: {total_net:.2f}")
    print("=" * 80)


def delete_payroll():
    print("Payroll records are historical HR records and cannot be deleted.")
