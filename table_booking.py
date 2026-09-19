from database.table_booking_db import (
    create_table_booking,
    create_restaurant_table,
    update_restaurant_table_capacity,
    update_restaurant_table_section,
    get_table_sections,
    add_table_section,
    deactivate_table_section,
    get_all_tables,
    get_available_restaurant_tables,
    get_reserved_restaurant_tables,
    get_table_by_number,
    check_table_available,
    get_active_table_assignments,
    get_table_history,
    reassign_table_booking,
    delete_table_booking,
    merge_restaurant_tables,
    get_active_table_merges,
    release_table_merge,
    split_table_merge,
    get_table_cleaning_tasks,
    start_table_cleaning,
    complete_table_cleaning
)

from utils.display import (
    print_error,
    press_enter
)
from utils.date_time import (
    current_datetime_object,
    generate_order_id
)


def _create_table():
    print("=" * 50)
    print("          CREATE RESTAURANT TABLE")
    print("=" * 50)

    table_number = input("Enter New Table Number (0 = Back) : ").strip().upper()
    if table_number == "0":
        return

    while True:
        capacity_input = input("Enter Table Capacity : ").strip()
        try:
            capacity = int(capacity_input)
            if capacity <= 0:
                raise ValueError
            break
        except ValueError:
            print_error("Capacity must be a whole number greater than 0.")

    table_section = _select_table_section("Select Table Section/Area")
    if table_section is None:
        return

    try:
        create_restaurant_table(table_number, capacity, table_section)
        print("\n" + "=" * 50)
        print("Table Created Successfully!")
        print("=" * 50)
        print(f"Table Number : {table_number}")
        print(f"Capacity     : {capacity} Persons")
        print(f"Section/Area : {table_section}")
        print("Status       : Available")
        print("=" * 50)
    except ValueError as e:
        print_error(str(e))
    except Exception as e:
        print_error(f"Unable to create table: {e}")

    press_enter()


def _update_table_capacity():
    print("=" * 50)
    print("       UPDATE TABLE CAPACITY")
    print("=" * 50)

    table_number = input("Enter Table Number (0 = Back) : ").strip().upper()
    if table_number == "0":
        return

    table = get_table_by_number(table_number)
    if table is None:
        print_error("Invalid Table Number.")
        press_enter()
        return

    print(f"Current Capacity : {table['table_capacity']} Persons")
    print(f"Current Status   : {table['table_status']}")

    while True:
        capacity_input = input("Enter New Capacity : ").strip()
        try:
            capacity = int(capacity_input)
            if capacity <= 0:
                raise ValueError
            break
        except ValueError:
            print_error("Capacity must be a whole number greater than 0.")

    try:
        update_restaurant_table_capacity(table_number, capacity)
        print("\n" + "=" * 50)
        print("Table Capacity Updated Successfully!")
        print("=" * 50)
        print(f"Table Number : {table_number}")
        print(f"New Capacity : {capacity} Persons")
        print("=" * 50)
    except ValueError as e:
        print_error(str(e))
    except Exception as e:
        print_error(f"Unable to update table capacity: {e}")

    press_enter()



def _update_table_section():
    print("=" * 50)
    print("       UPDATE TABLE SECTION / AREA")
    print("=" * 50)

    table_number = input("Enter Table Number (0 = Back) : ").strip().upper()
    if table_number == "0":
        return

    table = get_table_by_number(table_number)
    if table is None:
        print_error("Invalid Table Number.")
        press_enter()
        return

    print(f"Current Section/Area : {table['table_section']}")

    table_section = _select_table_section("Select New Section/Area")
    if table_section is None:
        return

    try:
        update_restaurant_table_section(table_number, table_section)
        print("\n" + "=" * 50)
        print("Table Section/Area Updated Successfully!")
        print("=" * 50)
        print(f"Table Number : {table_number}")
        print(f"Section/Area : {table_section}")
        print("=" * 50)
    except ValueError as e:
        print_error(str(e))
    except Exception as e:
        print_error(f"Unable to update table section/area: {e}")

    press_enter()


