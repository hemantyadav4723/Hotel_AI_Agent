from db_manager import (
    create_customers_table,
    create_staff_table,
    create_attendance_table,
    create_salary_table,
    get_all_customers
)

create_customers_table()
create_staff_table()
create_attendance_table()
create_salary_table()

customers = get_all_customers()

for customer in customers:
    print(customer["customer_id"])
    print(customer["customer_name"])
    print(customer["customer_mobile"])
    print(customer["customer_email"])
    print(customer["customer_address"])
    print(customer["created_time"])
    print("-" * 40)