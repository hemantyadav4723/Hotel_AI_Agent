from db_manager import get_all_customers

customers = get_all_customers()

for customer in customers:
    print(customer["customer_id"])
    print(customer["customer_name"])
    print(customer["customer_mobile"])
    print(customer["customer_email"])
    print(customer["customer_address"])
    print(customer["created_time"])
    print("-" * 40)