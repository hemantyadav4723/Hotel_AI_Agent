from utils.error_logging import log_non_blocking_error
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id

SYSTEM_ROLES = {
    "Admin",
    "Manager",
    "Reception",
    "HR",
    "Restaurant Staff",
    "Accountant",
    "Housekeeping",
}


def create_roles_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roles(
                role_id TEXT PRIMARY KEY,
                role_name TEXT NOT NULL,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                is_system_role INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_roles_hotel_id ON roles(hotel_id)"
        )
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_hotel_name
            ON roles(hotel_id, lower(trim(role_name)))
        """)

        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        for role_name in SYSTEM_ROLES:
            role_id = "ROLE-" + re_safe_role_id(role_name)
            cursor.execute("""
                INSERT OR IGNORE INTO roles
                (role_id, role_name, hotel_id, is_system_role, status, created_at, updated_at)
                VALUES(?, ?, 1, 1, 'Active', ?, ?)
            """, (role_id, role_name, now, now))

        # Preserve legacy user roles as role-master entries.
        rows = cursor.execute(
            "SELECT DISTINCT role FROM users WHERE role IS NOT NULL AND TRIM(role) <> ''"
        ).fetchall()
        for row in rows:
            role_name = str(row["role"]).strip().title()
            if role_name:
                role_id = "ROLE-" + re_safe_role_id(role_name)
                cursor.execute("""
                    INSERT OR IGNORE INTO roles
                    (role_id, role_name, hotel_id, is_system_role, status, created_at, updated_at)
                    VALUES(?, ?, 1, 0, 'Active', ?, ?)
                """, (role_id, role_name, now, now))

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_role_assignments(
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                assigned_at TEXT NOT NULL,
                removed_at TEXT,
                assignment_status TEXT NOT NULL DEFAULT 'Active',
                UNIQUE(hotel_id, user_id, role_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_role_assignments_user
            ON user_role_assignments(hotel_id, user_id)
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_assignment_history(
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                role_id TEXT NOT NULL,
                action TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                reason TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_role_assignment_history_user
            ON role_assignment_history(hotel_id, user_id)
        """)

        # Seed the legacy users.role relationship into assignment table.
        legacy = cursor.execute("""
            SELECT user_id, hotel_id, role FROM users
            WHERE role IS NOT NULL AND TRIM(role) <> ''
        """).fetchall()
        for user in legacy:
            role_name = str(user["role"]).strip().title()
            role = cursor.execute("""
                SELECT role_id FROM roles
                WHERE hotel_id = ? AND lower(trim(role_name)) = lower(trim(?))
            """, (user["hotel_id"], role_name)).fetchone()
            if role:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_role_assignments
                    (hotel_id, user_id, role_id, assigned_at, assignment_status)
                    VALUES(?, ?, ?, ?, 'Active')
                """, (user["hotel_id"], user["user_id"], role["role_id"], now))

        connection.commit()
    finally:
        connection.close()


def re_safe_role_id(role_name):
    return "".join(ch if ch.isalnum() else "-" for ch in role_name.upper()).strip("-")


def _role_name_exists(cursor, hotel_id, role_name, exclude_role_id=None):
    sql = """
        SELECT 1 FROM roles
        WHERE hotel_id = ? AND lower(trim(role_name)) = lower(trim(?))
    """
    params = [hotel_id, role_name]
    if exclude_role_id:
        sql += " AND role_id <> ?"
        params.append(exclude_role_id)
    return cursor.execute(sql, params).fetchone() is not None


def save_role(role_id, role_name):
    hotel_id = get_current_hotel_id()
    role_id = role_id.strip().upper()
    role_name = role_name.strip()
    if not role_id or not role_name:
        raise ValueError("Role ID and Role Name are required.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        if cursor.execute(
            "SELECT 1 FROM roles WHERE role_id = ? AND hotel_id = ?",
            (role_id, hotel_id)
        ).fetchone():
            raise ValueError("Role ID already exists.")
        if _role_name_exists(cursor, hotel_id, role_name):
            raise ValueError("Role Name already exists.")
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""
            INSERT INTO roles
            (role_id, role_name, hotel_id, is_system_role, status, created_at, updated_at)
            VALUES(?, ?, ?, 0, 'Active', ?, ?)
        """, (role_id, role_name, hotel_id, now, now))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Role",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_role completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_active_roles():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        return connection.execute("""
            SELECT role_id, role_name, is_system_role
            FROM roles
            WHERE hotel_id = ? AND status = 'Active'
            ORDER BY role_name
        """, (hotel_id,)).fetchall()
    finally:
        connection.close()


def view_roles(include_inactive=True):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        if include_inactive:
            rows = connection.execute("""
                SELECT role_id, role_name, status, is_system_role
                FROM roles WHERE hotel_id = ? ORDER BY role_name
            """, (hotel_id,)).fetchall()
        else:
            rows = connection.execute("""
                SELECT role_id, role_name, status, is_system_role
                FROM roles WHERE hotel_id = ? AND status = 'Active'
                ORDER BY role_name
            """, (hotel_id,)).fetchall()
    finally:
        connection.close()

    print("=" * 60)
    print("              ROLE LIST")
    print("=" * 60)
    if not rows:
        print("No Roles Found.")
        return
    for row in rows:
        role_type = "System" if row["is_system_role"] else "Custom"
        print(f"Role ID      : {row['role_id']}")
        print(f"Role Name    : {row['role_name']}")
        print(f"Type         : {role_type}")
        print(f"Status       : {row['status']}")
        print("-" * 60)


def search_role():
    hotel_id = get_current_hotel_id()
    term = input("Search Role : ").strip()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT role_id, role_name, status, is_system_role
            FROM roles
            WHERE hotel_id = ?
              AND (lower(role_id) LIKE lower(?) OR lower(role_name) LIKE lower(?))
            ORDER BY role_name
        """, (hotel_id, f"%{term}%", f"%{term}%")).fetchall()
    finally:
        connection.close()
    if not rows:
        print("No Role Found.")
        return
    for row in rows:
        print(f"{row['role_id']} | {row['role_name']} | {row['status']}")