def _select_table_section(title="Select Table Section/Area"):
    """Let the user choose only from currently configured active areas."""
    sections = get_table_sections()

    if not sections:
        print_error("No active Section/Area is configured. Add one first.")
        press_enter()
        return None

    print("\n" + "=" * 50)
    print(f"          {title.upper()}")
    print("=" * 50)
    for index, section in enumerate(sections, 1):
        print(f"{index}. {section['section_name']}")
    print("0. Back")
    print("-" * 50)

    valid_choices = {str(index): section["section_name"] for index, section in enumerate(sections, 1)}
    while True:
        choice = input("Enter Choice : ").strip()
        if choice == "0":
            return None
        if choice in valid_choices:
            return valid_choices[choice]
        print_error("Invalid Choice. Please select a configured Section/Area.")


def _manage_table_sections():
    """Manage the hotel-specific Section/Area master."""
    while True:
        sections = get_table_sections(active_only=False)

        print("\n" + "=" * 50)
        print("       MANAGE TABLE SECTIONS / AREAS")
        print("=" * 50)
        print("1. Add Section / Area")
        print("2. Deactivate Section / Area")
        print("3. View Sections / Areas")
        print("0. Back")
        print("-" * 50)

        choice = input("Enter Your Choice : ").strip()

        if choice == "1":
            section_name = input("Enter New Section/Area Name (0 = Back) : ").strip()
            if section_name == "0":
                continue
            try:
                result = add_table_section(section_name)
                print(f"\nSection/Area '{result}' is active and ready to use.")
            except ValueError as e:
                print_error(str(e))
            press_enter()

        elif choice == "2":
            active_sections = get_table_sections()
            if not active_sections:
                print_error("No active Section/Area is available.")
                press_enter()
                continue

            print("\nActive Sections / Areas")
            for index, section in enumerate(active_sections, 1):
                print(f"{index}. {section['section_name']}")
            print("0. Back")

            section_choice = input("Enter Choice : ").strip()
            if section_choice == "0":
                continue
            if not section_choice.isdigit() or not (1 <= int(section_choice) <= len(active_sections)):
                print_error("Invalid Choice.")
                press_enter()
                continue

            section_name = active_sections[int(section_choice) - 1]["section_name"]
            try:
                deactivate_table_section(section_name)
                print(f"\nSection/Area '{section_name}' deactivated successfully.")
            except ValueError as e:
                print_error(str(e))
            press_enter()

        elif choice == "3":
            print("\nConfigured Sections / Areas")
            if not sections:
                print("No sections configured.")
            else:
                for section in sections:
                    status = "Active" if section["is_active"] else "Inactive"
                    print(f"- {section['section_name']} [{status}]")
            press_enter()

        elif choice == "0":
            return
        else:
            print_error("Invalid Choice.")


def _view_available_tables():
    print("=" * 50)
    print("          AVAILABLE TABLES")
    print("=" * 50)

    tables = get_available_restaurant_tables()

    if not tables:
        print("No Available Tables Found.")
        press_enter()
        return

    for table in tables:
        print(
            f"Table : {table['table_number']} | "
            f"Capacity : {table['table_capacity']} Persons | "
            f"Section/Area : {table['table_section']} | "
            f"Status : Available"
        )

    print("=" * 50)
    press_enter()


def _view_reserved_tables():
    print("=" * 50)
    print("          RESERVED TABLES")
    print("=" * 50)

    tables = get_reserved_restaurant_tables()

    if not tables:
        print("No Reserved Tables Found.")
        press_enter()
        return

    for table in tables:
        print("-" * 50)
        print(f"Table        : {table['table_number']}")
        print(f"Capacity     : {table['table_capacity']} Persons")
        print(f"Section/Area : {table['table_section']}")
        print(f"Booking ID   : {table['booking_id']}")
        print(f"Customer     : {table['customer_name']}")
        print(f"Mobile       : {table['customer_mobile']}")
        print(f"Persons      : {table['persons']}")
        print(f"Booking Date : {table['booking_date']}")
        print(f"Booking Time : {table['booking_time']}")
        print("Status       : Reserved")

    print("=" * 50)
    press_enter()


def _find_available_tables_by_capacity():
    print("=" * 50)
    print("      AVAILABLE TABLES BY CAPACITY")
    print("=" * 50)

    while True:
        capacity_input = input("Enter Minimum Capacity (0 = Back) : ").strip()

        if capacity_input == "0":
            return

        try:
            minimum_capacity = int(capacity_input)
            if minimum_capacity <= 0:
                raise ValueError
            break
        except ValueError:
            print_error("Capacity must be a whole number greater than 0.")

    try:
        tables = get_available_restaurant_tables(min_capacity=minimum_capacity)
    except ValueError as e:
        print_error(str(e))
        press_enter()
        return

    print("\nAvailable Tables")
    print("-" * 50)

    if not tables:
        print(f"No Available Table Found for {minimum_capacity}+ Persons.")
    else:
        for table in tables:
            print(
                f"Table : {table['table_number']} | "
                f"Capacity : {table['table_capacity']} Persons | "
                f"Section/Area : {table['table_section']} | "
                f"Status : Available"
            )

    print("=" * 50)
    press_enter()


