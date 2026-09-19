from utils.error_logging import log_non_blocking_error
import json
from decimal import Decimal, ROUND_HALF_UP
from database.restaurant_menu_db import get_menu_items
from restaurant_menu import restaurant_menu_management

from billing import calculate_bill, print_final_bill

from utils.display import (
    print_header,
    print_footer,
    print_success,
    print_error,
    press_enter
)

from utils.validators import (
    validate_menu_choice,
    validate_positive_number,
    validate_yes_no,
    validate_name,
    validate_mobile,
)

from utils.date_time import (
    current_datetime_object,
    generate_order_id
)


from database.order_db import (
    save_order,
    get_orders,
    restaurant_order_history,
    update_order_status,
    record_order_payment,
    add_order_payment,
    settle_order_rounding,
    get_order_payment,
    get_order_payment_history,
    correct_order_payment,
    record_order_refund,
    cancel_restaurant_order,
    cancel_order_item,
    get_order_audit,
    ORDER_STATUSES,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    get_restaurant_sales_analytics,
    get_restaurant_operational_orders,
    restaurant_operational_summary,
    restaurant_security_integrity_report
)
from database.table_booking_db import (
    get_restaurant_tables,
    get_available_restaurant_tables,
    validate_restaurant_table,
    claim_restaurant_table,
    release_table
)
from database.hotel_information_db import get_hotel_information
from database.hotel_context import get_current_hotel_id
from database.settings_db import get_automatic_discount
from database.customer_db import (
    resolve_guest_for_booking,
    search_restaurant_guests,
    validate_guest_hotel_relationship
)


from database.inventory_db import (
    restaurant_order_inventory_integration
)



def _get_order_discount(subtotal):
    """
    Discount input rules:
    - Enter: use the configured automatic discount rule.
    - 0: no discount.
    - Positive amount: manual discount override.
    """
    hotel_id = get_current_hotel_id()
    automatic_discount, matched_rule = get_automatic_discount(
        subtotal,
        hotel_id
    )

    if matched_rule is not None:
        if matched_rule["discount_type"] == "PERCENTAGE":
            rule_value = f"{float(matched_rule['discount_value']):.2f}%"
        else:
            rule_value = f"₹{float(matched_rule['discount_value']):.2f}"

        print(
            f"Automatic Discount Rule: {matched_rule['rule_name']} "
            f"({rule_value})"
        )
        print(f"Automatic Discount Amount: ₹{automatic_discount:.2f}")
    else:
        print("Automatic Discount: ₹0.00 (No matching rule)")

    while True:
        raw = input(
            "Manual Discount Override "
            "(Enter = automatic, 0 = no discount) : "
        ).strip()

        if raw == "":
            return automatic_discount

        try:
            manual_discount = round(float(raw), 2)
        except (ValueError, TypeError):
            print("Enter a valid discount amount, 0, or press Enter.")
            continue

        if manual_discount < 0:
            print("Discount cannot be negative.")
            continue

        if manual_discount > subtotal:
            print("Discount cannot be greater than subtotal.")
            continue

        return manual_discount


def _print_cart(cart):
    print_header("CURRENT CART")
    if not cart:
        print("Cart is empty.")
        print_footer()
        return

    for index, item in enumerate(cart, 1):
        instruction = item.get("special_instructions") or "-"
        print(
            f"{index}. {item['name']} | Qty: {item['quantity']} | "
            f"Price: ₹{item['price']:.2f} | Subtotal: ₹{item['subtotal']:.2f}"
        )
        print(f"   Instruction: {instruction}")
    print_footer()


