'Classes used in the smart parking system.'
import os
import re
import json
import csv
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path


# ============================================================================
# Requirement 6: Custom Exception Hierarchy
# ============================================================================

class ParkingSystemException(Exception):
    'Base exception for all parking system related errors.'
    pass


class SlotNotAvailableException(ParkingSystemException):
    'Raised when no parking slot is available for the requested vehicle type.'
    pass


class InvalidVehicleException(ParkingSystemException):
    'Raised when a vehicle registration number or type is invalid.'
    pass


class TicketNotFoundException(ParkingSystemException):
    'Raised when an active parking ticket or vehicle number is not found.'
    pass


class VehicleAlreadyParkedException(ParkingSystemException):
    'Raised when trying to check-in a vehicle that is already currently parked.'
    pass


# ============================================================================
# Requirement 1, 3, 4, 5: Base Class Vehicle (Abstraction & Encapsulation)
# ============================================================================

class Vehicle(ABC):
    'Abstract base class representing a generic vehicle.'
    def __init__(self, vehicle_number: str, owner_name: str, hourly_rate: float):
        self._vehicle_number = None
        self._owner_name = None
        self._hourly_rate = 0.0

        # Set values using property setters to enforce validation
        self.vehicle_number = vehicle_number
        self.owner_name = owner_name
        self.hourly_rate = hourly_rate

    # --- Encapsulation: Getter and Setter with Validation ---

    @property
    def vehicle_number(self) -> str:
        'Getter for vehicle registration number.'
        return self._vehicle_number

    @vehicle_number.setter
    def vehicle_number(self, value: str):
        'Setter validating format (e.g. MH12AB1234 or clean alphanumeric plate).'
        if not value or not isinstance(value, str):
            raise InvalidVehicleException("Vehicle number cannot be empty.")
        clean_num = re.sub(r"[\s\-]", "", value).upper()
        if len(clean_num) < 4 or len(clean_num) > 15 or not clean_num.isalnum():
            raise InvalidVehicleException(f"Invalid vehicle number format: '{value}'")
        self._vehicle_number = clean_num

    @property
    def owner_name(self) -> str:
        'Getter for vehicle owner name.'
        return self._owner_name

    @owner_name.setter
    def owner_name(self, value: str):
        'Setter validating non-empty owner name.'
        if not value or not str(value).strip():
            raise InvalidVehicleException("Owner name cannot be empty.")
        self._owner_name = str(value).strip()

    @property
    def hourly_rate(self) -> float:
        'Getter for hourly parking rate.'
        return self._hourly_rate

    @hourly_rate.setter
    def hourly_rate(self, value: float):
        'Setter validating non-negative rate.'
        rate = float(value)
        if rate < 0:
            raise ValueError("Hourly rate cannot be negative.")
        self._hourly_rate = rate

    # --- Abstraction: Abstract Methods ---

    @abstractmethod
    def get_vehicle_type(self) -> str:
        "Returns the type name of the vehicle ('CAR' or 'BIKE')."
        pass

    @abstractmethod
    def get_slot_prefix(self) -> str:
        "Returns the slot code prefix ('C-' for Car, 'B-' for Bike)."
        pass

    @abstractmethod
    def calculate_fee(self, hours: int) -> float:
        'Calculates parking charge based on duration in hours.'
        pass

    def __str__(self) -> str:
        return f"{self.get_vehicle_type()} [{self.vehicle_number}] (Owner: {self.owner_name})"


# ============================================================================
# Requirement 3 & 5: Subclasses Car & Bike (Inheritance & Polymorphism)
# ============================================================================

class Car(Vehicle):
    'Car class inheriting from Vehicle.'
    def __init__(self, vehicle_number: str, owner_name: str, hourly_rate: float = 30.0):
        super().__init__(vehicle_number, owner_name, hourly_rate)

    # Method Overriding
    def get_vehicle_type(self) -> str:
        return "CAR"

    def get_slot_prefix(self) -> str:
        return "C-"

    def calculate_fee(self, hours: int) -> float:
        'Calculates fee for cars: minimum 1 hour.'
        billable_hours = max(1, int(hours))
        return round(billable_hours * self.hourly_rate, 2)


class Bike(Vehicle):
    'Bike (Two-Wheeler) class inheriting from Vehicle.'
    def __init__(self, vehicle_number: str, owner_name: str, hourly_rate: float = 15.0):
        super().__init__(vehicle_number, owner_name, hourly_rate)

    # Method Overriding
    def get_vehicle_type(self) -> str:
        return "BIKE"

    def get_slot_prefix(self) -> str:
        return "B-"

    def calculate_fee(self, hours: int) -> float:
        'Calculates fee for bikes: minimum 1 hour.'
        billable_hours = max(1, int(hours))
        return round(billable_hours * self.hourly_rate, 2)


