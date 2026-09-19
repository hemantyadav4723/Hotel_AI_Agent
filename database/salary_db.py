from utils.error_logging import log_non_blocking_error
from datetime import datetime, timedelta

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


SALARY_DATE_FORMAT = "%d-%m-%Y"


def create_salary_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS salary(
                salary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                staff_id TEXT NOT NULL,
                staff_name TEXT NOT NULL,
                department TEXT,
                designation TEXT,
                basic_salary REAL NOT NULL DEFAULT 0,
                allowances REAL NOT NULL DEFAULT 0,
                bonus REAL NOT NULL DEFAULT 0,
                deduction REAL NOT NULL DEFAULT 0,
                net_salary REAL NOT NULL DEFAULT 0,
                effective_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(salary)").fetchall()
        }

        additions = {
            "hotel_id": "INTEGER NOT NULL DEFAULT 1",
            "designation": "TEXT",
            "allowances": "REAL NOT NULL DEFAULT 0",
            "effective_date": "TEXT",
            "created_at": "TEXT",
        }

        for column, definition in additions.items():
            if column not in columns:
                cursor.execute(
                    f"ALTER TABLE salary ADD COLUMN {column} {definition}"
                )

        cursor.execute("UPDATE salary SET hotel_id = 1 WHERE hotel_id IS NULL")
        cursor.execute("UPDATE salary SET allowances = 0 WHERE allowances IS NULL")

        legacy_date = datetime.now().strftime(SALARY_DATE_FORMAT)
        cursor.execute(
            "UPDATE salary SET effective_date = ? WHERE effective_date IS NULL OR TRIM(effective_date) = ''",
            (legacy_date,)
        )
        cursor.execute(
            "UPDATE salary SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL OR TRIM(created_at) = ''"
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_salary_hotel_staff ON salary(hotel_id, staff_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_salary_effective_date ON salary(hotel_id, staff_id, effective_date DESC)"
        )
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_salary_staff_effective_date
            ON salary(hotel_id, staff_id, effective_date)
        """)

        connection.commit()
    finally:
        connection.close()


def _validate_salary_values(basic_salary, allowances, bonus, deduction):
    values = (basic_salary, allowances, bonus, deduction)
    if any(value < 0 for value in values):
        raise ValueError("Salary amounts cannot be negative.")

    net_salary = basic_salary + allowances + bonus - deduction
    if net_salary < 0:
        raise ValueError("Net salary cannot be negative.")

    return round(net_salary, 2)


def _parse_effective_date(value):
    value = str(value).strip()
    try:
        return datetime.strptime(value, SALARY_DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError("Effective date must be in DD-MM-YYYY format.") from exc


def _sync_staff_current_salary(cursor, hotel_id, staff_id):
    today = datetime.now().date()
    today_text = today.strftime(SALARY_DATE_FORMAT)
    cursor.execute("""
        SELECT net_salary
        FROM salary
        WHERE hotel_id = ? AND staff_id = ?
          AND date(substr(effective_date, 7, 4) || '-' || substr(effective_date, 4, 2) || '-' || substr(effective_date, 1, 2)) <=
              date(substr(?, 7, 4) || '-' || substr(?, 4, 2) || '-' || substr(?, 1, 2))
        ORDER BY date(substr(effective_date, 7, 4) || '-' || substr(effective_date, 4, 2) || '-' || substr(effective_date, 1, 2)) DESC, salary_id DESC
        LIMIT 1
    """, (hotel_id, staff_id, today_text, today_text, today_text))
    current = cursor.fetchone()
    if current is not None:
        cursor.execute(
            "UPDATE staff SET salary = ? WHERE staff_id = ? AND hotel_id = ?",
            (current["net_salary"], staff_id, hotel_id)
        )


def _print_salary_record(record):
    print(f"Salary ID     : {record['salary_id']}")
    print(f"Staff ID      : {record['staff_id']}")
    print(f"Name          : {record['staff_name']}")
    print(f"Department    : {record['department'] or '-'}")
    print(f"Designation   : {record['designation'] or '-'}")
    print(f"Basic Salary  : {record['basic_salary']:.2f}")
    print(f"Allowances    : {record['allowances']:.2f}")
    print(f"Bonus         : {record['bonus']:.2f}")
    print(f"Deduction     : {record['deduction']:.2f}")
    print(f"Net Salary    : {record['net_salary']:.2f}")
    print(f"Effective Date: {record['effective_date']}")
    print(f"Created At    : {record['created_at']}")


def save_salary(staff_id, basic_salary, allowances, bonus, deduction, effective_date, reason=None):
    from database.permission_db import require_hr_authorization
    require_hr_authorization("salary_update")

    hotel_id = get_current_hotel_id()
    if reason is not None and not str(reason).strip():
        raise ValueError("Reason is required for salary change.")
    effective = _parse_effective_date(effective_date)
    net_salary = _validate_salary_values(
        float(basic_salary),
        float(allowances),
        float(bonus),
        float(deduction),
    )

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT staff_name, department, designation, status
            FROM staff
            WHERE staff_id = ? AND hotel_id = ?
        """, (staff_id, hotel_id))
        staff = cursor.fetchone()

        if staff is None:
            raise ValueError("Staff Not Found for the current hotel.")

        if staff["status"] in {"Inactive", "Resigned", "Terminated"}:
            raise ValueError("Salary cannot be assigned to inactive or separated staff.")

        previous_salary = cursor.execute("""
            SELECT salary_id, basic_salary, allowances, bonus, deduction,
                   net_salary, effective_date
            FROM salary
            WHERE hotel_id = ? AND staff_id = ?
              AND effective_date <= ?
            ORDER BY date(substr(effective_date, 7, 4) || '-' ||
                          substr(effective_date, 4, 2) || '-' ||
                          substr(effective_date, 1, 2)) DESC,
                     salary_id DESC
            LIMIT 1
        """, (hotel_id, staff_id, effective.strftime(SALARY_DATE_FORMAT))).fetchone()

        cursor.execute("""
            SELECT 1
            FROM salary
            WHERE hotel_id = ? AND staff_id = ? AND effective_date = ?
        """, (hotel_id, staff_id, effective.strftime(SALARY_DATE_FORMAT)))
        if cursor.fetchone() is not None:
            raise ValueError("Salary already exists for this staff on the effective date.")

        cursor.execute("""
            INSERT INTO salary(
                hotel_id, staff_id, staff_name, department, designation,
                basic_salary, allowances, bonus, deduction, net_salary,
                effective_date, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            hotel_id,
            staff_id,
            staff["staff_name"],
            staff["department"],
            staff["designation"],
            float(basic_salary),
            float(allowances),
            float(bonus),
            float(deduction),
            net_salary,
            effective.strftime(SALARY_DATE_FORMAT),
        ))

        salary_id = cursor.lastrowid
        _sync_staff_current_salary(cursor, hotel_id, staff_id)
        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="SALARY_UPDATED",
            target_type="STAFF_SALARY",
            target_id=staff_id,
            old_value=dict(previous_salary) if previous_salary else None,
            new_value={
                "salary_id": salary_id,
                "basic_salary": float(basic_salary),
                "allowances": float(allowances),
                "bonus": float(bonus),
                "deduction": float(deduction),
                "net_salary": net_salary,
                "effective_date": effective.strftime(SALARY_DATE_FORMAT),
            },
            reason=reason or "Salary record created/updated.",
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Salary",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_salary completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Salary Saved Successfully.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def get_current_salary_for_date(staff_id, effective_date, hotel_id=None):
    hotel_id = hotel_id or get_current_hotel_id()
    try:
        target_date = datetime.strptime(
            str(effective_date).strip(), "%Y-%m-%d"
        ).date()
    except ValueError as exc:
        raise ValueError("Salary lookup date must be in YYYY-MM-DD format.") from exc

    target_text = target_date.strftime(SALARY_DATE_FORMAT)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM salary
            WHERE hotel_id = ? AND staff_id = ?
              AND date(substr(effective_date, 7, 4) || '-' ||
                       substr(effective_date, 4, 2) || '-' ||
                       substr(effective_date, 1, 2)) <= date(?)
            ORDER BY
                date(substr(effective_date, 7, 4) || '-' ||
                     substr(effective_date, 4, 2) || '-' ||
                     substr(effective_date, 1, 2)) DESC,
                salary_id DESC
            LIMIT 1
        """, (hotel_id, staff_id, target_date.strftime("%Y-%m-%d")))
        return cursor.fetchone()
    finally:
        connection.close()


