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