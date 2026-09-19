from database.permission_db import (
    view_permissions,
    search_permission,
    deactivate_permission,
    activate_permission,
    get_active_permissions,
    assign_permission_to_role,
    remove_permission_from_role,
    view_role_permissions,
    view_permission_roles,
    view_role_permission_history,
)
from utils.validators import validate_menu_choice


def permission_management():
    while True:
        print("=" * 60)
        print("              PERMISSION MANAGEMENT")
        print("=" * 60)
        print("1. View Permissions")
        print("2. Search Permission")
        print("3. View Permissions by Module")
        print("4. Deactivate Permission")
        print("5. Activate Permission")
        print("6. Assign Permission to Role")
        print("7. Remove Permission from Role")
        print("8. View Role Permissions")
        print("9. View Permission Roles")
        print("10. Role-Permission History")
        print("11. Back")
        print("-" * 60)

        choice = validate_menu_choice(
            "Enter Choice : ", [str(i) for i in range(1, 12)]
        )
        try:
            if choice == "1":
                view_permissions()
            elif choice == "2":
                search_permission()
            elif choice == "3":
                module = input("Module Name : ").strip()
                rows = get_active_permissions(module)
                if not rows:
                    print("No active permissions found for this module.")
                else:
                    for row in rows:
                        print(f"{row['permission_id']} | {row['permission_name']}")
            elif choice == "4":
                deactivate_permission()
            elif choice == "5":
                activate_permission()
            elif choice == "6":
                assign_permission_to_role(input("Reason : ").strip())
            elif choice == "7":
                remove_permission_from_role(input("Reason : ").strip())
            elif choice == "8":
                view_role_permissions()
            elif choice == "9":
                view_permission_roles()
            elif choice == "10":
                view_role_permission_history()
            elif choice == "11":
                return
        except Exception as exc:
            print(f"Permission Management Error: {exc}")

        if choice != "11":
            input("\nPress Enter to continue...")
