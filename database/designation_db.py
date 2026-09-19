from database.database import get_connection
from database.hotel_context import get_current_hotel_id


ACTIVE_STATUS = "Active"
INACTIVE_STATUS = "Inactive"


def create_designation_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS designation(
                designation_id TEXT PRIMARY KEY,
                designation_name TEXT NOT NULL,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'Active'
            )
        """)

        columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(designation)").fetchall()
        }

        if "hotel_id" not in columns:
            cursor.execute(
                "ALTER TABLE designation ADD COLUMN hotel_id INTEGER NOT NULL DEFAULT 1"
            )

        if "status" not in columns:
            cursor.execute(
                "ALTER TABLE designation ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'"
            )

        cursor.execute("""
            UPDATE designation
            SET hotel_id = 1
            WHERE hotel_id IS NULL
        """)
        cursor.execute("""
            UPDATE designation
            SET status = 'Active'
            WHERE status IS NULL OR TRIM(status) = ''
        """)

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_designation_hotel_id ON designation(hotel_id)"
        )
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_designation_hotel_name
            ON designation(hotel_id, lower(trim(designation_name)))
            WHERE trim(designation_name) <> ''
        """)

        # Backfill legacy staff designations into the master table.
        cursor.execute("""
            SELECT DISTINCT hotel_id, TRIM(designation) AS designation_name
            FROM staff
            WHERE designation IS NOT NULL
              AND TRIM(designation) <> ''
        """)
        legacy_designations = cursor.fetchall()

        for row in legacy_designations:
            hotel_id = row["hotel_id"] or 1
            designation_name = row["designation_name"]

            cursor.execute("""
                SELECT 1
                FROM designation
                WHERE hotel_id = ?
                  AND lower(trim(designation_name)) = lower(trim(?))
                LIMIT 1
            """, (hotel_id, designation_name))

            if cursor.fetchone():
                continue

            cursor.execute("""
                SELECT designation_id
                FROM designation
                WHERE designation_id LIKE 'DES-%'
                ORDER BY CAST(SUBSTR(designation_id, 5) AS INTEGER) DESC
                LIMIT 1
            """)
            latest = cursor.fetchone()

            if latest:
                try:
                    next_number = int(latest["designation_id"][4:]) + 1
                except (TypeError, ValueError):
                    next_number = 1
            else:
                next_number = 1

            designation_id = f"DES-{next_number:03d}"

            while True:
                cursor.execute(
                    "SELECT 1 FROM designation WHERE designation_id = ?",
                    (designation_id,)
                )
                if cursor.fetchone() is None:
                    break
                next_number += 1
                designation_id = f"DES-{next_number:03d}"

            cursor.execute("""
                INSERT INTO designation(
                    designation_id, designation_name, hotel_id, status
                )
                VALUES (?, ?, ?, 'Active')
            """, (designation_id, designation_name, hotel_id))

        connection.commit()
    finally:
        connection.close()


def save_designation(designation_id, designation_name):
    designation_id = str(designation_id or "").strip().upper()
    designation_name = str(designation_name or "").strip()
    hotel_id = get_current_hotel_id()

    if not designation_id:
        raise ValueError("Designation ID is required.")
    if not designation_name:
        raise ValueError("Designation Name is required.")

    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT 1 FROM designation WHERE designation_id = ?",
            (designation_id,)
        )
        if cursor.fetchone():
            raise ValueError("Designation ID already exists.")

        cursor.execute("""
            SELECT 1
            FROM designation
            WHERE hotel_id = ?
              AND lower(trim(designation_name)) = lower(trim(?))
        """, (hotel_id, designation_name))
        if cursor.fetchone():
            raise ValueError(
                "Designation Name already exists for the current hotel."
            )

        cursor.execute("""
            INSERT INTO designation(
                designation_id, designation_name, hotel_id, status
            )
            VALUES (?, ?, ?, 'Active')
        """, (designation_id, designation_name, hotel_id))

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_designation_names(include_inactive=False):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()

        if include_inactive:
            cursor.execute("""
                SELECT designation_name
                FROM designation
                WHERE hotel_id = ?
                ORDER BY designation_name COLLATE NOCASE
            """, (hotel_id,))
        else:
            cursor.execute("""
                SELECT designation_name
                FROM designation
                WHERE hotel_id = ?
                  AND status = 'Active'
                ORDER BY designation_name COLLATE NOCASE
            """, (hotel_id,))

        return [row["designation_name"] for row in cursor.fetchall()]
    finally:
        connection.close()


def view_designation():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM designation
            WHERE hotel_id = ?
            ORDER BY designation_name COLLATE NOCASE
        """, (hotel_id,))
        records = cursor.fetchall()
    finally:
        connection.close()

    if not records:
        print("No Designation Found.")
        return

    print("=" * 60)
    print("           DESIGNATION LIST")
    print("=" * 60)

    for record in records:
        print(f"Designation ID   : {record['designation_id']}")
        print(f"Designation Name : {record['designation_name']}")
        print(f"Status           : {record['status']}")
        print("-" * 60)


def search_designation():
    designation_id = input("Enter Designation ID : ").strip().upper()
    hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM designation
            WHERE designation_id = ?
              AND hotel_id = ?
        """, (designation_id, hotel_id))
        record = cursor.fetchone()
    finally:
        connection.close()

    if not record:
        print("Designation Not Found.")
        return

    print("=" * 60)
    print(f"Designation ID   : {record['designation_id']}")
    print(f"Designation Name : {record['designation_name']}")
    print(f"Status           : {record['status']}")
    print("=" * 60)


