import sqlite3
import os


DATABASE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "hotel.db"
)


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def initialize_database():

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
        create_table_bookings_table
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