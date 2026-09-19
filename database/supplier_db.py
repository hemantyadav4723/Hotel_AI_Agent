from utils.error_logging import log_non_blocking_error
from database.database import get_connection
from database.hotel_context import get_current_hotel_id


def create_supplier_table():
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers(
            supplier_id TEXT PRIMARY KEY,
            supplier_name TEXT NOT NULL,
            mobile TEXT,
            contact_person TEXT,
            email TEXT,
            alternate_mobile TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            pincode TEXT,
            gstin TEXT,
            tax_registration_number TEXT,
            tax_type TEXT NOT NULL DEFAULT 'GST',
            tax_status TEXT NOT NULL DEFAULT 'Not Registered',
            hotel_id INTEGER,
            supplier_type TEXT NOT NULL DEFAULT 'General',
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT,
            updated_at TEXT
        )
        """)

        columns = {row["name"] for row in cursor.execute("PRAGMA table_info(suppliers)").fetchall()}
        if "contact_person" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN contact_person TEXT")
        if "email" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN email TEXT")
        if "alternate_mobile" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN alternate_mobile TEXT")
        if "address" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN address TEXT")
        if "city" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN city TEXT")
        if "state" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN state TEXT")
        if "pincode" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN pincode TEXT")
        if "gstin" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN gstin TEXT")
        if "tax_registration_number" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN tax_registration_number TEXT")
        if "tax_type" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN tax_type TEXT NOT NULL DEFAULT 'GST'")
        if "tax_status" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN tax_status TEXT NOT NULL DEFAULT 'Not Registered'")
        if "hotel_id" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN hotel_id INTEGER")
        if "supplier_type" not in columns:
            cursor.execute(
                "ALTER TABLE suppliers ADD COLUMN supplier_type TEXT NOT NULL DEFAULT 'General'"
            )
        if "status" not in columns:
            cursor.execute(
                "ALTER TABLE suppliers ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'"
            )
        if "created_at" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN created_at TEXT")
        if "updated_at" not in columns:
            cursor.execute("ALTER TABLE suppliers ADD COLUMN updated_at TEXT")

        hotel = cursor.execute("""
            SELECT hotel_id FROM hotels
            WHERE hotel_code = ?
            LIMIT 1
        """, ("YADAV-HOTEL",)).fetchone()
        if hotel is not None:
            cursor.execute("""
                UPDATE suppliers SET hotel_id = ?
                WHERE hotel_id IS NULL
            """, (hotel["hotel_id"],))

        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE suppliers
            SET supplier_type = COALESCE(NULLIF(TRIM(supplier_type), ''), 'General'),
                status = COALESCE(NULLIF(TRIM(status), ''), 'Active'),
                tax_type = COALESCE(NULLIF(TRIM(tax_type), ''), 'GST'),
                tax_status = COALESCE(NULLIF(TRIM(tax_status), ''), 'Not Registered'),
                created_at = COALESCE(created_at, ?),
                updated_at = COALESCE(updated_at, ?)
            WHERE supplier_type IS NULL
               OR TRIM(supplier_type) = ''
               OR status IS NULL
               OR TRIM(status) = ''
               OR tax_type IS NULL
               OR TRIM(tax_type) = ''
               OR tax_status IS NULL
               OR TRIM(tax_status) = ''
               OR created_at IS NULL
               OR updated_at IS NULL
        """, (now, now))

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_suppliers_hotel_id
            ON suppliers(hotel_id)
        """)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_supplier(supplier_id, supplier_name, mobile, supplier_type="General", contact_person=None, email=None, alternate_mobile=None, address=None, city=None, state=None, pincode=None, gstin=None, tax_registration_number=None, tax_type="GST", tax_status="Not Registered"):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO suppliers(
            supplier_id, supplier_name, mobile, contact_person, email, alternate_mobile, address, city, state, pincode, gstin, tax_registration_number, tax_type, tax_status, hotel_id,
            supplier_type, status, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)
        """, (supplier_id, supplier_name, mobile, contact_person, email, alternate_mobile, address, city, state, pincode, gstin, tax_registration_number, tax_type, tax_status, hotel_id, supplier_type, now, now))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Supplier",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_supplier completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def view_supplier():
    print("=" * 60)
    print("          SUPPLIERS")
    print("=" * 60)
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        suppliers = cursor.execute("""
            SELECT * FROM suppliers
            WHERE hotel_id = ?
            ORDER BY supplier_name
        """, (hotel_id,)).fetchall()
        if suppliers:
            for supplier in suppliers:
                print("=" * 60)
                print("Supplier ID   :", supplier["supplier_id"])
                print("Supplier Name :", supplier["supplier_name"])
                print("Mobile        :", supplier["mobile"] or "Not Provided")
                print("Contact Person:", supplier["contact_person"] or "Not Provided")
                print("Email         :", supplier["email"] or "Not Provided")
                print("Alt. Mobile   :", supplier["alternate_mobile"] or "Not Provided")
                print("Address       :", supplier["address"] or "Not Provided")
                print("City          :", supplier["city"] or "Not Provided")
                print("State         :", supplier["state"] or "Not Provided")
                print("PIN Code      :", supplier["pincode"] or "Not Provided")
                print("GSTIN         :", supplier["gstin"] or "Not Provided")
                print("Tax Reg. No.  :", supplier["tax_registration_number"] or "Not Provided")
                print("Tax Type      :", supplier["tax_type"] or "GST")
                print("Tax Status    :", supplier["tax_status"] or "Not Registered")
                print("Type          :", supplier["supplier_type"] or "General")
                print("Status        :", supplier["status"] or "Active")
                print("=" * 60)
        else:
            print("No Suppliers Found.")
    finally:
        connection.close()


