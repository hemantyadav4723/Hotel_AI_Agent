from utils.display import print_error

# ==========================================
# VALIDATORS
# ==========================================

def validate_name(message):

    while True:

        value = input(message).strip()

        if value == "":
            print_error("This field cannot be empty.")
            continue

        if not value.replace(" ", "").isalpha():
            print_error("Name should contain only letters.")
            continue

        return value.title()


def validate_mobile(message):

    while True:

        mobile = input(message).strip()

        if mobile.isdigit() and len(mobile) == 10:
            return mobile

        print_error("Invalid Mobile Number. Enter 10 digits.")


def validate_email(message):

    while True:

        email = input(message).strip()

        if "@" in email and "." in email:
            return email

        print_error("Invalid Email Address.")


def validate_pincode(message):

    while True:

        pincode = input(message).strip()

        if pincode.isdigit() and len(pincode) == 6:
            return pincode

        print_error("Invalid PIN Code.")


def validate_positive_number(message):

    while True:

        try:

            number = int(input(message))

            if number > 0:
                return number

        except:

            pass

        print_error("Enter a valid positive number.")


def validate_rating(message):

    while True:

        try:

            rating = float(input(message))

            if 1 <= rating <= 5:
                return rating

        except:

            pass

        print_error("Rating must be between 1 and 5.")

def validate_year(message):

    while True:

        year = input(message).strip()

        if year.isdigit() and len(year) == 4:
            return year

        print_error("Enter a valid 4-digit year.")


def validate_available(message):

    while True:

        value = input(message).strip().lower()

        if value in ["available", "not available"]:
            return value.title()

        print_error("Enter Available or Not Available.")


def validate_currency(message):

    while True:

        currency = input(message).strip().upper()

        if currency in ["INR", "USD", "EUR", "AED"]:
            return currency

        print_error("Supported: INR, USD, EUR, AED")


def validate_time(message):

    while True:

        time = input(message).strip()

        if ":" in time:
            return time

        print_error("Example: 12:00 PM")

def validate_website(message):

    while True:

        website = input(message).strip().lower()

        if (
            website.startswith("www.")
            or website.startswith("http://")
            or website.startswith("https://")
        ) and "." in website:

            return website

        print_error("Invalid Website.")
        print("Example:")
        print("www.yadavhotel.com")
        print("https://www.yadavhotel.com")

def validate_hotel_type(message):

    hotel_types = [
        "Hotel",
        "Resort",
        "Motel",
        "Hostel",
        "Villa",
        "Apartment",
        "Guest House",
        "Homestay"
    ]

    while True:

        hotel_type = input(message).strip().title()

        if hotel_type in hotel_types:
            return hotel_type

        print("Invalid Hotel Type.")
        print("Available Types:")

        for item in hotel_types:
            print("-", item)

def validate_country(message):

    while True:

        country = input(message).strip().title()

        if country.replace(" ", "").isalpha():
            return country

        print_error("Country name should contain letters only.")

def validate_location(message):

    while True:

        value = input(message).strip().title()

        if value.replace(" ", "").isalpha():
            return value

        print_error("Only letters are allowed.")

def validate_address(message):

    while True:

        address = input(message).strip()

        if len(address) >= 5:
            return address

        print_error("Address is too short.")

def validate_description(message):

    while True:

        description = input(message).strip()

        if len(description) >= 10:
            return description

        print_error("Description must be at least 10 characters.")

def validate_yes_no(message):

    while True:

        value = input(message).strip().lower()

        if value in ["y", "yes"]:
            return "Yes"

        if value in ["n", "no"]:
            return "No"

        print_error("Enter Yes or No.")

def validate_price(message):

    while True:

        try:

            price = float(input(message))

            if price >= 0:
                return price

        except:
            pass

        print_error("Invalid Price.")

def validate_percentage(message):

    while True:

        try:

            percentage = float(input(message))

            if 0 <= percentage <= 100:
                return percentage

        except:
            pass

        print_error("Enter percentage between 0 and 100.")

def validate_quantity(message):

    while True:

        try:

            quantity = int(input(message))

            if quantity > 0:
                return quantity

        except:
            pass

        print_error("Invalid Quantity.")

def validate_password(message):

    while True:

        password = input(message)

        if len(password) >= 6:
            return password

        print_error("Password must contain at least 6 characters.")

def validate_username(message):

    while True:

        username = input(message).strip()

        if len(username) >= 4 and username.replace("_", "").isalnum():
            return username

        print_error("Invalid Username.")


# ==========================================================
# TABLE NUMBER
# ==========================================================

def validate_table_number(message):

    while True:

        table = input(message).strip()

        if table.isdigit() and int(table) > 0:
            return table

        print_error("Invalid Table Number.")

# ==========================================================
# MENU CHOICE
# ==========================================================

def validate_menu_choice(message, valid_choices):

    while True:

        choice = input(message).strip()

        if choice in valid_choices:
            return choice

        print_error("Invalid Choice.")