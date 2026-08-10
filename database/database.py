from db_manager import (
    create_customers_table,
    create_staff_table,
    create_attendance_table,
    create_salary_table,
    create_payroll_table,
    create_department_table,
    create_orders_table,
    create_room_bookings_table,
    create_rooms_table,
    insert_default_rooms,
    create_tables_table,
    insert_default_tables,
    create_table_bookings_table
)

create_customers_table()
create_staff_table()
create_attendance_table()
create_salary_table()
create_payroll_table()
create_department_table()
create_orders_table()
create_room_bookings_table()
create_rooms_table()
insert_default_rooms()
create_tables_table()
insert_default_tables()
create_table_bookings_table()

print("Table Booking Table Ready.")

print("Payroll Table Ready.")
print("Room Booking Table Ready.")
print("Rooms Table Ready.")
print("Default Rooms Added.")
print("Tables Table Ready.")
print("Default Tables Ready")
print("Order Table Ready.")

from db_manager import get_connection

connection = get_connection()

cursor = connection.cursor()

cursor.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
""")

for table in cursor.fetchall():

    print(table["name"])

connection.close()