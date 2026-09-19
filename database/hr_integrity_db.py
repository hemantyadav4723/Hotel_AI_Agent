"""
HR data-integrity and security guards.

This module contains SQLite triggers for cross-table integrity rules that
must remain enforced even when a future module writes directly through the
database layer.  It intentionally does not create a new data table.
"""

from database.database import get_connection


def create_hr_integrity_guards():
    """Create idempotent SQLite triggers for critical HR relationships."""
    connection = get_connection()
    try:
        cursor = connection.cursor()

        triggers = [
            # Staff must reference active department/designation belonging to
            # the same hotel. This prevents cross-hotel master-data links.
            """
            CREATE TRIGGER IF NOT EXISTS trg_staff_integrity_insert
            BEFORE INSERT ON staff
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM hotels WHERE hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Invalid hotel for staff.')
                    WHEN NOT EXISTS (
                        SELECT 1 FROM department
                        WHERE department_name = NEW.department
                          AND hotel_id = NEW.hotel_id
                          AND status = 'Active'
                    )
                    THEN RAISE(ABORT, 'Staff department must belong to the same hotel and be active.')
                    WHEN NOT EXISTS (
                        SELECT 1 FROM designation
                        WHERE designation_name = NEW.designation
                          AND hotel_id = NEW.hotel_id
                          AND status = 'Active'
                    )
                    THEN RAISE(ABORT, 'Staff designation must belong to the same hotel and be active.')
                END;
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_staff_integrity_update
            BEFORE UPDATE OF hotel_id, department, designation ON staff
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM hotels WHERE hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Invalid hotel for staff.')
                    WHEN NOT EXISTS (
                        SELECT 1 FROM department
                        WHERE department_name = NEW.department
                          AND hotel_id = NEW.hotel_id
                          AND status = 'Active'
                    )
                    THEN RAISE(ABORT, 'Staff department must belong to the same hotel and be active.')
                    WHEN NOT EXISTS (
                        SELECT 1 FROM designation
                        WHERE designation_name = NEW.designation
                          AND hotel_id = NEW.hotel_id
                          AND status = 'Active'
                    )
                    THEN RAISE(ABORT, 'Staff designation must belong to the same hotel and be active.')
                END;
            END;
            """,

            # Attendance must reference a staff record in the same hotel.
            """
            CREATE TRIGGER IF NOT EXISTS trg_attendance_staff_integrity_insert
            BEFORE INSERT ON attendance
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM staff
                        WHERE staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Attendance staff must belong to the same hotel.')
                END;
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_attendance_staff_integrity_update
            BEFORE UPDATE OF hotel_id, staff_id ON attendance
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM staff
                        WHERE staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Attendance staff must belong to the same hotel.')
                END;
            END;
            """,

            # Leave must reference same-hotel staff and valid date range.
            """
            CREATE TRIGGER IF NOT EXISTS trg_leave_integrity_insert
            BEFORE INSERT ON staff_leaves
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM staff
                        WHERE staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Leave staff must belong to the same hotel.')
                    WHEN NEW.end_date < NEW.start_date
                    THEN RAISE(ABORT, 'Leave end date cannot be before start date.')
                END;
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_leave_integrity_update
            BEFORE UPDATE OF hotel_id, staff_id, start_date, end_date ON staff_leaves
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM staff
                        WHERE staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Leave staff must belong to the same hotel.')
                    WHEN NEW.end_date < NEW.start_date
                    THEN RAISE(ABORT, 'Leave end date cannot be before start date.')
                END;
            END;
            """,

            # Salary must reference same-hotel staff and never contain
            # negative financial components.
            """
            CREATE TRIGGER IF NOT EXISTS trg_salary_integrity_insert
            BEFORE INSERT ON salary
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM staff
                        WHERE staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Salary staff must belong to the same hotel.')
                    WHEN NEW.basic_salary < 0
                      OR NEW.allowances < 0
                      OR NEW.bonus < 0
                      OR NEW.deduction < 0
                    THEN RAISE(ABORT, 'Salary values cannot be negative.')
                END;
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_salary_integrity_update
            BEFORE UPDATE OF hotel_id, staff_id, basic_salary, allowances, bonus, deduction ON salary
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM staff
                        WHERE staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Salary staff must belong to the same hotel.')
                    WHEN NEW.basic_salary < 0
                      OR NEW.allowances < 0
                      OR NEW.bonus < 0
                      OR NEW.deduction < 0
                    THEN RAISE(ABORT, 'Salary values cannot be negative.')
                END;
            END;
            """,

            # Payroll must reference same-hotel staff. If salary_id is present,
            # that salary must also belong to the same hotel and staff.
            """
            CREATE TRIGGER IF NOT EXISTS trg_payroll_integrity_insert
            BEFORE INSERT ON payroll
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM staff
                        WHERE staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Payroll staff must belong to the same hotel.')
                    WHEN NEW.salary_id IS NOT NULL
                     AND NOT EXISTS (
                        SELECT 1 FROM salary
                        WHERE salary_id = NEW.salary_id
                          AND staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Payroll salary reference must belong to the same staff and hotel.')
                END;
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_payroll_integrity_update
            BEFORE UPDATE OF hotel_id, staff_id, salary_id ON payroll
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM staff
                        WHERE staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Payroll staff must belong to the same hotel.')
                    WHEN NEW.salary_id IS NOT NULL
                     AND NOT EXISTS (
                        SELECT 1 FROM salary
                        WHERE salary_id = NEW.salary_id
                          AND staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Payroll salary reference must belong to the same staff and hotel.')
                END;
            END;
            """,

            # A staff-linked login must reference staff in the same hotel.
            """
            CREATE TRIGGER IF NOT EXISTS trg_user_staff_integrity_insert
            BEFORE INSERT ON users
            FOR EACH ROW
            WHEN NEW.staff_id IS NOT NULL AND TRIM(NEW.staff_id) <> ''
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM staff
                        WHERE staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'User staff link must belong to the same hotel.')
                END;
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_user_staff_integrity_update
            BEFORE UPDATE OF hotel_id, staff_id ON users
            FOR EACH ROW
            WHEN NEW.staff_id IS NOT NULL AND TRIM(NEW.staff_id) <> ''
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM staff
                        WHERE staff_id = NEW.staff_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'User staff link must belong to the same hotel.')
                END;
            END;
            """,

            # Role assignment must use same-hotel user and role.
            """
            CREATE TRIGGER IF NOT EXISTS trg_user_role_integrity_insert
            BEFORE INSERT ON user_role_assignments
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM users
                        WHERE user_id = NEW.user_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'User role assignment user must belong to the same hotel.')
                    WHEN NOT EXISTS (
                        SELECT 1 FROM roles
                        WHERE role_id = NEW.role_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'User role assignment role must belong to the same hotel.')
                END;
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_user_role_integrity_update
            BEFORE UPDATE OF hotel_id, user_id, role_id ON user_role_assignments
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM users
                        WHERE user_id = NEW.user_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'User role assignment user must belong to the same hotel.')
                    WHEN NOT EXISTS (
                        SELECT 1 FROM roles
                        WHERE role_id = NEW.role_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'User role assignment role must belong to the same hotel.')
                END;
            END;
            """,

            # Role-permission assignment must use same-hotel role and permission.
            """
            CREATE TRIGGER IF NOT EXISTS trg_role_permission_integrity_insert
            BEFORE INSERT ON role_permissions
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM roles
                        WHERE role_id = NEW.role_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Role permission role must belong to the same hotel.')
                    WHEN NOT EXISTS (
                        SELECT 1 FROM permissions
                        WHERE permission_id = NEW.permission_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Role permission must belong to the same hotel.')
                END;
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_role_permission_integrity_update
            BEFORE UPDATE OF hotel_id, role_id, permission_id ON role_permissions
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN NOT EXISTS (
                        SELECT 1 FROM roles
                        WHERE role_id = NEW.role_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Role permission role must belong to the same hotel.')
                    WHEN NOT EXISTS (
                        SELECT 1 FROM permissions
                        WHERE permission_id = NEW.permission_id
                          AND hotel_id = NEW.hotel_id
                    )
                    THEN RAISE(ABORT, 'Role permission must belong to the same hotel.')
                END;
            END;
            """,
        ]

        for trigger_sql in triggers:
            cursor.execute(trigger_sql)

        # Helpful indexes for the guarded relationship lookups. Existing
        # indexes are preserved; these are idempotent and inexpensive.
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_staff_hotel_department ON staff(hotel_id, department)",
            "CREATE INDEX IF NOT EXISTS idx_staff_hotel_designation ON staff(hotel_id, designation)",
            "CREATE INDEX IF NOT EXISTS idx_salary_hotel_staff ON salary(hotel_id, staff_id, salary_id)",
            "CREATE INDEX IF NOT EXISTS idx_attendance_hotel_staff ON attendance(hotel_id, staff_id, date)",
            "CREATE INDEX IF NOT EXISTS idx_leave_hotel_staff ON staff_leaves(hotel_id, staff_id, start_date, end_date)",
        ]
        for sql in indexes:
            cursor.execute(sql)

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def find_hr_integrity_issues():
    """Return existing HR orphan/integrity issues without modifying data."""
    connection = get_connection()
    try:
        checks = [
            (
                "STAFF_DEPARTMENT",
                """
                SELECT staff_id FROM staff s
                WHERE NOT EXISTS (
                    SELECT 1 FROM department d
                    WHERE d.hotel_id=s.hotel_id
                      AND d.department_name=s.department
                )
                """
            ),
            (
                "STAFF_DESIGNATION",
                """
                SELECT staff_id FROM staff s
                WHERE NOT EXISTS (
                    SELECT 1 FROM designation d
                    WHERE d.hotel_id=s.hotel_id
                      AND d.designation_name=s.designation
                )
                """
            ),
            (
                "ATTENDANCE_STAFF",
                """
                SELECT attendance_id FROM attendance a
                WHERE NOT EXISTS (
                    SELECT 1 FROM staff s
                    WHERE s.hotel_id=a.hotel_id AND s.staff_id=a.staff_id
                )
                """
            ),
            (
                "LEAVE_STAFF",
                """
                SELECT leave_id FROM staff_leaves l
                WHERE NOT EXISTS (
                    SELECT 1 FROM staff s
                    WHERE s.hotel_id=l.hotel_id AND s.staff_id=l.staff_id
                )
                """
            ),
            (
                "SALARY_STAFF",
                """
                SELECT salary_id FROM salary x
                WHERE NOT EXISTS (
                    SELECT 1 FROM staff s
                    WHERE s.hotel_id=x.hotel_id AND s.staff_id=x.staff_id
                )
                """
            ),
            (
                "PAYROLL_STAFF",
                """
                SELECT payroll_id FROM payroll p
                WHERE NOT EXISTS (
                    SELECT 1 FROM staff s
                    WHERE s.hotel_id=p.hotel_id AND s.staff_id=p.staff_id
                )
                """
            ),
            (
                "USER_STAFF",
                """
                SELECT user_id FROM users u
                WHERE u.staff_id IS NOT NULL
                  AND TRIM(u.staff_id) <> ''
                  AND NOT EXISTS (
                    SELECT 1 FROM staff s
                    WHERE s.hotel_id=u.hotel_id AND s.staff_id=u.staff_id
                  )
                """
            ),
            (
                "USER_ROLE",
                """
                SELECT assignment_id FROM user_role_assignments a
                WHERE NOT EXISTS (
                    SELECT 1 FROM users u
                    WHERE u.hotel_id=a.hotel_id AND u.user_id=a.user_id
                )
                OR NOT EXISTS (
                    SELECT 1 FROM roles r
                    WHERE r.hotel_id=a.hotel_id AND r.role_id=a.role_id
                )
                """
            ),
            (
                "ROLE_PERMISSION",
                """
                SELECT role_permission_id FROM role_permissions rp
                WHERE NOT EXISTS (
                    SELECT 1 FROM roles r
                    WHERE r.hotel_id=rp.hotel_id AND r.role_id=rp.role_id
                )
                OR NOT EXISTS (
                    SELECT 1 FROM permissions p
                    WHERE p.hotel_id=rp.hotel_id AND p.permission_id=rp.permission_id
                )
                """
            ),
        ]

        issues = []
        for category, sql in checks:
            rows = connection.execute(sql).fetchall()
            for row in rows:
                issues.append({"category": category, "record_id": row[0]})
        return issues
    finally:
        connection.close()
