from database.settings_db import (
    save_settings,
    view_settings,
    get_discount_rules,
    add_discount_rule,
    update_discount_rule,
    set_discount_rule_status
)

from utils.validators import (
    validate_menu_choice,
    validate_name,
    validate_mobile,
    validate_email,
    validate_non_empty
)

from utils.display import press_enter


def _read_amount(message, allow_blank=False):
    while True:
        raw = input(message).strip()

        if allow_blank and raw == "":
            return None

        try:
            value = round(float(raw), 2)
            if value < 0:
                raise ValueError
            return value
        except (ValueError, TypeError):
            print("Enter a valid non-negative amount.")


def _read_discount_type():
    while True:
        print("1. Percentage")
        print("2. Fixed Amount")

        choice = validate_menu_choice(
            "Select Discount Type : ",
            ["1", "2"]
        )

        if choice == "1":
            return "PERCENTAGE"
        return "FIXED"


def _view_discount_rules():
    print("=" * 80)
    print("                 AUTOMATIC DISCOUNT RULES")
    print("=" * 80)

    rules = get_discount_rules(include_inactive=True)

    if not rules:
        print("No discount rules configured.")
        return

    for rule in rules:
        max_amount = (
            "No Limit"
            if rule["max_amount"] is None
            else f"₹{float(rule['max_amount']):.2f}"
        )

        if rule["discount_type"] == "PERCENTAGE":
            discount_value = f"{float(rule['discount_value']):.2f}%"
        else:
            discount_value = f"₹{float(rule['discount_value']):.2f}"

        status = "Active" if rule["is_active"] else "Inactive"

        print(
            f"ID: {rule['discount_rule_id']} | "
            f"Name: {rule['rule_name']} | "
            f"Range: ₹{float(rule['min_amount']):.2f} - {max_amount} | "
            f"Discount: {discount_value} | "
            f"Status: {status}"
        )

    print("=" * 80)


def _add_discount_rule():
    print("=" * 60)
    print("              ADD DISCOUNT RULE")
    print("=" * 60)

    rule_name = validate_non_empty("Rule Name : ")
    min_amount = _read_amount("Minimum Order Amount : ₹")
    max_amount = _read_amount(
        "Maximum Order Amount (Enter = No Limit) : ₹",
        allow_blank=True
    )
    discount_type = _read_discount_type()

    if discount_type == "PERCENTAGE":
        while True:
            discount_value = _read_amount("Discount Percentage : ")
            if discount_value <= 100:
                break
            print("Percentage discount cannot exceed 100%.")
    else:
        discount_value = _read_amount("Fixed Discount Amount : ₹")

    add_discount_rule(
        rule_name,
        min_amount,
        max_amount,
        discount_type,
        discount_value
    )

    print("Discount Rule Added Successfully.")


def _update_discount_rule():
    _view_discount_rules()

    rule_id = validate_non_empty("Enter Discount Rule ID : ")

    rule_name = validate_non_empty("Rule Name : ")
    min_amount = _read_amount("Minimum Order Amount : ₹")
    max_amount = _read_amount(
        "Maximum Order Amount (Enter = No Limit) : ₹",
        allow_blank=True
    )
    discount_type = _read_discount_type()

    if discount_type == "PERCENTAGE":
        while True:
            discount_value = _read_amount("Discount Percentage : ")
            if discount_value <= 100:
                break
            print("Percentage discount cannot exceed 100%.")
    else:
        discount_value = _read_amount("Fixed Discount Amount : ₹")

    update_discount_rule(
        rule_id,
        rule_name,
        min_amount,
        max_amount,
        discount_type,
        discount_value
    )

    print("Discount Rule Updated Successfully.")


def _change_discount_rule_status(active):
    _view_discount_rules()
    rule_id = validate_non_empty("Enter Discount Rule ID : ")

    set_discount_rule_status(rule_id, active)

    if active:
        print("Discount Rule Activated Successfully.")
    else:
        print("Discount Rule Deactivated Successfully.")


def _discount_management():
    while True:
        print("=" * 60)
        print("            DISCOUNT MANAGEMENT")
        print("=" * 60)

        print("1. View Discount Rules")
        print("2. Add Discount Rule")
        print("3. Update Discount Rule")
        print("4. Deactivate Discount Rule")
        print("5. Activate Discount Rule")
        print("6. Back")

        choice = validate_menu_choice(
            "Enter Choice : ",
            ["1", "2", "3", "4", "5", "6"]
        )

        try:
            if choice == "1":
                _view_discount_rules()
            elif choice == "2":
                _add_discount_rule()
            elif choice == "3":
                _update_discount_rule()
            elif choice == "4":
                _change_discount_rule_status(False)
            elif choice == "5":
                _change_discount_rule_status(True)
            elif choice == "6":
                break
        except ValueError as error:
            print(f"Error: {error}")

        if choice != "6":
            press_enter()


def settings_management():

    while True:

        print("=" * 60)
        print("         SETTINGS")
        print("=" * 60)

        print("1. Update Hotel Settings")
        print("2. View Settings")
        print("3. Discount Management")
        print("4. Back")

        choice = validate_menu_choice(
            "Enter Choice : ",
            ["1", "2", "3", "4"]
        )

        if choice == "1":

            hotel_name = validate_name("Hotel Name : ")
            owner_name = validate_name("Owner Name : ")
            gst = validate_non_empty("GST Number : ")
            phone = validate_mobile("Phone : ")
            email = validate_email("Email : ")

            save_settings(
                hotel_name,
                owner_name,
                gst,
                phone,
                email
            )

        elif choice == "2":
            view_settings()

        elif choice == "3":
            _discount_management()

        elif choice == "4":
            break

        press_enter()
