from database.database import get_connection

from database.audit_db import log_business_activity
def create_hotels_table():

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hotels(

                hotel_id INTEGER PRIMARY KEY AUTOINCREMENT,

                hotel_code TEXT NOT NULL UNIQUE,

                hotel_name TEXT NOT NULL,

                is_active INTEGER NOT NULL DEFAULT 1,

                created_at TEXT,
                updated_at TEXT

            )
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def initialize_hotel_master():

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT hotel_id
            FROM hotels
            WHERE hotel_code = ?
        """, ("YADAV-HOTEL",))

        hotel = cursor.fetchone()

        if hotel:
            return

        cursor.execute("""
            INSERT INTO hotels(
                hotel_code,
                hotel_name,
                is_active,
                created_at,
                updated_at
            )
            VALUES(
                ?, ?, 1,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
        """, (
            "YADAV-HOTEL",
            "YADAV HOTEL"
        ))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def create_hotel_information_table():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hotel_information(

        id INTEGER PRIMARY KEY,
        hotel_id INTEGER NOT NULL DEFAULT 1 UNIQUE,

        hotel_name TEXT,
        hotel_owner TEXT,
        hotel_type TEXT,
        hotel_established TEXT,
        hotel_description TEXT,

        hotel_address TEXT,
        hotel_city TEXT,
        hotel_state TEXT,
        hotel_country TEXT,
        hotel_pincode TEXT,

        hotel_mobile TEXT,
        hotel_email TEXT,
        hotel_website TEXT,
        hotel_rating TEXT,

        total_rooms INTEGER,

        restaurant TEXT,
        parking TEXT,
        wifi TEXT,
        laundry TEXT,

        hotel_checkin_time TEXT,
        hotel_checkout_time TEXT,
        hotel_opening TEXT,
        hotel_closing TEXT,

        hotel_currency TEXT,
        hotel_support_email TEXT,
        hotel_support_mobile TEXT,

        gst_rate REAL NOT NULL DEFAULT 0.05

        )
    """)

    connection.commit()
    connection.close()

def migrate_hotel_information_configuration():

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("PRAGMA table_info(hotel_information)")
        columns = {row["name"] for row in cursor.fetchall()}

        if "gst_rate" not in columns:
            cursor.execute("""
                ALTER TABLE hotel_information
                ADD COLUMN gst_rate REAL NOT NULL DEFAULT 0.05
            """)

        if "hotel_id" not in columns:
            cursor.execute("""
                ALTER TABLE hotel_information
                ADD COLUMN hotel_id INTEGER NOT NULL DEFAULT 1
            """)

        cursor.execute("""
            UPDATE hotel_information
            SET hotel_id = 1
            WHERE hotel_id IS NULL
        """)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def save_hotel_information(
    hotel_name,
    hotel_owner,
    hotel_type,
    hotel_established,
    hotel_description,
    hotel_address,
    hotel_city,
    hotel_state,
    hotel_country,
    hotel_pincode,
    hotel_mobile,
    hotel_email,
    hotel_website,
    hotel_rating,
    total_rooms,
    restaurant,
    parking,
    wifi,
    laundry,
    hotel_checkin_time,
    hotel_checkout_time,
    hotel_opening,
    hotel_closing,
    hotel_currency,
    hotel_support_email,
    hotel_support_mobile,
    gst_rate=0.05,
    hotel_id=None
):

    connection = get_connection()

    try:
        cursor = connection.cursor()

        if hotel_id is None:
            from database.hotel_context import get_current_hotel_id
            hotel_id = get_current_hotel_id()

        cursor.execute("""
        INSERT OR REPLACE INTO hotel_information(
            id,
            hotel_id,
            hotel_name,
            hotel_owner,
            hotel_type,
            hotel_established,
            hotel_description,
            hotel_address,
            hotel_city,
            hotel_state,
            hotel_country,
            hotel_pincode,
            hotel_mobile,
            hotel_email,
            hotel_website,
            hotel_rating,
            total_rooms,
            restaurant,
            parking,
            wifi,
            laundry,
            hotel_checkin_time,
            hotel_checkout_time,
            hotel_opening,
            hotel_closing,
            hotel_currency,
            hotel_support_email,
            hotel_support_mobile,
            gst_rate
        )
        VALUES(
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """, (
            hotel_id,
            hotel_id,
            hotel_name,
            hotel_owner,
            hotel_type,
            hotel_established,
            hotel_description,
            hotel_address,
            hotel_city,
            hotel_state,
            hotel_country,
            hotel_pincode,
            hotel_mobile,
            hotel_email,
            hotel_website,
            hotel_rating,
            total_rooms,
            restaurant,
            parking,
            wifi,
            laundry,
            hotel_checkin_time,
            hotel_checkout_time,
            hotel_opening,
            hotel_closing,
            hotel_currency,
            hotel_support_email,
            hotel_support_mobile,
            gst_rate
        ))

        connection.commit()
        log_business_activity(
            "Hotel Information",
            "CREATE",
            local_values={"hotel_id": hotel_id},
            details="Hotel master information saved.",
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

def initialize_hotel_information():

    connection = get_connection()
    cursor = connection.cursor()

    from database.hotel_context import get_current_hotel_id
    hotel_id = get_current_hotel_id()

    cursor.execute("""
        SELECT COUNT(*) FROM hotel_information
        WHERE hotel_id = ?
    """, (hotel_id,))

    count = cursor.fetchone()[0]

    connection.close()

    if count > 0:
        return

    save_hotel_information(
        "YADAV HOTEL",
        "Sandeep Yadav",
        "Luxury Hotel",
        "2026",
        "Premium Hotel with Restaurant, Rooms and Banquet",
        "Alwar, Rajasthan",
        "Alwar",
        "Rajasthan",
        "India",
        "301001",
        "9876543210",
        "info@yadavhotel.com",
        "www.yadavhotel.com",
        "4.8/5",
        50,
        "Available",
        "Available",
        "Available",
        "Available",
        "12:00 PM",
        "11:00 AM",
        "08:00 AM",
        "11:00 PM",
        "INR",
        "support@yadavhotel.com",
        "9876543210",
        0.05,
        hotel_id
    )

def get_hotel_information():

    from database.hotel_context import get_current_hotel_id
    hotel_id = get_current_hotel_id()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM hotel_information WHERE hotel_id = ?",
        (hotel_id,)
    )

    hotel = cursor.fetchone()

    connection.close()

    return hotel

