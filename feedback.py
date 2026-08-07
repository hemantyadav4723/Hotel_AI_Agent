from billing import *
from utils.validators import *
from utils.display import *

def feedback_management():

    while True:

        print_header("FEEDBACK MANAGEMENT")

        print("1. Add Feedback")
        print("2. View Feedback")
        print("3. Search Feedback")
        print("4. Delete Feedback")
        print("5. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Chice : ",
            ["1", "2", "3", "4", "5"]
        )

        if choice == "1":

            feedback_id = input("Feedback ID : ").upper()
            customer_name = validate_name("Customer Name : ")
            mobile = validate_mobile("Mobile : ")
            rating = validate_rating("Rating (1-5) : ")
            review = validate_description("Review : ")

            save_feedback(
                feedback_id,
                customer_name,
                mobile,
                rating,
                review
            )

            print_success("Feedback Saved Successfully.")

        elif choice == "2":

            view_feedback()

        elif choice == "3":

            search_feedback()

        elif choice == "4":

            delete_feedback()

        elif choice == "5":

            break

        press_enter()