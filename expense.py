from database.db_manager import save_expense, view_expenses, search_expense, update_expense, delete_expense

def expense_management():

    while True:

        print("=" * 60)
        print("         EXPENSE MANAGEMENT")
        print("=" * 60)

        print("1. Add Expense")
        print("2. View Expenses")
        print("3. Search Expense")
        print("4. Update Expense")
        print("5. Delete Expense")
        print("6. Back")

        choice = input("Enter Choice : ")

        if choice == "1":

            expense_id = input("Expense ID : ").upper()

            expense_name = input("Expense Name : ")

            amount = float(input("Amount : "))

            category = input("Category : ")

            description = input("Description : ")

            expense_date = input("Date (DD-MM-YYYY) : ")

            expense_time = input("Time (HH:MM AM/PM) : ")

            save_expense(
                expense_id,
                expense_date,
                expense_time,
                expense_name,
                amount,
                category,
                description
            )

            print("Expense Added Successfully.")

        elif choice == "2":

            view_expenses()

        elif choice == "3":

            search_expense()

        elif choice == "4":

            update_expense()

        elif choice == "5":

            delete_expense()

        elif choice == "6":

            break

        else:

            print("Invalid Choice")

        input("\nPress Enter...")