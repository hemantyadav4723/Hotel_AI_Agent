from datetime import datetime
import sqlite3
import json


DATABASE_NAME = "hotel.db"

import os
import sqlite3

DATABASE_NAME = "hotel.db"

def get_connection():

    connection = sqlite3.connect(DATABASE_NAME)

    connection.row_factory = sqlite3.Row

    return connection

def create_customers_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers(

        customer_id TEXT PRIMARY KEY,
        customer_name TEXT NOT NULL,
        customer_mobile TEXT,
        customer_email TEXT,
        customer_address TEXT,
        created_time TEXT

    )
    """)

    connection.commit()

    connection.close()

def save_customer(
    customer_id,
    customer_name,
    customer_mobile,
    customer_email,
    customer_address,
    created_time
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO customers
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        customer_id,
        customer_name,
        customer_mobile,
        customer_email,
        customer_address,
        created_time.strftime("%d-%m-%Y %I:%M:%S %p")
    ))

    connection.commit()

    connection.close()

def get_all_customers():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM customers")

    customers = cursor.fetchall()

    connection.close()

    return customers

def view_customers():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM customers")

    customers = cursor.fetchall()

    connection.close()

    if not customers:

        print("No Customers Found.")
        return

    print("=" * 60)
    print("            CUSTOMER LIST")
    print("=" * 60)

    for customer in customers:

        print(f"Customer ID : {customer['customer_id']}")
        print(f"Name        : {customer['customer_name']}")
        print(f"Mobile      : {customer['customer_mobile']}")
        print(f"Email       : {customer['customer_email']}")
        print(f"Address     : {customer['customer_address']}")
        print(f"Created     : {customer['created_time']}")
        print("-" * 60)

def search_customer():

    customer_id = input("Enter Customer ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM customers WHERE customer_id = ?",
        (customer_id,)
    )

    customer = cursor.fetchone()

    connection.close()

    print("=" * 60)
    print("          SEARCH CUSTOMER")
    print("=" * 60)

    if customer:

        print(f"Customer ID : {customer['customer_id']}")
        print(f"Name        : {customer['customer_name']}")
        print(f"Mobile      : {customer['customer_mobile']}")
        print(f"Email       : {customer['customer_email']}")
        print(f"Address     : {customer['customer_address']}")
        print(f"Created     : {customer['created_time']}")

    else:

        print("Customer Not Found.")

def update_customer():

    customer_id = input("Enter Customer ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM customers WHERE customer_id = ?",
        (customer_id,)
    )

    customer = cursor.fetchone()

    if not customer:

        print("Customer Not Found.")

        connection.close()

        return

    print("\nCustomer Found\n")

    name = input("Enter New Name : ")
    mobile = input("Enter New Mobile : ")
    email = input("Enter New Email : ")
    address = input("Enter New Address : ")

    cursor.execute("""
    UPDATE customers
    SET customer_name = ?,
        customer_mobile = ?,
        customer_email = ?,
        customer_address = ?
    WHERE customer_id = ?
    """, (
        name,
        mobile,
        email,
        address,
        customer_id
    ))

    connection.commit()

    connection.close()

    print("\nCustomer Updated Successfully.")

def delete_customer():

    customer_id = input("Enter Customer ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM customers WHERE customer_id = ?",
        (customer_id,)
    )

    customer = cursor.fetchone()

    if not customer:

        print("Customer Not Found.")

        connection.close()

        return

    cursor.execute(
        "DELETE FROM customers WHERE customer_id = ?",
        (customer_id,)
    )

    connection.commit()

    connection.close()

    print("Customer Deleted Successfully.")

def customer_history():

    view_customers()

def get_next_customer_id():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM customers")

    count = cursor.fetchone()[0]

    connection.close()

    return f"CUST{1001 + count}"


def create_staff_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS staff(

        staff_id TEXT PRIMARY KEY,
        staff_name TEXT NOT NULL,
        mobile TEXT,
        email TEXT,
        address TEXT,
        department TEXT,
        designation TEXT,
        salary REAL,
        joining_date TEXT

    )
    """)

    connection.commit()

    connection.close()

create_staff_table()

print("Staff Table Ready.")

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

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO staff
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        staff_id,
        staff_name,
        mobile,
        email,
        "",
        department,
        designation,
        salary,
        joining_date.strftime("%d-%m-%Y %I:%M:%S %p")
    ))

    connection.commit()

    connection.close()

def get_next_staff_id():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM staff")

    count = cursor.fetchone()[0]

    connection.close()

    return f"EMP{1001 + count}"

def view_staff():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM staff")

    staffs = cursor.fetchall()

    connection.close()

    if not staffs:

        print("No Staff Found.")
        return

    print("=" * 60)
    print("              STAFF LIST")
    print("=" * 60)

    for staff in staffs:

        print(f"Staff ID     : {staff['staff_id']}")
        print(f"Name         : {staff['staff_name']}")
        print(f"Mobile       : {staff['mobile']}")
        print(f"Email        : {staff['email']}")
        print(f"Department   : {staff['department']}")
        print(f"Designation  : {staff['designation']}")
        print(f"Salary       : {staff['salary']}")
        print(f"Joining Date : {staff['joining_date']}")
        print("-" * 60)

def search_staff():

    print("=" * 60)
    print("            SEARCH STAFF")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM staff WHERE staff_id = ?",
        (staff_id,)
    )

    staff = cursor.fetchone()

    connection.close()

    if staff:

        print(f"Staff ID     : {staff['staff_id']}")
        print(f"Name         : {staff['staff_name']}")
        print(f"Mobile       : {staff['mobile']}")
        print(f"Email        : {staff['email']}")
        print(f"Department   : {staff['department']}")
        print(f"Designation  : {staff['designation']}")
        print(f"Salary       : {staff['salary']}")
        print(f"Joining Date : {staff['joining_date']}")

    else:

        print("Staff Not Found.")

def update_staff():

    print("=" * 60)
    print("            UPDATE STAFF")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM staff WHERE staff_id = ?",
        (staff_id,)
    )

    staff = cursor.fetchone()

    if not staff:

        print("Staff Not Found.")

        connection.close()

        return

    print("\nStaff Found\n")

    name = input("Enter New Name : ")
    mobile = input("Enter New Mobile : ")
    email = input("Enter New Email : ")
    department = input("Enter New Department : ")
    designation = input("Enter New Designation : ")
    salary = input("Enter New Salary : ")

    cursor.execute("""
    UPDATE staff
    SET staff_name = ?,
        mobile = ?,
        email = ?,
        department = ?,
        designation = ?,
        salary = ?
    WHERE staff_id = ?
    """, (
        name,
        mobile,
        email,
        department,
        designation,
        salary,
        staff_id
    ))

    connection.commit()

    connection.close()

    print("\nStaff Updated Successfully.")

def delete_staff():

    print("=" * 60)
    print("            DELETE STAFF")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM staff WHERE staff_id = ?",
        (staff_id,)
    )

    staff = cursor.fetchone()

    if not staff:

        print("Staff Not Found.")

        connection.close()

        return

    cursor.execute(
        "DELETE FROM staff WHERE staff_id = ?",
        (staff_id,)
    )

    connection.commit()

    connection.close()

    print("\nStaff Deleted Successfully.")

def create_attendance_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance(

        attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id TEXT,
        date TEXT,
        check_in TEXT,
        check_out TEXT,
        status TEXT

    )
    """)

    connection.commit()

    connection.close()

def staff_check_in():

    print("=" * 60)
    print("             STAFF CHECK IN")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    check_in = datetime.now()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO attendance
    (staff_id, date, check_in, check_out, status)
    VALUES (?, ?, ?, ?, ?)
    """, (
        staff_id,
        check_in.strftime("%d-%m-%Y"),
        check_in.strftime("%I:%M:%S %p"),
        "--",
        "Present"
    ))

    connection.commit()

    connection.close()

    print("\nCheck In Successful.")

