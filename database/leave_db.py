from utils.error_logging import log_non_blocking_error
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


LEAVE_STATUSES = ("Pending", "Approved", "Rejected", "Cancelled")
ACTIVE_STAFF_STATUSES = {"New", "Active"}


def create_leave_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff_leaves(
                leave_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                staff_id TEXT NOT NULL,
                leave_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                approved_by TEXT,
                approved_at TEXT,
                decision_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_staff_leaves_hotel_staff
            ON staff_leaves(hotel_id, staff_id, start_date, end_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_staff_leaves_hotel_status
            ON staff_leaves(hotel_id, status)
        """)
        connection.commit()
    finally:
        connection.close()


def _parse_date(value):
    try:
        return datetime.strptime(value, "%d-%m-%Y").strftime("%d-%m-%Y")
    except ValueError as exc:
        raise ValueError("Invalid date. Use DD-MM-YYYY.") from exc


def _date_key(value):
    return datetime.strptime(value, "%d-%m-%Y").date()


def _get_staff(cursor, staff_id, hotel_id):
    cursor.execute(
        "SELECT staff_id, staff_name, status FROM staff WHERE staff_id = ? AND hotel_id = ?",
        (staff_id, hotel_id),
    )
    return cursor.fetchone()


def _overlap_exists(cursor, hotel_id, staff_id, start_date, end_date, exclude_leave_id=None):
    query = """
        SELECT leave_id
        FROM staff_leaves
        WHERE hotel_id = ?
          AND staff_id = ?
          AND status IN ('Pending', 'Approved')
          AND start_date <= ?
          AND end_date >= ?
    """
    params = [hotel_id, staff_id, end_date, start_date]
    if exclude_leave_id is not None:
        query += " AND leave_id != ?"
        params.append(exclude_leave_id)
    query += " LIMIT 1"
    cursor.execute(query, params)
    return cursor.fetchone()


def request_leave():
    print("=" * 60)
    print("             LEAVE REQUEST")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()
    leave_type = input("Leave Type : ").strip()
    start_date = input("Start Date (DD-MM-YYYY) : ").strip()
    end_date = input("End Date (DD-MM-YYYY) : ").strip()
    reason = input("Reason : ").strip()

    if not leave_type:
        print("Leave Type is required.")
        return
    if not reason:
        print("Reason is required.")
        return

    try:
        start_date = _parse_date(start_date)
        end_date = _parse_date(end_date)
        if _date_key(start_date) > _date_key(end_date):
            raise ValueError("Start Date cannot be after End Date.")
    except ValueError as exc:
        print(exc)
        return

    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        staff = _get_staff(cursor, staff_id, hotel_id)
        if not staff:
            print("Staff Not Found.")
            return
        if staff["status"] not in ACTIVE_STAFF_STATUSES:
            print(f"Staff status is '{staff['status']}'. Leave cannot be requested.")
            return

        if _overlap_exists(cursor, hotel_id, staff_id, start_date, end_date):
            print("An active leave request already overlaps this date range.")
            return

        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""
            INSERT INTO staff_leaves(
                hotel_id, staff_id, leave_type, start_date, end_date,
                reason, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
        """, (hotel_id, staff_id, leave_type, start_date, end_date, reason, now, now))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Leave",
        action="CREATE",
        local_values=locals(),
        details="Business operation request_leave completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("\nLeave Request Created Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error creating leave request: {exc}")
    finally:
        connection.close()


def view_leave_requests():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT l.*, s.staff_name
            FROM staff_leaves l
            LEFT JOIN staff s
              ON s.staff_id = l.staff_id AND s.hotel_id = l.hotel_id
            WHERE l.hotel_id = ?
            ORDER BY l.leave_id DESC
        """, (hotel_id,))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Leave Records Found.")
        return

    print("=" * 70)
    print("                  LEAVE HISTORY")
    print("=" * 70)
    for record in records:
        print(f"Leave ID       : {record['leave_id']}")
        print(f"Staff ID       : {record['staff_id']}")
        print(f"Staff Name     : {record['staff_name'] or 'N/A'}")
        print(f"Leave Type     : {record['leave_type']}")
        print(f"Start Date     : {record['start_date']}")
        print(f"End Date       : {record['end_date']}")
        print(f"Reason         : {record['reason']}")
        print(f"Status         : {record['status']}")
        print(f"Approved By    : {record['approved_by'] or 'N/A'}")
        print(f"Approved At    : {record['approved_at'] or 'N/A'}")
        print(f"Decision Note  : {record['decision_reason'] or 'N/A'}")
        print(f"Created At     : {record['created_at']}")
        print("-" * 70)


def search_leave():
    staff_id = input("Enter Staff ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT * FROM staff_leaves
            WHERE hotel_id = ? AND staff_id = ?
            ORDER BY leave_id DESC
        """, (hotel_id, staff_id))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Leave Records Found.")
        return

    for record in records:
        print(
            f"Leave ID: {record['leave_id']} | {record['leave_type']} | "
            f"{record['start_date']} to {record['end_date']} | {record['status']}"
        )


