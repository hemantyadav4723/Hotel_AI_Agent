from database.user_db import (
    save_user,
    view_users,
    delete_user,
    deactivate_user,
    activate_user,
    login_user,
    logout_user,
    get_current_session,
    change_password,
    reset_password,
    view_staff_user_link,
    link_staff_to_user,
    unlink_staff_from_user,
)

from utils.validators import (
    validate_menu_choice,
    validate_non_empty,
    validate_username,
    validate_password,
    validate_role,
)

from utils.display import print_success, press_enter
from role import role_management
from permission import permission_management


def login_management():
    while True:
        print("=" * 60)
        print("         LOGIN MANAGEMENT")
        print("=" * 60)

        print("1. Create User")
        print("2. View Users")
        print("3. Deactivate User")
        print("4. Activate User")
        print("5. Delete User")
        print("6. Login")
        print("7. Logout")
        print("8. Current Session")
        print("9. Change Password")
        print("10. Reset Password")
        print("11. Staff ↔ User Integration")
        print("12. Role Management")
        print("13. Permission Management")
        print("14. Back")

        choice = validate_menu_choice(
            "Enter Choice : ",
            [str(i) for i in range(1, 15)]
        )

        try:
            if choice == "1":
                user_id = validate_non_empty("User ID : ").upper()
                username = validate_username("Username : ")
                password = validate_password("Password : ")
                role = validate_role("Role (Admin/Staff) : ")
                staff_id = input("Staff ID (Optional) : ").strip().upper() or None
                reason = input("Creation Reason : ").strip()

                save_user(user_id, username, password, role, staff_id, reason)
                print_success("User Created Successfully.")

            elif choice == "2":
                view_users()

            elif choice == "3":
                deactivate_user()

            elif choice == "4":
                activate_user()

            elif choice == "5":
                delete_user()

            elif choice == "6":
                username = validate_username("Username : ")
                password = validate_password("Password : ")
                login_user(username, password)

            elif choice == "7":
                logout_user()

            elif choice == "8":
                session = get_current_session()
                if not session:
                    print("No Active Session.")
                else:
                    print("Current Session")
                    print("User ID    :", session["user_id"])
                    print("Username   :", session["username"])
                    print("Role       :", session["role"])
                    print("Hotel ID   :", session["hotel_id"])
                    print("Staff ID   :", session["staff_id"] or "-")
                    print("Login Time :", session["login_at"])

            elif choice == "9":
                change_password()

            elif choice == "10":
                reset_password()

            elif choice == "11":
                while True:
                    print("=" * 60)
                    print("        STAFF ↔ USER INTEGRATION")
                    print("=" * 60)
                    print("1. View Staff ↔ User Link")
                    print("2. Link Staff to User")
                    print("3. Unlink Staff from User")
                    print("4. Back")
                    sub_choice = validate_menu_choice(
                        "Enter Choice : ", ["1", "2", "3", "4"]
                    )
                    if sub_choice == "1":
                        view_staff_user_link()
                    elif sub_choice == "2":
                        link_staff_to_user()
                    elif sub_choice == "3":
                        unlink_staff_from_user()
                    elif sub_choice == "4":
                        break
                    press_enter()

            elif choice == "12":
                role_management()

            elif choice == "13":
                permission_management()

            elif choice == "14":
                break

        except ValueError as exc:
            print(f"Invalid User Data: {exc}")
        except Exception as exc:
            print(f"Error: {exc}")

        press_enter()
