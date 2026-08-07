from data import table_menu
from billing import is_table_booked, save_table_booking
from datetime import datetime

def table_booking():

    print("=" * 50)
    print("          TABLE BOOKING")
    print("=" * 50)

    print("\nAvailable Tables\n")

    for table_no, details in table_menu.items():

        if is_table_booked(table_no):

            status = "❌ Booked"

        else:

            status = "✅ Available"

        print(
            f"Table : {table_no} | "
            f"Capacity : {details['capacity']} Persons | "
            f"Status : {status}"
        )

    print("-" * 50)

    table_number = input("Enter Table Number : ").upper()

    if table_number not in table_menu:

        print("Invalid Table Number")
        input("\nPress Enter To Return...")
        return

    if is_table_booked(table_number):

        print("Table Already Booked.")
        input("\nPress Enter To Return...")
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

            if persons > 0:

                break

            print("Persons Must Be Greater Than 0.")

        except ValueError:

            print("Enter Numbers Only.")

    booking_time = datetime.now()

    booking_id = booking_time.strftime("%Y%m%d%H%M%S")

    save_table_booking(
        booking_id,
        booking_time,
        customer_name,
        customer_mobile,
        table_number,
        persons
    )

    print("\n" + "=" * 50)
    print("Table Booking Successful!")
    print("=" * 50)

    print(f"Booking ID : {booking_id}")
    print(f"Customer   : {customer_name}")
    print(f"Table No   : {table_number}")
    print(f"Persons    : {persons}")
    print("=" * 50)

    input("\nPress Enter To Return...")