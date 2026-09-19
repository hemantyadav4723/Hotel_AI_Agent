from utils.error_logging import log_non_blocking_error
from utils.helpers import get_room_booking_customer_details

from utils.validators import (
    validate_positive_number,
    validate_price,
    validate_non_empty,
    validate_menu_choice,
    validate_yes_no
)

from utils.date_time import (
    current_datetime_object,
    generate_order_id
)

from utils.display import (
    print_header,
    print_separator,
    print_footer,
    print_success,
    print_warning,
    print_error,
    print_room_booking_summary,
    press_enter
)
from database.room_booking_db import (
    save_and_book_room,
    check_room_available,
    get_all_rooms,
    get_room_by_number,
    add_room,
    update_room,
    set_room_active_status,
    get_active_rooms,
    get_room_booking_by_id,
    confirm_reservation,
    cancel_reservation,
    mark_booking_no_show,
    check_in_guest,
    check_out_guest,
    transfer_room,
    modify_reservation,
    create_multi_room_reservation,
    get_reservation_rooms,
    delete_room_booking,
    get_available_rooms_for_dates,
    start_room_cleaning,
    complete_room_cleaning,
    mark_room_maintenance_required,
    start_room_maintenance,
    complete_room_maintenance
)
from database.room_payment_db import (
    PAYMENT_METHODS as ROOM_PAYMENT_METHODS,
    get_room_advance_rules,
    set_room_reservation_advance,
    get_required_reservation_advance,
    record_room_payment,
    add_room_extra_charge,
    get_room_extra_charges,
    get_room_payment_transactions,
    get_room_folio_summary
)

def view_room_configuration():

    print_header("ROOM CONFIGURATION")

    rooms = get_all_rooms()

    if not rooms:
        print_warning("No rooms found.")
        press_enter()
        return

    print(
        f"{'Room':<8}"
        f"{'Type':<12}"
        f"{'Floor':<8}"
        f"{'Capacity':<10}"
        f"{'Price':<12}"
        f"{'Status':<18}"
        f"{'Active':<8}"
    )

    print_separator()

    for room in rooms:

        active_status = (
            "Active"
            if room["is_active"]
            else "Inactive"
        )

        print(
            f"{room['room_number']:<8}"
            f"{room['room_type']:<12}"
            f"{str(room['floor']):<8}"
            f"{str(room['capacity']):<10}"
            f"₹{room['room_price']:<11}"
            f"{room['room_status']:<18}"
            f"{active_status:<8}"
        )

    print_footer()
    press_enter()


def add_room_configuration():

    print_header("ADD ROOM")

    room_number = validate_non_empty(
        "Enter Room Number : "
    )

    room_type = validate_non_empty(
        "Enter Room Type : "
    )

    floor = validate_positive_number(
        "Enter Floor Number : "
    )

    capacity = validate_positive_number(
        "Enter Room Capacity : "
    )

    room_price = validate_price(
        "Enter Room Price : "
    )

    amenities = input(
        "Enter Amenities (optional) : "
    ).strip()

    description = input(
        "Enter Description (optional) : "
    ).strip()

    try:

        add_room(
            room_number,
            room_type,
            floor,
            capacity,
            room_price,
            amenities,
            description
        )

        print_success(
            f"Room {room_number} added successfully."
        )

    except ValueError as e:

        print_error(str(e))

    except Exception as e:

        print_error(
            f"Unable to add room: {e}"
        )

    press_enter()


def update_room_configuration():

    print_header("UPDATE ROOM")

    room_number = validate_non_empty(
        "Enter Room Number : "
    )

    room = get_room_by_number(room_number)

    if room is None:

        print_error("Room not found.")
        press_enter()
        return

    print("\nCurrent Room Configuration")
    print_separator()

    print("Room Number :", room["room_number"])
    print("Room Type   :", room["room_type"])
    print("Floor       :", room["floor"])
    print("Capacity    :", room["capacity"])
    print("Price       :", f"₹{room['room_price']}")
    print("Amenities   :", room["amenities"] or "-")
    print("Description :", room["description"] or "-")

    print_separator()

    room_type = validate_non_empty(
        "Enter New Room Type : "
    )

    floor = validate_positive_number(
        "Enter New Floor Number : "
    )

    capacity = validate_positive_number(
        "Enter New Room Capacity : "
    )

    room_price = validate_price(
        "Enter New Room Price : "
    )

    amenities = input(
        "Enter New Amenities (optional) : "
    ).strip()

    description = input(
        "Enter New Description (optional) : "
    ).strip()

    try:

        update_room(
            room_number,
            room_type,
            floor,
            capacity,
            room_price,
            amenities,
            description
        )

        print_success(
            f"Room {room_number} updated successfully."
        )

    except ValueError as e:

        print_error(str(e))

    except Exception as e:

        print_error(
            f"Unable to update room: {e}"
        )

    press_enter()