# ============================================================================
# Requirement 2 & 4: ParkingSlot Class (Encapsulation)
# ============================================================================

class ParkingSlot:
    'Represents a parking slot in the facility.'
    def __init__(self, slot_id: int, slot_number: str, slot_type: str, occupancy_status: str = "AVAILABLE"):
        self._slot_id = slot_id
        self._slot_number = slot_number
        self._slot_type = slot_type.upper()
        self._occupancy_status = "AVAILABLE"
        self.occupancy_status = occupancy_status

    @property
    def slot_id(self) -> int:
        return self._slot_id

    @property
    def slot_number(self) -> str:
        return self._slot_number

    @property
    def slot_type(self) -> str:
        return self._slot_type

    @property
    def occupancy_status(self) -> str:
        return self._occupancy_status

    @occupancy_status.setter
    def occupancy_status(self, status: str):
        valid = {"AVAILABLE", "OCCUPIED"}
        st = status.upper().strip()
        if st not in valid:
            raise ValueError(f"Invalid occupancy status '{status}'. Must be AVAILABLE or OCCUPIED.")
        self._occupancy_status = st

    def is_available(self) -> bool:
        return self._occupancy_status == "AVAILABLE"

    def occupy(self):
        self.occupancy_status = "OCCUPIED"

    def vacate(self):
        self.occupancy_status = "AVAILABLE"

    def to_dict(self) -> dict:
        return {
            "slot_id": self._slot_id,
            "slot_number": self._slot_number,
            "slot_type": self._slot_type,
            "occupancy_status": self._occupancy_status
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            slot_id=data["slot_id"],
            slot_number=data["slot_number"],
            slot_type=data["slot_type"],
            occupancy_status=data.get("occupancy_status", "AVAILABLE")
        )

    def __str__(self) -> str:
        status_label = "FREE" if self.is_available() else "OCCUPIED"
        return f"Slot {self._slot_number} [{self._slot_type}] - {status_label}"


# ============================================================================
# Requirement 2 & 4: ParkingTicket Class (Record Model)
# ============================================================================

class ParkingTicket:
    'Stores the details of a vehicle parking session.'
    def __init__(self, ticket_id: str, vehicle_number: str, owner_name: str,
                 vehicle_type: str, slot_number: str, entry_time: str,
                 hourly_rate: float, exit_time: str = None,
                 chargeable_hours: int = 0, total_fee: float = 0.0,
                 status: str = "ACTIVE", payment_method: str = None):
        self.ticket_id = ticket_id
        self.vehicle_number = vehicle_number
        self.owner_name = owner_name
        self.vehicle_type = vehicle_type.upper()
        self.slot_number = slot_number
        self.entry_time = entry_time
        self.hourly_rate = float(hourly_rate)
        self.exit_time = exit_time
        self.chargeable_hours = chargeable_hours
        self.total_fee = float(total_fee)
        self.status = status  # 'ACTIVE' or 'COMPLETED'
        self.payment_method = payment_method

    def is_active(self) -> bool:
        return self.status == "ACTIVE"

    def complete_checkout(self, exit_time: str, hours: int, fee: float, payment_method: str):
        'Marks the ticket as completed after payment.'
        self.exit_time = exit_time
        self.chargeable_hours = hours
        self.total_fee = fee
        self.payment_method = payment_method
        self.status = "COMPLETED"

    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id,
            "vehicle_number": self.vehicle_number,
            "owner_name": self.owner_name,
            "vehicle_type": self.vehicle_type,
            "slot_number": self.slot_number,
            "entry_time": self.entry_time,
            "hourly_rate": self.hourly_rate,
            "exit_time": self.exit_time,
            "chargeable_hours": self.chargeable_hours,
            "total_fee": self.total_fee,
            "status": self.status,
            "payment_method": self.payment_method
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


# ============================================================================
# Requirement 2, 5, 7: ParkingLot Management Class
# ============================================================================

