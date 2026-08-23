from data import hotel_name, gst_rate

def print_bill(food_name, price, quantity):

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

    print("Subtotal  : ₹", subtotal)
    print("GST       : ₹", gst)
    print("Grand Total : ₹", grand_total)

    print("=" * 40)

def print_final_bill(
        cart,
        order_id,
        order_time,
        customer_name,
        customer_mobile,
        table_number
):

    subtotal = 0

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

        subtotal += item["subtotal"]

    print("-" * 40)

    gst = subtotal * gst_rate

    grand_total = subtotal + gst

    print("Subtotal    : ₹", subtotal)
    print("GST (5%)    : ₹", gst)
    print("Grand Total : ₹", grand_total)

    print("=" * 40)
    print("Thank You! Visit Again")
    print("=" * 40)