def change_room_active_status():

    print_header("ROOM ACTIVE STATUS")

    room_number = validate_non_empty(
        "Enter Room Number : "
    )

    room = get_room_by_number(room_number)

    if room is None:

        print_error("Room not found.")
        press_enter()
        return

    current_status = (
        "Active"
        if room["is_active"]
        else "Inactive"
    )

    print(
        f"\nCurrent Status : {current_status}"
    )

    print_separator()

    choice = validate_menu_choice(
        "1. Activate\n"
        "2. Deactivate\n"
        "3. Back\n"
        "\nEnter Your Choice : ",
        ["1", "2", "3"]
    )

    if choice == "3":
        return

    try:

        if choice == "1":

            set_room_active_status(
                room_number,
                True
            )

            print_success(
                f"Room {room_number} activated successfully."
            )

        elif choice == "2":

            set_room_active_status(
                room_number,
                False
            )

            print_success(
                f"Room {room_number} deactivated successfully."
            )

    except ValueError as e:

        print_error(str(e))

    except Exception as e:

        print_error(
            f"Unable to change room status: {e}"
        )

    press_enter()

def show_booking_details(booking):

    print_separator()

    print(f"Booking ID       : {booking['booking_id']}")
    print(f"Customer         : {booking['customer_name']}")
    print(f"Mobile           : {booking['customer_mobile']}")
    print(f"Room Number      : {booking['room_number']}")
    print(f"Room Type        : {booking['room_type']}")
    print(f"Check-In Date    : {booking['check_in_date'] or '-'}")
    print(f"Expected Check-Out : {booking['expected_check_out'] or '-'}")
    print(f"Actual Check-In  : {booking['actual_check_in'] or '-'}")
    print(f"Actual Check-Out : {booking['actual_check_out'] or '-'}")
    print(f"Adults           : {booking['adults']}")
    print(f"Children         : {booking['children']}")
    print(f"Nights           : {booking['nights']}")
    print(f"Room Rate        : ₹{booking['room_rate']}")
    print(f"Reservation Advance : ₹{booking['advance_amount'] or 0}")
    print(f"Room Amount Paid    : ₹{booking['paid_amount'] if booking['paid_amount'] is not None else (booking['advance_amount'] or 0)}")
    print(f"Room Balance Due    : ₹{booking['balance_amount'] or 0}")
    print(f"Payment Method   : {booking['payment_method'] or '-'}")
    print(f"Payment Status   : {booking['payment_status']}")
    print(f"Booking Status   : {booking['booking_status']}")
    print(f"Booking Source   : {booking['booking_source']}")
    print(f"Notes            : {booking['notes'] or '-'}")
    try:
        reservation_rooms = get_reservation_rooms(booking['booking_id'])
        if len(reservation_rooms) > 1:
            print(f"Reserved Rooms   : {', '.join(r['room_number'] for r in reservation_rooms)}")
    except Exception as exc:
        log_non_blocking_error("Non-blocking optional operation failed", exc)

    print_separator()


def get_booking_for_lifecycle():

    booking_id = validate_non_empty(
        "Enter Booking ID : "
    ).upper()

    booking = get_room_booking_by_id(booking_id)

    if booking is None:

        print_error("Booking not found.")
        press_enter()
        return None

    show_booking_details(booking)

    return booking



def _prompt_booking_date():
    while True:
        value = input("Check-In Date (DD-MM-YYYY, blank = today) : ").strip()
        if not value:
            return current_datetime_object()
        try:
            from datetime import datetime
            return datetime.strptime(value, "%d-%m-%Y")
        except ValueError:
            print_error("Invalid date. Use DD-MM-YYYY format.")