def staff_check_out():

    print("=" * 60)
    print("             STAFF CHECK OUT")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    check_out = datetime.now().strftime("%I:%M:%S %p")

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    SELECT attendance_id
    FROM attendance
    WHERE staff_id = ?
      AND check_out = '--'
    ORDER BY attendance_id DESC
    LIMIT 1
    """, (staff_id,))

    record = cursor.fetchone()

    if not record:

        print("\nNo Active Check In Found.")

        connection.close()

        return

    cursor.execute("""
    UPDATE attendance
    SET check_out = ?
    WHERE attendance_id = ?
    """, (
        check_out,
        record["attendance_id"]
    ))

    connection.commit()

    connection.close()

    print("\nCheck Out Successful.")

# create_attendance_table()

def view_attendance():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM attendance")

    records = cursor.fetchall()

    connection.close()

    if not records:

        print("No Attendance Found.")
        return

    print("=" * 60)
    print("          ATTENDANCE HISTORY")
    print("=" * 60)

    for record in records:

        print(f"Staff ID   : {record['staff_id']}")
        print(f"Date       : {record['date']}")
        print(f"Check In   : {record['check_in']}")
        print(f"Check Out  : {record['check_out']}")
        print(f"Status     : {record['status']}")
        print("-" * 60)

def search_attendance():

    print("=" * 60)
    print("          SEARCH ATTENDANCE")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM attendance WHERE staff_id = ?",
        (staff_id,)
    )

    records = cursor.fetchall()

    connection.close()

    if not records:

        print("Attendance Not Found.")
        return

    for record in records:

        print(f"Staff ID   : {record['staff_id']}")
        print(f"Date       : {record['date']}")
        print(f"Check In   : {record['check_in']}")
        print(f"Check Out  : {record['check_out']}")
        print(f"Status     : {record['status']}")
        print("-" * 60)

def monthly_attendance_report():

    print("=" * 60)
    print("        MONTHLY ATTENDANCE REPORT")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT COUNT(*) AS total FROM attendance WHERE staff_id = ?",
        (staff_id,)
    )

    result = cursor.fetchone()

    connection.close()

    total_present = result["total"]

    print("-" * 60)
    print("Staff ID      :", staff_id)
    print("Present Days  :", total_present)
    print("Absent Days   : Under Development")
    print("Working Hours : Under Development")
    print("-" * 60)

def create_salary_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS salary(

        salary_id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id TEXT,
        staff_name TEXT,
        department TEXT,
        basic_salary REAL,
        bonus REAL,
        deduction REAL,
        net_salary REAL

    )
    """)

    connection.commit()

    connection.close()

def save_salary(
    staff_id,
    staff_name,
    department,
    basic_salary,
    bonus,
    deduction,
    net_salary
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO salary
    (
        staff_id,
        staff_name,
        department,
        basic_salary,
        bonus,
        deduction,
        net_salary
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        staff_id,
        staff_name,
        department,
        basic_salary,
        bonus,
        deduction,
        net_salary
    ))

    connection.commit()

    connection.close()

def view_salary():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM salary")

    records = cursor.fetchall()

    connection.close()

    if not records:

        print("No Salary Record Found.")
        return

    print("=" * 60)
    print("            SALARY LIST")
    print("=" * 60)

    for record in records:

        print(f"Staff ID      : {record['staff_id']}")
        print(f"Name          : {record['staff_name']}")
        print(f"Department    : {record['department']}")
        print(f"Basic Salary  : {record['basic_salary']}")
        print(f"Bonus         : {record['bonus']}")
        print(f"Deduction     : {record['deduction']}")
        print(f"Net Salary    : {record['net_salary']}")
        print("-" * 60)

def search_salary():

    print("=" * 60)
    print("           SEARCH SALARY")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM salary WHERE staff_id = ?",
        (staff_id,)
    )

    records = cursor.fetchall()

    connection.close()

    if not records:

        print("Salary Record Not Found.")
        return

    for record in records:

        print(f"Staff ID      : {record['staff_id']}")
        print(f"Name          : {record['staff_name']}")
        print(f"Department    : {record['department']}")
        print(f"Basic Salary  : {record['basic_salary']}")
        print(f"Bonus         : {record['bonus']}")
        print(f"Deduction     : {record['deduction']}")
        print(f"Net Salary    : {record['net_salary']}")
        print("-" * 60)

def update_salary():

    print("=" * 60)
    print("           UPDATE SALARY")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM salary WHERE staff_id = ?",
        (staff_id,)
    )

    record = cursor.fetchone()

    if not record:

        print("Salary Record Not Found.")
        connection.close()
        return

    print("\nSalary Record Found\n")

    staff_name = input("Enter Staff Name : ")
    department = input("Enter Department : ")

    basic_salary = float(input("Enter Basic Salary : "))
    bonus = float(input("Enter Bonus : "))
    deduction = float(input("Enter Deduction : "))

    net_salary = basic_salary + bonus - deduction

    cursor.execute("""
        UPDATE salary
        SET
            staff_name = ?,
            department = ?,
            basic_salary = ?,
            bonus = ?,
            deduction = ?,
            net_salary = ?
        WHERE staff_id = ?
    """, (
        staff_name,
        department,
        basic_salary,
        bonus,
        deduction,
        net_salary,
        staff_id
    ))

    connection.commit()
    connection.close()

    print("\nSalary Updated Successfully.")

def delete_salary():

    print("=" * 60)
    print("           DELETE SALARY")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM salary WHERE staff_id = ?",
        (staff_id,)
    )

    record = cursor.fetchone()

    if not record:

        print("Salary Record Not Found.")

        connection.close()

        return

    cursor.execute(
        "DELETE FROM salary WHERE staff_id = ?",
        (staff_id,)
    )

    connection.commit()

    connection.close()

    print("\nSalary Deleted Successfully.")

def create_payroll_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payroll(

        payroll_id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id TEXT,
        staff_name TEXT,
        department TEXT,
        basic_salary REAL,
        bonus REAL,
        deduction REAL,
        net_salary REAL,
        payroll_status TEXT

    )
    """)

    connection.commit()

    connection.close()

def generate_payroll():

    print("=" * 60)
    print("           MONTHLY PAYROLL")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM salary WHERE staff_id = ?",
        (staff_id,)
    )

    record = cursor.fetchone()

    if not record:

        print("Salary Record Not Found.")

        connection.close()

        return

    cursor.execute("""
    INSERT INTO payroll(
        staff_id,
        staff_name,
        department,
        basic_salary,
        bonus,
        deduction,
        net_salary,
        payroll_status
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record["staff_id"],
        record["staff_name"],
        record["department"],
        record["basic_salary"],
        record["bonus"],
        record["deduction"],
        record["net_salary"],
        "Generated"
    ))

    connection.commit()

    connection.close()

    print("\nPayroll Generated Successfully.")

def view_payroll():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM payroll")

    records = cursor.fetchall()

    connection.close()

    if not records:

        print("No Payroll Found.")
        return

    print("=" * 60)
    print("           PAYROLL HISTORY")
    print("=" * 60)

    for record in records:

        print(f"Staff ID      : {record['staff_id']}")
        print(f"Name          : {record['staff_name']}")
        print(f"Department    : {record['department']}")
        print(f"Basic Salary  : {record['basic_salary']}")
        print(f"Bonus         : {record['bonus']}")
        print(f"Deduction     : {record['deduction']}")
        print(f"Net Salary    : {record['net_salary']}")
        print(f"Status        : {record['payroll_status']}")
        print("-" * 60)

