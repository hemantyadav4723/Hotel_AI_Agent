from db_manager import (
    create_customers_table,
    create_staff_table,
    create_attendance_table,
    create_salary_table,
    create_payroll_table,
    create_department_table,
    create_orders_table,
    create_room_bookings_table,
    get_all_customers
)

create_customers_table()
create_staff_table()
create_attendance_table()
create_salary_table()
create_payroll_table()
create_department_table()
create_orders_table()
create_room_bookings_table()
print("Payroll Table Ready.")
print("Room Booking Table Ready.")

customers = get_all_customers()

for customer in customers:
    print(customer["customer_id"])
    print(customer["customer_name"])
    print(customer["customer_mobile"])
    print(customer["customer_email"])
    print(customer["customer_address"])
    print(customer["created_time"])
    print("-" * 40)

from db_manager import get_connection

connection = get_connection()

cursor = connection.cursor()

cursor.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
""")

tables = cursor.fetchall()

for table in tables:
    print(table["name"])

connection.close()

print("Order Table Ready.")