def reservation_modify():
    print_header("MODIFY RESERVATION")
    booking = get_booking_for_lifecycle()
    if booking is None:
        return
    try:
        customer_name = input(f"Guest Name [{booking['customer_name']}] : ").strip() or booking['customer_name']
        customer_mobile = input(f"Mobile [{booking['customer_mobile']}] : ").strip() or booking['customer_mobile']
        room_number = input(f"Room Number(s) [{booking['room_number']}] (comma separated) : ").strip() or booking['room_number']
        date_text = input(f"Check-In Date [{booking['check_in_date']}] : ").strip() or booking['check_in_date']
        nights_text = input(f"Nights [{booking['nights']}] : ").strip() or str(booking['nights'])
        notes = input(f"Notes [{booking['notes'] or ''}] : ").strip()
        print("Payment changes are handled through Room Payment & Folio.")
        adults_text = input(f"Adults [{booking['adults'] or 1}] : ").strip() or str(booking['adults'] or 1)
        children_text = input(f"Children [{booking['children'] or 0}] : ").strip() or str(booking['children'] or 0)
        modify_reservation(booking['booking_id'], customer_name, customer_mobile, room_number, date_text, int(nights_text), notes, None, None, int(adults_text), int(children_text))
        print_success("Reservation modified successfully.")
    except ValueError as e:
        print_error(str(e))
    except Exception as e:
        print_error(f"Unable to modify reservation: {e}")
    press_enter()


def reservation_multiple_rooms():
    print_header("MULTI-ROOM RESERVATION")
    try:
        booking_date = _prompt_booking_date()
        nights = int(validate_positive_number("Enter Number of Nights : "))
        available = get_available_rooms_for_dates(booking_date, nights)
        if not available:
            print_error("No rooms are available for the selected dates.")
            press_enter(); return
        for room in available:
            print(f"Room No : {room['room_number']} | Type : {room['room_type']} | Price : ₹{room['room_price']}/Night")
        print_separator()
        room_numbers = [x.strip() for x in input("Room Numbers (comma separated) : ").split(',') if x.strip()]
        if not room_numbers:
            raise ValueError("At least one room is required.")
        customer_name, customer_mobile, customer_email, customer_address = get_room_booking_customer_details()
        booking_id = generate_order_id()
        minimum_advance = sum(get_required_reservation_advance(r.upper()) for r in room_numbers)
        total_preview = sum(float(r["room_price"]) for r in available if r["room_number"] in [x.upper() for x in room_numbers]) * nights * 1.05
        advance, payment_method = _collect_reservation_payment(
            room_numbers[0].upper(), round(total_preview, 2), round(minimum_advance, 2)
        )
        notes = input("Notes (optional) : ").strip()
        adults = int(input("Adults (minimum 1) : ").strip() or 1)
        children = int(input("Children (0 if none) : ").strip() or 0)
        booking_status = "Confirmed"
        create_multi_room_reservation(
            booking_id,
            booking_date,
            customer_name,
            customer_mobile,
            room_numbers,
            nights,
            'Direct',
            notes,
            advance,
            payment_method,
            booking_date,
            booking_status,
            adults,
            children,
            customer_email,
            customer_address
        )
        print_success(f"Multi-room reservation {booking_id} created successfully as {booking_status}.")
    except ValueError as e:
        print_error(str(e))
    except Exception as e:
        print_error(f"Unable to create reservation: {e}")
    press_enter()

def reservation_confirm():

    print_header("CONFIRM RESERVATION")

    booking = get_booking_for_lifecycle()

    if booking is None:
        return

    try:

        confirm_reservation(
            booking["booking_id"]
        )

        print_success(
            f"Reservation {booking['booking_id']} confirmed successfully."
        )

    except ValueError as e:

        print_error(str(e))

    except Exception as e:

        print_error(
            f"Unable to confirm reservation: {e}"
        )

    press_enter()


def reservation_cancel():

    print_header("CANCEL RESERVATION")

    booking = get_booking_for_lifecycle()

    if booking is None:
        return

    try:

        cancellation_reason = validate_non_empty(
            "Cancellation Reason : "
        ).strip()

        cancel_reservation(
            booking["booking_id"],
            cancellation_reason
        )

        print_success(
            f"Reservation {booking['booking_id']} cancelled successfully."
        )

    except ValueError as e:

        print_error(str(e))

    except Exception as e:

        print_error(
            f"Unable to cancel reservation: {e}"
        )

    press_enter()


