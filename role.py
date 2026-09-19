from database.role_db import (
    save_role,
    view_roles,
    search_role,
    update_role,
    deactivate_role,
    activate_role,
    delete_role,
    assign_role_to_user,
    remove_role_from_user,
    view_user_roles,
    view_role_assignment_history,
)
from utils.validators import validate_menu_choice, validate_non_empty
from utils.display import print_success, press_enter


def role_management():
    while True:
        print("=" * 60)
        print("              ROLE MANAGEMENT")
        print("=" * 60)
        print("1. Add Role")
        print("2. View Roles")
        print("3. Search Role")
        print("4. Update Role")
        print("5. Deactivate Role")
        print("6. Activate Role")
        print("7. Delete Role")
        print("8. Assign Role to User")
        print("9. Remove Role from User")
        print("10. View User Roles")
        print("11. Role Assignment History")
        print("12. Back")

        choice = validate_menu_choice("Enter Choice : ", [str(i) for i in range(1, 13)])

        try:
            if choice == "1":
                role_id = validate_non_empty("Role ID : ").upper()
                role_name = validate_non_empty("Role Name : ")
                save_role(role_id, role_name)
                print_success("Role Created Successfully.")
            elif choice == "2":
                view_roles()
            elif choice == "3":
                search_role()
            elif choice == "4":
                update_role()
            elif choice == "5":
                deactivate_role()
            elif choice == "6":
                activate_role()
            elif choice == "7":
                delete_role()
            elif choice == "8":
                assign_role_to_user(input("Reason : ").strip())
            elif choice == "9":
                remove_role_from_user(input("Reason : ").strip())
            elif choice == "10":
                view_user_roles()
            elif choice == "11":
                view_role_assignment_history()
            elif choice == "12":
                break
        except ValueError as exc:
            print(f"Invalid Role Data: {exc}")
        except Exception as exc:
            print(f"Error: {exc}")
        press_enter()
