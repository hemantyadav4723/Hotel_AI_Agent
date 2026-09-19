from database.hotel_information_db import (
    save_hotel_information,
    get_hotel_information
)

from utils.validators import (
    validate_name,
    validate_mobile,
    validate_email,
    validate_website,
    validate_rating,
    validate_positive_number,
    validate_available,
    validate_time,
    validate_currency,
    validate_hotel_type,
    validate_year,
    validate_location,
    validate_address,
    validate_description,
    validate_pincode,
    validate_menu_choice
)

from utils.display import (
    print_header,
    print_footer,
    print_success,
    print_error,
    press_enter
)

# ==========================================================
# LOAD HOTEL DATA
# ==========================================================

def load_hotel_data():

    global hotel_name
    global hotel_owner
    global hotel_type
    global hotel_established
    global hotel_description
    global hotel_address
    global hotel_city
    global hotel_state
    global hotel_country
    global hotel_pincode
    global hotel_mobile
    global hotel_email
    global hotel_website
    global hotel_rating
    global total_rooms
    global restaurant
    global parking
    global wifi
    global laundry
    global hotel_checkin_time
    global hotel_checkout_time
    global hotel_opening
    global hotel_closing
    global hotel_currency
    global hotel_support_email
    global hotel_support_mobile

    hotel = get_hotel_information()

    if not hotel:
        return

    hotel_name = hotel["hotel_name"]
    hotel_owner = hotel["hotel_owner"]
    hotel_type = hotel["hotel_type"]
    hotel_established = hotel["hotel_established"]
    hotel_description = hotel["hotel_description"]
    hotel_address = hotel["hotel_address"]
    hotel_city = hotel["hotel_city"]
    hotel_state = hotel["hotel_state"]
    hotel_country = hotel["hotel_country"]
    hotel_pincode = hotel["hotel_pincode"]
    hotel_mobile = hotel["hotel_mobile"]
    hotel_email = hotel["hotel_email"]
    hotel_website = hotel["hotel_website"]
    hotel_rating = hotel["hotel_rating"]
    total_rooms = hotel["total_rooms"]
    restaurant = hotel["restaurant"]
    parking = hotel["parking"]
    wifi = hotel["wifi"]
    laundry = hotel["laundry"]
    hotel_checkin_time = hotel["hotel_checkin_time"]
    hotel_checkout_time = hotel["hotel_checkout_time"]
    hotel_opening = hotel["hotel_opening"]
    hotel_closing = hotel["hotel_closing"]
    hotel_currency = hotel["hotel_currency"]
    hotel_support_email = hotel["hotel_support_email"]
    hotel_support_mobile = hotel["hotel_support_mobile"]

# ==========================================================
# SAVE HOTEL DATA
# ==========================================================

def save_hotel_data():

    save_hotel_information(
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
    )


# ==========================================================
# HOTEL INFORMATION
# ==========================================================

def hotel_information():

    load_hotel_data()

    while True:

        
        print_header("HOTEL INFORMATION")
        
        print("1. Hotel Profile")
        print("2. Contact Information")
        print("3. Hotel Facilities")
        print("4. Hotel Timings")
        print("5. Update Hotel Information")
        print("6. Back")

        print_footer()

        choice = validate_menu_choice(
           "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6"]
        )

        if choice == "1":

            hotel_profile()

        elif choice == "2":

            contact_information()

        elif choice == "3":

            hotel_facilities()

        elif choice == "4":

            hotel_timings()

        elif choice == "5":

            update_hotel_information()

        elif choice == "6":

            break

        else:

            print_error("Invalid Choice")

        press_enter()


# ==========================================================
# HOTEL PROFILE
# ==========================================================

def hotel_profile():

    print_header("HOTEL PROFILE")

    print("Hotel Name    :", hotel_name)
    print("Owner         :", hotel_owner)
    print("Hotel Type    :", hotel_type)
    print("Established   :", hotel_established)
    print("Rating        :", hotel_rating)
    print("Description   :", hotel_description)

    print_footer()


# ==========================================================
# CONTACT INFORMATION
# ==========================================================

def contact_information():

    print_header("CONTACT INFORMATION")

    print("Address       :", hotel_address)
    print("City          :", hotel_city)
    print("State         :", hotel_state)
    print("Country       :", hotel_country)
    print("PIN Code      :", hotel_pincode)
    print("Mobile        :", hotel_mobile)
    print("Email         :", hotel_email)
    print("Website       :", hotel_website)

    print_footer()

# ==========================================================
# HOTEL FACILITIES
# ==========================================================

def hotel_facilities():

    print_header("HOTEL FACILITIES")

    print("Restaurant   :", restaurant)
    print("Parking      :", parking)
    print("WiFi         :", wifi)
    print("Laundry      :", laundry)
    print("Total Rooms  :", total_rooms)

    print_footer()