def _book_table():
    print("=" * 50)
    print("          TABLE BOOKING")
    print("=" * 50)

    print("\nAvailable Tables\n")

    tables = get_available_restaurant_tables()

    if not tables:
        print("No Available Tables Found.")
        press_enter()
        return

    for table in tables:
        print(
            f"Table : {table['table_number']} | "
            f"Capacity : {table['table_capacity']} Persons | "
            f"Section/Area : {table['table_section']} | "
            f"Status : Available"
        )

    print("-" * 50)

    table_number = input("Enter Table Number (0 = Back) : ").strip().upper()
    if table_number == "0":
        return

    table = get_table_by_number(table_number)
    if table is None:
        print_error("Invalid Table Number.")
        press_enter()
        return

    if not check_table_available(table_number):
        print_error("Table Already Booked.")
        press_enter()
        return

    customer_id = input("Enter Customer ID (0 = Back) : ").strip().upper()
    if customer_id == "0":
        return

    from database.customer_db import get_customer_by_id, validate_guest_hotel_relationship
    try:
        customer = get_customer_by_id(customer_id)
        if customer is None:
            raise ValueError("Customer ID not found.")
        validate_guest_hotel_relationship(customer_id)
    except Exception as e:
        print_error(str(e))
        press_enter()
        return

    customer_name = customer["customer_name"]
    customer_mobile = customer["customer_mobile"] or ""

    print(f"Customer Name : {customer_name}")
    print(f"Mobile        : {customer_mobile or 'Not Available'}")

    while True:
        try:
            persons = int(input("Enter Number Of Persons : "))
            if persons <= 0:
                print_error("Persons Must Be Greater Than 0.")
                continue
            if persons > table["table_capacity"]:
                print_error(f"Maximum Capacity Is {table['table_capacity']} Persons.")
                continue
            break
        except ValueError:
            print_error("Enter Numbers Only.")

    booking_time = current_datetime_object()
    booking_id = generate_order_id()

    create_table_booking(
        booking_id, booking_time, customer_id, customer_name, customer_mobile,
        table_number, persons
    )

    print("\n" + "=" * 50)
    print("Table Booking Successful!")
    print("=" * 50)
    print(f"Booking ID : {booking_id}")
    print(f"Customer   : {customer_name}")
    print(f"Table No   : {table_number}")
    print(f"Persons    : {persons}")
    print("=" * 50)
    input("\nPress Enter To Return...")



def _view_table_assignments():
    print("=" * 70)
    print("                 ACTIVE TABLE ASSIGNMENTS")
    print("=" * 70)

    assignments = get_active_table_assignments()
    if not assignments:
        print("No active table assignments found.")
        press_enter()
        return

    for assignment in assignments:
        print(
            f"Table : {assignment['table_number']} | "
            f"Type : {assignment['assignment_type']} | "
            f"Reference : {assignment['reference_id']}"
        )
        print(f"Customer ID : {assignment['customer_id'] or '-'}")
        print(f"Capacity : {assignment['table_capacity']} Persons")
        print(f"Section/Area : {assignment['table_section']}")
        print(f"Status : {assignment['table_status']}")
        print(f"Assigned At : {assignment['assigned_at']}")
        print("-" * 70)

    press_enter()



def _view_table_history():
    print("=" * 70)
    print("                 TABLE HISTORY")
    print("=" * 70)

    table_number = input("Enter Table Number (0 = All Tables) : ").strip().upper()
    if table_number == "0":
        table_number = None

    try:
        history = get_table_history(table_number=table_number)
    except Exception as e:
        print_error(f"Unable to load table history: {e}")
        press_enter()
        return

    if not history:
        print("No Table History Found.")
        press_enter()
        return

    for item in history:
        print("-" * 70)
        print(f"Table        : {item['table_number']}")
        print(f"Event Type   : {item['event_type']}")
        print(f"Reference ID : {item['reference_id']}")
        print(f"Customer ID  : {item['customer_id'] or '-'}")
        print(f"Customer     : {item['customer_name'] or '-'}")
        print(f"Capacity     : {item['table_capacity'] or '-'} Persons")
        print(f"Section/Area : {item['table_section'] or '-'}")
        print(f"Started At   : {item['event_start']}")
        print(f"Released At  : {item['event_end'] or '-'}")
        print(f"Status       : {item['history_status']}")

    print("=" * 70)
    press_enter()


