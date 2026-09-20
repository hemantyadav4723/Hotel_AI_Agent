import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "hotel.db"
DEFAULT_DATABASE_BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


def _env_int(name: str, default: int, minimum: int = 1, maximum: int = 120000) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))

def _env_path(name: str, default: Path) -> str:
    raw = os.getenv(name, "").strip()
    return os.path.abspath(raw) if raw else str(default.resolve())


# Production deployments can point the application at a dedicated database
# volume without changing source code. Development keeps the historical path.
DATABASE_PATH = _env_path("HOTEL_DATABASE_PATH", DEFAULT_DATABASE_PATH)
DATABASE_BACKUP_DIR = _env_path("HOTEL_DATABASE_BACKUP_DIR", DEFAULT_DATABASE_BACKUP_DIR)
SQLITE_BUSY_TIMEOUT_MS = _env_int("SQLITE_BUSY_TIMEOUT_MS", 30000, 1000, 120000)
SQLITE_JOURNAL_MODE = os.getenv("SQLITE_JOURNAL_MODE", "WAL").strip().upper() or "WAL"
SQLITE_SYNCHRONOUS = os.getenv("SQLITE_SYNCHRONOUS", "NORMAL").strip().upper() or "NORMAL"
_ALLOWED_JOURNAL_MODES = {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}
_ALLOWED_SYNCHRONOUS = {"OFF", "NORMAL", "FULL", "EXTRA"}

if SQLITE_JOURNAL_MODE not in _ALLOWED_JOURNAL_MODES:
    raise ValueError(f"Unsupported SQLITE_JOURNAL_MODE: {SQLITE_JOURNAL_MODE}")
if SQLITE_SYNCHRONOUS not in _ALLOWED_SYNCHRONOUS:
    raise ValueError(f"Unsupported SQLITE_SYNCHRONOUS: {SQLITE_SYNCHRONOUS}")


def ensure_database_directories():
    """Create the configured database and backup directories if required."""
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(DATABASE_BACKUP_DIR).mkdir(parents=True, exist_ok=True)


