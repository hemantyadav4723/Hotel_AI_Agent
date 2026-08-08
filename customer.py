from utils.date_time import current_datetime_object
from utils.validators import *
from utils.display import *
from utils.helpers import *
from database.db_manager import save_customer, view_customers, search_customer, update_customer, delete_customer, customer_history, get_next_customer_id


from data import customer_counter

def customer_management():

    while True:

        print_header("CUSTOMER MANAGEMENT")

        print("1. Add Customer")
        print("2. View Customers")
        print("3. Search Customer")
        print("4. Update Customer")
        print("5. Delete Customer")
        print("6. Customer History")
        print("7. Back")

        print_separator
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6", "7"]
        )

        if choice == "1":

            customer_name, customer_mobile, customer_email, customer_address = get_customer_details()

            created_time = current_datetime_object()

            customer_id = get_next_customer_id()

            save_customer(
                customer_id,
                customer_name,
                customer_mobile,
                customer_email,
                customer_address,
                created_time
            )

            print_success("Customer Added Successfully.")
            print("Customer ID :", customer_id)

            press_enter()

        elif choice == "2":

            view_customers()          
            press_enter()

        elif choice == "3":

            search_customer()
            press_enter()

        elif choice == "4":

            update_customer()
            press_enter()

        elif choice == "5":

            delete_customer()
            press_enter()

        elif choice == "6":

            customer_history()
            press_enter()

        elif choice == "7":

            break