def _edit_cart(cart):
    while cart:
        _print_cart(cart)
        choices = [str(index) for index in range(1, len(cart) + 1)] + ["0"]
        item_choice = validate_menu_choice(
            "Select Item to Edit (0 = Done) : ", choices
        )
        if item_choice == "0":
            return

        index = int(item_choice) - 1
        item = cart[index]
        print("1. Update Quantity")
        print("2. Remove Item")
        print("3. Update Special Instructions")
        action = validate_menu_choice("Enter Choice : ", ["1", "2", "3"])

        if action == "1":
            item["quantity"] = validate_positive_number("Enter New Quantity : ")
            item["subtotal"] = item["price"] * item["quantity"]
            print_success("Quantity Updated Successfully.")
        elif action == "2":
            cart.pop(index)
            print_success("Item Removed From Cart.")
            if not cart:
                return
        else:
            item["special_instructions"] = input(
                "Enter Special Instructions (optional) : "
            ).strip()
            print_success("Item Instructions Updated Successfully.")


def _get_payment_input(grand_total):
    print_header("PAYMENT")
    print(f"Grand Total : ₹{grand_total:.2f}")
    print("1. Cash")
    print("2. UPI")
    print("3. Card")
    print("4. Other")
    print("5. Pending / Pay Later")
    print_footer()

    method_choice = validate_menu_choice(
        "Select Payment Method : ", ["1", "2", "3", "4", "5"]
    )

    if method_choice == "5":
        return None, 0.0

    payment_method = PAYMENT_METHODS[int(method_choice) - 1]
    rounded_cash_total = float(
        Decimal(str(round(float(grand_total), 2))).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )

    while True:
        if payment_method == "Cash" and abs(float(grand_total) - rounded_cash_total) > 0.001:
            print(f"Suggested Cash Settlement : ₹{rounded_cash_total:.2f}")
            max_amount = max(float(grand_total), rounded_cash_total)
        else:
            max_amount = float(grand_total)

        try:
            paid_amount = float(input("Enter Paid Amount : ").strip())
        except ValueError:
            print("Enter a valid payment amount.")
            continue

        if paid_amount < 0:
            print("Paid amount cannot be negative.")
            continue

        if paid_amount > max_amount + 0.01:
            print(f"Paid amount cannot exceed ₹{max_amount:.2f}.")
            continue

        if paid_amount > float(grand_total) + 0.01:
            if payment_method != "Cash" or abs(paid_amount - rounded_cash_total) > 0.01:
                print("Only the suggested whole-rupee Cash settlement may exceed the exact bill by a small rounding amount.")
                continue

        return payment_method, round(paid_amount, 2)


def _show_payment_history(order_id):
    history = get_order_payment_history(order_id)
    print_header("PAYMENT HISTORY")
    if not history:
        print("No payment transactions found.")
    else:
        for entry in history:
            print(
                f"#{entry['transaction_id']} | {entry['created_at']} | "
                f"{entry['transaction_type']} | "
                f"{entry['payment_method'] or '-'} | "
                f"₹{float(entry['amount'] or 0):.2f} | "
                f"{entry['notes'] or '-'}"
            )
    print_footer()
    press_enter()


