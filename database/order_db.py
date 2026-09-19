from utils.error_logging import log_non_blocking_error
import json

from database.database import get_connection


def create_orders_table():

    from database.hotel_context import get_current_hotel_id

    connection = get_connection()

    try:
        cursor = connection.cursor()
        from database.table_booking_db import ensure_table_assignments_table, record_table_assignment, release_table_assignment
        ensure_table_assignments_table(connection)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders(

                order_id TEXT PRIMARY KEY,
                invoice_number TEXT,
                advance_amount REAL NOT NULL DEFAULT 0,
                hotel_id INTEGER,
                customer_id TEXT,
                order_date TEXT,
                order_time TEXT,
                customer_name TEXT,
                customer_mobile TEXT,
                table_number TEXT,
                cart TEXT,
                subtotal REAL NOT NULL DEFAULT 0,
                gst REAL NOT NULL DEFAULT 0,
                grand_total REAL NOT NULL DEFAULT 0,
                discount REAL NOT NULL DEFAULT 0,
                order_status TEXT NOT NULL DEFAULT 'New',
                order_notes TEXT,
                payment_method TEXT,
                payment_status TEXT NOT NULL DEFAULT 'Pending',
                paid_amount REAL NOT NULL DEFAULT 0,
                balance_amount REAL NOT NULL DEFAULT 0,
                refund_amount REAL NOT NULL DEFAULT 0,
                settlement_adjustment REAL NOT NULL DEFAULT 0,
                cancellation_reason TEXT,
                cancelled_at TEXT

            )
        """)

        cursor.execute("PRAGMA table_info(orders)")

        columns = {
            row["name"]
            for row in cursor.fetchall()
        }

        migrations = {
            "invoice_number": "TEXT",
            "advance_amount": "REAL NOT NULL DEFAULT 0",
            "hotel_id": "INTEGER",
            "customer_id": "TEXT",
            "subtotal": "REAL NOT NULL DEFAULT 0",
            "gst": "REAL NOT NULL DEFAULT 0",
            "grand_total": "REAL NOT NULL DEFAULT 0",
            "discount": "REAL NOT NULL DEFAULT 0",
            "order_status": "TEXT NOT NULL DEFAULT 'New'",
            "order_notes": "TEXT",
            "payment_method": "TEXT",
            "payment_status": "TEXT NOT NULL DEFAULT 'Pending'",
            "paid_amount": "REAL NOT NULL DEFAULT 0",
            "balance_amount": "REAL NOT NULL DEFAULT 0",
            "refund_amount": "REAL NOT NULL DEFAULT 0",
            "settlement_adjustment": "REAL NOT NULL DEFAULT 0",
            "cancellation_reason": "TEXT",
            "cancelled_at": "TEXT",
        }

        for column_name, column_definition in migrations.items():
            if column_name not in columns:
                cursor.execute(
                    f"ALTER TABLE orders ADD COLUMN {column_name} {column_definition}"
                )

        hotel_id = get_current_hotel_id()

        cursor.execute("""
            UPDATE orders
            SET hotel_id = ?
            WHERE hotel_id IS NULL
        """, (hotel_id,))

        cursor.execute("""
            UPDATE orders
            SET customer_id = (
                SELECT c.customer_id
                FROM customers c
                WHERE c.customer_mobile = orders.customer_mobile
                ORDER BY c.created_time ASC
                LIMIT 1
            )
            WHERE (customer_id IS NULL OR TRIM(customer_id) = '')
              AND customer_mobile IS NOT NULL
              AND TRIM(customer_mobile) <> ''
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_customer_hotel
            ON orders(customer_id, hotel_id, order_date, order_time)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_hotel
            ON orders(hotel_id)
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_hotel_invoice
            ON orders(hotel_id, invoice_number)
            WHERE invoice_number IS NOT NULL
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_hotel_date
            ON orders(hotel_id, order_date, order_time)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_hotel_table
            ON orders(hotel_id, table_number, order_date, order_time)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_hotel_status
            ON orders(hotel_id, order_status, order_date, order_time)
        """)

        # Repair deterministic legacy payment-balance values introduced before
        # payment management existed. This does not alter paid/refund amounts.
        cursor.execute("""
            UPDATE orders
            SET balance_amount = CASE
                WHEN COALESCE(refund_amount, 0) > 0 THEN 0
                ELSE MAX(COALESCE(grand_total, 0) - COALESCE(paid_amount, 0), 0)
            END
            WHERE balance_amount IS NULL
               OR ABS(
                    COALESCE(balance_amount, 0) -
                    CASE
                        WHEN COALESCE(refund_amount, 0) > 0 THEN 0
                        ELSE MAX(COALESCE(grand_total, 0) - COALESCE(paid_amount, 0), 0)
                    END
               ) > 0.01
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()





def create_split_payment_table():
    """Create the split-payment allocation foundation for restaurant orders.

    Each allocation represents one payment component of an order.  The table
    is intentionally additive: existing payment/order APIs remain unchanged.
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS restaurant_split_payments (
                split_payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                order_id TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount >= 0),
                reference_number TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (hotel_id) REFERENCES hotels(hotel_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_restaurant_split_payments_order
            ON restaurant_split_payments (hotel_id, order_id, split_payment_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_restaurant_split_payments_method
            ON restaurant_split_payments (hotel_id, payment_method)
        """)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_split_payments(order_id, hotel_id=None):
    """Return split-payment allocations for one order."""
    hotel_id = _resolve_active_hotel_id(hotel_id)
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT split_payment_id, order_id, payment_method, amount,
                   reference_number, notes, created_at
            FROM restaurant_split_payments
            WHERE hotel_id = ? AND order_id = ?
            ORDER BY split_payment_id ASC
        """, (hotel_id, order_id))
        return cursor.fetchall()
    finally:
        connection.close()


def create_restaurant_payment_transactions_table():
    """Create the immutable restaurant payment/refund transaction ledger."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS restaurant_payment_transactions(
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                order_id TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                payment_method TEXT,
                amount REAL NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_restaurant_payment_txn_hotel_order
            ON restaurant_payment_transactions(hotel_id, order_id, transaction_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_restaurant_payment_txn_hotel_method
            ON restaurant_payment_transactions(hotel_id, payment_method, created_at)
        """)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def migrate_restaurant_payment_transactions():
    """Seed legacy paid/refunded order totals into the transaction ledger once."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT order_id, hotel_id, paid_amount, refund_amount, payment_method
            FROM orders
            WHERE COALESCE(paid_amount, 0) > 0 OR COALESCE(refund_amount, 0) > 0
        """)
        orders = cursor.fetchall()
        for order in orders:
            cursor.execute("""
                SELECT COUNT(*) AS count
                FROM restaurant_payment_transactions
                WHERE hotel_id = ? AND order_id = ?
            """, (order["hotel_id"], order["order_id"]))
            if int(cursor.fetchone()["count"] or 0) > 0:
                continue

            paid = float(order["paid_amount"] or 0)
            refund = float(order["refund_amount"] or 0)
            if paid > 0:
                _insert_payment_transaction(
                    cursor, order["hotel_id"], order["order_id"],
                    "PAYMENT", paid, order["payment_method"],
                    "Legacy order payment migrated to transaction ledger"
                )
            if refund > 0:
                _insert_payment_transaction(
                    cursor, order["hotel_id"], order["order_id"],
                    "REFUND", -refund, order["payment_method"],
                    "Legacy order refund migrated to transaction ledger"
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def _insert_payment_transaction(
    cursor, hotel_id, order_id, transaction_type, amount,
    payment_method=None, notes=None
):
    amount = round(float(amount), 2)
    cursor.execute("""
        INSERT INTO restaurant_payment_transactions(
            hotel_id, order_id, transaction_type, payment_method, amount, notes
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        hotel_id, order_id, str(transaction_type).strip().upper(),
        payment_method, amount, notes
    ))