def _reassign_booking_table():
    print("=" * 70)
    print("                 REASSIGN BOOKING TABLE")
    print("=" * 70)

    booking_id = input("Enter Booking ID (0 = Back) : ").strip().upper()
    if booking_id == "0":
        return

    new_table_number = input("Enter New Available Table Number : ").strip().upper()
    if new_table_number == "0":
        return

    try:
        old_table, new_table = reassign_table_booking(
            booking_id,
            new_table_number
        )
        print("\nTable Reassignment Successful!")
        print(f"Booking ID : {booking_id}")
        print(f"Old Table  : {old_table}")
        print(f"New Table  : {new_table}")
        print("New Status : Reserved")
    except Exception as e:
        print_error(f"Unable to reassign table: {e}")

    press_enter()


def _merge_tables():
    print("=" * 70)
    print("                    MERGE TABLES")
    print("=" * 70)
    print("Foundation only: this records a table group.")
    print("Only Available tables can be merged.")
    print("Enter table numbers separated by commas (minimum 2).")
    print("Example: T1,T2")
    print()

    raw = input("Enter Table Numbers (0 = Back) : ").strip()
    if raw == "0":
        return

    table_numbers = [item.strip().upper() for item in raw.split(",") if item.strip()]

    try:
        result = merge_restaurant_tables(table_numbers)
        print("\n" + "=" * 70)
        print("TABLE MERGE CREATED SUCCESSFULLY!")
        print("=" * 70)
        print(f"Merge Code   : {result['merge_code']}")
        print(f"Primary Table: {result['primary_table_number']}")
        print(f"Tables       : {', '.join(result['table_numbers'])}")
        print(f"Table Count  : {result['table_count']}")
        print("Operational table status was not changed.")
    except Exception as e:
        print_error(f"Unable to merge tables: {e}")

    press_enter()


def _view_active_table_merges():
    print("=" * 70)
    print("                 ACTIVE TABLE MERGES")
    print("=" * 70)

    try:
        merges = get_active_table_merges()
    except Exception as e:
        print_error(f"Unable to load table merges: {e}")
        press_enter()
        return

    if not merges:
        print("No Active Table Merges Found.")
        press_enter()
        return

    for merge in merges:
        print("-" * 70)
        print(f"Merge Code   : {merge['merge_code']}")
        print(f"Primary Table: {merge['primary_table_number']}")
        print(f"Tables       : {merge['table_numbers']}")
        print(f"Table Count  : {merge['table_count']}")
        print(f"Created At   : {merge['created_at']}")

    print("=" * 70)
    press_enter()


def _release_table_merge():
    print("=" * 70)
    print("                 RELEASE TABLE MERGE")
    print("=" * 70)

    merge_code = input("Enter Merge Code (0 = Back) : ").strip().upper()
    if merge_code == "0":
        return

    try:
        release_table_merge(merge_code)
        print("\nTable Merge Released Successfully!")
        print("Merge history has been preserved.")
    except Exception as e:
        print_error(f"Unable to release table merge: {e}")

    press_enter()


def _split_table_merge():
    print("=" * 70)
    print("                 SPLIT TABLE MERGE")
    print("=" * 70)
    print("This safely closes the merge relationship and restores each table")
    print("as an independent table without deleting booking/order/assignment data.")
    print()

    merge_code = input("Enter Merge Code (0 = Back) : ").strip().upper()
    if merge_code == "0":
        return

    try:
        result = split_table_merge(merge_code)
        print("\nTable Merge Split Successfully!")
        print(f"Merge Code          : {result['merge_code']}")
        print(f"Tables Restored     : {', '.join(result['table_numbers'])}")
        print(f"Assignments Preserved: {result['restored_assignments']}")
        print("Booking/Order data  : Preserved")
        print("Table status        : Restored consistently")
    except Exception as e:
        print_error(f"Unable to split table merge: {e}")

    press_enter()


