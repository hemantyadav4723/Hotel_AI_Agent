from utils.validators import validate_menu_choice
from utils.display import (
    print_header,
    print_footer,
    print_separator,
    print_success,
    press_enter,
)
from database.designation_db import (
    save_designation,
    view_designation,
    search_designation,
    update_designation,
    deactivate_designation,
    activate_designation,
    view_designation_staff,
    delete_designation,
)


def designation_management():
    while True:
        print_header("DESIGNATION / POSITION MANAGEMENT")

        print("1. Add Designation")
        print("2. View Designation")
        print("3. Search Designation")
        print("4. Update Designation")
        print("5. Deactivate Designation")
        print("6. Activate Designation")
        print("7. Designation-wise Staff View")
        print("8. Delete Designation")
        print("9. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            [str(i) for i in range(1, 10)],
        )

        if choice == "1":
            designation_id = input("Enter Designation ID : ").strip().upper()
            designation_name = input("Enter Designation Name : ").strip()

            try:
                save_designation(designation_id, designation_name)
                print_success("Designation Added Successfully.")
            except ValueError as exc:
                print(f"Invalid Designation Data: {exc}")
            except Exception as exc:
                print(f"Error adding designation: {exc}")

        elif choice == "2":
            view_designation()

        elif choice == "3":
            search_designation()

        elif choice == "4":
            update_designation()

        elif choice == "5":
            deactivate_designation()

        elif choice == "6":
            activate_designation()

        elif choice == "7":
            view_designation_staff()

        elif choice == "8":
            delete_designation()

        elif choice == "9":
            break

        press_enter()