def reservation_no_show():

    print_header("MARK NO-SHOW")

    booking = get_booking_for_lifecycle()

    if booking is None:
        return

    try:

        no_show_reason = validate_non_empty(
            "No-Show Reason : "
        ).strip()

        mark_booking_no_show(
            booking["booking_id"],
            no_show_reason
        )

        print_success(
            f"Reservation {booking['booking_id']} marked as No-Show."
        )

    except ValueError as e:

        print_error(str(e))

    except Exception as e:

        print_error(
            f"Unable to mark No-Show: {e}"
        )

    press_enter()


def reservation_check_in():

    print_header("GUEST CHECK-IN")

    booking = get_booking_for_lifecycle()

    if booking is None:
        return

    try:

        check_in_guest(
            booking["booking_id"]
        )

        print_success(
            f"Guest checked in successfully. "
            f"Room {booking['room_number']} is now Occupied."
        )

    except ValueError as e:

        print_error(str(e))

    except Exception as e:

        print_error(
            f"Unable to check in guest: {e}"
        )

    press_enter()


def reservation_check_out():

    print_header("GUEST CHECK-OUT")

    booking = get_booking_for_lifecycle()

    if booking is None:
        return

    try:

        check_out_guest(
            booking["booking_id"]
        )

        print_success(
            f"Guest checked out successfully. "
            f"Room {booking['room_number']} is now Dirty "
            f"and requires housekeeping."
        )

    except ValueError as e:

        print_error(str(e))

    except Exception as e:

        print_error(
            f"Unable to check out guest: {e}"
        )

    press_enter()

def reservation_room_transfer():

    print_header("ROOM TRANSFER")

    booking = get_booking_for_lifecycle()

    if booking is None:
        return

    try:

        if booking["booking_status"] != "Checked-In":
            raise ValueError(
                "Only Checked-In bookings can be transferred."
            )

        print("\nAvailable Rooms")
        print_separator()

        rooms = get_active_rooms()

        available_rooms = [
            room
            for room in rooms
            if room["room_status"] == "Available"
        ]

        if not available_rooms:
            print_error("No available rooms for transfer.")
            press_enter()
            return

        for room in available_rooms:
            print(
                f"Room No : {room['room_number']} | "
                f"Type : {room['room_type']} | "
                f"Price : ₹{room['room_price']}/Night"
            )

        print_separator()

        new_room_number = validate_non_empty(
            "Enter New Room Number : "
        ).strip()

        transfer_room(
            booking["booking_id"],
            new_room_number
        )

        print_success(
            f"Guest transferred successfully from "
            f"Room {booking['room_number']} to "
            f"Room {new_room_number}."
        )

    except ValueError as e:

        print_error(str(e))

    except Exception as e:

        print_error(
            f"Unable to transfer room: {e}"
        )

    press_enter()

def reservation_management():

    while True:

        print_header("RESERVATION MANAGEMENT")

        print("1. Confirm Reservation")
        print("2. Modify Reservation")
        print("3. Cancel Reservation")
        print("4. Mark No-Show")
        print("5. Guest Check-In")
        print("6. Guest Check-Out")
        print("7. Room Transfer")
        print("8. Multi-Room Reservation")
        print("9. Room Payment & Folio")
        print("10. Delete Room Booking")
        print("11. Back")

        print_separator()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
        )

        if choice == "1":
            reservation_confirm()
        elif choice == "2":
            reservation_modify()
        elif choice == "3":
            reservation_cancel()
        elif choice == "4":
            reservation_no_show()
        elif choice == "5":
            reservation_check_in()
        elif choice == "6":
            reservation_check_out()
        elif choice == "7":
            reservation_room_transfer()
        elif choice == "8":
            reservation_multiple_rooms()
        elif choice == "9":
            room_payment_management()
        elif choice == "10":
            delete_room_booking()
        elif choice == "11":
            return

