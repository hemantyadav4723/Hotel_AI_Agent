from database.hotel_information_db import get_hotel_information


def get_billing_configuration():
    hotel = get_hotel_information()
    if not hotel:
        raise RuntimeError("Hotel configuration is not available.")
    return hotel["hotel_name"], hotel["gst_rate"]


def calculate_bill(cart, discount=0):
    """Calculate subtotal, discount, GST and grand total."""
    _, gst_rate = get_billing_configuration()
    subtotal = sum(float(item["subtotal"]) for item in cart)
    try:
        discount = float(discount)
    except (TypeError, ValueError):
        raise ValueError("Discount must be a valid number.")
    if discount < 0:
        raise ValueError("Discount cannot be negative.")
    if discount > subtotal:
        raise ValueError("Discount cannot be greater than subtotal.")
    taxable_amount = subtotal - discount
    gst = taxable_amount * gst_rate
    grand_total = taxable_amount + gst
    return subtotal, discount, gst, grand_total


def print_bill(food_name, price, quantity):
    hotel_name, gst_rate = get_billing_configuration()
    subtotal = price * quantity
    gst = subtotal * gst_rate
    grand_total = subtotal + gst
    print("=" * 40)
    print(hotel_name.center(40))
    print("=" * 40)
    print("Food Item :", food_name)
    print("Price     : ₹", price)
    print("Quantity  :", quantity)
    print("-" * 40)
    print("Subtotal    : ₹", subtotal)
    print("GST         : ₹", gst)
    print("Grand Total : ₹", grand_total)
    print("=" * 40)


def print_final_bill(
        cart,
        order_id,
        order_time,
        customer_name,
        customer_mobile,
        table_number,
        discount=0
):
    hotel_name, gst_rate = get_billing_configuration()
    subtotal, discount, gst, grand_total = calculate_bill(cart, discount)
    print("=" * 40)
    print(hotel_name.center(40))
    print("=" * 40)
    print(f"Order ID : {order_id}")
    print(f"Date     : {order_time.strftime('%d-%m-%Y')}")
    print(f"Time     : {order_time.strftime('%I:%M:%S %p')}")
    print("-" * 40)
    print(f"Customer : {customer_name}")
    print(f"Mobile   : {customer_mobile}")
    print(f"Table No : {table_number}")
    print("=" * 40)
    print("Items Ordered\n")
    for item in cart:
        print(f"{item['name']} x{item['quantity']} = ₹{item['subtotal']}")
        if item.get("special_instructions"):
            print(f"  Instruction: {item['special_instructions']}")
    print("-" * 40)
    print("Subtotal    : ₹", subtotal)
    print("Discount    : ₹", discount)
    print(f"GST ({gst_rate * 100:.0f}%)    : ₹", gst)
    print("Grand Total : ₹", grand_total)
    print("=" * 40)
    print("Thank You! Visit Again")
    print("=" * 40)
    return subtotal, discount, gst, grand_total
