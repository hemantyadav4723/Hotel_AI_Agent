from utils.validators import *
from utils.display import *
from utils.date_time import current_datetime_object
from database.db_manager import (
    get_next_staff_id,
    save_staff, view_staff, search_staff, update_staff, delete_staff, staff_check_in, staff_check_out, view_attendance,
    search_attendance, monthly_attendance_report
)

from billing import (
    save_salary,
    view_salary,
    search_salary,
    update_salary,
    delete_salary,
    generate_payroll,
    view_payroll,
    search_payroll,
    delete_payroll,
    save_department,
    view_department,
    search_department,
    update_department,
    delete_department
)

def staff_management():

    while True:

        print_header("STAFF MANAGEMENT")

        print("1. Staff Records")
        print("2. Attendance Management")
        print("3. Salary Management")
        print("4. Departments")
        print("5. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5"]
        )

        if choice == "1":

            staff_records()

        elif choice == "2":

            attendance_management()

        elif choice == "3":

            salary_management()

        elif choice == "4":

            department_management()

        elif choice == "5":
       
            break

        press_enter()

def attendance_management():

    while True:

        print_header("ATTENDANCE MANAGEMENT")

        print("1. Check In")
        print("2. Check Out")
        print("3. View Attendance")
        print("4. Search Attendance")
        print("5. Monthly Report")
        print("6. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6"]
        )

        if choice == "1":

            staff_check_in()

        elif choice == "2":

            staff_check_out()

        elif choice == "3":

            view_attendance()

        elif choice == "4":

            search_attendance()

        elif choice == "5":

            monthly_attendance_report()

        elif choice == "6":

            break

        press_enter()


def salary_management():

    while True:

        print_header("SALARY MANAGEMENT")

        print("1. Add Salary")
        print("2. View Salary")
        print("3. Search Salary")
        print("4. Update Salary")
        print("5. Delete Salary")
        print("6. Generate Payroll")
        print("7. View Payroll")
        print("8. Search Payroll")
        print("9. Delete Payroll")
        print("10. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        )

        if choice == "1":

            staff_id = input("Enter Staff ID : ").upper()

            staff_name = input("Enter Staff Name : ")

            department = input("Enter Department : ")

            basic_salary = validate_price("Enter Basic Salary : ")

            bonus = validate_price("Enter Bonus : ")

            deduction = validate_price("Enter Deduction : ")

            net_salary = basic_salary + bonus - deduction

            save_salary(

                staff_id,
                staff_name,
                department,
                basic_salary,
                bonus,
                deduction,
                net_salary
            )

            print_success("Salary Saved Successfully.")

        elif choice == "2":

            view_salary()

        elif choice == "3":

            search_salary()

        elif choice == "4":

            update_salary()

        elif choice == "5":

            delete_salary()

        elif choice == "6":

            generate_payroll()

        elif choice == "7":

            view_payroll()

        elif choice == "8":

            search_payroll()

        elif choice == "9":

            delete_payroll()

        elif choice == "10":

            break

        press_enter()


def department_management():

    while True:

        print_header("DEPARTMENT MANAGEMENT")

        print("1. Add Department")
        print("2. View Department")
        print("3. Search Department")
        print("4. Update Department")
        print("5. Delete Department")
        print("6. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6"]
        )

        if choice == "1":

            department_id = input("Enter Department ID : ").upper()

            department_name = input("Enter Department Name : ")

            save_department(
                department_id,
                department_name
            )

            print_success("Department Added Successfully.")

        elif choice == "2":

            view_department()

        elif choice == "3":

            search_department()

        elif choice == "4":

            update_department()

        elif choice == "5":

            delete_department()

        elif choice == "6":

            break

        press_enter()

def staff_records():

    while True:

        print_header("STAFF RECORDS")

        print("1. Add Staff")
        print("2. View Staff")
        print("3. Search Staff")
        print("4. Update Staff")
        print("5. Delete Staff")
        print("6. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6"]
    
        )

        if choice == "1":

            staff_id = get_next_staff_id()

            joining_date = current_datetime_object()

            staff_name = validate_name("Enter Staff Name : ")

            mobile = validate_mobile("Enter Mobile Number : ")

            email = validate_email("Enter Email : ")
            department = input("Enter Department : ")
            designation = input("Enter Designation : ")

            salary = validate_price("Enter Salary : ")

            save_staff(
                staff_id,
                joining_date,
                staff_name,
                mobile,
                email,
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

            delete_staff()

        elif choice == "6":

            break

        press_enter()