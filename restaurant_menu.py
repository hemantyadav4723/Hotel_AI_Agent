from database.restaurant_menu_db import (
    add_menu_category,
    add_menu_item,
    deactivate_menu_item,
    get_menu_categories,
    get_menu_items,
    get_menu_item,
    search_menu_items,
    set_menu_item_availability,
    update_menu_item,
)

from utils.display import print_header, print_footer, print_success, press_enter
from utils.validators import validate_menu_choice, validate_positive_number, validate_yes_no


def _print_items(items):
    print_header("RESTAURANT MENU ITEMS")

    if not items:
        print("No menu items found.")
        print_footer()
        return

    current_category = None
    for item in items:
        if item["category_name"] != current_category:
            current_category = item["category_name"]
            print(f"\n[{current_category}]")

        status = "Available" if item["is_available"] else "Not Available"
        print(
            f"{item['item_id']} | {item['item_name']} | "
            f"₹{item['price']:.2f} | {status}"
        )
        if item["description"]:
            print(f"  {item['description']}")

    print_footer()


def _select_category(active_only=True):
    categories = get_menu_categories(active_only=active_only)
    if not categories:
        print("No menu categories found.")
        return None

    print_header("MENU CATEGORIES")
    for index, category in enumerate(categories, 1):
        status = "Active" if category["is_active"] else "Inactive"
        print(f"{index}. {category['category_id']} - {category['category_name']} ({status})")
    print_footer()

    choice = validate_menu_choice(
        "Select Category Number : ",
        [str(index) for index in range(1, len(categories) + 1)]
    )
    return categories[int(choice) - 1]


def add_category_menu():
    print_header("ADD MENU CATEGORY")
    name = input("Enter Category Name : ").strip()
    try:
        category_id = add_menu_category(name)
        print_success(f"Category Added Successfully. ID: {category_id}")
    except ValueError as exc:
        print(f"Error: {exc}")
    print_footer()
    press_enter()


def add_item_menu():
    category = _select_category()
    if category is None:
        press_enter()
        return

    print_header("ADD MENU ITEM")
    name = input("Enter Item Name : ").strip()
    price = validate_positive_number("Enter Price : ")
    description = input("Enter Description (optional) : ").strip()

    try:
        item_id = add_menu_item(
            name,
            price,
            category["category_id"],
            description
        )
        print_success(f"Menu Item Added Successfully. ID: {item_id}")
    except ValueError as exc:
        print(f"Error: {exc}")
    print_footer()
    press_enter()


def update_item_menu():
    items = get_menu_items()
    _print_items(items)
    if not items:
        press_enter()
        return

    item_id = input("Enter Menu Item ID : ").strip().upper()
    item = get_menu_item(item_id)
    if item is None:
        print("Menu item not found.")
        press_enter()
        return

    category = _select_category()
    if category is None:
        press_enter()
        return

    print_header("UPDATE MENU ITEM")
    name = input(f"Enter Item Name [{item['item_name']}] : ").strip() or item["item_name"]
    price_input = input(f"Enter Price [{item['price']}] : ").strip()
    price = item["price"] if not price_input else validate_positive_number("Enter Price : ")
    description = input(
        f"Enter Description [{item['description'] or ''}] : "
    ).strip()
    if not description:
        description = item["description"] or ""

    try:
        update_menu_item(
            item_id,
            name,
            price,
            category["category_id"],
            description
        )
        print_success("Menu Item Updated Successfully.")
    except ValueError as exc:
        print(f"Error: {exc}")
    print_footer()
    press_enter()


def availability_menu():
    items = get_menu_items()
    _print_items(items)
    if not items:
        press_enter()
        return

    item_id = input("Enter Menu Item ID : ").strip().upper()
    item = get_menu_item(item_id)
    if item is None:
        print("Menu item not found.")
        press_enter()
        return

    status = validate_yes_no("Make Item Available? (Yes/No): ")
    try:
        set_menu_item_availability(item_id, status == "Yes")
        print_success("Menu Item Availability Updated Successfully.")
    except ValueError as exc:
        print(f"Error: {exc}")
    press_enter()


def search_menu():
    print_header("SEARCH / FILTER MENU")
    search_text = input("Enter Item / Category / Description (optional) : ").strip()
    available_input = input("Availability (A=Available, N=Not Available, Enter=All) : ").strip().upper()

    available = None
    if available_input == "A":
        available = True
    elif available_input == "N":
        available = False

    category_id = None
    if input("Filter by Category? (Yes/No): ").strip().lower() in {"yes", "y"}:
        category = _select_category()
        if category:
            category_id = category["category_id"]

    items = search_menu_items(
        search_text,
        category_id=category_id,
        available=available
    )
    _print_items(items)
    print(f"Results Found: {len(items)}")
    press_enter()


def deactivate_item_menu():
    items = get_menu_items()
    _print_items(items)
    if not items:
        press_enter()
        return

    item_id = input("Enter Menu Item ID : ").strip().upper()
    item = get_menu_item(item_id)
    if item is None:
        print("Menu item not found.")
        press_enter()
        return

    confirm = validate_yes_no("Deactivate this item? (Yes/No): ")
    if confirm == "Yes":
        try:
            deactivate_menu_item(item_id)
            print_success("Menu Item Deactivated Successfully.")
        except ValueError as exc:
            print(f"Error: {exc}")
    press_enter()


def restaurant_menu_management():
    while True:
        print_header("RESTAURANT MENU MANAGEMENT")
        print("1. View Menu")
        print("2. View Categories")
        print("3. Add Category")
        print("4. Add Menu Item")
        print("5. Update Menu Item")
        print("6. Change Item Availability")
        print("7. Search / Filter Menu")
        print("8. Deactivate Menu Item")
        print("9. Back")
        print_footer()

        choice = validate_menu_choice(
            "Enter Choice : ",
            [str(index) for index in range(1, 10)]
        )

        if choice == "1":
            _print_items(get_menu_items())
            press_enter()
        elif choice == "2":
            categories = get_menu_categories()
            print_header("RESTAURANT MENU CATEGORIES")
            if categories:
                for category in categories:
                    status = "Active" if category["is_active"] else "Inactive"
                    print(f"{category['category_id']} | {category['category_name']} | {status}")
            else:
                print("No categories found.")
            print_footer()
            press_enter()
        elif choice == "3":
            add_category_menu()
        elif choice == "4":
            add_item_menu()
        elif choice == "5":
            update_item_menu()
        elif choice == "6":
            availability_menu()
        elif choice == "7":
            search_menu()
        elif choice == "8":
            deactivate_item_menu()
        else:
            break
