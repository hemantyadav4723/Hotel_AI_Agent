from utils.error_logging import log_non_blocking_error
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id

PERMISSION_ACTIONS = (
    "View", "Create", "Update", "Delete", "Approve", "Cancel", "Payment", "Refund", "Reports"
)

PERMISSION_MODULES = (
    "Hotel", "Rooms", "Restaurant", "Tables", "Customers", "Staff",
    "Attendance", "Leave", "Salary", "Payroll", "Inventory", "Expenses", "Reports", "Settings", "Users"
)


def _permission_key(module_name, action):
    return f"{module_name.upper()}_{action.upper()}"


def create_permissions_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permissions(
                permission_id TEXT PRIMARY KEY,
                module_name TEXT NOT NULL,
                action_name TEXT NOT NULL,
                permission_name TEXT NOT NULL,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                is_system_permission INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(hotel_id, module_name, action_name)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_permissions_hotel ON permissions(hotel_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_permissions_module_action ON permissions(hotel_id, module_name, action_name)")

        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        for module_name in PERMISSION_MODULES:
            for action in PERMISSION_ACTIONS:
                permission_id = "PERM-" + _permission_key(module_name, action)
                permission_name = f"{module_name} - {action}"
                cursor.execute("""
                    INSERT OR IGNORE INTO permissions
                    (permission_id, module_name, action_name, permission_name,
                     hotel_id, is_system_permission, status, created_at, updated_at)
                    VALUES(?, ?, ?, ?, 1, 1, 'Active', ?, ?)
                """, (permission_id, module_name, action, permission_name, now, now))
        connection.commit()
    finally:
        connection.close()


def get_active_permissions(module_name=None):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        sql = """
            SELECT permission_id, module_name, action_name, permission_name,
                   is_system_permission, status
            FROM permissions
            WHERE hotel_id = ? AND status = 'Active'
        """
        params = [hotel_id]
        if module_name:
            sql += " AND lower(module_name) = lower(?)"
            params.append(module_name.strip())
        sql += " ORDER BY module_name, action_name"
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def view_permissions(include_inactive=True):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        condition = "" if include_inactive else " AND status = 'Active'"
        rows = connection.execute(f"""
            SELECT permission_id, module_name, action_name, permission_name,
                   status, is_system_permission
            FROM permissions
            WHERE hotel_id = ?{condition}
            ORDER BY module_name, action_name
        """, (hotel_id,)).fetchall()
    finally:
        connection.close()

    print("=" * 72)
    print("                       PERMISSION LIST")
    print("=" * 72)
    if not rows:
        print("No Permissions Found.")
        return
    for row in rows:
        kind = "System" if row["is_system_permission"] else "Custom"
        print(f"Permission ID : {row['permission_id']}")
        print(f"Module        : {row['module_name']}")
        print(f"Action        : {row['action_name']}")
        print(f"Permission    : {row['permission_name']}")
        print(f"Type          : {kind}")
        print(f"Status        : {row['status']}")
        print("-" * 72)


def search_permission():
    hotel_id = get_current_hotel_id()
    term = input("Search Permission : ").strip()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT permission_id, module_name, action_name, permission_name, status
            FROM permissions
            WHERE hotel_id = ?
              AND (lower(permission_id) LIKE lower(?)
                   OR lower(module_name) LIKE lower(?)
                   OR lower(action_name) LIKE lower(?)
                   OR lower(permission_name) LIKE lower(?))
            ORDER BY module_name, action_name
        """, (hotel_id, f"%{term}%", f"%{term}%", f"%{term}%", f"%{term}%")).fetchall()
    finally:
        connection.close()
    if not rows:
        print("No Permission Found.")
        return
    for row in rows:
        print(f"{row['permission_id']} | {row['permission_name']} | {row['status']}")


def _set_permission_status(status):
    hotel_id = get_current_hotel_id()
    permission_id = input("Permission ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        row = cursor.execute("""
            SELECT status, is_system_permission
            FROM permissions WHERE permission_id = ? AND hotel_id = ?
        """, (permission_id, hotel_id)).fetchone()
        if not row:
            print("Permission Not Found.")
            return
        if row["is_system_permission"]:
            print("System permission cannot be deactivated/activated.")
            return
        if row["status"] == status:
            print(f"Permission is already {status}.")
            return
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""
            UPDATE permissions SET status = ?, updated_at = ?
            WHERE permission_id = ? AND hotel_id = ?
        """, (status, now, permission_id, hotel_id))
        connection.commit()
        print(f"Permission {status} Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error changing permission status: {exc}")
    finally:
        connection.close()


def deactivate_permission():
    _set_permission_status("Inactive")


def activate_permission():
    _set_permission_status("Active")


def get_permission(permission_id):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        return connection.execute("""
            SELECT permission_id, module_name, action_name, permission_name, status
            FROM permissions
            WHERE permission_id = ? AND hotel_id = ?
        """, (permission_id.strip().upper(), hotel_id)).fetchone()
    finally:
        connection.close()


def has_permission(user_id, module_name, action_name):
    """Resolve permission through the user's active roles.

    The role_permissions table is introduced by 4.8.12. Until that table
    exists, Admin remains allowed so existing administration is not locked.
    Once role-permission assignments exist, normal users are evaluated from
    their active role assignments.
    """
    hotel_id = get_current_hotel_id()
    module_name = module_name.strip()
    action_name = action_name.strip()
    connection = get_connection()
    try:
        user = connection.execute("""
            SELECT user_id, role, status
            FROM users WHERE user_id = ? AND hotel_id = ?
        """, (user_id, hotel_id)).fetchone()
        if not user or user["status"] != "Active":
            return False

        if str(user["role"] or "").strip().lower() == "admin":
            return True

        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='role_permissions'"
        ).fetchone()
        if not tables:
            return False

        row = connection.execute("""
            SELECT 1
            FROM user_role_assignments ura
            JOIN roles r
              ON r.hotel_id = ura.hotel_id
             AND r.role_id = ura.role_id
             AND r.status = 'Active'
            JOIN role_permissions rp
              ON rp.hotel_id = ura.hotel_id
             AND rp.role_id = ura.role_id
             AND rp.status = 'Active'
            JOIN permissions p
              ON p.hotel_id = rp.hotel_id
             AND p.permission_id = rp.permission_id
             AND p.status = 'Active'
            WHERE ura.hotel_id = ?
              AND ura.user_id = ?
              AND ura.assignment_status = 'Active'
              AND lower(p.module_name) = lower(?)
              AND lower(p.action_name) = lower(?)
            LIMIT 1
        """, (hotel_id, user_id, module_name, action_name)).fetchone()
        return row is not None
    finally:
        connection.close()