def _view_table_cleaning_tasks():
    print("=" * 70)
    print("                 TABLE CLEANING TASKS")
    print("=" * 70)
    tasks = get_table_cleaning_tasks()
    if not tasks:
        print("No active table cleaning tasks.")
    else:
        for task in tasks:
            print("-" * 70)
            print(f"Table Number : {task['table_number']}")
            print(f"Capacity     : {task['table_capacity']} Persons")
            print(f"Section/Area : {task['table_section']}")
            print(f"Status       : {task['table_status']}")
            print(f"Reason       : {task['cleaning_reason'] or 'Not specified'}")
            print(f"Started At   : {task['cleaning_started_at'] or '-'}")
            print(f"Completed At : {task['cleaning_completed_at'] or '-'}")
    print("=" * 70)
    press_enter()


def _start_table_cleaning():
    print("=" * 70)
    print("                 START TABLE CLEANING")
    print("=" * 70)
    table_number = input("Enter Table Number (0 = Back) : ").strip().upper()
    if table_number == "0":
        return
    try:
        start_table_cleaning(table_number)
        print(f"\nCleaning started for Table {table_number}.")
    except Exception as e:
        print_error(f"Unable to start table cleaning: {e}")
    press_enter()


def _complete_table_cleaning():
    print("=" * 70)
    print("                COMPLETE TABLE CLEANING")
    print("=" * 70)
    table_number = input("Enter Table Number (0 = Back) : ").strip().upper()
    if table_number == "0":
        return
    try:
        complete_table_cleaning(table_number)
        print(f"\nCleaning completed for Table {table_number}.")
        print("Table is now Available.")
    except Exception as e:
        print_error(f"Unable to complete table cleaning: {e}")
    press_enter()


def _table_cleaning_management():
    while True:
        print("=" * 60)
        print("             TABLE CLEANING MANAGEMENT")
        print("=" * 60)
        print("1. View Cleaning Tasks")
        print("2. Start Cleaning")
        print("3. Complete Cleaning")
        print("0. Back")
        print("-" * 60)
        choice = input("Enter Your Choice : ").strip()
        if choice == "1":
            _view_table_cleaning_tasks()
        elif choice == "2":
            _start_table_cleaning()
        elif choice == "3":
            _complete_table_cleaning()
        elif choice == "0":
            return
        else:
            print_error("Invalid Choice.")


def table_booking():
    while True:
        print("=" * 50)
        print("          TABLE MANAGEMENT")
        print("=" * 50)
        print("1. Book Table")
        print("2. Create Table")
        print("3. View Tables")
        print("4. Update Table Capacity")
        print("5. Update Table Section / Area")
        print("6. Manage Sections / Areas")
        print("7. View Available Tables")
        print("8. Find Available Tables by Capacity")
        print("9. View Reserved Tables")
        print("10. View Active Table Assignments")
        print("11. Reassign Booking Table")
        print("12. View Table History")
        print("13. Merge Tables (Foundation)")
        print("14. View Active Table Merges")
        print("15. Release Table Merge")
        print("16. Split Table Merge (Foundation)")
        print("17. Table Cleaning Management")
        print("0. Back")
        print("-" * 50)

        choice = input("Enter Your Choice : ").strip()

        if choice == "1":
            _book_table()
        elif choice == "2":
            _create_table()
        elif choice == "3":
            tables = get_all_tables()
            print("\n" + "=" * 50)
            print("          ALL RESTAURANT TABLES")
            print("=" * 50)
            for table in tables:
                print(
                    f"Table : {table['table_number']} | "
                    f"Capacity : {table['table_capacity']} Persons | "
                    f"Section/Area : {table['table_section']} | "
                    f"Status : {table['table_status']}"
                )
            print("=" * 50)
            press_enter()
        elif choice == "4":
            _update_table_capacity()
        elif choice == "5":
            _update_table_section()
        elif choice == "6":
            _manage_table_sections()
        elif choice == "7":
            _view_available_tables()
        elif choice == "8":
            _find_available_tables_by_capacity()
        elif choice == "9":
            _view_reserved_tables()
        elif choice == "10":
            _view_table_assignments()
        elif choice == "11":
            _reassign_booking_table()
        elif choice == "12":
            _view_table_history()
        elif choice == "13":
            _merge_tables()
        elif choice == "14":
            _view_active_table_merges()
        elif choice == "15":
            _release_table_merge()
        elif choice == "16":
            _split_table_merge()
        elif choice == "17":
            _table_cleaning_management()
        elif choice == "0":
            return
        else:
            print_error("Invalid Choice.")