def update_hotel_information(
    hotel_name,
    hotel_owner,
    hotel_type,
    hotel_established,
    hotel_description,
    hotel_address,
    hotel_city,
    hotel_state,
    hotel_country,
    hotel_pincode,
    hotel_mobile,
    hotel_email,
    hotel_website,
    hotel_rating,
    total_rooms,
    restaurant,
    parking,
    wifi,
    laundry,
    hotel_checkin_time,
    hotel_checkout_time,
    hotel_opening,
    hotel_closing,
    hotel_currency,
    hotel_support_email,
    hotel_support_mobile
):

    from database.hotel_context import get_current_hotel_id
    hotel_id = get_current_hotel_id()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE hotel_information
            SET
                hotel_name = ?,
                hotel_owner = ?,
                hotel_type = ?,
                hotel_established = ?,
                hotel_description = ?,
                hotel_address = ?,
                hotel_city = ?,
                hotel_state = ?,
                hotel_country = ?,
                hotel_pincode = ?,
                hotel_mobile = ?,
                hotel_email = ?,
                hotel_website = ?,
                hotel_rating = ?,
                total_rooms = ?,
                restaurant = ?,
                parking = ?,
                wifi = ?,
                laundry = ?,
                hotel_checkin_time = ?,
                hotel_checkout_time = ?,
                hotel_opening = ?,
                hotel_closing = ?,
                hotel_currency = ?,
                hotel_support_email = ?,
                hotel_support_mobile = ?
            WHERE hotel_id = ?
        """, (
            hotel_name,
            hotel_owner,
            hotel_type,
            hotel_established,
            hotel_description,
            hotel_address,
            hotel_city,
            hotel_state,
            hotel_country,
            hotel_pincode,
            hotel_mobile,
            hotel_email,
            hotel_website,
            hotel_rating,
            total_rooms,
            restaurant,
            parking,
            wifi,
            laundry,
            hotel_checkin_time,
            hotel_checkout_time,
            hotel_opening,
            hotel_closing,
            hotel_currency,
            hotel_support_email,
            hotel_support_mobile,
            hotel_id
        ))

        connection.commit()
        log_business_activity(
            "Hotel Information",
            "UPDATE",
            local_values={"hotel_id": hotel_id},
            details="Hotel master information updated.",
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
