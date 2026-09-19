from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


def _current_timestamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _normalize_optional(value):
    value = str(value or "").strip()
    return value or None


def _normalize_date(value, field_name):
    value = _normalize_optional(value)
    if value is None:
        return None
    try:
        parsed = datetime.strptime(value, "%d-%m-%Y")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be in DD-MM-YYYY format.") from exc
    return parsed.strftime("%d-%m-%Y")


def create_inventory_batches_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_batches(
                batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL DEFAULT 1,
                item_id TEXT NOT NULL,
                batch_no TEXT,
                lot_no TEXT,
                received_date TEXT,
                expiry_date TEXT,
                quantity_received INTEGER NOT NULL DEFAULT 0,
                current_quantity INTEGER NOT NULL DEFAULT 0,
                cost_price REAL NOT NULL DEFAULT 0,
                supplier_id TEXT,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(hotel_id, item_id, batch_no, lot_no),
                FOREIGN KEY(hotel_id) REFERENCES hotels(hotel_id)
                    ON UPDATE CASCADE ON DELETE RESTRICT,
                FOREIGN KEY(item_id) REFERENCES inventory(item_id)
                    ON UPDATE CASCADE ON DELETE RESTRICT,
                FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id)
                    ON UPDATE CASCADE ON DELETE RESTRICT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_batches_item
            ON inventory_batches(hotel_id, item_id, batch_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_batches_expiry
            ON inventory_batches(hotel_id, expiry_date, current_quantity)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_inventory_batches_batch
            ON inventory_batches(hotel_id, batch_no, lot_no)
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_batch_nonnegative_qty
            BEFORE INSERT ON inventory_batches
            WHEN NEW.quantity_received < 0 OR NEW.current_quantity < 0
            BEGIN SELECT RAISE(ABORT, 'Batch quantities cannot be negative.'); END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_inventory_batch_update_nonnegative_qty
            BEFORE UPDATE OF quantity_received, current_quantity ON inventory_batches
            WHEN NEW.quantity_received < 0 OR NEW.current_quantity < 0
            BEGIN SELECT RAISE(ABORT, 'Batch quantities cannot be negative.'); END;
        """)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_or_receive_batch(
    item_id,
    quantity,
    cost_price,
    batch_no=None,
    lot_no=None,
    received_date=None,
    expiry_date=None,
    supplier_id=None,
    connection=None,
):
    """Create or increase a batch/lot record during Stock In."""
    own_connection = connection is None
    connection = connection or get_connection()
    try:
        hotel_id = get_current_hotel_id()
        item_id = str(item_id or "").strip().upper()
        batch_no = _normalize_optional(batch_no)
        lot_no = _normalize_optional(lot_no)
        received_date = _normalize_date(received_date, "Received Date") or datetime.now().strftime("%d-%m-%Y")
        expiry_date = _normalize_date(expiry_date, "Expiry Date")
        quantity = int(quantity)
        cost_price = float(cost_price)
        if quantity <= 0:
            raise ValueError("Batch Quantity must be greater than zero.")
        if cost_price < 0:
            raise ValueError("Batch Cost Price cannot be negative.")
        if not batch_no and not lot_no:
            raise ValueError("Batch No or Lot No is required when creating a batch record.")

        cursor = connection.cursor()
        item = cursor.execute(
            "SELECT 1 FROM inventory WHERE hotel_id = ? AND item_id = ? AND status = 'Active'",
            (hotel_id, item_id),
        ).fetchone()
        if item is None:
            raise ValueError("Invalid or inactive Inventory Item.")

        existing = cursor.execute("""
            SELECT batch_id, current_quantity
            FROM inventory_batches
            WHERE hotel_id = ? AND item_id = ?
              AND COALESCE(batch_no, '') = COALESCE(?, '')
              AND COALESCE(lot_no, '') = COALESCE(?, '')
        """, (hotel_id, item_id, batch_no, lot_no)).fetchone()

        now = _current_timestamp()
        if existing:
            new_qty = int(existing["current_quantity"] or 0) + quantity
            cursor.execute("""
                UPDATE inventory_batches
                SET current_quantity = ?,
                    quantity_received = quantity_received + ?,
                    received_date = COALESCE(?, received_date),
                    expiry_date = COALESCE(?, expiry_date),
                    cost_price = ?,
                    supplier_id = COALESCE(?, supplier_id),
                    status = 'Active',
                    updated_at = ?
                WHERE hotel_id = ? AND batch_id = ?
            """, (new_qty, quantity, received_date, expiry_date, cost_price,
                  supplier_id, now, hotel_id, existing["batch_id"]))
            batch_id = existing["batch_id"]
        else:
            cursor.execute("""
                INSERT INTO inventory_batches(
                    hotel_id, item_id, batch_no, lot_no, received_date,
                    expiry_date, quantity_received, current_quantity,
                    cost_price, supplier_id, status, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)
            """, (hotel_id, item_id, batch_no, lot_no, received_date,
                  expiry_date, quantity, quantity, cost_price, supplier_id,
                  now, now))
            batch_id = cursor.lastrowid

        if own_connection:
            connection.commit()
        return batch_id
    except Exception:
        if own_connection:
            connection.rollback()
        raise
    finally:
        if own_connection:
            connection.close()


def view_batches():
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT b.*, i.item_name, i.unit
            FROM inventory_batches b
            JOIN inventory i ON i.item_id = b.item_id AND i.hotel_id = b.hotel_id
            WHERE b.hotel_id = ?
            ORDER BY b.batch_id DESC
        """, (hotel_id,)).fetchall()
        print("                         BATCH / LOT RECORDS")
        print("-" * 120)
        if not rows:
            print("No Batch / Lot Records Found.")
            return rows
        for row in rows:
            print(
                f"ID: {row['batch_id']} | Item: {row['item_id']} - {row['item_name']} | "
                f"Batch: {row['batch_no'] or '-'} | Lot: {row['lot_no'] or '-'} | "
                f"Qty: {row['current_quantity']} {row['unit']} | "
                f"Expiry: {row['expiry_date'] or 'Not Set'} | Status: {row['status']}"
            )
        print("-" * 120)
        return rows
    finally:
        connection.close()


