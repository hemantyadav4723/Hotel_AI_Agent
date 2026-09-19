from attendance import attendance_management
from leave import leave_management
from salary import salary_management
from department import department_management
from utils.validators import (
    validate_menu_choice,
    validate_name,
    validate_mobile,
    validate_email,
    validate_price
)

from utils.display import (
    print_header,
    print_footer,
    print_separator,
    print_success,
    press_enter
)
from utils.date_time import current_datetime_object
from database.staff_db import (
    save_staff,
    view_staff,
    search_staff,
    update_staff,
    delete_staff,
    deactivate_staff,
    activate_staff,
    change_staff_status,
    view_staff_status_history,
    get_next_staff_id
)
from database.hr_audit_db import view_hr_audit_history
from database.department_db import get_department_names
from database.designation_db import get_designation_names
from payroll import payroll_management


def select_department():
    departments = get_department_names()

    print()
    print("Available Departments:")

    if not departments:
        print("No departments available. Please create a department first from Department Management.")
        return None

    for index, department_name in enumerate(departments, start=1):
        print(f"{index}. {department_name}")

    while True:
        selection = input("Select Department No : ").strip()
        if selection.isdigit():
            department_index = int(selection)
            if 1 <= department_index <= len(departments):
                return departments[department_index - 1]
        print("Invalid selection. Please select a valid department number.")


def select_designation():
    designations = get_designation_names()

    print()
    print("Available Designations:")

    if not designations:
        print("No designations available. Please create a designation first from Designation Management.")
        return None

    for index, designation_name in enumerate(designations, start=1):
        print(f"{index}. {designation_name}")

    while True:
        selection = input("Select Designation No : ").strip()
        if selection.isdigit():
            designation_index = int(selection)
            if 1 <= designation_index <= len(designations):
                return designations[designation_index - 1]
        print("Invalid selection. Please select a valid designation number.")


def staff_management():

    while True:

        print_header("STAFF MANAGEMENT")

        print("1. Staff Records")
        print("2. Attendance Management")
        print("3. Leave Management")
        print("4. Salary Management")
        print("5. Payroll Management")
        print("6. Department Management")
        print("7. Designation Management")
        print("8. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            [str(i) for i in range(1, 9)]
        )

        if choice == "1":
            staff_records()

        elif choice == "2":
            attendance_management()

        elif choice == "3":
            leave_management()

        elif choice == "4":
            salary_management()

        elif choice == "5":
            payroll_management()

        elif choice == "6":
            department_management()

        elif choice == "7":
            from designation import designation_management
            designation_management()

        elif choice == "8":
            break

        press_enter()


def staff_records():

    while True:

        print_header("STAFF RECORDS")

        print("1. Add Staff")
        print("2. View Staff")
        print("3. Search Staff")
        print("4. Update Staff")
        print("5. Deactivate Staff")
        print("6. Activate Staff")
        print("7. Change Staff Status")
        print("8. Staff Status History")
        print("9. HR Audit & Activity History")
        print("10. Delete Staff")
        print("11. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            [str(i) for i in range(1, 12)]
        )

        if choice == "1":

            staff_id = get_next_staff_id()

            joining_date = current_datetime_object()

            staff_name = validate_name("Enter Staff Name : ")

            mobile = validate_mobile("Enter Mobile Number : ")

            email = validate_email("Enter Email : ")
            address = input("Enter Address : ").strip()
            department = select_department()
            if department is None:
                press_enter()
                continue

            designation = select_designation()
            if designation is None:
                press_enter()
                continue

            salary = validate_price("Enter Salary : ")

            save_staff(
                staff_id,
                joining_date,
                staff_name,
                mobile,
                email,
                address,
                department,
                designation,
                salary
            )

            print_success("Staff Added Successfully.")
            print("Staff ID :", staff_id)

        elif choice == "2":

            view_staff()

        elif choice == "3":

            search_staff()

        elif choice == "4":

            update_staff()

        elif choice == "5":

            deactivate_staff()

        elif choice == "6":

            activate_staff()

        elif choice == "7":

            change_staff_status()

        elif choice == "8":

            view_staff_status_history()

        elif choice == "9":

            view_hr_audit_history()

        elif choice == "10":

            delete_staff()

        elif choice == "11":

            break

        press_enter()