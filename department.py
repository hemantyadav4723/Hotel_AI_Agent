from utils.validators import validate_menu_choice
from utils.display import print_header, print_footer, print_separator, print_success, press_enter
from database.department_db import (
    save_department,
    view_department,
    search_department,
    update_department,
    delete_department,
    deactivate_department,
    activate_department,
    view_department_staff,
)


def department_management():
    while True:
        print_header("DEPARTMENT MANAGEMENT")
        print("1. Add Department")
        print("2. View Department")
        print("3. Search Department")
        print("4. Update Department")
        print("5. Deactivate Department")
        print("6. Activate Department")
        print("7. Department-wise Staff View")
        print("8. Delete Department")
        print("9. Back")
        print_separator()
        print_footer()

        choice = validate_menu_choice("Enter Your Choice : ", [str(i) for i in range(1, 10)])

        if choice == "1":
            department_id = input("Enter Department ID : ").strip().upper()
            department_name = input("Enter Department Name : ").strip()
            try:
                save_department(department_id, department_name)
                print_success("Department Added Successfully.")
            except ValueError as exc:
                print(f"Invalid Department Data: {exc}")
            except Exception as exc:
                print(f"Error adding department: {exc}")

        elif choice == "2":
            view_department()
        elif choice == "3":
            search_department()
        elif choice == "4":
            update_department()
        elif choice == "5":
            deactivate_department()
        elif choice == "6":
            activate_department()
        elif choice == "7":
            view_department_staff()
        elif choice == "8":
            delete_department()
        elif choice == "9":
            break

        press_enter()
