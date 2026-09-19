from contextvars import ContextVar

from database.database import get_connection


DEFAULT_HOTEL_CODE = "YADAV-HOTEL"


_current_hotel_id = ContextVar(
    "current_hotel_id",
    default=None
)


def set_current_hotel_id(hotel_id):
    """
    Set the current hotel context after validating
    that the hotel exists and is active.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT hotel_id
            FROM hotels
            WHERE hotel_id = ?
            AND is_active = 1
            """,
            (hotel_id,)
        )

        hotel = cursor.fetchone()

        if hotel is None:
            raise ValueError(
                "Hotel does not exist or is inactive."
            )

        current_hotel_id = int(hotel["hotel_id"])

        _current_hotel_id.set(current_hotel_id)

        return current_hotel_id

    finally:
        connection.close()


def set_current_hotel_by_code(hotel_code):
    """
    Set the current hotel context using hotel code.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT hotel_id
            FROM hotels
            WHERE hotel_code = ?
            AND is_active = 1
            """,
            (hotel_code,)
        )

        hotel = cursor.fetchone()

        if hotel is None:
            raise ValueError(
                "Hotel does not exist or is inactive."
            )

        current_hotel_id = int(hotel["hotel_id"])

        _current_hotel_id.set(current_hotel_id)

        return current_hotel_id

    finally:
        connection.close()


def get_current_hotel_id():
    """
    Return the current hotel ID.

    If no hotel context has been explicitly selected,
    the default active hotel is used.
    """

    current_hotel_id = _current_hotel_id.get()

    if current_hotel_id is not None:
        return current_hotel_id

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT hotel_id
            FROM hotels
            WHERE hotel_code = ?
            AND is_active = 1
            """,
            (DEFAULT_HOTEL_CODE,)
        )

        hotel = cursor.fetchone()

        if hotel is None:
            cursor.execute(
                """
                SELECT hotel_id
                FROM hotels
                WHERE is_active = 1
                ORDER BY hotel_id
                LIMIT 1
                """
            )

            hotel = cursor.fetchone()

        if hotel is None:
            raise ValueError(
                "No active hotel is available."
            )

        current_hotel_id = int(hotel["hotel_id"])

        _current_hotel_id.set(current_hotel_id)

        return current_hotel_id

    finally:
        connection.close()


def get_current_hotel():
    """
    Return the complete current hotel record.
    """

    hotel_id = get_current_hotel_id()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT *
            FROM hotels
            WHERE hotel_id = ?
            AND is_active = 1
            """,
            (hotel_id,)
        )

        hotel = cursor.fetchone()

        if hotel is None:
            raise ValueError(
                "Current hotel does not exist or is inactive."
            )

        return hotel

    finally:
        connection.close()


def clear_current_hotel():
    """
    Clear the current hotel context.
    """

    _current_hotel_id.set(None)