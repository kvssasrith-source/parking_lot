# Smart Parking Lot Management System - Academic Project Documentation

This project has been developed strictly according to the **Common Requirements for All Projects** academic rubric for Object-Oriented Programming (OOP) in Python.

---

## Rubric Compliance Mapping

### Requirement 1 & 2: Python Classes and Objects (At Least 4 or 5 Meaningful Classes)
The system is built using **5 meaningful domain classes** located in `models.py`:

1. **`Vehicle`** (Abstract Base Class): Generic representation of any vehicle entering the parking facility.
2. **`Car`** (Subclass of `Vehicle`): Represents four-wheeler cars with car-specific slot allocation and hourly pricing.
3. **`Bike`** (Subclass of `Vehicle`): Represents two-wheeler bikes with bike-specific slot allocation and hourly pricing.
4. **`ParkingSlot`**: Encapsulates an individual parking slot, its number (`C-01`, `B-01`), type, and availability status.
5. **`ParkingTicket`**: Encapsulates a complete parking session (ticket ID, entry time, exit time, assigned slot, duration, total fee, and payment status).
6. **`ParkingLot`**: Manages the collection of slots, check-in, check-out, fee calculation, and file persistence.

---

### Requirement 3: Inheritance & Method Overriding
Located in `models.py`:
- **Inheritance Hierarchy:**
  ```text
            Vehicle (Abstract Base Class)
               ▲
               │
       ┌───────┴───────┐
       │               │
      Car             Bike
  ```
- **Method Overriding:**
  - `get_vehicle_type()`: Overridden by `Car` (returns `"CAR"`) and `Bike` (returns `"BIKE"`).
  - `get_slot_prefix()`: Overridden by `Car` (returns `"C-"`) and `Bike` (returns `"B-"`).
  - `calculate_fee(hours)`: Overridden by both subclasses to apply their specific hourly rates.

---

### Requirement 4: Encapsulation with Data Validation
Located in `models.py`:
- All sensitive internal data is stored in protected attributes with leading underscores (e.g., `_vehicle_number`, `_owner_name`, `_hourly_rate`, `_occupancy_status`).
- Data access is governed by Python `@property` getters and setters with strict validation:
  - **Vehicle Registration Validation:** Ensures registration numbers are non-empty and formatted correctly.
  - **Rate Validation:** Ensures hourly rates cannot be negative numbers (`rate < 0`).
  - **Slot Occupancy Validation:** Ensures status can only be set to `"AVAILABLE"` or `"OCCUPIED"`.

---

### Requirement 5: Abstraction and Polymorphism
Located in `models.py` and `main.py`:
- **Abstraction:**
  - `Vehicle` inherits from Python's standard `ABC` (`from abc import ABC, abstractmethod`).
  - Contains `@abstractmethod` definitions for `get_vehicle_type()`, `get_slot_prefix()`, and `calculate_fee()`.
- **Polymorphism:**
  - The check-in and checkout operations (`lot.park_vehicle(vehicle)` and `lot.checkout_vehicle(ticket)`) work polymorphically with any `Vehicle` instance.
  - The system calls `vehicle.calculate_fee(hours)` uniformly, and the correct overridden logic executes dynamically depending on whether the object is a `Car` or a `Bike`.

---

### Requirement 6: Exception Handling for Invalid Inputs & Operations
Located in `models.py` and `main.py`:
- **Custom Exception Hierarchy:**
  - `ParkingSystemException` (Base Exception)
  - `SlotNotAvailableException`: Raised when all slots of a particular vehicle type are occupied.
  - `InvalidVehicleException`: Raised when plate format or owner name is invalid.
  - `TicketNotFoundException`: Raised when searching for a non-existent or inactive ticket.
  - `VehicleAlreadyParkedException`: Raised when trying to check-in an already parked vehicle.
- **Defensive Error Handling:**
  - `main.py` wraps all user inputs in `try ... except` blocks to prevent crashes on non-numeric inputs, missing files, or invalid menu choices.

---

### Requirement 7: File Handling to Preserve Data Between Executions
Located in `models.py`:
Demonstrates **all three major file handling formats** required by the rubric:
1. **JSON (`parking_data.json`)**: Automatically saves the entire system state (all slots, rates, active tickets, and history) on every change and reloads it on startup to preserve data between executions.
2. **CSV (`parking_records.csv`)**: Allows exporting all parking records into a structured spreadsheet file via Menu Option 6.
3. **Text Files (`receipts/Ticket_<ID>_<TYPE>.txt`)**: Automatically formats and saves printable entry slips and exit payment receipts in the `receipts/` directory.

---

### Requirement 8: Menu-Driven Interface
Located in `main.py`:
An interactive terminal menu application providing complete control over the system:

```text
=================================================================
      CITY SMART PARKING - MANAGEMENT SYSTEM
      Location: Main Market | Active Slots: 25
=================================================================
  Cars Available: 10/10 | Bikes Available: 15/15 | Total Free: 25
-----------------------------------------------------------------
  [1] Park a Vehicle (Check-In)
  [2] Exit a Vehicle & Pay Bill (Check-Out)
  [3] View Live Parking Slots Status
  [4] View Parking Records & History
  [5] Configure Facility (Name, Location & Rates)
  [6] Export Records to CSV File
  [7] View / Print Parking Ticket Slip
  [8] Exit System
=================================================================
Enter your choice (1-8):
```

---

## How to Run the Menu-Driven System

To start the menu-driven application:
```bash
python main.py
```

*(Optional Bonus: The Web dashboard can still be launched anytime with `python app.py`).*

