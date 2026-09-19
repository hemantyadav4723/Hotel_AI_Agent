from utils.error_logging import log_non_blocking_error
from database.maps_navigation_db import (
    MAP_PROVIDERS,
    INTEGRATION_STATUSES,
    get_map_configuration,
    save_map_configuration,
    add_nearby_place,
    get_nearby_places,
    set_nearby_place_status,
    create_navigation_route,
    get_navigation_routes,
)
from database.hotel_context import get_current_hotel
from database.hotel_information_db import get_hotel_information
from utils.validators import validate_menu_choice, validate_non_empty
from utils.display import print_header, print_footer, print_success, print_error, press_enter


NEARBY_CATEGORIES = [
    "Airport",
    "Railway Station",
    "Hospital",
    "Restaurant",
    "Tourist Place",
    "Shopping",
    "Important Location",
    "Other",
]


def _read_optional_float(message, minimum=0):
    while True:
        raw = input(message).strip()
        if raw == "":
            return None
        try:
            value = float(raw)
            if value < minimum:
                raise ValueError
            return value
        except (ValueError, TypeError):
            print_error("Enter a valid number or leave blank.")


def _read_coordinate(message, minimum, maximum):
    while True:
        raw = input(message).strip()
        try:
            value = float(raw)
            if not minimum <= value <= maximum:
                raise ValueError
            return round(value, 7)
        except (ValueError, TypeError):
            print_error(f"Enter a value between {minimum} and {maximum}.")


def _read_optional_int(message, minimum=0):
    while True:
        raw = input(message).strip()
        if raw == "":
            return None
        try:
            value = int(raw)
            if value < minimum:
                raise ValueError
            return value
        except (ValueError, TypeError):
            print_error("Enter a valid whole number or leave blank.")


def _choose_provider(current=None):
    print("\nMap Provider")
    for index, provider in enumerate(MAP_PROVIDERS, 1):
        marker = " (Current)" if provider == current else ""
        print(f"{index}. {provider}{marker}")

    choice = validate_menu_choice(
        "Select Provider : ",
        [str(i) for i in range(1, len(MAP_PROVIDERS) + 1)]
    )
    return MAP_PROVIDERS[int(choice) - 1]


def _choose_integration_status(current=None):
    print("\nIntegration Status")
    for index, status in enumerate(INTEGRATION_STATUSES, 1):
        marker = " (Current)" if status == current else ""
        print(f"{index}. {status}{marker}")

    choice = validate_menu_choice(
        "Select Status : ",
        [str(i) for i in range(1, len(INTEGRATION_STATUSES) + 1)]
    )
    return INTEGRATION_STATUSES[int(choice) - 1]


def _view_hotel_location():
    print_header("HOTEL LOCATION")

    hotel = get_current_hotel()
    hotel_info = get_hotel_information()
    config = get_map_configuration()

    if hotel_info is None:
        raise ValueError("Hotel information is not configured for the current hotel.")

    address_parts = [
        hotel_info["hotel_address"],
        hotel_info["hotel_city"],
        hotel_info["hotel_state"],
        hotel_info["hotel_country"],
        hotel_info["hotel_pincode"],
    ]
    address = ", ".join(
        str(value).strip() for value in address_parts if str(value or "").strip()
    )

    print("Hotel Name       :", hotel["hotel_name"])
    print("Address          :", address)
    print("Map Provider     :", config["map_provider"])
    print("Latitude         :", config["latitude"] or "Not Configured")
    print("Longitude        :", config["longitude"] or "Not Configured")
    print("Default Zoom     :", config["default_zoom"])
    print("API Enabled      :", "Yes" if config["api_enabled"] else "No")
    print("Integration      :", config["integration_status"])
    print("Map URL          :", config["map_place_url"] or "Not Available")

    print_footer()


def _update_location():
    print_header("UPDATE HOTEL MAP LOCATION")

    current = get_map_configuration()
    print("Current Latitude :", current["latitude"] or "Not Configured")
    print("Current Longitude:", current["longitude"] or "Not Configured")

    latitude = _read_coordinate("Latitude : ", -90, 90)
    longitude = _read_coordinate("Longitude : ", -180, 180)

    save_map_configuration(
        current["map_provider"],
        latitude,
        longitude,
        current["default_zoom"],
        bool(current["api_enabled"]),
        current["integration_status"],
    )

    print_success("Hotel map coordinates updated successfully.")
    print("Map URL:", get_map_configuration()["map_place_url"])
    print_footer()