def update_role():
    hotel_id = get_current_hotel_id()
    role_id = input("Role ID : ").strip().upper()
    new_name = input("New Role Name : ").strip()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        role = cursor.execute(
            "SELECT role_name, is_system_role FROM roles WHERE role_id = ? AND hotel_id = ?",
            (role_id, hotel_id)
        ).fetchone()
        if not role:
            print("Role Not Found.")
            return
        if role["is_system_role"]:
            print("System role cannot be modified.")
            return
        if not new_name:
            print("Role Name cannot be empty.")
            return
        if _role_name_exists(cursor, hotel_id, new_name, role_id):
            print("Role Name already exists.")
            return
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute(
            "UPDATE roles SET role_name = ?, updated_at = ? WHERE role_id = ? AND hotel_id = ?",
            (new_name, now, role_id, hotel_id)
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Role",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_role completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Role Updated Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error updating role: {exc}")
    finally:
        connection.close()


def _set_role_status(status):
    hotel_id = get_current_hotel_id()
    role_id = input("Role ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        role = cursor.execute("""
            SELECT role_name, status, is_system_role
            FROM roles WHERE role_id = ? AND hotel_id = ?
        """, (role_id, hotel_id)).fetchone()
        if not role:
            print("Role Not Found.")
            return
        if role["is_system_role"]:
            print("System role cannot be deactivated/activated.")
            return
        if role["status"] == status:
            print(f"Role is already {status}.")
            return
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute(
            "UPDATE roles SET status = ?, updated_at = ? WHERE role_id = ? AND hotel_id = ?",
            (status, now, role_id, hotel_id)
        )
        connection.commit()
        print(f"Role {status} Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error changing role status: {exc}")
    finally:
        connection.close()


def deactivate_role():
    _set_role_status("Inactive")


def activate_role():
    _set_role_status("Active")


def delete_role():
    hotel_id = get_current_hotel_id()
    role_id = input("Role ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        role = cursor.execute("""
            SELECT role_name, is_system_role, status
            FROM roles WHERE role_id = ? AND hotel_id = ?
        """, (role_id, hotel_id)).fetchone()
        if not role:
            print("Role Not Found.")
            return
        if role["is_system_role"]:
            print("System role cannot be deleted.")
            return
        used = cursor.execute("""
            SELECT 1 FROM user_role_assignments
            WHERE hotel_id = ? AND role_id = ? AND assignment_status = 'Active'
        """, (hotel_id, role_id)).fetchone()
        if used:
            print("Role is assigned to a user and cannot be deleted.")
            return
        if role["status"] != "Inactive":
            print("Deactivate the role before deleting it.")
            return
        cursor.execute(
            "DELETE FROM roles WHERE role_id = ? AND hotel_id = ?",
            (role_id, hotel_id)
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Role",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_role completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Role Deleted Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error deleting role: {exc}")
    finally:
        connection.close()


def assign_role_to_user(reason=None):
    from database.permission_db import require_hr_authorization
    require_hr_authorization("role_assignment")

    hotel_id = get_current_hotel_id()
    if reason is not None and not str(reason).strip():
        raise ValueError("Reason is required for role assignment.")
    user_id = input("User ID : ").strip().upper()
    role_id = input("Role ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        user = cursor.execute(
            "SELECT 1 FROM users WHERE user_id = ? AND hotel_id = ?",
            (user_id, hotel_id)
        ).fetchone()
        role = cursor.execute(
            "SELECT role_name, status FROM roles WHERE role_id = ? AND hotel_id = ?",
            (role_id, hotel_id)
        ).fetchone()
        if not user:
            print("User Not Found.")
            return
        if not role:
            print("Role Not Found.")
            return
        if role["status"] != "Active":
            print("Inactive role cannot be assigned.")
            return
        if cursor.execute("""
            SELECT 1 FROM user_role_assignments
            WHERE hotel_id = ? AND user_id = ? AND role_id = ?
              AND assignment_status = 'Active'
        """, (hotel_id, user_id, role_id)).fetchone():
            print("Role is already assigned to this user.")
            return
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""
            INSERT INTO user_role_assignments
            (hotel_id, user_id, role_id, assigned_at, assignment_status)
            VALUES(?, ?, ?, ?, 'Active')
            ON CONFLICT(hotel_id, user_id, role_id)
            DO UPDATE SET assigned_at=excluded.assigned_at,
                          removed_at=NULL,
                          assignment_status='Active'
        """, (hotel_id, user_id, role_id, now))
        cursor.execute(
            "UPDATE users SET role = ? WHERE user_id = ? AND hotel_id = ?",
            (role["role_name"], user_id, hotel_id)
        )
        cursor.execute("""
            INSERT INTO role_assignment_history
            (hotel_id, user_id, role_id, action, changed_at, reason)
            VALUES(?, ?, ?, 'ASSIGNED', ?, 'Role assigned')
        """, (hotel_id, user_id, role_id, now))
        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="ROLE_ASSIGNED",
            target_type="USER_ROLE",
            target_id=user_id,
            old_value=None,
            new_value={"role_id": role_id, "role_name": role["role_name"]},
            reason=reason or "Role assigned.",
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Role",
        action="UPDATE",
        local_values=locals(),
        details="Business operation assign_role_to_user completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Role Assigned Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error assigning role: {exc}")
    finally:
        connection.close()


