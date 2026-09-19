from utils.display import (
    print_header,
    print_footer,
    print_separator,
    print_success,
    press_enter
)

from utils.validators import (
    validate_menu_choice,
    validate_mobile,
    validate_optional_mobile,
    validate_address,
    validate_location,
    validate_pincode,
    validate_email,
    validate_name,
    validate_price,
    validate_quantity,
    validate_non_negative_quantity,
    validate_non_empty,
    validate_optional_price,
    validate_optional_date,
    validate_optional_gstin,
    validate_tax_type,
    validate_tax_status
)

from database.permission_db import require_current_user_permission

from database.inventory_db import (
    save_item,
    view_items,
    search_item,
    update_item,
    deactivate_item,
    activate_item,
    delete_item,
    stock_in,
    stock_out,
    stock_adjustment,
    damaged_stock,
    low_stock_alert,
    reorder_level_management,
    expiry_foundation,
    update_expiry_date,
    stock_history,
    get_active_item_options,
    inventory_valuation,
    restaurant_order_inventory_integration
)

from database.inventory_category_db import (
    save_category,
    view_categories,
    search_category,
    update_category,
    deactivate_category,
    activate_category,
    delete_category,
    get_category_options
)

from database.inventory_unit_db import (
    save_unit,
    view_units,
    search_unit,
    update_unit,
    deactivate_unit,
    activate_unit,
    delete_unit,
    get_unit_options
)

from database.inventory_batch_db import batch_lot_management
from database.purchase_order_db import purchase_order_management


from database.supplier_db import (
    save_supplier,
    view_supplier,
    search_supplier,
    update_supplier,
    delete_supplier,
    supplier_exists,
    deactivate_supplier,
    activate_supplier
)