def _payment_management():
    records = get_orders()
    if not records:
        print("No Orders Found.")
        press_enter()
        return

    print_header("PAYMENT MANAGEMENT")
    for index, record in enumerate(records, 1):
        print(
            f"{index}. {record['order_id']} | "
            f"₹{float(record['grand_total'] or 0):.2f} | "
            f"{record['payment_status'] or 'Pending'} | "
            f"Paid: ₹{float(record['paid_amount'] or 0):.2f} | "
            f"Balance: ₹{float(record['balance_amount'] or 0):.2f}"
        )
    print_footer()

    selected = validate_menu_choice(
        "Select Order Number (0 = Back) : ",
        [str(i) for i in range(1, len(records) + 1)] + ["0"]
    )
    if selected == "0":
        return

    order = records[int(selected) - 1]
    order_id = order["order_id"]
    grand_total = float(order["grand_total"] or 0)
    current_paid = float(order["paid_amount"] or 0)
    current_refund = float(order["refund_amount"] or 0)
    balance = float(order["balance_amount"] or 0)

    print_header("ORDER PAYMENT")
    print(f"Order ID       : {order_id}")
    print(f"Grand Total    : ₹{grand_total:.2f}")
    print(f"Payment Method : {order['payment_method'] or '-'}")
    print(f"Payment Status : {order['payment_status'] or 'Pending'}")
    print(f"Paid Amount    : ₹{current_paid:.2f}")
    print(f"Balance        : ₹{balance:.2f}")
    print(f"Refund Amount  : ₹{current_refund:.2f}")
    print_footer()

    print("1. Add Payment")
    print("2. Correct Payment")
    print("3. Refund")
    print("4. Payment History")
    print("5. Back")
    action = validate_menu_choice("Enter Choice : ", ["1", "2", "3", "4", "5"])
    if action == "5":
        return

    if action == "4":
        _show_payment_history(order_id)
        return

    if action == "1":
        if balance <= 0.01:
            print("No outstanding balance remains for this order.")
            press_enter()
            return
        print(f"Outstanding Balance : ₹{balance:.2f}")
        if abs(balance - round(balance)) > 0.001:
            print("Final cash settlement can use the nearest whole-rupee amount.")
            if balance <= 0.50:
                print("Enter 0 for Cash to settle this small fractional balance by rounding.")
        print("1. Cash")
        print("2. UPI")
        print("3. Card")
        print("4. Other")
        method_choice = validate_menu_choice("Select Payment Method : ", ["1", "2", "3", "4"])
        payment_method = PAYMENT_METHODS[int(method_choice) - 1]
        try:
            max_payment = balance
            if payment_method == "Cash" and abs(balance - round(balance)) > 0.001:
                suggested_cash = float(
                    Decimal(str(round(balance, 2))).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                )
                max_payment = max(balance, suggested_cash)
                print(f"Suggested Cash Settlement : ₹{suggested_cash:.2f}")
            amount = float(input(f"Enter Payment Amount (max ₹{max_payment:.2f}) : ").strip())
            if amount == 0 and payment_method == "Cash" and balance <= 0.50:
                notes = input("Rounding Notes (optional) : ").strip()
                result = settle_order_rounding(order_id, notes=notes)
                print_success(
                    f"Small balance settled by rounding. Status: {result['status']} | "
                    f"Paid: ₹{result['paid_amount']:.2f} | Balance: ₹{result['balance_amount']:.2f}"
                )
                press_enter()
                return
            notes = input("Payment Notes (optional) : ").strip()
            result = add_order_payment(
                order_id, amount, payment_method=payment_method, notes=notes
            )
        except (ValueError, TypeError) as exc:
            print(str(exc))
            press_enter()
            return
        print_success(
            f"Payment recorded. Status: {result['status']} | "
            f"Paid: ₹{result['paid_amount']:.2f} | "
            f"Balance: ₹{result['balance_amount']:.2f}"
        )
        press_enter()
        return

    if action == "2":
        payment_method, paid_amount = _get_payment_input(grand_total)
        reason = input("Payment Correction Reason : ").strip()
        try:
            status = correct_order_payment(
                order_id,
                paid_amount,
                payment_method=payment_method,
                correction_reason=reason
            )
        except ValueError as exc:
            print(str(exc))
            press_enter()
            return
        print_success(f"Payment corrected successfully. Status: {status}")
        press_enter()
        return

    if current_paid <= 0:
        print("There is no paid amount available for refund.")
        press_enter()
        return
    if (order["order_status"] or "New") not in ("Completed", "Cancelled"):
        print("Refund is allowed only for Completed or Cancelled orders.")
        press_enter()
        return

    refundable = max(current_paid - current_refund, 0)
    if refundable <= 0:
        print("No refundable balance remains.")
        press_enter()
        return
    try:
        refund_amount = float(input(
            f"Enter Refund Amount (max ₹{refundable:.2f}) : "
        ).strip())
    except ValueError:
        print("Enter a valid refund amount.")
        press_enter()
        return
    reason = input("Refund Reason : ").strip()
    try:
        status = record_order_refund(order_id, refund_amount, reason)
    except ValueError as exc:
        print(str(exc))
        press_enter()
        return
    print_success(f"Refund recorded successfully. Status: {status}")
    press_enter()