def remove_role_from_user(reason=None):
    from database.permission_db import require_hr_authorization
    require_hr_authorization("role_assignment")

    hotel_id = get_current_hotel_id()
    if reason is not None and not str(reason).strip():
        raise ValueError("Reason is required for role assignment.")
    user_id = input("User ID : ").strip().upper()
    role_id = input("Role ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        assignment = cursor.execute("""
            SELECT 1 FROM user_role_assignments
            WHERE hotel_id = ? AND user_id = ? AND role_id = ?
              AND assignment_status = 'Active'
        """, (hotel_id, user_id, role_id)).fetchone()
        if not assignment:
            print("Active role assignment not found.")
            return
        role = cursor.execute(
            "SELECT is_system_role FROM roles WHERE role_id = ? AND hotel_id = ?",
            (role_id, hotel_id)
        ).fetchone()
        if role and role["is_system_role"]:
            print("System role cannot be removed.")
            return
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""
            UPDATE user_role_assignments
            SET assignment_status='Removed', removed_at=?
            WHERE hotel_id=? AND user_id=? AND role_id=?
        """, (now, hotel_id, user_id, role_id))

        # Keep the legacy users.role field synchronized with the
        # user's remaining active role for backward compatibility.
        replacement = cursor.execute("""
            SELECT r.role_name
            FROM user_role_assignments a
            JOIN roles r ON r.role_id = a.role_id AND r.hotel_id = a.hotel_id
            WHERE a.hotel_id = ? AND a.user_id = ?
              AND a.assignment_status = 'Active'
              AND r.status = 'Active'
            ORDER BY a.assigned_at DESC, a.assignment_id DESC
            LIMIT 1
        """, (hotel_id, user_id)).fetchone()
        cursor.execute(
            "UPDATE users SET role = ? WHERE user_id = ? AND hotel_id = ?",
            (replacement["role_name"] if replacement else None, user_id, hotel_id)
        )

        cursor.execute("""
            INSERT INTO role_assignment_history
            (hotel_id, user_id, role_id, action, changed_at, reason)
            VALUES(?, ?, ?, 'REMOVED', ?, 'Role removed')
        """, (hotel_id, user_id, role_id, now))
        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="ROLE_REMOVED",
            target_type="USER_ROLE",
            target_id=user_id,
            old_value={"role_id": role_id},
            new_value={"role": replacement["role_name"] if replacement else None},
            reason=reason or "Role removed.",
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Role",
        action="CREATE",
        local_values=locals(),
        details="Business operation remove_role_from_user completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Role Removed Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error removing role: {exc}")
    finally:
        connection.close()