def approve_leave():
    from database.permission_db import require_hr_authorization
    require_hr_authorization("leave_approval")
    _decide_leave("Approved")


def reject_leave():
    from database.permission_db import require_hr_authorization
    require_hr_authorization("leave_approval")
    _decide_leave("Rejected")


def _decide_leave(new_status):
    from getpass import getpass
    from database.user_db import get_current_session, verify_current_session_password

    print("=" * 60)
    print(f"             {new_status.upper()} LEAVE")
    print("=" * 60)

    session = get_current_session()
    if not session:
        print("Login required for this action.")
        return

    approver = str(session.get("username") or "").strip()
    if not approver:
        print("Current logged-in user could not be identified.")
        return

    leave_id = input("Enter Leave ID : ").strip()
    if not leave_id.isdigit():
        print("Invalid Leave ID.")
        return

    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM staff_leaves WHERE leave_id = ? AND hotel_id = ?",
            (int(leave_id), hotel_id),
        )
        leave = cursor.fetchone()
        if not leave:
            print("Leave Record Not Found.")
            return
        if leave["status"] != "Pending":
            print(f"Leave is already {leave['status']}. Only Pending requests can be decided.")
            return
    finally:
        connection.close()

    # The approver is always the currently authenticated user. It cannot be
    # supplied manually because that would allow forged HR history.
    print(f"Approver (Current Logged-in User) : {approver}")
    print("Password confirmation is required for this sensitive HR action.")

    while True:
        password = getpass("Confirm Password : ")
        if verify_current_session_password(password):
            print("Password Verified Successfully.")
            break

        print("Incorrect Password. Leave approval/rejection was NOT performed.")
        retry = input("Try Again? (Y/N) : ").strip().upper()
        if retry != "Y":
            print("Action Cancelled. Leave status remains Pending.")
            return

    decision_reason = input("Decision Reason : ").strip()
    if not decision_reason:
        print("Decision Reason is required.")
        return

    connection = get_connection()
    try:
        cursor = connection.cursor()
        # Re-read the row inside the write transaction so a stale screen cannot
        # decide a leave that has already been processed elsewhere.
        cursor.execute(
            "SELECT * FROM staff_leaves WHERE leave_id = ? AND hotel_id = ?",
            (int(leave_id), hotel_id),
        )
        leave = cursor.fetchone()
        if not leave:
            print("Leave Record Not Found.")
            return
        if leave["status"] != "Pending":
            print(f"Leave is already {leave['status']}. Only Pending requests can be decided.")
            return

        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""
            UPDATE staff_leaves
            SET status = ?, approved_by = ?, approved_at = ?, decision_reason = ?, updated_at = ?
            WHERE leave_id = ? AND hotel_id = ? AND status = 'Pending'
        """, (new_status, approver, now, decision_reason, now, int(leave_id), hotel_id))
        if cursor.rowcount != 1:
            raise ValueError("Leave status could not be updated.")

        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action=f"LEAVE_{new_status.upper()}",
            target_type="LEAVE",
            target_id=leave_id,
            old_value={"status": leave["status"]},
            new_value={"status": new_status, "approved_by": approver},
            reason=decision_reason,
        )
        connection.commit()
        print(f"\nLeave {new_status} Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error updating leave: {exc}")
    finally:
        connection.close()


def cancel_leave():
    print("=" * 60)
    print("             CANCEL LEAVE")
    print("=" * 60)

    leave_id = input("Enter Leave ID : ").strip()
    reason = input("Cancellation Reason : ").strip()
    if not leave_id.isdigit() or not reason:
        print("Valid Leave ID and Cancellation Reason are required.")
        return

    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT status FROM staff_leaves WHERE leave_id = ? AND hotel_id = ?",
            (int(leave_id), hotel_id),
        )
        leave = cursor.fetchone()
        if not leave:
            print("Leave Record Not Found.")
            return
        if leave["status"] not in {"Pending", "Approved"}:
            print(f"Leave is already {leave['status']} and cannot be cancelled.")
            return

        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""
            UPDATE staff_leaves
            SET status = 'Cancelled', decision_reason = ?, updated_at = ?
            WHERE leave_id = ? AND hotel_id = ?
        """, (reason, now, int(leave_id), hotel_id))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Leave",
        action="CANCEL",
        local_values=locals(),
        details="Business operation cancel_leave completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("\nLeave Cancelled Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error cancelling leave: {exc}")
    finally:
        connection.close()


def is_staff_on_approved_leave(staff_id, attendance_date, cursor=None, connection=None):
    own_connection = connection is None
    if own_connection:
        connection = get_connection()
    try:
        if cursor is None:
            cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        cursor.execute("""
            SELECT 1
            FROM staff_leaves
            WHERE hotel_id = ?
              AND staff_id = ?
              AND status = 'Approved'
              AND start_date <= ?
              AND end_date >= ?
            LIMIT 1
        """, (hotel_id, staff_id, attendance_date, attendance_date))
        return cursor.fetchone() is not None
    finally:
        if own_connection:
            connection.close()
