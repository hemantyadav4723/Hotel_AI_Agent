from utils.error_logging import log_non_blocking_error
import hashlib
import secrets
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id


PASSWORD_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 200_000
USER_STATUSES = ("Active", "Inactive")

_current_session = None


def _hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{PASSWORD_SCHEME}${PBKDF2_ITERATIONS}${salt}${digest}"


def _verify_password(password, stored_password):
    if not stored_password:
        return False

    if not stored_password.startswith(f"{PASSWORD_SCHEME}$"):
        return secrets.compare_digest(password, stored_password)

    try:
        scheme, iterations, salt, expected = stored_password.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return secrets.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def _ensure_column(cursor, table, column, definition):
    columns = {row["name"] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def create_users_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                staff_id TEXT,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT,
                updated_at TEXT
            )
        """)

        _ensure_column(cursor, "users", "hotel_id", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(cursor, "users", "staff_id", "TEXT")
        _ensure_column(cursor, "users", "status", "TEXT NOT NULL DEFAULT 'Active'")
        _ensure_column(cursor, "users", "created_at", "TEXT")
        _ensure_column(cursor, "users", "updated_at", "TEXT")

        cursor.execute("UPDATE users SET hotel_id = 1 WHERE hotel_id IS NULL")
        cursor.execute("UPDATE users SET status = 'Active' WHERE status IS NULL OR TRIM(status) = ''")
        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("UPDATE users SET created_at = ? WHERE created_at IS NULL OR TRIM(created_at) = ''", (now,))
        cursor.execute("UPDATE users SET updated_at = COALESCE(updated_at, created_at)", ())

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_hotel_id ON users(hotel_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_staff_id ON users(hotel_id, staff_id)")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_users_hotel_staff
            ON users(hotel_id, staff_id)
            WHERE staff_id IS NOT NULL AND TRIM(staff_id) <> ''
        """)
        connection.commit()
    finally:
        connection.close()


def _get_staff(cursor, staff_id, hotel_id):
    cursor.execute(
        """
        SELECT staff_id, staff_name, status
        FROM staff
        WHERE staff_id = ? AND hotel_id = ?
        """,
        (staff_id, hotel_id),
    )
    return cursor.fetchone()