class ParkingLot:
    'Core parking lot management class.'
    def __init__(self, lot_name: str = "City Smart Parking", location: str = "Main Market",
                 car_capacity: int = 10, bike_capacity: int = 15,
                 car_rate: float = 30.0, bike_rate: float = 15.0,
                 data_file: str = "parking_data.json"):
        self.lot_name = lot_name
        self.location = location
        self.car_rate = float(car_rate)
        self.bike_rate = float(bike_rate)
        self.data_file = Path(data_file)
        self.receipts_dir = Path("receipts")
        self.receipts_dir.mkdir(exist_ok=True)

        self.slots: list[ParkingSlot] = []
        self.tickets: list[ParkingTicket] = []
        self._next_ticket_number = 1

        # Load existing data if file exists, else initialize fresh slots
        if self.data_file.exists():
            self.load_from_json()
        else:
            self._init_default_slots(car_capacity, bike_capacity)
            self.save_to_json()

    def _init_default_slots(self, car_capacity: int, bike_capacity: int):
        'Generates initial car and bike slots.'
        self.slots = []
        slot_id = 1
        for i in range(1, car_capacity + 1):
            self.slots.append(ParkingSlot(slot_id, f"C-{i:02d}", "CAR"))
            slot_id += 1
        for i in range(1, bike_capacity + 1):
            self.slots.append(ParkingSlot(slot_id, f"B-{i:02d}", "BIKE"))
            slot_id += 1

    # --- Slot Allocation & Vehicle Check-In ---

    def park_vehicle(self, vehicle: Vehicle) -> ParkingTicket:
        'Allocates an available slot and creates an active parking ticket.'
        # Check if already parked
        for ticket in self.tickets:
            if ticket.is_active() and ticket.vehicle_number == vehicle.vehicle_number:
                raise VehicleAlreadyParkedException(
                    f"Vehicle '{vehicle.vehicle_number}' is already currently parked (Ticket: {ticket.ticket_id})."
                )

        # Find first available slot matching vehicle type
        v_type = vehicle.get_vehicle_type()
        target_slot = None
        for s in self.slots:
            if s.slot_type == v_type and s.is_available():
                target_slot = s
                break

        if not target_slot:
            raise SlotNotAvailableException(f"Sorry! No available {v_type.lower()} parking slots left.")

        # Occupy the slot
        target_slot.occupy()

        # Create ticket
        ticket_id = f"T{self._next_ticket_number:04d}"
        self._next_ticket_number += 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ticket = ParkingTicket(
            ticket_id=ticket_id,
            vehicle_number=vehicle.vehicle_number,
            owner_name=vehicle.owner_name,
            vehicle_type=v_type,
            slot_number=target_slot.slot_number,
            entry_time=now_str,
            hourly_rate=vehicle.hourly_rate,
            status="ACTIVE"
        )
        self.tickets.append(ticket)
        self.save_to_json()

        # Generate text entry slip
        self.generate_text_slip(ticket, slip_type="ENTRY")

        return ticket

    # --- Vehicle Check-Out & Fee Calculation ---

    def find_active_ticket(self, query: str) -> ParkingTicket:
        'Finds active ticket by either ticket ID or vehicle number.'
        clean_query = re.sub(r"[\s\-]", "", query).upper()
        for t in self.tickets:
            if t.is_active() and (t.ticket_id.upper() == clean_query or t.vehicle_number == clean_query):
                return t
        raise TicketNotFoundException(f"No active parking ticket found matching '{query}'.")

    def checkout_vehicle(self, ticket: ParkingTicket, payment_method: str = "CASH") -> tuple[int, float]:
        'Calculates parking fee, marks ticket completed, and vacates the slot.'
        if not ticket.is_active():
            raise ParkingSystemException(f"Ticket '{ticket.ticket_id}' has already been checked out.")

        # Re-construct vehicle instance to use polymorphic fee calculation
        if ticket.vehicle_type == "CAR":
            veh = Car(ticket.vehicle_number, ticket.owner_name, ticket.hourly_rate)
        else:
            veh = Bike(ticket.vehicle_number, ticket.owner_name, ticket.hourly_rate)

        # Calculate duration
        entry_dt = datetime.strptime(ticket.entry_time, "%Y-%m-%d %H:%M:%S")
        exit_dt = datetime.now()
        seconds_parked = int((exit_dt - entry_dt).total_seconds())
        # Minimum 1 hour, rounding up
        billable_hours = max(1, (seconds_parked + 3599) // 3600)

        # Polymorphic calculation
        total_fee = veh.calculate_fee(billable_hours)
        exit_str = exit_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Complete ticket
        ticket.complete_checkout(exit_str, billable_hours, total_fee, payment_method.upper())

        # Vacate the assigned slot
        for s in self.slots:
            if s.slot_number == ticket.slot_number:
                s.vacate()
                break

        self.save_to_json()

        # Generate text exit receipt
        self.generate_text_slip(ticket, slip_type="EXIT")

        return billable_hours, total_fee

    # --- Statistics & Slot Overview ---

    def get_slot_summary(self) -> dict:
        'Returns slot counts and occupancy statistics.'
        car_slots = [s for s in self.slots if s.slot_type == "CAR"]
        bike_slots = [s for s in self.slots if s.slot_type == "BIKE"]

        car_free = sum(1 for s in car_slots if s.is_available())
        bike_free = sum(1 for s in bike_slots if s.is_available())

        total_slots = len(self.slots)
        total_free = car_free + bike_free
        total_occupied = total_slots - total_free

        return {
            "total_slots": total_slots,
            "total_occupied": total_occupied,
            "total_free": total_free,
            "car_total": len(car_slots),
            "car_occupied": len(car_slots) - car_free,
            "car_free": car_free,
            "bike_total": len(bike_slots),
            "bike_occupied": len(bike_slots) - bike_free,
            "bike_free": bike_free,
        }

    # ========================================================================
    # Requirement 7: File Handling (JSON Persistence, CSV Export, Text Slips)
    # ========================================================================

    def save_to_json(self):
        'Saves current slots, rates, and tickets to JSON file.'
        data = {
            "lot_name": self.lot_name,
            "location": self.location,
            "car_rate": self.car_rate,
            "bike_rate": self.bike_rate,
            "next_ticket_number": self._next_ticket_number,
            "slots": [s.to_dict() for s in self.slots],
            "tickets": [t.to_dict() for t in self.tickets]
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_from_json(self):
        'Loads state from JSON file.'
        with open(self.data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.lot_name = data.get("lot_name", self.lot_name)
        self.location = data.get("location", self.location)
        self.car_rate = float(data.get("car_rate", self.car_rate))
        self.bike_rate = float(data.get("bike_rate", self.bike_rate))
        self._next_ticket_number = int(data.get("next_ticket_number", 1))

        self.slots = [ParkingSlot.from_dict(d) for d in data.get("slots", [])]
        self.tickets = [ParkingTicket.from_dict(d) for d in data.get("tickets", [])]

    def export_records_to_csv(self, filename: str = "parking_records.csv") -> str:
        'Exports all parking records to a CSV file.'
        filepath = Path(filename)
        headers = [
            "Ticket ID", "Vehicle Number", "Owner Name", "Type",
            "Slot Number", "Entry Time", "Exit Time", "Rate/hr",
            "Duration (hrs)", "Total Fee", "Status", "Payment Method"
        ]

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for t in self.tickets:
                writer.writerow([
                    t.ticket_id, t.vehicle_number, t.owner_name, t.vehicle_type,
                    t.slot_number, t.entry_time, t.exit_time or "-", t.hourly_rate,
                    t.chargeable_hours, t.total_fee, t.status, t.payment_method or "-"
                ])
        return str(filepath.resolve())

    def generate_text_slip(self, ticket: ParkingTicket, slip_type: str = "ENTRY") -> str:
        'Generates and saves a printable text slip/receipt in receipts/ folder.'
        filename = self.receipts_dir / f"Ticket_{ticket.ticket_id}_{slip_type}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("========================================\n")
            f.write(f"      {self.lot_name.upper()}\n")
            f.write(f"      Location: {self.location}\n")
            f.write("========================================\n")
            f.write(f" Slip Type   : PARKING {slip_type} RECEIPT\n")
            f.write(f" Ticket ID   : {ticket.ticket_id}\n")
            f.write(f" Vehicle No  : {ticket.vehicle_number}\n")
            f.write(f" Owner Name  : {ticket.owner_name}\n")
            f.write(f" Vehicle Type: {ticket.vehicle_type}\n")
            f.write(f" Slot Number : {ticket.slot_number}\n")
            f.write(f" Entry Time  : {ticket.entry_time}\n")
            if slip_type == "EXIT":
                f.write(f" Exit Time   : {ticket.exit_time}\n")
                f.write(f" Duration    : {ticket.chargeable_hours} hour(s)\n")
                f.write(f" Total Paid  : INR {ticket.total_fee:.2f}\n")
                f.write(f" Payment Via : {ticket.payment_method}\n")
            else:
                f.write(f" Rate        : INR {ticket.hourly_rate:.2f}/hour\n")
            f.write("----------------------------------------\n")
            f.write("   Thank you! Have a safe journey.\n")
            f.write("========================================\n")
        return str(filename)