def search_supplier():
    supplier_id = input("Enter Supplier ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        supplier = connection.execute(
            "SELECT * FROM suppliers WHERE supplier_id = ? AND hotel_id = ?",
            (supplier_id, hotel_id)
        ).fetchone()
        if supplier:
            print("=" * 60)
            print("Supplier ID   :", supplier["supplier_id"])
            print("Supplier Name :", supplier["supplier_name"])
            print("Mobile        :", supplier["mobile"] or "Not Provided")
            print("Contact Person:", supplier["contact_person"] or "Not Provided")
            print("Email         :", supplier["email"] or "Not Provided")
            print("Alt. Mobile   :", supplier["alternate_mobile"] or "Not Provided")
            print("Address       :", supplier["address"] or "Not Provided")
            print("City          :", supplier["city"] or "Not Provided")
            print("State         :", supplier["state"] or "Not Provided")
            print("PIN Code      :", supplier["pincode"] or "Not Provided")
            print("GSTIN         :", supplier["gstin"] or "Not Provided")
            print("Tax Reg. No.  :", supplier["tax_registration_number"] or "Not Provided")
            print("Tax Type      :", supplier["tax_type"] or "GST")
            print("Tax Status    :", supplier["tax_status"] or "Not Registered")
            print("Type          :", supplier["supplier_type"] or "General")
            print("Status        :", supplier["status"] or "Active")
            print("=" * 60)
        else:
            print("Supplier Not Found.")
    finally:
        connection.close()


