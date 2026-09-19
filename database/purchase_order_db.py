from utils.error_logging import log_non_blocking_error
from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


def _timestamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def create_purchase_order_tables():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders(
                po_id TEXT NOT NULL,
                hotel_id INTEGER NOT NULL,
                supplier_id TEXT NOT NULL,
                po_date TEXT NOT NULL,
                expected_delivery_date TEXT,
                status TEXT NOT NULL DEFAULT 'Draft',
                notes TEXT,
                subtotal REAL NOT NULL DEFAULT 0,
                tax_amount REAL NOT NULL DEFAULT 0,
                grand_total REAL NOT NULL DEFAULT 0,
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(po_id, hotel_id),
                FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id)
                    ON UPDATE CASCADE ON DELETE RESTRICT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_order_items(
                po_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_id TEXT NOT NULL,
                hotel_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                unit TEXT NOT NULL,
                quantity REAL NOT NULL CHECK(quantity > 0),
                unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
                tax_rate REAL NOT NULL DEFAULT 0 CHECK(tax_rate >= 0 AND tax_rate <= 100),
                line_subtotal REAL NOT NULL CHECK(line_subtotal >= 0),
                line_tax REAL NOT NULL CHECK(line_tax >= 0),
                line_total REAL NOT NULL CHECK(line_total >= 0),
                FOREIGN KEY(po_id, hotel_id) REFERENCES purchase_orders(po_id, hotel_id)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_hotel_date ON purchase_orders(hotel_id, po_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_hotel_supplier ON purchase_orders(hotel_id, supplier_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_order_items_po ON purchase_order_items(hotel_id, po_id)")
        connection.commit()
    finally:
        connection.close()


def _supplier(cursor, supplier_id, hotel_id):
    return cursor.execute("""
        SELECT supplier_id, supplier_name, status
        FROM suppliers
        WHERE supplier_id = ? AND hotel_id = ?
    """, (supplier_id, hotel_id)).fetchone()


def _inventory_item(cursor, item_id, hotel_id):
    return cursor.execute("""
        SELECT item_id, item_name, unit, status, cost_price
        FROM inventory
        WHERE item_id = ? AND hotel_id = ?
    """, (item_id, hotel_id)).fetchone()


def create_purchase_order(po_id, supplier_id, po_date, expected_delivery_date=None, notes=None, items=None, created_by=None):
    require_current_user_permission("Inventory", "Create")
    hotel_id = get_current_hotel_id()
    items = items or []
    if not items:
        raise ValueError("Purchase Order must contain at least one item.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        supplier = _supplier(cursor, supplier_id, hotel_id)
        if not supplier:
            raise ValueError("Supplier Not Found for the current hotel.")
        if supplier["status"] != "Active":
            raise ValueError("Inactive supplier cannot be used for a new Purchase Order.")
        if cursor.execute("SELECT 1 FROM purchase_orders WHERE po_id=? AND hotel_id=?", (po_id, hotel_id)).fetchone():
            raise ValueError("Purchase Order ID already exists.")

        subtotal = 0.0
        tax_amount = 0.0
        normalized = []
        for entry in items:
            item_id = str(entry["item_id"]).strip().upper()
            quantity = float(entry["quantity"])
            unit_cost = float(entry["unit_cost"])
            tax_rate = float(entry.get("tax_rate", 0) or 0)
            if quantity <= 0:
                raise ValueError("Purchase quantity must be greater than zero.")
            if unit_cost < 0:
                raise ValueError("Unit cost cannot be negative.")
            if tax_rate < 0 or tax_rate > 100:
                raise ValueError("Tax rate must be between 0 and 100.")
            item = _inventory_item(cursor, item_id, hotel_id)
            if not item or item["status"] != "Active":
                raise ValueError(f"Invalid or inactive Inventory Item: {item_id}.")
            line_subtotal = round(quantity * unit_cost, 2)
            line_tax = round(line_subtotal * tax_rate / 100, 2)
            line_total = round(line_subtotal + line_tax, 2)
            subtotal += line_subtotal
            tax_amount += line_tax
            normalized.append((item_id, item["item_name"], item["unit"], quantity, unit_cost, tax_rate, line_subtotal, line_tax, line_total))

        now = _timestamp()
        grand_total = round(subtotal + tax_amount, 2)
        cursor.execute("""
            INSERT INTO purchase_orders(
                po_id, hotel_id, supplier_id, po_date, expected_delivery_date,
                status, notes, subtotal, tax_amount, grand_total, created_by, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, 'Draft', ?, ?, ?, ?, ?, ?, ?)
        """, (po_id, hotel_id, supplier_id, po_date, expected_delivery_date, notes, round(subtotal,2), round(tax_amount,2), grand_total, created_by, now, now))
        for row in normalized:
            cursor.execute("""
                INSERT INTO purchase_order_items(
                    po_id, hotel_id, item_id, item_name, unit, quantity, unit_cost, tax_rate,
                    line_subtotal, line_tax, line_total
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (po_id, hotel_id, *row))
        connection.commit()
        return {"po_id": po_id, "subtotal": round(subtotal,2), "tax_amount": round(tax_amount,2), "grand_total": grand_total}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def view_purchase_orders():
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        orders = connection.execute("""
            SELECT po.*, s.supplier_name
            FROM purchase_orders po
            JOIN suppliers s ON s.supplier_id=po.supplier_id AND s.hotel_id=po.hotel_id
            WHERE po.hotel_id=?
            ORDER BY po.po_date DESC, po.created_at DESC
        """, (hotel_id,)).fetchall()
        if not orders:
            print("No Purchase Orders Found.")
            return
        for po in orders:
            print("=" * 72)
            print("PO Number           :", po["po_id"])
            print("Supplier            :", f'{po["supplier_id"]} - {po["supplier_name"]}')
            print("PO Date             :", po["po_date"])
            print("Expected Delivery   :", po["expected_delivery_date"] or "Not Provided")
            print("Status              :", po["status"])
            print("Subtotal            :", f'{float(po["subtotal"]):.2f}')
            print("Tax                 :", f'{float(po["tax_amount"]):.2f}')
            print("Grand Total         :", f'{float(po["grand_total"]):.2f}')
            print("Notes               :", po["notes"] or "-")
            items = connection.execute("""SELECT * FROM purchase_order_items WHERE po_id=? AND hotel_id=? ORDER BY po_item_id""", (po["po_id"], hotel_id)).fetchall()
            for item in items:
                print(f'  - {item["item_id"]} | {item["item_name"]} | {item["quantity"]} {item["unit"]} | Rate {float(item["unit_cost"]):.2f} | Tax {float(item["tax_rate"]):.2f}% | Total {float(item["line_total"]):.2f}')
        print("=" * 72)
    finally:
        connection.close()


def search_purchase_order(po_id):
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        po = connection.execute("""SELECT po.*, s.supplier_name FROM purchase_orders po JOIN suppliers s ON s.supplier_id=po.supplier_id AND s.hotel_id=po.hotel_id WHERE po.po_id=? AND po.hotel_id=?""", (po_id.strip().upper(), hotel_id)).fetchone()
        if not po:
            print("Purchase Order Not Found.")
            return
        print("=" * 72)
        print("PO Number         :", po["po_id"])
        print("Supplier          :", f'{po["supplier_id"]} - {po["supplier_name"]}')
        print("PO Date           :", po["po_date"])
        print("Expected Delivery :", po["expected_delivery_date"] or "Not Provided")
        print("Status            :", po["status"])
        print("Subtotal          :", f'{float(po["subtotal"]):.2f}')
        print("Tax               :", f'{float(po["tax_amount"]):.2f}')
        print("Grand Total       :", f'{float(po["grand_total"]):.2f}')
        print("Notes             :", po["notes"] or "-")
        print("ITEMS")
        items = connection.execute("SELECT * FROM purchase_order_items WHERE po_id=? AND hotel_id=? ORDER BY po_item_id", (po["po_id"], hotel_id)).fetchall()
        for item in items:
            print(f'{item["item_id"]} | {item["item_name"]} | {item["quantity"]} {item["unit"]} | Rate {float(item["unit_cost"]):.2f} | Tax {float(item["tax_rate"]):.2f}% | Total {float(item["line_total"]):.2f}')
        print("=" * 72)
    finally:
        connection.close()


def update_purchase_order_status(po_id, new_status):
    allowed = {"Draft", "Approved", "Cancelled"}
    if new_status == "Approved":
        require_current_user_permission("Inventory", "Approve")
    elif new_status == "Cancelled":
        require_current_user_permission("Inventory", "Cancel")
    else:
        require_current_user_permission("Inventory", "Update")
    if new_status not in allowed:
        raise ValueError("Invalid Purchase Order status.")
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        po = cursor.execute("SELECT status FROM purchase_orders WHERE po_id=? AND hotel_id=?", (po_id.strip().upper(), hotel_id)).fetchone()
        if not po:
            raise ValueError("Purchase Order Not Found.")
        current = po["status"]
        if current == "Cancelled" and new_status != "Cancelled":
            raise ValueError("Cancelled Purchase Order cannot be reopened.")
        if current == "Approved" and new_status == "Draft":
            raise ValueError("Approved Purchase Order cannot be moved back to Draft.")
        if current == new_status:
            print(f"Purchase Order is already {new_status}.")
            return
        cursor.execute("UPDATE purchase_orders SET status=?, updated_at=? WHERE po_id=? AND hotel_id=?", (new_status, _timestamp(), po_id.strip().upper(), hotel_id))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Purchase Order",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation update_purchase_order_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print(f"Purchase Order {new_status} Successfully.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def purchase_order_management():
    require_current_user_permission("Inventory", "View")
    from utils.validators import (
        validate_menu_choice, validate_non_empty, validate_optional_date,
        validate_positive_number, validate_percentage
    )
    from database.supplier_db import view_supplier
    from database.inventory_db import get_active_item_options

    while True:
        print("=" * 72)
        print("                     PURCHASE ORDER MANAGEMENT")
        print("=" * 72)
        print("1. Create Purchase Order")
        print("2. View Purchase Orders")
        print("3. Search Purchase Order")
        print("4. Update PO Status")
        print("5. Back")
        choice = validate_menu_choice("Enter Your Choice : ", ["1","2","3","4","5"])
        if choice == "1":
            try:
                require_current_user_permission("Inventory", "Create")
                po_id = validate_non_empty("Enter PO Number : ").strip().upper()
                view_supplier()
                supplier_id = validate_non_empty("Enter Supplier ID : ").strip().upper()
                po_date = validate_non_empty("PO Date (DD-MM-YYYY) : ").strip()
                # Validate supplied date without changing the stored display format.
                from datetime import datetime as _dt
                _dt.strptime(po_date, "%d-%m-%Y")
                expected_delivery_date = validate_optional_date("Expected Delivery Date (optional, DD-MM-YYYY) : ")
                notes = input("Notes / Reference (optional) : ").strip() or None
                items = []
                while True:
                    options = get_active_item_options()
                    if not options:
                        raise ValueError("No active Inventory Items found.")
                    print("Available Active Inventory Items:")
                    for item in options:
                        print(f'{item["item_id"]} - {item["item_name"]} | Unit: {item["unit"]} | Current Cost: {float(item["cost_price"] or 0):.2f}')
                    item_id = validate_non_empty("Enter Item ID : ").strip().upper()
                    selected = next((x for x in options if x["item_id"] == item_id), None)
                    if not selected:
                        raise ValueError("Invalid or inactive Inventory Item.")
                    quantity = validate_positive_number(f'Enter Quantity ({selected["unit"]}) : ')
                    unit_cost = validate_positive_number("Enter Unit Cost : ")
                    tax_rate = validate_percentage("Enter Tax Rate (%) : ")
                    items.append({"item_id": item_id, "quantity": quantity, "unit_cost": unit_cost, "tax_rate": tax_rate})
                    more = input("Add another item? (Y/N) : ").strip().upper()
                    if more != "Y":
                        break
                result = create_purchase_order(po_id, supplier_id, po_date, expected_delivery_date, notes, items)
                print(f'Purchase Order Created Successfully. PO: {result["po_id"]}')
                print(f'Subtotal: {result["subtotal"]:.2f} | Tax: {result["tax_amount"]:.2f} | Grand Total: {result["grand_total"]:.2f}')
            except (ValueError, PermissionError) as exc:
                print(f"Error: {exc}")
        elif choice == "2":
            view_purchase_orders()
        elif choice == "3":
            try:
                po_id = validate_non_empty("Enter PO Number : ").strip().upper()
                search_purchase_order(po_id)
            except ValueError as exc:
                print(f"Error: {exc}")
        elif choice == "4":
            try:
                po_id = validate_non_empty("Enter PO Number : ").strip().upper()
                print("1. Draft")
                print("2. Approved")
                print("3. Cancelled")
                status_choice = validate_menu_choice("Enter New Status : ", ["1","2","3"])
                status = {"1":"Draft","2":"Approved","3":"Cancelled"}[status_choice]
                update_purchase_order_status(po_id, status)
            except (ValueError, PermissionError) as exc:
                print(f"Error: {exc}")
        else:
            break
