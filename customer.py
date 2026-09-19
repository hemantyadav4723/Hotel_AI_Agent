from utils.date_time import current_datetime_object

from utils.validators import (
    validate_menu_choice,
    validate_name,
    validate_mobile,
    validate_email,
    validate_address,
    validate_location,
    validate_country,
    validate_pincode
)

from utils.display import (
    print_header,
    print_footer,
    print_separator,
    print_success,
    print_error,
    press_enter
)

from database.customer_db import (
    save_customer,
    view_customers,
    search_customer,
    update_customer,
    delete_customer,
    customer_history,
    customer_booking_history,
    customer_restaurant_history,
    get_next_customer_id,
    customer_lifecycle,
    get_customer_by_mobile,
    ensure_guest_hotel_relationship,
    get_guest_data_integrity_report

)

from database.feedback_db import customer_feedback_history


def _optional_email():
    while True:
        value = input("Enter Email (optional) : ").strip()
        if not value:
            return None
        try:
            return validate_email_from_value(value)
        except ValueError as error:
            from utils.display import print_error
            print_error(str(error))


def validate_email_from_value(value):
    import re

    if not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
        value
    ):
        raise ValueError("Invalid Email Address.")

    return value.lower()


def _optional_location(message):
    value = input(message).strip()
    if not value:
        return None
    if not value.replace(" ", "").isalpha():
        raise ValueError("Only letters and spaces are allowed.")
    return value.title()


def _optional_country(message):
    value = input(message).strip()
    if not value:
        return None
    if not value.replace(" ", "").isalpha():
        raise ValueError("Country name should contain letters only.")
    return value.title()


def _optional_pincode(message):
    value = input(message).strip()
    if not value:
        return None
    if not value.isdigit() or len(value) != 6:
        raise ValueError("Invalid PIN Code. Enter 6 digits.")
    return value


def customer_management():
    while True:
        print_header("CUSTOMER MANAGEMENT")

        print("1. Add Customer")
        print("2. View Customers")
        print("3. Search / Filter Guest")
        print("4. Update Customer")
        print("5. Delete Customer")
        print("6. Customer History")
        print("7. Customer Booking History")
        print("8. Customer Restaurant History")
        print("9. Customer Feedback History")
        print("10. Customer Lifecycle")
        print("11. Multi-Hotel / Data Integrity Check")
        print("12. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
        )

        if choice == "1":
            try:
                customer_name = validate_name("Enter Customer Name : ")
                customer_mobile = validate_mobile("Enter Mobile Number : ")

                customer_email = _optional_email()
                customer_address = input("Enter Address (optional) : ").strip()
                if customer_address:
                    if len(customer_address) < 5:
                        raise ValueError("Address is too short.")
                else:
                    customer_address = None

                customer_city = _optional_location("Enter City (optional) : ")
                customer_state = _optional_location("Enter State (optional) : ")
                customer_country = _optional_country(
                    "Enter Country (optional, default India) : "
                ) or "India"
                customer_pincode = _optional_pincode(
                    "Enter PIN Code (optional) : "
                )

                preferences = input(
                    "Enter Preferences (optional) : "
                ).strip() or None

                special_requests = input(
                    "Enter Special Requests (optional) : "
                ).strip() or None

                guest_notes = input(
                    "Enter Guest Notes (optional) : "
                ).strip() or None

                existing_customer = get_customer_by_mobile(customer_mobile)
                if existing_customer is not None:
                    from database.hotel_context import get_current_hotel_id

                    hotel_id = get_current_hotel_id()
                    ensure_guest_hotel_relationship(
                        existing_customer["customer_id"],
                        hotel_id
                    )
                    print_error(
                        f"Existing Guest Found. Customer ID: {existing_customer['customer_id']}."
                    )
                    print("Guest Master was not duplicated; existing guest was linked to this hotel.")
                    press_enter()
                    continue

                created_time = current_datetime_object()
                customer_id = get_next_customer_id()

                save_customer(
                    customer_id,
                    customer_name,
                    customer_mobile,
                    customer_email,
                    customer_address,
                    created_time,
                    customer_city,
                    customer_state,
                    customer_country,
                    customer_pincode,
                    "Active",
                    1,
                    preferences,
                    special_requests,
                    guest_notes
                )

                from database.hotel_context import get_current_hotel_id
                ensure_guest_hotel_relationship(
                    customer_id,
                    get_current_hotel_id()
                )

                print_success("Customer Added Successfully.")
                print("Customer ID :", customer_id)

            except ValueError as error:
                print_error(str(error))

            press_enter()

        elif choice == "2":
            view_customers()
            press_enter()

        elif choice == "3":
            search_customer()
            press_enter()

        elif choice == "4":
            update_customer()
            press_enter()

        elif choice == "5":
            delete_customer()
            press_enter()

        elif choice == "6":
            customer_history()
            press_enter()

        elif choice == "7":
            customer_booking_history()
            press_enter()

        elif choice == "8":
            customer_restaurant_history()
            press_enter()

        elif choice == "9":
            customer_id = input("Enter Customer ID : ").strip().upper()
            customer_feedback_history(customer_id)
            press_enter()

        elif choice == "10":
            customer_lifecycle()
            press_enter()

        elif choice == "11":
            report = get_guest_data_integrity_report()
            print_header("GUEST DATA INTEGRITY")
            print("Hotel ID                              :", report["hotel_id"])
            print("Duplicate Mobile Groups              :", report["duplicate_mobile_groups"])
            print("Orphan Guest-Hotel Relationships     :", report["orphan_guest_hotel_relationships"])
            print("Bookings Missing Hotel Relationship  :", report["guest_bookings_missing_hotel_relationship"])
            print("Orders Missing Hotel Relationship   :", report["guest_orders_missing_hotel_relationship"])
            print("Feedback Missing Hotel Relationship :", report["guest_feedback_missing_hotel_relationship"])
            print("Integrity Status                     :", "PASS" if report["is_integrity_ok"] else "CHECK REQUIRED")
            press_enter()

        elif choice == "12":
            break
