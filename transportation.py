from database.transportation_db import (
    TRANSPORTATION_TYPES,
    TRANSPORTATION_STATUSES,
    VEHICLE_STATUSES,
    DRIVER_STATUSES,
    INTEGRATION_STATUSES,
    create_transportation_request,
    get_transportation_requests,
    search_transportation_requests,
    update_transportation_request,
    add_vehicle,
    get_vehicles,
    update_vehicle_status,
    add_driver,
    get_drivers,
    update_driver_status,
)
from database.permission_db import require_current_user_permission
import sqlite3
from utils.validators import validate_menu_choice, validate_non_empty


def _pause():
    input("\nPress Enter To Continue...")


def _print_request(row):
    print("-" * 78)
    print(f"Request ID          : {row['request_id']}")
    print(f"Customer ID         : {row['customer_id'] or '-'}")
    print(f"Guest Name          : {row['guest_name'] or '-'}")
    print(f"Mobile              : {row['guest_mobile'] or '-'}")
    print(f"Transportation      : {row['transportation_type']}")
    print(f"Pickup              : {row['pickup_date']} {row['pickup_time']}")
    print(f"Pickup Location     : {row['pickup_location']}")
    print(f"Drop Location       : {row['drop_location']}")
    print(f"Vehicle             : {row['vehicle_id'] or '-'} | {row['vehicle_type'] or '-'}")
    print(f"Driver              : {row['driver_id'] or '-'} | {row['driver_name'] or '-'}")
    print(f"Fare                : ₹{float(row['fare'] or 0):.2f}")
    print(f"Status              : {row['status']}")
    print(f"Special Request     : {row['special_request'] or '-'}")
    print(f"Notes               : {row['notes'] or '-'}")
    print(f"Provider            : {row['provider_name'] or '-'}")
    print(f"Provider Reference  : {row['provider_reference'] or '-'}")
    print(f"Integration Status  : {row['integration_status']}")
    print(f"Created             : {row['created_at']}")
    print(f"Updated             : {row['updated_at']}")


def _choose_from_list(title, values):
    print(title)
    for index, value in enumerate(values, start=1):
        print(f"{index}. {value}")
    choice = validate_menu_choice("Select : ", [str(i) for i in range(1, len(values) + 1)])
    return values[int(choice) - 1]


def _create_request():
    print("=" * 78)
    print("                       CREATE TRANSPORTATION REQUEST")
    print("=" * 78)
    customer_id = input("Customer ID (optional) : ").strip().upper()
    guest_name = guest_mobile = guest_email = None
    if not customer_id:
        guest_name = validate_non_empty("Guest Name : ")
        guest_mobile = input("Guest Mobile (optional) : ").strip()
        guest_email = input("Guest Email (optional) : ").strip()

    transportation_type = _choose_from_list("Transportation Type:", TRANSPORTATION_TYPES)
    pickup_date = validate_non_empty("Pickup Date (DD-MM-YYYY) : ")
    pickup_time = validate_non_empty("Pickup Time (HH:MM) : ")
    pickup_location = validate_non_empty("Pickup Location : ")
    drop_location = validate_non_empty("Drop Location : ")

    vehicles = get_vehicles(include_inactive=False)
    vehicle_id = None
    vehicle_type = None
    if vehicles:
        print("Active Vehicles:")
        for vehicle in vehicles:
            print(f"{vehicle['vehicle_id']} - {vehicle['vehicle_number']} | {vehicle['vehicle_type']} | Capacity: {vehicle['capacity']}")
        vehicle_id = input("Vehicle ID (optional) : ").strip().upper() or None
    else:
        vehicle_type = input("Vehicle Type (optional) : ").strip() or None

    drivers = get_drivers(include_inactive=False)
    driver_id = None
    if drivers:
        print("Active Drivers:")
        for driver in drivers:
            print(f"{driver['driver_id']} - {driver['driver_name']} | {driver['driver_mobile'] or '-'}")
        driver_id = input("Driver ID (optional) : ").strip().upper() or None

    fare_text = input("Fare (INR, blank = 0) : ").strip()
    fare = float(fare_text) if fare_text else 0
    special_request = input("Special Transportation Request (optional) : ").strip()
    notes = input("Notes (optional) : ").strip()

    request_id = create_transportation_request(
        customer_id, guest_name, guest_mobile, guest_email,
        transportation_type, pickup_date, pickup_time,
        pickup_location, drop_location, vehicle_id, vehicle_type,
        driver_id, fare, special_request, notes,
    )
    print("\n✅ Transportation Request Created Successfully.")
    print(f"Request ID : {request_id}")
    print("Status     : Requested")
    print("Integration: Not Integrated")


def _view_requests():
    print("=" * 78)
    print("                       TRANSPORTATION REQUESTS")
    print("=" * 78)
    rows = get_transportation_requests()
    if not rows:
        print("No Transportation Requests Found.")
        return
    for row in rows:
        _print_request(row)


def _search_requests():
    term = input("Search Request ID / Customer / Guest / Type / Location / Status / Keyword : ").strip()
    rows = search_transportation_requests(term)
    print("=" * 78)
    print("                       TRANSPORTATION SEARCH")
    print("=" * 78)
    if not rows:
        print("No Transportation Requests Found.")
        return
    for row in rows:
        _print_request(row)


