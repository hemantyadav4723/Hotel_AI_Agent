from utils.validators import validate_menu_choice
from utils.display import print_header, print_footer, print_separator, press_enter
from database.payroll_db import (
    generate_payroll,
    view_payroll,
    search_payroll,
    correct_payroll,
    view_payroll_correction_history,
    monthly_payroll_report,
    delete_payroll,
)


def payroll_management():
    while True:
        print_header("PAYROLL MANAGEMENT")

        print("1. Generate Payroll")
        print("2. View Payroll")
        print("3. Search Staff Payroll")
        print("4. Correct Payroll")
        print("5. Monthly Payroll Report")
        print("6. Payroll Correction History")
        print("7. Delete Payroll")
        print("8. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6", "7", "8"]
        )

        try:
            if choice == "1":
                reason = input("Generation Reason : ").strip()
                generate_payroll(reason)
            elif choice == "2":
                view_payroll()
            elif choice == "3":
                search_payroll()
            elif choice == "4":
                correct_payroll()
            elif choice == "5":
                monthly_payroll_report()
            elif choice == "6":
                view_payroll_correction_history()
            elif choice == "7":
                delete_payroll()
            elif choice == "8":
                break

        except PermissionError as exc:
            message = str(exc).strip()
            if message.lower().startswith("login required"):
                print("Login Required: Please login first from Main Menu -> 17. Login Management -> 6. Login.")
            else:
                print(f"Authorization Denied: {message}")

        if choice != "8":
            press_enter()