def search_payroll():

    print("=" * 60)
    print("          SEARCH PAYROLL")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM payroll WHERE staff_id = ?",
        (staff_id,)
    )

    records = cursor.fetchall()

    connection.close()

    if not records:

        print("Payroll Not Found.")
        return

    for record in records:

        print(f"Staff ID      : {record['staff_id']}")
        print(f"Name          : {record['staff_name']}")
        print(f"Department    : {record['department']}")
        print(f"Basic Salary  : {record['basic_salary']}")
        print(f"Bonus         : {record['bonus']}")
        print(f"Deduction     : {record['deduction']}")
        print(f"Net Salary    : {record['net_salary']}")
        print(f"Status        : {record['payroll_status']}")
        print("-" * 60)

def delete_payroll():

    print("=" * 60)
    print("          DELETE PAYROLL")
    print("=" * 60)

    staff_id = input("Enter Staff ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM payroll WHERE staff_id = ?",
        (staff_id,)
    )

    record = cursor.fetchone()

    if not record:

        print("Payroll Not Found.")

        connection.close()

        return

    cursor.execute(
        "DELETE FROM payroll WHERE staff_id = ?",
        (staff_id,)
    )

    connection.commit()

    connection.close()

    print("Payroll Deleted Successfully.")

def create_department_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS department(

        department_id TEXT PRIMARY KEY,
        department_name TEXT

    )
    """)

    connection.commit()

    connection.close()

def save_department(department_id, department_name):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO department(
        department_id,
        department_name
    )
    VALUES (?, ?)
    """, (
        department_id,
        department_name
    ))

    connection.commit()

    connection.close()

def view_department():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM department")

    records = cursor.fetchall()

    connection.close()

    if not records:

        print("No Department Found.")
        return

    print("=" * 60)
    print("        DEPARTMENT LIST")
    print("=" * 60)

    for record in records:

        print(f"Department ID   : {record['department_id']}")
        print(f"Department Name : {record['department_name']}")
        print("-" * 60)

def search_department():

    print("=" * 60)
    print("        SEARCH DEPARTMENT")
    print("=" * 60)

    department_id = input("Enter Department ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM department WHERE department_id = ?",
        (department_id,)
    )

    record = cursor.fetchone()

    connection.close()

    if not record:

        print("Department Not Found.")
        return

    print("=" * 60)
    print(f"Department ID   : {record['department_id']}")
    print(f"Department Name : {record['department_name']}")
    print("=" * 60)

def update_department():

    print("=" * 60)
    print("        UPDATE DEPARTMENT")
    print("=" * 60)

    department_id = input("Enter Department ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM department WHERE department_id = ?",
        (department_id,)
    )

    record = cursor.fetchone()

    if not record:

        print("Department Not Found.")

        connection.close()

        return

    department_name = input("Enter New Department Name : ")

    cursor.execute("""
    UPDATE department
    SET department_name = ?
    WHERE department_id = ?
    """, (
        department_name,
        department_id
    ))

    connection.commit()

    connection.close()

    print("Department Updated Successfully.")

def delete_department():

    print("=" * 60)
    print("        DELETE DEPARTMENT")
    print("=" * 60)

    department_id = input("Enter Department ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM department WHERE department_id = ?",
        (department_id,)
    )

    record = cursor.fetchone()

    if not record:

        print("Department Not Found.")

        connection.close()

        return

    cursor.execute(
        "DELETE FROM department WHERE department_id = ?",
        (department_id,)
    )

    connection.commit()

    connection.close()

    print("Department Deleted Successfully.")

def create_orders_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders(

        order_id TEXT PRIMARY KEY,
        order_date TEXT,
        order_time TEXT,
        customer_name TEXT,
        customer_mobile TEXT,
        table_number TEXT,
        cart TEXT

    )
    """)

    connection.commit()

    connection.close()

def save_order(
    cart,
    order_id,
    order_time,
    customer_name,
    customer_mobile,
    table_number
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO orders(
        order_id,
        order_date,
        order_time,
        customer_name,
        customer_mobile,
        table_number,
        cart
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id,
        order_time.strftime("%d-%m-%Y"),
        order_time.strftime("%I:%M:%S %p"),
        customer_name,
        customer_mobile,
        table_number,
        json.dumps(cart)
    ))

    connection.commit()

    connection.close()

def view_orders():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM orders")

    records = cursor.fetchall()

    connection.close()

    if not records:

        print("No Orders Found.")
        return

    print("=" * 40)
    print("      ORDER HISTORY")
    print("=" * 40)

    import json

    for record in records:

        print(f"Order ID : {record['order_id']}")
        print(f"Date : {record['order_date']}")
        print(f"Time : {record['order_time']}")
        print(f"Customer : {record['customer_name']}")
        print(f"Mobile : {record['customer_mobile']}")
        print(f"Table No : {record['table_number']}")
        print("-" * 40)

        cart = json.loads(record["cart"])

        for item in cart:

            print(
                f"{item['name']} x{item['quantity']} = ₹{item['subtotal']}"
            )

        print("=" * 40)

import json

def search_order():

    print("=" * 40)
    print("      SEARCH ORDER")
    print("=" * 40)

    search = input("Enter Food Name : ").lower()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM orders")

    records = cursor.fetchall()

    connection.close()

    found = False

    for record in records:

        cart = json.loads(record["cart"])

        for item in cart:

            if search in item["name"].lower():

                print("=" * 40)
                print(f"Order ID : {record['order_id']}")
                print(f"Date : {record['order_date']}")
                print(f"Time : {record['order_time']}")
                print(f"Customer : {record['customer_name']}")
                print(f"Mobile : {record['customer_mobile']}")
                print(f"Table No : {record['table_number']}")
                print("-" * 40)

                for food in cart:

                    print(
                        f"{food['name']} x{food['quantity']} = ₹{food['subtotal']}"
                    )

                print("=" * 40)

                found = True
                break

    if not found:

        print("Order Not Found.")

def delete_order():

    print("=" * 40)
    print("      DELETE ORDER")
    print("=" * 40)

    order_id = input("Enter Order ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM orders WHERE order_id = ?",
        (order_id,)
    )

    connection.commit()

    if cursor.rowcount > 0:

        print("Order Deleted Successfully.")

    else:

        print("Order Not Found.")

    connection.close()

def create_room_bookings_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS room_bookings(

        booking_id TEXT PRIMARY KEY,
        booking_date TEXT,
        booking_time TEXT,
        customer_name TEXT,
        customer_mobile TEXT,
        room_number TEXT,
        room_type TEXT,
        room_price REAL,
        days INTEGER,
        subtotal REAL,
        gst REAL,
        grand_total REAL

    )
    """)

    connection.commit()

    connection.close()

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

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO room_bookings(

        booking_id,
        booking_date,
        booking_time,
        customer_name,
        customer_mobile,
        room_number,
        room_type,
        room_price,
        days,
        subtotal,
        gst,
        grand_total

    )

    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)

    """, (

        booking_id,
        booking_time.strftime("%d-%m-%Y"),
        booking_time.strftime("%I:%M:%S %p"),
        customer_name,
        customer_mobile,
        room_choice,
        room_type,
        room_price,
        days,
        total,
        gst,
        grand_total

    ))

    connection.commit()

    connection.close()

def view_room_bookings():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM room_bookings")

    records = cursor.fetchall()

    connection.close()

    if not records:

        print("No Room Bookings Found.")
        return

    print("=" * 50)
    print("      ROOM BOOKING HISTORY")
    print("=" * 50)

    for record in records:

        print(f"Booking ID : {record['booking_id']}")
        print(f"Date : {record['booking_date']}")
        print(f"Time : {record['booking_time']}")

        print("-" * 50)

        print(f"Customer : {record['customer_name']}")
        print(f"Mobile : {record['customer_mobile']}")

        print("-" * 50)

        print(f"Room Number : {record['room_number']}")
        print(f"Room Type : {record['room_type']}")
        print(f"Price/Night : ₹{record['room_price']}")
        print(f"Days : {record['days']}")

        print("-" * 50)

        print(f"Subtotal : ₹{record['subtotal']}")
        print(f"GST : ₹{record['gst']}")
        print(f"Grand Total : ₹{record['grand_total']}")

        print("=" * 50)

def search_room_booking():

    print("=" * 50)
    print("      SEARCH ROOM BOOKING")
    print("=" * 50)

    booking_id = input("Enter Booking ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM room_bookings WHERE booking_id = ?",
        (booking_id,)
    )

    record = cursor.fetchone()

    connection.close()

    if record:

        print("=" * 50)

        print(f"Booking ID : {record['booking_id']}")
        print(f"Date : {record['booking_date']}")
        print(f"Time : {record['booking_time']}")

        print("-" * 50)

        print(f"Customer : {record['customer_name']}")
        print(f"Mobile : {record['customer_mobile']}")

        print("-" * 50)

        print(f"Room Number : {record['room_number']}")
        print(f"Room Type : {record['room_type']}")
        print(f"Price/Night : ₹{record['room_price']}")
        print(f"Days : {record['days']}")

        print("-" * 50)

        print(f"Subtotal : ₹{record['subtotal']}")
        print(f"GST : ₹{record['gst']}")
        print(f"Grand Total : ₹{record['grand_total']}")

        print("=" * 50)

    else:

        print("Booking Not Found.")

def delete_room_booking():

    print("=" * 50)
    print("      DELETE ROOM BOOKING")
    print("=" * 50)

    booking_id = input("Enter Booking ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT room_number FROM room_bookings WHERE booking_id = ?",
        (booking_id,)
    )

    room = cursor.fetchone()

    if room:

        release_room(room["room_number"])

    cursor.execute(
        "DELETE FROM room_bookings WHERE booking_id = ?",
        (booking_id,)
    )

    connection.commit()

    if cursor.rowcount > 0:

        print("Room Booking Deleted Successfully.")

    else:

        print("Booking Not Found.")

    connection.close()

def create_rooms_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms(

        room_number TEXT PRIMARY KEY,
        room_type TEXT NOT NULL,
        room_price REAL NOT NULL,
        room_status TEXT NOT NULL

    )
    """)

    connection.commit()

    connection.close()