def _restaurant_sales_analytics():
    try:
        analytics = get_restaurant_sales_analytics()
    except Exception as exc:
        print(f"Error generating restaurant sales analytics: {exc}")
        press_enter()
        return

    print_header("RESTAURANT SALES & ANALYTICS")
    today = analytics["today"]
    overall = analytics["overall"]

    print("TODAY'S SALES")
    print(f"Sales              : ₹{today['sales']:.2f}")
    print(f"Order Count        : {today['order_count']}")
    print(f"Average Order Value: ₹{today['average_order_value']:.2f}")

    print("\nOVERALL SALES")
    print(f"Total Sales        : ₹{overall['sales']:.2f}")
    print(f"Total Orders       : {overall['order_count']}")
    print(f"Average Order Value: ₹{overall['average_order_value']:.2f}")

    print("\nDAILY SALES")
    if analytics["daily_sales"]:
        for order_date, sales, order_count in analytics["daily_sales"]:
            print(f"{order_date} | Sales: ₹{sales:.2f} | Orders: {order_count}")
    else:
        print("No sales data found.")

    print("\nITEM-WISE SALES")
    if analytics["item_sales"]:
        for item_name, data in analytics["item_sales"]:
            print(f"{item_name} | Qty: {data['quantity']:g} | Sales: ₹{data['sales']:.2f}")
    else:
        print("No item sales data found.")

    print("\nCATEGORY-WISE SALES")
    if analytics["category_sales"]:
        for category_name, data in analytics["category_sales"]:
            print(f"{category_name} | Qty: {data['quantity']:g} | Sales: ₹{data['sales']:.2f}")
    else:
        print("No category sales data found.")

    print("\nPAYMENT-WISE SALES / COLLECTIONS")
    if analytics["payment_sales"]:
        for payment_method, data in analytics["payment_sales"]:
            print(f"{payment_method} | Orders: {data['orders']} | Collected: ₹{data['collected']:.2f}")
    else:
        print("No payment data found.")

    print_footer()
    press_enter()

def _show_operational_orders(records, title):
    print_header(title)
    print(f"Active Orders : {len(records)}")
    if not records:
        print("No active orders found.")
        print_footer()
        press_enter()
        return

    for record in records:
        print(f"Order ID   : {record['order_id']}")
        print(f"Date/Time  : {record['order_date'] or '-'} {record['order_time'] or '-'}")
        print(f"Table      : {record['table_number'] or '-'}")
        print(f"Customer   : {record['customer_name'] or '-'}")
        print(f"Status     : {record['order_status'] or 'New'}")
        print("Items:")
        try:
            cart = json.loads(record['cart'] or '[]')
        except (TypeError, ValueError, json.JSONDecodeError):
            cart = []
        for item in cart:
            instruction = item.get("special_instructions") or "-"
            print(
                f"  - {item.get('name', '-')} | Qty: {item.get('quantity', 0)} "
                f"| Instruction: {instruction}"
            )
        if record["order_notes"]:
            print(f"Order Notes: {record['order_notes']}")
        print("-" * 70)

    print_footer()
    press_enter()