def get_current_salary(staff_id, hotel_id=None):
    hotel_id = hotel_id or get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM salary
            WHERE hotel_id = ? AND staff_id = ?
              AND date(substr(effective_date, 7, 4) || '-' || substr(effective_date, 4, 2) || '-' || substr(effective_date, 1, 2)) <=
                  date(substr(?, 7, 4) || '-' || substr(?, 4, 2) || '-' || substr(?, 1, 2))
            ORDER BY date(substr(effective_date, 7, 4) || '-' || substr(effective_date, 4, 2) || '-' || substr(effective_date, 1, 2)) DESC,
                     salary_id DESC
            LIMIT 1
        """, (hotel_id, staff_id, datetime.now().strftime(SALARY_DATE_FORMAT), datetime.now().strftime(SALARY_DATE_FORMAT), datetime.now().strftime(SALARY_DATE_FORMAT)))
        return cursor.fetchone()
    finally:
        connection.close()


def view_salary():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT * FROM salary
            WHERE hotel_id = ?
            ORDER BY salary_id DESC
        """, (hotel_id,))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Salary Record Found.")
        return

    print("=" * 60)
    print("            SALARY RECORDS")
    print("=" * 60)
    for record in records:
        _print_salary_record(record)
        print("-" * 60)


def search_salary(staff_id):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT * FROM salary
            WHERE hotel_id = ? AND staff_id = ?
            ORDER BY salary_id DESC
        """, (hotel_id, staff_id))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("Salary Record Not Found.")
        return

    for record in records:
        _print_salary_record(record)
        print("-" * 60)


def update_salary(staff_id, basic_salary, allowances, bonus, deduction, effective_date):
    # Salary updates are versioned: a new effective-dated record is created.
    save_salary(
        staff_id,
        basic_salary,
        allowances,
        bonus,
        deduction,
        effective_date,
    )
    print("Salary Updated Successfully as a new effective-dated record.")


def get_salary_history(staff_id):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT * FROM salary
            WHERE hotel_id = ? AND staff_id = ?
            ORDER BY date(substr(effective_date, 7, 4) || '-' || substr(effective_date, 4, 2) || '-' || substr(effective_date, 1, 2)) DESC,
                     salary_id DESC
        """, (hotel_id, staff_id))
        return cursor.fetchall()
    finally:
        connection.close()


def delete_salary(staff_id=None):
    print("Salary records are historical HR records and cannot be deleted.")