# ==========================================================
# HOTEL TIMINGS
# ==========================================================

def hotel_timings():

    print_header("HOTEL TIMINGS")

    print("Check-In Time   :", hotel_checkin_time)
    print("Check-Out Time  :", hotel_checkout_time)
    print("Opening Time    :", hotel_opening)
    print("Closing Time    :", hotel_closing)

    print_footer()


# ==========================================================
# UPDATE HOTEL INFORMATION
# ==========================================================

def update_hotel_information():

    global hotel_name
    global hotel_owner
    global hotel_type
    global hotel_established
    global hotel_description
    global hotel_address
    global hotel_city
    global hotel_state
    global hotel_country
    global hotel_pincode
    global hotel_mobile
    global hotel_email
    global hotel_website
    global hotel_rating
    global total_rooms
    global restaurant
    global parking
    global wifi
    global laundry
    global hotel_checkin_time
    global hotel_checkout_time
    global hotel_opening
    global hotel_closing
    global hotel_currency
    global hotel_support_email
    global hotel_support_mobile

    while True:

        print_header("UPDATE HOTEL INFORMATION")

        print("1. Hotel Name")
        print("2. Owner")
        print("3. Hotel Type")
        print("4. Established")
        print("5. Description")
        print("6. Address")
        print("7. City")
        print("8. State")
        print("9. Country")
        print("10. PIN Code")
        print("11. Mobile")
        print("12. Email")
        print("13. Website")
        print("14. Rating")
        print("15. Total Rooms")
        print("16. Restaurant")
        print("17. Parking")
        print("18. WiFi")
        print("19. Laundry")
        print("20. Check-In Time")
        print("21. Check-Out Time")
        print("22. Opening Time")
        print("23. Closing Time")
        print("24. Currency")
        print("25. Support Email")
        print("26. Support Mobile")
        print("27. Save Changes")
        print("28. Back")

        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            [
                "1", "2", "3", "4", "5", "6", "7",
                "8", "9", "10", "11", "12", "13", "14",
                "15", "16", "17", "18", "19", "20", "21",
                "22", "23", "24", "25", "26", "27", "28"
            ]
        )

        if choice == "1":
            hotel_name = validate_name("New Hotel Name : ")

        elif choice == "2":
            hotel_owner = validate_name("New Owner : ")

        elif choice == "3":
            hotel_type = validate_hotel_type("New Hotel Type : ")

        elif choice == "4":
            hotel_established = validate_year("New Established Year : ")

        elif choice == "5":
            hotel_description = validate_description("New Description : ")

        elif choice == "6":
            hotel_address = validate_address("New Address : ")

        elif choice == "7":
            hotel_city = validate_location("New City : ")

        elif choice == "8":
            hotel_state = validate_location("New State : ")

        elif choice == "9":
            hotel_country = validate_location("New Country : ")

        elif choice == "10":
            hotel_pincode = validate_pincode("New PIN Code : ")

        elif choice == "11":   
            hotel_mobile = validate_mobile("New Mobile : ")

        elif choice == "12":
            hotel_email = validate_email("New Email : ")

        elif choice == "13":
            hotel_website = validate_website("New Website : ")

        elif choice == "14":
            hotel_rating = validate_rating("New Rating (1-5) : ")

        elif choice == "15":
            total_rooms = validate_positive_number("Total Rooms : ")

        elif choice == "16":
            restaurant = validate_available("Restaurant (Available/Not Available): ")

        elif choice == "17":
            parking = validate_available("Parking (Available/Not Available): ")

        elif choice == "18":
            wifi = validate_available("WiFi (Available/Not Available): ")

        elif choice == "19":
            laundry = validate_available("Laundry (Available/Not Available): ")

        elif choice == "20":
            hotel_checkin_time = validate_time("Check-In Time : ")

        elif choice == "21":
            hotel_checkout_time = validate_time("Check-Out Time : ")

        elif choice == "22":
            hotel_opening = validate_time("Opening Time : ")

        elif choice == "23":
            hotel_closing = validate_time("Closing Time : ")

        elif choice == "24":
            hotel_currency = validate_currency("Currency : ")

        elif choice == "25":
            hotel_support_email = validate_email("Support Email : ")

        elif choice == "26":
            hotel_support_mobile = validate_mobile("Support Mobile : ")

        elif choice == "27":

            save_hotel_data()

            print_success("Hotel Information Saved Successfully.")

            press_enter()


        elif choice == "28":
            confirm = input("Save before exit? (Y/N):").upper()

            if confirm == "Y":
                save_hotel_data()

            break

        else:

            print_error("Invalid Choice")

            press_enter()

            continue

        print_success("Information Updated Successfully.")
        press_enter()