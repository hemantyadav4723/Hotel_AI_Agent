from utils.error_logging import log_non_blocking_error
from database.database import get_connection
from database.hotel_context import get_current_hotel_id


ACTIVE_STATUS = "Active"
INACTIVE_STATUS = "Inactive"


def create_department_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS department(
                department_id TEXT PRIMARY KEY,
                department_name TEXT,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'Active'
            )
        """)

        columns = {row["name"] for row in cursor.execute("PRAGMA table_info(department)").fetchall()}
        if "hotel_id" not in columns:
            cursor.execute("ALTER TABLE department ADD COLUMN hotel_id INTEGER NOT NULL DEFAULT 1")
        if "status" not in columns:
            cursor.execute("ALTER TABLE department ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'")

        cursor.execute("UPDATE department SET hotel_id = 1 WHERE hotel_id IS NULL")
        cursor.execute("""
            UPDATE department
            SET status = 'Active'
            WHERE status IS NULL OR TRIM(status) = ''
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_department_hotel_id ON department(hotel_id)")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_department_hotel_name
            ON department(hotel_id, lower(trim(department_name)))
            WHERE department_name IS NOT NULL AND trim(department_name) != ''
        """)
        connection.commit()
    finally:
        connection.close()


def _normalize_name(value):
    name = str(value or "").strip()
    if not name:
        raise ValueError("Department Name cannot be empty.")
    return " ".join(name.split())


def save_department(department_id, department_name):
    department_id = str(department_id or "").strip().upper()
    department_name = _normalize_name(department_name)
    if not department_id:
        raise ValueError("Department ID cannot be empty.")

    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM department WHERE department_id = ?", (department_id,))
        if cursor.fetchone():
            raise ValueError("Department ID already exists.")

        cursor.execute(
            """
            SELECT 1 FROM department
            WHERE hotel_id = ? AND lower(trim(department_name)) = lower(trim(?))
            """,
            (hotel_id, department_name),
        )
        if cursor.fetchone():
            raise ValueError("Department Name already exists for the current hotel.")

        cursor.execute(
            """
            INSERT INTO department(department_id, department_name, hotel_id, status)
            VALUES (?, ?, ?, 'Active')
            """,
            (department_id, department_name, hotel_id),
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Department",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_department completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_department_names(include_inactive=False):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = """
            SELECT department_name
            FROM department
            WHERE hotel_id = ?
              AND department_name IS NOT NULL
              AND TRIM(department_name) != ''
        """
        params = [hotel_id]
        if not include_inactive:
            query += " AND status = 'Active'"
        query += " ORDER BY department_name COLLATE NOCASE"
        cursor.execute(query, params)
        return [row["department_name"].strip() for row in cursor.fetchall()]
    finally:
        connection.close()



def get_active_department_options():
    """Return active departments for cross-module selection, scoped to the current hotel."""
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT department_id, department_name
            FROM department
            WHERE hotel_id = ? AND status = 'Active'
            ORDER BY department_name COLLATE NOCASE
            """,
            (hotel_id,),
        )
        return cursor.fetchall()
    finally:
        connection.close()


def view_department():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM department WHERE hotel_id = ? ORDER BY department_name COLLATE NOCASE",
            (hotel_id,),
        )
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Department Found.")
        return

    print("=" * 60)
    print("        DEPARTMENT LIST")
    print("=" * 60)
    for record in records:
        print(f"Department ID   : {record['department_id']}")
        print(f"Department Name : {record['department_name']}")
        print(f"Status          : {record['status']}")
        print("-" * 60)


def search_department():
    department_id = input("Enter Department ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM department WHERE department_id = ? AND hotel_id = ?",
            (department_id, hotel_id),
        )
        record = cursor.fetchone()
    finally:
        connection.close()

    if not record:
        print("Department Not Found.")
        return

    print("=" * 60)
    print(f"Department ID   : {record['department_id']}")
    print(f"Department Name : {record['department_name']}")
    print(f"Status          : {record['status']}")
    print("=" * 60)


