from utils.error_logging import log_non_blocking_error
from datetime import datetime
from urllib.parse import quote_plus

from database.database import get_connection
from database.hotel_context import get_current_hotel_id, get_current_hotel


MAP_PROVIDERS = (
    "Google Maps",
    "OpenStreetMap",
    "Apple Maps",
)

INTEGRATION_STATUSES = (
    "Not Integrated",
    "Pending Integration",
    "Integrated",
    "Failed",
)


def create_maps_navigation_tables():
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS map_configurations(
                map_config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL UNIQUE,
                map_provider TEXT NOT NULL DEFAULT 'Google Maps',
                latitude REAL,
                longitude REAL,
                default_zoom INTEGER NOT NULL DEFAULT 16,
                map_place_url TEXT,
                api_enabled INTEGER NOT NULL DEFAULT 0
                    CHECK(api_enabled IN (0, 1)),
                integration_status TEXT NOT NULL DEFAULT 'Not Integrated'
                    CHECK(integration_status IN (
                        'Not Integrated',
                        'Pending Integration',
                        'Integrated',
                        'Failed'
                    )),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(hotel_id) REFERENCES hotels(hotel_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nearby_places(
                place_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                place_name TEXT NOT NULL,
                category TEXT NOT NULL,
                address TEXT,
                distance_km REAL,
                travel_time_minutes INTEGER,
                latitude REAL,
                longitude REAL,
                notes TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK(is_active IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(hotel_id) REFERENCES hotels(hotel_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS navigation_routes(
                route_id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER NOT NULL,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                route_provider TEXT NOT NULL DEFAULT 'Google Maps',
                distance_km REAL,
                eta_minutes INTEGER,
                directions_url TEXT,
                integration_status TEXT NOT NULL DEFAULT 'Not Integrated'
                    CHECK(integration_status IN (
                        'Not Integrated',
                        'Pending Integration',
                        'Integrated',
                        'Failed'
                    )),
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(hotel_id) REFERENCES hotels(hotel_id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_nearby_places_hotel_category
            ON nearby_places(hotel_id, category, is_active)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_navigation_routes_hotel_created
            ON navigation_routes(hotel_id, created_at DESC)
        """)

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _validate_coordinates(latitude, longitude):
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        raise ValueError("Latitude and longitude must be valid numbers.")

    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")

    return round(latitude, 7), round(longitude, 7)


def _validate_provider(provider):
    provider = str(provider or "").strip()
    if provider not in MAP_PROVIDERS:
        raise ValueError("Unsupported map provider.")
    return provider


def _build_map_url(provider, latitude=None, longitude=None, address=None):
    provider = _validate_provider(provider)

    if latitude is not None and longitude is not None:
        location = f"{latitude},{longitude}"
    else:
        location = str(address or "").strip()

    if not location:
        return None

    encoded = quote_plus(location)

    if provider == "Google Maps":
        return f"https://www.google.com/maps/search/?api=1&query={encoded}"

    if provider == "OpenStreetMap":
        return f"https://www.openstreetmap.org/search?query={encoded}"

    return f"https://maps.apple.com/?q={encoded}"


def build_directions_url(provider, origin, destination):
    provider = _validate_provider(provider)
    origin = str(origin or "").strip()
    destination = str(destination or "").strip()

    if not origin or not destination:
        raise ValueError("Origin and destination are required.")

    if provider == "Google Maps":
        return (
            "https://www.google.com/maps/dir/?api=1"
            f"&origin={quote_plus(origin)}"
            f"&destination={quote_plus(destination)}"
        )

    if provider == "OpenStreetMap":
        return (
            "https://www.openstreetmap.org/directions"
            f"?engine=fossgis_osrm_car&route={quote_plus(origin)}"
            f"%3B{quote_plus(destination)}"
        )

    return (
        "https://maps.apple.com/"
        f"?saddr={quote_plus(origin)}&daddr={quote_plus(destination)}"
    )


def _get_hotel_address(hotel_id):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT
                hotel_address,
                hotel_city,
                hotel_state,
                hotel_country,
                hotel_pincode
            FROM hotel_information
            WHERE hotel_id = ?
            LIMIT 1
        """, (hotel_id,))
        hotel = cursor.fetchone()

        if not hotel:
            return ""

        return ", ".join(
            str(hotel[key] or "").strip()
            for key in (
                "hotel_address",
                "hotel_city",
                "hotel_state",
                "hotel_country",
                "hotel_pincode",
            )
            if str(hotel[key] or "").strip()
        )
    finally:
        connection.close()


def get_map_configuration(hotel_id=None):
    hotel_id = int(hotel_id or get_current_hotel_id())

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM map_configurations WHERE hotel_id = ?",
            (hotel_id,),
        )
        row = cursor.fetchone()

        if row:
            return row

        address = _get_hotel_address(hotel_id)

        now = _now()
        provider = "Google Maps"
        url = _build_map_url(provider, address=address)

        cursor.execute("""
            INSERT INTO map_configurations(
                hotel_id, map_provider, latitude, longitude,
                default_zoom, map_place_url, api_enabled,
                integration_status, created_at, updated_at
            )
            VALUES(?, ?, NULL, NULL, 16, ?, 0, 'Not Integrated', ?, ?)
        """, (hotel_id, provider, url, now, now))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Maps Navigation",
        action="CREATE",
        local_values=locals(),
        details="Business operation get_map_configuration completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        cursor.execute(
            "SELECT * FROM map_configurations WHERE hotel_id = ?",
            (hotel_id,),
        )
        return cursor.fetchone()
    finally:
        connection.close()


def save_map_configuration(
    provider,
    latitude=None,
    longitude=None,
    default_zoom=16,
    api_enabled=False,
    integration_status="Not Integrated",
    hotel_id=None,
):
    hotel_id = int(hotel_id or get_current_hotel_id())
    provider = _validate_provider(provider)
    integration_status = str(integration_status or "").strip().title()

    if integration_status not in INTEGRATION_STATUSES:
        raise ValueError("Invalid integration status.")

    if latitude in ("", None) or longitude in ("", None):
        latitude = longitude = None
    else:
        latitude, longitude = _validate_coordinates(latitude, longitude)

    try:
        default_zoom = int(default_zoom)
    except (TypeError, ValueError):
        raise ValueError("Default zoom must be a whole number.")

    if not 1 <= default_zoom <= 22:
        raise ValueError("Default zoom must be between 1 and 22.")

    api_enabled = 1 if api_enabled else 0
    address = _get_hotel_address(hotel_id)

    url = _build_map_url(
        provider,
        latitude=latitude,
        longitude=longitude,
        address=address,
    )
    now = _now()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT map_config_id FROM map_configurations WHERE hotel_id = ?",
            (hotel_id,),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE map_configurations
                SET map_provider = ?,
                    latitude = ?,
                    longitude = ?,
                    default_zoom = ?,
                    map_place_url = ?,
                    api_enabled = ?,
                    integration_status = ?,
                    updated_at = ?
                WHERE hotel_id = ?
            """, (
                provider,
                latitude,
                longitude,
                default_zoom,
                url,
                api_enabled,
                integration_status,
                now,
                hotel_id,
            ))
        else:
            cursor.execute("""
                INSERT INTO map_configurations(
                    hotel_id, map_provider, latitude, longitude,
                    default_zoom, map_place_url, api_enabled,
                    integration_status, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                hotel_id,
                provider,
                latitude,
                longitude,
                default_zoom,
                url,
                api_enabled,
                integration_status,
                now,
                now,
            ))

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Maps Navigation",
        action="CREATE",
        local_values=locals(),
        details="Business operation save_map_configuration completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)

        # Read back the saved provider to ensure the configuration
        # persisted for the active hotel before returning to the UI.
        cursor.execute(
            "SELECT map_provider FROM map_configurations WHERE hotel_id = ?",
            (hotel_id,),
        )
        saved = cursor.fetchone()
        if not saved or saved["map_provider"] != provider:
            raise RuntimeError("Map provider configuration could not be persisted.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_hotel_map_url(hotel_id=None):
    row = get_map_configuration(hotel_id)
    return row["map_place_url"] if row else None


def add_nearby_place(
    place_name,
    category,
    address="",
    distance_km=None,
    travel_time_minutes=None,
    latitude=None,
    longitude=None,
    notes="",
    hotel_id=None,
):
    hotel_id = int(hotel_id or get_current_hotel_id())
    place_name = str(place_name or "").strip()
    category = str(category or "").strip()

    if not place_name:
        raise ValueError("Place name is required.")
    if not category:
        raise ValueError("Category is required.")

    if distance_km not in ("", None):
        try:
            distance_km = round(float(distance_km), 2)
            if distance_km < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("Distance must be a non-negative number.")
    else:
        distance_km = None

    if travel_time_minutes not in ("", None):
        try:
            travel_time_minutes = int(travel_time_minutes)
            if travel_time_minutes < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("Travel time must be a non-negative whole number.")
    else:
        travel_time_minutes = None

    if latitude not in ("", None) or longitude not in ("", None):
        if latitude in ("", None) or longitude in ("", None):
            raise ValueError("Both latitude and longitude are required.")
        latitude, longitude = _validate_coordinates(latitude, longitude)
    else:
        latitude = longitude = None

    now = _now()
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO nearby_places(
                hotel_id, place_name, category, address,
                distance_km, travel_time_minutes,
                latitude, longitude, notes,
                is_active, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            hotel_id, place_name, category, str(address or "").strip(),
            distance_km, travel_time_minutes,
            latitude, longitude, str(notes or "").strip(),
            now, now,
        ))
        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Maps Navigation",
        action="CREATE",
        local_values=locals(),
        details="Business operation add_nearby_place completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_nearby_places(category=None, include_inactive=False, hotel_id=None):
    hotel_id = int(hotel_id or get_current_hotel_id())

    query = """
        SELECT *
        FROM nearby_places
        WHERE hotel_id = ?
    """
    params = [hotel_id]

    if not include_inactive:
        query += " AND is_active = 1"

    if category:
        query += " AND lower(category) = lower(?)"
        params.append(str(category).strip())

    query += " ORDER BY category, place_name"

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        connection.close()


def set_nearby_place_status(place_id, is_active, hotel_id=None):
    hotel_id = int(hotel_id or get_current_hotel_id())
    now = _now()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE nearby_places
            SET is_active = ?, updated_at = ?
            WHERE place_id = ? AND hotel_id = ?
        """, (1 if is_active else 0, now, place_id, hotel_id))

        if cursor.rowcount == 0:
            raise ValueError("Nearby place not found.")

        connection.commit()
        try:
            from database.audit_db import log_business_activity
            log_business_activity(
                module="Maps Navigation",
        action="STATUS_CHANGE",
        local_values=locals(),
        details="Business operation set_nearby_place_status completed successfully.",
            )
        except Exception as exc:
            log_non_blocking_error("Non-blocking optional operation failed", exc)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_navigation_route(
    origin,
    destination,
    distance_km=None,
    eta_minutes=None,
    provider=None,
    integration_status="Not Integrated",
    notes="",
    hotel_id=None,
):
    hotel_id = int(hotel_id or get_current_hotel_id())
    config = get_map_configuration(hotel_id)
    provider = str(provider or config["map_provider"] or "Google Maps").strip()
    provider = _validate_provider(provider)

    integration_status = str(integration_status or "").strip().title()
    if integration_status not in INTEGRATION_STATUSES:
        raise ValueError("Invalid integration status.")

    origin = str(origin or "").strip()
    destination = str(destination or "").strip()
    if not origin or not destination:
        raise ValueError("Origin and destination are required.")

    if distance_km not in ("", None):
        try:
            distance_km = round(float(distance_km), 2)
            if distance_km < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("Distance must be a non-negative number.")
    else:
        distance_km = None

    if eta_minutes not in ("", None):
        try:
            eta_minutes = int(eta_minutes)
            if eta_minutes < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("ETA must be a non-negative whole number.")
    else:
        eta_minutes = None

    directions_url = build_directions_url(provider, origin, destination)
    now = _now()

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO navigation_routes(
                hotel_id, origin, destination, route_provider,
                distance_km, eta_minutes, directions_url,
                integration_status, notes, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hotel_id, origin, destination, provider,
            distance_km, eta_minutes, directions_url,
            integration_status, str(notes or "").strip(),
            now, now,
        ))
        connection.commit()
        return cursor.lastrowid, directions_url
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_navigation_routes(hotel_id=None, limit=50):
    hotel_id = int(hotel_id or get_current_hotel_id())
    try:
        limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        limit = 50

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT *
            FROM navigation_routes
            WHERE hotel_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (hotel_id, limit))
        return cursor.fetchall()
    finally:
        connection.close()