def create_restaurant_order_audit_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS restaurant_order_audit(
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                order_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_order_audit_hotel_order
            ON restaurant_order_audit(hotel_id, order_id, created_at)
        """)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _write_order_audit(cursor, hotel_id, order_id, action, details=None):
    cursor.execute("""
        INSERT INTO restaurant_order_audit(
            hotel_id, order_id, action, details
        ) VALUES (?, ?, ?, ?)
    """, (hotel_id, order_id, action, details))


def _get_current_hotel_id():
    from database.hotel_context import get_current_hotel_id
    return get_current_hotel_id()


def _validate_cart(cart):
    if not isinstance(cart, list) or not cart:
        raise ValueError("Order cart cannot be empty.")

    for item in cart:
        if not isinstance(item, dict):
            raise ValueError("Invalid order item.")

        required = {"name", "price", "quantity", "subtotal"}
        if not required.issubset(item):
            raise ValueError("Invalid order item data.")

        if not str(item["name"]).strip():
            raise ValueError("Food item name cannot be empty.")

        try:
            price = float(item["price"])
            quantity = float(item["quantity"])
            item_subtotal = float(item["subtotal"])
        except (TypeError, ValueError):
            raise ValueError("Invalid order item amount.")

        if price < 0 or quantity <= 0 or item_subtotal < 0:
            raise ValueError("Invalid order item amount.")



def _resolve_active_hotel_id(hotel_id=None):
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    try:
        hotel_id = int(hotel_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid hotel context.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT hotel_id FROM hotels WHERE hotel_id = ? AND is_active = 1",
            (hotel_id,)
        )
        if cursor.fetchone() is None:
            raise ValueError("Hotel does not exist or is inactive.")
    finally:
        connection.close()

    return hotel_id


def _validate_cart_against_menu(cursor, cart, hotel_id):
    for item in cart:
        item_id = str(item.get("item_id") or "").strip()
        if not item_id:
            raise ValueError("Order item is missing a valid menu item ID.")

        cursor.execute(
            """
            SELECT item_id, category_id, item_name, price, is_available
            FROM restaurant_menu_items
            WHERE item_id = ? AND hotel_id = ?
            """,
            (item_id, hotel_id)
        )
        menu_item = cursor.fetchone()

        if menu_item is None:
            raise ValueError(
                "Order contains a menu item that does not belong to the current hotel."
            )

        if not menu_item["is_available"]:
            raise ValueError(
                f"Menu item '{menu_item['item_name']}' is currently unavailable."
            )

        try:
            price = float(item["price"])
            quantity = float(item["quantity"])
            item_subtotal = float(item["subtotal"])
            menu_price = float(menu_item["price"])
        except (TypeError, ValueError):
            raise ValueError("Invalid order item amount.")

        expected_subtotal = round(menu_price * quantity, 2)

        if abs(price - menu_price) > 0.001:
            raise ValueError(
                f"Menu price mismatch for '{menu_item['item_name']}'."
            )

        if abs(item_subtotal - expected_subtotal) > 0.01:
            raise ValueError(
                f"Item subtotal mismatch for '{menu_item['item_name']}'."
            )


def _validate_order_financials(
    cursor,
    cart,
    discount,
    gst,
    grand_total,
    hotel_id
):
    cursor.execute(
        "SELECT gst_rate FROM hotel_information WHERE hotel_id = ?",
        (hotel_id,)
    )
    hotel = cursor.fetchone()

    if hotel is None:
        raise ValueError("Hotel billing configuration not found.")

    try:
        gst_rate = float(hotel["gst_rate"])
        discount = float(discount)
        gst = float(gst)
        grand_total = float(grand_total)
    except (TypeError, ValueError):
        raise ValueError("Invalid billing amount.")

    calculated_subtotal = round(
        sum(float(item["subtotal"]) for item in cart),
        2
    )

    if discount < 0 or discount > calculated_subtotal:
        raise ValueError("Discount is outside the valid order range.")

    taxable = round(calculated_subtotal - discount, 2)
    expected_gst = round(taxable * gst_rate, 2)
    expected_grand_total = round(taxable + expected_gst, 2)

    if abs(gst - expected_gst) > 0.01:
        raise ValueError(
            "GST amount does not match the hotel's configured GST rate."
        )

    if abs(grand_total - expected_grand_total) > 0.01:
        raise ValueError(
            "Grand total does not match the order items and billing configuration."
        )

    return calculated_subtotal, expected_gst, expected_grand_total


def restaurant_security_integrity_report(hotel_id=None):
    hotel_id = _resolve_active_hotel_id(hotel_id)
    connection = get_connection()

    try:
        cursor = connection.cursor()
        checks = {
            "orders": 0,
            "hotel_isolation_issues": 0,
            "customer_order_relationship_issues": 0,
            "table_order_consistency_issues": 0,
            "payment_consistency_issues": 0,
            "foreign_key_violations": 0,
            "duplicate_order_issues": 0,
        }

        cursor.execute(
            "SELECT COUNT(*) AS total FROM orders WHERE hotel_id = ?",
            (hotel_id,)
        )
        checks["orders"] = int(cursor.fetchone()["total"] or 0)

        # Hotel isolation: restaurant orders must point to an existing hotel.
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM orders o
            LEFT JOIN hotels h ON h.hotel_id = o.hotel_id
            WHERE o.hotel_id = ?
              AND h.hotel_id IS NULL
        """, (hotel_id,))
        checks["hotel_isolation_issues"] = int(cursor.fetchone()["total"] or 0)

        # Customer/order relationship must be valid for the same hotel.
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            LEFT JOIN guest_hotel_relationships r
              ON r.customer_id = o.customer_id
             AND r.hotel_id = o.hotel_id
            WHERE o.hotel_id = ?
              AND (
                  (o.customer_id IS NOT NULL AND TRIM(o.customer_id) <> ''
                   AND c.customer_id IS NULL)
                  OR
                  (o.customer_id IS NOT NULL AND TRIM(o.customer_id) <> ''
                   AND r.relationship_id IS NULL)
              )
        """, (hotel_id,))
        checks["customer_order_relationship_issues"] = int(
            cursor.fetchone()["total"] or 0
        )

        # Table/order consistency: table must exist; active orders require an occupied table.
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM orders o
            LEFT JOIN tables t
              ON t.hotel_id = o.hotel_id
             AND UPPER(TRIM(t.table_number)) = UPPER(TRIM(o.table_number))
            WHERE o.hotel_id = ?
              AND o.table_number IS NOT NULL
              AND TRIM(o.table_number) <> ''
              AND (
                  t.table_id IS NULL
                  OR (
                      COALESCE(o.order_status, 'New')
                      IN ('New','Preparing','Ready','Served')
                      AND t.table_status <> 'Occupied'
                  )
              )
        """, (hotel_id,))
        checks["table_order_consistency_issues"] = int(
            cursor.fetchone()["total"] or 0
        )

        # Payment consistency: amounts, balance, and status must agree.
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM orders
            WHERE hotel_id = ?
              AND (
                  subtotal < 0
                  OR gst < 0
                  OR grand_total < 0
                  OR discount < 0
                  OR discount > subtotal + 0.01
                  OR paid_amount < 0
                  OR paid_amount > grand_total + 0.01
                  OR refund_amount < 0
                  OR refund_amount > paid_amount + 0.01
                  OR ABS(grand_total - (subtotal - discount + gst)) > 0.01
                  OR (refund_amount = 0 AND ABS(balance_amount - MAX(grand_total - paid_amount + COALESCE(settlement_adjustment, 0), 0)) > 0.01)
                  OR (refund_amount > 0 AND balance_amount < -0.01)
                  OR (payment_status = 'Pending' AND paid_amount > 0.01)
                  OR (payment_status = 'Partially Paid' AND (paid_amount <= 0.01 OR paid_amount >= grand_total - 0.01))
                  OR (payment_status = 'Paid' AND ABS(grand_total - paid_amount + COALESCE(settlement_adjustment, 0)) > 0.01)
                  OR (payment_status = 'Refunded' AND refund_amount < paid_amount - 0.01)
              )
        """, (hotel_id,))
        checks["payment_consistency_issues"] = int(
            cursor.fetchone()["total"] or 0
        )

        # SQLite foreign-key enforcement is enabled on every connection.
        cursor.execute("PRAGMA foreign_key_check")
        checks["foreign_key_violations"] = len(cursor.fetchall())

        # order_id is the PRIMARY KEY; this check documents duplicate prevention.
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM (
                SELECT order_id
                FROM orders
                GROUP BY order_id
                HAVING COUNT(*) > 1
            )
        """)
        checks["duplicate_order_issues"] = int(cursor.fetchone()["total"] or 0)

        checks["passed"] = all(
            value == 0
            for key, value in checks.items()
            if key != "orders"
        )
        return checks

    finally:
        connection.close()


