'Menu-based version of the smart parking system.'
import sys
from models import (
    Car,
    Bike,
    ParkingLot,
    ParkingSystemException,
    SlotNotAvailableException,
    InvalidVehicleException,
    TicketNotFoundException,
    VehicleAlreadyParkedException
)


def print_banner(lot: ParkingLot):
    'Prints the system header and facility status banner.'
    summary = lot.get_slot_summary()
    print("\n" + "=" * 65)
    print(f"      {lot.lot_name.upper()} - MANAGEMENT SYSTEM")
    print(f"      Location: {lot.location} | Active Slots: {summary['total_slots']}")
    print("=" * 65)
    print(f"  Cars Available: {summary['car_free']}/{summary['car_total']} | "
          f"Bikes Available: {summary['bike_free']}/{summary['bike_total']} | "
          f"Total Free: {summary['total_free']}")
    print("-" * 65)


def handle_vehicle_checkin(lot: ParkingLot):
    'Menu Option 1: Checks in a vehicle, allocates a slot, and prints a ticket.'
    print("\n--- [1] VEHICLE ENTRY (CHECK-IN) ---")
    vehicle_number = input("Enter vehicle registration number (e.g., MH12AB1234): ").strip()
    owner_name = input("Enter vehicle owner name: ").strip()

    print("Vehicle Types: [1] CAR (INR {:.2f}/hr) | [2] BIKE (INR {:.2f}/hr)".format(lot.car_rate, lot.bike_rate))
    choice = input("Select vehicle type (1 or 2): ").strip()

    try:
        if choice == "1" or choice.upper() == "CAR":
            vehicle = Car(vehicle_number=vehicle_number, owner_name=owner_name, hourly_rate=lot.car_rate)
        elif choice == "2" or choice.upper() == "BIKE":
            vehicle = Bike(vehicle_number=vehicle_number, owner_name=owner_name, hourly_rate=lot.bike_rate)
        else:
            print("❌ Invalid vehicle type selected. Please choose 1 (CAR) or 2 (BIKE).")
            return

        # Park vehicle (Polymorphic method call)
        ticket = lot.park_vehicle(vehicle)

        print("\n✅ VEHICLE PARKED SUCCESSFULLY!")
        print("+" + "-" * 45 + "+")
        print(f"| Ticket ID   : {ticket.ticket_id:<30} |")
        print(f"| Vehicle No  : {ticket.vehicle_number:<30} |")
        print(f"| Owner Name  : {ticket.owner_name:<30} |")
        print(f"| Vehicle Type: {ticket.vehicle_type:<30} |")
        print(f"| Slot Number : {ticket.slot_number:<30} |")
        print(f"| Entry Time  : {ticket.entry_time:<30} |")
        print(f"| Hourly Rate : INR {ticket.hourly_rate:<26.2f} |")
        print("+" + "-" * 45 + "+")
        print(f"📄 Printable entry slip saved to: receipts/Ticket_{ticket.ticket_id}_ENTRY.txt")

    except (InvalidVehicleException, SlotNotAvailableException, VehicleAlreadyParkedException) as err:
        print(f"❌ Error: {err}")
    except Exception as err:
        print(f"❌ Unexpected Error during check-in: {err}")


