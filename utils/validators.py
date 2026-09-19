from utils.display import print_error

_VALIDATOR_DEFAULT_MISSING = object()

# ==========================================
# VALIDATORS
# ==========================================

def validate_name(message, default=_VALIDATOR_DEFAULT_MISSING):

    while True:

        value = input(message).strip()

        if value == "":
            if default is not _VALIDATOR_DEFAULT_MISSING:
                return default
            print_error("This field cannot be empty.")
            continue

        if not value.replace(" ", "").isalpha():
            print_error("Name should contain only letters.")
            continue

        if len(value.replace(" ", "")) < 3:

            print_error("Name must contain at least 3 letters.")

            continue

        return value.title()


def validate_mobile(message, default=_VALIDATOR_DEFAULT_MISSING):

    while True:

        mobile = input(message).strip()

        if mobile == "" and default is not _VALIDATOR_DEFAULT_MISSING:
            return default

        if mobile.isdigit() and len(mobile) == 10:
            return mobile

        print_error("Invalid Mobile Number. Enter 10 digits.")


def validate_optional_mobile(message, default=_VALIDATOR_DEFAULT_MISSING):
    """Return None for blank input, otherwise a valid 10-digit mobile number."""
    while True:
        mobile = input(message).strip()
        if mobile == "":
            if default is not _VALIDATOR_DEFAULT_MISSING:
                return default
            return None
        if mobile.isdigit() and len(mobile) == 10:
            return mobile
        print_error("Invalid Mobile Number. Enter 10 digits or leave blank.")


def validate_email(message, default=_VALIDATOR_DEFAULT_MISSING):

    import re

    pattern = r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"

    while True:

        email = input(message).strip()

        if email == "" and default is not _VALIDATOR_DEFAULT_MISSING:
            return default

        if re.fullmatch(pattern, email):
            return email.lower()

        print_error("Invalid Email Address.")


def validate_pincode(message, default=_VALIDATOR_DEFAULT_MISSING):

    while True:

        pincode = input(message).strip()

        if pincode == "" and default is not _VALIDATOR_DEFAULT_MISSING:
            return default

        if pincode.isdigit() and len(pincode) == 6:
            return pincode

        print_error("Invalid PIN Code.")


def validate_positive_number(message):

    while True:

        try:

            number = int(input(message))

            if number > 0:
                return number

        except (ValueError, TypeError):

            pass

        print_error("Enter a valid positive number.")


def validate_rating(message):

    while True:

        try:

            rating = float(input(message))

            if 1 <= rating <= 5:
                return rating

        except (ValueError, TypeError):

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

def validate_location(message, default=_VALIDATOR_DEFAULT_MISSING):

    while True:

        value = input(message).strip().title()

        if value == "" and default is not _VALIDATOR_DEFAULT_MISSING:
            return default

        if value.replace(" ", "").isalpha():
            return value

        print_error("Only letters are allowed.")

def validate_address(message, default=_VALIDATOR_DEFAULT_MISSING):

    while True:

        address = input(message).strip()

        if address == "" and default is not _VALIDATOR_DEFAULT_MISSING:
            return default

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

        except (ValueError, TypeError):
            pass

        print_error("Invalid Price.")

def validate_optional_price(message):
    """Return None for blank input, otherwise a non-negative price."""
    while True:
        raw_value = input(message).strip()

        if raw_value == "":
            return None

        try:
            price = float(raw_value)
            if price >= 0:
                return price
        except (ValueError, TypeError):
            pass

        print_error("Invalid Price. Enter a non-negative amount or leave blank.")


def validate_optional_date(message):
    """Return None for blank input, otherwise a DD-MM-YYYY date."""
    from datetime import datetime

    while True:
        value = input(message).strip()
        if value == "":
            return None
        try:
            parsed = datetime.strptime(value, "%d-%m-%Y")
            return parsed.strftime("%d-%m-%Y")
        except ValueError:
            print_error("Invalid Date. Use DD-MM-YYYY format.")

def validate_gstin(message):
    """Validate an Indian GSTIN (15 alphanumeric characters)."""
    import re

    pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"

    while True:
        gstin = input(message).strip().upper()
        if re.fullmatch(pattern, gstin):
            return gstin
        print_error("Invalid GSTIN. Enter a valid 15-character GSTIN.")


