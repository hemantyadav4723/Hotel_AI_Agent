import sqlite3
from database.hotel_context import get_current_hotel_id

from database.expense_category_db import (
    expense_category_management,
    get_active_expense_category_options,
)
from database.department_db import get_active_department_options

from database.expenses_db import (
    save_expense,
    view_expenses,
    search_expense,
    update_expense,
    delete_expense,
    _vendor_options,
    get_expense_payment_methods,
    approve_expense,
    reject_expense,
    view_pending_expense_approvals,
)

from utils.validators import (
    validate_positive_number,
    validate_menu_choice,
)


def expense_management():

    while True:

        print("=" * 60)
        print("         EXPENSE MANAGEMENT")
        print("=" * 60)

        print("1. Expense Categories")
        print("2. Add Expense")
        print("3. View Expenses")
        print("4. Search Expense")
        print("5. Update Expense")
        print("6. Delete Expense")
        print("7. Expense Approval")
        print("8. Back")

        choice = validate_menu_choice(
            "Enter Choice : ",
            ["1", "2", "3", "4", "5", "6", "7", "8"]
        )

        try:
            if choice == "1":

                expense_category_management()

            elif choice == "2":

                expense_id = input("Expense ID : ").strip().upper()
                expense_name = input("Expense Name : ").strip()
                amount = validate_positive_number("Amount : ")

                categories = get_active_expense_category_options()

                if not categories:
                    print("No Active Expense Categories Found.")
                    print("Create an Expense Category first.")
                    input("\nPress Enter...")
                    continue

                print("\nAvailable Expense Categories:")
                for index, category in enumerate(categories, start=1):
                    print(
                        f"{index}. {category['category_id']} - "
                        f"{category['category_name']}"
                    )

                category_choice = validate_menu_choice(
                    "Select Category : ",
                    [str(i) for i in range(1, len(categories) + 1)]
                )

                selected_category = categories[int(category_choice) - 1]

                print("\nExpense Payment Methods:")
                payment_methods = get_expense_payment_methods()
                for index, method in enumerate(payment_methods, start=1):
                    print(f"{index}. {method}")

                payment_choice = validate_menu_choice(
                    "Select Payment Method : ",
                    [str(i) for i in range(1, len(payment_methods) + 1)]
                )
                selected_payment_method = payment_methods[int(payment_choice) - 1]

                vendors = _vendor_options(
                    get_current_hotel_id()
                )
                selected_vendor_id = None

                if vendors:
                    print("\nAvailable Vendors:")
                    print("0. Not Provided")
                    for index, vendor in enumerate(vendors, start=1):
                        print(
                            f"{index}. {vendor['supplier_id']} - "
                            f"{vendor['supplier_name']}"
                        )

                    vendor_choice = validate_menu_choice(
                        "Select Vendor : ",
                        ["0"] + [str(i) for i in range(1, len(vendors) + 1)]
                    )
                    if vendor_choice != "0":
                        selected_vendor_id = vendors[int(vendor_choice) - 1]["supplier_id"]
                else:
                    print("\nNo Active Vendors Found. Vendor will be Not Provided.")

                departments = get_active_department_options()
                selected_department_id = None

                print("\nAvailable Departments:")
                print("0. Not Provided")
                for index, department in enumerate(departments, start=1):
                    print(
                        f"{index}. {department['department_id']} - "
                        f"{department['department_name']}"
                    )

                department_choice = validate_menu_choice(
                    "Select Department : ",
                    ["0"] + [str(i) for i in range(1, len(departments) + 1)]
                )

                if department_choice != "0":
                    selected_department_id = departments[int(department_choice) - 1]["department_id"]

                recurring_choice = validate_menu_choice(
                    "Recurring Expense? (1=No, 2=Yes) : ",
                    ["1", "2"]
                )
                is_recurring = recurring_choice == "2"
                recurrence_frequency = None
                recurrence_start_date = None

                if is_recurring:
                    frequency_choice = validate_menu_choice(
                        "Frequency (1=Daily, 2=Weekly, 3=Monthly, 4=Quarterly, 5=Yearly) : ",
                        ["1", "2", "3", "4", "5"]
                    )
                    recurrence_frequency = {
                        "1": "Daily",
                        "2": "Weekly",
                        "3": "Monthly",
                        "4": "Quarterly",
                        "5": "Yearly",
                    }[frequency_choice]
                    recurrence_start_date = input(
                        "Recurring Start Date (YYYY-MM-DD) : "
                    ).strip()

                receipt_reference = input("Receipt / Reference (Optional) : ").strip()
                description = input("Description : ").strip()
                expense_date = input("Date (DD-MM-YYYY) : ").strip()
                expense_time = input("Time (HH:MM AM/PM) : ").strip()

                save_expense(
                    expense_id,
                    expense_date,
                    expense_time,
                    expense_name,
                    amount,
                    selected_category["category_name"],
                    description,
                    category_id=selected_category["category_id"],
                    vendor_id=selected_vendor_id,
                    payment_method=selected_payment_method,
                    receipt_reference=receipt_reference,
                    department_id=selected_department_id,
                    is_recurring=is_recurring,
                    recurrence_frequency=recurrence_frequency,
                    recurrence_start_date=recurrence_start_date,
                )

                print("Expense Added Successfully.")

            elif choice == "3":

                view_expenses()

            elif choice == "4":

                search_expense()

            elif choice == "5":

                update_expense()

            elif choice == "6":

                delete_expense()

            elif choice == "7":

                while True:
                    print("\n" + "=" * 60)
                    print("              EXPENSE APPROVAL")
                    print("=" * 60)
                    print("1. Pending Approvals")
                    print("2. Approve Expense")
                    print("3. Reject Expense")
                    print("4. Back")

                    approval_choice = validate_menu_choice(
                        "Enter Choice : ",
                        ["1", "2", "3", "4"]
                    )

                    try:
                        if approval_choice == "1":
                            view_pending_expense_approvals()
                        elif approval_choice == "2":
                            approve_expense()
                        elif approval_choice == "3":
                            reject_expense()
                        else:
                            break
                    except (ValueError, PermissionError) as exc:
                        print(f"Error: {exc}")

                    if approval_choice != "4":
                        input("\nPress Enter...")

            elif choice == "8":

                break

        except PermissionError as exc:
            print(f"\n[LOGIN REQUIRED] {exc}")
            print("Please login with an authorized account and try again.")
        except sqlite3.Error as exc:
            print(f"\n[DATABASE ERROR] {exc}")
            print("The operation could not be completed. Your Expense data was not saved.")
        except ValueError as exc:
            print(f"\nError: {exc}")

        if choice != "7":
            input("\nPress Enter...")