def housekeeping_management():

    while True:

        print_header("HOUSEKEEPING MANAGEMENT")

        print("1. View Rooms")
        print("2. Start Cleaning")
        print("3. Complete Cleaning")
        print("4. Back")

        print_separator()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4"]
        )

        if choice == "1":

            rooms = get_all_rooms()

            print_separator()

            for room in rooms:
                print(
                    f"Room : {room['room_number']} | "
                    f"Room Status : {room['room_status']} | "
                    f"Housekeeping : "
                    f"{room['housekeeping_status']}"
                )

            print_separator()
            press_enter()

        elif choice == "2":

            room_number = validate_non_empty(
                "Enter Room Number : "
            ).strip()

            try:

                start_room_cleaning(
                    room_number
                )

                print_success(
                    f"Cleaning started for Room "
                    f"{room_number}."
                )

            except ValueError as e:

                print_error(str(e))

            except Exception as e:

                print_error(
                    f"Unable to start cleaning: {e}"
                )

            press_enter()

        elif choice == "3":

            room_number = validate_non_empty(
                "Enter Room Number : "
            ).strip()

            try:

                complete_room_cleaning(
                    room_number
                )

                print_success(
                    f"Cleaning completed for Room "
                    f"{room_number}. Room is now Available."
                )

            except ValueError as e:

                print_error(str(e))

            except Exception as e:

                print_error(
                    f"Unable to complete cleaning: {e}"
                )

            press_enter()

        elif choice == "4":

            return

def maintenance_management():

    while True:

        print_header("MAINTENANCE MANAGEMENT")

        print("1. View Maintenance Status")
        print("2. Mark Maintenance Required")
        print("3. Start Maintenance")
        print("4. Complete Maintenance")
        print("5. Back")

        print_separator()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5"]
        )

        if choice == "1":

            rooms = get_all_rooms()

            print_separator()

            for room in rooms:
                print(
                    f"Room : {room['room_number']} | "
                    f"Room Status : {room['room_status']} | "
                    f"Maintenance : "
                    f"{room['maintenance_status']}"
                )

            print_separator()
            press_enter()

        elif choice == "2":

            room_number = validate_non_empty(
                "Enter Room Number : "
            ).strip()

            try:

                mark_room_maintenance_required(
                    room_number
                )

                print_success(
                    f"Room {room_number} marked for maintenance."
                )

            except ValueError as e:

                print_error(str(e))

            except Exception as e:

                print_error(
                    f"Unable to mark maintenance: {e}"
                )

            press_enter()

        elif choice == "3":

            room_number = validate_non_empty(
                "Enter Room Number : "
            ).strip()

            try:

                start_room_maintenance(
                    room_number
                )

                print_success(
                    f"Maintenance started for Room "
                    f"{room_number}."
                )

            except ValueError as e:

                print_error(str(e))

            except Exception as e:

                print_error(
                    f"Unable to start maintenance: {e}"
                )

            press_enter()

        elif choice == "4":

            room_number = validate_non_empty(
                "Enter Room Number : "
            ).strip()

            try:

                complete_room_maintenance(
                    room_number
                )

                print_success(
                    f"Maintenance completed for Room "
                    f"{room_number}. Room is now Available."
                )

            except ValueError as e:

                print_error(str(e))

            except Exception as e:

                print_error(
                    f"Unable to complete maintenance: {e}"
                )

            press_enter()

        elif choice == "5":

            return


def _room_payment_method():
    print("1. Cash")
    print("2. UPI")
    print("3. Card")
    print("4. Other")
    choice = validate_menu_choice("Select Payment Method : ", ["1", "2", "3", "4"])
    return ROOM_PAYMENT_METHODS[int(choice) - 1]


def room_advance_settings():
    print_header("ROOM RESERVATION ADVANCE SETTINGS")
    rules = get_room_advance_rules(include_inactive=True)
    if not rules:
        print_warning("No room advance rules configured.")
    for rule in rules:
        status = "Active" if rule["is_active"] else "Inactive"
        print(f"Room {rule['room_number']} | Minimum Advance: ₹{float(rule['minimum_advance']):.2f} | {status}")
    print_separator()
    room_number = validate_non_empty("Enter Room Number to Configure (0 = Back) : ").upper()
    if room_number == "0":
        return
    room = get_room_by_number(room_number)
    if room is None:
        raise ValueError("Room not found.")
    current = get_required_reservation_advance(room_number)
    print(f"Current Minimum Advance : ₹{current:.2f}")
    amount = validate_positive_number("New Minimum Reservation Advance : ₹")
    set_room_reservation_advance(room_number, float(amount))
    print_success(f"Room {room_number} minimum reservation advance updated to ₹{float(amount):.2f}.")
    press_enter()


