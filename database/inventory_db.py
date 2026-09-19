from utils.error_logging import log_non_blocking_error
from datetime import datetime, timedelta
import sqlite3

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from utils.date_time import current_date


def _current_timestamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _require_inventory_permission(action):
    """Require the active session to have the requested Inventory permission."""
    from database.permission_db import require_current_user_permission
    return require_current_user_permission("Inventory", action)


EXPIRY_NEAR_DAYS = 30


def _normalize_expiry_date(value):
    """Validate and normalize an optional inventory expiry date."""
    if value is None:
        return None
    value = str(value).strip()
    if value == "":
        return None
    try:
        parsed = datetime.strptime(value, "%d-%m-%Y")
    except ValueError as exc:
        raise ValueError("Expiry Date must be in DD-MM-YYYY format.") from exc
    return parsed.strftime("%d-%m-%Y")


def get_expiry_status(expiry_date, today=None):
    """Return a derived, non-stored expiry status for an inventory item."""
    if not expiry_date:
        return "No Expiry Date"

    try:
        expiry = datetime.strptime(str(expiry_date), "%d-%m-%Y").date()
        today_date = datetime.strptime(
            today or current_date(), "%d-%m-%Y"
        ).date()
    except ValueError:
        return "Invalid Expiry Date"

    if expiry < today_date:
        return "Expired"
    if expiry <= today_date + timedelta(days=EXPIRY_NEAR_DAYS):
        return "Near Expiry"
    return "Valid"


def _table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row["name"] for row in cursor.fetchall()}


def _add_column(cursor, table_name, column_definition):
    column_name = column_definition.split()[0]
    columns = _table_columns(cursor, table_name)
    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"
        )


