from utils.error_logging import log_non_blocking_error
"""Enterprise SQLite administration and health utilities.

Phase 5 foundation:
- schema/version tracking
- integrity and foreign-key checks
- hotel-scope audit
- index/constraint readiness reporting
- legacy TXT dependency audit
- verified SQLite backup/restore
- non-destructive database health report
"""

from datetime import datetime
import os
import shutil
import sqlite3

from database.database import DATABASE_PATH, get_connection

SCHEMA_VERSION = "5.0.0"
SCHEMA_MIGRATION_KEY = "phase5_sqlite_foundation_v1"

EXPECTED_TABLES = (
    "attendance", "attendance_correction_history", "audit_activity_log",
    "cleaning_tasks", "customers", "department", "designation",
    "discount_rules", "expense_categories", "expenses", "feedback",
    "feedback_id_sequences", "guest_hotel_relationships", "hotel_information",
    "hotel_media", "hotels", "hr_audit_log", "inventory", "inventory_batches",
    "inventory_categories", "inventory_transactions", "inventory_units",
    "invoice_sequences", "invoices", "map_configurations", "navigation_routes",
    "nearby_places", "notification_channels", "notification_deliveries",
    "notification_events", "orders", "payroll", "payroll_correction_history",
    "permissions", "purchase_order_items", "purchase_orders",
    "purchase_receiving_items", "purchase_receivings", "restaurant_menu_categories",
    "restaurant_menu_items", "restaurant_order_audit",
    "restaurant_payment_transactions", "role_assignment_history",
    "role_permission_history", "role_permissions", "roles",
    "room_booking_allocations", "room_bookings", "room_extra_charges",
    "room_payment_transactions", "room_reservation_advance_rules", "rooms",
    "salary", "settings", "staff", "staff_leaves", "staff_status_history",
    "supplier_payment_terms", "supplier_payments", "suppliers", "table_assignments",
    "table_bookings", "table_merge_groups", "table_merge_members", "table_sections",
    "tables", "transportation_drivers", "transportation_requests",
    "transportation_vehicles", "user_role_assignments", "users",
)

# These are intentionally global/identity masters. All other business tables
# are expected to carry hotel_id for tenant isolation.
GLOBAL_TABLES = {"customers", "hotels", "notification_channels", "settings"}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_database_foundation():
    """Create Phase 5 metadata/backup registries idempotently."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS database_metadata(
                metadata_key TEXT PRIMARY KEY,
                metadata_value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS database_schema_migrations(
                migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_key TEXT NOT NULL UNIQUE,
                version TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS database_backup_history(
                backup_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                backup_path TEXT NOT NULL,
                backup_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                details TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_database_backup_history_time
            ON database_backup_history(created_at DESC, backup_id DESC)
        """)
        # Complete the remaining hotel-scope indexes identified during the
        # Phase 5 schema audit.
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_feedback_id_sequences_hotel ON feedback_id_sequences(hotel_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_hotel_information_hotel_id ON hotel_information(hotel_id)"
        )
        now = _now()
        cursor.execute("""
            INSERT INTO database_metadata(metadata_key, metadata_value, updated_at)
            VALUES('schema_version', ?, ?)
            ON CONFLICT(metadata_key) DO UPDATE SET
                metadata_value = excluded.metadata_value,
                updated_at = excluded.updated_at
        """, (SCHEMA_VERSION, now))
        cursor.execute("""
            INSERT OR IGNORE INTO database_schema_migrations(
                migration_key, version, applied_at
            ) VALUES(?, ?, ?)
        """, (SCHEMA_MIGRATION_KEY, SCHEMA_VERSION, now))
        connection.commit()
    finally:
        connection.close()


def _table_names(connection):
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row["name"] for row in rows}


def _index_names(connection):
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row["name"] for row in rows}