def validate_optional_gstin(message, default=_VALIDATOR_DEFAULT_MISSING):
    """Return None for blank input, otherwise a valid GSTIN."""
    while True:
        gstin = input(message).strip().upper()
        if gstin == "":
            if default is not _VALIDATOR_DEFAULT_MISSING:
                return default
            return None
        import re
        pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
        if re.fullmatch(pattern, gstin):
            return gstin
        print_error("Invalid GSTIN. Enter a valid 15-character GSTIN or leave blank.")


def validate_tax_type(message, default=_VALIDATOR_DEFAULT_MISSING):
    tax_types = ["GST", "VAT", "TDS", "Other", "None"]
    while True:
        value = input(message).strip().upper()
        if value == "" and default is not _VALIDATOR_DEFAULT_MISSING:
            return default
        if value in tax_types:
            return value
        print_error("Tax Type must be GST, VAT, TDS, Other, or None.")


def validate_tax_status(message, default=_VALIDATOR_DEFAULT_MISSING):
    statuses = ["Registered", "Unregistered", "Composition", "Not Applicable", "Not Registered"]
    while True:
        value = input(message).strip().title()
        if value == "" and default is not _VALIDATOR_DEFAULT_MISSING:
            return default
        if value in statuses:
            return value
        print_error("Invalid Tax Status. Choose Registered, Unregistered, Composition, Not Applicable, or Not Registered.")


def validate_percentage(message):

    while True:

        try:

            percentage = float(input(message))

            if 0 <= percentage <= 100:
                return percentage

        except (ValueError, TypeError):
            pass

        print_error("Enter percentage between 0 and 100.")

def validate_quantity(message):

    while True:

        try:

            quantity = int(input(message))

            if quantity > 0:
                return quantity

        except (ValueError, TypeError):
            pass

        print_error("Invalid Quantity.")


def validate_non_negative_quantity(message):

    while True:

        try:
            quantity = int(input(message))

            if quantity >= 0:
                return quantity

        except (ValueError, TypeError):
            pass

        print_error("Quantity cannot be negative.")

# ==========================================================
# TABLE NUMBER
# ==========================================================

def validate_table_number(message):

    while True:

        table = input(message).strip().upper()

        if (
            table.startswith("T")
            and table[1:].isdigit()
            and int(table[1:]) > 0
        ):

            return table

        print_error(
            "Invalid Table Number. Example: T1, T2, T3"
        )

# ==========================================================
# MENU CHOICE
# ==========================================================

def validate_menu_choice(message, valid_choices):

    while True:

        choice = input(message).strip()

        if choice in valid_choices:
            return choice

        print_error("Invalid Choice.")

def validate_non_empty(message):

    while True:
        value = input(message).strip()

        if value:
            return value

        print_error("This field cannot be empty.")


def validate_username(message):

    while True:
        username = input(message).strip()

        if 3 <= len(username) <= 50 and username.replace("_", "").replace(".", "").isalnum():
            return username

        print_error("Username must be 3-50 characters and use letters, numbers, '_' or '.'.")


def validate_password(message):

    while True:
        password = input(message)

        if len(password) >= 8 and not password.isspace():
            return password

        print_error("Password must contain at least 8 characters.")


def validate_role(message="Role : "):
    from database.role_db import get_active_roles

    while True:
        roles = get_active_roles()
        if not roles:
            print_error("No active roles available. Create a role first.")
            return None

        print("\nAvailable Roles:")
        for index, role in enumerate(roles, start=1):
            print(f"{index}. {role['role_name']}")

        choice = input("Select Role No: ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(roles)):
            print_error("Invalid role selection.")
            continue
        return roles[int(choice) - 1]["role_name"]


def validate_permission(message="Permission : "):
    from database.permission_db import get_active_permissions

    while True:
        permissions = get_active_permissions()
        if not permissions:
            print_error("No active permissions available.")
            return None

        print("\nAvailable Permissions:")
        for index, permission in enumerate(permissions, start=1):
            print(f"{index}. {permission['permission_name']}")

        choice = input("Select Permission No: ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= len(permissions)):
            print_error("Invalid permission selection.")
            continue
        return permissions[int(choice) - 1]