def get_user_permissions(user_id):
    """Return active permission records assigned through the user's active roles."""
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        user = connection.execute(
            "SELECT user_id, role, status FROM users WHERE user_id=? AND hotel_id=?",
            (user_id, hotel_id),
        ).fetchone()
        if not user or user["status"] != "Active":
            return []
        if str(user["role"] or "").strip().lower() == "admin":
            rows = connection.execute("""
                SELECT permission_id, module_name, action_name, permission_name
                FROM permissions WHERE hotel_id=? AND status='Active'
                ORDER BY module_name, action_name
            """, (hotel_id,)).fetchall()
            return rows
        rows = connection.execute("""
            SELECT DISTINCT p.permission_id, p.module_name, p.action_name, p.permission_name
            FROM user_role_assignments ura
            JOIN roles r ON r.hotel_id=ura.hotel_id AND r.role_id=ura.role_id AND r.status='Active'
            JOIN role_permissions rp ON rp.hotel_id=ura.hotel_id AND rp.role_id=ura.role_id AND rp.status='Active'
            JOIN permissions p ON p.hotel_id=rp.hotel_id AND p.permission_id=rp.permission_id AND p.status='Active'
            WHERE ura.hotel_id=? AND ura.user_id=? AND ura.assignment_status='Active'
            ORDER BY p.module_name, p.action_name
        """, (hotel_id, user_id)).fetchall()
        return rows
    finally:
        connection.close()

def require_permission(user_id, module_name, action_name):
    if not has_permission(user_id, module_name, action_name):
        raise PermissionError(
            f"Permission denied: {module_name} - {action_name}."
        )
    return True


