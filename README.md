# Smart Parking Lot Management System

A beginner-friendly and clean web-based Smart Parking Management System built with **Python (Flask)**, **HTML/CSS/JavaScript**, and **MySQL**.

---

## Project Structure

```text
SMART_PARKING_ALOT_SYSTEM/
│
├── app.py                # Main Flask web application and all page routes
├── database.py           # Database connection and automatic table creation
├── helpers.py            # Utility functions (fee calculation, password hashing, plate formatting)
├── inspect_db.py         # Terminal tool to view database tables and live data
├── main.py               # Alternative entry point to run the web server
├── schema.sql            # MySQL database schema definition
├── requirements.txt      # Project dependencies (Flask, mysql-connector-python, python-dotenv)
├── README.md             # Project documentation and guide
├── .env                  # Local database settings and credentials
├── .env.example          # Sample environment variables template
│
├── static/
│   └── css/
│       └── style.css     # Clean and responsive styling
│
└── templates/            # HTML pages
    ├── base.html
    ├── login.html
    ├── register.html
    ├── admin_dashboard.html
    ├── worker_dashboard.html
    ├── parking_setup.html
    ├── slot_management.html
    ├── vehicle_entry.html
    ├── vehicle_exit.html
    ├── manage_workers.html
    ├── parking_history.html
    ├── reports.html
    ├── entry_slip_print.html
    ├── exit_receipt_print.html
    └── partials/
        ├── admin_sidebar.html
        └── worker_sidebar.html
```

---

## Features

- **Role-based Authentication**: Separate Admin and Worker dashboards with secure password hashing.
- **Facility Isolation**: Each Admin manages their own independent parking lot, slot capacities, rates, and stats.
- **Live Slot Availability Map**: Interactive real-time slot view showing available vs. occupied car and bike slots.
- **Vehicle Entry**: Real-time slot allocation, hourly rate assignment, and printable thermal entry slips / text file downloads.
- **Vehicle Exit & Fee Calculation**: Automatic bill calculation based on parked duration, checkout payment (Cash, UPI, Card), and printable exit receipts.
- **Worker Management**: Admins can add workers, securely view/change worker passwords, and remove workers with password verification.
- **Reports & Analytics**: Daily, weekly, monthly revenue summaries, payment mode breakdown, and occupancy percentages.

---

## How to Run the Project

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure MySQL Database
Make sure MySQL is running on your machine, then verify your credentials in the `.env` file:
```properties
SMART_PARKING_USE_MYSQL=true
SMART_PARKING_DB_HOST=127.0.0.1
SMART_PARKING_DB_PORT=3306
SMART_PARKING_DB_USER=root
SMART_PARKING_DB_PASSWORD=your_mysql_password
SMART_PARKING_DB_NAME=smart_parking
```
*(The app automatically creates the `smart_parking` database and tables if they don't exist).*

### 3. Start the Web Server
Run either:
```bash
python app.py
```
or:
```bash
python main.py
```

### 4. Open in Your Browser
Visit: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## Default Admin Credentials
- **Username:** `admin`
- **Password:** `admin123`

---

## Checking the Database in Console
To inspect all tables, column names, row counts, and sample data directly in the terminal, run:
```bash
python inspect_db.py
```
