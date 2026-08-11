from database.db_manager import (
    get_all_tables,
    get_table_by_number,
    check_table_available,
    book_table,
    save_table_booking
)

from utils.helpers import get_table_booking_customer_details
from utils.validators import *
from utils.display import *
from utils.date_time import (
    current_datetime_object,
    generate_order_id
)

def table_booking():

    print("=" * 50)
    print("          TABLE BOOKING")
    print("=" * 50)

    print("\nAvailable Tables\n")

    tables = get_all_tables()

    for table in tables:

        if table["table_status"] == "Available":

            status = "✅ Available"

        else:

            status = "❌ Booked"

        print(
            f"Table : {table['table_number']} | "
            f"Capacity : {table['table_capacity']} Persons | "
            f"Status : {status}"
        )

    print("-" * 50)

    table_numbers = []

    for table in tables:

        table_numbers.append(table["table_number"])

    table_number = input(
        "Enter Table Number (0 = Back) : "
    ).strip().upper()

    if table_number == "0":

        return

    table = get_table_by_number(table_number)

    if not check_table_available(table_number):

        print_error("Table Already Booked.")

        press_enter()

        return

    customer_name = input("Enter Customer Name : ")

    while True:

        customer_mobile = input("Enter Mobile Number : ")

        if customer_mobile.isdigit() and len(customer_mobile) == 10:

            break

        print("Invalid Mobile Number.")

    while True:

        try:

            persons = int(input("Enter Number Of Persons : "))

            if persons <= 0:

                print_error("Persons Must Be Greater Than 0.")

                continue

            if persons > table["table_capacity"]:

                print_error(
                    f"Maximum Capacity Is {table['table_capacity']} Persons."
                )

                continue

            break

        except ValueError:

            print_error("Enter Numbers Only.")

    booking_time = current_datetime_object()

    booking_id = generate_order_id()

    save_table_booking(
        booking_id,
        booking_time,
        customer_name,
        customer_mobile,
        table_number,
        persons
    )

    book_table(table_number)

    print("\n" + "=" * 50)
    print("Table Booking Successful!")
    print("=" * 50)

    print(f"Booking ID : {booking_id}")
    print(f"Customer   : {customer_name}")
    print(f"Table No   : {table_number}")
    print(f"Persons    : {persons}")
    print("=" * 50)

    input("\nPress Enter To Return...")