def insert_default_rooms():

    connection = get_connection()

    cursor = connection.cursor()

    rooms = [

        ("101", "Standard", 1000, "Available"),
        ("102", "Standard", 1000, "Available"),
        ("103", "Standard", 1000, "Available"),

        ("201", "Deluxe", 1800, "Available"),
        ("202", "Deluxe", 1800, "Available"),
        ("203", "Deluxe", 1800, "Available"),

        ("301", "Suite", 3000, "Available"),
        ("302", "Suite", 3000, "Available")

    ]

    cursor.executemany("""

        INSERT OR IGNORE INTO rooms(

            room_number,
            room_type,
            room_price,
            room_status

        )

        VALUES(?,?,?,?)

    """, rooms)

    connection.commit()

    connection.close()

def view_rooms():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT * FROM rooms
        ORDER BY room_number
    """)

    rooms = cursor.fetchall()

    connection.close()

    print("=" * 65)
    print("                    HOTEL ROOMS")
    print("=" * 65)

    print(
        f"{'Room':<10}"
        f"{'Type':<15}"
        f"{'Price':<15}"
        f"{'Status':<15}"
    )

    print("-" * 65)

    for room in rooms:

        print(
            f"{room['room_number']:<10}"
            f"{room['room_type']:<15}"
            f"₹{room['room_price']:<14}"
            f"{room['room_status']:<15}"
        )

    print("=" * 65)

def check_room_available(room_number):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT room_status
        FROM rooms
        WHERE room_number = ?

    """, (room_number,))

    room = cursor.fetchone()

    connection.close()

    if room is None:

        return False

    return room["room_status"] == "Available"

def book_room(room_number):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        UPDATE rooms

        SET room_status = ?

        WHERE room_number = ?

    """, ("Booked", room_number))

    connection.commit()

    connection.close()

def get_all_rooms():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT *

        FROM rooms

        ORDER BY room_number

    """)

    rooms = cursor.fetchall()

    connection.close()

    return rooms

def get_room_by_number(room_number):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT *

        FROM rooms

        WHERE room_number = ?

    """, (room_number,))

    room = cursor.fetchone()

    connection.close()

    return room

def release_room(room_number):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        UPDATE rooms

        SET room_status = ?

        WHERE room_number = ?

    """, ("Available", room_number))

    connection.commit()

    connection.close()

def create_tables_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tables(

        table_number TEXT PRIMARY KEY,
        table_capacity INTEGER NOT NULL,
        table_status TEXT NOT NULL

    )
    """)

    connection.commit()

    connection.close()

def insert_default_tables():

    connection = get_connection()

    cursor = connection.cursor()

    tables = [

        ("T1", 2, "Available"),
        ("T2", 2, "Available"),

        ("T3", 4, "Available"),
        ("T4", 4, "Available"),

        ("T5", 6, "Available"),
        ("T6", 6, "Available"),

        ("T7", 8, "Available"),
        ("T8", 8, "Available")

    ]

    cursor.executemany("""

        INSERT OR IGNORE INTO tables(

            table_number,
            table_capacity,
            table_status

        )

        VALUES(?,?,?)

    """, tables)

    connection.commit()

    connection.close()

def view_tables():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT *

        FROM tables

        ORDER BY table_number

    """)

    tables = cursor.fetchall()

    connection.close()

    print("=" * 65)
    print("                  HOTEL TABLES")
    print("=" * 65)

    print(
        f"{'Table':<12}"
        f"{'Capacity':<15}"
        f"{'Status':<15}"
    )

    print("-" * 65)

    for table in tables:

        print(
            f"{table['table_number']:<12}"
            f"{table['table_capacity']:<15}"
            f"{table['table_status']:<15}"
        )

    print("=" * 65)

def check_table_available(table_number):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT table_status

        FROM tables

        WHERE table_number = ?

    """, (table_number,))

    table = cursor.fetchone()

    connection.close()

    if table is None:

        return False

    return table["table_status"] == "Available"

def book_table(table_number):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        UPDATE tables

        SET table_status = ?

        WHERE table_number = ?

    """, ("Booked", table_number))

    connection.commit()

    connection.close()

def is_table_booked(table_number):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT status
        FROM tables
        WHERE table_number = ?
        """,
        (table_number,)
    )

    table = cursor.fetchone()

    connection.close()

    if table and table["status"] == "Booked":

        return True

    return False

def release_table(table_number):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        UPDATE tables

        SET table_status = ?

        WHERE table_number = ?

    """, ("Available", table_number))

    connection.commit()

    connection.close()

def get_all_tables():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT *

        FROM tables

        ORDER BY table_number

    """)

    tables = cursor.fetchall()

    connection.close()

    return tables

def get_table_by_number(table_number):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        SELECT *

        FROM tables

        WHERE table_number = ?

    """, (table_number,))

    table = cursor.fetchone()

    connection.close()

    return table