def _map_configuration():
    print_header("MAP CONFIGURATION")

    current = get_map_configuration()
    print("Current Provider     :", current["map_provider"])
    print("Current Integration  :", current["integration_status"])
    print("API Enabled          :", "Yes" if current["api_enabled"] else "No")

    provider = _choose_provider(current["map_provider"])
    zoom = _read_optional_int(
        f"Default Zoom (1-22, Current {current['default_zoom']}) : ",
        minimum=1
    )
    if zoom is None:
        zoom = current["default_zoom"]

    print("\nAPI Integration")
    print("1. Disabled")
    print("2. Enabled")
    api_choice = validate_menu_choice("Select API Setting : ", ["1", "2"])
    api_enabled = api_choice == "2"

    integration_status = _choose_integration_status(
        current["integration_status"]
    )

    latitude = current["latitude"]
    longitude = current["longitude"]

    update_coordinates = input(
        "\nUpdate coordinates? (Y/N) : "
    ).strip().lower()

    if update_coordinates in ("y", "yes"):
        latitude = _read_coordinate("Latitude : ", -90, 90)
        longitude = _read_coordinate("Longitude : ", -180, 180)

    save_map_configuration(
        provider,
        latitude,
        longitude,
        zoom,
        api_enabled,
        integration_status,
    )

    print_success("Map configuration saved successfully.")
    print_footer()


def _view_nearby_places():
    print_header("NEARBY PLACES")

    places = get_nearby_places(include_inactive=True)

    if not places:
        print("No nearby places configured.")
        print_footer()
        return

    for place in places:
        status = "Active" if place["is_active"] else "Inactive"
        print("-" * 80)
        print("ID                 :", place["place_id"])
        print("Place              :", place["place_name"])
        print("Category           :", place["category"])
        print("Address            :", place["address"] or "-")
        print("Distance (km)      :", place["distance_km"] if place["distance_km"] is not None else "-")
        print("Travel Time (min)  :", place["travel_time_minutes"] if place["travel_time_minutes"] is not None else "-")
        print("Coordinates        :", (
            f"{place['latitude']}, {place['longitude']}"
            if place["latitude"] is not None and place["longitude"] is not None
            else "-"
        ))
        print("Notes              :", place["notes"] or "-")
        print("Status             :", status)

    print_footer()


def _add_nearby_place():
    print_header("ADD NEARBY PLACE")

    place_name = validate_non_empty("Place Name : ")

    print("\nCategory")
    for index, category in enumerate(NEARBY_CATEGORIES, 1):
        print(f"{index}. {category}")

    category_choice = validate_menu_choice(
        "Select Category : ",
        [str(i) for i in range(1, len(NEARBY_CATEGORIES) + 1)]
    )
    category = NEARBY_CATEGORIES[int(category_choice) - 1]

    address = input("Address (Optional) : ").strip()
    distance = _read_optional_float("Distance in KM (Optional) : ")
    travel_time = _read_optional_int("Travel Time in Minutes (Optional) : ")

    print("\nCoordinates are optional.")
    raw_latitude = input("Latitude (Optional) : ").strip()
    raw_longitude = input("Longitude (Optional) : ")

    if raw_latitude or raw_longitude:
        try:
            latitude = float(raw_latitude)
            longitude = float(raw_longitude)
        except ValueError:
            raise ValueError("Both coordinates must be valid numbers.")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("Nearby place coordinates are out of range.")
    else:
        latitude = longitude = None

    notes = input("Notes (Optional) : ").strip()

    place_id = add_nearby_place(
        place_name,
        category,
        address,
        distance,
        travel_time,
        latitude,
        longitude,
        notes,
    )

    print_success(f"Nearby place added successfully. ID: {place_id}")
    print_footer()


def _change_nearby_place_status():
    _view_nearby_places()

    place_id = validate_non_empty("Enter Nearby Place ID : ")

    print("1. Active")
    print("2. Inactive")

    choice = validate_menu_choice("Select Status : ", ["1", "2"])
    set_nearby_place_status(place_id, choice == "1")

    print_success("Nearby place status updated successfully.")


