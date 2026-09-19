from utils.display import (
    print_header,
    print_footer,
    print_separator,
    press_enter
)

from utils.validators import validate_menu_choice
from database.attendance_db import (
    staff_check_in,
    staff_check_out,
    view_attendance,
    search_attendance,
    correct_attendance,
    view_attendance_correction_history,
    monthly_attendance_report,
)


def attendance_management():

    while True:

        print_header("ATTENDANCE MANAGEMENT")

        print("1. Check In")
        print("2. Check Out")
        print("3. View Attendance")
        print("4. Search Attendance")
        print("5. Correct Attendance")
        print("6. Attendance Correction History")
        print("7. Monthly Report")
        print("8. Back")

        print_separator()
        print_footer()

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            ["1", "2", "3", "4", "5", "6", "7", "8"]
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
            correct_attendance()

        elif choice == "6":
            view_attendance_correction_history()

        elif choice == "7":
            monthly_attendance_report()

        elif choice == "8":
            break

        press_enter()