def _restaurant_operations():
    while True:
        summary = restaurant_operational_summary()
        print_header("RESTAURANT OPERATIONS")
        print(f"1. Pending / New Orders    ({summary['new']})")
        print(f"2. Preparing Orders         ({summary['preparing']})")
        print(f"3. Ready Orders             ({summary['ready']})")
        print(f"4. Served / Active Orders   ({summary['served']})")
        print("5. All Active Operations")
        print("6. Update Order Status")
        print("7. Back")
        print_footer()

        choice = validate_menu_choice(
            "Enter Choice : ",
            ["1", "2", "3", "4", "5", "6", "7"]
        )

        status_map = {
            "1": "New",
            "2": "Preparing",
            "3": "Ready",
            "4": "Served",
        }
        if choice in status_map:
            records = get_restaurant_operational_orders(status_map[choice])
            _show_operational_orders(records, f"{status_map[choice].upper()} ORDERS")
            continue

        if choice == "5":
            records = get_restaurant_operational_orders()
            _show_operational_orders(records, "ALL ACTIVE RESTAURANT OPERATIONS")
            continue

        if choice == "6":
            records = get_restaurant_operational_orders()
            if not records:
                print("No active orders found.")
                press_enter()
                continue
            print_header("UPDATE OPERATIONAL ORDER STATUS")
            for index, record in enumerate(records, 1):
                print(
                    f"{index}. {record['order_id']} | "
                    f"{record['order_status'] or 'New'} | "
                    f"Table: {record['table_number'] or '-'}"
                )
            print_footer()
            selected = validate_menu_choice(
                "Select Order Number (0 = Back) : ",
                [str(i) for i in range(1, len(records) + 1)] + ["0"]
            )
            if selected == "0":
                continue
            order = records[int(selected) - 1]
            current = order["order_status"] or "New"
            next_statuses = {
                "New": ["Preparing", "Cancelled"],
                "Preparing": ["Ready", "Cancelled"],
                "Ready": ["Served", "Cancelled"],
                "Served": ["Completed"],
                "Completed": [],
                "Cancelled": [],
            }[current]
            if not next_statuses:
                print(f"Order is already {current}. No further status transition is available.")
                press_enter()
                continue
            print("Available Statuses:")
            for status_index, status_name in enumerate(next_statuses, 1):
                print(f"{status_index}. {status_name}")

            while True:
                status_input = input("Select New Status : ").strip()
                if status_input.isdigit():
                    status_index = int(status_input)
                    if 1 <= status_index <= len(next_statuses):
                        new_status = next_statuses[status_index - 1]
                        break
                else:
                    normalized_status = status_input.casefold()
                    status_match = next(
                        (status_name for status_name in next_statuses
                         if status_name.casefold() == normalized_status),
                        None
                    )
                    if status_match is not None:
                        new_status = status_match
                        break
                print("❌ Invalid Status. Select a listed number or status name.")

            if new_status == "Cancelled":
                reason = input("Cancellation Reason : ").strip()
                cancel_restaurant_order(order["order_id"], reason)
            else:
                update_order_status(order["order_id"], new_status)
            print_success(f"Order status updated: {current} → {new_status}")
            press_enter()
            continue

        return



def _restaurant_security_integrity():
    report = restaurant_security_integrity_report()

    print_header("RESTAURANT SECURITY & DATA INTEGRITY")
    print(f"Total Restaurant Orders       : {report['orders']}")
    print(
        "1. Hotel Isolation Issues     : "
        f"{report['hotel_isolation_issues']}"
    )
    print(
        "2. Customer/Order Issues      : "
        f"{report['customer_order_relationship_issues']}"
    )
    print(
        "3. Table/Order Issues         : "
        f"{report['table_order_consistency_issues']}"
    )
    print(
        "4. Payment Consistency Issues : "
        f"{report['payment_consistency_issues']}"
    )
    print(
        "5. Foreign-Key Violations     : "
        f"{report['foreign_key_violations']}"
    )
    print(
        "6. Duplicate Order Issues     : "
        f"{report['duplicate_order_issues']}"
    )
    print_footer()

    if report["passed"]:
        print_success(
            "Restaurant security and data integrity check PASSED."
        )
    else:
        print(
            "❌ Integrity issues detected. "
            "Review the counts above before further operations."
        )

    press_enter()