def create_inventory_table():
    """Create the enterprise inventory item master and migrate old schema."""
    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        now = _current_timestamp()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory(
                item_id TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                category_id TEXT,
                unit TEXT NOT NULL DEFAULT 'Piece',
                opening_quantity INTEGER NOT NULL DEFAULT 0,
                quantity INTEGER NOT NULL DEFAULT 0,
                damaged_quantity INTEGER NOT NULL DEFAULT 0,
                expiry_date TEXT,
                reorder_level INTEGER NOT NULL DEFAULT 10,
                cost_price REAL NOT NULL DEFAULT 0,
                selling_price REAL NOT NULL DEFAULT 0,
                supplier_id TEXT,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (hotel_id)
                    REFERENCES hotels(hotel_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT,
                FOREIGN KEY (supplier_id)
                    REFERENCES suppliers(supplier_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            )
        """)

        columns = _table_columns(cursor, "inventory")

        _add_column(
            cursor,
            "inventory",
            "damaged_quantity INTEGER NOT NULL DEFAULT 0"
        )
        _add_column(
            cursor,
            "inventory",
            "expiry_date TEXT"
        )

        # Existing Phase 3/4 schema used `price`. Promote it to the
        # enterprise `cost_price` field without losing existing data.
        if "cost_price" not in columns and "price" in columns:
            cursor.execute(
                "ALTER TABLE inventory RENAME COLUMN price TO cost_price"
            )
            columns = _table_columns(cursor, "inventory")

        _add_column(
            cursor,
            "inventory",
            "hotel_id INTEGER"
        )
        _add_column(
            cursor,
            "inventory",
            "category_id TEXT"
        )
        _add_column(
            cursor,
            "inventory",
            "unit TEXT DEFAULT 'Piece'"
        )
        _add_column(
            cursor,
            "inventory",
            "opening_quantity INTEGER DEFAULT 0"
        )
        _add_column(
            cursor,
            "inventory",
            "reorder_level INTEGER DEFAULT 10"
        )
        _add_column(
            cursor,
            "inventory",
            "cost_price REAL DEFAULT 0"
        )
        _add_column(
            cursor,
            "inventory",
            "selling_price REAL DEFAULT 0"
        )
        _add_column(
            cursor,
            "inventory",
            "status TEXT DEFAULT 'Active'"
        )
        _add_column(
            cursor,
            "inventory",
            "created_at TEXT"
        )
        _add_column(
            cursor,
            "inventory",
            "updated_at TEXT"
        )

        # Backfill legacy records only. Newer records already have values.
        cursor.execute("""
            UPDATE inventory
            SET hotel_id = ?
            WHERE hotel_id IS NULL
        """, (hotel_id,))

        cursor.execute("""
            UPDATE inventory
            SET unit = 'Piece'
            WHERE unit IS NULL OR TRIM(unit) = ''
        """)

        cursor.execute("""
            UPDATE inventory
            SET opening_quantity = quantity
            WHERE opening_quantity IS NULL
        """)

        cursor.execute("""
            UPDATE inventory
            SET reorder_level = 10
            WHERE reorder_level IS NULL OR reorder_level < 0
        """)

        cursor.execute("""
            UPDATE inventory
            SET cost_price = 0
            WHERE cost_price IS NULL
        """)

        cursor.execute("""
            UPDATE inventory
            SET selling_price = cost_price
            WHERE selling_price IS NULL
        """)

        cursor.execute("""
            UPDATE inventory
            SET status = 'Active'
            WHERE status IS NULL OR TRIM(status) = ''
        """)

        cursor.execute("""
            UPDATE inventory
            SET created_at = ?
            WHERE created_at IS NULL OR TRIM(created_at) = ''
        """, (now,))

        cursor.execute("""
            UPDATE inventory
            SET updated_at = created_at
            WHERE updated_at IS NULL OR TRIM(updated_at) = ''
        """)

        # SQLite cannot retroactively add a NOT NULL/FK constraint to an
        # existing table without a rebuild. The populated hotel_id is now
        # enforced by all application queries; full integrity triggers are
        # handled by the later 4.9 security/integrity stage.
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_hotel
            ON inventory(hotel_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_hotel_status
            ON inventory(hotel_id, status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_hotel_category
            ON inventory(hotel_id, category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_hotel_category_id
            ON inventory(hotel_id, category_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_hotel_reorder
            ON inventory(hotel_id, reorder_level, quantity)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_hotel_expiry
            ON inventory(hotel_id, expiry_date, quantity)
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def _get_inventory_actor():
    """Return the authenticated actor for inventory ledger traceability."""
    try:
        from database.user_db import get_current_session
        session = get_current_session()
    except Exception:
        session = None

    if session:
        return (
            session.get("user_id") or "SYSTEM",
            session.get("username") or session.get("user_id") or "SYSTEM",
            session.get("role") or "Unknown",
        )

    return "SYSTEM", "SYSTEM", "System"


def create_inventory_transactions_table():
    """Create the central inventory stock movement ledger."""
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_transactions(
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                item_id TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL,
                transaction_date TEXT NOT NULL,
                supplier_id TEXT,
                reference_no TEXT,
                reason TEXT,
                before_quantity REAL,
                after_quantity REAL,
                total_value REAL,
                batch_id INTEGER,
                batch_no TEXT,
                lot_no TEXT,
                actor_user_id TEXT,
                actor_username TEXT,
                actor_role TEXT,
                order_id TEXT,
                FOREIGN KEY (hotel_id)
                    REFERENCES hotels(hotel_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT,
                FOREIGN KEY (item_id)
                    REFERENCES inventory(item_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT
            )
        """)

        columns = _table_columns(cursor, "inventory_transactions")

        for definition in (
            "hotel_id INTEGER",
            "supplier_id TEXT",
            "reference_no TEXT",
            "reason TEXT",
            "before_quantity REAL",
            "after_quantity REAL",
            "total_value REAL",
            "batch_id INTEGER",
            "batch_no TEXT",
            "lot_no TEXT",
            "actor_user_id TEXT",
            "actor_username TEXT",
            "actor_role TEXT",
            "order_id TEXT",
        ):
            _add_column(
                cursor,
                "inventory_transactions",
                definition
            )

        # Backfill hotel ownership from the authoritative inventory item.
        cursor.execute("""
            UPDATE inventory_transactions
            SET hotel_id = (
                SELECT i.hotel_id
                FROM inventory i
                WHERE i.item_id = inventory_transactions.item_id
            )
            WHERE hotel_id IS NULL
        """)

        orphaned = cursor.execute("""
            SELECT 1
            FROM inventory_transactions t
            LEFT JOIN inventory i
              ON i.item_id = t.item_id
            WHERE i.item_id IS NULL
            LIMIT 1
        """).fetchone()

        if orphaned:
            raise ValueError(
                "Inventory transaction history contains an unknown item."
            )

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_transactions_hotel
            ON inventory_transactions(hotel_id, transaction_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_transactions_item
            ON inventory_transactions(hotel_id, item_id, transaction_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_transactions_type
            ON inventory_transactions(hotel_id, transaction_type, transaction_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_transactions_actor
            ON inventory_transactions(hotel_id, actor_user_id, transaction_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_transactions_order
            ON inventory_transactions(hotel_id, order_id, transaction_id)
        """)


        # Database-level integrity guards: application validation is not the only line of defense.
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_insert_nonnegative_stock
            BEFORE INSERT ON inventory
            WHEN NEW.quantity < 0 OR NEW.opening_quantity < 0
            BEGIN SELECT RAISE(ABORT, 'Inventory quantity cannot be negative.'); END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_nonnegative_stock
            BEFORE UPDATE OF quantity, opening_quantity ON inventory
            WHEN NEW.quantity < 0 OR NEW.opening_quantity < 0
            BEGIN SELECT RAISE(ABORT, 'Inventory quantity cannot be negative.'); END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_insert_nonnegative_damaged
            BEFORE INSERT ON inventory
            WHEN NEW.damaged_quantity < 0
            BEGIN SELECT RAISE(ABORT, 'Damaged quantity cannot be negative.'); END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_nonnegative_damaged
            BEFORE UPDATE OF damaged_quantity ON inventory
            WHEN NEW.damaged_quantity < 0
            BEGIN SELECT RAISE(ABORT, 'Damaged quantity cannot be negative.'); END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_insert_nonnegative_reorder
            BEFORE INSERT ON inventory
            WHEN NEW.reorder_level < 0
            BEGIN SELECT RAISE(ABORT, 'Reorder level cannot be negative.'); END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_nonnegative_reorder
            BEFORE UPDATE OF reorder_level ON inventory
            WHEN NEW.reorder_level < 0
            BEGIN SELECT RAISE(ABORT, 'Reorder level cannot be negative.'); END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_transaction_quantity_nonzero
            BEFORE INSERT ON inventory_transactions
            WHEN NEW.quantity = 0
            BEGIN SELECT RAISE(ABORT, 'Inventory transaction quantity cannot be zero.'); END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_transaction_stock_consistency
            BEFORE INSERT ON inventory_transactions
            WHEN NEW.before_quantity IS NOT NULL AND NEW.after_quantity IS NOT NULL
             AND (NEW.before_quantity < 0 OR NEW.after_quantity < 0)
            BEGIN SELECT RAISE(ABORT, 'Inventory transaction stock quantities cannot be negative.'); END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_transaction_hotel_item_match
            BEFORE INSERT ON inventory_transactions
            WHEN NOT EXISTS (
                SELECT 1 FROM inventory i
                WHERE i.item_id = NEW.item_id AND i.hotel_id = NEW.hotel_id
            )
            BEGIN SELECT RAISE(ABORT, 'Inventory transaction hotel/item mismatch.'); END;
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def migrate_inventory_relationships():
    """Preserve and strengthen existing inventory relationships."""
    connection = get_connection()

    try:
        cursor = connection.cursor()

        # ---------------------------------------------------------
        # Inventory -> Supplier relationship
        # ---------------------------------------------------------
        inventory_columns = _table_columns(cursor, "inventory")
        if "supplier_id" not in inventory_columns:
            cursor.execute("""
                ALTER TABLE inventory
                ADD COLUMN supplier_id TEXT
                REFERENCES suppliers(supplier_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
            """)

        # ---------------------------------------------------------
        # Inventory transaction -> Item relationship
        # ---------------------------------------------------------
        cursor.execute("PRAGMA foreign_key_list(inventory_transactions)")
        foreign_keys = cursor.fetchall()

        has_item_fk = any(
            fk["table"] == "inventory"
            and fk["from"] == "item_id"
            and fk["to"] == "item_id"
            for fk in foreign_keys
        )

        if not has_item_fk:
            cursor.execute("""
                SELECT DISTINCT t.item_id
                FROM inventory_transactions t
                LEFT JOIN inventory i
                    ON i.item_id = t.item_id
                WHERE i.item_id IS NULL
            """)
            orphaned_items = cursor.fetchall()

            if orphaned_items:
                raise ValueError(
                    "Cannot migrate inventory transactions because "
                    "orphaned item records were found."
                )

            # create_inventory_transactions_table() has already added all
            # current ledger columns before this migration runs.
            cursor.execute("""
                CREATE TABLE inventory_transactions_new(
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hotel_id INTEGER NOT NULL DEFAULT 1,
                    item_id TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL,
                    transaction_date TEXT NOT NULL,
                    supplier_id TEXT,
                    reference_no TEXT,
                    reason TEXT,
                    before_quantity REAL,
                    after_quantity REAL,
                    total_value REAL,
                    batch_id INTEGER,
                    batch_no TEXT,
                    lot_no TEXT,
                    actor_user_id TEXT,
                    actor_username TEXT,
                    actor_role TEXT,
                    FOREIGN KEY (hotel_id)
                        REFERENCES hotels(hotel_id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT,
                    FOREIGN KEY (item_id)
                        REFERENCES inventory(item_id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT
                )
            """)

            cursor.execute("""
                INSERT INTO inventory_transactions_new(
                    transaction_id,
                    hotel_id,
                    item_id,
                    transaction_type,
                    quantity,
                    price,
                    transaction_date,
                    supplier_id,
                    reference_no,
                    reason,
                    before_quantity,
                    after_quantity,
                    total_value,
                    batch_id,
                    batch_no,
                    lot_no,
                    actor_user_id,
                    actor_username,
                    actor_role
                )
                SELECT
                    transaction_id,
                    COALESCE(
                        hotel_id,
                        (SELECT i.hotel_id
                         FROM inventory i
                         WHERE i.item_id = inventory_transactions.item_id),
                        1
                    ),
                    item_id,
                    transaction_type,
                    quantity,
                    price,
                    transaction_date,
                    supplier_id,
                    reference_no,
                    reason,
                    before_quantity,
                    after_quantity,
                    total_value,
                    batch_id,
                    batch_no,
                    lot_no,
                    COALESCE(actor_user_id, 'SYSTEM'),
                    COALESCE(actor_username, 'SYSTEM'),
                    COALESCE(actor_role, 'System')
                FROM inventory_transactions
            """)

            cursor.execute("DROP TABLE inventory_transactions")
            cursor.execute("""
                ALTER TABLE inventory_transactions_new
                RENAME TO inventory_transactions
            """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_transactions_hotel
            ON inventory_transactions(hotel_id, transaction_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_transactions_item
            ON inventory_transactions(hotel_id, item_id, transaction_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_transactions_type
            ON inventory_transactions(hotel_id, transaction_type, transaction_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_transactions_actor
            ON inventory_transactions(hotel_id, actor_user_id, transaction_id)
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_item(
    item_id,
    item_name,
    category_id,
    unit_id,
    opening_quantity,
    cost_price,
    selling_price,
    reorder_level=10,
    supplier_id=None,
    expiry_date=None
):
    """Create an inventory item in the current hotel."""
    connection = get_connection()

    try:
        cursor = connection.cursor()
        hotel_id = get_current_hotel_id()
        now = _current_timestamp()

        if not item_id or not item_name or not category_id or not unit_id:
            raise ValueError("Item master fields cannot be empty.")

        category_id = str(category_id).strip().upper()
        unit_id = str(unit_id).strip().upper()
        category = cursor.execute("""
            SELECT category_id, category_name
            FROM inventory_categories
            WHERE hotel_id = ?
              AND category_id = ?
              AND status = 'Active'
            LIMIT 1
        """, (hotel_id, category_id)).fetchone()

        # Compatibility: allow a legacy category name from programmatic callers,
        # but always persist the normalized master Category ID.
        if category is None:
            category = cursor.execute("""
                SELECT category_id, category_name
                FROM inventory_categories
                WHERE hotel_id = ?
                  AND lower(trim(category_name)) = lower(trim(?))
                  AND status = 'Active'
                LIMIT 1
            """, (hotel_id, category_id)).fetchone()

        if category is None:
            raise ValueError("Invalid or inactive Inventory Category.")

        unit_record = cursor.execute("""
            SELECT unit_id, unit_name, unit_symbol
            FROM inventory_units
            WHERE hotel_id = ?
              AND unit_id = ?
              AND status = 'Active'
            LIMIT 1
        """, (hotel_id, unit_id)).fetchone()

        # Compatibility: allow a legacy unit name/symbol from programmatic
        # callers, but always persist the normalized master Unit ID.
        if unit_record is None:
            unit_record = cursor.execute("""
                SELECT unit_id, unit_name, unit_symbol
                FROM inventory_units
                WHERE hotel_id = ?
                  AND (
                        lower(trim(unit_name)) = lower(trim(?))
                        OR lower(trim(unit_symbol)) = lower(trim(?))
                      )
                  AND status = 'Active'
                LIMIT 1
            """, (hotel_id, unit_id, unit_id)).fetchone()

        if unit_record is None:
            raise ValueError("Invalid or inactive Inventory Unit.")

        try:
            reorder_level = int(reorder_level)
        except (TypeError, ValueError) as exc:
            raise ValueError("Reorder level must be a whole number.") from exc

        if reorder_level < 0:
            raise ValueError("Reorder level cannot be negative.")

        if opening_quantity < 0:
            raise ValueError("Opening quantity cannot be negative.")

        if cost_price < 0 or selling_price < 0:
            raise ValueError("Item prices cannot be negative.")

        expiry_date = _normalize_expiry_date(expiry_date)

        if supplier_id:
            cursor.execute(
                """
                SELECT status
                FROM suppliers
                WHERE supplier_id = ?
                  AND hotel_id = ?
                """,
                (supplier_id, hotel_id)
            )
            supplier_record = cursor.fetchone()
            if supplier_record is None:
                raise ValueError("Supplier Not Found.")
            if supplier_record["status"] != "Active":
                raise ValueError("Inactive Supplier cannot be assigned to an inventory item.")

        cursor.execute(
            """
            SELECT 1
            FROM inventory
            WHERE item_id = ?
            """,
            (item_id,)
        )
        if cursor.fetchone() is not None:
            raise ValueError("Item ID already exists.")

        cursor.execute(
            """
            INSERT INTO inventory(
                item_id,
                hotel_id,
                item_name,
                category,
                category_id,
                unit_id,
                unit,
                opening_quantity,
                quantity,
                expiry_date,
                reorder_level,
                cost_price,
                selling_price,
                supplier_id,
                status,
                created_at,
                updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)
            """,
            (
                item_id,
                hotel_id,
                item_name,
                category["category_name"],
                category["category_id"],
                unit_record["unit_id"],
                unit_record["unit_name"],
                opening_quantity,
                opening_quantity,
                expiry_date,
                reorder_level,
                cost_price,
                selling_price,
                supplier_id,
                now,
                now
            )
        )

        actor_user_id, actor_username, actor_role = _get_inventory_actor()

        # Opening stock must have a ledger entry so the initial quantity is
        # traceable once stock history is viewed.
        if opening_quantity > 0:
            cursor.execute("""
                INSERT INTO inventory_transactions(
                    hotel_id,
                    item_id,
                    transaction_type,
                    quantity,
                    price,
                    transaction_date,
                    reason,
                    before_quantity,
                    after_quantity,
                    total_value,
                    actor_user_id,
                    actor_username,
                    actor_role
                )
                VALUES(?, ?, 'OPENING STOCK', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                hotel_id,
                item_id,
                opening_quantity,
                cost_price,
                now,
                "Opening Stock",
                0,
                opening_quantity,
                opening_quantity * cost_price,
                actor_user_id,
                actor_username,
                actor_role
            ))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Inventory",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_item completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except sqlite3.IntegrityError as exc:
        connection.rollback()
        raise ValueError(f"Unable to save item: {exc}") from exc
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def view_items():
    _require_inventory_permission("View")
    hotel_id = get_current_hotel_id()

    print("=" * 72)
    print("                         INVENTORY ITEMS")
    print("=" * 72)

    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT
                i.item_id,
                i.item_name,
                i.category_id,
                COALESCE(c.category_name, i.category) AS category_name,
                i.unit_id,
                i.unit,
                u.unit_symbol,
                i.opening_quantity,
                i.quantity,
                i.damaged_quantity,
                i.expiry_date,
                i.reorder_level,
                i.cost_price,
                i.selling_price,
                i.supplier_id,
                i.status,
                i.created_at,
                i.updated_at,
                s.supplier_name
            FROM inventory i
            LEFT JOIN suppliers s
              ON s.supplier_id = i.supplier_id
            LEFT JOIN inventory_categories c
              ON c.category_id = i.category_id
             AND c.hotel_id = i.hotel_id
            LEFT JOIN inventory_units u
              ON u.unit_id = i.unit_id
             AND u.hotel_id = i.hotel_id
            WHERE i.hotel_id = ?
            ORDER BY i.item_name, i.item_id
        """, (hotel_id,)).fetchall()

        if not rows:
            print("No Inventory Items Found.")
            return

        for item in rows:
            print("-" * 72)
            print("Item ID          :", item["item_id"])
            print("Item Name        :", item["item_name"])
            print("Category ID      :", item["category_id"] or "Legacy")
            print("Category         :", item["category_name"])
            print("Unit ID          :", item["unit_id"] or "Legacy")
            print("Unit             :", item["unit"])
            print("Unit Symbol      :", item["unit_symbol"] or "N/A")
            print("Opening Quantity :", item["opening_quantity"])
            print("Current Quantity :", item["quantity"])
            print("Damaged Quantity :", item["damaged_quantity"])
            print("Expiry Date      :", item["expiry_date"] or "Not Set")
            print("Expiry Status    :", get_expiry_status(item["expiry_date"]))
            print("Reorder Level    :", item["reorder_level"])
            print("Cost Price       :", f"{float(item['cost_price']):.2f}")
            print("Selling Price    :", f"{float(item['selling_price']):.2f}")
            print("Supplier ID      :", item["supplier_id"] or "Not Assigned")
            print("Supplier Name    :", item["supplier_name"] or "Not Assigned")
            print("Status           :", item["status"])
            print("Created At       :", item["created_at"] or "N/A")
            print("Updated At       :", item["updated_at"] or "N/A")
        print("-" * 72)

    finally:
        connection.close()


def search_item():
    _require_inventory_permission("View")
    hotel_id = get_current_hotel_id()
    item_id = input("Enter Item ID : ").strip().upper()

    connection = get_connection()
    try:
        item = connection.execute("""
            SELECT
                i.*,
                COALESCE(c.category_name, i.category) AS category_name,
                u.unit_symbol,
                s.supplier_name
            FROM inventory i
            LEFT JOIN suppliers s
              ON s.supplier_id = i.supplier_id
            LEFT JOIN inventory_categories c
              ON c.category_id = i.category_id
             AND c.hotel_id = i.hotel_id
            LEFT JOIN inventory_units u
              ON u.unit_id = i.unit_id
             AND u.hotel_id = i.hotel_id
            WHERE i.hotel_id = ?
              AND i.item_id = ?
        """, (hotel_id, item_id)).fetchone()

        if not item:
            print("Item Not Found.")
            return

        print("=" * 72)
        print("                         ITEM DETAILS")
        print("=" * 72)
        print("Item ID          :", item["item_id"])
        print("Item Name        :", item["item_name"])
        print("Category ID      :", item["category_id"] or "Legacy")
        print("Category         :", item["category_name"])
        print("Unit ID          :", item["unit_id"] or "Legacy")
        print("Unit             :", item["unit"])
        print("Unit Symbol      :", item["unit_symbol"] or "N/A")
        print("Opening Quantity :", item["opening_quantity"])
        print("Current Quantity :", item["quantity"])
        print("Damaged Quantity :", item["damaged_quantity"])
        print("Expiry Date      :", item["expiry_date"] or "Not Set")
        print("Expiry Status    :", get_expiry_status(item["expiry_date"]))
        print("Cost Price       :", f"{float(item['cost_price']):.2f}")
        print("Selling Price    :", f"{float(item['selling_price']):.2f}")
        print("Supplier ID      :", item["supplier_id"] or "Not Assigned")
        print("Supplier Name    :", item["supplier_name"] or "Not Assigned")
        print("Status           :", item["status"])
        print("Created At       :", item["created_at"] or "N/A")
        print("Updated At       :", item["updated_at"] or "N/A")
        print("=" * 72)

    finally:
        connection.close()


def update_item():
    _require_inventory_permission("Update")
    hotel_id = get_current_hotel_id()
    item_id = input("Enter Item ID : ").strip().upper()

    connection = get_connection()

    try:
        cursor = connection.cursor()
        item = cursor.execute("""
            SELECT *
            FROM inventory
            WHERE hotel_id = ?
              AND item_id = ?
        """, (hotel_id, item_id)).fetchone()

        if not item:
            print("Item Not Found.")
            return

        item_name = input(
            f"Item Name ({item['item_name']}) : "
        ).strip() or item["item_name"]

        current_category_id = item["category_id"]
        current_category_name = item["category"]

        if current_category_id:
            current_category = cursor.execute("""
                SELECT category_id, category_name, status
                FROM inventory_categories
                WHERE hotel_id = ? AND category_id = ?
            """, (hotel_id, current_category_id)).fetchone()
            if current_category:
                current_category_name = current_category["category_name"]

        print("Available Inventory Categories:")
        category_options = cursor.execute("""
            SELECT category_id, category_name, status
            FROM inventory_categories
            WHERE hotel_id = ?
              AND (status = 'Active' OR category_id = ?)
            ORDER BY category_name COLLATE NOCASE
        """, (hotel_id, current_category_id or "")).fetchall()

        for option in category_options:
            marker = " (Current)" if option["category_id"] == current_category_id else ""
            status_label = "" if option["status"] == "Active" else " [Inactive]"
            print(f"{option['category_id']} - {option['category_name']}{status_label}{marker}")

        category_raw = input(
            f"Category ID ({current_category_id or current_category_name}) : "
        ).strip().upper()

        if category_raw:
            category_record = cursor.execute("""
                SELECT category_id, category_name, status
                FROM inventory_categories
                WHERE hotel_id = ?
                  AND category_id = ?
                  AND status = 'Active'
            """, (hotel_id, category_raw)).fetchone()
            if category_record is None:
                raise ValueError("Invalid or inactive Inventory Category.")
            category_id = category_record["category_id"]
            category = category_record["category_name"]
        else:
            category_id = current_category_id
            category = current_category_name
            if not category_id:
                raise ValueError("Inventory Category is required.")

        current_unit_id = item["unit_id"]
        current_unit_name = item["unit"]

        if current_unit_id:
            current_unit = cursor.execute("""
                SELECT unit_id, unit_name, unit_symbol, status
                FROM inventory_units
                WHERE hotel_id = ? AND unit_id = ?
            """, (hotel_id, current_unit_id)).fetchone()
            if current_unit:
                current_unit_name = current_unit["unit_name"]

        print("Available Inventory Units:")
        unit_options = cursor.execute("""
            SELECT unit_id, unit_name, unit_symbol, status
            FROM inventory_units
            WHERE hotel_id = ?
              AND (status = 'Active' OR unit_id = ?)
            ORDER BY unit_name COLLATE NOCASE, unit_id
        """, (hotel_id, current_unit_id or "")).fetchall()

        for option in unit_options:
            marker = " (Current)" if option["unit_id"] == current_unit_id else ""
            status_label = "" if option["status"] == "Active" else " [Inactive]"
            print(
                f"{option['unit_id']} - {option['unit_name']} "
                f"[{option['unit_symbol']}]"
                f"{status_label}{marker}"
            )

        unit_raw = input(
            f"Unit ID ({current_unit_id or current_unit_name}) : "
        ).strip().upper()

        if unit_raw:
            unit_record = cursor.execute("""
                SELECT unit_id, unit_name, unit_symbol, status
                FROM inventory_units
                WHERE hotel_id = ?
                  AND unit_id = ?
                  AND status = 'Active'
            """, (hotel_id, unit_raw)).fetchone()
            if unit_record is None:
                raise ValueError("Invalid or inactive Inventory Unit.")
            unit_id = unit_record["unit_id"]
            unit = unit_record["unit_name"]
        else:
            unit_id = current_unit_id
            unit = current_unit_name
            if not unit_id:
                raise ValueError("Inventory Unit is required.")

        reorder_raw = input(
            f"Reorder Level ({int(item['reorder_level'] or 0)}) : "
        ).strip()
        if reorder_raw:
            try:
                reorder_level = int(reorder_raw)
            except ValueError as exc:
                raise ValueError("Reorder Level must be a whole number.") from exc
            if reorder_level < 0:
                raise ValueError("Reorder Level cannot be negative.")
        else:
            reorder_level = int(item["reorder_level"] or 0)

        cost_raw = input(
            f"Cost Price ({float(item['cost_price']):.2f}) : "
        ).strip()
        if cost_raw:
            try:
                cost_price = float(cost_raw)
            except ValueError as exc:
                raise ValueError("Invalid Cost Price.") from exc
            if cost_price < 0:
                raise ValueError("Cost Price cannot be negative.")
        else:
            cost_price = float(item["cost_price"])

        selling_raw = input(
            f"Selling Price ({float(item['selling_price']):.2f}) : "
        ).strip()
        if selling_raw:
            try:
                selling_price = float(selling_raw)
            except ValueError as exc:
                raise ValueError("Invalid Selling Price.") from exc
            if selling_price < 0:
                raise ValueError("Selling Price cannot be negative.")
        else:
            selling_price = float(item["selling_price"])

        current_expiry = item["expiry_date"] or "Not Set"
        expiry_raw = input(
            f"Expiry Date ({current_expiry}; blank = current; CLEAR = remove) : "
        ).strip()
        if expiry_raw.upper() == "CLEAR":
            expiry_date = None
        elif expiry_raw:
            expiry_date = _normalize_expiry_date(expiry_raw)
        else:
            expiry_date = item["expiry_date"]

        current_supplier = item["supplier_id"] or "Not Assigned"
        supplier_raw = input(
            f"Supplier ID ({current_supplier}) : "
        ).strip().upper()
        supplier_id = supplier_raw or item["supplier_id"]

        if supplier_id:
            supplier = cursor.execute("""
                SELECT status
                FROM suppliers
                WHERE supplier_id = ?
                  AND hotel_id = ?
            """, (supplier_id, hotel_id)).fetchone()
            if supplier is None:
                raise ValueError("Supplier Not Found.")
            if supplier["status"] != "Active":
                raise ValueError("Inactive Supplier cannot be assigned to an inventory item.")

        now = _current_timestamp()

        # Current stock is deliberately NOT editable here. Any stock change
        # must go through Stock In/Out or future Adjustment functionality so
        # the stock ledger can remain correct.
        cursor.execute("""
            UPDATE inventory
            SET
                item_name = ?,
                category = ?,
                category_id = ?,
                unit_id = ?,
                unit = ?,
                reorder_level = ?,
                cost_price = ?,
                selling_price = ?,
                supplier_id = ?,
                expiry_date = ?,
                updated_at = ?
            WHERE hotel_id = ?
              AND item_id = ?
        """, (
            item_name,
            category,
            category_id,
            unit_id,
            unit,
            reorder_level,
            cost_price,
            selling_price,
            supplier_id,
            expiry_date,
            now,
            hotel_id,
            item_id
        ))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Inventory",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_item completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Item Updated Successfully.")

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _set_item_status(status):
    hotel_id = get_current_hotel_id()
    item_id = input("Enter Item ID : ").strip().upper()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        item = cursor.execute("""
            SELECT status
            FROM inventory
            WHERE hotel_id = ?
              AND item_id = ?
        """, (hotel_id, item_id)).fetchone()

        if not item:
            print("Item Not Found.")
            return

        if item["status"] == status:
            print(f"Item is already {status}.")
            return

        cursor.execute("""
            UPDATE inventory
            SET status = ?, updated_at = ?
            WHERE hotel_id = ?
              AND item_id = ?
        """, (status, _current_timestamp(), hotel_id, item_id))

        connection.commit()
        print(f"Item {status} Successfully.")

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def deactivate_item():
    _require_inventory_permission("Update")
    _set_item_status("Inactive")


def activate_item():
    _require_inventory_permission("Update")
    _set_item_status("Active")


def delete_item():
    _require_inventory_permission("Delete")
    hotel_id = get_current_hotel_id()
    item_id = input("Enter Item ID : ").strip().upper()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        item = cursor.execute("""
            SELECT 1
            FROM inventory
            WHERE hotel_id = ?
              AND item_id = ?
        """, (hotel_id, item_id)).fetchone()

        if item is None:
            print("Item Not Found.")
            return

        cursor.execute("""
            SELECT 1
            FROM inventory_transactions
            WHERE hotel_id = ?
              AND item_id = ?
            LIMIT 1
        """, (hotel_id, item_id))

        if cursor.fetchone():
            print(
                "Item has stock transaction history and cannot be deleted. "
                "Deactivate it instead to preserve inventory history."
            )
            connection.rollback()
            return

        cursor.execute("""
            DELETE FROM inventory
            WHERE hotel_id = ?
              AND item_id = ?
        """, (hotel_id, item_id))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Inventory",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_item completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Item Deleted Successfully.")

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_active_item_options():
    """Return active inventory items for stock movement selection."""
    hotel_id = get_current_hotel_id()
    connection = get_connection()

    try:
        return connection.execute("""
            SELECT
                item_id,
                item_name,
                quantity,
                damaged_quantity,
                unit,
                cost_price,
                supplier_id
            FROM inventory
            WHERE hotel_id = ?
              AND status = 'Active'
            ORDER BY item_name COLLATE NOCASE, item_id
        """, (hotel_id,)).fetchall()
    finally:
        connection.close()


def stock_in(
    item_id,
    quantity,
    unit_cost=None,
    supplier_id=None,
    reference_no=None,
    reason=None,
    batch_no=None,
    lot_no=None,
    batch_expiry_date=None,
    connection=None,
):
    _require_inventory_permission("Create")
    """
    Receive stock into the current hotel atomically.

    The movement updates current stock and creates a traceable STOCK IN
    ledger entry in the same database transaction.
    """
    hotel_id = get_current_hotel_id()
    item_id = str(item_id or "").strip().upper()

    if not item_id:
        raise ValueError("Item ID cannot be empty.")

    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError("Quantity must be a whole number greater than zero.") from exc

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    if unit_cost is not None:
        try:
            unit_cost = float(unit_cost)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid Stock In Unit Cost.") from exc
        if unit_cost < 0:
            raise ValueError("Stock In Unit Cost cannot be negative.")

    supplier_id = (
        str(supplier_id).strip().upper()
        if supplier_id is not None and str(supplier_id).strip()
        else None
    )
    reference_no = (
        str(reference_no).strip()
        if reference_no is not None and str(reference_no).strip()
        else None
    )
    reason = (
        " ".join(str(reason).strip().split())
        if reason is not None and str(reason).strip()
        else "Stock In"
    )
    batch_no = str(batch_no or "").strip() or None
    lot_no = str(lot_no or "").strip() or None
    batch_expiry_date = str(batch_expiry_date or "").strip() or None

    # Reuse a caller-provided connection so higher-level workflows
    # (for example Purchase Receiving) remain one atomic transaction.
    own_connection = connection is None
    connection = connection or get_connection()
    try:
        cursor = connection.cursor()

        item = cursor.execute("""
            SELECT
                quantity,
                cost_price,
                status,
                supplier_id
            FROM inventory
            WHERE hotel_id = ?
              AND item_id = ?
        """, (hotel_id, item_id)).fetchone()

        if item is None:
            raise ValueError("Item Not Found.")

        if item["status"] != "Active":
            raise ValueError("Inactive Item cannot receive stock.")

        current_quantity = int(item["quantity"] or 0)
        before_quantity = current_quantity
        after_quantity = current_quantity + quantity

        effective_cost = (
            float(item["cost_price"] or 0)
            if unit_cost is None
            else float(unit_cost)
        )

        effective_supplier = supplier_id or item["supplier_id"]

        if effective_supplier:
            supplier = cursor.execute("""
                SELECT status
                FROM suppliers
                WHERE supplier_id = ?
                  AND hotel_id = ?
            """, (effective_supplier, hotel_id)).fetchone()

            if supplier is None:
                raise ValueError("Supplier Not Found.")
            if supplier["status"] != "Active":
                raise ValueError("Inactive Supplier cannot receive stock.")

        now = _current_timestamp()
        total_value = quantity * effective_cost

        batch_id = None
        if batch_no or lot_no:
            from database.inventory_batch_db import save_or_receive_batch
            batch_id = save_or_receive_batch(
                item_id=item_id,
                quantity=quantity,
                cost_price=effective_cost,
                batch_no=batch_no,
                lot_no=lot_no,
                received_date=current_date(),
                expiry_date=batch_expiry_date,
                supplier_id=effective_supplier,
                connection=connection,
            )

        # Update current stock. If a new unit cost was explicitly supplied,
        # keep the item master aligned with the latest received cost.
        if unit_cost is None:
            cursor.execute("""
                UPDATE inventory
                SET
                    quantity = ?,
                    supplier_id = ?,
                    updated_at = ?
                WHERE hotel_id = ?
                  AND item_id = ?
            """, (
                after_quantity,
                effective_supplier,
                now,
                hotel_id,
                item_id
            ))
        else:
            cursor.execute("""
                UPDATE inventory
                SET
                    quantity = ?,
                    cost_price = ?,
                    supplier_id = ?,
                    updated_at = ?
                WHERE hotel_id = ?
                  AND item_id = ?
            """, (
                after_quantity,
                effective_cost,
                effective_supplier,
                now,
                hotel_id,
                item_id
            ))

        actor_user_id, actor_username, actor_role = _get_inventory_actor()

        cursor.execute("""
            INSERT INTO inventory_transactions(
                hotel_id,
                item_id,
                transaction_type,
                quantity,
                price,
                transaction_date,
                supplier_id,
                reference_no,
                reason,
                before_quantity,
                after_quantity,
                total_value,
                batch_id,
                batch_no,
                lot_no,
                actor_user_id,
                actor_username,
                actor_role
            )
            VALUES(
                ?, ?, 'STOCK IN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            hotel_id,
            item_id,
            quantity,
            effective_cost,
            now,
            effective_supplier,
            reference_no,
            reason,
            before_quantity,
            after_quantity,
            total_value,
            batch_id,
            batch_no,
            lot_no,
            actor_user_id,
            actor_username,
            actor_role
        ))

        transaction_id = cursor.lastrowid

        if own_connection:
            connection.commit()
            try:
                from database.audit_db import log_business_activity
                log_business_activity(
                    module="Inventory",
        action="CREATE",
        local_values=locals(),
        details="Business operation stock_in completed successfully.",
                )
            except Exception as exc:
                log_non_blocking_error("Non-blocking optional operation failed", exc)

        print("Stock Added Successfully.")
        print("Transaction ID :", transaction_id)
        print("Item ID        :", item_id)
        print("Quantity Added :", quantity)
        print("Before Stock   :", before_quantity)
        print("After Stock    :", after_quantity)
        print("Unit Cost      :", f"{effective_cost:.2f}")
        print("Total Value    :", f"{total_value:.2f}")
        if batch_id is not None:
            print("Batch ID       :", batch_id)
            print("Batch No       :", batch_no or "Not Set")
            print("Lot No         :", lot_no or "Not Set")

        return transaction_id

    except Exception:
        if own_connection:
            connection.rollback()
        raise
    finally:
        if own_connection:
            connection.close()


def stock_out(
    item_id,
    quantity,
    reference_no=None,
    reason=None,
    order_id=None
):
    _require_inventory_permission("Create")
    """
    Issue stock from the current hotel atomically.

    Stock can only be issued from an active item when sufficient
    quantity is available. The current quantity is reduced and a
    traceable STOCK OUT ledger entry is created in the same SQLite
    transaction.
    """
    hotel_id = get_current_hotel_id()
    item_id = str(item_id or "").strip().upper()

    if not item_id:
        raise ValueError("Item ID cannot be empty.")

    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Quantity must be a whole number greater than zero."
        ) from exc

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    reference_no = (
        str(reference_no).strip()
        if reference_no is not None and str(reference_no).strip()
        else None
    )

    reason = (
        " ".join(str(reason).strip().split())
        if reason is not None and str(reason).strip()
        else None
    )

    if not reason:
        raise ValueError("Stock Out Reason is required.")

    order_id = (
        str(order_id).strip().upper()
        if order_id is not None and str(order_id).strip()
        else None
    )

    connection = get_connection()

    try:
        # Serialize stock-out operations so the quantity check and
        # quantity update cannot be interleaved with another writer.
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.cursor()

        item = cursor.execute("""
            SELECT
                item_name,
                unit,
                quantity,
                cost_price,
                status
            FROM inventory
            WHERE hotel_id = ?
              AND item_id = ?
        """, (hotel_id, item_id)).fetchone()

        if item is None:
            raise ValueError("Item Not Found.")

        if item["status"] != "Active":
            raise ValueError("Inactive Item cannot issue stock.")

        before_quantity = int(item["quantity"] or 0)

        if before_quantity < quantity:
            raise ValueError(
                f"Insufficient Stock. Available: "
                f"{before_quantity} {item['unit']}."
            )

        after_quantity = before_quantity - quantity
        effective_cost = float(item["cost_price"] or 0)
        total_value = quantity * effective_cost
        now = _current_timestamp()

        cursor.execute("""
            UPDATE inventory
            SET
                quantity = ?,
                updated_at = ?
            WHERE hotel_id = ?
              AND item_id = ?
              AND status = 'Active'
              AND quantity >= ?
        """, (
            after_quantity,
            now,
            hotel_id,
            item_id,
            quantity
        ))

        if cursor.rowcount != 1:
            raise ValueError(
                "Stock Out could not be completed because "
                "the available stock changed. Please try again."
            )

        actor_user_id, actor_username, actor_role = _get_inventory_actor()

        cursor.execute("""
            INSERT INTO inventory_transactions(
                hotel_id,
                item_id,
                transaction_type,
                quantity,
                price,
                transaction_date,
                reference_no,
                reason,
                before_quantity,
                after_quantity,
                total_value,
                actor_user_id,
                actor_username,
                actor_role,
                order_id
            )
            VALUES(
                ?, ?, 'STOCK OUT', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            hotel_id,
            item_id,
            quantity,
            effective_cost,
            now,
            reference_no,
            reason,
            before_quantity,
            after_quantity,
            total_value,
            actor_user_id,
            actor_username,
            actor_role,
            order_id
        ))

        try:
            from database.notification_db import record_low_stock_notification_if_needed
            record_low_stock_notification_if_needed(
                cursor,
                hotel_id,
                item_id,
                before_quantity,
                after_quantity,
                item_name=item["item_name"],
                unit=item["unit"],
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        transaction_id = cursor.lastrowid
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Inventory",
        action="CREATE",
        local_values=locals(),
        details="Business operation stock_out completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        print("Stock Removed Successfully.")
        print("Transaction ID :", transaction_id)
        print("Item ID        :", item_id)
        print("Quantity Issued:", quantity)
        print("Before Stock   :", before_quantity)
        print("After Stock    :", after_quantity)
        print("Unit Cost      :", f"{effective_cost:.2f}")
        print("Total Value    :", f"{total_value:.2f}")
        print("Reason         :", reason)

        if reference_no:
            print("Reference No   :", reference_no)
        if order_id:
            print("Restaurant Order:", order_id)

        return transaction_id

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def stock_out_for_restaurant_order(
    order_id,
    item_id,
    quantity,
    reason=None
):
    """
    Issue inventory stock against an existing restaurant order.

    The order is validated for the current hotel and must not be
    cancelled. The actual stock movement reuses stock_out(), so
    quantity validation, transaction handling, actor tracking and
    ledger recording remain centralized in the inventory layer.
    """

    _require_inventory_permission("Create")
    order_id = str(order_id or "").strip().upper()
    if not order_id:
        raise ValueError("Restaurant Order ID is required.")

    hotel_id = get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        order = cursor.execute("""
            SELECT order_id, order_status
            FROM orders
            WHERE hotel_id = ?
              AND order_id = ?
        """, (hotel_id, order_id)).fetchone()
    finally:
        connection.close()

    if order is None:
        raise ValueError("Restaurant Order Not Found for the current hotel.")

    order_status = order["order_status"] or "New"
    if order_status == "Cancelled":
        raise ValueError("Cancelled Restaurant Order cannot consume inventory.")

    normalized_reason = (
        " ".join(str(reason).strip().split())
        if reason is not None and str(reason).strip()
        else f"Restaurant Order Inventory Issue - {order_id}"
    )

    return stock_out(
        item_id=item_id,
        quantity=quantity,
        reference_no=f"ORDER:{order_id}",
        reason=normalized_reason,
        order_id=order_id
    )


def get_restaurant_order_inventory_usage(order_id):
    """Return inventory stock-out transactions linked to one restaurant order."""
    _require_inventory_permission("View")
    order_id = str(order_id or "").strip().upper()
    if not order_id:
        raise ValueError("Restaurant Order ID is required.")

    hotel_id = get_current_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()
        return cursor.execute("""
            SELECT
                t.transaction_id,
                t.order_id,
                t.item_id,
                i.item_name,
                t.quantity,
                i.unit,
                t.price,
                t.total_value,
                t.before_quantity,
                t.after_quantity,
                t.reason,
                t.actor_username,
                t.actor_role,
                t.transaction_date,
                t.reference_no
            FROM inventory_transactions t
            JOIN inventory i
              ON i.item_id = t.item_id
             AND i.hotel_id = t.hotel_id
            WHERE t.hotel_id = ?
              AND t.order_id = ?
              AND t.transaction_type = 'STOCK OUT'
            ORDER BY t.transaction_id DESC
        """, (hotel_id, order_id)).fetchall()
    finally:
        connection.close()


def restaurant_order_inventory_integration():
    """Interactive inventory issue and history workflow for restaurant orders."""
    _require_inventory_permission("View")
    from database.order_db import get_orders

    while True:
        print("\n1. Issue Inventory Stock Against Restaurant Order")
        print("2. View Restaurant Order Inventory Usage")
        print("3. Back")

        choice = input("Enter Choice : ").strip()

        if choice == "3":
            return

        if choice not in {"1", "2"}:
            print("Invalid Choice.")
            continue

        orders = [
            record for record in get_orders()
            if (record["order_status"] or "New") != "Cancelled"
        ]

        if not orders:
            print("No active/non-cancelled Restaurant Orders Found.")
            continue

        print("\nAvailable Restaurant Orders:")
        for index, order in enumerate(orders, 1):
            print(
                f"{index}. {order['order_id']} | "
                f"{order['order_status'] or 'New'} | "
                f"Table: {order['table_number'] or '-'} | "
                f"₹{float(order['grand_total'] or 0):.2f}"
            )

        valid_choices = [str(i) for i in range(1, len(orders) + 1)] + ["0"]
        selected = input("Select Order Number (0 = Back) : ").strip()
        if selected == "0":
            continue
        if selected not in valid_choices:
            print("Invalid Order Selection.")
            continue

        order = orders[int(selected) - 1]
        order_id = order["order_id"]

        if choice == "2":
            usage = get_restaurant_order_inventory_usage(order_id)
            print(f"\nInventory Usage for Order: {order_id}")
            if not usage:
                print("No Inventory Stock Issue has been recorded for this order.")
                continue

            for record in usage:
                print(
                    f"TXN {record['transaction_id']} | "
                    f"{record['item_id']} - {record['item_name']} | "
                    f"Qty: {record['quantity']} {record['unit']} | "
                    f"Value: ₹{float(record['total_value'] or 0):.2f} | "
                    f"{record['transaction_date']}"
                )
            continue

        item_options = get_active_item_options()
        if not item_options:
            print("No Active Inventory Items Found.")
            continue

        print("\nAvailable Active Inventory Items:")
        for item in item_options:
            print(
                f"{item['item_id']} - {item['item_name']} | "
                f"Stock: {item['quantity']} {item['unit']}"
            )

        item_id = input("Enter Inventory Item ID : ").strip().upper()
        selected_item = next(
            (item for item in item_options if item["item_id"] == item_id),
            None
        )
        if selected_item is None:
            print("Invalid or inactive Inventory Item.")
            continue

        try:
            quantity = int(input(
                f"Enter Quantity to Issue "
                f"(Available: {selected_item['quantity']} {selected_item['unit']}) : "
            ).strip())
            if quantity <= 0:
                raise ValueError("Quantity must be greater than zero.")
            if quantity > int(selected_item["quantity"] or 0):
                raise ValueError(
                    f"Insufficient Stock. Available: {selected_item['quantity']} "
                    f"{selected_item['unit']}."
                )

            reason = input(
                "Reason (Enter = Restaurant Order Inventory Issue) : "
            ).strip()

            transaction_id = stock_out_for_restaurant_order(
                order_id,
                item_id,
                quantity,
                reason=reason or None
            )
            print(
                f"Restaurant Order {order_id} linked to Inventory "
                f"Transaction {transaction_id}."
            )
        except ValueError as exc:
            print(f"Error: {exc}")


def stock_adjustment(
    item_id,
    adjustment_type,
    quantity,
    reason,
    reference_no=None
):
    """Apply a controlled positive/negative stock adjustment atomically."""
    _require_inventory_permission("Update")
    hotel_id = get_current_hotel_id()
    item_id = str(item_id or "").strip().upper()
    adjustment_type = str(adjustment_type or "").strip().upper()

    if not item_id:
        raise ValueError("Item ID cannot be empty.")
    if adjustment_type not in {"INCREASE", "DECREASE"}:
        raise ValueError("Adjustment type must be Increase or Decrease.")

    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError("Adjustment quantity must be a whole number greater than zero.") from exc

    if quantity <= 0:
        raise ValueError("Adjustment quantity must be greater than zero.")

    reason = " ".join(str(reason or "").strip().split())
    if not reason:
        raise ValueError("Adjustment Reason is required.")

    reference_no = (
        str(reference_no).strip()
        if reference_no is not None and str(reference_no).strip()
        else None
    )

    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.cursor()

        item = cursor.execute("""
            SELECT item_name, unit, quantity, cost_price, status
            FROM inventory
            WHERE hotel_id = ?
              AND item_id = ?
        """, (hotel_id, item_id)).fetchone()

        if item is None:
            raise ValueError("Item Not Found.")
        if item["status"] != "Active":
            raise ValueError("Inactive Item cannot be adjusted.")

        before_quantity = int(item["quantity"] or 0)
        if adjustment_type == "INCREASE":
            after_quantity = before_quantity + quantity
        else:
            if quantity > before_quantity:
                raise ValueError(
                    f"Adjustment would create negative stock. Available: "
                    f"{before_quantity} {item['unit']}."
                )
            after_quantity = before_quantity - quantity

        effective_cost = float(item["cost_price"] or 0)
        total_value = quantity * effective_cost
        now = _current_timestamp()

        cursor.execute("""
            UPDATE inventory
            SET quantity = ?, updated_at = ?
            WHERE hotel_id = ?
              AND item_id = ?
              AND status = 'Active'
        """, (after_quantity, now, hotel_id, item_id))

        if cursor.rowcount != 1:
            raise ValueError("Stock Adjustment could not be completed. Please try again.")

        actor_user_id, actor_username, actor_role = _get_inventory_actor()

        cursor.execute("""
            INSERT INTO inventory_transactions(
                hotel_id, item_id, transaction_type, quantity, price,
                transaction_date, reference_no, reason,
                before_quantity, after_quantity, total_value,
                actor_user_id, actor_username, actor_role
            )
            VALUES(?, ?, 'ADJUSTMENT', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hotel_id,
            item_id,
            quantity if adjustment_type == "INCREASE" else -quantity,
            effective_cost,
            now,
            reference_no,
            f"{adjustment_type}: {reason}",
            before_quantity,
            after_quantity,
            total_value,
            actor_user_id,
            actor_username,
            actor_role
        ))

        try:
            from database.notification_db import record_low_stock_notification_if_needed
            record_low_stock_notification_if_needed(
                cursor,
                hotel_id,
                item_id,
                before_quantity,
                after_quantity,
                item_name=item["item_name"],
                unit=item["unit"],
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        transaction_id = cursor.lastrowid
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Inventory",
        action="CREATE",
        local_values=locals(),
        details="Business operation stock_adjustment completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        print("Stock Adjustment Completed Successfully.")
        print("Transaction ID  :", transaction_id)
        print("Item ID         :", item_id)
        print("Adjustment Type :", adjustment_type)
        print("Quantity        :", quantity)
        print("Before Stock    :", before_quantity)
        print("After Stock     :", after_quantity)
        print("Unit Cost       :", f"{effective_cost:.2f}")
        print("Adjustment Value:", f"{total_value:.2f}")
        print("Reason          :", reason)
        if reference_no:
            print("Reference No    :", reference_no)

        return transaction_id

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def damaged_stock(
    item_id,
    quantity,
    reference_no=None,
    reason=None
):
    _require_inventory_permission("Update")
    """Record damaged stock and reduce usable stock atomically.

    Damaged quantity is tracked separately on the item master while the
    movement is recorded in the central inventory transaction ledger.
    """
    hotel_id = get_current_hotel_id()
    item_id = str(item_id or "").strip().upper()

    if not item_id:
        raise ValueError("Item ID cannot be empty.")

    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError("Damaged quantity must be a whole number greater than zero.") from exc

    if quantity <= 0:
        raise ValueError("Damaged quantity must be greater than zero.")

    reference_no = (
        str(reference_no).strip()
        if reference_no is not None and str(reference_no).strip()
        else None
    )
    reason = (
        " ".join(str(reason).strip().split())
        if reason is not None and str(reason).strip()
        else None
    )
    if not reason:
        raise ValueError("Damage Reason is required.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        item = cursor.execute("""
            SELECT quantity, damaged_quantity, cost_price, unit, status
            FROM inventory
            WHERE hotel_id = ? AND item_id = ?
        """, (hotel_id, item_id)).fetchone()

        if item is None:
            raise ValueError("Item Not Found.")
        if item["status"] != "Active":
            raise ValueError("Inactive Item cannot be marked as damaged stock.")

        before_quantity = int(item["quantity"] or 0)
        if quantity > before_quantity:
            raise ValueError(
                f"Damaged quantity cannot exceed available stock. Available: "
                f"{before_quantity} {item['unit']}."
            )

        before_damaged = int(item["damaged_quantity"] or 0)
        after_quantity = before_quantity - quantity
        after_damaged = before_damaged + quantity
        unit_cost = float(item["cost_price"] or 0)
        total_value = quantity * unit_cost
        now = _current_timestamp()

        cursor.execute("""
            UPDATE inventory
            SET quantity = ?, damaged_quantity = ?, updated_at = ?
            WHERE hotel_id = ? AND item_id = ? AND status = 'Active'
        """, (
            after_quantity, after_damaged, now, hotel_id, item_id
        ))
        if cursor.rowcount != 1:
            raise ValueError("Damaged Stock could not be recorded. Please try again.")

        actor_user_id, actor_username, actor_role = _get_inventory_actor()

        cursor.execute("""
            INSERT INTO inventory_transactions(
                hotel_id, item_id, transaction_type, quantity, price,
                transaction_date, reference_no, reason,
                before_quantity, after_quantity, total_value,
                actor_user_id, actor_username, actor_role
            )
            VALUES(?, ?, 'DAMAGED STOCK', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hotel_id, item_id, -quantity, unit_cost, now,
            reference_no, reason, before_quantity, after_quantity, total_value,
            actor_user_id, actor_username, actor_role
        ))

        try:
            from database.notification_db import record_low_stock_notification_if_needed
            record_low_stock_notification_if_needed(
                cursor,
                hotel_id,
                item_id,
                before_quantity,
                after_quantity,
                unit=item["unit"],
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        transaction_id = cursor.lastrowid
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Inventory",
        action="CREATE",
        local_values=locals(),
        details="Business operation damaged_stock completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        print("Damaged Stock Recorded Successfully.")
        print("Transaction ID  :", transaction_id)
        print("Item ID         :", item_id)
        print("Damaged Qty     :", quantity, item["unit"])
        print("Usable Stock    :", f"{before_quantity} -> {after_quantity}")
        print("Damaged Total   :", f"{before_damaged} -> {after_damaged}")
        print("Unit Cost       :", f"{unit_cost:.2f}")
        print("Damage Value    :", f"{total_value:.2f}")
        print("Reason          :", reason)
        if reference_no:
            print("Reference No    :", reference_no)
        return transaction_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_low_stock_items(threshold=None, *, user_id=None, hotel_id=None):
    """Return low-stock items using either the legacy session or an explicit AI auth context."""
    if user_id is None:
        _require_inventory_permission("View")
        hotel_id = get_current_hotel_id()
    else:
        from database.permission_db import has_permission
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        if not has_permission(user_id, "Inventory", "View"):
            raise PermissionError("Permission denied: Inventory - View.")
    """Return active inventory items at or below their item-specific reorder level."""
    if threshold is not None:
        try:
            threshold = int(threshold)
        except (TypeError, ValueError):
            raise ValueError("Low stock threshold must be a whole number.")
        if threshold < 0:
            raise ValueError("Low stock threshold cannot be negative.")

    connection = get_connection()

    try:
        if threshold is None:
            return connection.execute("""
                SELECT
                    item_id, item_name, unit, quantity, reorder_level,
                    cost_price, (quantity * cost_price) AS stock_value
                FROM inventory
                WHERE hotel_id = ?
                  AND status = 'Active'
                  AND quantity <= reorder_level
                ORDER BY quantity ASC, item_name COLLATE NOCASE ASC
            """, (hotel_id,)).fetchall()

        return connection.execute("""
            SELECT
                item_id, item_name, unit, quantity, reorder_level,
                cost_price, (quantity * cost_price) AS stock_value
            FROM inventory
            WHERE hotel_id = ?
              AND status = 'Active'
              AND quantity <= ?
            ORDER BY quantity ASC, item_name COLLATE NOCASE ASC
        """, (hotel_id, threshold)).fetchall()
    finally:
        connection.close()


def update_reorder_level(item_id, reorder_level):
    _require_inventory_permission("Update")
    """Update the item-specific reorder level for the current hotel."""
    hotel_id = get_current_hotel_id()
    item_id = str(item_id or "").strip().upper()
    try:
        reorder_level = int(reorder_level)
    except (TypeError, ValueError) as exc:
        raise ValueError("Reorder level must be a whole number.") from exc
    if reorder_level < 0:
        raise ValueError("Reorder level cannot be negative.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        item = cursor.execute("""
            SELECT item_id FROM inventory
            WHERE hotel_id = ? AND item_id = ?
        """, (hotel_id, item_id)).fetchone()
        if item is None:
            raise ValueError("Item Not Found.")
        cursor.execute("""
            UPDATE inventory
            SET reorder_level = ?, updated_at = ?
            WHERE hotel_id = ? AND item_id = ?
        """, (reorder_level, _current_timestamp(), hotel_id, item_id))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Inventory",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_reorder_level completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def reorder_level_management():
    _require_inventory_permission("Update")
    """Display and update item-specific reorder levels."""
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT item_id, item_name, quantity, unit, reorder_level, status
            FROM inventory
            WHERE hotel_id = ?
            ORDER BY item_name COLLATE NOCASE, item_id
        """, (hotel_id,)).fetchall()
    finally:
        connection.close()

    print("=" * 92)
    print("                         REORDER LEVEL MANAGEMENT")
    print("=" * 92)
    if not rows:
        print("No Inventory Items Found.")
        return

    print(f"{'Item ID':<12} {'Item Name':<28} {'Stock':>8} {'Unit':<10} {'Reorder':>10} {'Status':<10}")
    print("-" * 92)
    for row in rows:
        print(f"{row['item_id']:<12} {str(row['item_name'])[:27]:<28} {int(row['quantity'] or 0):>8} {str(row['unit'])[:9]:<10} {int(row['reorder_level'] or 0):>10} {row['status']:<10}")

    item_id = input("Enter Item ID to update (blank to return) : ").strip().upper()
    if not item_id:
        return
    selected = next((r for r in rows if r['item_id'] == item_id), None)
    if selected is None:
        raise ValueError("Item Not Found.")
    print(f"Current Reorder Level : {int(selected['reorder_level'] or 0)} {selected['unit']}")
    raw = input("New Reorder Level : ").strip()
    if not raw:
        raise ValueError("Reorder Level is required.")
    update_reorder_level(item_id, raw)
    print("Reorder Level Updated Successfully.")


def low_stock_alert():
    _require_inventory_permission("View")
    """Display active items whose stock is at or below their reorder level."""
    rows = get_low_stock_items()

    print("=" * 108)
    print("                         LOW STOCK ALERT")
    print("=" * 108)
    print("Alert Rule : Current Stock <= Item Reorder Level")
    print("-" * 108)

    if not rows:
        print("No Low Stock Items.")
        print("All active inventory items are above their reorder levels.")
        return

    print(f"{'Item ID':<12} {'Item Name':<25} {'Stock':>8} {'Reorder':>10} {'Unit':<10} {'Cost':>12} {'Stock Value':>16} {'Level':<10}")
    print("-" * 108)
    for item in rows:
        quantity = int(item['quantity'] or 0)
        reorder_level = int(item['reorder_level'] or 0)
        cost_price = float(item['cost_price'] or 0)
        stock_value = float(item['stock_value'] or 0)
        level = "CRITICAL" if quantity <= 0 else "LOW"
        print(f"{str(item['item_id']):<12} {str(item['item_name'])[:24]:<25} {quantity:>8} {reorder_level:>10} {str(item['unit'])[:9]:<10} {cost_price:>12.2f} {stock_value:>16.2f} {level:<10}")
    print("-" * 108)
    print(f"Total Low Stock Items : {len(rows)}")

def expiry_foundation():
    _require_inventory_permission("Update")
    """Display and manage the Phase 4.9.10 item-level expiry foundation."""
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT
                item_id, item_name, quantity, unit, cost_price,
                expiry_date, status
            FROM inventory
            WHERE hotel_id = ?
            ORDER BY
                CASE WHEN expiry_date IS NULL OR trim(expiry_date) = '' THEN 1 ELSE 0 END,
                expiry_date ASC,
                item_name COLLATE NOCASE ASC
        """, (hotel_id,)).fetchall()
    finally:
        connection.close()

    print("=" * 104)
    print("                         EXPIRY FOUNDATION")
    print("=" * 104)
    if not rows:
        print("No Inventory Items Found.")
        return

    print(
        f"{'Item ID':<12} {'Item Name':<26} {'Stock':>8} "
        f"{'Unit':<10} {'Expiry Date':<14} {'Expiry Status':<18} {'Stock Value':>14}"
    )
    print("-" * 104)
    for row in rows:
        qty = int(row["quantity"] or 0)
        cost = float(row["cost_price"] or 0)
        status = get_expiry_status(row["expiry_date"])
        print(
            f"{row['item_id']:<12} {str(row['item_name'])[:25]:<26} "
            f"{qty:>8} {str(row['unit'])[:9]:<10} "
            f"{(row['expiry_date'] or 'Not Set'):<14} {status:<18} "
            f"{qty * cost:>14.2f}"
        )
    print("-" * 104)
    print(f"Near Expiry Window : {EXPIRY_NEAR_DAYS} days")
    print("Expiry status is derived from the expiry date; it is not stored as stale data.")


def set_expiry_date(item_id, expiry_date):
    _require_inventory_permission("Update")
    hotel_id = get_current_hotel_id()
    item_id = str(item_id or "").strip().upper()
    normalized = _normalize_expiry_date(expiry_date)
    if not item_id:
        raise ValueError("Item ID cannot be empty.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        item = cursor.execute("SELECT item_id FROM inventory WHERE hotel_id = ? AND item_id = ?", (hotel_id, item_id)).fetchone()
        if not item:
            raise ValueError("Inventory Item Not Found.")
        cursor.execute("UPDATE inventory SET expiry_date = ?, updated_at = ? WHERE hotel_id = ? AND item_id = ?", (normalized, _current_timestamp(), hotel_id, item_id))
        connection.commit()
        return {"item_id": item_id, "expiry_date": normalized}
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()

def update_expiry_date():
    _require_inventory_permission("Update")
    """Set, update, or clear an inventory item's optional expiry date."""
    hotel_id = get_current_hotel_id()
    item_id = input("Enter Item ID : ").strip().upper()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        item = cursor.execute("""
            SELECT item_id, item_name, quantity, unit, expiry_date
            FROM inventory
            WHERE hotel_id = ? AND item_id = ?
        """, (hotel_id, item_id)).fetchone()
        if item is None:
            raise ValueError("Item Not Found.")

        print("Item Name       :", item["item_name"])
        print("Current Stock   :", item["quantity"], item["unit"])
        print("Current Expiry  :", item["expiry_date"] or "Not Set")
        raw = input("Enter Expiry Date (DD-MM-YYYY) or CLEAR : ").strip()
        if raw.upper() == "CLEAR":
            expiry_date = None
        else:
            expiry_date = _normalize_expiry_date(raw)
            if expiry_date is None:
                raise ValueError("Expiry Date cannot be blank in this option. Use CLEAR to remove it.")

        cursor.execute("""
            UPDATE inventory
            SET expiry_date = ?, updated_at = ?
            WHERE hotel_id = ? AND item_id = ?
        """, (expiry_date, _current_timestamp(), hotel_id, item_id))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Inventory",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_expiry_date completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Expiry Date Updated Successfully.")
        print("Expiry Date      :", expiry_date or "Not Set")
        print("Expiry Status    :", get_expiry_status(expiry_date))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def stock_history():
    _require_inventory_permission("View")
    """Display the central inventory stock ledger for the current hotel."""
    hotel_id = get_current_hotel_id()

    print("=" * 100)
    print("                           STOCK HISTORY")
    print("=" * 100)
    print("1. All Stock History")
    print("2. Item-wise History")
    print("3. Transaction-type History")
    print("4. Back")

    choice = input("Select Option : ").strip()
    if choice == "4":
        return

    connection = get_connection()
    try:
        conditions = ["t.hotel_id = ?"]
        params = [hotel_id]

        if choice == "2":
            item_id = input("Enter Item ID : ").strip().upper()
            if not item_id:
                raise ValueError("Item ID is required.")
            conditions.append("t.item_id = ?")
            params.append(item_id)
        elif choice == "3":
            print("Transaction Types: OPENING STOCK, STOCK IN, STOCK OUT, ADJUSTMENT, DAMAGED STOCK")
            transaction_type = input("Enter Transaction Type : ").strip().upper()
            if not transaction_type:
                raise ValueError("Transaction Type is required.")
            conditions.append("UPPER(t.transaction_type) = ?")
            params.append(transaction_type)
        elif choice != "1":
            raise ValueError("Invalid Stock History option.")

        records = connection.execute(f"""
            SELECT
                t.transaction_id,
                t.item_id,
                i.item_name,
                i.unit,
                t.transaction_type,
                t.quantity,
                t.price,
                t.transaction_date,
                t.supplier_id,
                s.supplier_name,
                t.reference_no,
                t.reason,
                t.before_quantity,
                t.after_quantity,
                t.total_value,
                t.batch_id,
                t.batch_no,
                t.lot_no,
                t.actor_user_id,
                t.actor_username,
                t.actor_role
            FROM inventory_transactions t
            JOIN inventory i
              ON i.item_id = t.item_id
             AND i.hotel_id = t.hotel_id
            LEFT JOIN suppliers s
              ON s.supplier_id = t.supplier_id
            WHERE {" AND ".join(conditions)}
            ORDER BY t.transaction_id DESC
        """, params).fetchall()

        if not records:
            print("No Stock History Found.")
            return

        for record in records:
            print("-" * 100)
            print("Transaction ID :", record["transaction_id"])
            print("Item ID        :", record["item_id"])
            print("Item Name      :", record["item_name"])
            print("Type           :", record["transaction_type"])
            print("Quantity       :", record["quantity"], record["unit"])
            print("Cost Price     :", f"{float(record['price'] or 0):.2f}")
            print("Total Value    :", f"{float(record['total_value'] or 0):.2f}")
            print("Before Stock   :", record["before_quantity"] if record["before_quantity"] is not None else "N/A")
            print("After Stock    :", record["after_quantity"] if record["after_quantity"] is not None else "N/A")
            print("Batch / Lot    :", f"{record['batch_no'] or '-'} / {record['lot_no'] or '-'}")
            print("Supplier       :", record["supplier_name"] or record["supplier_id"] or "Not Assigned")
            print("Reference No   :", record["reference_no"] or "N/A")
            print("Reason         :", record["reason"] or "N/A")
            print("Performed By   :", record["actor_username"] or record["actor_user_id"] or "SYSTEM")
            print("Actor Role     :", record["actor_role"] or "System")
            print("Date / Time    :", record["transaction_date"])

        print("-" * 100)
        print("Total Transactions :", len(records))
    finally:
        connection.close()


def get_inventory_valuation(*, user_id=None, hotel_id=None):
    """Return item-wise inventory valuation using the legacy session or explicit AI auth context."""
    if user_id is None:
        _require_inventory_permission("View")
        hotel_id = get_current_hotel_id()
    else:
        from database.permission_db import has_permission
        if hotel_id is None:
            hotel_id = get_current_hotel_id()
        if not has_permission(user_id, "Inventory", "View"):
            raise PermissionError("Permission denied: Inventory - View.")
    connection = get_connection()
    try:
        return connection.execute("""
            SELECT
                item_id, item_name, category, category_id, unit,
                quantity, damaged_quantity, cost_price,
                (quantity * cost_price) AS stock_value,
                (damaged_quantity * cost_price) AS damaged_value,
                ((quantity + damaged_quantity) * cost_price) AS total_tracked_value,
                status
            FROM inventory
            WHERE hotel_id = ?
            ORDER BY item_name COLLATE NOCASE ASC, item_id ASC
        """, (hotel_id,)).fetchall()
    finally:
        connection.close()


def inventory_valuation():
    _require_inventory_permission("View")
    """Display current usable-stock and damaged-stock valuation."""
    rows = get_inventory_valuation()
    print("=" * 132)
    print("                         INVENTORY VALUATION")
    print("=" * 132)

    if not rows:
        print("No Inventory Items Found.")
        return

    total_usable = 0.0
    total_damaged = 0.0

    print(
        f"{'Item ID':<12} {'Item Name':<24} {'Qty':>8} {'Damaged':>9} "
        f"{'Unit':<9} {'Cost':>12} {'Stock Value':>15} "
        f"{'Damaged Value':>16} {'Status':<10}"
    )
    print("-" * 132)

    for row in rows:
        qty = int(row["quantity"] or 0)
        damaged = int(row["damaged_quantity"] or 0)
        cost = float(row["cost_price"] or 0)
        stock_value = float(row["stock_value"] or 0)
        damaged_value = float(row["damaged_value"] or 0)
        status = str(row["status"] or "")

        if status.strip().lower() == "active":
            total_usable += stock_value
            total_damaged += damaged_value

        print(
            f"{str(row['item_id']):<12} {str(row['item_name'])[:23]:<24} "
            f"{qty:>8} {damaged:>9} {str(row['unit'])[:8]:<9} "
            f"{cost:>12.2f} {stock_value:>15.2f} "
            f"{damaged_value:>16.2f} {status:<10}"
        )

    print("-" * 132)
    print(f"Total Usable Stock Value  : {total_usable:.2f}")
    print(f"Total Damaged Stock Value : {total_damaged:.2f}")
    print(f"Total Inventory Value     : {(total_usable + total_damaged):.2f}")
    print()
    print("Valuation Rule: Current Quantity × Current Cost Price.")
    print("Damaged stock is shown separately from usable stock.")

def purchase_history():
    _require_inventory_permission("View")
    """Backward-compatible alias for the Stock History screen."""
    return stock_history()
