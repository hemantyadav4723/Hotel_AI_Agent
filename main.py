from restaurant import restaurant_menu
from billing import *
from database.db_manager import delete_table_booking, view_table_bookings, search_table_booking
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
from data import *
from database.db_manager import view_orders, search_order, delete_order
from database.db_manager import view_room_bookings, search_room_booking, delete_room_booking

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
    print("19. Exit")

    print("-" * 60)

    choice = input("Enter Your Choice : ")

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

        booking_choice = input("Enter Your Choice : ")

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

        else:

            print("Invalid Choice")

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
        print("Thank You...")
        break

        input("\nPress Enter to return to Main Menu...")

    else:
        print("Invalid Choice")

def monthly_attendance_report():

    print("=" * 60)
    print("        MONTHLY ATTENDANCE REPORT")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    total_present = 0

    try:

        with open("attendance.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Staff ID : {staff_id}" in record:

                total_present += 1

        print("-" * 60)
        print("Staff ID      :", staff_id)
        print("Present Days  :", total_present)
        print("Absent Days   : Under Development")
        print("Working Hours : Under Development")
        print("-" * 60)

    except FileNotFoundError:

        print("attendance.txt File Not Found.")