def save_table_booking(
    booking_id,
    booking_time,
    customer_name,
    customer_mobile,
    table_number,
    persons
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        INSERT INTO table_bookings(

            booking_id,
            booking_date,
            booking_time,
            customer_name,
            customer_mobile,
            table_number,
            persons

        )

        VALUES(?,?,?,?,?,?,?)

    """, (

        booking_id,
        booking_time.strftime("%d-%m-%Y"),
        booking_time.strftime("%I:%M:%S %p"),
        customer_name,
        customer_mobile,
        table_number,
        persons

    ))

    connection.commit()

    connection.close()

def create_table_bookings_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS table_bookings(

            booking_id TEXT PRIMARY KEY,
            booking_date TEXT,
            booking_time TEXT,
            customer_name TEXT,
            customer_mobile TEXT,
            table_number TEXT,
            persons INTEGER

        )

    """)

    connection.commit()

    connection.close()

def delete_table_booking():

    print("=" * 50)
    print("      DELETE TABLE BOOKING")
    print("=" * 50)

    booking_id = input("Enter Booking ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT table_number FROM table_bookings WHERE booking_id = ?",
        (booking_id,)
    )

    booking = cursor.fetchone()

    if booking:

        table_number = booking["table_number"]

        cursor.execute(
            "DELETE FROM table_bookings WHERE booking_id = ?",
            (booking_id,)
        )

        connection.commit()

        release_table(table_number)

        print("Table Booking Deleted Successfully.")

    else:

        print("Booking Not Found.")

    connection.close()

def view_table_bookings():

    print("=" * 50)
    print("      TABLE BOOKING HISTORY")
    print("=" * 50)

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM table_bookings
        ORDER BY booking_date DESC, booking_time DESC
    """)

    bookings = cursor.fetchall()

    if bookings:

        for booking in bookings:

            print("=" * 50)
            print("Booking ID   :", booking["booking_id"])
            print("Date         :", booking["booking_date"])
            print("Time         :", booking["booking_time"])
            print("-" * 50)
            print("Customer     :", booking["customer_name"])
            print("Mobile       :", booking["customer_mobile"])
            print("-" * 50)
            print("Table Number :", booking["table_number"])
            print("Persons      :", booking["persons"])
            print("=" * 50)

    else:

        print("No Table Bookings Found.")

    connection.close()

def search_table_booking():

    print("=" * 50)
    print("      SEARCH TABLE BOOKING")
    print("=" * 50)

    booking_id = input("Enter Booking ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM table_bookings WHERE booking_id = ?",
        (booking_id,)
    )

    booking = cursor.fetchone()

    if booking:

        print("=" * 50)
        print("Booking ID   :", booking["booking_id"])
        print("Date         :", booking["booking_date"])
        print("Time         :", booking["booking_time"])
        print("-" * 50)
        print("Customer     :", booking["customer_name"])
        print("Mobile       :", booking["customer_mobile"])
        print("-" * 50)
        print("Table Number :", booking["table_number"])
        print("Persons      :", booking["persons"])
        print("=" * 50)

    else:

        print("Booking Not Found.")

    connection.close()

def create_table_bookings_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS table_bookings(

        booking_id TEXT PRIMARY KEY,
        booking_date TEXT,
        booking_time TEXT,
        customer_name TEXT,
        customer_mobile TEXT,
        table_number TEXT,
        persons INTEGER

    )
    """)

    connection.commit()

    connection.close()

def create_hotel_information_table():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hotel_information(

        id INTEGER PRIMARY KEY,

        hotel_name TEXT,
        hotel_owner TEXT,
        hotel_type TEXT,
        hotel_established TEXT,
        hotel_description TEXT,

        hotel_address TEXT,
        hotel_city TEXT,
        hotel_state TEXT,
        hotel_country TEXT,
        hotel_pincode TEXT,

        hotel_mobile TEXT,
        hotel_email TEXT,
        hotel_website TEXT,
        hotel_rating TEXT,

        total_rooms INTEGER,

        restaurant TEXT,
        parking TEXT,
        wifi TEXT,
        laundry TEXT,

        hotel_checkin_time TEXT,
        hotel_checkout_time TEXT,
        hotel_opening TEXT,
        hotel_closing TEXT,

        hotel_currency TEXT,
        hotel_support_email TEXT,
        hotel_support_mobile TEXT

    )
    """)

    connection.commit()
    connection.close()

def save_hotel_information(
    hotel_name,
    hotel_owner,
    hotel_type,
    hotel_established,
    hotel_description,
    hotel_address,
    hotel_city,
    hotel_state,
    hotel_country,
    hotel_pincode,
    hotel_mobile,
    hotel_email,
    hotel_website,
    hotel_rating,
    total_rooms,
    restaurant,
    parking,
    wifi,
    laundry,
    hotel_checkin_time,
    hotel_checkout_time,
    hotel_opening,
    hotel_closing,
    hotel_currency,
    hotel_support_email,
    hotel_support_mobile
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO hotel_information(
        id,
        hotel_name,
        hotel_owner,
        hotel_type,
        hotel_established,
        hotel_description,
        hotel_address,
        hotel_city,
        hotel_state,
        hotel_country,
        hotel_pincode,
        hotel_mobile,
        hotel_email,
        hotel_website,
        hotel_rating,
        total_rooms,
        restaurant,
        parking,
        wifi,
        laundry,
        hotel_checkin_time,
        hotel_checkout_time,
        hotel_opening,
        hotel_closing,
        hotel_currency,
        hotel_support_email,
        hotel_support_mobile
    )
    VALUES(
        1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    )
    """, (
        hotel_name,
        hotel_owner,
        hotel_type,
        hotel_established,
        hotel_description,
        hotel_address,
        hotel_city,
        hotel_state,
        hotel_country,
        hotel_pincode,
        hotel_mobile,
        hotel_email,
        hotel_website,
        hotel_rating,
        total_rooms,
        restaurant,
        parking,
        wifi,
        laundry,
        hotel_checkin_time,
        hotel_checkout_time,
        hotel_opening,
        hotel_closing,
        hotel_currency,
        hotel_support_email,
        hotel_support_mobile
    ))

    connection.commit()
    connection.close()

def initialize_hotel_information():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM hotel_information
    """)

    count = cursor.fetchone()[0]

    connection.close()

    if count > 0:
        return

    save_hotel_information(
        "YADAV HOTEL",
        "Sandeep Yadav",
        "Luxury Hotel",
        "2026",
        "Premium Hotel with Restaurant, Rooms and Banquet",
        "Alwar, Rajasthan",
        "Alwar",
        "Rajasthan",
        "India",
        "301001",
        "9876543210",
        "info@yadavhotel.com",
        "www.yadavhotel.com",
        "4.8/5",
        50,
        "Available",
        "Available",
        "Available",
        "Available",
        "12:00 PM",
        "11:00 AM",
        "08:00 AM",
        "11:00 PM",
        "INR",
        "support@yadavhotel.com",
        "9876543210"
    )

def get_hotel_information():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM hotel_information WHERE id = 1"
    )

    hotel = cursor.fetchone()

    connection.close()

    return hotel

def update_hotel_information(
    hotel_name,
    hotel_owner,
    hotel_type,
    hotel_established,
    hotel_description,
    hotel_address,
    hotel_city,
    hotel_state,
    hotel_country,
    hotel_pincode,
    hotel_mobile,
    hotel_email,
    hotel_website,
    hotel_rating,
    total_rooms,
    restaurant,
    parking,
    wifi,
    laundry,
    hotel_checkin_time,
    hotel_checkout_time,
    hotel_opening,
    hotel_closing,
    hotel_currency,
    hotel_support_email,
    hotel_support_mobile
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE hotel_information
        SET
            hotel_name = ?,
            hotel_owner = ?,
            hotel_type = ?,
            hotel_established = ?,
            hotel_description = ?,
            hotel_address = ?,
            hotel_city = ?,
            hotel_state = ?,
            hotel_country = ?,
            hotel_pincode = ?,
            hotel_mobile = ?,
            hotel_email = ?,
            hotel_website = ?,
            hotel_rating = ?,
            total_rooms = ?,
            restaurant = ?,
            parking = ?,
            wifi = ?,
            laundry = ?,
            hotel_checkin_time = ?,
            hotel_checkout_time = ?,
            hotel_opening = ?,
            hotel_closing = ?,
            hotel_currency = ?,
            hotel_support_email = ?,
            hotel_support_mobile = ?
        WHERE id = 1
    """, (
        hotel_name,
        hotel_owner,
        hotel_type,
        hotel_established,
        hotel_description,
        hotel_address,
        hotel_city,
        hotel_state,
        hotel_country,
        hotel_pincode,
        hotel_mobile,
        hotel_email,
        hotel_website,
        hotel_rating,
        total_rooms,
        restaurant,
        parking,
        wifi,
        laundry,
        hotel_checkin_time,
        hotel_checkout_time,
        hotel_opening,
        hotel_closing,
        hotel_currency,
        hotel_support_email,
        hotel_support_mobile
    ))

    connection.commit()
    connection.close()

