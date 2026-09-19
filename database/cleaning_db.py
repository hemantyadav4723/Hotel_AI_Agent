from database.database import get_connection
from database.hotel_context import get_current_hotel_id

CLEANING_ENTITY_TYPES = ("ROOM", "TABLE", "OTHER")
CLEANING_STATUSES = ("Cleaning Required", "Cleaning In Progress", "Completed", "Cancelled")


def create_cleaning_tasks_table(connection=None):
    owns_connection = connection is None
    if owns_connection:
        connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cleaning_tasks(
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                cleaning_reason TEXT NOT NULL,
                task_status TEXT NOT NULL DEFAULT 'Cleaning Required',
                assigned_staff_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                completed_at TEXT,
                cancelled_at TEXT,
                notes TEXT,
                CHECK(entity_type IN ('ROOM', 'TABLE', 'OTHER')),
                CHECK(task_status IN ('Cleaning Required', 'Cleaning In Progress', 'Completed', 'Cancelled'))
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cleaning_tasks_hotel_status
            ON cleaning_tasks(hotel_id, task_status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cleaning_tasks_entity
            ON cleaning_tasks(hotel_id, entity_type, entity_id)
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_cleaning_active_entity
            ON cleaning_tasks(hotel_id, entity_type, entity_id)
            WHERE task_status IN ('Cleaning Required', 'Cleaning In Progress')
        """)
        if owns_connection:
            connection.commit()
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def create_cleaning_task(entity_type, entity_id, cleaning_reason, hotel_id=None, connection=None, assigned_staff_id=None, notes=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    entity_type = str(entity_type or '').strip().upper()
    entity_id = str(entity_id or '').strip().upper()
    cleaning_reason = str(cleaning_reason or '').strip()
    if entity_type not in CLEANING_ENTITY_TYPES:
        raise ValueError("Invalid cleaning entity type.")
    if not entity_id or not cleaning_reason:
        raise ValueError("Cleaning item and reason are required.")

    owns_connection = connection is None
    if owns_connection:
        connection = get_connection()
    try:
        create_cleaning_tasks_table(connection)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT task_id
            FROM cleaning_tasks
            WHERE hotel_id = ? AND entity_type = ? AND entity_id = ?
              AND task_status IN ('Cleaning Required', 'Cleaning In Progress')
            LIMIT 1
        """, (hotel_id, entity_type, entity_id))
        existing = cursor.fetchone()
        if existing:
            return existing["task_id"]

        cursor.execute("""
            INSERT INTO cleaning_tasks
                (hotel_id, entity_type, entity_id, cleaning_reason, assigned_staff_id, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (hotel_id, entity_type, entity_id, cleaning_reason, assigned_staff_id, notes))
        task_id = cursor.lastrowid
        if owns_connection:
            connection.commit()
        return task_id
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def update_cleaning_task_status(entity_type, entity_id, new_status, hotel_id=None, connection=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    entity_type = str(entity_type or '').strip().upper()
    entity_id = str(entity_id or '').strip().upper()
    if new_status not in CLEANING_STATUSES:
        raise ValueError("Invalid cleaning status.")

    owns_connection = connection is None
    if owns_connection:
        connection = get_connection()
    try:
        create_cleaning_tasks_table(connection)
        cursor = connection.cursor()
        if new_status == "Cleaning In Progress":
            cursor.execute("""
                UPDATE cleaning_tasks
                SET task_status = 'Cleaning In Progress', started_at = COALESCE(started_at, CURRENT_TIMESTAMP)
                WHERE task_id = (
                    SELECT task_id FROM cleaning_tasks
                    WHERE hotel_id = ? AND entity_type = ? AND entity_id = ?
                      AND task_status = 'Cleaning Required'
                    ORDER BY task_id DESC LIMIT 1
                )
            """, (hotel_id, entity_type, entity_id))
        elif new_status == "Completed":
            cursor.execute("""
                UPDATE cleaning_tasks
                SET task_status = 'Completed',
                    started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                    completed_at = CURRENT_TIMESTAMP
                WHERE hotel_id = ? AND entity_type = ? AND entity_id = ?
                  AND task_status IN ('Cleaning Required', 'Cleaning In Progress')
            """, (hotel_id, entity_type, entity_id))
        elif new_status == "Cancelled":
            cursor.execute("""
                UPDATE cleaning_tasks
                SET task_status = 'Cancelled', cancelled_at = CURRENT_TIMESTAMP
                WHERE hotel_id = ? AND entity_type = ? AND entity_id = ?
                  AND task_status IN ('Cleaning Required', 'Cleaning In Progress')
            """, (hotel_id, entity_type, entity_id))
        else:
            raise ValueError("Cleaning Required is created automatically; use create_cleaning_task().")
        if owns_connection:
            connection.commit()
        return cursor.rowcount
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def get_cleaning_tasks(hotel_id=None, task_status=None, entity_type=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = "SELECT * FROM cleaning_tasks WHERE hotel_id = ?"
        params = [hotel_id]
        if task_status:
            query += " AND task_status = ?"; params.append(task_status)
        if entity_type:
            query += " AND entity_type = ?"; params.append(str(entity_type).strip().upper())
        query += " ORDER BY CASE task_status WHEN 'Cleaning Required' THEN 1 WHEN 'Cleaning In Progress' THEN 2 ELSE 3 END, created_at DESC, task_id DESC"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def assign_cleaning_task(task_id, staff_id, hotel_id=None):
    if hotel_id is None:
        hotel_id = get_current_hotel_id()
    staff_id = str(staff_id or '').strip()
    if not staff_id:
        raise ValueError("Staff ID is required.")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE cleaning_tasks SET assigned_staff_id = ?
            WHERE task_id = ? AND hotel_id = ?
              AND task_status IN ('Cleaning Required', 'Cleaning In Progress')
        """, (staff_id, task_id, hotel_id))
        if cursor.rowcount != 1:
            raise ValueError("Active cleaning task not found.")
        connection.commit()
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()


def sync_existing_cleaning_tasks(connection=None):
    """Backfill active cleaning tasks for rooms/tables already awaiting cleaning."""
    owns_connection = connection is None
    if owns_connection:
        connection = get_connection()
    try:
        create_cleaning_tasks_table(connection)
        cursor = connection.cursor()
        cursor.execute("SELECT hotel_id, room_number, room_status FROM rooms WHERE room_status IN ('Dirty', 'Cleaning')")
        for row in cursor.fetchall():
            reason = "Checkout Cleaning"
            create_cleaning_task("ROOM", row["room_number"], reason, hotel_id=row["hotel_id"], connection=connection)
            if row["room_status"] == "Cleaning":
                update_cleaning_task_status("ROOM", row["room_number"], "Cleaning In Progress", hotel_id=row["hotel_id"], connection=connection)
        cursor.execute("SELECT hotel_id, table_number, table_status FROM tables WHERE table_status IN ('Cleaning Required', 'Cleaning In Progress')")
        for row in cursor.fetchall():
            create_cleaning_task("TABLE", row["table_number"], "After Guest Use", hotel_id=row["hotel_id"], connection=connection)
            if row["table_status"] == "Cleaning In Progress":
                update_cleaning_task_status("TABLE", row["table_number"], "Cleaning In Progress", hotel_id=row["hotel_id"], connection=connection)
        if owns_connection:
            connection.commit()
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()
