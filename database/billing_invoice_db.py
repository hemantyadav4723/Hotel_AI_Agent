from datetime import datetime


def create_billing_invoice_tables():
    """Create the canonical invoice registry and per-hotel daily sequence."""
    from database.database import get_connection

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoice_sequences(
                hotel_id INTEGER NOT NULL,
                invoice_date TEXT NOT NULL,
                last_number INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(hotel_id, invoice_date)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices(
                invoice_number TEXT PRIMARY KEY,
                hotel_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                invoice_status TEXT NOT NULL DEFAULT 'Issued',
                UNIQUE(hotel_id, source_type, source_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_invoices_hotel_date
            ON invoices(hotel_id, invoice_date, invoice_number)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_invoices_source
            ON invoices(hotel_id, source_type, source_id)
        """)
        connection.commit()
    finally:
        connection.close()


def _next_invoice_number(cursor, hotel_id, invoice_date):
    cursor.execute("""
        INSERT INTO invoice_sequences(hotel_id, invoice_date, last_number)
        VALUES (?, ?, 1)
        ON CONFLICT(hotel_id, invoice_date)
        DO UPDATE SET last_number = invoice_sequences.last_number + 1
    """, (hotel_id, invoice_date))

    cursor.execute("""
        SELECT last_number
        FROM invoice_sequences
        WHERE hotel_id = ? AND invoice_date = ?
    """, (hotel_id, invoice_date))

    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Unable to allocate invoice number.")

    return f"INV-{invoice_date.replace('-', '')}-{int(row['last_number']):05d}"


def create_invoice_for_source(
    cursor, hotel_id, source_type, source_id, invoice_date=None
):
    """Create or return the canonical invoice number for a hotel-scoped source."""
    if hotel_id is None:
        raise ValueError("Hotel ID is required for invoice generation.")
    if not source_type or not str(source_type).strip():
        raise ValueError("Invoice source type is required.")
    if not source_id or not str(source_id).strip():
        raise ValueError("Invoice source ID is required.")

    source_type = str(source_type).strip().upper()
    source_id = str(source_id).strip()
    invoice_date = invoice_date or datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT invoice_number
        FROM invoices
        WHERE hotel_id = ? AND source_type = ? AND source_id = ?
    """, (hotel_id, source_type, source_id))
    existing = cursor.fetchone()
    if existing is not None:
        return existing["invoice_number"]

    invoice_number = _next_invoice_number(cursor, hotel_id, invoice_date)

    cursor.execute("""
        INSERT INTO invoices(
            invoice_number, hotel_id, source_type, source_id, invoice_date
        )
        VALUES (?, ?, ?, ?, ?)
    """, (invoice_number, hotel_id, source_type, source_id, invoice_date))

    return invoice_number


def list_invoice_history(
    cursor,
    hotel_id,
    invoice_date=None,
    source_type=None,
    invoice_status=None,
    limit=100
):
    """Return invoice history for one hotel, newest first."""
    if hotel_id is None:
        raise ValueError("Hotel ID is required.")

    try:
        limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        raise ValueError("Invoice history limit must be a valid positive number.")

    query = """
        SELECT
            invoice_number,
            hotel_id,
            source_type,
            source_id,
            invoice_date,
            issued_at,
            invoice_status
        FROM invoices
        WHERE hotel_id = ?
    """
    params = [hotel_id]

    if invoice_date:
        query += " AND invoice_date = ?"
        params.append(str(invoice_date).strip())

    if source_type:
        query += " AND source_type = ?"
        params.append(str(source_type).strip().upper())

    if invoice_status:
        query += " AND invoice_status = ?"
        params.append(str(invoice_status).strip())

    query += " ORDER BY issued_at DESC, invoice_number DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    return cursor.fetchall()


def get_invoice_by_number(cursor, hotel_id, invoice_number):
    """Fetch one invoice by its hotel-scoped invoice number."""
    if hotel_id is None:
        raise ValueError("Hotel ID is required.")
    if not invoice_number or not str(invoice_number).strip():
        raise ValueError("Invoice number is required.")

    cursor.execute("""
        SELECT
            invoice_number,
            hotel_id,
            source_type,
            source_id,
            invoice_date,
            issued_at,
            invoice_status
        FROM invoices
        WHERE hotel_id = ? AND invoice_number = ?
    """, (hotel_id, str(invoice_number).strip()))

    return cursor.fetchone()