def run_database_health_check():
    """Return a complete, read-only health report for the current database."""
    connection = get_connection()
    try:
        tables = _table_names(connection)
        indexes = _index_names(connection)
        missing_tables = [t for t in EXPECTED_TABLES if t not in tables]

        missing_hotel_scope = []
        empty_hotel_scope = []
        for table in EXPECTED_TABLES:
            if table in GLOBAL_TABLES or table not in tables:
                continue
            columns = {
                row["name"] for row in connection.execute(
                    f'PRAGMA table_info("{table}")'
                ).fetchall()
            }
            if "hotel_id" not in columns:
                missing_hotel_scope.append(table)
            else:
                bad_count = connection.execute(
                    f'SELECT COUNT(*) AS n FROM "{table}" WHERE hotel_id IS NULL'
                ).fetchone()["n"]
                if bad_count:
                    empty_hotel_scope.append({"table": table, "null_hotel_id_rows": bad_count})

        fk_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

        index_hotel_gaps = []
        for table in EXPECTED_TABLES:
            if table in GLOBAL_TABLES or table not in tables:
                continue
            cols = [r["name"] for r in connection.execute(f'PRAGMA table_info("{table}")').fetchall()]
            if "hotel_id" not in cols:
                continue
            table_indexes = connection.execute(f'PRAGMA index_list("{table}")').fetchall()
            indexed = False
            for idx in table_indexes:
                idx_name = idx[1]
                idx_cols = [r[2] for r in connection.execute(f'PRAGMA index_info("{idx_name}")').fetchall()]
                if "hotel_id" in idx_cols:
                    indexed = True
                    break
            if not indexed:
                index_hotel_gaps.append(table)

        data_dir = os.path.dirname(DATABASE_PATH)
        legacy_txt_files = sorted(
            name for name in os.listdir(data_dir)
            if name.lower().endswith(".txt")
        ) if os.path.isdir(data_dir) else []

        version = connection.execute(
            "SELECT metadata_value FROM database_metadata WHERE metadata_key='schema_version'"
        ).fetchone()
        version_value = version["metadata_value"] if version else None

        return {
            "database_path": DATABASE_PATH,
            "database_exists": os.path.isfile(DATABASE_PATH),
            "database_size_bytes": os.path.getsize(DATABASE_PATH) if os.path.isfile(DATABASE_PATH) else 0,
            "schema_version": version_value,
            "expected_table_count": len(EXPECTED_TABLES),
            "actual_table_count": len(tables),
            "missing_tables": missing_tables,
            "hotel_scope_gaps": missing_hotel_scope,
            "null_hotel_id_rows": empty_hotel_scope,
            "hotel_index_gaps": index_hotel_gaps,
            "index_count": len(indexes),
            "integrity_check": integrity,
            "foreign_key_check_errors": [tuple(row) for row in fk_rows],
            "foreign_keys_enabled": bool(foreign_keys),
            "journal_mode": journal_mode,
            "busy_timeout_ms": busy_timeout,
            "legacy_txt_files": legacy_txt_files,
        }
    finally:
        connection.close()


def is_database_healthy(report=None):
    report = report or run_database_health_check()
    return (
        report["database_exists"]
        and report["schema_version"] == SCHEMA_VERSION
        and not report["missing_tables"]
        and not report["hotel_scope_gaps"]
        and not report["null_hotel_id_rows"]
        and not report["foreign_key_check_errors"]
        and report["integrity_check"] == "ok"
        and report["foreign_keys_enabled"]
    )


def _validate_sqlite_file(path):
    connection = sqlite3.connect(path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"SQLite integrity check failed: {integrity}")
        fk_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise ValueError(f"SQLite foreign-key check failed: {fk_errors[:3]}")
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing = [t for t in EXPECTED_TABLES if t not in tables]
        if missing:
            raise ValueError(f"Backup is missing required tables: {', '.join(missing[:8])}")
    finally:
        connection.close()