def _update_request():
    request_id = validate_non_empty("Transportation Request ID : ").strip().upper()
    status = _choose_from_list("Transportation Status:", TRANSPORTATION_STATUSES)

    vehicles = get_vehicles(include_inactive=False)
    vehicle_id = input("Vehicle ID (blank = keep current) : ").strip().upper() or None
    if vehicle_id and not vehicles:
        raise ValueError("No active vehicles available.")

    drivers = get_drivers(include_inactive=False)
    driver_id = input("Driver ID (blank = keep current) : ").strip().upper() or None
    if driver_id and not drivers:
        raise ValueError("No active drivers available.")

    fare_text = input("Fare (blank = keep current) : ").strip()
    fare = float(fare_text) if fare_text else None
    provider_name = input("Provider Name (blank = keep current) : ").strip() or None
    provider_reference = input("Provider Reference (blank = keep current) : ").strip() or None
    integration_status = _choose_from_list("Integration Status:", INTEGRATION_STATUSES)
    special_request = input("Special Request (blank = keep current) : ").strip() or None
    notes = input("Notes (blank = keep current) : ").strip() or None

    update_transportation_request(
        request_id, status, vehicle_id, driver_id, fare,
        provider_name, provider_reference, integration_status,
        special_request, notes,
    )
    print("\n✅ Transportation Request Updated Successfully.")


def _vehicle_management():
    while True:
        print("=" * 60)
        print("                    VEHICLE MANAGEMENT")
        print("=" * 60)
        print("1. Add Vehicle")
        print("2. View Vehicles")
        print("3. Update Vehicle Status")
        print("4. Back")
        choice = validate_menu_choice("Enter Your Choice : ", ["1", "2", "3", "4"])
        if choice == "1":
            vehicle_number = validate_non_empty("Vehicle Number : ")
            vehicle_type = validate_non_empty("Vehicle Type : ")
            capacity = input("Capacity (default 4) : ").strip() or "4"
            notes = input("Notes (optional) : ").strip()
            vehicle_id = add_vehicle(vehicle_number, vehicle_type, capacity, notes)
            print(f"\n✅ Vehicle Added Successfully. Vehicle ID : {vehicle_id}")
        elif choice == "2":
            rows = get_vehicles()
            if not rows:
                print("No Vehicles Found.")
            for row in rows:
                print(f"{row['vehicle_id']} | {row['vehicle_number']} | {row['vehicle_type']} | Capacity: {row['capacity']} | {row['status']}")
        elif choice == "3":
            vehicle_id = validate_non_empty("Vehicle ID : ").strip().upper()
            status = _choose_from_list("Vehicle Status:", VEHICLE_STATUSES)
            update_vehicle_status(vehicle_id, status)
            print("\n✅ Vehicle Status Updated Successfully.")
        else:
            return
        _pause()


def _driver_management():
    while True:
        print("=" * 60)
        print("                    DRIVER MANAGEMENT")
        print("=" * 60)
        print("1. Add Driver")
        print("2. View Drivers")
        print("3. Update Driver Status")
        print("4. Back")
        choice = validate_menu_choice("Enter Your Choice : ", ["1", "2", "3", "4"])
        if choice == "1":
            driver_name = validate_non_empty("Driver Name : ")
            mobile = input("Driver Mobile (optional) : ").strip()
            license_number = input("License Number (optional) : ").strip().upper()
            vehicle_type = input("Vehicle Type (optional) : ").strip()
            notes = input("Notes (optional) : ").strip()
            driver_id = add_driver(driver_name, mobile, license_number, vehicle_type, notes)
            print(f"\n✅ Driver Added Successfully. Driver ID : {driver_id}")
        elif choice == "2":
            rows = get_drivers()
            if not rows:
                print("No Drivers Found.")
            for row in rows:
                print(f"{row['driver_id']} | {row['driver_name']} | {row['driver_mobile'] or '-'} | {row['license_number'] or '-'} | {row['status']}")
        elif choice == "3":
            driver_id = validate_non_empty("Driver ID : ").strip().upper()
            status = _choose_from_list("Driver Status:", DRIVER_STATUSES)
            update_driver_status(driver_id, status)
            print("\n✅ Driver Status Updated Successfully.")
        else:
            return
        _pause()


def transportation_management():
    try:
        require_current_user_permission("Transportation", "View")
    except PermissionError as exc:
        # Transportation permissions are not part of the locked 4.8 module
        # list in older installations. Keep the module usable until a
        # dedicated permission master is added in a later enterprise phase.
        if "Transportation" not in str(exc):
            print(f"Login/Permission Required: {exc}")
            return
    
    while True:
        print("=" * 66)
        print("                 TRANSPORTATION MANAGEMENT")
        print("=" * 66)
        print("1. Create Transportation Request")
        print("2. View Transportation Requests")
        print("3. Search Transportation Request")
        print("4. Update Transportation Request")
        print("5. Vehicle Management")
        print("6. Driver Management")
        print("7. Transportation History")
        print("8. Back")
        choice = validate_menu_choice("Enter Your Choice : ", [str(i) for i in range(1, 9)])
        try:
            if choice == "1":
                _create_request()
            elif choice == "2":
                _view_requests()
            elif choice == "3":
                _search_requests()
            elif choice == "4":
                _update_request()
            elif choice == "5":
                _vehicle_management()
            elif choice == "6":
                _driver_management()
            elif choice == "7":
                _view_requests()
            elif choice == "8":
                return
        except (ValueError, sqlite3.Error) as exc:
            print(f"❌ {exc}")
        _pause()
