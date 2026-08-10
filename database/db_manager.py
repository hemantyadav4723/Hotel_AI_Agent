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