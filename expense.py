from billing import *

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
            title = input("Title : ")
            category = input("Category : ")
            amount = input("Amount : ")
            date = input("Date : ")

            save_expense(
                expense_id,
                title,
                category,
                amount,
                date
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