SYSTEM_ROLE_PERMISSION_MAP = {
    "Admin": "ALL",
    "Manager": {
        "Hotel": {"View", "Update"},
        "Rooms": set(PERMISSION_ACTIONS),
        "Restaurant": set(PERMISSION_ACTIONS),
        "Tables": set(PERMISSION_ACTIONS),
        "Customers": set(PERMISSION_ACTIONS),
        "Staff": {"View", "Create", "Update", "Reports"},
        "Attendance": {"View", "Create", "Update", "Reports"},
        "Leave": {"View", "Approve"},
        "Salary": {"View", "Reports"},
        "Payroll": {"View", "Create", "Update", "Reports"},
        "Inventory": set(PERMISSION_ACTIONS),
        "Expenses": set(PERMISSION_ACTIONS),
        "Reports": {"View", "Reports"},
        "Settings": {"View", "Update"},
    },
    "Reception": {
        "Hotel": {"View"}, "Rooms": set(PERMISSION_ACTIONS),
        "Tables": set(PERMISSION_ACTIONS), "Customers": set(PERMISSION_ACTIONS),
        "Restaurant": {"View", "Create", "Update", "Payment", "Cancel"},
    },
    "HR": {
        "Hotel": {"View"}, "Staff": set(PERMISSION_ACTIONS),
        "Attendance": set(PERMISSION_ACTIONS), "Leave": set(PERMISSION_ACTIONS),
        "Salary": set(PERMISSION_ACTIONS),
        "Payroll": set(PERMISSION_ACTIONS), "Reports": {"View", "Reports"},
        "Users": {"View", "Create", "Update", "Approve"},
    },
    "Restaurant Staff": {
        "Hotel": {"View"}, "Restaurant": set(PERMISSION_ACTIONS),
        "Tables": {"View", "Update", "Create", "Cancel"}, "Customers": {"View", "Create", "Update"},
    },
    "Accountant": {
        "Hotel": {"View"}, "Restaurant": {"View", "Payment", "Refund", "Reports"},
        "Rooms": {"View", "Payment", "Reports"}, "Tables": {"View", "Reports"},
        "Salary": {"View", "Reports"}, "Payroll": set(PERMISSION_ACTIONS),
        "Expenses": set(PERMISSION_ACTIONS), "Reports": {"View", "Reports"},
    },
    "Housekeeping": {
        "Hotel": {"View"}, "Rooms": {"View", "Update"}, "Tables": {"View", "Update"},
    },
}


