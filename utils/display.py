# ==========================================
# DISPLAY FUNCTIONS
# ==========================================

def print_header(title):

    print("\n" + "=" * 60)
    print(title.center(60))
    print("=" * 60)


def print_footer():

    print("=" * 60)


def print_success(message):

    print(f"\n✅ {message}")


def print_error(message):

    print(f"\n❌ {message}")


def print_warning(message):

    print(f"\n⚠️ {message}")


def press_enter():

    input("\nPress Enter To Continue...")

# ==========================================================
# ROOM BOOKING SUMMARY
# ==========================================================

def print_room_booking_summary(
    booking_id,
    booking_time,
    customer_name,
    customer_mobile,
    room_number,
    room_type,
    room_price,
    days,
    total,
    gst,
    grand_total
):

    print_header("ROOM BOOKING SUMMARY")

    print(f"Booking ID     : {booking_id}")
    print(f"Date           : {booking_time.strftime('%d-%m-%Y')}")
    print(f"Time           : {booking_time.strftime('%I:%M:%S %p')}")

    print("-" * 50)

    print(f"Customer Name  : {customer_name}")
    print(f"Mobile         : {customer_mobile}")

    print("-" * 50)

    print(f"Room Number    : {room_number}")
    print(f"Room Type      : {room_type}")
    print(f"Price/Night    : ₹{room_price}")
    print(f"Days           : {days}")

    print("-" * 50)

    print(f"Subtotal       : ₹{total}")
    print(f"GST (5%)       : ₹{gst}")
    print(f"Grand Total    : ₹{grand_total}")

    print_footer()

# ==========================================================
# SEPARATOR
# ==========================================================

def print_separator():

    print("-" * 50)