def configure_database():
    """Apply persistent SQLite settings required by the production runtime."""
    ensure_database_directories()
    connection = sqlite3.connect(DATABASE_PATH, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        connection.execute(f"PRAGMA journal_mode = {SQLITE_JOURNAL_MODE}")
        connection.execute(f"PRAGMA synchronous = {SQLITE_SYNCHRONOUS}")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.commit()
    finally:
        connection.close()


def get_connection():
    ensure_database_directories()
    connection = sqlite3.connect(DATABASE_PATH, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute(f"PRAGMA synchronous = {SQLITE_SYNCHRONOUS}")
    connection.execute("PRAGMA temp_store = MEMORY")
    return connection


def initialize_database():
    # Configure the runtime before any schema creation/migration work.
    configure_database()

    from database.customer_db import (
        create_customers_table,
        create_guest_hotel_relationships_table
    )

    from database.staff_db import create_staff_table, create_staff_status_history_table

    from database.attendance_db import create_attendance_table
    from database.leave_db import create_leave_table

    from database.salary_db import create_salary_table

    from database.payroll_db import create_payroll_table

    from database.department_db import create_department_table
    from database.designation_db import create_designation_table

    from database.billing_invoice_db import create_billing_invoice_tables

    from database.order_db import (
        create_orders_table,
        create_restaurant_order_audit_table,
        create_restaurant_payment_transactions_table,
        migrate_restaurant_payment_transactions
    )
    from database.restaurant_menu_db import (
        create_restaurant_menu_tables,
        seed_default_restaurant_menu
    )

    from database.room_booking_db import (
        create_room_bookings_table,
        create_room_booking_allocations_table,
        migrate_room_bookings_schema,
        migrate_room_booking_customer_links,
        create_rooms_table,
        migrate_rooms_schema,
        insert_default_rooms,
        reconcile_room_statuses
    )

    from database.room_payment_db import (
        create_room_payment_tables,
        seed_room_reservation_advance_rules
    )

    from database.table_booking_db import (
        create_tables_table,
        insert_default_tables,
        create_table_bookings_table,
        ensure_table_assignments_table,
        ensure_table_merge_tables,
    )

    from database.expenses_db import create_expenses_table
    from database.expense_category_db import create_expense_categories_table

    from database.feedback_db import create_feedback_table
    from database.notification_db import create_notifications_tables
    from database.transportation_db import create_transportation_tables
    from database.maps_navigation_db import create_maps_navigation_tables
    from database.media_db import create_media_tables
    from database.audit_db import create_audit_log_table

    from database.user_db import create_users_table
    from database.role_db import create_roles_table
    from database.permission_db import create_permissions_table, create_role_permissions_table
    from database.hr_audit_db import create_hr_audit_table
    from database.hr_integrity_db import create_hr_integrity_guards

    from database.settings_db import create_settings_table, create_discount_rules_table
    from database.purchase_receiving_db import create_purchase_receiving_tables

    from database.inventory_db import (
        create_inventory_table,
        create_inventory_transactions_table,
        migrate_inventory_relationships
    )
    from database.inventory_category_db import create_inventory_categories_table
    from database.inventory_unit_db import create_inventory_units_table
    from database.inventory_batch_db import create_inventory_batches_table

    from database.supplier_db import create_supplier_table
    from database.purchase_order_db import create_purchase_order_tables
    from database.supplier_payment_terms_db import create_supplier_payment_terms_table
    from database.supplier_outstanding_db import create_supplier_outstanding_tables
    from database.procurement_integrity_db import create_procurement_integrity_guards
    from database.cleaning_db import create_cleaning_tasks_table, sync_existing_cleaning_tasks
    from database.guest_service_db import create_guest_service_requests_table

    from database.hotel_information_db import (
        create_hotels_table,
        initialize_hotel_master,
        create_hotel_information_table,
        initialize_hotel_information,
        migrate_hotel_information_configuration
    )

    # ========================================================
    # HOTEL MASTER
    # ========================================================
    # Hotel master must exist before any hotel-scoped
    # information is initialized.

    create_hotels_table()
    initialize_hotel_master()

    # ========================================================
    # CORE TABLES
    # ========================================================

    create_customers_table()
    create_guest_hotel_relationships_table()
    create_staff_table()
    create_staff_status_history_table()
    create_attendance_table()
    create_leave_table()
    create_salary_table()
    create_payroll_table()
    create_department_table()
    create_designation_table()
    create_billing_invoice_tables()
    create_orders_table()
    create_restaurant_order_audit_table()
    create_restaurant_payment_transactions_table()
    migrate_restaurant_payment_transactions()
    create_restaurant_menu_tables()
    seed_default_restaurant_menu()

    # ========================================================
    # ROOM / RESERVATION
    # ========================================================

    create_room_bookings_table()
    migrate_room_bookings_schema()
    migrate_room_booking_customer_links()
    create_room_booking_allocations_table()

    create_rooms_table()
    migrate_rooms_schema()
    insert_default_rooms()
    create_room_payment_tables()
    seed_room_reservation_advance_rules()

    # Audit infrastructure must exist before any initialization/business
    # operation that can emit audit activity (for example room reconciliation).
    create_audit_log_table()
    reconcile_room_statuses()

    # ========================================================
    # TABLE BOOKING
    # ========================================================

    create_tables_table()
    insert_default_tables()
    create_table_bookings_table()
    with get_connection() as connection:
        ensure_table_assignments_table(connection)
        ensure_table_merge_tables(connection)
        connection.commit()
    create_cleaning_tasks_table()
    sync_existing_cleaning_tasks()
    create_guest_service_requests_table()

    # ========================================================
    # OTHER MODULES
    # ========================================================

    create_expense_categories_table()
    create_expenses_table()

    create_feedback_table()
    create_notifications_tables()
    create_transportation_tables()
    create_maps_navigation_tables()
    create_media_tables()

    create_users_table()
    create_roles_table()
    create_permissions_table()
    create_role_permissions_table()
    create_hr_audit_table()
    create_hr_integrity_guards()

    # Optional first-admin bootstrap for fresh deployments. This is opt-in
    # through environment variables and is a no-op once a hotel has users.
    from database.user_db import bootstrap_admin_from_environment
    bootstrap_admin_from_environment()

    create_settings_table()
    create_discount_rules_table()

    create_supplier_table()
    create_purchase_order_tables()
    create_supplier_payment_terms_table()
    create_supplier_outstanding_tables()
    create_purchase_receiving_tables()

    create_inventory_table()
    create_inventory_categories_table()
    create_inventory_units_table()
    create_inventory_batches_table()
    create_inventory_transactions_table()
    migrate_inventory_relationships()
    create_procurement_integrity_guards()

    # ========================================================
    # HOTEL INFORMATION
    # ========================================================
    #
    # IMPORTANT:
    # Existing databases may contain an older
    # hotel_information schema without hotel_id.
    #
    # Therefore migration MUST happen before initialization.
    # Otherwise initialize_hotel_information() would execute
    # a query against a column that does not yet exist.
    # ========================================================

    create_hotel_information_table()

    migrate_hotel_information_configuration()

    initialize_hotel_information()

    # ========================================================
    # PHASE 5 DATABASE FOUNDATION
    # ========================================================
    # Initialize schema/version metadata after all business tables
    # and migrations are ready.
    from database.database_admin import ensure_database_foundation
    ensure_database_foundation()