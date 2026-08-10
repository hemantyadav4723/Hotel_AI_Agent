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

def save_order(
        cart,
        order_id,
        order_time,
        customer_name,
        customer_mobile,
        table_number
):

    with open("orders.txt", "a", encoding="utf-8") as file:

        file.write("="*40 + "\n")

        file.write(f"Order ID : {order_id}\n")
        file.write(f"Date : {order_time.strftime('%d-%m-%Y')}\n")
        file.write(f"Time : {order_time.strftime('%I:%M:%S %p')}\n")
        file.write(f"Customer : {customer_name}\n")
        file.write(f"Mobile : {customer_mobile}\n")
        file.write(f"Table No : {table_number}\n")
        file.write("-" * 40 + "\n")

        for item in cart:

            file.write(
                f"{item['name']} *{item['quantity']} = ₹{item['subtotal']}\n"
            )

        file.write("="*40 + "\n\n")

def view_orders():

    print("=" * 40)
    print("      ORDER HISTORY")
    print("=" * 40)

    try:

        with open("orders.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if data:

                print(data)

            else:

                print("No Orders Found.")

    except FileNotFoundError:

        print("orders.txt File Not Found.")

def search_order():

    search = input("Enter Food Name : ").lower()

    found = False

    with open("orders.txt", "r", encoding="utf-8") as file:

        for line in file:

            if search in line.lower():

                print(line.strip())

                found = True

    if not found:

        print("Order Not Found.")

def delete_order():

    print("=" * 40)
    print("      DELETE ORDER")
    print("=" * 40)

    delete_name = input("Enter Food Name :").lower()

    lines = []

    deleted = False

    with open("orders.txt", "r", encoding="utf-8") as file:

        for line in file:

            if delete_name not in line.lower():

                lines.append(line)

            else:

                deleted = True

    with open("orders.txt", "w", encoding="utf-8") as file:

        file.writelines(lines)

    if deleted:

        print("Order Deleted Successfully.")

    else:

        print("Order Not Found.")

def save_room_booking(
        booking_id,
        booking_time,
        customer_name,
        customer_mobile,
        room_choice,
        room_type,
        room_price,
        days,
        total,
        gst,
        grand_total
):
    

    with open("room_bookings.txt", "a", encoding="utf-8") as file:

        file.write("=" * 50 + "\n")

        file.write(f"Booking ID : {booking_id}\n")
        file.write(f"Date : {booking_time.strftime('%d-%m-%Y')}\n")
        file.write(f"Time : {booking_time.strftime('%I:%M:%S %p')}\n")

        file.write("-" * 50 + "\n")

        file.write(f"Customer : {customer_name}\n")
        file.write(f"Mobile : {customer_mobile}\n")

        file.write("-" * 50 + "\n")

        file.write(f"Room Number : {room_choice}\n")
        file.write(f"Room Type : {room_type}\n")
        file.write(f"Price/Night : ₹{room_price}\n")
        file.write(f"Days : {days}\n")

        file.write("-" * 50 + "\n")

        file.write(f"Subtotal : ₹{total}\n")
        file.write(f"GST (5%) : ₹{gst}\n")
        file.write(f"Grand Total : ₹{grand_total}\n")

        file.write("=" * 50 + "\n\n")

def view_room_bookings():

    print("=" * 50)
    print("         ROOM BOOKING HISTORY")
    print("=" * 50)

    try:

        with open("room_bookings.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if data:

                print(data)

            else:

                print("No Room Bookings Found.")

    except FileNotFoundError:

        print("room_bookings.txt File Not Found.")

def search_room_booking():

    print("=" * 50)
    print("      SEARCH ROOM BOOKING")
    print("=" * 50)

    booking_id = input("Enter Booking ID : ")

    found = False

    with open("room_bookings.txt", "r", encoding="utf-8") as file:
        
        bookings = file.read().split("="*50)

    for booking in bookings:

        if booking_id in booking:

            print("="*50)
            print(booking.strip())
            print("="*50)

            found = True

    if not found:

        print("Booking Not Found.")

def delete_room_booking():

    print("=" * 50)
    print("      DELETE ROOM BOOKING")
    print("=" * 50)

    booking_id = input("Enter Booking ID : ")

    found = False

    with open("room_bookings.txt", "r", encoding="utf-8") as file:

        bookings = file.read().split("=" * 50)

    new_bookings = []

    for booking in bookings:

        if booking.strip() == "":
            continue

        if booking_id in booking:

            found = True

        else:

            new_bookings.append(booking)

    with open("room_bookings.txt", "w", encoding="utf-8") as file:

        for booking in new_bookings:

            file.write("=" * 50 + "\n")
            file.write(booking.strip() + "\n")
            file.write("=" * 50 + "\n\n")

    if found:

        print("Room Booking Deleted Successfully.")

    else:

        print("Booking Not Found.")

def is_room_booked(room_number):

    try:

        with open("room_bookings.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if f"Room Number : {room_number}" in data:

                return True

    except FileNotFoundError:

        pass

    return False

def is_table_booked(table_number):

    try:

        with open("table_bookings.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if f"Table Number : {table_number}" in data:

                return True

    except FileNotFoundError:

        pass

    return False

def save_customer(
        customer_id,
        customer_name,
        customer_mobile,
        customer_email,
        customer_address,
        created_time
):

    with open("customers.txt", "a", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")
        file.write(f"Customer ID : {customer_id}\n")
        file.write(f"Date : {created_time.strftime('%d-%m-%Y')}\n")
        file.write(f"Time : {created_time.strftime('%I:%M:%S %p')}\n")
        file.write("-" * 60 + "\n")
        file.write(f"Name : {customer_name}\n")
        file.write(f"Mobile : {customer_mobile}\n")
        file.write(f"Email : {customer_email}\n")
        file.write(f"Address : {customer_address}\n")
        file.write("=" * 60 + "\n\n")

def get_next_customer_id():

    try:

        with open("customers.txt", "r", encoding="utf-8") as file:

            data = file.read()

            ids = []

            for line in data.splitlines():

                if line.startswith("Customer ID :"):

                    customer_id = line.split(":")[1].strip()

                    number = int(customer_id.replace("CUST", ""))

                    ids.append(number)

            if ids:

                return f"CUST{max(ids) + 1}"

    except FileNotFoundError:

        pass

    return "CUST1001"

def view_customers():

    print("=" * 60)
    print("            CUSTOMER LIST")
    print("=" * 60)

    try:

        with open ("customers.txt", "r", encoding="utf-8") as file:
            data = file.read()

            if data.strip():
                print(data)

            else:
                print("No Customers Found.")

    except FileNotFoundError:

        print("customers.txt File Not Found.")

def search_customer():

   print("=" * 60)
   print("          SEARCH CUSTOMER")
   print("=" * 60)

   customer_id = input("Enter Customer ID : ").upper()

   found = False

   try:

       with open("customers.txt", "r", encoding="utf-8") as file:

           customers = file.read().split("=" * 60)

       for customer in customers:

           if customer.strip() == "":
               continue

           if customer_id in customer:

               print("=" * 60)
               print(customer.strip())
               print("=" * 60)

               found = True

       if not found:

           print("Customer Not Found.")

   except FileNotFoundError:

       print("customers.txt File Not Found.")    

def update_customer():

    print("=" * 60)
    print("          UPDATE CUSTOMER")
    print("=" * 60)

    customer_id = input("Enter Customer ID : ").upper()

    try:

        with open("customers.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("customers.txt File Not Found.")
        return

    customers = data.split("=" * 60)

    updated_data = ""

    found = False

    for customer in customers:

        if customer.strip() == "":
            continue

        if customer_id in customer:

            print("\nCustomer Found\n")

            name = input("Enter New Name : ")
            mobile = input("Enter New Mobile : ")
            email = input("Enter New Email : ")
            address = input("Enter New Address : ")

            lines = customer.strip().split("\n")

            date = lines[1].split(":",1)[1].strip()
            time = lines[2].split(":",1)[1].strip()

            new_customer = (
                "=" * 60 + "\n"
                f"Customer ID : {customer_id}\n"
                f"Date : {date}\n"
                f"Time : {time}\n"
                + "-" * 60 + "\n"
                f"Name : {name}\n"
                f"Mobile : {mobile}\n"
                f"Email : {email}\n"
                f"Address : {address}\n"
                + "=" * 60 + "\n\n"
            )

            updated_data += new_customer

            found = True

        else:

            updated_data += "=" * 60 + customer.strip() + "\n\n"

    with open("customers.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("\nCustomer Updated Successfully.")

    else:

        print("\nCustomer Not Found.")  

def delete_customer():

    print("=" * 60)
    print("          DELETE CUSTOMER")
    print("=" * 60)

    customer_id = input("Enter Customer ID : ").upper()

    try:

        with open("customers.txt", "r", encoding="utf-8") as file:

            customers = file.read().split("=" * 60)

        updated_customers = []

        found = False

        for customer in customers:

            if customer.strip() == "":
                continue

            if customer_id in customer:

                found = True

            else:

                updated_customers.append(customer)

        with open("customers.txt", "w", encoding="utf-8") as file:

            for customer in updated_customers:

                file.write("=" * 60)
                file.write(customer.strip())
                file.write("\n\n")

        if found:

            print("Customer Deleted Successfully.")

        else:

            print("Customer Not Found.")

    except FileNotFoundError:

        print("customers.txt File Not Found.")

def customer_history():

    print("=" * 60)
    print("          CUSTOMER HISTORY")
    print("=" * 60)

    try:

        with open("customers.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if data.strip():

                print(data)

            else:

                print("No Customer History Found.")

    except FileNotFoundError:

        print("customers.txt File Not Found.")

def get_next_staff_id():

    try:

        with open("staff.txt", "r", encoding="utf-8") as file:

            data = file.read()

            ids = []

            for line in data.splitlines():

                if line.startswith("Staff ID :"):

                    staff_id = line.split(":")[1].strip()

                    number = int(staff_id.replace("EMP", ""))

                    ids.append(number)

            if ids:

                return f"EMP{max(ids)+1}"

    except FileNotFoundError:

        pass

    return "EMP1001"


def save_staff(
        staff_id,
        joining_date,
        staff_name,
        mobile,
        email,
        department,
        designation,
        salary
):

    with open("staff.txt", "a", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")

        file.write(f"Staff ID : {staff_id}\n")
        file.write(f"Joining Date : {joining_date.strftime('%d-%m-%Y')}\n")
        file.write(f"Joining Time : {joining_date.strftime('%I:%M:%S %p')}\n")

        file.write("-" * 60 + "\n")

        file.write(f"Name : {staff_name}\n")
        file.write(f"Mobile : {mobile}\n")
        file.write(f"Email : {email}\n")
        file.write(f"Department : {department}\n")
        file.write(f"Designation : {designation}\n")
        file.write(f"Salary : {salary}\n")

        file.write("=" * 60 + "\n\n")

def view_staff():

    print("=" * 60)
    print("              STAFF LIST")
    print("=" * 60)

    try:

        with open("staff.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if data.strip():

                print(data)

            else:

                print("No Staff Found.")

    except FileNotFoundError:

        print("staff.txt File Not Found.")

def search_staff():

    print("=" * 60)
    print("            SEARCH STAFF")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    found = False

    try:

        with open("staff.txt", "r", encoding="utf-8") as file:

            staffs = file.read().split("=" * 60)

        for staff in staffs:

            if staff.strip() == "":
                continue

            if staff_id in staff:

                print("=" * 60)
                print(staff.strip())
                print("=" * 60)

                found = True

        if not found:

            print("Staff Not Found.")

    except FileNotFoundError:

        print("staff.txt File Not Found.")

def update_staff():

    print("=" * 60)
    print("            UPDATE STAFF")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    try:

        with open("staff.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("staff.txt File Not Found.")
        return

    staffs = data.split("=" * 60)

    updated_data = ""

    found = False

    for staff in staffs:

        if staff.strip() == "":
            continue

        if staff_id in staff:

            print("\nStaff Found\n")

            name = input("Enter New Name : ")
            mobile = input("Enter New Mobile : ")
            email = input("Enter New Email : ")
            department = input("Enter New Department : ")
            designation = input("Enter New Designation : ")
            salary = input("Enter New Salary : ")

            lines = staff.strip().split("\n")

            joining_date = lines[1].split(":", 1)[1].strip()
            joining_time = lines[2].split(":", 1)[1].strip()

            new_staff = (
                "=" * 60 + "\n"
                f"Staff ID : {staff_id}\n"
                f"Joining Date : {joining_date}\n"
                f"Joining Time : {joining_time}\n"
                + "-" * 60 + "\n"
                f"Name : {name}\n"
                f"Mobile : {mobile}\n"
                f"Email : {email}\n"
                f"Department : {department}\n"
                f"Designation : {designation}\n"
                f"Salary : {salary}\n"
                + "=" * 60 + "\n\n"
            )

            updated_data += new_staff

            found = True

        else:

            updated_data += "=" * 60 + staff.strip() + "\n\n"

    with open("staff.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("\nStaff Updated Successfully.")

    else:

        print("\nStaff Not Found.")

def delete_staff():

    print("=" * 60)
    print("            DELETE STAFF")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    try:

        with open("staff.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("staff.txt File Not Found.")
        return

    staffs = data.split("=" * 60)

    updated_data = ""

    found = False

    for staff in staffs:

        if staff.strip() == "":
            continue

        if staff_id in staff:

            found = True

            continue

        updated_data += "=" * 60 + staff.strip() + "\n\n"

    with open("staff.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("\nStaff Deleted Successfully.")

    else:

        print("\nStaff Not Found.")

from datetime import datetime

def staff_check_in():

    print("=" * 60)
    print("             STAFF CHECK IN")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    check_in = datetime.now()

    with open("attendance.txt", "a", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")
        file.write(f"Staff ID : {staff_id}\n")
        file.write(f"Date : {check_in.strftime('%d-%m-%Y')}\n")
        file.write(f"Check In : {check_in.strftime('%I:%M:%S %p')}\n")
        file.write("Check Out : --\n")
        file.write("Status : Present\n")
        file.write("=" * 60 + "\n\n")

    print("\nCheck In Successful.")

def staff_check_out():

    print("=" * 60)
    print("             STAFF CHECK OUT")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    try:

        with open("attendance.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("attendance.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated_data = ""

    found = False

    check_out = datetime.now().strftime("%I:%M:%S %p")

    for record in records:

        if record.strip() == "":
            continue

        if staff_id in record and "Check Out : --" in record:

            record = record.replace(
                "Check Out : --",
                f"Check Out : {check_out}"
            )

            found = True

        updated_data += "=" * 60 + "\n"
        updated_data += record.strip()
        updated_data += "\n\n"

    with open("attendance.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("\nCheck Out Successful.")

    else:

        print("\nNo Active Check In Found.")

def view_attendance():

    print("=" * 60)
    print("          ATTENDANCE HISTORY")
    print("=" * 60)

    try:

        with open("attendance.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if data.strip():

                print(data)

            else:

                print("No Attendance Found.")

    except FileNotFoundError:

        print("attendance.txt File Not Found.")

def search_attendance():

    print("=" * 60)
    print("          SEARCH ATTENDANCE")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    found = False

    try:

        with open("attendance.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Staff ID : {staff_id}" in record:

                print("=" * 60)
                print(record.strip())
                print("=" * 60)

                found = True

        if not found:

            print("Attendance Not Found.")

    except FileNotFoundError:

        print("attendance.txt File Not Found.")

def monthly_attendance_report():

    print("=" * 60)
    print("        MONTHLY ATTENDANCE REPORT")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    total_present = 0

    try:

        with open("attendance.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Staff ID : {staff_id}" in record:

                total_present += 1

        print("-" * 60)
        print("Staff ID      :", staff_id)
        print("Present Days  :", total_present)
        print("Absent Days   : Under Development")
        print("Working Hours : Under Development")
        print("-" * 60)

    except FileNotFoundError:

        print("attendance.txt File Not Found.")

def save_salary(
        staff_id,
        staff_name,
        department,
        basic_salary,
        bonus,
        deduction,
        net_salary
):

    with open("salary.txt", "a", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")

        file.write(f"Staff ID : {staff_id}\n")
        file.write(f"Name : {staff_name}\n")
        file.write(f"Department : {department}\n")

        file.write("-" * 60 + "\n")

        file.write(f"Basic Salary : {basic_salary}\n")
        file.write(f"Bonus : {bonus}\n")
        file.write(f"Deduction : {deduction}\n")
        file.write(f"Net Salary : {net_salary}\n")

        file.write("=" * 60 + "\n\n")

def view_salary():

    print("=" * 60)
    print("            SALARY LIST")
    print("=" * 60)

    try:

        with open("salary.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if data.strip():

                print(data)

            else:

                print("No Salary Record Found.")

    except FileNotFoundError:

        print("salary.txt File Not Found.")

def search_salary():

    print("=" * 60)
    print("           SEARCH SALARY")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    found = False

    try:

        with open("salary.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Staff ID : {staff_id}" in record:

                print("=" * 60)
                print(record.strip())
                print("=" * 60)

                found = True

        if not found:

            print("Salary Record Not Found.")

    except FileNotFoundError:

        print("salary.txt File Not Found.")

def update_salary():

    print("=" * 60)
    print("           UPDATE SALARY")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    try:

        with open("salary.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("salary.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated_data = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"Staff ID : {staff_id}" in record:

            print("\nSalary Record Found\n")

            staff_name = input("Enter Staff Name : ")
            department = input("Enter Department : ")

            basic_salary = float(input("Enter Basic Salary : "))
            bonus = float(input("Enter Bonus : "))
            deduction = float(input("Enter Deduction : "))

            net_salary = basic_salary + bonus - deduction

            new_record = (
                "=" * 60 + "\n"
                f"Staff ID : {staff_id}\n"
                f"Name : {staff_name}\n"
                f"Department : {department}\n"
                + "-" * 60 + "\n"
                f"Basic Salary : {basic_salary}\n"
                f"Bonus : {bonus}\n"
                f"Deduction : {deduction}\n"
                f"Net Salary : {net_salary}\n"
                + "=" * 60 + "\n\n"
            )

            updated_data += new_record

            found = True

        else:

            updated_data += "=" * 60 + record.strip() + "\n\n"

    with open("salary.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("\nSalary Updated Successfully.")

    else:

        print("\nSalary Record Not Found.")

def delete_salary():

    print("=" * 60)
    print("           DELETE SALARY")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    try:

        with open("salary.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("salary.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated_data = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"Staff ID : {staff_id}" in record:

            found = True

            continue

        updated_data += "=" * 60 + record.strip() + "\n\n"

    with open("salary.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("\nSalary Deleted Successfully.")

    else:

        print("\nSalary Record Not Found.")

def generate_payroll():

    print("=" * 60)
    print("           MONTHLY PAYROLL")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    found = False

    try:

        with open("salary.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Staff ID : {staff_id}" in record:

                print(record.strip())

                found = True

                with open("payroll.txt", "a", encoding="utf-8") as payroll:

                    payroll.write("=" * 60 + "\n")
                    payroll.write(record.strip())
                    payroll.write("\n")
                    payroll.write("Payroll Status : Generated\n")
                    payroll.write("=" * 60 + "\n\n")

                print("\nPayroll Generated Successfully.")

                break

        if not found:

            print("Salary Record Not Found.")

    except FileNotFoundError:

        print("salary.txt File Not Found.")

def view_payroll():

    print("=" * 60)
    print("           PAYROLL HISTORY")
    print("=" * 60)

    try:

        with open("payroll.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if data.strip():

                print(data)

            else:

                print("No Payroll Found.")

    except FileNotFoundError:

        print("payroll.txt File Not Found.")

def search_payroll():

    print("=" * 60)
    print("          SEARCH PAYROLL")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    found = False

    try:

        with open("payroll.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Staff ID : {staff_id}" in record:

                print("=" * 60)
                print(record.strip())
                print("=" * 60)

                found = True

        if not found:

            print("Payroll Not Found.")

    except FileNotFoundError:

        print("payroll.txt File Not Found.")

def delete_payroll():

    print("=" * 60)
    print("          DELETE PAYROLL")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    try:

        with open("payroll.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("payroll.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated_data = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"Staff ID : {staff_id}" in record:

            found = True

            continue

        updated_data += "=" * 60 + "\n"
        updated_data += record.strip()
        updated_data += "\n\n"

    with open("payroll.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("Payroll Deleted Successfully.")

    else:

        print("Payroll Not Found.")

def save_department(department_id, department_name):

    with open("department.txt", "a", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")
        file.write(f"Department ID : {department_id}\n")
        file.write(f"Department Name : {department_name}\n")
        file.write("=" * 60 + "\n\n")

def view_department():

    print("=" * 60)
    print("        DEPARTMENT LIST")
    print("=" * 60)

    try:

        with open("department.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if data.strip():

                print(data)

            else:

                print("No Department Found.")

    except FileNotFoundError:

        print("department.txt File Not Found.")

def search_department():

    department_id = input("Enter Department ID : ").upper()

    found = False

    try:

        with open("department.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Department ID : {department_id}" in record:

                print("=" * 60)
                print(record.strip())
                print("=" * 60)

                found = True

        if not found:

            print("Department Not Found.")

    except FileNotFoundError:

        print("department.txt File Not Found.")

def update_department():

    department_id = input("Enter Department ID : ").upper()

    try:

        with open("department.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("department.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated_data = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"Department ID : {department_id}" in record:

            department_name = input("Enter New Department Name : ")

            new_record = (
                "=" * 60 + "\n"
                f"Department ID : {department_id}\n"
                f"Department Name : {department_name}\n"
                + "=" * 60 + "\n\n"
            )

            updated_data += new_record

            found = True

        else:

            updated_data += "=" * 60 + record.strip() + "\n\n"

    with open("department.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("Department Updated Successfully.")

    else:

        print("Department Not Found.")

def delete_department():

    department_id = input("Enter Department ID : ").upper()

    try:

        with open("department.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("department.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated_data = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"Department ID : {department_id}" in record:

            found = True

            continue

        updated_data += "=" * 60 + record.strip() + "\n\n"

    with open("department.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("Department Deleted Successfully.")

    else:

        print("Department Not Found.")

def save_item(item_id, item_name, category, quantity, price):

    with open("inventory.txt", "a", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")
        file.write(f"Item ID : {item_id}\n")
        file.write(f"Item Name : {item_name}\n")
        file.write(f"Category : {category}\n")
        file.write(f"Quantity : {quantity}\n")
        file.write(f"Price : {price}\n")
        file.write("=" * 60 + "\n\n")

def view_items():

    print("=" * 60)
    print("          INVENTORY ITEMS")
    print("=" * 60)

    try:

        with open("inventory.txt","r",encoding="utf-8") as file:

            data=file.read()

            if data.strip():

                print(data)

            else:

                print("No Items Found.")

    except FileNotFoundError:

        print("inventory.txt File Not Found.")

def search_item():

    item_id=input("Enter Item ID : ").upper()

    found=False

    try:

        with open("inventory.txt","r",encoding="utf-8") as file:

            records=file.read().split("="*60)

        for record in records:

            if record.strip()=="":

                continue

            if f"Item ID : {item_id}" in record:

                print("="*60)
                print(record.strip())
                print("="*60)

                found=True

        if not found:

            print("Item Not Found.")

    except FileNotFoundError:

        print("inventory.txt File Not Found.")

def update_item():

    item_id=input("Enter Item ID : ").upper()

    try:

        with open("inventory.txt","r",encoding="utf-8") as file:

            data=file.read()

    except FileNotFoundError:

        print("inventory.txt File Not Found.")
        return

    records=data.split("="*60)

    updated_data=""

    found=False

    for record in records:

        if record.strip()=="":

            continue

        if f"Item ID : {item_id}" in record:

            item_name=input("Enter New Item Name : ")
            category=input("Enter Category : ")
            quantity=input("Enter Quantity : ")
            price=input("Enter Price : ")

            updated_data += "="*60+"\n"
            updated_data += f"Item ID : {item_id}\n"
            updated_data += f"Item Name : {item_name}\n"
            updated_data += f"Category : {category}\n"
            updated_data += f"Quantity : {quantity}\n"
            updated_data += f"Price : {price}\n"
            updated_data += "="*60+"\n\n"

            found=True

        else:

            updated_data += "="*60+record.strip()+"\n\n"

    with open("inventory.txt","w",encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("Item Updated Successfully.")

    else:

        print("Item Not Found.")

def delete_item():

    item_id=input("Enter Item ID : ").upper()

    try:

        with open("inventory.txt","r",encoding="utf-8") as file:

            data=file.read()

    except FileNotFoundError:

        print("inventory.txt File Not Found.")
        return

    records=data.split("="*60)

    updated_data=""

    found=False

    for record in records:

        if record.strip()=="":

            continue

        if f"Item ID : {item_id}" in record:

            found=True
            continue

        updated_data += "="*60+record.strip()+"\n\n"

    with open("inventory.txt","w",encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("Item Deleted Successfully.")

    else:

        print("Item Not Found.")

def stock_in():

    print("=" * 60)
    print("              STOCK IN")
    print("=" * 60)

    item_id = input("Enter Item ID : ").upper()

    try:

        with open("inventory.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("inventory.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated_data = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        lines = record.strip().split("\n")

        if f"Item ID : {item_id}" in record:

            item_name = lines[1].split(": ")[1]
            category = lines[2].split(": ")[1]
            quantity = int(lines[3].split(": ")[1])
            price = lines[4].split(": ")[1]

            add_qty = int(input("Enter Stock Quantity : "))

            quantity += add_qty

            updated_data += "=" * 60 + "\n"
            updated_data += f"Item ID : {item_id}\n"
            updated_data += f"Item Name : {item_name}\n"
            updated_data += f"Category : {category}\n"
            updated_data += f"Quantity : {quantity}\n"
            updated_data += f"Price : {price}\n"
            updated_data += "=" * 60 + "\n\n"

            found = True

        else:

            updated_data += "=" * 60 + record.strip() + "\n\n"

    with open("inventory.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("Stock Updated Successfully.")

    else:

        print("Item Not Found.")

def stock_out():

    print("=" * 60)
    print("             STOCK OUT")
    print("=" * 60)

    item_id = input("Enter Item ID : ").upper()

    try:

        with open("inventory.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("inventory.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated_data = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        lines = record.strip().split("\n")

        if f"Item ID : {item_id}" in record:

            item_name = lines[1].split(": ")[1]
            category = lines[2].split(": ")[1]
            quantity = int(lines[3].split(": ")[1])
            price = lines[4].split(": ")[1]

            remove_qty = int(input("Enter Used Quantity : "))

            if remove_qty > quantity:

                print("Not Enough Stock.")
                return

            quantity -= remove_qty

            updated_data += "=" * 60 + "\n"
            updated_data += f"Item ID : {item_id}\n"
            updated_data += f"Item Name : {item_name}\n"
            updated_data += f"Category : {category}\n"
            updated_data += f"Quantity : {quantity}\n"
            updated_data += f"Price : {price}\n"
            updated_data += "=" * 60 + "\n\n"

            found = True

        else:

            updated_data += "=" * 60 + record.strip() + "\n\n"

    with open("inventory.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("Stock Updated Successfully.")

    else:

        print("Item Not Found.")

def low_stock_alert():

    print("=" * 60)
    print("           LOW STOCK ALERT")
    print("=" * 60)

    found = False

    try:

        with open("inventory.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            lines = record.strip().split("\n")

            item_id = lines[0].split(": ")[1]
            item_name = lines[1].split(": ")[1]
            quantity = int(lines[3].split(": ")[1])

            if quantity <= 10:

                print(f"{item_id} | {item_name} | Stock : {quantity}")

                found = True

        if not found:

            print("No Low Stock Items.")

    except FileNotFoundError:

        print("inventory.txt File Not Found.")

def purchase_history():

    print("=" * 60)
    print("         PURCHASE HISTORY")
    print("=" * 60)

    try:

        with open("inventory.txt", "r", encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("inventory.txt File Not Found.")

def save_supplier(supplier_id, supplier_name, mobile):

    with open("supplier.txt", "a", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")
        file.write(f"Supplier ID : {supplier_id}\n")
        file.write(f"Supplier Name : {supplier_name}\n")
        file.write(f"Mobile : {mobile}\n")
        file.write("=" * 60 + "\n\n")

def view_supplier():

    print("=" * 60)
    print("         SUPPLIER LIST")
    print("=" * 60)

    try:

        with open("supplier.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if data.strip():

                print(data)

            else:

                print("No Supplier Found.")

    except FileNotFoundError:

        print("supplier.txt File Not Found.")

def search_supplier():

    print("=" * 60)
    print("         SEARCH SUPPLIER")
    print("=" * 60)

    supplier_id = input("Enter Supplier ID : ").upper()

    found = False

    try:

        with open("supplier.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Supplier ID : {supplier_id}" in record:

                print("=" * 60)
                print(record.strip())
                print("=" * 60)

                found = True

        if not found:

            print("Supplier Not Found.")

    except FileNotFoundError:

        print("supplier.txt File Not Found.")

def update_supplier():

    supplier_id = input("Enter Supplier ID : ").upper()

    try:

        with open("supplier.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("supplier.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated_data = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"Supplier ID : {supplier_id}" in record:

            supplier_name = input("Enter New Supplier Name : ")
            mobile = input("Enter Mobile : ")

            updated_data += "=" * 60 + "\n"
            updated_data += f"Supplier ID : {supplier_id}\n"
            updated_data += f"Supplier Name : {supplier_name}\n"
            updated_data += f"Mobile : {mobile}\n"
            updated_data += "=" * 60 + "\n\n"

            found = True

        else:

            updated_data += "=" * 60 + record.strip() + "\n\n"

    with open("supplier.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("Supplier Updated Successfully.")

    else:

        print("Supplier Not Found.")

def delete_supplier():

    supplier_id = input("Enter Supplier ID : ").upper()

    try:

        with open("supplier.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("supplier.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated_data = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"Supplier ID : {supplier_id}" in record:

            found = True

            continue

        updated_data += "=" * 60 + record.strip() + "\n\n"

    with open("supplier.txt", "w", encoding="utf-8") as file:

        file.write(updated_data)

    if found:

        print("Supplier Deleted Successfully.")

    else:

        print("Supplier Not Found.")

def sales_report():

    print("=" * 60)
    print("            SALES REPORT")
    print("=" * 60)

    try:

        with open("orders.txt", "r", encoding="utf-8") as file:

            data = file.read()

            if data.strip():

                print(data)

            else:

                print("No Sales Found.")

    except FileNotFoundError:

        print("orders.txt File Not Found.")

def restaurant_report():

    print("=" * 60)
    print("       RESTAURANT REPORT")
    print("=" * 60)

    sales_report()

def room_report():

    print("=" * 60)
    print("       ROOM BOOKING REPORT")
    print("=" * 60)

    try:

        with open("room_bookings.txt","r",encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("room_bookings.txt File Not Found.")

def table_report():

    print("=" * 60)
    print("       TABLE BOOKING REPORT")
    print("=" * 60)

    try:

        with open("table_bookings.txt","r",encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("table_bookings.txt File Not Found.")

def customer_report():

    print("=" * 60)
    print("       CUSTOMER REPORT")
    print("=" * 60)

    try:

        with open("customers.txt","r",encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("customers.txt File Not Found.")

def staff_report():

    print("=" * 60)
    print("         STAFF REPORT")
    print("=" * 60)

    try:

        with open("staff.txt","r",encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("staff.txt File Not Found.")

def salary_report():

    print("=" * 60)
    print("        SALARY REPORT")
    print("=" * 60)

    try:

        with open("salary.txt","r",encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("salary.txt File Not Found.")

def inventory_report():

    print("=" * 60)
    print("       INVENTORY REPORT")
    print("=" * 60)

    try:

        with open("inventory.txt","r",encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("inventory.txt File Not Found.")

def hotel_dashboard():

    print("=" * 60)
    print("          HOTEL DASHBOARD")
    print("=" * 60)

    files = {
        "Restaurant Orders": "orders.txt",
        "Room Bookings": "room_bookings.txt",
        "Table Bookings": "table_bookings.txt",
        "Customers": "customers.txt",
        "Staff": "staff.txt",
        "Departments": "department.txt",
        "Inventory Items": "inventory.txt",
        "Suppliers": "supplier.txt"
    }

    for title, filename in files.items():

        count = 0

        try:

            with open(filename, "r", encoding="utf-8") as file:

                data = file.read()

                count = data.count("=" * 60) // 2

        except FileNotFoundError:

            count = 0

        print(f"{title:<22}: {count}")

    print("=" * 60)

def save_expense(expense_id, title, category, amount, date):

    with open("expenses.txt", "a", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")
        file.write(f"Expense ID : {expense_id}\n")
        file.write(f"Title : {title}\n")
        file.write(f"Category : {category}\n")
        file.write(f"Amount : {amount}\n")
        file.write(f"Date : {date}\n")
        file.write("=" * 60 + "\n\n")

def view_expenses():

    try:

        with open("expenses.txt", "r", encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("No Expense Found.")

def search_expense():

    expense_id = input("Enter Expense ID : ").upper()

    found = False

    try:

        with open("expenses.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Expense ID : {expense_id}" in record:

                print(record)

                found = True

        if not found:

            print("Expense Not Found.")

    except FileNotFoundError:

        print("expenses.txt File Not Found.")

def update_expense():

    expense_id = input("Enter Expense ID : ").upper()

    try:

        with open("expenses.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("expenses.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"Expense ID : {expense_id}" in record:

            title = input("Title : ")
            category = input("Category : ")
            amount = input("Amount : ")
            date = input("Date : ")

            updated += "=" * 60 + "\n"
            updated += f"Expense ID : {expense_id}\n"
            updated += f"Title : {title}\n"
            updated += f"Category : {category}\n"
            updated += f"Amount : {amount}\n"
            updated += f"Date : {date}\n"
            updated += "=" * 60 + "\n\n"

            found = True

        else:

            updated += "=" * 60 + record.strip() + "\n\n"

    with open("expenses.txt", "w", encoding="utf-8") as file:

        file.write(updated)

    if found:

        print("Expense Updated Successfully.")

    else:

        print("Expense Not Found.")

def delete_expense():

    expense_id = input("Enter Expense ID : ").upper()

    try:

        with open("expenses.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("expenses.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"Expense ID : {expense_id}" in record:

            found = True

            continue

        updated += "=" * 60 + record.strip() + "\n\n"

    with open("expenses.txt", "w", encoding="utf-8") as file:

        file.write(updated)

    if found:

        print("Expense Deleted Successfully.")

    else:

        print("Expense Not Found.")

def save_feedback(feedback_id, customer_name, mobile, rating, review):

    with open("feedback.txt", "a", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")
        file.write(f"Feedback ID : {feedback_id}\n")
        file.write(f"Customer Name : {customer_name}\n")
        file.write(f"Mobile : {mobile}\n")
        file.write(f"Rating : {rating}/5\n")
        file.write(f"Review : {review}\n")
        file.write("=" * 60 + "\n\n")

def view_feedback():

    try:

        with open("feedback.txt", "r", encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("No Feedback Found.")

def search_feedback():

    feedback_id = input("Enter Feedback ID : ").upper()

    found = False

    try:

        with open("feedback.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Feedback ID : {feedback_id}" in record:

                print(record)

                found = True

        if not found:

            print("Feedback Not Found.")

    except FileNotFoundError:

        print("feedback.txt File Not Found.")

def delete_feedback():

    feedback_id = input("Enter Feedback ID : ").upper()

    try:

        with open("feedback.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("feedback.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"Feedback ID : {feedback_id}" in record:

            found = True
            continue

        updated += "=" * 60 + record.strip() + "\n\n"

    with open("feedback.txt", "w", encoding="utf-8") as file:

        file.write(updated)

    if found:

        print("Feedback Deleted Successfully.")

    else:

        print("Feedback Not Found.")

def save_user(user_id, username, password, role):

    with open("users.txt", "a", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")
        file.write(f"User ID : {user_id}\n")
        file.write(f"Username : {username}\n")
        file.write(f"Password : {password}\n")
        file.write(f"Role : {role}\n")
        file.write("=" * 60 + "\n\n")

def view_users():

    try:

        with open("users.txt", "r", encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("No Users Found.")

def delete_user():

    user_id = input("Enter User ID : ").upper()

    try:

        with open("users.txt", "r", encoding="utf-8") as file:

            data = file.read()

    except FileNotFoundError:

        print("users.txt File Not Found.")
        return

    records = data.split("=" * 60)

    updated = ""

    found = False

    for record in records:

        if record.strip() == "":
            continue

        if f"User ID : {user_id}" in record:

            found = True

            continue

        updated += "=" * 60 + record.strip() + "\n\n"

    with open("users.txt", "w", encoding="utf-8") as file:

        file.write(updated)

    if found:

        print("User Deleted Successfully.")

    else:

        print("User Not Found.")

def verify_login(username, password):

    try:

        with open("users.txt", "r", encoding="utf-8") as file:

            records = file.read().split("=" * 60)

        for record in records:

            if record.strip() == "":
                continue

            if f"Username : {username}" in record and f"Password : {password}" in record:

                print("\nLogin Successful.\n")
                return True

        print("\nInvalid Username or Password.")
        return False

    except FileNotFoundError:

        print("users.txt File Not Found.")
        return False

def save_settings(hotel_name, owner_name, gst, phone, email):

    with open("settings.txt", "w", encoding="utf-8") as file:

        file.write("=" * 60 + "\n")
        file.write(f"Hotel Name : {hotel_name}\n")
        file.write(f"Owner Name : {owner_name}\n")
        file.write(f"GST Number : {gst}\n")
        file.write(f"Phone : {phone}\n")
        file.write(f"Email : {email}\n")
        file.write("=" * 60 + "\n")

    print("\nSettings Saved Successfully.")

def view_settings():

    print("=" * 60)
    print("        HOTEL SETTINGS")
    print("=" * 60)

    try:

        with open("settings.txt", "r", encoding="utf-8") as file:

            print(file.read())

    except FileNotFoundError:

        print("No Settings Found.")

