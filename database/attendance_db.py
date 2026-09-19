from utils.error_logging import log_non_blocking_error
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


ATTENDANCE_STATUSES = (
    "Present",
    "Absent",
    "Late",
    "Half Day",
    "Leave",
)


def create_attendance_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance(
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                staff_id TEXT NOT NULL,
                date TEXT NOT NULL,
                check_in TEXT,
                check_out TEXT,
                status TEXT NOT NULL DEFAULT 'Present'
            )
        """)

        columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(attendance)").fetchall()
        }

        if "hotel_id" not in columns:
            cursor.execute(
                "ALTER TABLE attendance ADD COLUMN hotel_id INTEGER NOT NULL DEFAULT 1"
            )

        if "check_in" not in columns:
            cursor.execute("ALTER TABLE attendance ADD COLUMN check_in TEXT")

        if "check_out" not in columns:
            cursor.execute("ALTER TABLE attendance ADD COLUMN check_out TEXT")

        if "status" not in columns:
            cursor.execute(
                "ALTER TABLE attendance ADD COLUMN status TEXT NOT NULL DEFAULT 'Present'"
            )

        cursor.execute("""
            UPDATE attendance
            SET hotel_id = 1
            WHERE hotel_id IS NULL
        """)
        cursor.execute("""
            UPDATE attendance
            SET status = 'Present'
            WHERE status IS NULL OR TRIM(status) = ''
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_attendance_hotel_staff_date
            ON attendance(hotel_id, staff_id, date)
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_hotel_staff_date
            ON attendance(hotel_id, staff_id, date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_attendance_hotel_date
            ON attendance(hotel_id, date)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance_correction_history(
                correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                attendance_id INTEGER NOT NULL,
                staff_id TEXT NOT NULL,
                old_date TEXT,
                new_date TEXT,
                old_check_in TEXT,
                new_check_in TEXT,
                old_check_out TEXT,
                new_check_out TEXT,
                old_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                reason TEXT NOT NULL,
                corrected_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_attendance_correction_staff
            ON attendance_correction_history(hotel_id, staff_id, correction_id DESC)
        """)

        connection.commit()
    finally:
        connection.close()


def _get_staff(cursor, staff_id, hotel_id):
    cursor.execute(
        "SELECT staff_id, status FROM staff WHERE staff_id = ? AND hotel_id = ?",
        (staff_id, hotel_id),
    )
    return cursor.fetchone()


def _staff_can_receive_attendance(staff):
    return staff is not None and staff["status"] in {"New", "Active"}


def _parse_date(value):
    try:
        return datetime.strptime(value, "%d-%m-%Y").strftime("%d-%m-%Y")
    except ValueError as exc:
        raise ValueError("Invalid date. Use DD-MM-YYYY.") from exc


def _select_status(default="Present"):
    print("\nAttendance Status:")
    for index, status in enumerate(ATTENDANCE_STATUSES, start=1):
        print(f"{index}. {status}")

    while True:
        selection = input("Select Status No : ").strip()
        if selection.isdigit() and 1 <= int(selection) <= len(ATTENDANCE_STATUSES):
            return ATTENDANCE_STATUSES[int(selection) - 1]
        print("Invalid selection. Please select a valid status number.")


def _find_attendance(cursor, attendance_id, hotel_id):
    cursor.execute(
        "SELECT * FROM attendance WHERE attendance_id = ? AND hotel_id = ?",
        (attendance_id, hotel_id),
    )
    return cursor.fetchone()


def staff_check_in():
    print("=" * 60)
    print("             STAFF CHECK IN")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()
    attendance_date = input("Attendance Date (DD-MM-YYYY) [Today] : ").strip()

    if not attendance_date:
        attendance_date = datetime.now().strftime("%d-%m-%Y")
    else:
        try:
            attendance_date = _parse_date(attendance_date)
        except ValueError as exc:
            print(exc)
            return

    now = datetime.now()

    connection = get_connection()
    try:
        hotel_id = get_current_hotel_id()
        cursor = connection.cursor()
        staff = _get_staff(cursor, staff_id, hotel_id)

        if not staff:
            print("Staff Not Found.")
            return

        if not _staff_can_receive_attendance(staff):
            print(
                f"Staff status is '{staff['status']}'. "
                "Staff cannot receive a new attendance assignment."
            )
            return

        from database.leave_db import is_staff_on_approved_leave
        if is_staff_on_approved_leave(staff_id, attendance_date, cursor=cursor, connection=connection):
            print("Staff is on approved leave for this date. Attendance cannot be created.")
            return

        cursor.execute("""
            SELECT attendance_id
            FROM attendance
            WHERE hotel_id = ? AND staff_id = ? AND date = ?
            LIMIT 1
        """, (hotel_id, staff_id, attendance_date))

        if cursor.fetchone():
            print("Attendance Already Exists For This Date.")
            return

        cursor.execute("""
            INSERT INTO attendance
                (hotel_id, staff_id, date, check_in, check_out, status)
            VALUES (?, ?, ?, ?, NULL, 'Present')
        """, (
            hotel_id,
            staff_id,
            attendance_date,
            now.strftime("%I:%M:%S %p"),
        ))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Attendance",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation staff_check_in completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("\nCheck In Successful.")

    except Exception as exc:
        connection.rollback()
        print(f"Error during check in: {exc}")
    finally:
        connection.close()


def staff_check_out():
    print("=" * 60)
    print("             STAFF CHECK OUT")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()
    now = datetime.now()

    connection = get_connection()
    try:
        hotel_id = get_current_hotel_id()
        cursor = connection.cursor()
        staff = _get_staff(cursor, staff_id, hotel_id)

        if not staff:
            print("Staff Not Found.")
            return

        cursor.execute("""
            SELECT attendance_id
            FROM attendance
            WHERE hotel_id = ?
              AND staff_id = ?
              AND check_out IS NULL
              AND check_in IS NOT NULL
            ORDER BY attendance_id DESC
            LIMIT 1
        """, (hotel_id, staff_id))

        record = cursor.fetchone()

        if not record:
            print("\nNo Active Check In Found.")
            return

        cursor.execute("""
            UPDATE attendance
            SET check_out = ?
            WHERE attendance_id = ?
              AND hotel_id = ?
              AND check_out IS NULL
        """, (
            now.strftime("%I:%M:%S %p"),
            record["attendance_id"],
            hotel_id,
        ))

        if cursor.rowcount != 1:
            raise ValueError("Attendance record could not be updated.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Attendance",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation staff_check_out completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("\nCheck Out Successful.")

    except Exception as exc:
        connection.rollback()
        print(f"Error during check out: {exc}")
    finally:
        connection.close()


def view_attendance():
    connection = get_connection()
    try:
        hotel_id = get_current_hotel_id()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM attendance
            WHERE hotel_id = ?
            ORDER BY date DESC, attendance_id DESC
        """, (hotel_id,))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Attendance Found.")
        return

    print("=" * 70)
    print("                    ATTENDANCE HISTORY")
    print("=" * 70)

    for record in records:
        print(f"Attendance ID : {record['attendance_id']}")
        print(f"Staff ID      : {record['staff_id']}")
        print(f"Date          : {record['date']}")
        print(f"Check In      : {record['check_in'] or '--'}")
        print(f"Check Out     : {record['check_out'] or '--'}")
        print(f"Status        : {record['status']}")
        print("-" * 70)


def search_attendance():
    print("=" * 60)
    print("          SEARCH ATTENDANCE")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()

    connection = get_connection()
    try:
        hotel_id = get_current_hotel_id()
        cursor = connection.cursor()
        staff = _get_staff(cursor, staff_id, hotel_id)

        if not staff:
            print("Staff Not Found.")
            return

        cursor.execute("""
            SELECT *
            FROM attendance
            WHERE hotel_id = ? AND staff_id = ?
            ORDER BY date DESC, attendance_id DESC
        """, (hotel_id, staff_id))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("Attendance Not Found.")
        return

    for record in records:
        print(f"Attendance ID : {record['attendance_id']}")
        print(f"Staff ID      : {record['staff_id']}")
        print(f"Date          : {record['date']}")
        print(f"Check In      : {record['check_in'] or '--'}")
        print(f"Check Out     : {record['check_out'] or '--'}")
        print(f"Status        : {record['status']}")
        print("-" * 60)


def correct_attendance():
    print("=" * 60)
    print("          ATTENDANCE CORRECTION")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()
    connection = get_connection()

    try:
        hotel_id = get_current_hotel_id()
        cursor = connection.cursor()
        staff = _get_staff(cursor, staff_id, hotel_id)

        if not staff:
            print("Staff Not Found.")
            return

        cursor.execute("""
            SELECT *
            FROM attendance
            WHERE hotel_id = ? AND staff_id = ?
            ORDER BY date DESC, attendance_id DESC
        """, (hotel_id, staff_id))
        records = cursor.fetchall()

        if not records:
            print("Attendance Not Found.")
            return

        print("\nAttendance Records:")
        for record in records:
            print(
                f"{record['attendance_id']}. "
                f"{record['date']} | "
                f"{record['status']} | "
                f"In: {record['check_in'] or '--'} | "
                f"Out: {record['check_out'] or '--'}"
            )

        while True:
            attendance_id = input("Enter Attendance ID : ").strip()
            if attendance_id.isdigit():
                record = _find_attendance(cursor, int(attendance_id), hotel_id)
                if record and record["staff_id"] == staff_id:
                    break
            print("Invalid Attendance ID.")

        new_date_input = input(
            f"New Date (DD-MM-YYYY) [{record['date']}] : "
        ).strip()
        new_date = record["date"] if not new_date_input else _parse_date(new_date_input)

        new_check_in = input(
            f"New Check In (HH:MM:SS AM/PM) [{record['check_in'] or '--'}] : "
        ).strip()
        new_check_in = record["check_in"] if not new_check_in else new_check_in

        new_check_out = input(
            f"New Check Out (HH:MM:SS AM/PM) [{record['check_out'] or '--'}] : "
        ).strip()
        if new_check_out:
            new_check_out = new_check_out
        else:
            new_check_out = record["check_out"]

        new_status = _select_status(record["status"])
        reason = input("Correction Reason : ").strip()

        if not reason:
            print("Correction reason is required.")
            return

        if new_date != record["date"]:
            cursor.execute("""
                SELECT 1
                FROM attendance
                WHERE hotel_id = ?
                  AND staff_id = ?
                  AND date = ?
                  AND attendance_id != ?
                LIMIT 1
            """, (hotel_id, staff_id, new_date, record["attendance_id"]))
            if cursor.fetchone():
                print("Attendance Already Exists For This Date.")
                return

        cursor.execute("""
            INSERT INTO attendance_correction_history(
                hotel_id, attendance_id, staff_id,
                old_date, new_date,
                old_check_in, new_check_in,
                old_check_out, new_check_out,
                old_status, new_status,
                reason, corrected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hotel_id,
            record["attendance_id"],
            staff_id,
            record["date"],
            new_date,
            record["check_in"],
            new_check_in,
            record["check_out"],
            new_check_out,
            record["status"],
            new_status,
            reason,
            datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"),
        ))

        cursor.execute("""
            UPDATE attendance
            SET date = ?, check_in = ?, check_out = ?, status = ?
            WHERE attendance_id = ? AND hotel_id = ?
        """, (
            new_date,
            new_check_in,
            new_check_out,
            new_status,
            record["attendance_id"],
            hotel_id,
        ))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Attendance",
        action="UPDATE",
        local_values=locals(),
        details="Business operation correct_attendance completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("\nAttendance Corrected Successfully.")

    except ValueError as exc:
        connection.rollback()
        print(f"Invalid Attendance Data: {exc}")
    except Exception as exc:
        connection.rollback()
        print(f"Error correcting attendance: {exc}")
    finally:
        connection.close()


def view_attendance_correction_history():
    print("=" * 60)
    print("       ATTENDANCE CORRECTION HISTORY")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()

    connection = get_connection()
    try:
        hotel_id = get_current_hotel_id()
        cursor = connection.cursor()
        if not _get_staff(cursor, staff_id, hotel_id):
            print("Staff Not Found.")
            return

        cursor.execute("""
            SELECT *
            FROM attendance_correction_history
            WHERE hotel_id = ? AND staff_id = ?
            ORDER BY correction_id DESC
        """, (hotel_id, staff_id))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Attendance Correction History Found.")
        return

    for record in records:
        print(f"Correction ID : {record['correction_id']}")
        print(f"Attendance ID : {record['attendance_id']}")
        print(f"Old Date      : {record['old_date']}")
        print(f"New Date      : {record['new_date']}")
        print(f"Old Status    : {record['old_status']}")
        print(f"New Status    : {record['new_status']}")
        print(f"Old Check In  : {record['old_check_in'] or '--'}")
        print(f"New Check In  : {record['new_check_in'] or '--'}")
        print(f"Old Check Out : {record['old_check_out'] or '--'}")
        print(f"New Check Out : {record['new_check_out'] or '--'}")
        print(f"Reason        : {record['reason']}")
        print(f"Corrected At  : {record['corrected_at']}")
        print("-" * 60)


def monthly_attendance_report():
    print("=" * 60)
    print("        MONTHLY ATTENDANCE REPORT")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()
    month = input("Enter Month (MM-YYYY) : ").strip()

    try:
        month_number, year = month.split("-")
        if (
            len(month_number) != 2
            or len(year) != 4
            or not (1 <= int(month_number) <= 12)
        ):
            raise ValueError
    except ValueError:
        print("Invalid Month. Use MM-YYYY.")
        return

    connection = get_connection()
    try:
        hotel_id = get_current_hotel_id()
        cursor = connection.cursor()
        staff = _get_staff(cursor, staff_id, hotel_id)

        if not staff:
            print("Staff Not Found.")
            return

        cursor.execute("""
            SELECT
                status,
                COUNT(*) AS total
            FROM attendance
            WHERE hotel_id = ?
              AND staff_id = ?
              AND substr(date, 4, 7) = ?
            GROUP BY status
            ORDER BY status
        """, (hotel_id, staff_id, month))
        rows = cursor.fetchall()
    finally:
        connection.close()

    summary = {status: 0 for status in ATTENDANCE_STATUSES}
    for row in rows:
        summary[row["status"]] = row["total"]

    print("-" * 60)
    print("Staff ID :", staff_id)
    print("Month    :", month)
    for status in ATTENDANCE_STATUSES:
        print(f"{status:<10}: {summary[status]}")
    print("-" * 60)