def search_batch():
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    term = input("Enter Batch No / Lot No / Item ID : ").strip()
    if not term:
        raise ValueError("Search value is required.")
    connection = get_connection()
    try:
        like = f"%{term}%"
        rows = connection.execute("""
            SELECT b.*, i.item_name, i.unit
            FROM inventory_batches b
            JOIN inventory i ON i.item_id = b.item_id AND i.hotel_id = b.hotel_id
            WHERE b.hotel_id = ?
              AND (b.batch_no LIKE ? OR b.lot_no LIKE ? OR b.item_id LIKE ? OR i.item_name LIKE ?)
            ORDER BY b.batch_id DESC
        """, (hotel_id, like, like, like, like)).fetchall()
        if not rows:
            print("No Batch / Lot Records Found.")
            return rows
        for row in rows:
            print(
                f"Batch ID: {row['batch_id']} | Item: {row['item_id']} - {row['item_name']} | "
                f"Batch: {row['batch_no'] or '-'} | Lot: {row['lot_no'] or '-'} | "
                f"Current Qty: {row['current_quantity']} {row['unit']} | "
                f"Expiry: {row['expiry_date'] or 'Not Set'} | Status: {row['status']}"
            )
        return rows
    finally:
        connection.close()


def batch_lot_management():
    require_current_user_permission("Inventory", "View")
    while True:
        print("\n========== BATCH / LOT FOUNDATION ==========")
        print("1. View Batch / Lot Records")
        print("2. Search Batch / Lot")
        print("3. Back")
        choice = input("Enter Your Choice : ").strip()
        if choice == "1":
            view_batches()
        elif choice == "2":
            try:
                search_batch()
            except ValueError as exc:
                print(f"Error: {exc}")
        elif choice == "3":
            break
        else:
            print("Invalid Choice.")