def update_supplier():
    from utils.validators import (
        validate_name,
        validate_mobile,
        validate_optional_mobile,
        validate_email,
        validate_pincode,
        validate_location,
        validate_address,
        validate_optional_gstin,
        validate_tax_type,
        validate_tax_status,
    )

    supplier_id = input("Enter Supplier ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        supplier = cursor.execute(
            "SELECT * FROM suppliers WHERE supplier_id = ? AND hotel_id = ?",
            (supplier_id, hotel_id)
        ).fetchone()
        if not supplier:
            print("Supplier Not Found.")
            return

        supplier_name = validate_name(
            f"Supplier Name ({supplier['supplier_name']}) : ",
            supplier['supplier_name']
        )
        mobile = validate_mobile(
            f"Mobile ({supplier['mobile'] or 'Not Provided'}) : ",
            supplier['mobile']
        )
        supplier_type = input(
            f"Supplier Type ({supplier['supplier_type'] or 'General'}) : "
        ).strip() or supplier['supplier_type'] or 'General'

        contact_person = validate_name(
            f"Contact Person ({supplier['contact_person'] or 'Not Provided'}) : ",
            supplier['contact_person']
        )
        email = validate_email(
            f"Email ({supplier['email'] or 'Not Provided'}) : ",
            supplier['email']
        )
        alternate_mobile = validate_optional_mobile(
            f"Alternate Mobile ({supplier['alternate_mobile'] or 'Not Provided'}) : ",
            supplier['alternate_mobile']
        )
        address = validate_address(
            f"Address ({supplier['address'] or 'Not Provided'}) : ",
            supplier['address']
        )
        city = validate_location(
            f"City ({supplier['city'] or 'Not Provided'}) : ",
            supplier['city']
        )
        state = validate_location(
            f"State ({supplier['state'] or 'Not Provided'}) : ",
            supplier['state']
        )
        pincode = validate_pincode(
            f"PIN Code ({supplier['pincode'] or 'Not Provided'}) : ",
            supplier['pincode']
        )
        gstin = validate_optional_gstin(
            f"GSTIN ({supplier['gstin'] or 'Not Provided'}) : ",
            supplier['gstin']
        )
        tax_registration_number = input(
            f"Tax Registration No. ({supplier['tax_registration_number'] or 'Not Provided'}) : "
        ).strip() or supplier['tax_registration_number']

        tax_type = validate_tax_type(
            f"Tax Type ({supplier['tax_type'] or 'GST'}) : ",
            supplier['tax_type'] or 'GST'
        )
        tax_status = validate_tax_status(
            f"Tax Status ({supplier['tax_status'] or 'Not Registered'}) : ",
            supplier['tax_status'] or 'Not Registered'
        )

        if tax_status in ["Registered", "Composition"] and not gstin:
            raise ValueError("GSTIN is required for Registered or Composition tax status.")

        from datetime import datetime
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE suppliers
            SET supplier_name = ?,
                mobile = ?,
                supplier_type = ?,
                contact_person = ?,
                email = ?,
                alternate_mobile = ?,
                address = ?,
                city = ?,
                state = ?,
                pincode = ?,
                gstin = ?,
                tax_registration_number = ?,
                tax_type = ?,
                tax_status = ?,
                updated_at = ?
            WHERE supplier_id = ? AND hotel_id = ?
        """, (
            supplier_name, mobile, supplier_type, contact_person, email,
            alternate_mobile, address, city, state, pincode, gstin,
            tax_registration_number, tax_type, tax_status, updated_at,
            supplier_id, hotel_id
        ))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Supplier",
        action="UPDATE",
        local_values=locals(),
        details="Business operation update_supplier completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Supplier Updated Successfully.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def _set_supplier_status(new_status):
    from database.permission_db import require_current_user_permission
    require_current_user_permission("Inventory", "Update")
    supplier_id = input("Enter Supplier ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        supplier = cursor.execute("""
            SELECT supplier_id, status
            FROM suppliers
            WHERE supplier_id = ? AND hotel_id = ?
        """, (supplier_id, hotel_id)).fetchone()
        if supplier is None:
            print("Supplier Not Found.")
            return
        if supplier["status"] == new_status:
            print(f"Supplier is already {new_status}.")
            return
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE suppliers
            SET status = ?, updated_at = ?
            WHERE supplier_id = ? AND hotel_id = ?
        """, (new_status, now, supplier_id, hotel_id))
        connection.commit()
        print(f"Supplier {new_status} Successfully.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def deactivate_supplier():
    _set_supplier_status("Inactive")


def activate_supplier():
    _set_supplier_status("Active")


def delete_supplier():
    supplier_id = input("Enter Supplier ID : ").strip().upper()
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        if cursor.execute(
            "SELECT 1 FROM suppliers WHERE supplier_id = ? AND hotel_id = ?",
            (supplier_id, hotel_id)
        ).fetchone() is None:
            print("Supplier Not Found.")
            return
        if cursor.execute("""
            SELECT 1 FROM inventory
            WHERE supplier_id = ? AND hotel_id = ?
            LIMIT 1
        """, (supplier_id, hotel_id)).fetchone():
            print("Supplier is linked with inventory items and cannot be deleted.")
            connection.rollback()
            return
        cursor.execute(
            "DELETE FROM suppliers WHERE supplier_id = ? AND hotel_id = ?",
            (supplier_id, hotel_id)
        )
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Supplier",
        action="DELETE",
        local_values=locals(),
        details="Business operation delete_supplier completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        print("Supplier Deleted Successfully.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def supplier_exists(supplier_id):
    hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT 1 FROM suppliers WHERE supplier_id = ? AND hotel_id = ?",
            (supplier_id, hotel_id)
        ).fetchone() is not None
    finally:
        connection.close()