def handle_vehicle_checkout(lot: ParkingLot):
    'Menu Option 2: Looks up active ticket, calculates fee, processes payment, and vacates slot.'
    print("\n--- [2] VEHICLE EXIT & BILLING (CHECK-OUT) ---")
    query = input("Enter Ticket ID or Vehicle Number: ").strip()
    if not query:
        print("❌ Search query cannot be empty.")
        return

    try:
        # Search ticket
        ticket = lot.find_active_ticket(query)

        print("\nActive Ticket Found:")
        print(f"  Ticket ID   : {ticket.ticket_id}")
        print(f"  Vehicle No  : {ticket.vehicle_number} ({ticket.vehicle_type})")
        print(f"  Owner       : {ticket.owner_name}")
        print(f"  Slot        : {ticket.slot_number}")
        print(f"  Entry Time  : {ticket.entry_time}")
        print(f"  Rate        : INR {ticket.hourly_rate:.2f}/hour")

        print("\nSelect Payment Method: [1] CASH | [2] UPI | [3] CARD")
        pay_choice = input("Enter choice (1-3) [Default: 1 (CASH)]: ").strip()
        payment_methods = {"1": "CASH", "2": "UPI", "3": "CARD"}
        payment_method = payment_methods.get(pay_choice, "CASH")

        confirm = input(f"Confirm checkout for {ticket.vehicle_number}? (Y/N): ").strip().upper()
        if confirm != "Y":
            print("Checkout cancelled.")
            return

        # Complete checkout
        billable_hours, total_fee = lot.checkout_vehicle(ticket, payment_method)

        print("\n✅ CHECKOUT COMPLETED SUCCESSFULLY!")
        print("+" + "-" * 45 + "+")
        print(f"| Ticket ID   : {ticket.ticket_id:<30} |")
        print(f"| Vehicle No  : {ticket.vehicle_number:<30} |")
        print(f"| Entry Time  : {ticket.entry_time:<30} |")
        print(f"| Exit Time   : {ticket.exit_time:<30} |")
        print(f"| Duration    : {billable_hours} hour(s){'':<20} |")
        print(f"| Total Bill  : INR {total_fee:<26.2f} |")
        print(f"| Paid Via    : {payment_method:<30} |")
        print(f"| Status      : Slot {ticket.slot_number} is now VACATED{'':<11} |")
        print("+" + "-" * 45 + "+")
        print(f"📄 Printable exit receipt saved to: receipts/Ticket_{ticket.ticket_id}_EXIT.txt")

    except (TicketNotFoundException, ParkingSystemException) as err:
        print(f"❌ Error: {err}")
    except Exception as err:
        print(f"❌ Unexpected Error during check-out: {err}")


def handle_view_slots(lot: ParkingLot):
    'Menu Option 3: Displays all slots in an organized status grid.'
    print("\n--- [3] LIVE PARKING SLOTS STATUS ---")
    summary = lot.get_slot_summary()
    print(f"Overview: Total Slots: {summary['total_slots']} | "
          f"Free: {summary['total_free']} | Occupied: {summary['total_occupied']}\n")

    print("🚗 CAR SLOTS:")
    car_slots = [s for s in lot.slots if s.slot_type == "CAR"]
    for i, s in enumerate(car_slots, 1):
        status = "FREE" if s.is_available() else "OCCUPIED"
        color_marker = "[OK]" if s.is_available() else "[X]"
        print(f"  {color_marker} {s.slot_number:<6} ({status:<8})", end="")
        if i % 4 == 0:
            print()
    if len(car_slots) % 4 != 0:
        print()

    print("\n🏍️ BIKE SLOTS:")
    bike_slots = [s for s in lot.slots if s.slot_type == "BIKE"]
    for i, s in enumerate(bike_slots, 1):
        status = "FREE" if s.is_available() else "OCCUPIED"
        color_marker = "[OK]" if s.is_available() else "[X]"
        print(f"  {color_marker} {s.slot_number:<6} ({status:<8})", end="")
        if i % 4 == 0:
            print()
    if len(bike_slots) % 4 != 0:
        print()


def handle_view_records(lot: ParkingLot):
    'Menu Option 4: Displays parking logs and recent sessions.'
    print("\n--- [4] PARKING RECORDS & HISTORY ---")
    if not lot.tickets:
        print("No parking records available yet.")
        return

    print("{:<8} {:<14} {:<10} {:<6} {:<8} {:<20} {:<10} {:<10}".format(
        "TICKET", "VEHICLE", "TYPE", "SLOT", "STATUS", "ENTRY TIME", "HOURS", "FEE"
    ))
    print("-" * 90)

    # Display in reverse chronological order
    for t in reversed(lot.tickets[-25:]):
        fee_str = f"INR {t.total_fee:.2f}" if t.status == "COMPLETED" else "-"
        hours_str = str(t.chargeable_hours) if t.status == "COMPLETED" else "-"
        print("{:<8} {:<14} {:<10} {:<6} {:<8} {:<20} {:<10} {:<10}".format(
            t.ticket_id, t.vehicle_number, t.vehicle_type, t.slot_number,
            t.status, t.entry_time[:16], hours_str, fee_str
        ))
    print(f"\nTotal Records: {len(lot.tickets)} (Showing latest {min(len(lot.tickets), 25)})")


