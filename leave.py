from utils.display import print_header, print_footer, print_separator, press_enter
from utils.validators import validate_menu_choice
from database.leave_db import (
    request_leave,
    view_leave_requests,
    search_leave,
    approve_leave,
    reject_leave,
    cancel_leave,
)


def leave_management():
    while True:
        print_header("LEAVE MANAGEMENT")

        print("1. Request Leave")
        print("2. View Leave History")
        print("3. Search Staff Leave")
        print("4. Approve Leave")
        print("5. Reject Leave")
        print("6. Cancel Leave")
        print("7. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6", "7"]
        )

        if choice == "1":
            request_leave()
        elif choice == "2":
            view_leave_requests()
        elif choice == "3":
            search_leave()
        elif choice == "4":
            approve_leave()
        elif choice == "5":
            reject_leave()
        elif choice == "6":
            cancel_leave()
        elif choice == "7":
            break

        press_enter()
