from utils.error_logging import log_non_blocking_error
from datetime import datetime

from database.database import get_connection
from utils.date_time import current_date


STAFF_STATUSES = (
    "New",
    "Active",
    "On Leave",
    "Inactive",
    "Resigned",
    "Terminated",
)

TERMINAL_STAFF_STATUSES = {"Resigned", "Terminated"}


def create_staff_status_history_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff_status_history(
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                staff_id TEXT NOT NULL,
                old_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                effective_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                changed_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_staff_status_history_staff
            ON staff_status_history(hotel_id, staff_id, history_id DESC)
        """)
        connection.commit()
    finally:
        connection.close()


def create_staff_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff(
                staff_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                staff_name TEXT NOT NULL,
                mobile TEXT,
                email TEXT,
                address TEXT,
                department TEXT,
                designation TEXT,
                salary REAL,
                joining_date TEXT,
                status TEXT NOT NULL DEFAULT 'Active'
            )
        """)

        # Existing databases may contain the earlier staff schema.
        columns = {row["name"] for row in cursor.execute("PRAGMA table_info(staff)").fetchall()}
        if "hotel_id" not in columns:
            cursor.execute("ALTER TABLE staff ADD COLUMN hotel_id INTEGER NOT NULL DEFAULT 1")
        if "status" not in columns:
            cursor.execute("ALTER TABLE staff ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'")

        cursor.execute("""
            UPDATE staff
            SET hotel_id = 1
            WHERE hotel_id IS NULL
        """)
        cursor.execute("""
            UPDATE staff
            SET status = 'Active'
            WHERE status IS NULL OR TRIM(status) = ''
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_staff_hotel_id ON staff(hotel_id)")
        connection.commit()
    finally:
        connection.close()


def save_staff(staff_id, joining_date, staff_name, mobile, email, address, department, designation, salary):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        from database.hotel_context import get_current_hotel_id
        hotel_id = get_current_hotel_id()

        cursor.execute(
            "SELECT 1 FROM staff WHERE staff_id = ? AND hotel_id = ?",
            (staff_id, hotel_id)
        )
        if cursor.fetchone() is not None:
            raise ValueError("Staff ID already exists for the current hotel.")

        cursor.execute(
            "SELECT 1 FROM department WHERE department_name = ? AND hotel_id = ? AND status = 'Active'",
            (department, hotel_id)
        )

        if cursor.fetchone() is None:
            raise ValueError("Department Not Found.")

        cursor.execute(
            "SELECT 1 FROM designation WHERE designation_name = ? AND hotel_id = ? AND status = 'Active'",
            (designation, hotel_id)
        )
        if cursor.fetchone() is None:
            raise ValueError("Designation Not Found.")

        cursor.execute("""
            INSERT INTO staff
            (staff_id, hotel_id, staff_name, mobile, email, address, department, designation, salary, joining_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
        """, (
            staff_id, hotel_id, staff_name, mobile, email, address, department,
            designation, salary, joining_date.strftime("%d-%m-%Y %I:%M:%S %p")
        ))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Staff",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_staff completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_next_staff_id():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT staff_id FROM staff
            WHERE staff_id LIKE 'EMP%'
            ORDER BY CAST(SUBSTR(staff_id, 4) AS INTEGER) DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
    finally:
        connection.close()

    if not row:
        return "EMP1001"
    return f"EMP{int(row['staff_id'][3:]) + 1}"


def view_staff():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        from database.hotel_context import get_current_hotel_id
        hotel_id = get_current_hotel_id()
        cursor.execute("SELECT * FROM staff WHERE hotel_id = ? ORDER BY staff_id", (hotel_id,))
        staffs = cursor.fetchall()
    finally:
        connection.close()

    if not staffs:
        print("No Staff Found.")
        return

    print("=" * 60)
    print("              STAFF LIST")
    print("=" * 60)
    for staff in staffs:
        print(f"Staff ID     : {staff['staff_id']}")
        print(f"Name         : {staff['staff_name']}")
        print(f"Mobile       : {staff['mobile']}")
        print(f"Email        : {staff['email']}")
        print(f"Department   : {staff['department']}")
        print(f"Designation  : {staff['designation']}")
        print(f"Salary       : {staff['salary']}")
        print(f"Joining Date : {staff['joining_date']}")
        print(f"Status       : {staff['status']}")
        print("-" * 60)


def search_staff():
    staff_id = input("Enter Staff ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        from database.hotel_context import get_current_hotel_id
        hotel_id = get_current_hotel_id()
        cursor.execute("SELECT * FROM staff WHERE staff_id = ? AND hotel_id = ?", (staff_id, hotel_id))
        staff = cursor.fetchone()
    finally:
        connection.close()

    if not staff:
        print("Staff Not Found.")
        return

    for key in ("staff_id", "staff_name", "mobile", "email", "address", "department", "designation", "salary", "joining_date", "status"):
        print(f"{key.replace('_', ' ').title()} : {staff[key]}")


def update_staff():
    """Update only the staff fields the user chooses to change.

    Blank input keeps the existing value. Department and designation are
    selected from the current hotel's active master lists instead of being
    typed manually. Salary remains under Salary Management so salary history
    and HR authorization cannot be bypassed through the generic staff update.
    """
    print("=" * 60)
    print("            UPDATE STAFF")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        from database.hotel_context import get_current_hotel_id
        hotel_id = get_current_hotel_id()
        cursor.execute(
            "SELECT * FROM staff WHERE staff_id = ? AND hotel_id = ?",
            (staff_id, hotel_id),
        )
        staff = cursor.fetchone()
        if not staff:
            print("Staff Not Found.")
            return

        current_name = staff["staff_name"] or ""
        current_mobile = staff["mobile"] or ""
        current_email = staff["email"] or ""
        current_address = staff["address"] or ""
        current_department = staff["department"] or ""
        current_designation = staff["designation"] or ""
        current_salary = staff["salary"]

        print("\nLeave a field blank to keep its current value.")
        print("Salary is managed separately through Salary Management.")
        print()

        name_input = input(f"New Name [{current_name}] : ").strip()
        name = name_input or current_name

        mobile_input = input(f"New Mobile [{current_mobile or '-'}] : ").strip()
        mobile = mobile_input or current_mobile

        email_input = input(f"New Email [{current_email or '-'}] : ").strip()
        email = email_input or current_email

        address_input = input(f"New Address [{current_address or '-'}] : ").strip()
        address = address_input or current_address

        # Department: blank keeps current; otherwise select an active
        # department from the current hotel's master list.
        from database.department_db import get_department_names
        departments = get_department_names()
        print("\nAvailable Departments:")
        if departments:
            for index, department_name in enumerate(departments, start=1):
                marker = " (Current)" if department_name == current_department else ""
                print(f"{index}. {department_name}{marker}")
        else:
            print("No active departments available.")

        while True:
            department_selection = input(
                f"Select Department No [Current: {current_department or '-'}] (Enter = keep) : "
            ).strip()
            if not department_selection:
                department = current_department
                break
            if department_selection.isdigit() and 1 <= int(department_selection) <= len(departments):
                department = departments[int(department_selection) - 1]
                break
            print("Invalid selection. Please select a valid department number or press Enter to keep current.")

        # Designation: blank keeps current; otherwise select an active
        # designation from the current hotel's master list.
        from database.designation_db import get_designation_names
        designations = get_designation_names()
        print("\nAvailable Designations:")
        if designations:
            for index, designation_name in enumerate(designations, start=1):
                marker = " (Current)" if designation_name == current_designation else ""
                print(f"{index}. {designation_name}{marker}")
        else:
            print("No active designations available.")

        while True:
            designation_selection = input(
                f"Select Designation No [Current: {current_designation or '-'}] (Enter = keep) : "
            ).strip()
            if not designation_selection:
                designation = current_designation
                break
            if designation_selection.isdigit() and 1 <= int(designation_selection) <= len(designations):
                designation = designations[int(designation_selection) - 1]
                break
            print("Invalid selection. Please select a valid designation number or press Enter to keep current.")

        cursor.execute(
            """
            SELECT 1
            FROM department
            WHERE department_name = ?
              AND hotel_id = ?
              AND status = 'Active'
            """,
            (department, hotel_id),
        )
        if cursor.fetchone() is None:
            raise ValueError("Department Not Found.")

        cursor.execute(
            """
            SELECT 1
            FROM designation
            WHERE designation_name = ?
              AND hotel_id = ?
              AND status = 'Active'
            """,
            (designation, hotel_id),
        )
        if cursor.fetchone() is None:
            raise ValueError("Designation Not Found.")

        # Salary is intentionally not updated here. The dedicated Salary
        # Management module creates effective-dated salary history and applies
        # the existing HR authorization requirement.
        cursor.execute(
            """
            UPDATE staff SET
                staff_name = ?,
                mobile = ?,
                email = ?,
                address = ?,
                department = ?,
                designation = ?
            WHERE staff_id = ? AND hotel_id = ?
            """,
            (
                name,
                mobile,
                email,
                address,
                department,
                designation,
                staff_id,
                hotel_id,
            ),
        )

        if cursor.rowcount != 1:
            raise ValueError("Staff could not be updated.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Staff",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_staff completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("\nStaff Updated Successfully.")
        print(f"Salary : {current_salary if current_salary is not None else '-'} (unchanged; use Salary Management to change it)")
    except ValueError as exc:
        connection.rollback()
        print(f"Invalid Staff Data: {exc}")
    except Exception as exc:
        connection.rollback()
        print(f"Error updating staff: {exc}")
    finally:
        connection.close()


def _get_staff_for_current_hotel(cursor, staff_id, hotel_id):
    cursor.execute(
        "SELECT * FROM staff WHERE staff_id = ? AND hotel_id = ?",
        (staff_id, hotel_id),
    )
    return cursor.fetchone()


def _status_transition_allowed(old_status, new_status):
    if old_status == new_status:
        return True
    if old_status in TERMINAL_STAFF_STATUSES:
        return False
    if new_status == "New":
        return False
    return True


def change_staff_status():
    from database.permission_db import require_hr_authorization
    require_hr_authorization("staff_status_change")

    print("=" * 60)
    print("          CHANGE STAFF STATUS")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()
    connection = get_connection()
    try:
        from database.hotel_context import get_current_hotel_id
        hotel_id = get_current_hotel_id()
        cursor = connection.cursor()
        staff = _get_staff_for_current_hotel(cursor, staff_id, hotel_id)

        if not staff:
            print("Staff Not Found.")
            return

        print("\nAvailable Statuses:")
        for index, status in enumerate(STAFF_STATUSES, start=1):
            print(f"{index}. {status}")

        while True:
            selection = input("Select New Status No : ").strip()
            if selection.isdigit() and 1 <= int(selection) <= len(STAFF_STATUSES):
                new_status = STAFF_STATUSES[int(selection) - 1]
                break
            print("Invalid selection. Please select a valid status number.")

        old_status = staff["status"]
        if not _status_transition_allowed(old_status, new_status):
            if old_status in TERMINAL_STAFF_STATUSES:
                print(f"Staff is already in terminal status: {old_status}. Status cannot be changed.")
            else:
                print(f"Invalid status transition: {old_status} -> {new_status}.")
            return

        if old_status == new_status:
            print(f"Staff is already {new_status}.")
            return

        effective_date = current_date()
        reason = input("Reason : ").strip()
        if not reason:
            raise ValueError("Reason is required for staff status change.")

        changed_at = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

        cursor.execute(
            """
            UPDATE staff
            SET status = ?
            WHERE staff_id = ? AND hotel_id = ?
            """,
            (new_status, staff_id, hotel_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Staff status could not be updated.")

        cursor.execute(
            """
            INSERT INTO staff_status_history(
                hotel_id, staff_id, old_status, new_status,
                effective_date, reason, changed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hotel_id,
                staff_id,
                old_status,
                new_status,
                effective_date,
                reason,
                changed_at,
            ),
        )

        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="STAFF_STATUS_CHANGED",
            target_type="STAFF",
            target_id=staff_id,
            old_value={"status": old_status},
            new_value={"status": new_status, "effective_date": effective_date},
            reason=reason,
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Staff",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation change_staff_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print(f"\nStaff Status Changed: {old_status} -> {new_status}")
    except ValueError as exc:
        connection.rollback()
        print(f"Invalid Staff Status Data: {exc}")
    except Exception as exc:
        connection.rollback()
        print(f"Error changing staff status: {exc}")
    finally:
        connection.close()


def view_staff_status_history():
    print("=" * 60)
    print("         STAFF STATUS HISTORY")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()
    from database.hotel_context import get_current_hotel_id
    hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT *
            FROM staff_status_history
            WHERE staff_id = ? AND hotel_id = ?
            ORDER BY history_id DESC
            """,
            (staff_id, hotel_id),
        )
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Staff Status History Found.")
        return

    for record in records:
        print(f"History ID     : {record['history_id']}")
        print(f"Staff ID       : {record['staff_id']}")
        print(f"Old Status     : {record['old_status']}")
        print(f"New Status     : {record['new_status']}")
        print(f"Effective Date : {record['effective_date']}")
        print(f"Reason         : {record['reason']}")
        print(f"Changed At     : {record['changed_at']}")
        print("-" * 60)


def activate_staff():
    """Backward-compatible shortcut for activating staff."""
    _change_staff_status_direct("Active", "ACTIVATE STAFF")


def deactivate_staff():
    """Backward-compatible shortcut for deactivating staff."""
    _change_staff_status_direct("Inactive", "DEACTIVATE STAFF")


def _change_staff_status_direct(new_status, title):
    from database.permission_db import require_hr_authorization
    require_hr_authorization("staff_status_change")

    print("=" * 60)
    print(f"          {title}")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()
    connection = get_connection()
    try:
        from database.hotel_context import get_current_hotel_id
        hotel_id = get_current_hotel_id()
        cursor = connection.cursor()
        staff = _get_staff_for_current_hotel(cursor, staff_id, hotel_id)

        if not staff:
            print("Staff Not Found.")
            return

        old_status = staff["status"]
        if old_status == new_status:
            print(f"Staff is already {new_status}.")
            return
        if not _status_transition_allowed(old_status, new_status):
            print(f"Invalid status transition: {old_status} -> {new_status}.")
            return

        effective_date = current_date()
        reason = input("Reason : ").strip()
        if not reason:
            raise ValueError("Reason is required for staff status change.")

        cursor.execute(
            "UPDATE staff SET status = ? WHERE staff_id = ? AND hotel_id = ?",
            (new_status, staff_id, hotel_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Staff status could not be updated.")

        cursor.execute(
            """
            INSERT INTO staff_status_history(
                hotel_id, staff_id, old_status, new_status,
                effective_date, reason, changed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hotel_id,
                staff_id,
                old_status,
                new_status,
                effective_date,
                reason,
                datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"),
            ),
        )
        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="STAFF_STATUS_CHANGED",
            target_type="STAFF",
            target_id=staff_id,
            old_value={"status": old_status},
            new_value={"status": new_status, "effective_date": effective_date},
            reason=reason,
        )
        connection.commit()
        print(f"\nStaff {new_status} Successfully.")
    except ValueError as exc:
        connection.rollback()
        print(f"Invalid Staff Status Data: {exc}")
    except Exception as exc:
        connection.rollback()
        print(f"Error changing staff status: {exc}")
    finally:
        connection.close()


