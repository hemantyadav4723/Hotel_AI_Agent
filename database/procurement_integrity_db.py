"""Security and SQLite integrity guards for Supplier + Procurement.

The procurement modules already enforce hotel context and application-level
permissions. This module adds database-level invariants so direct SQL or
future callers cannot silently create cross-hotel or inconsistent procurement
records.
"""

from database.database import get_connection


def create_procurement_integrity_guards():
    connection = get_connection()
    try:
        cursor = connection.cursor()

        # Rebuild the PO status trigger so upgrades replace the older trigger
        # definition instead of being blocked by IF NOT EXISTS.
        cursor.execute("DROP TRIGGER IF EXISTS trg_po_status")

        triggers = [
            """
            CREATE TRIGGER IF NOT EXISTS trg_po_supplier_hotel
            BEFORE INSERT ON purchase_orders
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1 FROM suppliers
                WHERE supplier_id = NEW.supplier_id AND hotel_id = NEW.hotel_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Order supplier does not belong to the same hotel.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_po_item_hotel
            BEFORE INSERT ON purchase_order_items
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1 FROM inventory
                WHERE item_id = NEW.item_id AND hotel_id = NEW.hotel_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Order item does not belong to the same hotel.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_po_totals
            BEFORE INSERT ON purchase_orders
            FOR EACH ROW
            WHEN NEW.subtotal < 0 OR NEW.tax_amount < 0 OR NEW.grand_total < 0
                 OR abs(NEW.grand_total - (NEW.subtotal + NEW.tax_amount)) > 0.01
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Order totals are inconsistent.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_po_status
            BEFORE UPDATE OF status ON purchase_orders
            FOR EACH ROW
            WHEN NEW.status NOT IN (
                    'Draft', 'Approved', 'Partially Received',
                    'Fully Received', 'Cancelled'
                 )
                 OR (OLD.status = 'Cancelled' AND NEW.status <> 'Cancelled')
                 OR (OLD.status = 'Fully Received' AND NEW.status <> 'Fully Received')
                 OR (OLD.status = 'Approved' AND NEW.status = 'Draft')
                 OR (OLD.status = 'Partially Received'
                     AND NEW.status IN ('Draft', 'Approved'))
                 OR (OLD.status = 'Draft'
                     AND NEW.status IN ('Partially Received', 'Fully Received'))
            BEGIN
                SELECT RAISE(ABORT, 'Invalid Purchase Order status transition.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_receiving_supplier_hotel
            BEFORE INSERT ON purchase_receivings
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1 FROM suppliers
                WHERE supplier_id = NEW.supplier_id AND hotel_id = NEW.hotel_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Receiving supplier does not belong to the same hotel.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_receiving_po_supplier
            BEFORE INSERT ON purchase_receivings
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1 FROM purchase_orders
                WHERE po_id = NEW.po_id
                  AND hotel_id = NEW.hotel_id
                  AND supplier_id = NEW.supplier_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Receiving supplier does not match the Purchase Order.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_receiving_item_hotel
            BEFORE INSERT ON purchase_receiving_items
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1 FROM inventory
                WHERE item_id = NEW.item_id AND hotel_id = NEW.hotel_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Receiving item does not belong to the same hotel.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_receiving_po_item_match
            BEFORE INSERT ON purchase_receiving_items
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1 FROM purchase_order_items
                WHERE po_item_id = NEW.po_item_id
                  AND po_id = NEW.po_id
                  AND hotel_id = NEW.hotel_id
                  AND item_id = NEW.item_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Receiving item does not match the Purchase Order item.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_po_totals_update
            BEFORE UPDATE OF subtotal, tax_amount, grand_total ON purchase_orders
            FOR EACH ROW
            WHEN NEW.subtotal < 0 OR NEW.tax_amount < 0 OR NEW.grand_total < 0
                 OR abs(NEW.grand_total - (NEW.subtotal + NEW.tax_amount)) > 0.01
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Order totals are inconsistent.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_receiving_batch_hotel_item
            BEFORE INSERT ON purchase_receiving_items
            FOR EACH ROW
            WHEN NEW.batch_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM inventory_batches
                WHERE batch_id = NEW.batch_id
                  AND hotel_id = NEW.hotel_id
                  AND item_id = NEW.item_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Receiving batch does not match hotel and item.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_receiving_batch_quantity
            BEFORE INSERT ON purchase_receiving_items
            FOR EACH ROW
            WHEN NEW.batch_id IS NOT NULL AND NEW.received_quantity > COALESCE((
                SELECT current_quantity FROM inventory_batches
                WHERE batch_id = NEW.batch_id
            ), 0)
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Receiving batch quantity is inconsistent.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_receiving_total
            BEFORE INSERT ON purchase_receivings
            FOR EACH ROW
            WHEN NEW.total_value < 0
            BEGIN
                SELECT RAISE(ABORT, 'Purchase Receiving total cannot be negative.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_payment_supplier_hotel
            BEFORE INSERT ON supplier_payments
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1 FROM suppliers
                WHERE supplier_id = NEW.supplier_id AND hotel_id = NEW.hotel_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Supplier payment supplier does not belong to the same hotel.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_payment_positive
            BEFORE INSERT ON supplier_payments
            FOR EACH ROW
            WHEN NEW.amount <= 0
            BEGIN
                SELECT RAISE(ABORT, 'Supplier payment amount must be greater than zero.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_payment_method
            BEFORE INSERT ON supplier_payments
            FOR EACH ROW
            WHEN NEW.payment_method NOT IN ('Cash', 'Bank', 'UPI', 'Cheque', 'Other')
            BEGIN
                SELECT RAISE(ABORT, 'Invalid supplier payment method.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_payment_not_over_outstanding
            BEFORE INSERT ON supplier_payments
            FOR EACH ROW
            WHEN NEW.amount > (
                COALESCE((
                    SELECT SUM(total_value) FROM purchase_receivings
                    WHERE hotel_id = NEW.hotel_id AND supplier_id = NEW.supplier_id
                ), 0)
                -
                COALESCE((
                    SELECT SUM(amount) FROM supplier_payments
                    WHERE hotel_id = NEW.hotel_id AND supplier_id = NEW.supplier_id
                ), 0)
            )
            BEGIN
                SELECT RAISE(ABORT, 'Supplier payment exceeds outstanding balance.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_payment_terms_supplier_hotel
            BEFORE INSERT ON supplier_payment_terms
            FOR EACH ROW
            WHEN NOT EXISTS (
                SELECT 1 FROM suppliers
                WHERE supplier_id = NEW.supplier_id AND hotel_id = NEW.hotel_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'Payment terms supplier does not belong to the same hotel.');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_payment_terms_values
            BEFORE INSERT ON supplier_payment_terms
            FOR EACH ROW
            WHEN NEW.payment_type NOT IN ('Cash', 'Credit')
                 OR NEW.credit_days < 0
                 OR NEW.advance_percentage < 0
                 OR NEW.advance_percentage > 100
                 OR (NEW.payment_type = 'Cash' AND NEW.credit_days <> 0)
                 OR (NEW.payment_type = 'Credit' AND NEW.credit_days <= 0)
            BEGIN
                SELECT RAISE(ABORT, 'Invalid supplier payment terms.');
            END
            """
        ]

        for trigger_sql in triggers:
            cursor.execute(trigger_sql)

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