def get_orders(hotel_id=None):
    hotel_id = _resolve_active_hotel_id(hotel_id)

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM orders
            WHERE hotel_id = ?
            ORDER BY rowid DESC
        """, (hotel_id,))
        return cursor.fetchall()
    finally:
        connection.close()


def get_order(order_id, hotel_id=None):
    hotel_id = _resolve_active_hotel_id(hotel_id)

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM orders
            WHERE order_id = ?
              AND hotel_id = ?
        """, (order_id, hotel_id))
        return cursor.fetchone()
    finally:
        connection.close()

ORDER_STATUSES = ("New", "Preparing", "Ready", "Served", "Completed", "Cancelled")


def _validate_order_status(status):
    if status not in ORDER_STATUSES:
        raise ValueError("Invalid order status.")


def get_order_status(order_id, hotel_id=None):
    record = get_order(order_id, hotel_id)
    if record is None:
        return None
    return record["order_status"] or "New"


def update_order_status(order_id, status, hotel_id=None):
    _validate_order_status(status)
    hotel_id = _resolve_active_hotel_id(hotel_id)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT order_status, grand_total, paid_amount, refund_amount, settlement_adjustment
            FROM orders
            WHERE order_id = ? AND hotel_id = ?
        """, (order_id, hotel_id))
        order = cursor.fetchone()
        if order is None:
            raise ValueError("Order Not Found.")

        current = order["order_status"] or "New"
        allowed = {
            "New": {"Preparing", "Cancelled"},
            "Preparing": {"Ready", "Cancelled"},
            "Ready": {"Served", "Cancelled"},
            "Served": {"Completed"},
            "Completed": set(),
            "Cancelled": set(),
        }
        if status != current and status not in allowed[current]:
            raise ValueError(f"Invalid order status transition: {current} -> {status}.")

        if status == "Cancelled":
            raise ValueError("Use cancel_restaurant_order() to cancel an order safely.")

        if status == "Completed":
            grand_total = float(order["grand_total"] or 0)
            paid_amount = float(order["paid_amount"] or 0)
            refund_amount = float(order["refund_amount"] or 0)
            settlement_adjustment = float(order["settlement_adjustment"] or 0)
            outstanding = round(grand_total - paid_amount + settlement_adjustment, 2)
            if refund_amount <= 0 and outstanding > 0.01:
                raise ValueError(
                    f"Order cannot be completed. Outstanding payment is ₹{outstanding:.2f}."
                )

        cursor.execute("""
            UPDATE orders
            SET order_status = ?
            WHERE order_id = ? AND hotel_id = ?
        """, (status, order_id, hotel_id))

        if status == "Completed":
            # A completed POS order no longer owns the restaurant table.
            # Release it only when no other active order is using the same table.
            cursor.execute("""
                SELECT table_number
                FROM orders
                WHERE order_id = ? AND hotel_id = ?
            """, (order_id, hotel_id))
            completed_order = cursor.fetchone()
            table_number = completed_order["table_number"] if completed_order else None

            if table_number:
                cursor.execute("""
                    SELECT COUNT(*) AS active_orders
                    FROM orders
                    WHERE hotel_id = ?
                      AND table_number = ?
                      AND order_id <> ?
                      AND COALESCE(order_status, 'New')
                          IN ('New', 'Preparing', 'Ready', 'Served')
                """, (hotel_id, table_number, order_id))
                active_orders = int(cursor.fetchone()["active_orders"] or 0)

                if active_orders == 0:
                    cursor.execute("""
                        UPDATE tables
                        SET table_status = 'Cleaning Required',
                            cleaning_reason = 'After Guest Use',
                            cleaning_started_at = NULL,
                            cleaning_completed_at = NULL
                        WHERE hotel_id = ?
                          AND table_number = ?
                          AND table_status = 'Occupied'
                    """, (hotel_id, table_number))
                    if cursor.rowcount:
                        from database.table_booking_db import release_table_assignment
                        release_table_assignment(connection, "POS", order_id, hotel_id)
                        _write_order_audit(
                            cursor, hotel_id, order_id, "TABLE_CLEANING_REQUIRED",
                            f"Table {table_number} moved to cleaning after order completion."
                        )

        _write_order_audit(
            cursor, hotel_id, order_id, "STATUS_UPDATED",
            f"{current} -> {status}"
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Order",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation update_order_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return status
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def cancel_restaurant_order(order_id, cancellation_reason, hotel_id=None):
    hotel_id = _resolve_active_hotel_id(hotel_id)
    reason = str(cancellation_reason or "").strip()
    if not reason:
        raise ValueError("Cancellation reason is required.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT order_status, table_number, customer_id, customer_name, customer_mobile
            FROM orders
            WHERE order_id = ? AND hotel_id = ?
        """, (order_id, hotel_id))
        order = cursor.fetchone()
        if order is None:
            raise ValueError("Order Not Found.")

        current = order["order_status"] or "New"
        if current in ("Completed", "Cancelled"):
            raise ValueError(f"Order is already {current} and cannot be cancelled.")

        cursor.execute("""
            UPDATE orders
            SET order_status = 'Cancelled',
                cancellation_reason = ?,
                cancelled_at = CURRENT_TIMESTAMP
            WHERE order_id = ? AND hotel_id = ?
        """, (reason, order_id, hotel_id))

        if order["table_number"]:
            table_number = str(order["table_number"]).strip().upper()

            # Release the occupied table only when no other active POS order
            # is using it. This keeps the table lifecycle safe even if legacy
            # or recovery data contains more than one order for the same table.
            cursor.execute("""
                SELECT COUNT(*) AS active_orders
                FROM orders
                WHERE hotel_id = ?
                  AND table_number = ?
                  AND order_id <> ?
                  AND COALESCE(order_status, 'New')
                      IN ('New', 'Preparing', 'Ready', 'Served')
            """, (hotel_id, table_number, order_id))
            active_orders = int(cursor.fetchone()["active_orders"] or 0)

            if active_orders == 0:
                cursor.execute("""
                    UPDATE tables
                    SET table_status = 'Cleaning Required',
                        cleaning_reason = 'After Guest Use',
                        cleaning_started_at = NULL,
                        cleaning_completed_at = NULL
                    WHERE hotel_id = ?
                      AND table_number = ?
                      AND table_status = 'Occupied'
                """, (hotel_id, table_number))

                if cursor.rowcount:
                    from database.table_booking_db import release_table_assignment
                    release_table_assignment(connection, "POS", order_id, hotel_id)
                    _write_order_audit(
                        cursor, hotel_id, order_id, "TABLE_CLEANING_REQUIRED",
                        f"Table {table_number} moved to cleaning after order cancellation."
                    )

        _write_order_audit(
            cursor, hotel_id, order_id, "ORDER_CANCELLED", reason
        )
        try:
            from database.notification_db import record_notification_event
            record_notification_event(
                "Cancellation",
                "Restaurant Order Cancelled",
                f"Restaurant order {order_id} was cancelled. Reason: {reason}.",
                reference_type="RESTAURANT_ORDER",
                reference_id=order_id,
                recipient_type="Guest",
                recipient_id=order["customer_id"],
                recipient_name=order["customer_name"],
                recipient_mobile=order["customer_mobile"],
                hotel_id=hotel_id,
                idempotency_key=f"CANCELLATION:{hotel_id}:RESTAURANT:{order_id}",
                connection=connection,
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Order",
        action="CANCEL",
        local_values=locals(),
        details="Business operation cancel_restaurant_order completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return "Cancelled"
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


PAYMENT_METHODS = ("Cash", "UPI", "Card", "Online", "Other")
PAYMENT_STATUSES = ("Pending", "Partially Paid", "Paid", "Refunded")


def _validate_payment_method(payment_method):
    if payment_method is not None and payment_method not in PAYMENT_METHODS:
        raise ValueError("Invalid payment method.")


def _calculate_payment_status(grand_total, paid_amount, refund_amount=0, settlement_adjustment=0):
    if refund_amount >= paid_amount and refund_amount > 0:
        return "Refunded"
    if paid_amount <= 0:
        return "Pending"
    effective_balance = round(grand_total - paid_amount + settlement_adjustment, 2)
    if effective_balance > 0.01:
        return "Partially Paid"
    return "Paid"


def _round_cash_settlement(amount):
    """Round a final settlement to the nearest whole rupee using half-up rounding."""
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(str(round(float(amount), 2))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _get_settlement_adjustment(amount_due, payment_amount):
    """Return a small rounding adjustment when a whole-rupee final payment settles the due amount."""
    rounded_due = _round_cash_settlement(amount_due)
    payment_amount = round(float(payment_amount), 2)
    if abs(payment_amount - rounded_due) > 0.01:
        return 0.0
    adjustment = round(payment_amount - float(amount_due), 2)
    if abs(adjustment) > 0.50:
        return 0.0
    return adjustment



def settle_order_rounding(order_id, hotel_id=None, notes=None):
    """Settle a very small remaining balance as a cash rounding adjustment.

    This is a settlement adjustment, not a customer payment. It is allowed only
    when the remaining balance is at most ₹0.50, so customers are not required
    to pay fractional paise amounts at the counter.
    """
    hotel_id = _resolve_active_hotel_id(hotel_id)
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT grand_total, paid_amount, refund_amount, settlement_adjustment, order_status
            FROM orders
            WHERE order_id = ? AND hotel_id = ?
        """, (order_id, hotel_id))
        order = cursor.fetchone()
        if order is None:
            raise ValueError("Order Not Found.")
        if (order["order_status"] or "New") == "Cancelled":
            raise ValueError("Rounding settlement cannot be applied to a cancelled order.")

        grand_total = float(order["grand_total"] or 0)
        paid = float(order["paid_amount"] or 0)
        refund = float(order["refund_amount"] or 0)
        current_adjustment = float(order["settlement_adjustment"] or 0)
        remaining = max(round(grand_total - paid - current_adjustment, 2), 0.0)

        if remaining <= 0.01:
            raise ValueError("No outstanding balance remains for rounding settlement.")
        if remaining > 0.50:
            raise ValueError(
                f"Rounding settlement is allowed only up to ₹0.50. Outstanding is ₹{remaining:.2f}."
            )

        rounding_adjustment = round(-remaining, 2)
        new_adjustment = round(current_adjustment + rounding_adjustment, 2)
        status = _calculate_payment_status(
            grand_total, paid, refund, new_adjustment
        )

        cursor.execute("""
            UPDATE orders
            SET payment_status = ?, balance_amount = 0, settlement_adjustment = ?
            WHERE order_id = ? AND hotel_id = ?
        """, (status, new_adjustment, order_id, hotel_id))

        _insert_payment_transaction(
            cursor, hotel_id, order_id, "ROUNDING_ADJUSTMENT",
            rounding_adjustment, "Cash",
            notes or "Small fractional balance settled by cash rounding"
        )
        _write_order_audit(
            cursor, hotel_id, order_id, "ROUNDING_SETTLEMENT",
            f"Outstanding ₹{remaining:.2f} settled by adjustment ₹{rounding_adjustment:.2f}."
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Order",
        action="PAYMENT",
        local_values=locals(),
        details="Business operation settle_order_rounding completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return {
            "status": status,
            "paid_amount": paid,
            "balance_amount": 0.0,
            "rounding_adjustment": rounding_adjustment,
            "settlement_adjustment": new_adjustment,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def add_order_payment(
    order_id, payment_amount, payment_method=None, notes=None, hotel_id=None
):
    """Add one new restaurant payment transaction without overwriting history."""
    hotel_id = _resolve_active_hotel_id(hotel_id)
    _validate_payment_method(payment_method)
    try:
        payment_amount = float(payment_amount)
    except (TypeError, ValueError):
        raise ValueError("Payment amount must be a valid number.")
    if payment_amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT grand_total, paid_amount, refund_amount, settlement_adjustment, order_status
            FROM orders
            WHERE order_id = ? AND hotel_id = ?
        """, (order_id, hotel_id))
        order = cursor.fetchone()
        if order is None:
            raise ValueError("Order Not Found.")
        if (order["order_status"] or "New") == "Cancelled":
            raise ValueError("Payment cannot be added to a cancelled order.")

        grand_total = float(order["grand_total"] or 0)
        current_paid = float(order["paid_amount"] or 0)
        current_refund = float(order["refund_amount"] or 0)
        current_adjustment = float(order["settlement_adjustment"] or 0)
        remaining = max(round(grand_total - current_paid - current_adjustment, 2), 0.0)
        rounding_adjustment = 0.0
        allowed_rounded_payment = (
            _get_settlement_adjustment(remaining, payment_amount)
            if payment_method == "Cash" else 0.0
        )
        if payment_amount > remaining + 0.01 and abs(allowed_rounded_payment) <= 0.001:
            raise ValueError(
                f"Payment cannot exceed remaining balance ₹{remaining:.2f}."
            )

        new_paid = round(current_paid + payment_amount, 2)
        raw_balance = round(grand_total - new_paid + current_adjustment, 2)
        rounding_adjustment = allowed_rounded_payment
        if abs(rounding_adjustment) > 0.001:
            current_adjustment = round(current_adjustment + rounding_adjustment, 2)
            raw_balance = round(grand_total - new_paid + current_adjustment, 2)

        balance = max(raw_balance, 0.0)
        status = _calculate_payment_status(grand_total, new_paid, current_refund, current_adjustment)

        cursor.execute("""
            UPDATE orders
            SET payment_method = ?, payment_status = ?,
                paid_amount = ?, balance_amount = ?, settlement_adjustment = ?
            WHERE order_id = ? AND hotel_id = ?
        """, (
            payment_method, status, new_paid, balance, current_adjustment, order_id, hotel_id
        ))

        _insert_payment_transaction(
            cursor, hotel_id, order_id, "PAYMENT", payment_amount,
            payment_method, notes
        )
        if abs(rounding_adjustment) > 0.001:
            _insert_payment_transaction(
                cursor, hotel_id, order_id, "ROUNDING_ADJUSTMENT",
                rounding_adjustment, None,
                "Final restaurant payment settled to nearest whole rupee"
            )
        _write_order_audit(
            cursor, hotel_id, order_id, "PAYMENT_RECORDED",
            f"Amount: {payment_amount:.2f}; Total Paid: {new_paid:.2f}; "
            f"Balance: {balance:.2f}; Method: {payment_method or '-'}"
        )
        try:
            order_customer = cursor.execute(
                """
                SELECT customer_id, customer_name, customer_mobile
                FROM orders
                WHERE order_id = ? AND hotel_id = ?
                """,
                (order_id, hotel_id),
            ).fetchone()
            from database.notification_db import record_notification_event
            record_notification_event(
                "Payment",
                "Restaurant Payment Recorded",
                f"Payment of ₹{payment_amount:.2f} was recorded for restaurant order {order_id}.",
                reference_type="RESTAURANT_PAYMENT",
                reference_id=order_id,
                recipient_type="Guest",
                recipient_id=order_customer["customer_id"] if order_customer else None,
                recipient_name=order_customer["customer_name"] if order_customer else None,
                recipient_mobile=order_customer["customer_mobile"] if order_customer else None,
                hotel_id=hotel_id,
                idempotency_key=f"PAYMENT:{hotel_id}:RESTAURANT:{order_id}:{new_paid:.2f}",
                connection=connection,
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Order",
        action="PAYMENT",
        local_values=locals(),
        details="Business operation add_order_payment completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return {
            "status": status,
            "paid_amount": new_paid,
            "balance_amount": balance,
            "transaction_amount": payment_amount,
            "settlement_adjustment": current_adjustment,
            "rounding_adjustment": rounding_adjustment,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def record_order_payment(
    order_id,
    paid_amount,
    payment_method=None,
    refund_amount=0,
    hotel_id=None
):
    """Backward-compatible payment setter; records the change as a correction event."""
    hotel_id = _resolve_active_hotel_id(hotel_id)
    _validate_payment_method(payment_method)
    try:
        paid_amount = float(paid_amount)
        refund_amount = float(refund_amount)
    except (TypeError, ValueError):
        raise ValueError("Payment amount must be a valid number.")
    if paid_amount < 0 or refund_amount < 0:
        raise ValueError("Payment amounts cannot be negative.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT grand_total, paid_amount, refund_amount, settlement_adjustment
            FROM orders WHERE order_id = ? AND hotel_id = ?
        """, (order_id, hotel_id))
        order = cursor.fetchone()
        if order is None:
            raise ValueError("Order Not Found.")
        grand_total = float(order["grand_total"] or 0)
        old_paid = float(order["paid_amount"] or 0)
        settlement_adjustment = 0.0
        if paid_amount > grand_total:
            rounded_total = _round_cash_settlement(grand_total)
            if abs(paid_amount - rounded_total) > 0.01 or abs(paid_amount - grand_total) > 0.50:
                raise ValueError("Paid amount cannot be greater than grand total except for the small whole-rupee settlement adjustment.")
            settlement_adjustment = round(paid_amount - grand_total, 2)
        if refund_amount > paid_amount:
            raise ValueError("Refund amount cannot be greater than paid amount.")
        balance_amount = max(round(grand_total - paid_amount + settlement_adjustment, 2), 0)
        status = _calculate_payment_status(
            grand_total, paid_amount, refund_amount, settlement_adjustment
        )
        cursor.execute("""
            UPDATE orders SET payment_method=?, payment_status=?, paid_amount=?,
                balance_amount=?, refund_amount=?, settlement_adjustment=?
            WHERE order_id=? AND hotel_id=?
        """, (payment_method, status, paid_amount, balance_amount,
              refund_amount, settlement_adjustment, order_id, hotel_id))
        delta = round(paid_amount - old_paid, 2)
        if abs(delta) > 0.001:
            _insert_payment_transaction(
                cursor, hotel_id, order_id, "PAYMENT_CORRECTION", delta,
                payment_method, "Legacy payment setter adjustment"
            )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Order",
        action="PAYMENT",
        local_values=locals(),
        details="Business operation record_order_payment completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return status
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_order_payment_history(order_id, hotel_id=None):
    hotel_id = _resolve_active_hotel_id(hotel_id)
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT transaction_id, order_id, transaction_type, payment_method,
                   amount, notes, created_at
            FROM restaurant_payment_transactions
            WHERE order_id = ? AND hotel_id = ?
            ORDER BY transaction_id ASC
        """, (order_id, hotel_id))
        return cursor.fetchall()
    finally:
        connection.close()


def correct_order_payment(
    order_id, paid_amount, payment_method=None, correction_reason=None, hotel_id=None
):
    hotel_id = _resolve_active_hotel_id(hotel_id)
    reason = str(correction_reason or "").strip()
    if not reason:
        raise ValueError("Payment correction reason is required.")
    _validate_payment_method(payment_method)
    try:
        paid_amount = float(paid_amount)
    except (TypeError, ValueError):
        raise ValueError("Payment amount must be a valid number.")
    if paid_amount < 0:
        raise ValueError("Payment amount cannot be negative.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT grand_total, paid_amount, refund_amount, payment_method, payment_status
            FROM orders
            WHERE order_id = ? AND hotel_id = ?
        """, (order_id, hotel_id))
        order = cursor.fetchone()
        if order is None:
            raise ValueError("Order Not Found.")
        if float(order["refund_amount"] or 0) > 0:
            raise ValueError("Payment cannot be corrected after a refund has been recorded.")
        grand_total = float(order["grand_total"] or 0)
        if paid_amount > grand_total:
            raise ValueError("Paid amount cannot be greater than grand total.")
        status = _calculate_payment_status(grand_total, paid_amount, 0)
        balance = max(grand_total - paid_amount, 0)
        cursor.execute("""
            UPDATE orders
            SET payment_method = ?, payment_status = ?, paid_amount = ?,
                balance_amount = ?, refund_amount = 0, settlement_adjustment = 0
            WHERE order_id = ? AND hotel_id = ?
        """, (payment_method, status, paid_amount, balance, order_id, hotel_id))
        delta = round(paid_amount - float(order["paid_amount"] or 0), 2)
        if abs(delta) > 0.001:
            _insert_payment_transaction(
                cursor, hotel_id, order_id, "PAYMENT_CORRECTION", delta,
                payment_method, reason
            )
        _write_order_audit(
            cursor, hotel_id, order_id, "PAYMENT_CORRECTED",
            f"Reason: {reason}; Paid: {order['paid_amount']} -> {paid_amount}; Method: {order['payment_method'] or '-'} -> {payment_method or '-'}"
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Order",
        action="PAYMENT",
        local_values=locals(),
        details="Business operation correct_order_payment completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return status
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def record_order_refund(order_id, refund_amount, refund_reason, hotel_id=None):
    hotel_id = _resolve_active_hotel_id(hotel_id)
    reason = str(refund_reason or "").strip()
    if not reason:
        raise ValueError("Refund reason is required.")
    try:
        refund_amount = float(refund_amount)
    except (TypeError, ValueError):
        raise ValueError("Refund amount must be a valid number.")
    if refund_amount <= 0:
        raise ValueError("Refund amount must be greater than zero.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT grand_total, paid_amount, refund_amount, payment_method, order_status
            FROM orders
            WHERE order_id = ? AND hotel_id = ?
        """, (order_id, hotel_id))
        order = cursor.fetchone()
        if order is None:
            raise ValueError("Order Not Found.")
        paid = float(order["paid_amount"] or 0)
        already_refunded = float(order["refund_amount"] or 0)
        refundable = max(paid - already_refunded, 0)
        if refund_amount > refundable:
            raise ValueError(f"Refund amount cannot exceed refundable balance ₹{refundable:.2f}.")
        if (order["order_status"] or "New") not in ("Completed", "Cancelled"):
            raise ValueError("Refund is allowed only for Completed or Cancelled orders.")

        new_refund = already_refunded + refund_amount
        status = _calculate_payment_status(
            float(order["grand_total"] or 0), paid, new_refund
        )
        cursor.execute("""
            UPDATE orders
            SET payment_status = ?, refund_amount = ?,
                balance_amount = 0
            WHERE order_id = ? AND hotel_id = ?
        """, (status, new_refund, order_id, hotel_id))
        _insert_payment_transaction(
            cursor, hotel_id, order_id, "REFUND", -refund_amount,
            order["payment_method"], reason
        )
        _write_order_audit(
            cursor, hotel_id, order_id, "REFUND_RECORDED",
            f"Amount: {refund_amount:.2f}; Total Refund: {new_refund:.2f}; Reason: {reason}"
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Order",
        action="PAYMENT",
        local_values=locals(),
        details="Business operation record_order_refund completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return status
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def cancel_order_item(
    order_id, item_number, discount, gst_rate, cancellation_reason, hotel_id=None
):
    hotel_id = _resolve_active_hotel_id(hotel_id)
    reason = str(cancellation_reason or "").strip()
    if not reason:
        raise ValueError("Item cancellation reason is required.")
    try:
        item_number = int(item_number)
        discount = float(discount or 0)
        gst_rate = float(gst_rate or 0)
    except (TypeError, ValueError):
        raise ValueError("Invalid item or billing value.")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT * FROM orders
            WHERE order_id = ? AND hotel_id = ?
        """, (order_id, hotel_id))
        order = cursor.fetchone()
        if order is None:
            raise ValueError("Order Not Found.")
        status = order["order_status"] or "New"
        if status not in ("New", "Preparing", "Ready"):
            raise ValueError("Items can only be cancelled before the order is Served.")

        try:
            cart = json.loads(order["cart"] or "[]")
        except (TypeError, json.JSONDecodeError):
            raise ValueError("Order cart data is invalid.")
        if item_number < 1 or item_number > len(cart):
            raise ValueError("Invalid item number.")
        removed = cart.pop(item_number - 1)
        if not cart:
            raise ValueError("Use full order cancellation when cancelling the last item.")

        subtotal = sum(float(item["subtotal"]) for item in cart)
        discount = min(max(discount, 0), subtotal)
        taxable = subtotal - discount
        gst = taxable * gst_rate
        grand_total = taxable + gst
        paid = float(order["paid_amount"] or 0)
        refund = float(order["refund_amount"] or 0)
        if paid > grand_total:
            raise ValueError("Item cancellation would make paid amount exceed the new total. Correct/refund payment first.")
        balance = max(grand_total - paid, 0)
        payment_status = _calculate_payment_status(grand_total, paid, refund)

        cursor.execute("""
            UPDATE orders
            SET cart = ?, subtotal = ?, discount = ?, gst = ?, grand_total = ?,
                balance_amount = ?, payment_status = ?, settlement_adjustment = 0
            WHERE order_id = ? AND hotel_id = ?
        """, (
            json.dumps(cart), subtotal, discount, gst, grand_total,
            balance, payment_status, order_id, hotel_id
        ))
        _write_order_audit(
            cursor, hotel_id, order_id, "ITEM_CANCELLED",
            f"Item: {removed.get('name', 'Unknown')}; Reason: {reason}"
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Order",
        action="CANCEL",
        local_values=locals(),
        details="Business operation cancel_order_item completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return {
            "cart": cart,
            "subtotal": subtotal,
            "discount": discount,
            "gst": gst,
            "grand_total": grand_total,
            "payment_status": payment_status,
            "cancelled_item": removed,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_order_payment(order_id, hotel_id=None):
    record = get_order(order_id, hotel_id)
    if record is None:
        return None
    return {
        "payment_method": record["payment_method"],
        "payment_status": record["payment_status"] or "Pending",
        "paid_amount": float(record["paid_amount"] or 0),
        "balance_amount": float(record["balance_amount"] or 0),
        "refund_amount": float(record["refund_amount"] or 0),
        "grand_total": float(record["grand_total"] or 0),
    }


def save_order(
    cart,
    order_id,
    order_time,
    customer_name,
    customer_mobile,
    table_number,
    subtotal,
    gst,
    grand_total,
    customer_id=None,
    discount=0,
    hotel_id=None,
    order_notes=None,
    payment_method=None,
    paid_amount=0,
    refund_amount=0
,
    advance_amount=0
):
    hotel_id = _resolve_active_hotel_id(hotel_id)

    if not order_id or not str(order_id).strip():
        raise ValueError("Order ID is required.")
    if order_time is None:
        raise ValueError("Order time is required.")
    if not table_number or not str(table_number).strip():
        raise ValueError("Restaurant table is required.")

    _validate_cart(cart)
    _validate_payment_method(payment_method)

    try:
        paid_amount = float(paid_amount)
        refund_amount = float(refund_amount)
        discount = float(discount)
        supplied_subtotal = float(subtotal)
        supplied_gst = float(gst)
        supplied_grand_total = float(grand_total)
    except (TypeError, ValueError):
        raise ValueError("Invalid order or billing amount.")

    if paid_amount < 0 or refund_amount < 0:
        raise ValueError("Payment amounts cannot be negative.")
    if refund_amount > paid_amount:
        raise ValueError("Refund amount cannot be greater than paid amount.")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT 1 FROM orders WHERE order_id = ?",
            (order_id,)
        )
        if cursor.fetchone() is not None:
            raise ValueError("Order ID already exists.")

        _validate_cart_against_menu(cursor, cart, hotel_id)

        (
            calculated_subtotal,
            calculated_gst,
            calculated_grand_total
        ) = _validate_order_financials(
            cursor,
            cart,
            discount,
            supplied_gst,
            supplied_grand_total,
            hotel_id
        )

        if abs(supplied_subtotal - calculated_subtotal) > 0.01:
            raise ValueError("Subtotal does not match the order items.")

        settlement_adjustment = 0.0
        if paid_amount > calculated_grand_total:
            rounded_total = _round_cash_settlement(calculated_grand_total)
            if payment_method != "Cash" or abs(paid_amount - rounded_total) > 0.01 or abs(paid_amount - calculated_grand_total) > 0.50:
                raise ValueError("Paid amount cannot be greater than grand total except for the small whole-rupee cash settlement adjustment.")
        initial_balance = round(calculated_grand_total - paid_amount, 2)
        if payment_method == "Cash" and abs(_get_settlement_adjustment(calculated_grand_total, paid_amount)) > 0.001:
            settlement_adjustment = _get_settlement_adjustment(calculated_grand_total, paid_amount)

        cursor.execute(
            """
            SELECT table_status
            FROM tables
            WHERE hotel_id = ? AND table_number = ?
            """,
            (hotel_id, str(table_number).strip().upper())
        )
        table = cursor.fetchone()

        if table is None:
            raise ValueError("Invalid restaurant table.")

        if table["table_status"] != "Occupied":
            raise ValueError(
                "Restaurant table must be occupied by the current POS order."
            )

        if customer_id:
            from database.customer_db import validate_guest_hotel_relationship
            validate_guest_hotel_relationship(customer_id, hotel_id)

        try:
            normalized_advance_amount = round(float(advance_amount or 0), 2)
        except (TypeError, ValueError):
            raise ValueError("Advance amount must be a valid number.")

        if normalized_advance_amount < 0:
            raise ValueError("Advance amount cannot be negative.")

        if normalized_advance_amount > calculated_grand_total:
            raise ValueError("Advance amount cannot exceed the grand total.")

        balance_amount = max(
            round(calculated_grand_total - normalized_advance_amount, 2),
            0
        )
        payment_status = _calculate_payment_status(
            calculated_grand_total, paid_amount, refund_amount, settlement_adjustment
        )

        from database.billing_invoice_db import create_invoice_for_source

        invoice_number = create_invoice_for_source(
            cursor,
            hotel_id,
            "RESTAURANT_ORDER",
            order_id,
            invoice_date=order_time.strftime("%Y-%m-%d")
        )

        cursor.execute(
            """
            INSERT INTO orders(
                order_id,
                invoice_number,
                advance_amount,
                hotel_id,
                customer_id,
                order_date,
                order_time,
                customer_name,
                customer_mobile,
                table_number,
                cart,
                subtotal,
                gst,
                grand_total,
                discount,
                order_status,
                order_notes,
                payment_method,
                payment_status,
                paid_amount,
                balance_amount,
                refund_amount,
                settlement_adjustment
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                invoice_number,
                normalized_advance_amount,
                hotel_id,
                customer_id,
                order_time.strftime("%d-%m-%Y"),
                order_time.strftime("%I:%M:%S %p"),
                customer_name,
                customer_mobile,
                str(table_number).strip().upper(),
                json.dumps(cart),
                calculated_subtotal,
                calculated_gst,
                calculated_grand_total,
                discount,
                "New",
                order_notes,
                payment_method,
                payment_status,
                paid_amount,
                balance_amount,
                refund_amount,
                settlement_adjustment
            )
        )

        if paid_amount > 0.001:
            _insert_payment_transaction(
                cursor, hotel_id, order_id, "PAYMENT", paid_amount,
                payment_method, "Initial order payment"
            )
            if abs(settlement_adjustment) > 0.001:
                _insert_payment_transaction(
                    cursor, hotel_id, order_id, "ROUNDING_ADJUSTMENT",
                    settlement_adjustment, None,
                    "Initial restaurant payment settled to nearest whole rupee"
                )

        from database.table_booking_db import record_table_assignment

        record_table_assignment(
            connection,
            str(table_number).strip().upper(),
            "POS",
            order_id,
            customer_id,
            hotel_id
        )

        _write_order_audit(
            cursor,
            hotel_id,
            order_id,
            "ORDER_CREATED",
            f"Table: {str(table_number).strip().upper()}; "
            f"Total: {calculated_grand_total:.2f}"
        )

        if paid_amount > 0.001:
            try:
                from database.notification_db import record_notification_event
                record_notification_event(
                    "Payment",
                    "Restaurant Payment Recorded",
                    f"Payment of ₹{paid_amount:.2f} was recorded for restaurant order {order_id}.",
                    reference_type="RESTAURANT_PAYMENT",
                    reference_id=order_id,
                    recipient_type="Guest",
                    recipient_id=customer_id,
                    recipient_name=customer_name,
                    recipient_mobile=customer_mobile,
                    hotel_id=hotel_id,
                    idempotency_key=f"PAYMENT:{hotel_id}:RESTAURANT:{order_id}:INITIAL",
                    connection=connection,
                )
            except Exception as exc:
                log_non_blocking_error("Non-blocking optional operation failed", exc)

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Order",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_order completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



def get_restaurant_order_history(
    hotel_id=None,
    order_date=None,
    customer_id=None,
    customer_search=None,
    table_number=None,
    order_status=None,
    search_text=None,
):
    """Return hotel-scoped restaurant order history with optional filters."""
    hotel_id = _resolve_active_hotel_id(hotel_id)

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = """
            SELECT *
            FROM orders
            WHERE hotel_id = ?
        """
        params = [hotel_id]

        if order_date:
            query += " AND order_date = ?"
            params.append(order_date)

        if customer_id:
            query += " AND customer_id = ?"
            params.append(customer_id)

        if customer_search:
            search_value = f"%{customer_search.strip()}%"
            query += """
                AND (
                    customer_name LIKE ?
                    OR customer_mobile LIKE ?
                    OR customer_id LIKE ?
                )
            """
            params.extend([search_value, search_value, search_value])

        if table_number:
            query += " AND table_number = ?"
            params.append(str(table_number).strip())

        if order_status:
            query += " AND COALESCE(order_status, 'New') = ?"
            params.append(order_status)

        if search_text:
            search_value = f"%{search_text.strip()}%"
            query += """
                AND (
                    order_id LIKE ?
                    OR customer_id LIKE ?
                    OR customer_name LIKE ?
                    OR customer_mobile LIKE ?
                    OR table_number LIKE ?
                    OR order_notes LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM json_each(orders.cart)
                        WHERE json_extract(json_each.value, '$.name') LIKE ?
                           OR json_extract(json_each.value, '$.instruction') LIKE ?
                           OR json_extract(json_each.value, '$.special_instructions') LIKE ?
                    )
                )
            """
            params.extend([
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
            ])

        query += " ORDER BY order_date DESC, order_time DESC, rowid DESC"

        cursor.execute(query, params)
        return cursor.fetchall()

    finally:
        connection.close()


def get_todays_restaurant_orders(hotel_id=None):
    from utils.date_time import current_date

    return get_restaurant_order_history(
        hotel_id=hotel_id,
        order_date=current_date(),
    )


def get_customer_restaurant_orders(customer_id, hotel_id=None):
    return get_restaurant_order_history(
        hotel_id=hotel_id,
        customer_id=customer_id,
    )


def get_table_restaurant_orders(table_number, hotel_id=None):
    return get_restaurant_order_history(
        hotel_id=hotel_id,
        table_number=table_number,
    )


def _print_order_details(record):
    print("=" * 80)
    print(f"Order ID       : {record['order_id']}")
    print(f"Order Date     : {record['order_date'] or '-'}")
    print(f"Order Time     : {record['order_time'] or '-'}")
    print(f"Customer ID    : {record['customer_id'] or '-'}")
    print(f"Customer       : {record['customer_name'] or '-'}")
    print(f"Mobile         : {record['customer_mobile'] or '-'}")
    print(f"Table No       : {record['table_number'] or '-'}")
    print(f"Order Status   : {record['order_status'] or 'New'}")
    print(f"Payment Method : {record['payment_method'] or '-'}")
    print(f"Payment Status : {record['payment_status'] or 'Pending'}")
    print("-" * 80)

    try:
        cart = json.loads(record["cart"] or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        cart = []

    if cart:
        print("ITEMS")
        for item in cart:
            instruction = item.get("instruction") or item.get("special_instructions")
            line = (
                f"  {item.get('name', 'Unknown')} "
                f"x{item.get('quantity', 0)} "
                f"@ ₹{float(item.get('price', 0) or 0):.2f} "
                f"= ₹{float(item.get('subtotal', 0) or 0):.2f}"
            )
            print(line)
            if instruction:
                print(f"    Instruction : {instruction}")
    else:
        print("No item details available.")

    print("-" * 80)
    print(f"Subtotal       : ₹{float(record['subtotal'] or 0):.2f}")
    print(f"Discount       : ₹{float(record['discount'] or 0):.2f}")
    print(f"GST            : ₹{float(record['gst'] or 0):.2f}")
    print(f"Grand Total    : ₹{float(record['grand_total'] or 0):.2f}")
    print(f"Paid           : ₹{float(record['paid_amount'] or 0):.2f}")
    print(f"Balance        : ₹{float(record['balance_amount'] or 0):.2f}")
    print(f"Refund         : ₹{float(record['refund_amount'] or 0):.2f}")
    if record["order_notes"]:
        print(f"Order Notes    : {record['order_notes']}")
    print("=" * 80)



def get_restaurant_sales_analytics(hotel_id=None):
    """Return hotel-scoped restaurant sales analytics from SQLite orders."""
    hotel_id = _resolve_active_hotel_id(hotel_id)

    from collections import defaultdict
    from datetime import datetime

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT order_id, order_date, order_time, cart,
                   grand_total, paid_amount, refund_amount,
                   payment_method, order_status
            FROM orders
            WHERE hotel_id = ?
            ORDER BY order_date DESC, order_time DESC, rowid DESC
        """, (hotel_id,))
        orders = cursor.fetchall()

        cursor.execute("""
            SELECT i.item_name, c.category_name
            FROM restaurant_menu_items i
            JOIN restaurant_menu_categories c
              ON c.category_id = i.category_id
             AND c.hotel_id = i.hotel_id
            WHERE i.hotel_id = ?
        """, (hotel_id,))
        menu_category_map = {
            str(row["item_name"]).strip().lower(): row["category_name"]
            for row in cursor.fetchall()
        }

        cursor.execute("""
            SELECT t.order_id, t.transaction_type, t.payment_method, t.amount
            FROM restaurant_payment_transactions t
            JOIN orders o
              ON o.order_id = t.order_id
             AND o.hotel_id = t.hotel_id
            WHERE t.hotel_id = ?
              AND COALESCE(o.order_status, 'New') <> 'Cancelled'
            ORDER BY t.transaction_id ASC
        """, (hotel_id,))
        payment_transactions = cursor.fetchall()
    finally:
        connection.close()

    today = datetime.now().strftime("%d-%m-%Y")
    today_sales = 0.0
    today_orders = 0
    daily_sales = defaultdict(float)
    daily_orders = defaultdict(int)
    item_sales = defaultdict(lambda: {"quantity": 0.0, "sales": 0.0})
    category_sales = defaultdict(lambda: {"quantity": 0.0, "sales": 0.0})
    payment_sales = defaultdict(lambda: {"orders": 0, "collected": 0.0})
    total_sales = 0.0
    total_orders = 0

    for order in orders:
        if (order["order_status"] or "New") == "Cancelled":
            continue

        grand_total = float(order["grand_total"] or 0)
        refund_amount = float(order["refund_amount"] or 0)
        net_sales = max(grand_total - refund_amount, 0.0)
        order_date = order["order_date"] or "Unknown"

        total_sales += net_sales
        total_orders += 1
        daily_sales[order_date] += net_sales
        daily_orders[order_date] += 1

        if order_date == today:
            today_sales += net_sales
            today_orders += 1

        # Payment analytics are transaction-based so split payments are attributed
        # to the actual methods used, rather than only the latest order method.
        if float(order["paid_amount"] or 0) <= 0 and refund_amount <= 0:
            payment_sales["Pending / Unpaid"]["orders"] += 1


        try:
            cart = json.loads(order["cart"] or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            cart = []

        for item in cart:
            item_name = str(item.get("name") or "Unknown Item").strip()
            if not item_name:
                item_name = "Unknown Item"
            quantity = float(item.get("quantity") or 0)
            item_subtotal = float(item.get("subtotal") or 0)
            item_sales[item_name]["quantity"] += quantity
            item_sales[item_name]["sales"] += item_subtotal

            category_name = str(
                item.get("category_name")
                or menu_category_map.get(item_name.lower())
                or "Uncategorized"
            ).strip() or "Uncategorized"
            category_sales[category_name]["quantity"] += quantity
            category_sales[category_name]["sales"] += item_subtotal

    average_order_value = total_sales / total_orders if total_orders else 0.0

    payment_sales.clear()
    payment_order_ids = defaultdict(set)
    for transaction in payment_transactions:
        method = transaction["payment_method"] or "Other"
        amount = float(transaction["amount"] or 0)
        payment_sales[method]["collected"] += amount
        payment_order_ids[method].add(transaction["order_id"])
    for method, order_ids in payment_order_ids.items():
        payment_sales[method]["orders"] = len(order_ids)

    for order in orders:
        if (order["order_status"] or "New") == "Cancelled":
            continue
        if float(order["paid_amount"] or 0) <= 0:
            payment_sales["Pending / Unpaid"]["orders"] += 1

    return {
        "today": {
            "sales": today_sales,
            "order_count": today_orders,
            "average_order_value": today_sales / today_orders
            if today_orders else 0.0,
        },
        "overall": {
            "sales": total_sales,
            "order_count": total_orders,
            "average_order_value": average_order_value,
        },
        "daily_sales": sorted(
            [
                (order_date, daily_sales[order_date], daily_orders[order_date])
                for order_date in daily_sales
            ],
            key=lambda value: value[0],
            reverse=True
        ),
        "item_sales": sorted(
            item_sales.items(),
            key=lambda value: value[1]["sales"],
            reverse=True
        ),
        "category_sales": sorted(
            category_sales.items(),
            key=lambda value: value[1]["sales"],
            reverse=True
        ),
        "payment_sales": sorted(
            payment_sales.items(),
            key=lambda value: value[1]["collected"],
            reverse=True
        ),
    }

def get_restaurant_operational_orders(status=None, hotel_id=None):
    """Return current-hotel orders for restaurant operational/kitchen views."""
    hotel_id = _resolve_active_hotel_id(hotel_id)

    if status is not None:
        _validate_order_status(status)

    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = """
            SELECT *
            FROM orders
            WHERE hotel_id = ?
        """
        params = [hotel_id]
        if status is not None:
            query += " AND COALESCE(order_status, 'New') = ?"
            params.append(status)
        else:
            query += " AND COALESCE(order_status, 'New') IN ('New', 'Preparing', 'Ready', 'Served')"
        query += " ORDER BY order_date ASC, order_time ASC, rowid ASC"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def restaurant_operational_summary(hotel_id=None):
    """Return counts for active restaurant operational queues."""
    if hotel_id is None:
        hotel_id = _get_current_hotel_id()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                SUM(CASE WHEN COALESCE(order_status, 'New') = 'New' THEN 1 ELSE 0 END) AS new_orders,
                SUM(CASE WHEN order_status = 'Preparing' THEN 1 ELSE 0 END) AS preparing_orders,
                SUM(CASE WHEN order_status = 'Ready' THEN 1 ELSE 0 END) AS ready_orders,
                SUM(CASE WHEN order_status = 'Served' THEN 1 ELSE 0 END) AS served_orders
            FROM orders
            WHERE hotel_id = ?
        """, (hotel_id,))
        row = cursor.fetchone()
        return {
            "new": int(row["new_orders"] or 0),
            "preparing": int(row["preparing_orders"] or 0),
            "ready": int(row["ready_orders"] or 0),
            "served": int(row["served_orders"] or 0),
        }
    finally:
        connection.close()


def get_order_audit(order_id, hotel_id=None):
    hotel_id = _resolve_active_hotel_id(hotel_id)
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT audit_id, action, details, created_at
            FROM restaurant_order_audit
            WHERE order_id = ? AND hotel_id = ?
            ORDER BY audit_id ASC
        """, (order_id, hotel_id))
        return cursor.fetchall()
    finally:
        connection.close()


def restaurant_order_history():
    from datetime import date

    while True:
        print("=" * 80)
        print("                 RESTAURANT ORDER HISTORY")
        print("=" * 80)
        print("1. Today's Orders")
        print("2. All Previous Orders")
        print("3. Customer-wise Orders")
        print("4. Table-wise Orders")
        print("5. Search / Filter Orders")
        print("6. Order Details")
        print("7. Back")
        print("=" * 80)

        choice = input("Enter Choice : ").strip()

        if choice == "1":
            records = get_todays_restaurant_orders()
            _show_order_history_records(records, "TODAY'S RESTAURANT ORDERS")
        elif choice == "2":
            records = get_restaurant_order_history()
            _show_order_history_records(records, "ALL RESTAURANT ORDERS")
        elif choice == "3":
            customer_search = input(
                "Enter Customer ID / Name / Mobile : "
            ).strip()
            if not customer_search:
                print("Customer search is required.")
                continue
            records = get_restaurant_order_history(
                customer_search=customer_search
            )
            _show_order_history_records(records, "CUSTOMER-WISE ORDERS")
        elif choice == "4":
            table_number = input("Enter Table Number : ").strip()
            if not table_number:
                print("Table number is required.")
                continue
            records = get_table_restaurant_orders(table_number)
            _show_order_history_records(records, "TABLE-WISE ORDERS")
        elif choice == "5":
            search_text = input(
                "Search Order ID / Customer / Mobile / Table / Item : "
            ).strip()
            order_status = input(
                "Status (New/Preparing/Ready/Served/Completed/Cancelled, blank=all) : "
            ).strip()
            order_date = input(
                "Date YYYY-MM-DD (blank=all) : "
            ).strip()

            if order_date:
                try:
                    date.fromisoformat(order_date)
                except ValueError:
                    print("Invalid date format. Use YYYY-MM-DD.")
                    continue
                order_date = order_date[8:10] + "-" + order_date[5:7] + "-" + order_date[0:4]

            valid_statuses = set(ORDER_STATUSES)
            if order_status and order_status not in valid_statuses:
                print("Invalid order status.")
                continue

            records = get_restaurant_order_history(
                search_text=search_text or None,
                order_status=order_status or None,
                order_date=order_date or None,
            )
            _show_order_history_records(records, "FILTERED ORDERS")
        elif choice == "6":
            order_id = input("Enter Order ID : ").strip().upper()
            if not order_id:
                print("Order ID is required.")
                continue
            record = get_order(order_id)
            if record is None:
                print("Order Not Found.")
            else:
                _print_order_details(record)
        elif choice == "7":
            return
        else:
            print("Invalid Choice.")


def _show_order_history_records(records, title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)
    print(f"Total Orders : {len(records)}")
    print()

    if not records:
        print("No Orders Found.")
        print("=" * 80)
        return

    for record in records:
        _print_order_details(record)

def view_orders():

    records = get_orders()

    if not records:
        print("No Orders Found.")
        return

    print("=" * 40)
    print("          ORDER HISTORY")
    print("=" * 40)

    for record in records:

        print(f"Order ID : {record['order_id']}")
        print(f"Date     : {record['order_date']}")
        print(f"Time     : {record['order_time']}")
        print(f"Customer : {record['customer_name']}")
        print(f"Mobile   : {record['customer_mobile']}")
        print(f"Table No : {record['table_number']}")
        print(f"Status   : {record['order_status'] or 'New'}")

        print("-" * 40)

        try:
            cart = json.loads(record["cart"])
        except (TypeError, json.JSONDecodeError):
            cart = []

        for item in cart:
            print(
                f"{item['name']} x{item['quantity']} "
                f"= ₹{item['subtotal']}"
            )

        print("-" * 40)
        print(f"Subtotal    : ₹{record['subtotal']}")
        print(f"GST         : ₹{record['gst']}")
        print(f"Discount    : ₹{record['discount'] or 0}")
        print(f"Grand Total : ₹{record['grand_total']}")
        print(f"Payment     : {record['payment_method'] or '-'}")
        print(f"Payment Status : {record['payment_status'] or 'Pending'}")
        print(f"Paid        : ₹{record['paid_amount'] or 0}")
        print(f"Balance     : ₹{record['balance_amount'] or 0}")
        print(f"Refund      : ₹{record['refund_amount'] or 0}")
        if record['order_notes']:
            print(f"Order Notes : {record['order_notes']}")
        print("=" * 40)


def search_order():
    print("=" * 40)
    print("          SEARCH ORDER")
    print("=" * 40)

    search = input(
        "Enter Order ID / Customer / Mobile / Table / Food Name : "
    ).strip()

    if not search:
        print("Search value is required.")
        return

    records = get_restaurant_order_history(search_text=search)
    _show_order_history_records(records, "SEARCH ORDER RESULTS")

def delete_order():

    print("=" * 40)
    print("          DELETE ORDER")
    print("=" * 40)

    order_id = input("Enter Order ID : ").strip().upper()

    if not order_id:
        print("Order ID is required.")
        return

    hotel_id = _resolve_active_hotel_id()
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT order_status, paid_amount, refund_amount
            FROM orders
            WHERE order_id = ? AND hotel_id = ?
            """,
            (order_id, hotel_id)
        )
        order = cursor.fetchone()

        if order is None:
            print("Order Not Found.")
            return

        if (order["order_status"] or "New") != "Cancelled":
            print("Only Cancelled orders can be permanently deleted.")
            return

        if (
            float(order["paid_amount"] or 0) > 0
            or float(order["refund_amount"] or 0) > 0
        ):
            print("Financially involved orders cannot be permanently deleted.")
            return

        cursor.execute(
            """
            DELETE FROM orders
            WHERE order_id = ? AND hotel_id = ?
            """,
            (order_id, hotel_id)
        )

        if cursor.rowcount != 1:
            connection.rollback()
            print("Order Not Found.")
            return

        _write_order_audit(
            cursor,
            hotel_id,
            order_id,
            "ORDER_DELETED",
            "Cancelled order removed; no payment or refund was recorded."
        )

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Order",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_order completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Order Deleted Successfully.")

    except Exception as exc:
        connection.rollback()
        print(f"Error deleting order: {exc}")

    finally:
        connection.close()

