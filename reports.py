from billing import *
from utils.display import *
from utils.validators import *

def reports_management():

    while True:

        print_header("REPORTS & ANALYTICS")

        print("1. Sales Report")
        print("2. Restaurant Report")
        print("3. Room Booking Report")
        print("4. Table Booking Report")
        print("5. Customer Report")
        print("6. Staff Report")
        print("7. Salary Report")
        print("8. Inventory Report")
        print("9. Hotel Dashboard")
        print("10. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Choice : ",
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        )

        if choice=="1":

            sales_report()

        elif choice=="2":

            restaurant_report()

        elif choice=="3":

            room_report()

        elif choice=="4":

            table_report()

        elif choice=="5":

            customer_report()

        elif choice=="6":

            staff_report()

        elif choice=="7":

            salary_report()

        elif choice=="8":

            inventory_report()

        elif choice=="9":

            hotel_dashboard()

        elif choice=="10":

            break

        press_enter()