from utils.display import print_header, print_footer, print_separator, press_enter
from utils.validators import validate_menu_choice

from database.report_db import (
    sales_report,
    restaurant_report,
    room_report,
    table_report,
    customer_report,
    staff_report,
    salary_report,
    inventory_report,
    expense_report,
)
from database.hr_report_db import hr_analytics_menu
from database.procurement_report_db import procurement_report
from database.analytics_report_db import (
    dashboard_report,
    revenue_report,
    room_revenue_report,
    restaurant_revenue_report,
    occupancy_report,
    adr_report,
    revpar_report,
    booking_trends_report,
    cancellation_report,
    no_show_report,
    customer_trends_report,
    inventory_trends_report,
    expense_trends_report,
    department_performance_report,
    staff_reports_report,
    profitability_report,
)


def _operational_reports_menu():
    while True:
        print_header("OPERATIONAL REPORTS")
        print("1. Sales Report")
        print("2. Restaurant Report")
        print("3. Room Booking Report")
        print("4. Table Booking Report")
        print("5. Customer Report")
        print("6. Staff Report")
        print("7. Salary Report")
        print("8. Inventory Report")
        print("9. HR & Staff Analytics")
        print("10. Procurement Report")
        print("11. Expense Report")
        print("12. Back")
        print_separator()
        choice = validate_menu_choice("Enter Choice : ", [str(i) for i in range(1, 13)])
        actions = {
            "1": sales_report,
            "2": restaurant_report,
            "3": room_report,
            "4": table_report,
            "5": customer_report,
            "6": staff_report,
            "7": salary_report,
            "8": inventory_report,
            "9": hr_analytics_menu,
            "10": procurement_report,
            "11": expense_report,
        }
        if choice == "12":
            return
        actions[choice]()
        press_enter()


def reports_management():
    while True:
        print_header("REPORTS & ANALYTICS")
        print("1. Dashboard")
        print("2. Revenue")
        print("3. Room Revenue")
        print("4. Restaurant Revenue")
        print("5. Occupancy")
        print("6. ADR")
        print("7. RevPAR")
        print("8. Booking Trends")
        print("9. Cancellation")
        print("10. No-show")
        print("11. Customer Trends")
        print("12. Inventory Trends")
        print("13. Expense Trends")
        print("14. Department Performance")
        print("15. Staff Reports")
        print("16. Profitability Foundation")
        print("17. Operational Reports")
        print("18. Back")
        print_separator()
        choice = validate_menu_choice(
            "Enter Choice : ", [str(i) for i in range(1, 19)]
        )
        actions = {
            "1": dashboard_report,
            "2": revenue_report,
            "3": room_revenue_report,
            "4": restaurant_revenue_report,
            "5": occupancy_report,
            "6": adr_report,
            "7": revpar_report,
            "8": booking_trends_report,
            "9": cancellation_report,
            "10": no_show_report,
            "11": customer_trends_report,
            "12": inventory_trends_report,
            "13": expense_trends_report,
            "14": department_performance_report,
            "15": staff_reports_report,
            "16": profitability_report,
            "17": _operational_reports_menu,
        }
        if choice == "18":
            break
        actions[choice]()
        press_enter()