def update_department():
    department_id = input("Enter Department ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM department WHERE department_id = ? AND hotel_id = ?",
            (department_id, hotel_id),
        )
        record = cursor.fetchone()
        if not record:
            print("Department Not Found.")
            return

        department_name = _normalize_name(input("Enter New Department Name : "))
        cursor.execute(
            """
            SELECT 1 FROM department
            WHERE hotel_id = ?
              AND department_id != ?
              AND lower(trim(department_name)) = lower(trim(?))
            """,
            (hotel_id, department_id, department_name),
        )
        if cursor.fetchone():
            print("Department Name already exists for the current hotel.")
            return

        old_department_name = record["department_name"]
        cursor.execute(
            "UPDATE department SET department_name = ? WHERE department_id = ? AND hotel_id = ?",
            (department_name, department_id, hotel_id),
        )
        cursor.execute(
            "UPDATE staff SET department = ? WHERE department = ? AND hotel_id = ?",
            (department_name, old_department_name, hotel_id),
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Department",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_department completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Department Updated Successfully.")
    except ValueError as exc:
        connection.rollback()
        print(f"Invalid Department Data: {exc}")
    except Exception as exc:
        connection.rollback()
        print(f"Error updating department: {exc}")
    finally:
        connection.close()


def _set_status(status):
    department_id = input("Enter Department ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT department_name, status FROM department WHERE department_id = ? AND hotel_id = ?",
            (department_id, hotel_id),
        )
        record = cursor.fetchone()
        if not record:
            print("Department Not Found.")
            return
        if record["status"] == status:
            print(f"Department is already {status}.")
            return
        cursor.execute(
            "UPDATE department SET status = ? WHERE department_id = ? AND hotel_id = ?",
            (status, department_id, hotel_id),
        )
        connection.commit()
        print(f"Department {status} Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error changing department status: {exc}")
    finally:
        connection.close()


def deactivate_department():
    _set_status(INACTIVE_STATUS)


def activate_department():
    _set_status(ACTIVE_STATUS)


def view_department_staff():
    departments = get_department_names(include_inactive=True)
    if not departments:
        print("No Department Found.")
        return

    print("=" * 60)
    print("      DEPARTMENT-WISE STAFF VIEW")
    print("=" * 60)
    for index, department_name in enumerate(departments, start=1):
        print(f"{index}. {department_name}")

    while True:
        selection = input("Select Department No : ").strip()
        if selection.isdigit() and 1 <= int(selection) <= len(departments):
            department_name = departments[int(selection) - 1]
            break
        print("Invalid selection. Please select a valid department number.")

    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT staff_id, staff_name, mobile, designation, salary, status
            FROM staff
            WHERE hotel_id = ? AND department = ?
            ORDER BY staff_name COLLATE NOCASE
            """,
            (hotel_id, department_name),
        )
        staff_records = cursor.fetchall()
    finally:
        connection.close()

    print("\nDepartment:", department_name)
    if not staff_records:
        print("No Staff Found in this Department.")
        return

    print("-" * 60)
    for staff in staff_records:
        print(f"Staff ID     : {staff['staff_id']}")
        print(f"Name         : {staff['staff_name']}")
        print(f"Mobile       : {staff['mobile']}")
        print(f"Designation  : {staff['designation']}")
        print(f"Salary       : {staff['salary']}")
        print(f"Status       : {staff['status']}")
        print("-" * 60)


def delete_department():
    department_id = input("Enter Department ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT department_name FROM department WHERE department_id = ? AND hotel_id = ?",
            (department_id, hotel_id),
        )
        record = cursor.fetchone()
        if not record:
            print("Department Not Found.")
            return

        department_name = record["department_name"]
        cursor.execute(
            "SELECT 1 FROM staff WHERE department = ? AND hotel_id = ? LIMIT 1",
            (department_name, hotel_id),
        )
        if cursor.fetchone():
            print(
                "Department is assigned to staff and cannot be deleted. "
                "Update/reassign the staff records first."
            )
            return

        cursor.execute(
            "DELETE FROM department WHERE department_id = ? AND hotel_id = ?",
            (department_id, hotel_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Department could not be deleted.")
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Department",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_department completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Department Deleted Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error deleting department: {exc}")
    finally:
        connection.close()
