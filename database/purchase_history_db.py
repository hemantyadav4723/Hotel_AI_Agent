from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


def _print_purchase_history(rows):
    if not rows:
        print("No Purchase History Found.")
        return

    print("=" * 100)
    print("                                      PURCHASE HISTORY")
    print("=" * 100)

    for row in rows:
        print("-" * 100)
        print("Record Type         :", row["record_type"])
        print("Date                :", row["record_date"])
        print("PO Number           :", row["po_id"])
        print("Supplier            :", f'{row["supplier_id"]} - {row["supplier_name"]}')
        print("Item                :", f'{row["item_id"]} - {row["item_name"]}')
        print("Quantity            :", f'{row["quantity"]:g} {row["unit"]}')
        print("Unit Cost           :", f'{row["unit_cost"]:.2f}')
        print("Tax Rate            :", f'{row["tax_rate"]:.2f}%' if row["tax_rate"] is not None else "-")
        print("Amount              :", f'{row["amount"]:.2f}')
        print("Status              :", row["status"])
        print("Reference           :", row["reference_no"] or "-")
        if row["record_type"] == "RECEIVING":
            print("Receiving ID        :", row["receiving_id"] or "-")
            print("Batch No            :", row["batch_no"] or "-")
            print("Lot No              :", row["lot_no"] or "-")
            print("Inventory Txn ID    :", row["inventory_transaction_id"] or "-")
        print("Created By          :", row["created_by"] or "-")
    print("=" * 100)


def _history_query(cursor, hotel_id, where_clause="", params=()):
    query = f"""
        SELECT
            'PURCHASE ORDER' AS record_type,
            po.po_date AS record_date,
            po.po_id,
            po.supplier_id,
            s.supplier_name,
            poi.item_id,
            poi.item_name,
            poi.unit,
            poi.quantity,
            poi.unit_cost,
            poi.tax_rate,
            poi.line_total AS amount,
            po.status,
            po.notes AS reference_no,
            NULL AS receiving_id,
            NULL AS batch_no,
            NULL AS lot_no,
            NULL AS inventory_transaction_id,
            po.created_by
        FROM purchase_orders po
        JOIN suppliers s
          ON s.supplier_id = po.supplier_id
         AND s.hotel_id = po.hotel_id
        JOIN purchase_order_items poi
          ON poi.po_id = po.po_id
         AND poi.hotel_id = po.hotel_id
        WHERE po.hotel_id = ?
        {where_clause}

        UNION ALL

        SELECT
            'RECEIVING' AS record_type,
            pr.receiving_date AS record_date,
            pr.po_id,
            pr.supplier_id,
            s.supplier_name,
            pri.item_id,
            pri.item_name,
            pri.unit,
            pri.received_quantity AS quantity,
            pri.unit_cost,
            NULL AS tax_rate,
            pri.line_total AS amount,
            'Received' AS status,
            pr.reference_no,
            pr.receiving_id,
            pri.batch_no,
            pri.lot_no,
            pri.inventory_transaction_id,
            pr.received_by AS created_by
        FROM purchase_receivings pr
        JOIN suppliers s
          ON s.supplier_id = pr.supplier_id
         AND s.hotel_id = pr.hotel_id
        JOIN purchase_receiving_items pri
          ON pri.receiving_id = pr.receiving_id
         AND pri.hotel_id = pr.hotel_id
        WHERE pr.hotel_id = ?
        {where_clause.replace("po.", "pr.").replace("poi.", "pri.").replace("s.", "s.")}
        ORDER BY record_date DESC, 3 DESC, 1
    """
    # The UNION has the same filter shape twice.
    return cursor.execute(query, (hotel_id, *params, hotel_id, *params)).fetchall()


def view_purchase_history():
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = _history_query(connection.cursor(), hotel_id)
        _print_purchase_history(rows)
    finally:
        connection.close()


def search_purchase_history_by_po(po_id):
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    po_id = str(po_id or "").strip().upper()
    connection = get_connection()
    try:
        rows = _history_query(
            connection.cursor(),
            hotel_id,
            "AND po.po_id = ?",
            (po_id,)
        )
        _print_purchase_history(rows)
    finally:
        connection.close()


def search_purchase_history_by_supplier(supplier_id):
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    supplier_id = str(supplier_id or "").strip().upper()
    connection = get_connection()
    try:
        rows = _history_query(
            connection.cursor(),
            hotel_id,
            "AND po.supplier_id = ?",
            (supplier_id,)
        )
        _print_purchase_history(rows)
    finally:
        connection.close()


def search_purchase_history_by_item(item_id):
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    item_id = str(item_id or "").strip().upper()
    connection = get_connection()
    try:
        rows = _history_query(
            connection.cursor(),
            hotel_id,
            "AND poi.item_id = ?",
            (item_id,)
        )
        _print_purchase_history(rows)
    finally:
        connection.close()


def view_purchase_receiving_history():
    require_current_user_permission("Inventory", "View")
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        rows = connection.execute("""
            SELECT
                'RECEIVING' AS record_type,
                pr.receiving_date AS record_date,
                pr.po_id,
                pr.supplier_id,
                s.supplier_name,
                pri.item_id,
                pri.item_name,
                pri.unit,
                pri.received_quantity AS quantity,
                pri.unit_cost,
                NULL AS tax_rate,
                pri.line_total AS amount,
                'Received' AS status,
                pr.reference_no,
                pr.receiving_id,
                pri.batch_no,
                pri.lot_no,
                pri.inventory_transaction_id,
                pr.received_by AS created_by
            FROM purchase_receivings pr
            JOIN suppliers s
              ON s.supplier_id = pr.supplier_id
             AND s.hotel_id = pr.hotel_id
            JOIN purchase_receiving_items pri
              ON pri.receiving_id = pr.receiving_id
             AND pri.hotel_id = pr.hotel_id
            WHERE pr.hotel_id = ?
            ORDER BY pr.receiving_date DESC, pr.receiving_id DESC
        """, (hotel_id,)).fetchall()
        _print_purchase_history(rows)
    finally:
        connection.close()


def purchase_history_management():
    require_current_user_permission("Inventory", "View")
    from utils.validators import validate_menu_choice, validate_non_empty

    while True:
        print("=" * 72)
        print("                     PURCHASE HISTORY")
        print("=" * 72)
        print("1. All Purchase History")
        print("2. PO-wise History")
        print("3. Supplier-wise History")
        print("4. Item-wise History")
        print("5. Purchase Receiving History")
        print("6. Back")

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6"]
        )

        try:
            if choice == "1":
                view_purchase_history()
            elif choice == "2":
                po_id = validate_non_empty("Enter PO Number : ").strip().upper()
                search_purchase_history_by_po(po_id)
            elif choice == "3":
                supplier_id = validate_non_empty("Enter Supplier ID : ").strip().upper()
                search_purchase_history_by_supplier(supplier_id)
            elif choice == "4":
                item_id = validate_non_empty("Enter Item ID : ").strip().upper()
                search_purchase_history_by_item(item_id)
            elif choice == "5":
                view_purchase_receiving_history()
            else:
                break
        except (ValueError, PermissionError) as exc:
            print(f"Error: {exc}")