def create_role_permissions_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_permissions(
                role_permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                role_id TEXT NOT NULL,
                permission_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Active',
                assigned_at TEXT NOT NULL,
                removed_at TEXT,
                UNIQUE(hotel_id, role_id, permission_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_role_permissions_role
            ON role_permissions(hotel_id, role_id, status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_role_permissions_permission
            ON role_permissions(hotel_id, permission_id, status)
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_permission_history(
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                role_id TEXT NOT NULL,
                permission_id TEXT NOT NULL,
                action TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                reason TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_role_permission_history_role
            ON role_permission_history(hotel_id, role_id)
        """)

        # Seed safe defaults only where no assignment exists yet. Admin is
        # always full-access through has_permission(), while the other
        # system roles receive practical least-privilege defaults.
        roles = cursor.execute("""
            SELECT role_id, role_name FROM roles
            WHERE hotel_id = ? AND status = 'Active'
        """, (get_current_hotel_id(),)).fetchall()
        hotel_id = get_current_hotel_id()
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        for role in roles:
            if cursor.execute("SELECT 1 FROM role_permissions WHERE hotel_id=? AND role_id=? LIMIT 1", (hotel_id, role["role_id"])).fetchone():
                continue
            mapping = SYSTEM_ROLE_PERMISSION_MAP.get(role["role_name"], {})
            if mapping == "ALL":
                permissions = cursor.execute("SELECT permission_id FROM permissions WHERE hotel_id=? AND status='Active'", (hotel_id,)).fetchall()
                permission_ids = [r["permission_id"] for r in permissions]
            else:
                permission_ids = []
                for module, actions in mapping.items():
                    for action in actions:
                        row = cursor.execute("""
                            SELECT permission_id FROM permissions
                            WHERE hotel_id=? AND lower(module_name)=lower(?)
                              AND lower(action_name)=lower(?) AND status='Active'
                        """, (hotel_id, module, action)).fetchone()
                        if row:
                            permission_ids.append(row["permission_id"])
            for permission_id in permission_ids:
                cursor.execute("""
                    INSERT OR IGNORE INTO role_permissions
                    (hotel_id, role_id, permission_id, status, assigned_at)
                    VALUES(?, ?, ?, 'Active', ?)
                """, (hotel_id, role["role_id"], permission_id, now))
        connection.commit()
    finally:
        connection.close()


def _role_permission_role(cursor, role_id, hotel_id):
    return cursor.execute("""
        SELECT role_id, role_name, status, is_system_role
        FROM roles WHERE role_id=? AND hotel_id=?
    """, (role_id, hotel_id)).fetchone()


def assign_permission_to_role(reason=None):
    require_hr_authorization("permission_change")

    hotel_id = get_current_hotel_id()
    if reason is not None and not str(reason).strip():
        raise ValueError("Reason is required for permission change.")
    role_id = input("Role ID : ").strip().upper()
    permission_id = input("Permission ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        role = _role_permission_role(cursor, role_id, hotel_id)
        permission = cursor.execute("""
            SELECT permission_id, permission_name, status, is_system_permission
            FROM permissions WHERE permission_id=? AND hotel_id=?
        """, (permission_id, hotel_id)).fetchone()
        if not role:
            print("Role Not Found.")
            return
        if role["status"] != "Active":
            print("Inactive role cannot receive permissions.")
            return
        if not permission:
            print("Permission Not Found.")
            return
        if permission["status"] != "Active":
            print("Inactive permission cannot be assigned.")
            return
        if cursor.execute("""
            SELECT 1 FROM role_permissions
            WHERE hotel_id=? AND role_id=? AND permission_id=? AND status='Active'
        """, (hotel_id, role_id, permission_id)).fetchone():
            print("Permission is already assigned to this role.")
            return
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""
            INSERT INTO role_permissions
            (hotel_id, role_id, permission_id, status, assigned_at, removed_at)
            VALUES(?, ?, ?, 'Active', ?, NULL)
            ON CONFLICT(hotel_id, role_id, permission_id) DO UPDATE SET
                status='Active', assigned_at=excluded.assigned_at, removed_at=NULL
        """, (hotel_id, role_id, permission_id, now))
        cursor.execute("""
            INSERT INTO role_permission_history
            (hotel_id, role_id, permission_id, action, changed_at, reason)
            VALUES(?, ?, ?, 'ASSIGNED', ?, 'Permission assigned to role')
        """, (hotel_id, role_id, permission_id, now))
        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="PERMISSION_ASSIGNED",
            target_type="ROLE_PERMISSION",
            target_id=f"{role_id}:{permission_id}",
            old_value=None,
            new_value={
                "role_id": role_id,
                "permission_id": permission_id,
                "permission_name": permission["permission_name"],
            },
            reason=reason or "Permission assigned to role.",
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Permission",
        action="UPDATE",
        local_values=locals(),
        details="Business operation assign_permission_to_role completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Permission Assigned to Role Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error assigning permission: {exc}")
    finally:
        connection.close()


def remove_permission_from_role(reason=None):
    require_hr_authorization("permission_change")

    hotel_id = get_current_hotel_id()
    if reason is not None and not str(reason).strip():
        raise ValueError("Reason is required for permission change.")
    role_id = input("Role ID : ").strip().upper()
    permission_id = input("Permission ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        role = _role_permission_role(cursor, role_id, hotel_id)
        if not role:
            print("Role Not Found.")
            return
        if role["role_name"].strip().lower() == "admin" or role["is_system_role"] and role["role_name"].strip().lower() == "admin":
            print("Admin role permission protection is enabled. Admin access cannot be removed.")
            return
        assignment = cursor.execute("""
            SELECT 1 FROM role_permissions
            WHERE hotel_id=? AND role_id=? AND permission_id=? AND status='Active'
        """, (hotel_id, role_id, permission_id)).fetchone()
        if not assignment:
            print("Active role-permission assignment not found.")
            return
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""
            UPDATE role_permissions SET status='Inactive', removed_at=?
            WHERE hotel_id=? AND role_id=? AND permission_id=?
        """, (now, hotel_id, role_id, permission_id))
        cursor.execute("""
            INSERT INTO role_permission_history
            (hotel_id, role_id, permission_id, action, changed_at, reason)
            VALUES(?, ?, ?, 'REMOVED', ?, 'Permission removed from role')
        """, (hotel_id, role_id, permission_id, now))
        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="PERMISSION_REMOVED",
            target_type="ROLE_PERMISSION",
            target_id=f"{role_id}:{permission_id}",
            old_value={"role_id": role_id, "permission_id": permission_id},
            new_value=None,
            reason=reason or "Permission removed from role.",
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Permission",
        action="CREATE",
        local_values=locals(),
        details="Business operation remove_permission_from_role completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Permission Removed from Role Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error removing permission: {exc}")
    finally:
        connection.close()


def view_role_permissions():
    hotel_id = get_current_hotel_id()
    role_id = input("Role ID : ").strip().upper()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT r.role_name, p.permission_id, p.permission_name,
                   rp.status, rp.assigned_at, rp.removed_at
            FROM role_permissions rp
            JOIN roles r ON r.role_id=rp.role_id AND r.hotel_id=rp.hotel_id
            JOIN permissions p ON p.permission_id=rp.permission_id AND p.hotel_id=rp.hotel_id
            WHERE rp.hotel_id=? AND rp.role_id=?
            ORDER BY p.module_name, p.action_name
        """, (hotel_id, role_id)).fetchall()
    finally:
        connection.close()
    if not rows:
        print("No role-permission assignments found.")
        return
    print("=" * 72)
    print(f"ROLE PERMISSIONS : {rows[0]['role_name']}")
    print("=" * 72)
    for row in rows:
        print(f"{row['permission_id']} | {row['permission_name']} | {row['status']}")


def view_permission_roles():
    hotel_id = get_current_hotel_id()
    permission_id = input("Permission ID : ").strip().upper()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT r.role_id, r.role_name, rp.status, rp.assigned_at
            FROM role_permissions rp
            JOIN roles r ON r.role_id=rp.role_id AND r.hotel_id=rp.hotel_id
            WHERE rp.hotel_id=? AND rp.permission_id=?
            ORDER BY r.role_name
        """, (hotel_id, permission_id)).fetchall()
    finally:
        connection.close()
    if not rows:
        print("No roles have this permission.")
        return
    for row in rows:
        print(f"{row['role_id']} | {row['role_name']} | {row['status']} | {row['assigned_at']}")


def view_role_permission_history():
    hotel_id = get_current_hotel_id()
    role_id = input("Role ID : ").strip().upper()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT p.permission_name, h.action, h.changed_at, h.reason
            FROM role_permission_history h
            JOIN permissions p ON p.permission_id=h.permission_id AND p.hotel_id=h.hotel_id
            WHERE h.hotel_id=? AND h.role_id=?
            ORDER BY h.history_id DESC
        """, (hotel_id, role_id)).fetchall()
    finally:
        connection.close()
    if not rows:
        print("No role-permission history found.")
        return
    for row in rows:
        print(f"{row['changed_at']} | {row['action']} | {row['permission_name']} | {row['reason']}")


def require_current_user_permission(module_name, action_name):
    from database.user_db import get_current_session
    session = get_current_session()
    if not session:
        raise PermissionError("Login required for this action.")
    return require_permission(session["user_id"], module_name, action_name)


HR_AUTHORIZATION_MAP = {
    "leave_approval": ("Leave", "Approve"),
    "salary_update": ("Salary", "Update"),
    "payroll_generation": ("Payroll", "Create"),
    "payroll_correction": ("Payroll", "Update"),
    "staff_status_change": ("Staff", "Update"),
    "user_creation": ("Users", "Create"),
    "role_assignment": ("Users", "Approve"),
    "permission_change": ("Users", "Update"),
}


def require_hr_authorization(operation):
    """Authorize a sensitive HR operation through the existing permission engine."""
    operation_key = str(operation or "").strip().lower()
    permission = HR_AUTHORIZATION_MAP.get(operation_key)
    if permission is None:
        raise ValueError(f"Unknown HR authorization operation: {operation}")

    module_name, action_name = permission
    return require_current_user_permission(module_name, action_name)
