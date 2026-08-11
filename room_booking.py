from datetime import datetime
from utils.helpers import get_room_booking_customer_details
from utils.validators import *
from utils.date_time import current_datetime_object, generate_order_id
from utils.display import *
from database.db_manager import (
    save_room_booking,
    check_room_available,
    book_room,
    get_all_rooms,
    get_room_by_number
)

def room_booking():

    print_header("ROOM BOOKING")  
    print("Available Rooms\n")

    rooms = get_all_rooms()

    for room in rooms:

        if room["room_status"] == "Available":
 
            status = "✅ Available"

        else:

            status = "❌ Booked"

        print(
            f"Room No : {room['room_number']} | "
            f"Type : {room['room_type']} | "
            f"Price : ₹{room['room_price']}/Night | "
            f"Status : {status}"
        )

    print_separator()

    rooms = get_all_rooms()

    room_numbers = []

    for room in rooms:

            room_numbers.append(room["room_number"])

    room_choice = input(
         "Enter Room Number (0 = Back) : "
    ).strip()

    if room_choice == "0":

        return

    room = get_room_by_number(room_choice)

    room_type = room["room_type"]
    room_price = room["room_price"]

    if not check_room_available(room_choice):

        print_error("Room Already Booked.")
        press_enter()
        return

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

    days = validate_positive_number("Enter Number of Days : ")
        
    booking_time = current_datetime_object()
    booking_id = generate_order_id()
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
        
    print_success("Booking Successfully!")

    save_room_booking(
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

    book_room(room_choice)

    print_footer()

    press_enter()

    print_header("ROOM BOOKING")

    print("Feature Under Development")

    press_enter()