def _cancellation_refund_correction_management():
    records = get_orders()
    if not records:
        print("No Orders Found.")
        press_enter()
        return

    while True:
        print_header("CANCELLATION / REFUND / CORRECTION")
        print("1. Cancel Order")
        print("2. Cancel Order Item")
        print("3. Correct Payment")
        print("4. Record Refund")
        print("5. View Order Audit")
        print("6. Back")
        print_footer()
        choice = validate_menu_choice("Enter Choice : ", ["1", "2", "3", "4", "5", "6"])
        if choice == "6":
            return

        records = get_orders()
        if not records:
            print("No Orders Found.")
            press_enter()
            return

        print_header("SELECT ORDER")
        for index, record in enumerate(records, 1):
            print(
                f"{index}. {record['order_id']} | "
                f"{record['order_status'] or 'New'} | "
                f"₹{float(record['grand_total'] or 0):.2f}"
            )
        print_footer()
        selected = validate_menu_choice(
            "Select Order Number (0 = Back) : ",
            [str(i) for i in range(1, len(records) + 1)] + ["0"]
        )
        if selected == "0":
            continue
        order = records[int(selected) - 1]
        order_id = order["order_id"]

        try:
            if choice == "1":
                reason = input("Cancellation Reason : ").strip()
                cancel_restaurant_order(order_id, reason)
                print_success("Order cancelled safely. Associated table released.")
                press_enter()
                continue

            if choice == "2":
                if (order["order_status"] or "New") not in ("New", "Preparing", "Ready"):
                    print("Items can only be cancelled before the order is Served.")
                    press_enter()
                    continue
                try:
                    cart = json.loads(order["cart"] or "[]")
                except (TypeError, json.JSONDecodeError):
                    cart = []
                if len(cart) <= 1:
                    print("Use full order cancellation when only one item remains.")
                    press_enter()
                    continue
                print_header("ORDER ITEMS")
                for index, item in enumerate(cart, 1):
                    print(f"{index}. {item['name']} | Qty: {item['quantity']} | ₹{float(item['subtotal']):.2f}")
                print_footer()
                item_number = validate_menu_choice(
                    "Select Item Number : ",
                    [str(i) for i in range(1, len(cart) + 1)]
                )
                reason = input("Item Cancellation Reason : ").strip()
                hotel = get_hotel_information()
                gst_rate = float(hotel["gst_rate"]) if hotel else 0.05
                result = cancel_order_item(
                    order_id, int(item_number), float(order["discount"] or 0),
                    gst_rate, reason
                )
                print_success(
                    f"Item cancelled. New Grand Total: ₹{result['grand_total']:.2f}"
                )
                press_enter()
                continue

            if choice == "3":
                grand_total = float(order["grand_total"] or 0)
                payment_method, paid_amount = _get_payment_input(grand_total)
                reason = input("Payment Correction Reason : ").strip()
                status = correct_order_payment(
                    order_id, paid_amount, payment_method=payment_method,
                    correction_reason=reason
                )
                print_success(f"Payment corrected. Status: {status}")
                press_enter()
                continue

            if choice == "4":
                paid = float(order["paid_amount"] or 0)
                refunded = float(order["refund_amount"] or 0)
                refundable = max(paid - refunded, 0)
                print(f"Refundable Amount : ₹{refundable:.2f}")
                amount = float(input("Refund Amount : ").strip())
                reason = input("Refund Reason : ").strip()
                status = record_order_refund(order_id, amount, reason)
                print_success(f"Refund recorded. Status: {status}")
                press_enter()
                continue

            audit = get_order_audit(order_id)
            print_header("ORDER AUDIT")
            if not audit:
                print("No audit records found.")
            else:
                for entry in audit:
                    print(f"{entry['created_at']} | {entry['action']} | {entry['details'] or '-'}")
            print_footer()
            press_enter()
        except (ValueError, TypeError) as exc:
            print(str(exc))
            press_enter()



