from restaurant import restaurant_menu
from room_booking import room_booking
from table_booking import table_booking
from customer import customer_management
from staff import staff_management
from inventory import inventory_management
from reports import reports_management
from expense import expense_management
from feedback import feedback_management
from login import login_management
from settings import settings_management
from hotel_information import hotel_information
from notifications import notifications_management
from transportation import transportation_management
from maps_navigation import maps_navigation
from media import media_management
from audit_activity import audit_activity_management
from ai_tools import ai_tools_management
from database.database import initialize_database
from database.database_admin import database_management
from database.table_booking_db import (
    delete_table_booking,
    view_table_bookings,
    search_table_booking
)
from database.order_db import (
    view_orders,
    search_order,
    delete_order
)
from database.room_booking_db import (
    view_room_bookings,
    search_room_booking,
    delete_room_booking
)
from utils.validators import validate_menu_choice

initialize_database()

while True:

    print("=" * 60)
    print("            YADAV HOTEL AI AGENT PRO")
    print("=" * 60)

    print("Version : 1.0.0")
    print("Status  : Development")

    print("-" * 60)
    print("                 MAIN MENU")
    print("-" * 60)

    print("1. Hotel Information")
    print("2. Restaurant")
    print("3. Room Booking")
    print("4. Table Booking")
    print("5. My Booking")
    print("6. Customer Management")
    print("7. Staff Management")
    print("8. AI Receptionist")
    print("9. Contact Us")
    print("10. View Order History")
    print("11. Search Order")
    print("12. Delete Order")
    print("13. Inventory Management")
    print("14. Reports & Analytics")
    print("15. Expense Management")
    print("16. Feedback Management")
    print("17. Login Management")
    print("18. Settings Management")
    print("19. Notifications & Communication")
    print("20. Transportation Management")
    print("21. Maps & Navigation")
    print("22. Hotel Visual / Media System")
    print("23. Audit & Activity System")
    print("24. AI-Ready Business Tools")
    print("25. Database Management")
    print("26. Exit")

    print("-" * 60)

    choice = validate_menu_choice(
        "Enter Your Choice : ",
        [
            "1", "2", "3", "4", "5",
            "6", "7", "8", "9", "10",
            "11", "12", "13", "14", "15",
            "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26"
        ]
    )

    if choice == "1":
        hotel_information()

    elif choice == "2":
        restaurant_menu()      

    elif choice == "3":
        room_booking()

    elif choice == "4":
        table_booking()
        input("\nPress Enter to return to Main Menu...")

    elif choice == "5":

        print("=" * 50)
        print("          MY BOOKINGS")
        print("=" * 50)

        print("1. View Room Bookings")
        print("2. Search Room Booking")
        print("3. Delete Room Booking")
        print("4. View Table Bookings")
        print("5. Search Table Booking")
        print("6. Delete Table Booking")
        print("7. Back")

        booking_choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6", "7"]
        )

        if booking_choice == "1":

            view_room_bookings()

        elif booking_choice == "2":

            search_room_booking()

        elif booking_choice == "3":

            delete_room_booking()

        elif booking_choice == "4":

            view_table_bookings()

        elif booking_choice == "5":

            search_table_booking()

        elif booking_choice == "6":

            delete_table_booking()

        elif booking_choice == "7":

            continue

        input("\nPress Enter to return to Main Menu...")

    elif choice == "6":

        customer_management()

    elif choice == "7":

        staff_management()

    elif choice == "8":
        print("Opening AI Receptionist...")
        input("\nPress Enter to return to Main Menu...")

    elif choice == "9":
        print("Opening Contact Us...")
        input("\nPress Enter to return to Main Menu...")

    elif choice == "10":
        view_orders()
        input("\nPress Enter to return to Main Menu...")

    elif choice == "11":
        search_order()
        input("\nPress Enter to return to Main Menu...")

    elif choice == "12":
        delete_order()
        input("\nPress Enter to return to Main Menu...")

    elif choice == "13":
        inventory_management()

    elif choice == "14":
        reports_management()


    elif choice == "15":
        expense_management()

    elif choice == "16":
        feedback_management()

    elif choice == "17":
        login_management()

    elif choice == "18":
        settings_management()
        
    elif choice == "19":
        notifications_management()

    elif choice == "20":
        transportation_management()

    elif choice == "21":
        maps_navigation()

    elif choice == "22":
        media_management()

    elif choice == "23":
        audit_activity_management()

    elif choice == "24":
        ai_tools_management()

    elif choice == "25":
        database_management()

    elif choice == "26":
        print("Thank You...")
        break