def view_user_roles():
    hotel_id = get_current_hotel_id()
    user_id = input("User ID : ").strip().upper()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT r.role_id, r.role_name, a.assignment_status, a.assigned_at, a.removed_at
            FROM user_role_assignments a
            JOIN roles r ON r.role_id = a.role_id AND r.hotel_id = a.hotel_id
            WHERE a.hotel_id = ? AND a.user_id = ?
            ORDER BY r.role_name
        """, (hotel_id, user_id)).fetchall()
    finally:
        connection.close()
    if not rows:
        print("No role assignment found.")
        return
    for row in rows:
        print(
            f"{row['role_id']} | {row['role_name']} | "
            f"{row['assignment_status']} | Assigned: {row['assigned_at']}"
        )


def view_role_assignment_history():
    hotel_id = get_current_hotel_id()
    user_id = input("User ID : ").strip().upper()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT h.action, r.role_name, h.changed_at, h.reason
            FROM role_assignment_history h
            JOIN roles r ON r.role_id = h.role_id AND r.hotel_id = h.hotel_id
            WHERE h.hotel_id = ? AND h.user_id = ?
            ORDER BY h.history_id DESC
        """, (hotel_id, user_id)).fetchall()
    finally:
        connection.close()
    if not rows:
        print("No role history found.")
        return
    for row in rows:
        print(f"{row['changed_at']} | {row['action']} | {row['role_name']} | {row['reason']}")