def _show_folio(booking_id):
    summary = get_room_folio_summary(booking_id)
    print_header("ROOM FOLIO SUMMARY")
    print(f"Room Charges Total : ₹{summary['room_total']:.2f}")
    print(f"Room Amount Paid   : ₹{summary['room_paid']:.2f}")
    print(f"Room Balance       : ₹{summary['room_balance']:.2f}")
    print(f"Extra Charges      : ₹{summary['extra_total']:.2f}")
    print(f"Extra Paid         : ₹{summary['extra_paid']:.2f}")
    print(f"Extra Balance      : ₹{summary['extra_balance']:.2f}")
    print_separator()
    print(f"TOTAL OUTSTANDING  : ₹{summary['total_due']:.2f}")


def room_payment_management():
    while True:
        print_header("ROOM PAYMENT & FOLIO")
        print("1. View Folio")
        print("2. Make Room Payment")
        print("3. Add Extra Charge")
        print("4. View Extra Charges")
        print("5. Pay Extra Charge")
        print("6. View Payment History")
        print("7. Back")
        print_separator()
        choice = validate_menu_choice("Enter Your Choice : ", ["1", "2", "3", "4", "5", "6", "7"])
        if choice == "7":
            return
        try:
            booking = get_booking_for_lifecycle()
            if booking is None:
                continue
            booking_id = booking["booking_id"]
            if choice == "1":
                _show_folio(booking_id)
            elif choice == "2":
                summary = get_room_folio_summary(booking_id)
                if summary["room_balance"] <= 0.01:
                    raise ValueError("Room charges are already fully paid.")
                print(f"Room Balance : ₹{summary['room_balance']:.2f}")
                amount = float(input("Enter Room Payment Amount : ₹").strip())
                if amount <= 0:
                    raise ValueError("Payment amount must be greater than ₹0.")
                if amount > summary["room_balance"]:
                    raise ValueError("Payment cannot exceed room balance.")
                method = _room_payment_method()
                record_room_payment(booking_id, amount, method, transaction_type="ROOM_PAYMENT")
                print_success("Room payment recorded successfully.")
            elif choice == "3":
                description = validate_non_empty("Extra Charge Description : ")
                amount = float(validate_positive_number("Extra Charge Amount : ₹"))
                charge_id = add_room_extra_charge(booking_id, description, amount)
                print_success(f"Extra charge {charge_id} added successfully.")
            elif choice == "4":
                charges = get_room_extra_charges(booking_id)
                if not charges:
                    print("No extra charges found.")
                for charge in charges:
                    print(f"{charge['charge_id']} | {charge['description']} | Total ₹{float(charge['amount']):.2f} | Paid ₹{float(charge['paid_amount']):.2f} | Balance ₹{float(charge['balance_amount']):.2f} | {charge['payment_status']}")
            elif choice == "5":
                charges = get_room_extra_charges(booking_id)
                unpaid = [c for c in charges if float(c['balance_amount'] or 0) > 0.01]
                if not unpaid:
                    raise ValueError("No unpaid extra charges found.")
                for charge in unpaid:
                    print(f"{charge['charge_id']} | {charge['description']} | Balance ₹{float(charge['balance_amount']):.2f}")
                charge_id = validate_non_empty("Enter Charge ID : ")
                target = next((c for c in unpaid if c['charge_id'] == charge_id), None)
                if target is None:
                    raise ValueError("Invalid unpaid charge ID.")
                amount = float(input(f"Enter Payment Amount (Max ₹{float(target['balance_amount']):.2f}) : ₹").strip())
                method = _room_payment_method()
                record_room_payment(booking_id, amount, method, transaction_type="EXTRA_CHARGE", extra_charge_id=charge_id)
                print_success("Extra charge payment recorded successfully.")
            elif choice == "6":
                transactions = get_room_payment_transactions(booking_id)
                if not transactions:
                    print("No room payment transactions found.")
                for tx in transactions:
                    print(f"{tx['transaction_id']} | {tx['transaction_type']} | ₹{float(tx['amount']):.2f} | {tx['payment_method'] or '-'} | {tx['created_at']}")
            press_enter()
        except (ValueError, TypeError) as e:
            print_error(str(e))
            press_enter()

