from data import food_menu
from billing import print_final_bill
from utils.display import *
from utils.validators import *
from utils.date_time import current_datetime_object, generate_order_id
from utils.helpers import get_restaurant_customer_details
from database.db_manager import save_order

def restaurant_menu():

    cart = []

    print_header("RESTAURANT MENU")


    for key, value in food_menu.items():

        print(f"{key}. {value[0]}  ₹{value[1]}")

    print_footer()   

    customer_name,customer_mobile,table_number = get_restaurant_customer_details()

    while True:

        food_choice = validate_menu_choice(
            "Select Food Number : ",
            food_menu.keys()
        )

        food_name, price = food_menu[food_choice]
        quantity = validate_positive_number("Enter Quantity :")
        subtotal = price * quantity

        cart.append(
            {
                "name": food_name,
                "price": price,
                "quantity": quantity,
                "subtotal": subtotal
            }
        )

        print_success("Item Added To Cart Successfully.")

        more = validate_yes_no("Add More Items? (Yes/No):")

        if more == "Yes":
            continue

        order_time = current_datetime_object()
        order_id = generate_order_id()
        print_final_bill(
            cart,
            order_id,
            order_time,
            customer_name,
            customer_mobile,
            table_number
        )
        save_order(
            cart,
            order_id,
            order_time,
            customer_name,
            customer_mobile,
            table_number
        )
        cart.clear()
        break

    press_enter()