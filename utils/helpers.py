# ==========================================================
# CONVERT TO TITLE CASE
# ==========================================================

def to_title(text):
    """
    Convert text to Title Case.
    """
    return text.strip().title()


# ==========================================================
# CONVERT TO UPPER CASE
# ==========================================================

def to_upper(text):
    """
    Convert text to Upper Case.
    """
    return text.strip().upper()


# ==========================================================
# CONVERT TO LOWER CASE
# ==========================================================

def to_lower(text):
    """
    Convert text to Lower Case.
    """
    return text.strip().lower()


# ==========================================================
# YES / NO FORMAT
# ==========================================================

def yes_no(value):
    """
    Convert user input into Yes or No.
    """
    value = value.strip().lower()

    if value in ("yes", "y"):
        return "Yes"

    if value in ("no", "n"):
        return "No"

    return value

# ==========================================================
# CUSTOMER DETAILS
# ==========================================================

from utils.validators import (
    validate_name,
    validate_mobile,
    validate_email,
    validate_address,
    validate_table_number
)

def get_customer_details(include_table=False):

    customer_name = validate_name("Enter Customer Name : ")
    customer_mobile = validate_mobile("Enter Mobile Number : ")
    customer_email = validate_email("Enter Email : ")
    customer_address = validate_address("Enter Address : ")

    if include_table:

        table_number = validate_table_number("Enter Table Number : ")

        return (
            customer_name,
            customer_mobile,
            customer_email,
            customer_address,
            table_number
        )

    return (
        customer_name,
        customer_mobile,
        customer_email,
        customer_address
    )

from utils.validators import (
    validate_name,
    validate_mobile,
    validate_email,
    validate_address,
    validate_table_number
)

# ==========================================================
# CUSTOMER DETAILS
# ==========================================================

def get_customer_details():

    customer_name = validate_name("Enter Customer Name : ")
    customer_mobile = validate_mobile("Enter Mobile Number : ")
    customer_email = validate_email("Enter Email : ")
    customer_address = validate_address("Enter Address : ")

    return (
        customer_name,
        customer_mobile,
        customer_email,
        customer_address
    )

# ==========================================================
# RESTAURANT CUSTOMER DETAILS
# ==========================================================

def get_restaurant_customer_details():

    customer_name = validate_name("Enter Customer Name : ")
    customer_mobile = validate_mobile("Enter Mobile Number : ")
    table_number = validate_table_number("Enter Table Number : ")

    return (
        customer_name,
        customer_mobile,
        table_number
    )

# ==========================================================
# ROOM BOOKING CUSTOMER DETAILS
# ==========================================================

def get_room_booking_customer_details():

    customer_name = validate_name("Enter Customer Name : ")
    customer_mobile = validate_mobile("Enter Mobile Number : ")
    customer_email = validate_email("Enter Email : ")
    customer_address = validate_address("Enter Address : ")

    return (
        customer_name,
        customer_mobile,
        customer_email,
        customer_address
    )