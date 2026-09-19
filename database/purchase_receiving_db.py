from datetime import datetime

from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission
from database.inventory_db import stock_in


from database.audit_db import log_business_activity
def _timestamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _parse_date(value, field):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        datetime.strptime(value, "%d-%m-%Y")
    except ValueError as exc:
        raise ValueError(f"{field} must be in DD-MM-YYYY format.") from exc
    return value


def create_purchase_receiving_tables():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_receivings(
                receiving_id TEXT NOT NULL,
                hotel_id INTEGER NOT NULL,
                po_id TEXT NOT NULL,
                supplier_id TEXT NOT NULL,
                receiving_date TEXT NOT NULL,
                reference_no TEXT,
                notes TEXT,
                total_value REAL NOT NULL DEFAULT 0 CHECK(total_value >= 0),
                received_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(receiving_id, hotel_id),
                FOREIGN KEY(po_id, hotel_id)
                    REFERENCES purchase_orders(po_id, hotel_id)
                    ON UPDATE CASCADE ON DELETE RESTRICT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_receiving_items(
                receiving_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                receiving_id TEXT NOT NULL,
                hotel_id INTEGER NOT NULL,
                po_id TEXT NOT NULL,
                po_item_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                unit TEXT NOT NULL,
                received_quantity REAL NOT NULL CHECK(received_quantity > 0),
                unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
                line_total REAL NOT NULL CHECK(line_total >= 0),
                batch_id INTEGER,
                batch_no TEXT,
                lot_no TEXT,
                expiry_date TEXT,
                inventory_transaction_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(receiving_id, hotel_id)
                    REFERENCES purchase_receivings(receiving_id, hotel_id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
                FOREIGN KEY(po_id, hotel_id)
                    REFERENCES purchase_orders(po_id, hotel_id)
                    ON UPDATE CASCADE ON DELETE RESTRICT
            )
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_purchase_receiving_item_po
            ON purchase_receiving_items(hotel_id, receiving_id, po_item_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_purchase_receivings_hotel_po
            ON purchase_receivings(hotel_id, po_id, receiving_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_purchase_receiving_items_po
            ON purchase_receiving_items(hotel_id, po_id, po_item_id)
        """)
        connection.commit()
    finally:
        connection.close()


def _po_header(cursor, po_id, hotel_id):
    return cursor.execute("""
        SELECT po.*, s.supplier_name, s.status AS supplier_status
        FROM purchase_orders po
        JOIN suppliers s
          ON s.supplier_id = po.supplier_id
         AND s.hotel_id = po.hotel_id
        WHERE po.po_id = ? AND po.hotel_id = ?
    """, (po_id, hotel_id)).fetchone()


def _po_item(cursor, po_id, po_item_id, hotel_id):
    return cursor.execute("""
        SELECT *
        FROM purchase_order_items
        WHERE po_id = ? AND po_item_id = ? AND hotel_id = ?
    """, (po_id, po_item_id, hotel_id)).fetchone()


def _received_for_po_item(cursor, po_id, po_item_id, hotel_id):
    row = cursor.execute("""
        SELECT COALESCE(SUM(received_quantity), 0) AS received_quantity
        FROM purchase_receiving_items
        WHERE po_id = ? AND po_item_id = ? AND hotel_id = ?
    """, (po_id, po_item_id, hotel_id)).fetchone()
    return float(row["received_quantity"] or 0)


def _next_receiving_id(cursor, hotel_id):
    prefix = "GRN-"
    rows = cursor.execute("""
        SELECT receiving_id
        FROM purchase_receivings
        WHERE hotel_id = ? AND receiving_id LIKE ?
        ORDER BY receiving_id DESC
    """, (hotel_id, f"{prefix}%")).fetchall()
    max_no = 0
    for row in rows:
        try:
            max_no = max(max_no, int(str(row["receiving_id"])[4:]))
        except (ValueError, TypeError):
            continue
    return f"{prefix}{max_no + 1:05d}"


def create_purchase_receiving(
    po_id,
    receiving_date,
    items,
    reference_no=None,
    notes=None,
    received_by=None,
):
    require_current_user_permission("Inventory", "Create")
    hotel_id = get_current_hotel_id()
    po_id = str(po_id or "").strip().upper()
    receiving_date = _parse_date(receiving_date, "Receiving Date")
    if not po_id:
        raise ValueError("Purchase Order ID is required.")
    if not receiving_date:
        raise ValueError("Receiving Date is required.")
    if not items:
        raise ValueError("At least one Purchase Order item must be received.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        po = _po_header(cursor, po_id, hotel_id)
        if not po:
            raise ValueError("Purchase Order Not Found.")
        if po["status"] == "Cancelled":
            raise ValueError("Cancelled Purchase Order cannot be received.")
        if po["status"] not in ("Approved", "Partially Received"):
            raise ValueError("Only Approved Purchase Orders can be received.")
        if po["supplier_status"] != "Active":
            raise ValueError("Inactive Supplier cannot be used for Purchase Receiving.")

        normalized = []
        total_value = 0.0
        seen = set()

        for entry in items:
            po_item_id = int(entry["po_item_id"])
            if po_item_id in seen:
                raise ValueError("The same Purchase Order item cannot be received twice in one receipt.")
            seen.add(po_item_id)

            po_item = _po_item(cursor, po_id, po_item_id, hotel_id)
            if not po_item:
                raise ValueError(f"Invalid Purchase Order Item: {po_item_id}.")

            try:
                quantity = int(entry["quantity"])
            except (TypeError, ValueError) as exc:
                raise ValueError("Received quantity must be a whole number greater than zero.") from exc
            if quantity <= 0:
                raise ValueError("Received quantity must be greater than zero.")

            already_received = _received_for_po_item(cursor, po_id, po_item_id, hotel_id)
            pending = float(po_item["quantity"]) - already_received
            if quantity > pending + 1e-9:
                raise ValueError(
                    f"Receiving quantity exceeds pending quantity for {po_item['item_id']}. "
                    f"Pending: {pending:g} {po_item['unit']}."
                )

            unit_cost = float(entry.get("unit_cost", po_item["unit_cost"]))
            if unit_cost < 0:
                raise ValueError("Receiving unit cost cannot be negative.")

            batch_no = str(entry.get("batch_no") or "").strip() or None
            lot_no = str(entry.get("lot_no") or "").strip() or None
            expiry_date = _parse_date(entry.get("expiry_date"), "Batch Expiry Date")

            line_total = round(quantity * unit_cost, 2)
            total_value += line_total
            normalized.append({
                "po_item_id": po_item_id,
                "item_id": po_item["item_id"],
                "item_name": po_item["item_name"],
                "unit": po_item["unit"],
                "quantity": quantity,
                "unit_cost": unit_cost,
                "line_total": line_total,
                "batch_no": batch_no,
                "lot_no": lot_no,
                "expiry_date": expiry_date,
            })

        receiving_id = str(
            normalized and items and items[0].get("receiving_id") or ""
        ).strip().upper()
        if not receiving_id:
            receiving_id = _next_receiving_id(cursor, hotel_id)

        if cursor.execute("""
            SELECT 1 FROM purchase_receivings
            WHERE receiving_id = ? AND hotel_id = ?
        """, (receiving_id, hotel_id)).fetchone():
            raise ValueError("Receiving ID already exists.")

        now = _timestamp()
        cursor.execute("""
            INSERT INTO purchase_receivings(
                receiving_id, hotel_id, po_id, supplier_id, receiving_date,
                reference_no, notes, total_value, received_by, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            receiving_id, hotel_id, po_id, po["supplier_id"], receiving_date,
            str(reference_no or "").strip() or None,
            str(notes or "").strip() or None,
            round(total_value, 2),
            received_by,
            now, now,
        ))

        for row in normalized:
            # Reuse the existing atomic Inventory Stock In path. It receives
            # the same connection so inventory, ledger, batch and receipt
            # records commit or roll back together.
            tx_id = stock_in(
                row["item_id"],
                row["quantity"],
                unit_cost=row["unit_cost"],
                supplier_id=po["supplier_id"],
                reference_no=f"PO:{po_id} / GRN:{receiving_id}",
                reason=f"Purchase Receiving against {po_id}",
                batch_no=row["batch_no"],
                lot_no=row["lot_no"],
                batch_expiry_date=row["expiry_date"],
                connection=connection,
            )

            batch_id = None
            batch_no = row["batch_no"]
            lot_no = row["lot_no"]
            if batch_no or lot_no:
                batch_row = cursor.execute("""
                    SELECT batch_id
                    FROM inventory_batches
                    WHERE hotel_id = ? AND item_id = ?
                      AND COALESCE(batch_no, '') = COALESCE(?, '')
                      AND COALESCE(lot_no, '') = COALESCE(?, '')
                    ORDER BY batch_id DESC LIMIT 1
                """, (hotel_id, row["item_id"], batch_no, lot_no)).fetchone()
                batch_id = batch_row["batch_id"] if batch_row else None

            cursor.execute("""
                INSERT INTO purchase_receiving_items(
                    receiving_id, hotel_id, po_id, po_item_id, item_id,
                    item_name, unit, received_quantity, unit_cost, line_total,
                    batch_id, batch_no, lot_no, expiry_date,
                    inventory_transaction_id, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                receiving_id, hotel_id, po_id, row["po_item_id"], row["item_id"],
                row["item_name"], row["unit"], row["quantity"], row["unit_cost"],
                row["line_total"], batch_id, batch_no, lot_no, row["expiry_date"],
                tx_id, now,
            ))

        # Determine PO receiving state after this receipt.
        po_items = cursor.execute("""
            SELECT po_item_id, quantity
            FROM purchase_order_items
            WHERE po_id = ? AND hotel_id = ?
        """, (po_id, hotel_id)).fetchall()

        fully_received = True
        for po_item in po_items:
            received = _received_for_po_item(
                cursor, po_id, po_item["po_item_id"], hotel_id
            )
            if received + 1e-9 < float(po_item["quantity"]):
                fully_received = False
                break

        new_status = "Fully Received" if fully_received else "Partially Received"
        cursor.execute("""
            UPDATE purchase_orders
            SET status = ?, updated_at = ?
            WHERE po_id = ? AND hotel_id = ?
        """, (new_status, now, po_id, hotel_id))

        connection.commit()
        log_business_activity(
            "Purchase Receiving",
            "CREATE",
            local_values={"receiving_id": receiving_id, "po_id": po_id, "supplier_id": po["supplier_id"]},
            details=f"Purchase receiving {receiving_id} created for PO {po_id}.",
        )
        print("Purchase Receiving Created Successfully.")
        print("Receiving ID     :", receiving_id)
        print("Purchase Order   :", po_id)
        print("Supplier         :", po["supplier_id"], "-", po["supplier_name"])
        print("Total Value      :", f"{total_value:.2f}")
        print("PO Status        :", new_status)
        return receiving_id

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def view_purchase_receivings():
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT r.*, s.supplier_name
            FROM purchase_receivings r
            JOIN suppliers s
              ON s.supplier_id = r.supplier_id
             AND s.hotel_id = r.hotel_id
            WHERE r.hotel_id = ?
            ORDER BY r.receiving_date DESC, r.created_at DESC
        """, (hotel_id,)).fetchall()

        print("=" * 90)
        print("                         PURCHASE RECEIVING")
        print("=" * 90)
        if not rows:
            print("No Purchase Receiving Records Found.")
            return rows

        for row in rows:
            print("Receiving ID     :", row["receiving_id"])
            print("Purchase Order   :", row["po_id"])
            print("Supplier         :", f'{row["supplier_id"]} - {row["supplier_name"]}')
            print("Receiving Date   :", row["receiving_date"])
            print("Reference        :", row["reference_no"] or "-")
            print("Total Value      :", f'{float(row["total_value"]):.2f}')
            print("Received By      :", row["received_by"] or "-")
            print("Notes            :", row["notes"] or "-")
            items = connection.execute("""
                SELECT *
                FROM purchase_receiving_items
                WHERE receiving_id = ? AND hotel_id = ?
                ORDER BY receiving_item_id
            """, (row["receiving_id"], hotel_id)).fetchall()
            for item in items:
                print(
                    f'  - {item["item_id"]} | {item["item_name"]} | '
                    f'{float(item["received_quantity"]):g} {item["unit"]} | '
                    f'Rate {float(item["unit_cost"]):.2f} | '
                    f'Total {float(item["line_total"]):.2f} | '
                    f'Batch {item["batch_no"] or "-"} | Lot {item["lot_no"] or "-"} | '
                    f'TX {item["inventory_transaction_id"]}'
                )
            print("-" * 90)
        return rows
    finally:
        connection.close()


def search_purchase_receiving(term):
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    term = str(term or "").strip().upper()
    if not term:
        raise ValueError("Search value is required.")

    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT r.*, s.supplier_name
            FROM purchase_receivings r
            JOIN suppliers s
              ON s.supplier_id = r.supplier_id
             AND s.hotel_id = r.hotel_id
            WHERE r.hotel_id = ?
              AND (
                    UPPER(r.receiving_id) LIKE ?
                 OR UPPER(r.po_id) LIKE ?
                 OR UPPER(r.supplier_id) LIKE ?
                 OR UPPER(COALESCE(r.reference_no, '')) LIKE ?
              )
            ORDER BY r.receiving_date DESC, r.created_at DESC
        """, (hotel_id, f"%{term}%", f"%{term}%", f"%{term}%", f"%{term}%")).fetchall()

        if not rows:
            print("Purchase Receiving Not Found.")
            return rows

        for row in rows:
            print(
                f'{row["receiving_id"]} | PO {row["po_id"]} | '
                f'{row["supplier_id"]} - {row["supplier_name"]} | '
                f'{row["receiving_date"]} | Total {float(row["total_value"]):.2f}'
            )
        return rows
    finally:
        connection.close()


def purchase_receiving_management():
    require_current_user_permission("Inventory", "View")
    from utils.validators import validate_menu_choice, validate_non_empty, validate_positive_number, validate_quantity, validate_optional_date
    from database.purchase_order_db import view_purchase_orders

    while True:
        print("=" * 90)
        print("                     PURCHASE RECEIVING MANAGEMENT")
        print("=" * 90)
        print("1. Create Purchase Receiving")
        print("2. View Purchase Receiving")
        print("3. Search Purchase Receiving")
        print("4. Back")
        choice = validate_menu_choice("Enter Your Choice : ", ["1", "2", "3", "4"])

        if choice == "1":
            try:
                require_current_user_permission("Inventory", "Create")
                po_id = validate_non_empty("Enter Approved PO Number : ").strip().upper()
                connection = get_connection()
                try:
                    hotel_id = get_current_hotel_id()
                    po = _po_header(connection.cursor(), po_id, hotel_id)
                    if not po:
                        raise ValueError("Purchase Order Not Found.")
                    if po["status"] not in ("Approved", "Partially Received"):
                        raise ValueError("Only Approved or Partially Received Purchase Orders can be received.")
                    print("Purchase Order:", po_id)
                    print("Supplier:", po["supplier_id"], "-", po["supplier_name"])
                    po_items = connection.execute("""
                        SELECT *
                        FROM purchase_order_items
                        WHERE po_id = ? AND hotel_id = ?
                        ORDER BY po_item_id
                    """, (po_id, hotel_id)).fetchall()
                    if not po_items:
                        raise ValueError("Purchase Order has no items.")
                    for item in po_items:
                        received = _received_for_po_item(
                            connection.cursor(), po_id, item["po_item_id"], hotel_id
                        )
                        pending = float(item["quantity"]) - received
                        print(
                            f'{item["po_item_id"]} - {item["item_id"]} - {item["item_name"]} | '
                            f'Ordered {float(item["quantity"]):g} {item["unit"]} | '
                            f'Received {received:g} | Pending {pending:g}'
                        )
                finally:
                    connection.close()

                receiving_date = validate_non_empty("Receiving Date (DD-MM-YYYY) : ").strip()
                _parse_date(receiving_date, "Receiving Date")
                reference_no = input("GRN / Invoice Reference (optional) : ").strip() or None
                notes = input("Notes (optional) : ").strip() or None
                entries = []
                while True:
                    po_item_id = int(validate_non_empty("Enter PO Item ID : ").strip())
                    quantity = validate_quantity("Enter Received Quantity : ")
                    unit_cost = validate_positive_number("Enter Receiving Unit Cost : ")
                    batch_no = input("Batch No (optional) : ").strip() or None
                    lot_no = input("Lot No (optional) : ").strip() or None
                    expiry_date = validate_optional_date(
                        "Batch Expiry Date (optional, DD-MM-YYYY) : "
                    )
                    entries.append({
                        "po_item_id": po_item_id,
                        "quantity": quantity,
                        "unit_cost": unit_cost,
                        "batch_no": batch_no,
                        "lot_no": lot_no,
                        "expiry_date": expiry_date,
                    })
                    more = input("Receive another PO item? (Y/N) : ").strip().upper()
                    if more != "Y":
                        break

                create_purchase_receiving(
                    po_id=po_id,
                    receiving_date=receiving_date,
                    items=entries,
                    reference_no=reference_no,
                    notes=notes,
                )

            except (ValueError, PermissionError) as exc:
                print(f"Error: {exc}")

        elif choice == "2":
            view_purchase_receivings()

        elif choice == "3":
            try:
                term = validate_non_empty("Enter Receiving ID / PO Number / Supplier / Reference : ")
                search_purchase_receiving(term)
            except ValueError as exc:
                print(f"Error: {exc}")
        else:
            break