def backup_database(destination=None, backup_type="MANUAL"):
    """Create and verify a consistent SQLite backup using SQLite backup API."""
    if destination is None:
        backup_dir = os.path.join(os.path.dirname(DATABASE_PATH), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        destination = os.path.join(
            backup_dir,
            f"hotel_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
    destination = os.path.abspath(destination)
    source = os.path.abspath(DATABASE_PATH)
    if destination == source:
        raise ValueError("Backup destination cannot be the active database file.")
    os.makedirs(os.path.dirname(destination), exist_ok=True)

    temp = destination + ".tmp"
    try:
        if os.path.exists(temp):
            os.remove(temp)
        source_conn = sqlite3.connect(source)
        target_conn = sqlite3.connect(temp)
        try:
            source_conn.backup(target_conn)
            target_conn.commit()
        finally:
            target_conn.close()
            source_conn.close()
        _validate_sqlite_file(temp)
        os.replace(temp, destination)

        connection = get_connection()
        try:
            connection.execute(
                """INSERT INTO database_backup_history(
                    source_path, backup_path, backup_type, status, created_at, details
                ) VALUES(?, ?, ?, 'SUCCESS', ?, ?)""",
                (source, destination, backup_type, _now(), "Verified SQLite backup."),
            )
            connection.commit()
        finally:
            connection.close()
        return destination
    except Exception as exc:
        if os.path.exists(temp):
            os.remove(temp)
        try:
            connection = get_connection()
            connection.execute(
                """INSERT INTO database_backup_history(
                    source_path, backup_path, backup_type, status, created_at, details
                ) VALUES(?, ?, ?, 'FAILED', ?, ?)""",
                (source, destination, backup_type, _now(), str(exc)),
            )
            connection.commit()
            connection.close()
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        raise


def restore_database(backup_path):
    """Safely restore a verified backup, keeping a pre-restore backup first."""
    backup_path = os.path.abspath(str(backup_path).strip())
    source = os.path.abspath(DATABASE_PATH)
    if not os.path.isfile(backup_path):
        raise FileNotFoundError("Backup file was not found.")
    if backup_path == source:
        raise ValueError("Restore source cannot be the active database file.")

    _validate_sqlite_file(backup_path)
    pre_restore = backup_database(backup_type="PRE_RESTORE")
    temp = source + ".restore.tmp"
    try:
        if os.path.exists(temp):
            os.remove(temp)
        backup_conn = sqlite3.connect(backup_path)
        target_conn = sqlite3.connect(temp)
        try:
            backup_conn.backup(target_conn)
            target_conn.commit()
        finally:
            target_conn.close()
            backup_conn.close()
        _validate_sqlite_file(temp)
        os.replace(temp, source)
        connection = get_connection()
        try:
            connection.execute(
                """INSERT INTO database_backup_history(
                    source_path, backup_path, backup_type, status, created_at, details
                ) VALUES(?, ?, 'RESTORE', 'SUCCESS', ?, ?)""",
                (backup_path, pre_restore, _now(), "Restored verified backup; pre-restore backup retained."),
            )
            connection.commit()
        finally:
            connection.close()
        return pre_restore
    except Exception:
        if os.path.exists(temp):
            os.remove(temp)
        raise


def print_database_health_report(report=None):
    report = report or run_database_health_check()
    print("=" * 78)
    print("                    DATABASE HEALTH REPORT")
    print("=" * 78)
    print(f"Database       : {report['database_path']}")
    print(f"Schema Version : {report['schema_version'] or '-'}")
    print(f"Business Tables: {report['actual_table_count']} / {report['expected_table_count']}")
    print(f"Indexes        : {report['index_count']}")
    print(f"Integrity      : {report['integrity_check']}")
    print(f"Foreign Keys   : {'Enabled' if report['foreign_keys_enabled'] else 'Disabled'}")
    print(f"Journal Mode   : {report['journal_mode']}")
    print(f"Busy Timeout   : {report['busy_timeout_ms']} ms")
    print(f"Legacy TXT     : {len(report['legacy_txt_files'])}")
    print(f"Hotel Scope    : {'PASS' if not report['hotel_scope_gaps'] and not report['null_hotel_id_rows'] else 'CHECK'}")
    print(f"FK Check       : {'PASS' if not report['foreign_key_check_errors'] else 'CHECK'}")
    if report["missing_tables"]:
        print("Missing Tables : " + ", ".join(report["missing_tables"]))
    if report["hotel_scope_gaps"]:
        print("Hotel ID Gaps  : " + ", ".join(report["hotel_scope_gaps"]))
    if report["null_hotel_id_rows"]:
        print("NULL Hotel IDs : " + str(report["null_hotel_id_rows"]))
    if report["hotel_index_gaps"]:
        print("Index Gaps     : " + ", ".join(report["hotel_index_gaps"]))
    if report["legacy_txt_files"]:
        print("TXT Files      : " + ", ".join(report["legacy_txt_files"]))
    print("Overall Health : " + ("PASS" if is_database_healthy(report) else "CHECK REQUIRED"))
    print("=" * 78)


def database_management():
    """Restricted maintenance menu for administrators."""
    from database.user_db import get_current_session

    session = get_current_session()
    if not session or str(session.get("role", "")).strip().lower() != "admin":
        print("Database Management requires an active Admin login.")
        return

    while True:
        print("=" * 70)
        print("              DATABASE MANAGEMENT")
        print("=" * 70)
        print("1. Database Health Check")
        print("2. Schema / Migration Status")
        print("3. Create Verified Backup")
        print("4. Restore From Backup")
        print("5. Back")
        choice = input("Enter Choice : ").strip()

        try:
            if choice == "1":
                print_database_health_report()
            elif choice == "2":
                report = run_database_health_check()
                print(f"Schema Version : {report['schema_version'] or '-'}")
                print(f"Migration Key  : {SCHEMA_MIGRATION_KEY}")
                print(f"Integrity      : {report['integrity_check']}")
                print(f"Foreign Keys   : {'Enabled' if report['foreign_keys_enabled'] else 'Disabled'}")
            elif choice == "3":
                path = input("Backup path (Enter = default) : ").strip() or None
                print(f"Backup created: {backup_database(path)}")
            elif choice == "4":
                path = input("Verified backup file path : ").strip()
                if input("Restore this backup? (Y/N) : ").strip().upper() != "Y":
                    print("Restore cancelled.")
                else:
                    print(f"Pre-restore backup retained at: {restore_database(path)}")
                    print("Database restored successfully. Restart the application before continuing.")
            elif choice == "5":
                break
            else:
                print("Invalid Choice.")
        except Exception as exc:
            print(f"Database Error: {exc}")

        if choice != "5":
            input("\nPress Enter to continue...")
