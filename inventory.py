from billing import *
from utils.display import*
from utils.display import *
from utils.validators import *

def inventory_management():

    while True:

        print_header("INVENTORY MANAGEMENT")

        print("1. Add Item")
        print("2. View Items")
        print("3. Search Item")
        print("4. Update Item")
        print("5. Delete Item")
        print("6. Stock In")
        print("7. Stock Out")
        print("8. Low Stock Alert")
        print("9. Purchase History")
        print("10. Supplier Management")
        print("11. Back")

        choice = validate_menu_choice(
            "Enter Your Choice : "
        ,
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
        )

        print_separator()
        print_footer()

        if choice=="1":

            item_id=input("Enter Item ID : ").upper()
            item_name=validate_name("Enter Item Name : ")
            category=input("Enter Category : ")
            quantity=validate_quantity("Enter Quantity : ")
            price=validate_price("Enter Price : ")

            save_item(
                item_id,
                item_name,
                category,
                quantity,
                price
            )

            print_success("Item Added Successfully.")

        elif choice=="2":

            view_items()

        elif choice=="3":

            search_item()

        elif choice=="4":

            update_item()

        elif choice=="5":

            delete_item()

        elif choice=="6":

            stock_in()

        elif choice=="7":

            stock_out()

        elif choice=="8":

            low_stock_alert()

        elif choice=="9":

            purchase_history()

        elif choice=="10":

            while True:

                print_header("SUPPLIER MANAGEMENT")

                print("1. Add Supplier")
                print("2. View Supplier")
                print("3. Search Supplier")
                print("4. Update Supplier")
                print("5. Delete Supplier")
                print("6. Back")

                supplier_choice = validate_menu_choice(
                    "Enter Choice : ",
                    ["1", "2", "3", "4", "5", "6"]
                )

                print_separator()
                print_footer()

                if supplier_choice == "1":

                    supplier_id = input("Supplier ID : ").upper()
                    supplier_name = validate_name("Supplier Name : ")
                    mobile = validate_mobile("Mobile : ")

                    save_supplier(
                        supplier_id,
                        supplier_name,
                        mobile
                    )

                    print_success("Supplier Added Successfully.")

                elif supplier_choice == "2":

                    view_supplier()

                elif supplier_choice == "3":

                    search_supplier()

                elif supplier_choice == "4":

                    update_supplier()

                elif supplier_choice == "5":

                    delete_supplier()

                elif supplier_choice == "6":

                    break

                press_enter()

        elif choice=="11":

            break

        press_enter()