def inventory_management():

    try:
        require_current_user_permission("Inventory", "View")
    except PermissionError as exc:
        print(f"Login/Permission Required: {exc}")
        return

    while True:

        print_header("INVENTORY MANAGEMENT")

        print("ITEM MASTER")
        print("1. Add Item")
        print("2. View Items")
        print("3. Search Item")
        print("4. Update Item")
        print("5. Deactivate Item")
        print("6. Activate Item")
        print("7. Delete Item")
        print()
        print("STOCK OPERATIONS")
        print("8. Stock In")
        print("9. Stock Out")
        print("10. Stock Adjustment")
        print("11. Damaged Stock")
        print("12. Low Stock Alert")
        print("13. Reorder Level Management")
        print("14. Stock History")
        print("15. Inventory Valuation")
        print()
        print("MASTER & TRACEABILITY")
        print("16. Category Management")
        print("17. Unit Management")
        print()
        print("SUPPLIER & PROCUREMENT")
        print("18. Supplier & Procurement Management")
        print()
        print("INVENTORY TRACEABILITY")
        print("19. Expiry Foundation")
        print("20. Batch / Lot Foundation")
        print()
        print("CROSS-MODULE")
        print("21. Restaurant Order Stock Integration")
        print()
        print("22. Back")

        choice = validate_menu_choice(
            "Enter Your Choice : ",
            [
                "1", "2", "3", "4", "5", "6", "7",
                "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22"
            ]
        )

        print_separator()
        print_footer()

        if choice == "1":
            try:
                item_id = validate_non_empty(
                    "Enter Item ID : "
                ).strip().upper()
                item_name = validate_name("Enter Item Name : ")

                category_options = get_category_options()
                if not category_options:
                    print("No Inventory Categories Found.")
                    print("Please add an Inventory Category first.")
                    press_enter()
                    continue

                print("Available Inventory Categories:")
                for category_option in category_options:
                    print(
                        f"{category_option['category_id']} - "
                        f"{category_option['category_name']}"
                    )

                category_id = validate_non_empty(
                    "Enter Category ID : "
                ).strip().upper()

                unit_options = get_unit_options()
                if not unit_options:
                    print("No Inventory Units Found.")
                    print("Please add an Inventory Unit first.")
                    press_enter()
                    continue

                print("Available Inventory Units:")
                for unit_option in unit_options:
                    print(
                        f"{unit_option['unit_id']} - "
                        f"{unit_option['unit_name']} "
                        f"[{unit_option['unit_symbol']}]"
                    )

                unit_id = validate_non_empty(
                    "Enter Unit ID : "
                ).strip().upper()

                opening_quantity = validate_non_negative_quantity(
                    "Enter Opening Quantity : "
                )
                cost_price = validate_price("Enter Cost Price : ")
                selling_price = validate_price("Enter Selling Price : ")
                reorder_level = validate_non_negative_quantity(
                    "Enter Reorder Level : "
                )
                expiry_date = validate_optional_date(
                    "Expiry Date (optional, DD-MM-YYYY) : "
                )

                supplier_id = input(
                    "Enter Supplier ID (optional) : "
                ).strip().upper()

                if supplier_id and not supplier_exists(supplier_id):
                    print("Supplier Not Found.")
                    press_enter()
                    continue

                save_item(
                    item_id,
                    item_name,
                    category_id,
                    unit_id,
                    opening_quantity,
                    cost_price,
                    selling_price,
                    reorder_level,
                    supplier_id or None,
                    expiry_date
                )

                print_success("Item Added Successfully.")

            except ValueError as exc:
                print(f"Error: {exc}")

        elif choice == "2":
            view_items()

        elif choice == "3":
            search_item()

        elif choice == "4":
            try:
                update_item()
            except ValueError as exc:
                print(f"Error: {exc}")

        elif choice == "5":
            deactivate_item()

        elif choice == "6":
            activate_item()

        elif choice == "7":
            delete_item()

        elif choice == "8":
            item_options = get_active_item_options()

            if not item_options:
                print("No Active Inventory Items Found.")
                print("Please add an active Inventory Item first.")
                continue

            print("Available Active Inventory Items:")
            for item_option in item_options:
                supplier_label = item_option["supplier_id"] or "Not Assigned"
                print(
                    f"{item_option['item_id']} - "
                    f"{item_option['item_name']} | "
                    f"Stock: {item_option['quantity']} {item_option['unit']} | "
                    f"Cost: {float(item_option['cost_price'] or 0):.2f} | "
                    f"Supplier: {supplier_label}"
                )

            try:
                item_id = validate_non_empty(
                    "Enter Item ID : "
                ).strip().upper()

                selected_item = next(
                    (
                        item for item in item_options
                        if item["item_id"] == item_id
                    ),
                    None
                )

                if selected_item is None:
                    raise ValueError(
                        "Invalid or inactive Inventory Item."
                    )

                quantity = validate_quantity(
                    f"Enter Quantity ({selected_item['unit']}) : "
                )

                unit_cost = validate_optional_price(
                    f"Unit Cost "
                    f"({float(selected_item['cost_price'] or 0):.2f}, "
                    f"blank = current) : "
                )

                supplier_id = input(
                    "Supplier ID "
                    f"({selected_item['supplier_id'] or 'Not Assigned'}, "
                    f"blank = current) : "
                ).strip().upper()

                reference_no = input(
                    "Reference / Invoice No (optional) : "
                ).strip()

                reason = validate_non_empty(
                    "Stock In Reason : "
                )

                batch_no = input("Batch No (optional) : ").strip()
                lot_no = input("Lot No (optional) : ").strip()
                batch_expiry_date = validate_optional_date(
                    "Batch Expiry Date (optional, DD-MM-YYYY) : "
                )

                stock_in(
                    item_id,
                    quantity,
                    unit_cost=unit_cost,
                    supplier_id=supplier_id or None,
                    reference_no=reference_no or None,
                    reason=reason,
                    batch_no=batch_no or None,
                    lot_no=lot_no or None,
                    batch_expiry_date=batch_expiry_date
                )

            except ValueError as exc:
                print(f"Error: {exc}")

        elif choice == "9":
            item_options = get_active_item_options()

            if not item_options:
                print("No Active Inventory Items Found.")
                print("Please add an active Inventory Item first.")
                continue

            print("Available Active Inventory Items:")
            for item_option in item_options:
                print(
                    f"{item_option['item_id']} - "
                    f"{item_option['item_name']} | "
                    f"Stock: {item_option['quantity']} {item_option['unit']} | "
                    f"Cost: {float(item_option['cost_price'] or 0):.2f}"
                )

            try:
                item_id = validate_non_empty(
                    "Enter Item ID : "
                ).strip().upper()

                selected_item = next(
                    (
                        item for item in item_options
                        if item["item_id"] == item_id
                    ),
                    None
                )

                if selected_item is None:
                    raise ValueError(
                        "Invalid or inactive Inventory Item."
                    )

                available_quantity = int(selected_item["quantity"] or 0)

                if available_quantity <= 0:
                    raise ValueError(
                        "This item has no available stock for Stock Out."
                    )

                quantity = validate_quantity(
                    f"Enter Quantity "
                    f"(Available: {available_quantity} {selected_item['unit']}) : "
                )

                if quantity > available_quantity:
                    raise ValueError(
                        f"Insufficient Stock. Available: "
                        f"{available_quantity} {selected_item['unit']}."
                    )

                reference_no = input(
                    "Reference / Issue No (optional) : "
                ).strip()

                reason = validate_non_empty(
                    "Stock Out Reason : "
                )

                stock_out(
                    item_id,
                    quantity,
                    reference_no=reference_no or None,
                    reason=reason
                )

            except ValueError as exc:
                print(f"Error: {exc}")

        elif choice == "10":
            item_options = get_active_item_options()

            if not item_options:
                print("No Active Inventory Items Found.")
                print("Please add an active Inventory Item first.")
                continue

            print("Available Active Inventory Items:")
            for item_option in item_options:
                print(
                    f"{item_option['item_id']} - "
                    f"{item_option['item_name']} | "
                    f"Stock: {item_option['quantity']} {item_option['unit']} | "
                    f"Cost: {float(item_option['cost_price'] or 0):.2f}"
                )

            try:
                item_id = validate_non_empty("Enter Item ID : ").strip().upper()
                selected_item = next(
                    (item for item in item_options if item["item_id"] == item_id),
                    None
                )
                if selected_item is None:
                    raise ValueError("Invalid or inactive Inventory Item.")

                print("1. Increase Stock")
                print("2. Decrease Stock")
                adjustment_choice = validate_menu_choice(
                    "Enter Adjustment Type : ", ["1", "2"]
                )
                adjustment_type = "INCREASE" if adjustment_choice == "1" else "DECREASE"

                available = int(selected_item["quantity"] or 0)
                quantity = validate_quantity(
                    f"Enter Adjustment Quantity "
                    f"(Available: {available} {selected_item['unit']}) : "
                )

                if adjustment_type == "DECREASE" and quantity > available:
                    raise ValueError(
                        f"Adjustment would create negative stock. Available: "
                        f"{available} {selected_item['unit']}."
                    )

                reason = validate_non_empty("Adjustment Reason : ")
                reference_no = input(
                    "Reference / Adjustment No (optional) : "
                ).strip()

                stock_adjustment(
                    item_id,
                    adjustment_type,
                    quantity,
                    reason,
                    reference_no=reference_no or None
                )

            except ValueError as exc:
                print(f"Error: {exc}")

        elif choice == "11":
            item_options = get_active_item_options()

            if not item_options:
                print("No Active Inventory Items Found.")
                print("Please add an active Inventory Item first.")
                continue

            print("Available Active Inventory Items:")
            for item_option in item_options:
                print(
                    f"{item_option['item_id']} - "
                    f"{item_option['item_name']} | "
                    f"Usable Stock: {item_option['quantity']} {item_option['unit']} | "
                    f"Damaged: {item_option['damaged_quantity']} {item_option['unit']}"
                )

            try:
                item_id = validate_non_empty("Enter Item ID : ").strip().upper()
                selected_item = next(
                    (item for item in item_options if item["item_id"] == item_id),
                    None
                )
                if selected_item is None:
                    raise ValueError("Invalid or inactive Inventory Item.")

                available = int(selected_item["quantity"] or 0)
                if available <= 0:
                    raise ValueError("This item has no usable stock available for damage recording.")

                quantity = validate_quantity(
                    f"Enter Damaged Quantity "
                    f"(Available: {available} {selected_item['unit']}) : "
                )
                if quantity > available:
                    raise ValueError(
                        f"Damaged quantity cannot exceed available stock. "
                        f"Available: {available} {selected_item['unit']}."
                    )

                reason = validate_non_empty("Damage Reason : ")
                reference_no = input(
                    "Reference / Damage Report No (optional) : "
                ).strip()

                damaged_stock(
                    item_id,
                    quantity,
                    reference_no=reference_no or None,
                    reason=reason
                )

            except ValueError as exc:
                print(f"Error: {exc}")

        elif choice == "12":
            low_stock_alert()

        elif choice == "13":
            try:
                reorder_level_management()
            except ValueError as exc:
                print(f"Error: {exc}")

        elif choice == "14":
            stock_history()

        elif choice == "19":
            purchase_order_management()

        elif choice == "20":
            while True:
                print_header("EXPIRY FOUNDATION")
                print("1. View Expiry Status")
                print("2. Update Expiry Date")
                print("3. Back")

                expiry_choice = validate_menu_choice(
                    "Enter Your Choice : ",
                    ["1", "2", "3"]
                )

                print_separator()
                print_footer()

                if expiry_choice == "1":
                    expiry_foundation()
                elif expiry_choice == "2":
                    try:
                        update_expiry_date()
                    except ValueError as exc:
                        print(f"Error: {exc}")
                elif expiry_choice == "3":
                    break

        elif choice == "15":
            inventory_valuation()

        elif choice == "16":
            while True:

                print_header("INVENTORY CATEGORY MANAGEMENT")

                print("1. Add Category")
                print("2. View Categories")
                print("3. Search Category")
                print("4. Update Category")
                print("5. Deactivate Category")
                print("6. Activate Category")
                print("7. Delete Category")
                print("8. Back")

                category_choice = validate_menu_choice(
                    "Enter Your Choice : ",
                    ["1", "2", "3", "4", "5", "6", "7", "8"]
                )

                print_separator()
                print_footer()

                if category_choice == "1":
                    try:
                        category_id = validate_non_empty(
                            "Enter Category ID : "
                        ).strip().upper()
                        category_name = validate_name(
                            "Enter Category Name : "
                        )
                        save_category(category_id, category_name)
                        print_success("Category Added Successfully.")
                    except ValueError as exc:
                        print(f"Error: {exc}")

                elif category_choice == "2":
                    view_categories()

                elif category_choice == "3":
                    search_category()

                elif category_choice == "4":
                    update_category()

                elif category_choice == "5":
                    deactivate_category()

                elif category_choice == "6":
                    activate_category()

                elif category_choice == "7":
                    delete_category()

                elif category_choice == "8":
                    break

                press_enter()

        elif choice == "17":
            while True:

                print_header("INVENTORY UNIT MANAGEMENT")

                print("1. Add Unit")
                print("2. View Units")
                print("3. Search Unit")
                print("4. Update Unit")
                print("5. Deactivate Unit")
                print("6. Activate Unit")
                print("7. Delete Unit")
                print("8. Back")

                unit_choice = validate_menu_choice(
                    "Enter Your Choice : ",
                    ["1", "2", "3", "4", "5", "6", "7", "8"]
                )

                print_separator()
                print_footer()

                if unit_choice == "1":
                    try:
                        unit_id = validate_non_empty(
                            "Enter Unit ID : "
                        ).strip().upper()
                        unit_name = validate_non_empty(
                            "Enter Unit Name : "
                        )
                        unit_symbol = validate_non_empty(
                            "Enter Unit Symbol : "
                        ).strip().upper()
                        save_unit(unit_id, unit_name, unit_symbol)
                        print_success("Unit Added Successfully.")
                    except ValueError as exc:
                        print(f"Error: {exc}")

                elif unit_choice == "2":
                    view_units()

                elif unit_choice == "3":
                    search_unit()

                elif unit_choice == "4":
                    update_unit()

                elif unit_choice == "5":
                    deactivate_unit()

                elif unit_choice == "6":
                    activate_unit()

                elif unit_choice == "7":
                    delete_unit()

                elif unit_choice == "8":
                    break

                press_enter()

        elif choice == "18":
            while True:
                print_header("SUPPLIER & PROCUREMENT MANAGEMENT")

                print("SUPPLIER")
                print("1. Supplier Management")
                print()
                print("PROCUREMENT")
                print("2. Purchase Order")
                print("3. Purchase Receiving")
                print("4. Purchase History")
                print("5. Payment Terms")
                print("6. Supplier Outstanding")
                print("7. Back")

                procurement_choice = validate_menu_choice(
                    "Enter Your Choice : ",
                    ["1", "2", "3", "4", "5", "6", "7"]
                )

                print_separator()
                print_footer()

                if procurement_choice == "1":
                    while True:
                        print_header("SUPPLIER MANAGEMENT")

                        print("1. Add Supplier")
                        print("2. View Supplier")
                        print("3. Search Supplier")
                        print("4. Update Supplier")
                        print("5. Delete Supplier")
                        print("6. Deactivate Supplier")
                        print("7. Activate Supplier")
                        print("8. Back")

                        supplier_choice = validate_menu_choice(
                            "Enter Choice : ",
                            ["1", "2", "3", "4", "5", "6", "7", "8"]
                        )

                        print_separator()
                        print_footer()

                        if supplier_choice == "1":
                            try:
                                supplier_id = validate_non_empty("Supplier ID : ").upper()
                                supplier_name = validate_name("Supplier Name : ")
                                supplier_type = validate_non_empty(
                                    "Supplier Type (e.g. Food, Grocery, Maintenance) : "
                                )
                                mobile = validate_mobile("Mobile : ")
                                contact_person = validate_name("Contact Person : ")
                                email = validate_email("Email : ")
                                alternate_mobile = validate_optional_mobile(
                                    "Alternate Mobile (optional) : "
                                )
                                address = validate_address("Address : ")
                                city = validate_location("City : ")
                                state = validate_location("State : ")
                                pincode = validate_pincode("PIN Code : ")
                                tax_type = validate_tax_type(
                                    "Tax Type (GST/VAT/TDS/Other/None) : "
                                )
                                tax_status = validate_tax_status("Tax Status : ")
                                gstin = validate_optional_gstin("GSTIN (optional) : ")
                                tax_registration_number = validate_non_empty(
                                    "Tax Registration No. (enter N/A if not applicable) : "
                                )

                                if tax_status in ["Registered", "Composition"] and not gstin:
                                    print_error(
                                        "GSTIN is required for Registered or Composition tax status."
                                    )
                                    press_enter()
                                    continue

                                save_supplier(
                                    supplier_id,
                                    supplier_name,
                                    mobile,
                                    supplier_type,
                                    contact_person,
                                    email,
                                    alternate_mobile,
                                    address,
                                    city,
                                    state,
                                    pincode,
                                    gstin,
                                    tax_registration_number,
                                    tax_type,
                                    tax_status
                                )
                                print_success("Supplier Added Successfully.")
                            except (ValueError, PermissionError) as exc:
                                print_error(str(exc))

                        elif supplier_choice == "2":
                            view_supplier()

                        elif supplier_choice == "3":
                            search_supplier()

                        elif supplier_choice == "4":
                            update_supplier()

                        elif supplier_choice == "5":
                            delete_supplier()

                        elif supplier_choice == "6":
                            deactivate_supplier()

                        elif supplier_choice == "7":
                            activate_supplier()

                        elif supplier_choice == "8":
                            break

                        press_enter()

                elif procurement_choice == "2":
                    purchase_order_management()

                elif procurement_choice == "3":
                    from database.purchase_receiving_db import purchase_receiving_management
                    purchase_receiving_management()

                elif procurement_choice == "4":
                    from database.purchase_history_db import purchase_history_management
                    purchase_history_management()

                elif procurement_choice == "5":
                    from database.supplier_payment_terms_db import supplier_payment_terms_management
                    supplier_payment_terms_management()

                elif procurement_choice == "6":
                    from database.supplier_outstanding_db import supplier_outstanding_management
                    supplier_outstanding_management()

                elif procurement_choice == "7":
                    break

        elif choice == "19":
            while True:
                print_header("EXPIRY FOUNDATION")
                print("1. View Expiry Status")
                print("2. Update Expiry Date")
                print("3. Back")

                expiry_choice = validate_menu_choice(
                    "Enter Your Choice : ",
                    ["1", "2", "3"]
                )

                print_separator()
                print_footer()

                if expiry_choice == "1":
                    expiry_foundation()
                elif expiry_choice == "2":
                    try:
                        update_expiry_date()
                    except ValueError as exc:
                        print(f"Error: {exc}")
                elif expiry_choice == "3":
                    break

                press_enter()

        elif choice == "20":
            batch_lot_management()

        elif choice == "21":
            try:
                restaurant_order_inventory_integration()
            except ValueError as exc:
                print_error(str(exc))

        elif choice == "22":
            break

        press_enter()
