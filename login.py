from billing import *

def login_management():

    while True:

        print("=" * 60)
        print("         LOGIN MANAGEMENT")
        print("=" * 60)

        print("1. Create User")
        print("2. View Users")
        print("3. Delete User")
        print("4. Login")
        print("5. Back")

        choice = input("Enter Choice : ")

        if choice == "1":

            user_id = input("User ID : ").upper()
            username = input("Username : ")
            password = input("Password : ")
            role = input("Role (Admin/Staff) : ")

            save_user(
                user_id,
                username,
                password,
                role
            )

            print("User Created Successfully.")

        elif choice == "2":

            view_users()

        elif choice == "3":

            delete_user()

        elif choice == "4":

            username = input("Username : ")
            password = input("Password : ")

            verify_login(
                username,
                password
            )

        elif choice == "5":

            break

        else:

            print("Invalid Choice")

        input("\nPress Enter...")