def room_management():

    while True:

        print_header("ROOM MANAGEMENT")

        print("1. View Room Configuration")
        print("2. Add Room")
        print("3. Update Room")
        print("4. Activate / Deactivate Room")
        print("5. Housekeeping Management")
        print("6. Maintenance Management")
        print("7. Reservation Advance Settings")
        print("8. Back")

        print_separator()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6", "7", "8"]
        )

        if choice == "1":

            view_room_configuration()

        elif choice == "2":

            add_room_configuration()

        elif choice == "3":

            update_room_configuration()

        elif choice == "4":

            change_room_active_status()

        elif choice == "5":

            housekeeping_management()

        elif choice == "6":

            maintenance_management()

        elif choice == "7":

            try:
                room_advance_settings()
            except ValueError as e:
                print_error(str(e))
                press_enter()

        elif choice == "8":

            return

def _collect_reservation_payment(room_number, grand_total, minimum_advance):
    print_separator()
    print(f"Reservation Minimum Advance : ₹{minimum_advance:.2f}")
    print(f"Room Booking Grand Total    : ₹{grand_total:.2f}")
    while True:
        try:
            raw = input("Enter Reservation Payment (Minimum to Full) : ₹").strip()
            amount = float(raw)
            if amount < minimum_advance:
                print_error(f"Minimum reservation advance is ₹{minimum_advance:.2f}.")
                continue
            if amount > grand_total:
                print_error("Payment cannot exceed booking grand total.")
                continue
            method = _room_payment_method()
            return round(amount, 2), method
        except ValueError:
            print_error("Enter a valid payment amount.")


def room_booking():

    print_header("ROOM BOOKING")

    print("1. Book Room")
    print("2. Room Management")
    print("3. Reservation Management")
    print("4. Back") 

    print_separator()

    choice = validate_menu_choice(
        "Enter Your Choice : ",
        ["1", "2", "3", "4"]
    )

    if choice == "2":
        room_management()
        return

    if choice == "3":

        reservation_management()
        return

    if choice == "4":
        return

    print_header("ROOM BOOKING")
    print("Select reservation dates first.\n")
    check_in_date = _prompt_booking_date()
    days = int(validate_positive_number("Enter Number of Nights : "))
    rooms = get_available_rooms_for_dates(check_in_date, days)
    if not rooms:
        print_error("No rooms are available for the selected dates.")
        press_enter()
        return
    for room in rooms:
        print(f"Room No : {room['room_number']} | Type : {room['room_type']} | Price : ₹{room['room_price']}/Night | Status : ✅ Available")

    print_separator()

    room_choice = input(
         "Enter Room Number (0 = Back) : "
    ).strip()

    if room_choice == "0":

        return

    room = get_room_by_number(room_choice)

    if room is None:
        print_error("Invalid Room Number.")
        press_enter()
        return

    room_type = room["room_type"]
    room_price = room["room_price"]

    print_success("Room Selected Successfully.")

    print("Room Number :", room_choice)
    print("Room Type   :", room_type)
    print("Room Price  : ₹", room_price)

    print_separator()

    (
        customer_name,
        customer_mobile,
        customer_email,
        customer_address
    ) = get_room_booking_customer_details()

    booking_time = current_datetime_object()
    booking_id = generate_order_id()
    adults = int(input("Adults (minimum 1) : ").strip() or 1)
    children = int(input("Children (0 if none) : ").strip() or 0)
    if adults < 1 or children < 0:
        print_error("Adults must be at least 1 and children cannot be negative.")
        press_enter()
        return
    total = room_price * days
    gst = total * 0.05
    grand_total = total + gst

    print_room_booking_summary(
        booking_id,
        booking_time,
        customer_name,
        customer_mobile,
        room_choice,
        room_type,
        room_price,
        days,
        total,
        gst,
        grand_total
    )
        
    try:
        minimum_advance = get_required_reservation_advance(room_choice)
        advance_amount, payment_method = _collect_reservation_payment(
            room_choice, grand_total, minimum_advance
        )
        booking_status = "Confirmed"

        save_and_book_room(
            booking_id, booking_time, customer_name, customer_mobile,
            room_choice, room_type, room_price, days, total, gst, grand_total,
            check_in_date=check_in_date,
            advance_amount=advance_amount,
            payment_method=payment_method,
            booking_status=booking_status,
            adults=adults,
            children=children,
            customer_email=customer_email,
            customer_address=customer_address
        )

        print(f"\nReservation created successfully as {booking_status}.")

    except ValueError as e:
        print(f"\n❌ {e}")

    except Exception as e:
        print(f"\n❌ Booking failed: {e}")

    print_footer()

    press_enter()

    print_header("ROOM BOOKING")

    press_enter()