def is_room_booked(room_number):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT status
        FROM rooms
        WHERE room_number = ?
        """,
        (room_number,)
    )

    room = cursor.fetchone()

    connection.close()

    if room and room["status"] == "Booked":

        return True

    return False

def create_expenses_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses(

        expense_id TEXT PRIMARY KEY,
        expense_date TEXT,
        expense_time TEXT,
        expense_name TEXT,
        amount REAL,
        category TEXT,
        description TEXT

    )
    """)

    connection.commit()

    connection.close()

def save_expense(
    expense_id,
    expense_date,
    expense_time,
    expense_name,
    amount,
    category,
    description
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO expenses(

        expense_id,
        expense_date,
        expense_time,
        expense_name,
        amount,
        category,
        description

    )

    VALUES(?, ?, ?, ?, ?, ?, ?)
    """,

    (
        expense_id,
        expense_date,
        expense_time,
        expense_name,
        amount,
        category,
        description
    ))

    connection.commit()

    connection.close()

def view_expenses():

    print("=" * 50)
    print("          EXPENSE HISTORY")
    print("=" * 50)

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM expenses
        ORDER BY expense_date DESC, expense_time DESC
    """)

    expenses = cursor.fetchall()

    if expenses:

        for expense in expenses:

            print("=" * 50)
            print("Expense ID  :", expense["expense_id"])
            print("Date        :", expense["expense_date"])
            print("Time        :", expense["expense_time"])
            print("-" * 50)
            print("Name        :", expense["expense_name"])
            print("Amount      :", expense["amount"])
            print("Category    :", expense["category"])
            print("Description :", expense["description"])
            print("=" * 50)

    else:

        print("No Expenses Found.")

    connection.close()

def search_expense():

    print("=" * 50)
    print("         SEARCH EXPENSE")
    print("=" * 50)

    expense_id = input("Enter Expense ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM expenses WHERE expense_id = ?",
        (expense_id,)
    )

    expense = cursor.fetchone()

    if expense:

        print("=" * 50)
        print("Expense ID  :", expense["expense_id"])
        print("Date        :", expense["expense_date"])
        print("Time        :", expense["expense_time"])
        print("-" * 50)
        print("Name        :", expense["expense_name"])
        print("Amount      :", expense["amount"])
        print("Category    :", expense["category"])
        print("Description :", expense["description"])
        print("=" * 50)

    else:

        print("Expense Not Found.")

    connection.close()

def update_expense():

    print("=" * 50)
    print("         UPDATE EXPENSE")
    print("=" * 50)

    expense_id = input("Enter Expense ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM expenses WHERE expense_id = ?",
        (expense_id,)
    )

    expense = cursor.fetchone()

    if expense:

        expense_name = input(
            f"Expense Name ({expense['expense_name']}) : "
        ) or expense["expense_name"]

        amount = input(
            f"Amount ({expense['amount']}) : "
        ) or expense["amount"]

        category = input(
            f"Category ({expense['category']}) : "
        ) or expense["category"]

        description = input(
            f"Description ({expense['description']}) : "
        ) or expense["description"]

        cursor.execute("""
        UPDATE expenses
        SET
            expense_name = ?,
            amount = ?,
            category = ?,
            description = ?
        WHERE expense_id = ?
        """,
        (
            expense_name,
            amount,
            category,
            description,
            expense_id
        ))

        connection.commit()

        print("Expense Updated Successfully.")

    else:

        print("Expense Not Found.")

    connection.close()

def delete_expense():

    print("=" * 50)
    print("         DELETE EXPENSE")
    print("=" * 50)

    expense_id = input("Enter Expense ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM expenses WHERE expense_id = ?",
        (expense_id,)
    )

    expense = cursor.fetchone()

    if expense:

        cursor.execute(
            "DELETE FROM expenses WHERE expense_id = ?",
            (expense_id,)
        )

        connection.commit()

        print("Expense Deleted Successfully.")

    else:

        print("Expense Not Found.")

    connection.close()

def create_feedback_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback(

        feedback_id TEXT PRIMARY KEY,
        customer_name TEXT,
        customer_mobile TEXT,
        rating INTEGER,
        feedback TEXT,
        feedback_date TEXT,
        feedback_time TEXT

    )
    """)

    connection.commit()

    connection.close()

def save_feedback(
    feedback_id,
    customer_name,
    mobile,
    rating,
    review
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO feedback(

        feedback_id,
        customer_name,
        customer_mobile,
        rating,
        feedback

    )

    VALUES(?, ?, ?, ?, ?)
    """,

    (
        feedback_id,
        customer_name,
        mobile,
        rating,
        review
    ))

    connection.commit()

    connection.close()

def view_feedback():

    print("=" * 60)
    print("              FEEDBACK HISTORY")
    print("=" * 60)

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM feedback
        ORDER BY feedback_id
    """)

    feedbacks = cursor.fetchall()

    if feedbacks:

        for feedback in feedbacks:

            print("=" * 60)
            print("Feedback ID   :", feedback["feedback_id"])
            print("Customer Name :", feedback["customer_name"])
            print("Mobile        :", feedback["customer_mobile"])
            print("Rating        :", feedback["rating"])
            print("Review        :", feedback["feedback"])
            print("=" * 60)

    else:

        print("No Feedback Found.")

    connection.close()

def search_feedback():

    print("=" * 60)
    print("             SEARCH FEEDBACK")
    print("=" * 60)

    feedback_id = input("Enter Feedback ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM feedback WHERE feedback_id = ?",
        (feedback_id,)
    )

    feedback = cursor.fetchone()

    if feedback:

        print("=" * 60)
        print("Feedback ID   :", feedback["feedback_id"])
        print("Customer Name :", feedback["customer_name"])
        print("Mobile        :", feedback["customer_mobile"])
        print("Rating        :", feedback["rating"])
        print("Review        :", feedback["feedback"])
        print("=" * 60)

    else:

        print("Feedback Not Found.")

    connection.close()

def delete_feedback():

    print("=" * 60)
    print("             DELETE FEEDBACK")
    print("=" * 60)

    feedback_id = input("Enter Feedback ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM feedback WHERE feedback_id = ?",
        (feedback_id,)
    )

    feedback = cursor.fetchone()

    if feedback:

        cursor.execute(
            "DELETE FROM feedback WHERE feedback_id = ?",
            (feedback_id,)
        )

        connection.commit()

        print("Feedback Deleted Successfully.")

    else:

        print("Feedback Not Found.")

    connection.close()

def create_users_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(

        user_id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT

    )
    """)

    connection.commit()

    connection.close()