def _nearby_places_management():
    while True:
        print_header("NEARBY PLACES MANAGEMENT")
        print("1. View Nearby Places")
        print("2. Add Nearby Place")
        print("3. Activate / Deactivate Place")
        print("4. Back")
        print_footer()

        choice = validate_menu_choice(
            "Enter Choice : ",
            ["1", "2", "3", "4"]
        )

        try:
            if choice == "1":
                _view_nearby_places()
            elif choice == "2":
                _add_nearby_place()
            elif choice == "3":
                _change_nearby_place_status()
            else:
                break
        except ValueError as error:
            print_error(str(error))

        if choice != "4":
            press_enter()


def _create_navigation():
    print_header("NAVIGATION / ROUTE")

    print("Use a location name, address, hotel, airport, railway station,")
    print("or any other map-searchable origin and destination.")

    origin = validate_non_empty("Origin : ")
    destination = validate_non_empty("Destination : ")

    config = get_map_configuration()
    provider = _choose_provider(config["map_provider"])

    distance = _read_optional_float(
        "Distance in KM (Optional; live API can populate later) : "
    )
    eta = _read_optional_int(
        "Estimated Travel Time in Minutes (Optional; live API can populate later) : "
    )

    integration_status = _choose_integration_status(
        config["integration_status"]
    )
    notes = input("Notes (Optional) : ").strip()

    route_id, directions_url = create_navigation_route(
        origin,
        destination,
        distance,
        eta,
        provider,
        integration_status,
        notes,
    )

    print_success(f"Navigation route saved. Route ID: {route_id}")
    print("Provider     :", provider)
    print("Origin       :", origin)
    print("Destination  :", destination)
    print("Distance     :", f"{distance} KM" if distance is not None else "Not Available")
    print("ETA          :", f"{eta} minutes" if eta is not None else "Not Available")
    print("Directions   :", directions_url)
    print("\nDistance/ETA remain API-ready foundation values until a live")
    print("map/routing provider integration is configured.")
    print_footer()


def _view_navigation_history():
    print_header("NAVIGATION HISTORY")

    routes = get_navigation_routes()

    if not routes:
        print("No navigation routes found.")
        print_footer()
        return

    for route in routes:
        print("-" * 80)
        print("Route ID        :", route["route_id"])
        print("Origin          :", route["origin"])
        print("Destination     :", route["destination"])
        print("Provider        :", route["route_provider"])
        print("Distance (KM)   :", route["distance_km"] if route["distance_km"] is not None else "-")
        print("ETA (Minutes)   :", route["eta_minutes"] if route["eta_minutes"] is not None else "-")
        print("Integration     :", route["integration_status"])
        print("Directions URL  :", route["directions_url"])
        print("Notes           :", route["notes"] or "-")
        print("Created         :", route["created_at"])

    print_footer()


def _open_map():
    print_header("MAP LINK")

    config = get_map_configuration()
    url = config["map_place_url"]

    if not url:
        print_error("Map URL is not available.")
        print_footer()
        return

    print("Map Provider :", config["map_provider"])
    print("Map URL      :", url)
    print("\nOpen this link in your browser to view the hotel location.")

    try:
        import webbrowser
        webbrowser.open(url)
    except Exception as exc:
        log_non_blocking_error("Non-blocking optional operation failed", exc)

    print_footer()


def maps_navigation():
    while True:
        print_header("MAPS & NAVIGATION")

        print("1. Hotel Location")
        print("2. Update Hotel Coordinates")
        print("3. Map Configuration")
        print("4. Nearby Places")
        print("5. Navigation / Route")
        print("6. Navigation History")
        print("7. Open Hotel Map")
        print("8. Back")

        print_footer()

        choice = validate_menu_choice(
            "Enter Choice : ",
            ["1", "2", "3", "4", "5", "6", "7", "8"]
        )

        try:
            if choice == "1":
                _view_hotel_location()
            elif choice == "2":
                _update_location()
            elif choice == "3":
                _map_configuration()
            elif choice == "4":
                _nearby_places_management()
            elif choice == "5":
                _create_navigation()
            elif choice == "6":
                _view_navigation_history()
            elif choice == "7":
                _open_map()
            else:
                break
        except ValueError as error:
            print_error(str(error))

        if choice != "8":
            press_enter()