def handle_configure_lot(lot: ParkingLot):
    'Menu Option 5: Reconfigures facility name, rates, and capacity.'
    print("\n--- [5] CONFIGURE PARKING FACILITY ---")
    print(f"Current Name     : {lot.lot_name}")
    print(f"Current Location : {lot.location}")
    print(f"Current Car Rate : INR {lot.car_rate:.2f}/hour")
    print(f"Current Bike Rate: INR {lot.bike_rate:.2f}/hour")

    new_name = input("Enter new facility name (press Enter to keep current): ").strip()
    if new_name:
        lot.lot_name = new_name

    new_loc = input("Enter new location (press Enter to keep current): ").strip()
    if new_loc:
        lot.location = new_loc

    car_rate_input = input("Enter new Car hourly rate (press Enter to keep current): ").strip()
    if car_rate_input:
        try:
            rate = float(car_rate_input)
            if rate < 0:
                print("❌ Rate cannot be negative.")
            else:
                lot.car_rate = rate
        except ValueError:
            print("❌ Invalid number entered for car rate.")

    bike_rate_input = input("Enter new Bike hourly rate (press Enter to keep current): ").strip()
    if bike_rate_input:
        try:
            rate = float(bike_rate_input)
            if rate < 0:
                print("❌ Rate cannot be negative.")
            else:
                lot.bike_rate = rate
        except ValueError:
            print("❌ Invalid number entered for bike rate.")

    lot.save_to_json()
    print("✅ Facility settings updated successfully!")


def handle_export_csv(lot: ParkingLot):
    'Menu Option 6: Exports all parking records to a CSV spreadsheet file.'
    print("\n--- [6] EXPORT PARKING RECORDS TO CSV ---")
    filename = input("Enter CSV filename [default: parking_records.csv]: ").strip()
    if not filename:
        filename = "parking_records.csv"
    if not filename.endswith(".csv"):
        filename += ".csv"

    try:
        saved_path = lot.export_records_to_csv(filename)
        print(f"✅ Success! All records exported to CSV file:")
        print(f"   📁 File: {saved_path}")
    except Exception as err:
        print(f"❌ Failed to export CSV: {err}")


def handle_view_slip(lot: ParkingLot):
    'Menu Option 7: Views or regenerates text slip for any ticket.'
    print("\n--- [7] VIEW / PRINT TEXT TICKET SLIP ---")
    query = input("Enter Ticket ID to print/view: ").strip()
    if not query:
        return

    clean_query = query.upper()
    target_ticket = None
    for t in lot.tickets:
        if t.ticket_id.upper() == clean_query or t.vehicle_number == clean_query:
            target_ticket = t
            break

    if not target_ticket:
        print(f"❌ Ticket '{query}' not found.")
        return

    slip_type = "EXIT" if target_ticket.status == "COMPLETED" else "ENTRY"
    slip_file = lot.generate_text_slip(target_ticket, slip_type)

    print("\n" + "=" * 40)
    with open(slip_file, "r", encoding="utf-8") as f:
        print(f.read())
    print(f"📄 File saved at: {slip_file}")


def main():
    'Main application loop displaying the menu-driven console interface.'
    # Initialize ParkingLot instance (Loads from parking_data.json if present)
    lot = ParkingLot(
        lot_name="City Smart Parking",
        location="Main Market",
        car_capacity=10,
        bike_capacity=15,
        car_rate=30.0,
        bike_rate=15.0,
        data_file="parking_data.json"
    )

    while True:
        print_banner(lot)
        print("  [1] Park a Vehicle (Check-In)")
        print("  [2] Exit a Vehicle & Pay Bill (Check-Out)")
        print("  [3] View Live Parking Slots Status")
        print("  [4] View Parking Records & History")
        print("  [5] Configure Facility (Name, Location & Rates)")
        print("  [6] Export Records to CSV File")
        print("  [7] View / Print Parking Ticket Slip")
        print("  [8] Exit System")
        print("=" * 65)

        choice = input("Enter your choice (1-8): ").strip()

        if choice == "1":
            handle_vehicle_checkin(lot)
        elif choice == "2":
            handle_vehicle_checkout(lot)
        elif choice == "3":
            handle_view_slots(lot)
        elif choice == "4":
            handle_view_records(lot)
        elif choice == "5":
            handle_configure_lot(lot)
        elif choice == "6":
            handle_export_csv(lot)
        elif choice == "7":
            handle_view_slip(lot)
        elif choice == "8" or choice.lower() in ("exit", "quit", "q"):
            print("\nSaving data and shutting down system...")
            lot.save_to_json()
            print("✅ All data preserved in 'parking_data.json'.")
            print("Thank you for using Smart Parking Lot Management System! Goodbye.\n")
            sys.exit(0)
        else:
            print("❌ Invalid selection. Please enter a valid number from 1 to 8.")

        input("\nPress [Enter] to return to the main menu...")


if __name__ == "__main__":
    main()