def delete_staff():
    print("=" * 60)
    print("            DELETE STAFF")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        from database.hotel_context import get_current_hotel_id
        hotel_id = get_current_hotel_id()
        cursor.execute("SELECT 1 FROM staff WHERE staff_id = ? AND hotel_id = ?", (staff_id, hotel_id))
        if cursor.fetchone() is None:
            print("Staff Not Found.")
            return

        # A staff record is referenced by attendance, salary and payroll.
        # Deleting the master record would leave orphaned cross-module data.
        cursor.execute(
            "SELECT 1 FROM attendance WHERE staff_id = ? LIMIT 1",
            (staff_id,)
        )
        if cursor.fetchone():
            print(
                "Staff has attendance records and cannot be deleted. "
                "Preserve the staff record for historical consistency."
            )
            return

        cursor.execute(
            "SELECT 1 FROM salary WHERE staff_id = ? LIMIT 1",
            (staff_id,)
        )
        if cursor.fetchone():
            print(
                "Staff has salary records and cannot be deleted. "
                "Preserve the staff record for historical consistency."
            )
            return

        cursor.execute(
            "SELECT 1 FROM payroll WHERE staff_id = ? LIMIT 1",
            (staff_id,)
        )
        if cursor.fetchone():
            print(
                "Staff has payroll records and cannot be deleted. "
                "Preserve the staff record for historical consistency."
            )
            return

        cursor.execute(
            "SELECT 1 FROM staff_status_history WHERE staff_id = ? AND hotel_id = ? LIMIT 1",
            (staff_id, hotel_id)
        )
        if cursor.fetchone():
            print(
                "Staff has status history and cannot be deleted. "
                "Preserve the staff record for historical consistency."
            )
            return

        cursor.execute(
            "SELECT user_id, username FROM users WHERE staff_id = ? AND hotel_id = ? LIMIT 1",
            (staff_id, hotel_id)
        )
        linked_user = cursor.fetchone()
        if linked_user:
            print(
                f"Staff is linked to login user {linked_user['username']} ({linked_user['user_id']}) "
                "and cannot be deleted. Remove the staff ↔ user link first."
            )
            return

        cursor.execute("DELETE FROM staff WHERE staff_id = ? AND hotel_id = ?", (staff_id, hotel_id))
        if cursor.rowcount != 1:
            raise ValueError("Staff could not be deleted.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Staff",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_staff completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("\nStaff Deleted Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error deleting staff: {exc}")
    finally:
        connection.close()