def update_designation():
    designation_id = input("Enter Designation ID : ").strip().upper()
    hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM designation
            WHERE designation_id = ?
              AND hotel_id = ?
        """, (designation_id, hotel_id))
        record = cursor.fetchone()

        if not record:
            print("Designation Not Found.")
            return

        designation_name = input("Enter New Designation Name : ").strip()
        if not designation_name:
            raise ValueError("Designation Name is required.")

        cursor.execute("""
            SELECT 1
            FROM designation
            WHERE hotel_id = ?
              AND designation_id != ?
              AND lower(trim(designation_name)) = lower(trim(?))
        """, (hotel_id, designation_id, designation_name))

        if cursor.fetchone():
            print("Designation Name already exists for the current hotel.")
            return

        old_name = record["designation_name"]

        cursor.execute("""
            UPDATE designation
            SET designation_name = ?
            WHERE designation_id = ?
              AND hotel_id = ?
        """, (designation_name, designation_id, hotel_id))

        cursor.execute("""
            UPDATE staff
            SET designation = ?
            WHERE designation = ?
              AND hotel_id = ?
        """, (designation_name, old_name, hotel_id))

        connection.commit()
        print("Designation Updated Successfully.")
    except ValueError as exc:
        connection.rollback()
        print(f"Invalid Designation Data: {exc}")
    except Exception as exc:
        connection.rollback()
        print(f"Error updating designation: {exc}")
    finally:
        connection.close()


def _set_status(status):
    designation_id = input("Enter Designation ID : ").strip().upper()
    hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT designation_name, status
            FROM designation
            WHERE designation_id = ?
              AND hotel_id = ?
        """, (designation_id, hotel_id))
        record = cursor.fetchone()

        if not record:
            print("Designation Not Found.")
            return

        if record["status"] == status:
            print(f"Designation is already {status}.")
            return

        cursor.execute("""
            UPDATE designation
            SET status = ?
            WHERE designation_id = ?
              AND hotel_id = ?
        """, (status, designation_id, hotel_id))

        connection.commit()
        print(f"Designation {status} Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error changing designation status: {exc}")
    finally:
        connection.close()


def deactivate_designation():
    _set_status(INACTIVE_STATUS)


def activate_designation():
    _set_status(ACTIVE_STATUS)


def view_designation_staff():
    designations = get_designation_names(include_inactive=True)

    if not designations:
        print("No Designation Found.")
        return

    print("=" * 60)
    print("      DESIGNATION-WISE STAFF VIEW")
    print("=" * 60)

    for index, designation_name in enumerate(designations, start=1):
        print(f"{index}. {designation_name}")

    while True:
        selection = input("Select Designation No : ").strip()

        if selection.isdigit() and 1 <= int(selection) <= len(designations):
            designation_name = designations[int(selection) - 1]
            break

        print("Invalid selection. Please select a valid designation number.")

    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT staff_id, staff_name, mobile, department, salary, status
            FROM staff
            WHERE hotel_id = ?
              AND designation = ?
            ORDER BY staff_name COLLATE NOCASE
        """, (hotel_id, designation_name))
        staff_records = cursor.fetchall()
    finally:
        connection.close()

    print("\nDesignation:", designation_name)

    if not staff_records:
        print("No Staff Found with this Designation.")
        return

    print("-" * 60)
    for staff in staff_records:
        print(f"Staff ID     : {staff['staff_id']}")
        print(f"Name         : {staff['staff_name']}")
        print(f"Mobile       : {staff['mobile']}")
        print(f"Department   : {staff['department']}")
        print(f"Salary       : {staff['salary']}")
        print(f"Status       : {staff['status']}")
        print("-" * 60)


def delete_designation():
    designation_id = input("Enter Designation ID : ").strip().upper()
    hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT designation_name
            FROM designation
            WHERE designation_id = ?
              AND hotel_id = ?
        """, (designation_id, hotel_id))
        record = cursor.fetchone()

        if not record:
            print("Designation Not Found.")
            return

        cursor.execute("""
            SELECT 1
            FROM staff
            WHERE designation = ?
              AND hotel_id = ?
            LIMIT 1
        """, (record["designation_name"], hotel_id))

        if cursor.fetchone():
            print(
                "Designation is assigned to staff and cannot be deleted. "
                "Update/reassign the staff records first."
            )
            return

        cursor.execute("""
            DELETE FROM designation
            WHERE designation_id = ?
              AND hotel_id = ?
        """, (designation_id, hotel_id))

        if cursor.rowcount != 1:
            raise ValueError("Designation could not be deleted.")

        connection.commit()
        print("Designation Deleted Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error deleting designation: {exc}")
    finally:
        connection.close()
