from data import room_menu
from billing import is_room_booked
from datetime import datetime
from utils.helpers import get_room_booking_customer_details
from utils.validators import *
from utils.date_time import current_datetime_object, generate_order_id
from utils.display import *
from database.db_manager import save_room_booking

def room_booking():

    print_header("ROOM BOOKING")  
    print("Available Rooms\n")

    for room_no, details in room_menu.items():

        if is_room_booked(room_no):

            status = "❌ Booked"

        else:

            status = "✅ Available"

        print(
            f"Room No : {room_no} | "
            f"Type : {details['type']} | "
            f"Price : ₹{details['price']}/Night | "
            f"Status : {status}"
        )

    print_separator()

    room_choice = validate_menu_choice(
        "Enter Room Number : ",
        room_menu.keys()
        )

    room = room_menu[room_choice]

    room_type = room["type"]
    room_price = room["price"]
    room_status = room["status"]

    if is_room_booked(room_choice):

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
    print_footer()

    press_enter()

    print_header("ROOM BOOKING")

    print("Feature Under Development")

    press_enter()