def save_user(
    user_id,
    username,
    password,
    role
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO users(

        user_id,
        username,
        password,
        role

    )

    VALUES(?, ?, ?, ?)
    """,

    (
        user_id,
        username,
        password,
        role
    ))

    connection.commit()

    connection.close()

def view_users():

    print("=" * 60)
    print("              USERS LIST")
    print("=" * 60)

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM users
        ORDER BY user_id
    """)

    users = cursor.fetchall()

    if users:

        for user in users:

            print("=" * 60)
            print("User ID  :", user["user_id"])
            print("Username :", user["username"])
            print("Role     :", user["role"])
            print("=" * 60)

    else:

        print("No Users Found.")

    connection.close()

def delete_user():

    print("=" * 60)
    print("             DELETE USER")
    print("=" * 60)

    user_id = input("Enter User ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )

    user = cursor.fetchone()

    if user:

        cursor.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,)
        )

        connection.commit()

        print("User Deleted Successfully.")

    else:

        print("User Not Found.")

    connection.close()

def verify_login(username, password):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE username = ? AND password = ?
        """,
        (username, password)
    )

    user = cursor.fetchone()

    connection.close()

    if user:

        print(f"Welcome {user['username']} ({user['role']})")

    else:

        print("Invalid Username or Password.")

def create_settings_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings(

        id INTEGER PRIMARY KEY CHECK(id = 1),
        hotel_name TEXT,
        owner_name TEXT,
        gst TEXT,
        phone TEXT,
        email TEXT

    )
    """)

    connection.commit()

    connection.close()

def save_settings(
    hotel_name,
    owner_name,
    gst,
    phone,
    email
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO settings(

        id,
        hotel_name,
        owner_name,
        gst,
        phone,
        email

    )

    VALUES(1, ?, ?, ?, ?, ?)
    """,

    (
        hotel_name,
        owner_name,
        gst,
        phone,
        email
    ))

    connection.commit()

    connection.close()

    print("Settings Saved Successfully.")

def view_settings():

    print("=" * 60)
    print("            HOTEL SETTINGS")
    print("=" * 60)

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("SELECT * FROM settings WHERE id = 1")

    settings = cursor.fetchone()

    if settings:

        print("Hotel Name :", settings["hotel_name"])
        print("Owner Name :", settings["owner_name"])
        print("GST Number :", settings["gst"])
        print("Phone      :", settings["phone"])
        print("Email      :", settings["email"])

    else:

        print("Settings Not Found.")

    connection.close()

def create_inventory_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory(

        item_id TEXT PRIMARY KEY,
        item_name TEXT,
        category TEXT,
        quantity INTEGER,
        price REAL

    )
    """)

    connection.commit()

    connection.close()

def create_supplier_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers(

        supplier_id TEXT PRIMARY KEY,
        supplier_name TEXT,
        mobile TEXT

    )
    """)

    connection.commit()

    connection.close()

def save_item(
    item_id,
    item_name,
    category,
    quantity,
    price
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO inventory(

        item_id,
        item_name,
        category,
        quantity,
        price

    )

    VALUES(?, ?, ?, ?, ?)
    """,

    (
        item_id,
        item_name,
        category,
        quantity,
        price
    ))

    connection.commit()

    connection.close()

def view_items():

    print("=" * 60)
    print("              INVENTORY")
    print("=" * 60)

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM inventory
        ORDER BY item_name
    """)

    items = cursor.fetchall()

    if items:

        for item in items:

            print("=" * 60)
            print("Item ID   :", item["item_id"])
            print("Item Name :", item["item_name"])
            print("Category  :", item["category"])
            print("Quantity  :", item["quantity"])
            print("Price     :", item["price"])
            print("=" * 60)

    else:

        print("No Items Found.")

    connection.close()

def search_item():

    item_id = input("Enter Item ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM inventory WHERE item_id = ?",
        (item_id,)
    )

    item = cursor.fetchone()

    if item:

        print("=" * 60)
        print("Item ID   :", item["item_id"])
        print("Item Name :", item["item_name"])
        print("Category  :", item["category"])
        print("Quantity  :", item["quantity"])
        print("Price     :", item["price"])
        print("=" * 60)

    else:

        print("Item Not Found.")

    connection.close()

def update_item():

    item_id = input("Enter Item ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM inventory WHERE item_id = ?",
        (item_id,)
    )

    item = cursor.fetchone()

    if item:

        item_name = input(f"Item Name ({item['item_name']}) : ") or item["item_name"]

        category = input(f"Category ({item['category']}) : ") or item["category"]

        quantity = input(f"Quantity ({item['quantity']}) : ") or item["quantity"]

        price = input(f"Price ({item['price']}) : ") or item["price"]

        cursor.execute("""
        UPDATE inventory
        SET
            item_name = ?,
            category = ?,
            quantity = ?,
            price = ?
        WHERE item_id = ?
        """,
        (
            item_name,
            category,
            quantity,
            price,
            item_id
        ))

        connection.commit()

        print("Item Updated Successfully.")

    else:

        print("Item Not Found.")

    connection.close()

def delete_item():

    item_id = input("Enter Item ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM inventory WHERE item_id = ?",
        (item_id,)
    )

    item = cursor.fetchone()

    if item:

        cursor.execute(
            "DELETE FROM inventory WHERE item_id = ?",
            (item_id,)
        )

        connection.commit()

        print("Item Deleted Successfully.")

    else:

        print("Item Not Found.")

    connection.close()

def stock_in(item_id, quantity):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE inventory
        SET quantity = quantity + ?
        WHERE item_id = ?
        """,
        (quantity, item_id)
    )

    if cursor.rowcount == 0:
        print("Item Not Found.")
    else:
        connection.commit()
        print("Stock Added Successfully.")

    connection.close()

def stock_out(item_id, quantity):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE inventory
        SET quantity = quantity - ?
        WHERE item_id = ?
        AND quantity >= ?
        """,
        (quantity, item_id, quantity)
    )

    if cursor.rowcount == 0:
        print("Item Not Found or Insufficient Stock.")
    else:
        connection.commit()
        print("Stock Removed Successfully.")

    connection.close()

def low_stock_alert():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT item_id, item_name, quantity
        FROM inventory
        WHERE quantity <= 10
        ORDER BY quantity ASC
    """)

    items = cursor.fetchall()

    print("=" * 60)
    print("           LOW STOCK ALERT")
    print("=" * 60)

    if items:
        for item in items:
            print(
                f"{item['item_id']} | "
                f"{item['item_name']} | "
                f"Stock : {item['quantity']}"
            )
    else:
        print("No Low Stock Items.")

    connection.close()

def purchase_history():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            item_id,
            item_name,
            category,
            quantity,
            price
        FROM inventory
        ORDER BY item_id
    """)

    items = cursor.fetchall()

    print("=" * 60)
    print("         PURCHASE HISTORY")
    print("=" * 60)

    if items:
        for item in items:
            print("=" * 60)
            print("Item ID   :", item["item_id"])
            print("Item Name :", item["item_name"])
            print("Category  :", item["category"])
            print("Quantity  :", item["quantity"])
            print("Price     :", item["price"])
            print("=" * 60)
    else:
        print("No Purchase History Found.")

    connection.close()

def save_supplier(
    supplier_id,
    supplier_name,
    mobile
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
    INSERT INTO suppliers(

        supplier_id,
        supplier_name,
        mobile

    )

    VALUES(?, ?, ?)
    """,

    (
        supplier_id,
        supplier_name,
        mobile
    ))

    connection.commit()

    connection.close()

