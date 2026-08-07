from billing import *

def settings_management():

    while True:

        print("=" * 60)
        print("         SETTINGS")
        print("=" * 60)

        print("1. Update Hotel Settings")
        print("2. View Settings")
        print("3. Back")

        choice = input("Enter Choice : ")

        if choice == "1":

            hotel_name = input("Hotel Name : ")
            owner_name = input("Owner Name : ")
            gst = input("GST Number : ")
            phone = input("Phone : ")
            email = input("Email : ")

            save_settings(
                hotel_name,
                owner_name,
                gst,
                phone,
                email
            )

        elif choice == "2":

            view_settings()

        elif choice == "3":

            break

        else:

            print("Invalid Choice")

        input("\nPress Enter...")