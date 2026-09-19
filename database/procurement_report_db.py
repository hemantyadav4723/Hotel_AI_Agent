from database.database import get_connection
from database.hotel_context import get_current_hotel_id
from database.permission_db import require_current_user_permission


def procurement_report():
    """Show a current-hotel procurement summary across supplier, PO, receiving and payable data."""
    require_current_user_permission("Reports", "View")
    hotel_id = get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()

        suppliers = cursor.execute(
            """
            SELECT
                s.supplier_id,
                s.supplier_name,
                s.status,
                (SELECT COUNT(*)
                   FROM purchase_orders po
                  WHERE po.hotel_id = s.hotel_id
                    AND po.supplier_id = s.supplier_id) AS po_count,
                (SELECT COALESCE(SUM(po.grand_total), 0)
                   FROM purchase_orders po
                  WHERE po.hotel_id = s.hotel_id
                    AND po.supplier_id = s.supplier_id) AS po_value,
                (SELECT COUNT(*)
                   FROM purchase_receivings pr
                  WHERE pr.hotel_id = s.hotel_id
                    AND pr.supplier_id = s.supplier_id) AS receiving_count,
                (SELECT COALESCE(SUM(pr.total_value), 0)
                   FROM purchase_receivings pr
                  WHERE pr.hotel_id = s.hotel_id
                    AND pr.supplier_id = s.supplier_id) AS received_value,
                (SELECT COALESCE(SUM(sp.amount), 0)
                   FROM supplier_payments sp
                  WHERE sp.hotel_id = s.hotel_id
                    AND sp.supplier_id = s.supplier_id) AS paid_amount,
                COALESCE((
                    SELECT pt.payment_type
                      FROM supplier_payment_terms pt
                     WHERE pt.hotel_id = s.hotel_id
                       AND pt.supplier_id = s.supplier_id
                     LIMIT 1
                ), 'Cash') AS payment_type,
                COALESCE((
                    SELECT pt.credit_days
                      FROM supplier_payment_terms pt
                     WHERE pt.hotel_id = s.hotel_id
                       AND pt.supplier_id = s.supplier_id
                     LIMIT 1
                ), 0) AS credit_days
            FROM suppliers s
            WHERE s.hotel_id = ?
            ORDER BY s.supplier_name COLLATE NOCASE
            """,
            (hotel_id,),
        ).fetchall()

        print("=" * 110)
        print("                         PROCUREMENT REPORT".center(110))
        print("=" * 110)
        if not suppliers:
            print("No Supplier / Procurement Records Found.")
            print("=" * 110)
            return

        total_po_value = 0.0
        total_received = 0.0
        total_paid = 0.0

        for row in suppliers:
            received_value = float(row["received_value"] or 0)
            paid_amount = float(row["paid_amount"] or 0)
            outstanding = round(received_value - paid_amount, 2)

            print("-" * 110)
            print("Supplier ID       :", row["supplier_id"])
            print("Supplier Name     :", row["supplier_name"])
            print("Status            :", row["status"])
            print("Purchase Orders   :", row["po_count"])
            print("PO Value          :", f"₹{float(row['po_value'] or 0):.2f}")
            print("Receivings        :", row["receiving_count"])
            print("Received Value    :", f"₹{received_value:.2f}")
            print("Paid Amount       :", f"₹{paid_amount:.2f}")
            print("Outstanding       :", f"₹{outstanding:.2f}")
            print("Payment Terms     :", f"{row['payment_type']} | {int(row['credit_days'] or 0)} days")

            total_po_value += float(row["po_value"] or 0)
            total_received += received_value
            total_paid += paid_amount

        print("-" * 110)
        print("TOTAL PO VALUE    :", f"₹{total_po_value:.2f}")
        print("TOTAL RECEIVED    :", f"₹{total_received:.2f}")
        print("TOTAL PAID        :", f"₹{total_paid:.2f}")
        print("TOTAL OUTSTANDING :", f"₹{total_received - total_paid:.2f}")
        print("=" * 110)
    finally:
        connection.close()