def restaurant_menu():

    while True:

        print_header("RESTAURANT")
        print("1. New Restaurant Order")
        print("2. Menu Management")
        print("3. Order Status Management")
        print("4. Payment Management")
        print("5. Restaurant Order History")
        print("6. Restaurant Sales & Analytics")
        print("7. Restaurant Operations")
        print("8. Cancellation / Refund / Correction")
        print("9. Security & Data Integrity")
        print("10. Inventory Stock Integration")
        print("11. Back")
        print_footer()

        choice = validate_menu_choice(
            "Enter Choice : ",
            ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
        )

        if choice == "2":
            restaurant_menu_management()
            continue

        if choice == "3":
            records = get_orders()
            if not records:
                print("No Orders Found.")
                press_enter()
                continue
            print_header("ORDER STATUS MANAGEMENT")
            for index, record in enumerate(records, 1):
                print(f"{index}. {record['order_id']} | {record['order_status'] or 'New'} | {record['customer_name']}")
            print_footer()
            selected = validate_menu_choice("Select Order Number (0 = Back) : ", [str(i) for i in range(1, len(records) + 1)] + ["0"])
            if selected == "0":
                continue
            order = records[int(selected) - 1]
            current = order["order_status"] or "New"
            next_statuses = {
                "New": ["Preparing", "Cancelled"],
                "Preparing": ["Ready", "Cancelled"],
                "Ready": ["Served", "Cancelled"],
                "Served": ["Completed"],
                "Completed": [],
                "Cancelled": []
            }[current]
            if not next_statuses:
                print(f"Order is already {current}. No further status transition is available.")
                press_enter()
                continue
            print("Available Statuses:")
            for status_index, status_name in enumerate(next_statuses, 1):
                print(f"{status_index}. {status_name}")

            while True:
                status_input = input("Select New Status : ").strip()
                if status_input.isdigit():
                    status_index = int(status_input)
                    if 1 <= status_index <= len(next_statuses):
                        status = next_statuses[status_index - 1]
                        break
                else:
                    normalized_status = status_input.casefold()
                    status = next(
                        (status_name for status_name in next_statuses
                         if status_name.casefold() == normalized_status),
                        None
                    )
                    if status is not None:
                        break
                print("❌ Invalid Status. Select a listed number or status name.")

            try:
                if status == "Cancelled":
                    reason = input("Cancellation Reason : ").strip()
                    cancel_restaurant_order(order["order_id"], reason)
                else:
                    update_order_status(order["order_id"], status)
            except ValueError as exc:
                print_error(str(exc))
                press_enter()
                continue
            print_success(f"Order status updated: {current} → {status}")
            press_enter()
            continue

        if choice == "4":
            _payment_management()
            continue

        if choice == "5":
            restaurant_order_history()
            continue

        if choice == "6":
            _restaurant_sales_analytics()
            continue

        if choice == "7":
            _restaurant_operations()
            continue

        if choice == "8":
            _cancellation_refund_correction_management()
            continue

        if choice == "9":
            _restaurant_security_integrity()
            continue

        if choice == "10":
            try:
                restaurant_order_inventory_integration()
            except PermissionError as exc:
                print_error(str(exc))
                press_enter()
            continue

        if choice == "11":
            return

        cart = []

        print_header("RESTAURANT MENU")

        menu_items = get_menu_items(available_only=True)
        if not menu_items:
            print("No restaurant menu items are currently available.")
            print_footer()
            press_enter()
            continue

        for index, item in enumerate(menu_items, 1):
            print(
                f"{index}. {item['item_name']}  ₹{item['price']:.2f}"
            )

        print_footer()

        customer_id = None
        customer_name = None
        customer_mobile = None
        table_number = None

        print_header("RESTAURANT GUEST")
        print("1. Select Existing Guest")
        print("2. New Guest")
        print("3. Cancel Order")
        print_footer()

        guest_choice = validate_menu_choice(
            "Enter Choice : ",
            ["1", "2", "3"]
        )

        if guest_choice == "3":
            continue

        if guest_choice == "1":
            search_text = input(
                "Enter Guest ID / Name / Mobile / Email : "
            ).strip()

            guests = search_restaurant_guests(search_text)

            if not guests:
                print("No active guest found for this hotel.")
                press_enter()
                continue

            print_header("SELECT GUEST")
            for index, guest in enumerate(guests, 1):
                print(
                    f"{index}. {guest['customer_id']} | "
                    f"{guest['customer_name']} | "
                    f"{guest['customer_mobile'] or 'No Mobile'}"
                )
            print_footer()

            guest_index = validate_menu_choice(
                "Select Guest Number : ",
                [str(index) for index in range(1, len(guests) + 1)]
            )

            selected_guest = guests[int(guest_index) - 1]
            customer_id = selected_guest["customer_id"]
            customer_name = selected_guest["customer_name"]
            customer_mobile = selected_guest["customer_mobile"]

            validate_guest_hotel_relationship(customer_id)

        else:
            customer_name = validate_name("Enter Guest Name : ")
            customer_mobile = validate_mobile("Enter Mobile Number : ")
            customer_id = resolve_guest_for_booking(
                customer_name,
                customer_mobile
            )

        print_header("RESTAURANT TABLES")
        tables = get_available_restaurant_tables()

        if not tables:
            print("No Available restaurant tables are configured.")
            print_footer()
            press_enter()
            continue

        for table in tables:
            print(
                f"{table['table_number']} | "
                f"Capacity: {table['table_capacity']} | "
                f"Section/Area: {table['table_section']} | "
                f"Status: Available"
            )

        print_footer()

        table_number = input("Enter Available Table Number : ").strip().upper()

        try:
            validate_restaurant_table(table_number)
        except ValueError as exc:
            print(str(exc))
            press_enter()
            continue

        while True:

            food_choice = validate_menu_choice(
                "Select Food Number : ",
                [str(index) for index in range(1, len(menu_items) + 1)]
            )

            selected = menu_items[int(food_choice) - 1]
            food_name = selected["item_name"]
            price = selected["price"]

            quantity = validate_positive_number(
                "Enter Quantity : "
            )

            subtotal = price * quantity
            special_instructions = input(
                "Special Instructions (optional) : "
            ).strip()

            cart.append(
                {
                    "item_id": selected["item_id"],
                    "category_name": selected["category_name"],
                    "name": food_name,
                    "price": price,
                    "quantity": quantity,
                    "subtotal": subtotal,
                    "special_instructions": special_instructions
                }
            )

            print_success("Item Added To Cart Successfully.")
            _print_cart(cart)

            while True:
                print("1. Add More Items")
                print("2. Edit Cart")
                print("3. Finish Order")
                cart_action = validate_menu_choice(
                    "Enter Choice : ", ["1", "2", "3"]
                )
                if cart_action == "1":
                    break
                if cart_action == "2":
                    _edit_cart(cart)
                    if not cart:
                        print("Cart is empty. Add at least one item.")
                        continue
                    _print_cart(cart)
                    continue
                break

            if cart_action == "3":
                break

        order_notes = input("Order Notes (optional) : ").strip()
        subtotal_preview = round(
            sum(float(item["subtotal"]) for item in cart),
            2
        )
        discount = _get_order_discount(subtotal_preview)
        order_time = current_datetime_object()

        order_id = generate_order_id()

        subtotal, discount, gst, grand_total = calculate_bill(cart, discount)
        payment_method, paid_amount = _get_payment_input(grand_total)

        table_claimed = False

        try:
            claim_restaurant_table(table_number)
            table_claimed = True

            saved_order = save_order(
                cart,
                order_id,
                order_time,
                customer_name,
                customer_mobile,
                table_number,
                subtotal,
                gst,
                grand_total,
                customer_id=customer_id,
                order_notes=order_notes,
                discount=discount,
                payment_method=payment_method,
                paid_amount=paid_amount
            )

        except Exception:
            if table_claimed:
                try:
                    release_table(table_number)
                except Exception as exc:
                    log_non_blocking_error("Non-blocking optional operation failed", exc)
            raise

        print_success(
            "Order Saved Successfully. Table is now Occupied."
        )

        if saved_order and saved_order.get("invoice_number"):
            print(f"Invoice Number : {saved_order['invoice_number']}")

        print_final_bill(
            cart,
            order_id,
            order_time,
            customer_name,
            customer_mobile,
            table_number,
            discount=discount
        )

        cart.clear()

        press_enter()

