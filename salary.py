from utils.validators import validate_menu_choice, validate_price
from utils.display import print_header, print_footer, print_separator, press_enter
from database.salary_db import (
    save_salary,
    view_salary,
    search_salary,
    update_salary,
    get_salary_history,
)


def _read_effective_date():
    from datetime import datetime

    while True:
        value = input("Enter Effective Date (DD-MM-YYYY) : ").strip()
        try:
            datetime.strptime(value, "%d-%m-%Y")
            return value
        except ValueError:
            print("Invalid date. Use DD-MM-YYYY format.")


def _read_salary_values():
    basic_salary = validate_price("Enter Basic Salary : ")
    allowances = validate_price("Enter Allowances : ")
    bonus = validate_price("Enter Bonus : ")
    deduction = validate_price("Enter Deduction : ")
    return basic_salary, allowances, bonus, deduction


def _read_staff_id():
    return input("Enter Staff ID : ").strip().upper()


def salary_management():
    while True:
        print_header("SALARY MANAGEMENT")

        print("1. Add Salary")
        print("2. View Current Salary")
        print("3. Search Salary")
        print("4. Update Salary")
        print("5. Salary History")
        print("6. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6"]
        )

        try:
            if choice == "1":
                staff_id = _read_staff_id()
                basic, allowances, bonus, deduction = _read_salary_values()
                effective_date = _read_effective_date()
                save_salary(
                    staff_id,
                    basic,
                    allowances,
                    bonus,
                    deduction,
                    effective_date,
                    input("Reason : ").strip(),
                )

            elif choice == "2":
                view_salary()

            elif choice == "3":
                search_salary(_read_staff_id())

            elif choice == "4":
                staff_id = _read_staff_id()
                basic, allowances, bonus, deduction = _read_salary_values()
                effective_date = _read_effective_date()
                update_salary(
                    staff_id,
                    basic,
                    allowances,
                    bonus,
                    deduction,
                    effective_date,
                )

            elif choice == "5":
                records = get_salary_history(_read_staff_id())
                if not records:
                    print("Salary History Not Found.")
                else:
                    for record in records:
                        print_separator()
                        from database.salary_db import _print_salary_record
                        _print_salary_record(record)

            elif choice == "6":
                break

        except (ValueError, TypeError) as exc:
            print(f"Salary Error: {exc}")
        except Exception as exc:
            print(f"Error: {exc}")

        if choice != "6":
            press_enter()