def view_supplier():

    print("=" * 60)
    print("          SUPPLIERS")
    print("=" * 60)

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM suppliers
        ORDER BY supplier_name
    """)

    suppliers = cursor.fetchall()

    if suppliers:

        for supplier in suppliers:

            print("=" * 60)
            print("Supplier ID   :", supplier["supplier_id"])
            print("Supplier Name :", supplier["supplier_name"])
            print("Mobile        :", supplier["mobile"])
            print("=" * 60)

    else:

        print("No Suppliers Found.")

    connection.close()

def search_supplier():

    supplier_id = input("Enter Supplier ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM suppliers WHERE supplier_id = ?",
        (supplier_id,)
    )

    supplier = cursor.fetchone()

    if supplier:

        print("=" * 60)
        print("Supplier ID   :", supplier["supplier_id"])
        print("Supplier Name :", supplier["supplier_name"])
        print("Mobile        :", supplier["mobile"])
        print("=" * 60)

    else:

        print("Supplier Not Found.")

    connection.close()

def update_supplier():

    supplier_id = input("Enter Supplier ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM suppliers WHERE supplier_id = ?",
        (supplier_id,)
    )

    supplier = cursor.fetchone()

    if supplier:

        supplier_name = input(
            f"Supplier Name ({supplier['supplier_name']}) : "
        ) or supplier["supplier_name"]

        mobile = input(
            f"Mobile ({supplier['mobile']}) : "
        ) or supplier["mobile"]

        cursor.execute("""
        UPDATE suppliers
        SET
            supplier_name = ?,
            mobile = ?
        WHERE supplier_id = ?
        """,
        (
            supplier_name,
            mobile,
            supplier_id
        ))

        connection.commit()

        print("Supplier Updated Successfully.")

    else:

        print("Supplier Not Found.")

    connection.close()

def delete_supplier():

    supplier_id = input("Enter Supplier ID : ").upper()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM suppliers WHERE supplier_id = ?",
        (supplier_id,)
    )

    supplier = cursor.fetchone()

    if supplier:

        cursor.execute(
            "DELETE FROM suppliers WHERE supplier_id = ?",
            (supplier_id,)
        )

        connection.commit()

        print("Supplier Deleted Successfully.")

    else:

        print("Supplier Not Found.")

    connection.close()

def sales_report():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM orders
        ORDER BY order_id DESC
    """)

    orders = cursor.fetchall()

    print("=" * 60)
    print("              SALES REPORT")
    print("=" * 60)

    if not orders:
        print("No Sales Found.")
        connection.close()
        return

    for order in orders:
        print("-" * 60)

        for key in order.keys():
            print(f"{key.replace('_', ' ').title()} : {order[key]}")

    print("=" * 60)

    connection.close()

def restaurant_report():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            order_id,
            order_date,
            order_time,
            customer_name,
            customer_mobile,
            table_number,
            cart
        FROM orders
        ORDER BY order_id DESC
    """)

    orders = cursor.fetchall()

    print("=" * 60)
    print("             RESTAURANT REPORT")
    print("=" * 60)

    if not orders:
        print("No Restaurant Orders Found.")
        connection.close()
        return

    for order in orders:

        print("-" * 60)
        print("Order ID       :", order["order_id"])
        print("Date           :", order["order_date"])
        print("Time           :", order["order_time"])
        print("Customer Name  :", order["customer_name"])
        print("Mobile         :", order["customer_mobile"])
        print("Table Number   :", order["table_number"])
        print("Cart           :", order["cart"])

    print("=" * 60)

    connection.close()

def room_report():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM room_bookings
        ORDER BY booking_id DESC
    """)

    bookings = cursor.fetchall()

    print("=" * 60)
    print("           ROOM BOOKING REPORT")
    print("=" * 60)

    if not bookings:
        print("No Room Bookings Found.")
        connection.close()
        return

    for booking in bookings:

        print("-" * 60)

        for key in booking.keys():
            print(
                f"{key.replace('_', ' ').title()} : "
                f"{booking[key]}"
            )

    print("=" * 60)

    connection.close()

def table_report():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM table_bookings
        ORDER BY booking_id DESC
    """)

    bookings = cursor.fetchall()

    print("=" * 60)
    print("          TABLE BOOKING REPORT")
    print("=" * 60)

    if not bookings:
        print("No Table Bookings Found.")
        connection.close()
        return

    for booking in bookings:

        print("-" * 60)

        for key in booking.keys():
            print(
                f"{key.replace('_', ' ').title()} : "
                f"{booking[key]}"
            )

    print("=" * 60)

    connection.close()

def customer_report():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM customers
        ORDER BY customer_id DESC
    """)

    customers = cursor.fetchall()

    print("=" * 60)
    print("             CUSTOMER REPORT")
    print("=" * 60)

    if not customers:
        print("No Customers Found.")
        connection.close()
        return

    for customer in customers:

        print("-" * 60)

        for key in customer.keys():
            print(
                f"{key.replace('_', ' ').title()} : "
                f"{customer[key]}"
            )

    print("=" * 60)

    connection.close()

def staff_report():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM staff
        ORDER BY staff_id DESC
    """)

    staff_records = cursor.fetchall()

    print("=" * 60)
    print("              STAFF REPORT")
    print("=" * 60)

    if not staff_records:
        print("No Staff Found.")
        connection.close()
        return

    for staff in staff_records:

        print("-" * 60)

        for key in staff.keys():
            print(
                f"{key.replace('_', ' ').title()} : "
                f"{staff[key]}"
            )

    print("=" * 60)

    connection.close()

def salary_report():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM salary
        ORDER BY salary_id DESC
    """)

    salaries = cursor.fetchall()

    print("=" * 60)
    print("             SALARY REPORT")
    print("=" * 60)

    if not salaries:
        print("No Salary Records Found.")
        connection.close()
        return

    for salary in salaries:

        print("-" * 60)

        for key in salary.keys():
            print(
                f"{key.replace('_', ' ').title()} : "
                f"{salary[key]}"
            )

    print("=" * 60)

    connection.close()

def inventory_report():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM inventory
        ORDER BY item_id
    """)

    items = cursor.fetchall()

    print("=" * 60)
    print("            INVENTORY REPORT")
    print("=" * 60)

    if not items:
        print("No Inventory Records Found.")
        connection.close()
        return

    for item in items:

        print("-" * 60)

        for key in item.keys():
            print(
                f"{key.replace('_', ' ').title()} : "
                f"{item[key]}"
            )

    print("=" * 60)

    connection.close()

def hotel_dashboard():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM customers")
    total_customers = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM orders")
    total_orders = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM room_bookings")
    total_room_bookings = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM table_bookings")
    total_table_bookings = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM staff")
    total_staff = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM inventory")
    total_inventory_items = cursor.fetchone()["total"]

    connection.close()

    print("=" * 60)
    print("                 HOTEL DASHBOARD")
    print("=" * 60)

    print(f"Total Customers       : {total_customers}")
    print(f"Total Restaurant Orders : {total_orders}")
    print(f"Total Room Bookings   : {total_room_bookings}")
    print(f"Total Table Bookings  : {total_table_bookings}")
    print(f"Total Staff           : {total_staff}")
    print(f"Inventory Items       : {total_inventory_items}")

    print("=" * 60)

def hotel_dashboard():
    connection = get_connection()
    cursor = connection.cursor()

    tables = {
        "Restaurant Orders": "orders",
        "Room Bookings": "room_bookings",
        "Table Bookings": "table_bookings",
        "Customers": "customers",
        "Staff": "staff",
        "Departments": "department",
        "Inventory Items": "inventory",
        "Suppliers": "supplier"
    }

    results = {}

    for title, table_name in tables.items():
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        results[title] = cursor.fetchone()[0]

    connection.close()

    print("=" * 60)
    print("                 HOTEL DASHBOARD")
    print("=" * 60)

    for title, count in results.items():
        print(f"{title:<25}: {count}")

    print("=" * 60)