def save_user(user_id, username, password, role, staff_id=None, reason=None):
    hotel_id = get_current_hotel_id()
    if reason is not None and not str(reason).strip():
        raise ValueError("Reason is required for user creation.")

    # Allow a one-time first-admin bootstrap when the current hotel has no
    # users yet. After the first user exists, every user creation requires
    # the normal HR authorization path.
    connection = get_connection()
    try:
        existing_user = connection.execute(
            "SELECT 1 FROM users WHERE hotel_id = ? LIMIT 1",
            (hotel_id,),
        ).fetchone()
    finally:
        connection.close()

    if existing_user is not None or str(role or "").strip().lower() != "admin":
        from database.permission_db import require_hr_authorization
        require_hr_authorization("user_creation")
    user_id = user_id.strip().upper()
    username = username.strip()
    role = role.strip().title()
    staff_id = staff_id.strip().upper() if staff_id else None

    if not user_id:
        raise ValueError("User ID cannot be empty.")
    if not username:
        raise ValueError("Username cannot be empty.")
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    role_row = None
    role_connection = get_connection()
    try:
        role_row = role_connection.execute(
            "SELECT role_id, role_name FROM roles WHERE hotel_id = ? AND lower(trim(role_name)) = lower(trim(?)) AND status = 'Active'",
            (hotel_id, role),
        ).fetchone()
    finally:
        role_connection.close()
    if not role_row:
        raise ValueError("Selected role is not active in the current hotel.")
    role = role_row["role_name"]

    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            raise ValueError("User ID already exists.")

        cursor.execute("SELECT 1 FROM users WHERE lower(username) = lower(?)", (username,))
        if cursor.fetchone():
            raise ValueError("Username already exists.")

        if staff_id:
            staff = _get_staff(cursor, staff_id, hotel_id)
            if not staff:
                raise ValueError("Staff Not Found in the current hotel.")
            if staff["status"] not in {"New", "Active"}:
                raise ValueError("Only New or Active staff can be linked to a user.")

            cursor.execute(
                "SELECT 1 FROM users WHERE hotel_id = ? AND staff_id = ?",
                (hotel_id, staff_id),
            )
            if cursor.fetchone():
                raise ValueError("This staff member already has a login user.")

        now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
        cursor.execute("""
            INSERT INTO users(
                user_id, username, password, role, hotel_id, staff_id,
                status, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, 'Active', ?, ?)
        """, (
            user_id,
            username,
            _hash_password(password),
            role,
            hotel_id,
            staff_id,
            now,
            now,
        ))

        # Keep the normalized role-assignment architecture synchronized
        # immediately for newly created users. This prevents an authorization
        # gap between user creation and the next application restart.
        cursor.execute("""
            INSERT OR IGNORE INTO user_role_assignments(
                hotel_id, user_id, role_id, assigned_at, assignment_status
            )
            VALUES(?, ?, ?, ?, 'Active')
        """, (hotel_id, user_id, role_row["role_id"], now))

        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="USER_CREATED",
            target_type="USER",
            target_id=user_id,
            old_value=None,
            new_value={
                "username": username,
                "role": role,
                "staff_id": staff_id,
                "status": "Active",
            },
            reason=reason or "User created.",
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def view_users():
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT u.user_id, u.username, u.role, u.staff_id, u.status,
                   s.staff_name
            FROM users u
            LEFT JOIN staff s
              ON s.staff_id = u.staff_id AND s.hotel_id = u.hotel_id
            WHERE u.hotel_id = ?
            ORDER BY u.user_id
        """, (hotel_id,))
        users = cursor.fetchall()
    finally:
        connection.close()

    print("=" * 60)
    print("              USERS LIST")
    print("=" * 60)
    if not users:
        print("No Users Found.")
        return

    for user in users:
        print(f"User ID    : {user['user_id']}")
        print(f"Username   : {user['username']}")
        print(f"Role       : {user['role']}")
        print(f"Staff ID   : {user['staff_id'] or '-'}")
        print(f"Staff Name : {user['staff_name'] or '-'}")
        print(f"Status     : {user['status']}")
        print("-" * 60)


def _change_user_status(new_status, title):
    hotel_id = get_current_hotel_id()
    print("=" * 60)
    print(f"              {title}")
    print("=" * 60)
    user_id = input("Enter User ID : ").strip().upper()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT user_id, username, status FROM users WHERE user_id = ? AND hotel_id = ?",
            (user_id, hotel_id),
        )
        user = cursor.fetchone()
        if not user:
            print("User Not Found.")
            return
        if user["status"] == new_status:
            print(f"User is already {new_status}.")
            return

        cursor.execute(
            "UPDATE users SET status = ?, updated_at = ? WHERE user_id = ? AND hotel_id = ?",
            (new_status, datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"), user_id, hotel_id),
        )
        from database.hr_audit_db import log_hr_activity
        log_hr_activity(
            connection,
            action="USER_STATUS_CHANGED",
            target_type="USER",
            target_id=user_id,
            old_value={"status": user["status"]},
            new_value={"status": new_status},
            reason=f"User status changed to {new_status}.",
        )
        connection.commit()
        if new_status == "Inactive":
            _clear_session_if_user(user_id)
        print(f"User {new_status} Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error changing user status: {exc}")
    finally:
        connection.close()


def deactivate_user():
    _change_user_status("Inactive", "DEACTIVATE USER")


def activate_user():
    _change_user_status("Active", "ACTIVATE USER")


def delete_user():
    hotel_id = get_current_hotel_id()
    print("=" * 60)
    print("             DELETE USER")
    print("=" * 60)
    user_id = input("Enter User ID : ").strip().upper()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT status, staff_id FROM users WHERE user_id = ? AND hotel_id = ?",
            (user_id, hotel_id),
        )
        user = cursor.fetchone()
        if not user:
            print("User Not Found.")
            return
        if _current_session and _current_session.get("user_id") == user_id:
            print("Active logged-in user cannot be deleted. Logout first.")
            return
        if user["status"] != "Inactive":
            print("Only Inactive users can be deleted. Deactivate the user first.")
            return
        if user["staff_id"]:
            print("Staff-linked users cannot be deleted. Preserve the staff ↔ user relationship.")
            return

        cursor.execute(
            "DELETE FROM users WHERE user_id = ? AND hotel_id = ?",
            (user_id, hotel_id),
        )
        connection.commit()
        print("User Deleted Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error deleting user: {exc}")
    finally:
        connection.close()



def view_staff_user_link():
    """Show the login user linked to a staff member in the current hotel."""
    hotel_id = get_current_hotel_id()
    staff_id = input("Staff ID : ").strip().upper()
    connection = get_connection()
    try:
        row = connection.execute("""
            SELECT s.staff_id, s.staff_name, s.status AS staff_status,
                   u.user_id, u.username, u.status AS user_status, u.role
            FROM staff s
            LEFT JOIN users u
              ON u.staff_id = s.staff_id AND u.hotel_id = s.hotel_id
            WHERE s.staff_id = ? AND s.hotel_id = ?
        """, (staff_id, hotel_id)).fetchone()
    finally:
        connection.close()

    if not row:
        print("Staff Not Found.")
        return

    print("=" * 60)
    print("           STAFF ↔ USER LINK")
    print("=" * 60)
    print(f"Staff ID     : {row['staff_id']}")
    print(f"Staff Name   : {row['staff_name']}")
    print(f"Staff Status : {row['staff_status']}")
    print(f"User ID      : {row['user_id'] or '-'}")
    print(f"Username     : {row['username'] or '-'}")
    print(f"User Status  : {row['user_status'] or '-'}")
    print(f"Role         : {row['role'] or '-'}")


def link_staff_to_user():
    """Link an existing eligible user to one staff member."""
    hotel_id = get_current_hotel_id()
    user_id = input("User ID : ").strip().upper()
    staff_id = input("Staff ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        user = cursor.execute("""
            SELECT user_id, username, status, staff_id
            FROM users
            WHERE user_id = ? AND hotel_id = ?
        """, (user_id, hotel_id)).fetchone()
        if not user:
            print("User Not Found.")
            return
        if user["status"] != "Active":
            print("Only Active users can be linked to staff.")
            return
        if user["staff_id"]:
            print("This user is already linked to a staff member.")
            return

        staff = cursor.execute("""
            SELECT staff_id, staff_name, status
            FROM staff
            WHERE staff_id = ? AND hotel_id = ?
        """, (staff_id, hotel_id)).fetchone()
        if not staff:
            print("Staff Not Found.")
            return
        if staff["status"] not in {"New", "Active"}:
            print("Only New or Active staff can be linked to a user.")
            return

        existing = cursor.execute("""
            SELECT user_id, username
            FROM users
            WHERE hotel_id = ? AND staff_id = ?
        """, (hotel_id, staff_id)).fetchone()
        if existing:
            print(f"Staff already has a login user: {existing['username']} ({existing['user_id']}).")
            return

        cursor.execute(
            "UPDATE users SET staff_id = ?, updated_at = ? WHERE user_id = ? AND hotel_id = ?",
            (staff_id, datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"), user_id, hotel_id),
        )
        connection.commit()
        print("Staff ↔ User Link Created Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error linking staff and user: {exc}")
    finally:
        connection.close()


def unlink_staff_from_user():
    """Safely remove a staff ↔ user link before a user deletion."""
    hotel_id = get_current_hotel_id()
    user_id = input("User ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        user = cursor.execute("""
            SELECT user_id, username, status, staff_id
            FROM users
            WHERE user_id = ? AND hotel_id = ?
        """, (user_id, hotel_id)).fetchone()
        if not user:
            print("User Not Found.")
            return
        if not user["staff_id"]:
            print("This user is not linked to any staff member.")
            return
        if _current_session and _current_session.get("user_id") == user_id:
            print("Active logged-in user cannot be unlinked. Logout first.")
            return
        if user["status"] != "Inactive":
            print("Deactivate the user before unlinking the staff relationship.")
            return

        cursor.execute(
            "UPDATE users SET staff_id = NULL, updated_at = ? WHERE user_id = ? AND hotel_id = ?",
            (datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"), user_id, hotel_id),
        )
        connection.commit()
        print("Staff ↔ User Link Removed Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error unlinking staff and user: {exc}")
    finally:
        connection.close()

def change_password():
    hotel_id = get_current_hotel_id()
    print("=" * 60)
    print("            CHANGE PASSWORD")
    print("=" * 60)
    username = input("Username : ").strip()
    current_password = input("Current Password : ")
    new_password = input("New Password : ")
    confirm_password = input("Confirm New Password : ")

    if len(new_password) < 8:
        print("Password must contain at least 8 characters.")
        return
    if new_password != confirm_password:
        print("New passwords do not match.")
        return

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT user_id, password, status FROM users WHERE lower(username) = lower(?) AND hotel_id = ?",
            (username, hotel_id),
        )
        user = cursor.fetchone()
        if not user or user["status"] != "Active":
            print("Invalid or inactive user.")
            return
        if not _verify_password(current_password, user["password"]):
            print("Current password is incorrect.")
            return

        cursor.execute(
            "UPDATE users SET password = ?, updated_at = ? WHERE user_id = ? AND hotel_id = ?",
            (_hash_password(new_password), datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"), user["user_id"], hotel_id),
        )
        connection.commit()
        print("Password Changed Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error changing password: {exc}")
    finally:
        connection.close()


def reset_password():
    hotel_id = get_current_hotel_id()
    print("=" * 60)
    print("             RESET PASSWORD")
    print("=" * 60)
    user_id = input("User ID : ").strip().upper()
    new_password = input("New Password : ")
    confirm_password = input("Confirm New Password : ")

    if len(new_password) < 8:
        print("Password must contain at least 8 characters.")
        return
    if new_password != confirm_password:
        print("New passwords do not match.")
        return

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT user_id, status FROM users WHERE user_id = ? AND hotel_id = ?",
            (user_id, hotel_id),
        )
        user = cursor.fetchone()
        if not user:
            print("User Not Found.")
            return

        cursor.execute(
            "UPDATE users SET password = ?, status = 'Active', updated_at = ? WHERE user_id = ? AND hotel_id = ?",
            (_hash_password(new_password), datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"), user_id, hotel_id),
        )
        connection.commit()
        print("Password Reset Successfully.")
    except Exception as exc:
        connection.rollback()
        print(f"Error resetting password: {exc}")
    finally:
        connection.close()


def login_user(username, password):
    global _current_session
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT u.user_id, u.username, u.password, u.role, u.hotel_id,
                   u.staff_id, u.status, s.staff_name, s.status AS staff_status
            FROM users u
            LEFT JOIN staff s
              ON s.staff_id = u.staff_id AND s.hotel_id = u.hotel_id
            WHERE lower(u.username) = lower(?)
              AND u.hotel_id = ?
        """, (username.strip(), hotel_id))
        user = cursor.fetchone()

        if not user or user["status"] != "Active" or not _verify_password(password, user["password"]):
            try:
                from database.audit_db import log_activity
                log_activity(
                    module="Login",
                    action="LOGIN",
                    status="FAILED",
                    details=f"Failed login attempt for username: {username.strip()}",
                    actor_username=username.strip(),
                    hotel_id=hotel_id,
                )
            except Exception as exc:
                log_non_blocking_error("Non-blocking optional operation failed", exc)
            print("Invalid Username or Password.")
            return False

        if user["staff_id"] and user["staff_status"] not in {"New", "Active"}:
            print("Login blocked because linked staff is not Active/New.")
            return False

        if not user["password"].startswith(f"{PASSWORD_SCHEME}$"):
            cursor.execute(
                "UPDATE users SET password = ?, updated_at = ? WHERE user_id = ? AND hotel_id = ?",
                (_hash_password(password), datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"), user["user_id"], hotel_id),
            )
            connection.commit()

        _current_session = {
            "user_id": user["user_id"],
            "username": user["username"],
            "role": user["role"],
            "hotel_id": user["hotel_id"],
            "staff_id": user["staff_id"],
            "staff_name": user["staff_name"],
            "login_at": datetime.now().strftime("%d-%m-%Y %I:%M:%S %p"),
        }
        try:
            from database.audit_db import log_activity
            log_activity(
                module="Login",
                action="LOGIN",
                status="SUCCESS",
                details="User login successful.",
                actor_user_id=user["user_id"],
                actor_username=user["username"],
                actor_role=user["role"],
                hotel_id=hotel_id,
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        print(f"Welcome {user['username']} ({user['role']})")
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def verify_login(username, password):
    return login_user(username, password)


def logout_user():
    global _current_session
    if _current_session is None:
        print("No active login session.")
        return False
    session = dict(_current_session)
    username = session.get("username")
    try:
        from database.audit_db import log_activity
        log_activity(
            module="Login",
            action="LOGOUT",
            status="SUCCESS",
            details="User logout successful.",
            actor_user_id=session.get("user_id"),
            actor_username=username,
            actor_role=session.get("role"),
            hotel_id=session.get("hotel_id"),
        )
    except Exception as exc:
        log_non_blocking_error("Non-blocking optional operation failed", exc)
    _current_session = None
    print(f"{username} logged out successfully.")
    return True


def get_current_session():
    return dict(_current_session) if _current_session else None


def verify_current_session_password(password):
    """Verify the password of the currently authenticated user.

    This is used for sensitive re-authentication flows. The username/user ID
    is taken from the live session rather than from user input, and the
    password is checked against the current-hotel user record.
    """
    session = get_current_session()
    if not session:
        return False

    hotel_id = get_current_hotel_id()
    user_id = session.get("user_id")
    if not user_id or session.get("hotel_id") != hotel_id:
        return False

    connection = get_connection()
    try:
        user = connection.execute(
            """
            SELECT password, status
            FROM users
            WHERE user_id = ? AND hotel_id = ?
            """,
            (user_id, hotel_id),
        ).fetchone()
        if not user or user["status"] != "Active":
            return False
        return _verify_password(password, user["password"])
    finally:
        connection.close()


def _clear_session_if_user(user_id):
    global _current_session
    if _current_session and _current_session.get("user_id") == user_id:
        _current_session = None
