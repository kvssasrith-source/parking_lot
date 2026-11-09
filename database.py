'Database connection and setup for the parking system.'
import sqlite3
from pathlib import Path
from helpers import hash_password

# Force SQLite path to the current directory
ROOT_DIR = Path(__file__).resolve().parent
SQLITE_PATH = ROOT_DIR / "smart_parking.db"

def get_db():
    # timeout=20.0 prevents "database is locked" crashes when Render wakes up
    conn = sqlite3.connect(str(SQLITE_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    'Initializes tables and seeds default admin account and facility if empty.'
    conn = get_db()
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('ADMIN', 'WORKER')),
            account_status TEXT NOT NULL DEFAULT 'ACTIVE',
            plain_password TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS parking_lots (
            lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_name TEXT NOT NULL,
            location TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS parking_slots (
            slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            slot_number TEXT NOT NULL,
            slot_type TEXT NOT NULL CHECK(slot_type IN ('CAR', 'BIKE')),
            occupancy_status TEXT NOT NULL DEFAULT 'AVAILABLE',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(lot_id, slot_number),
            FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS parking_rates (
            rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            vehicle_type TEXT NOT NULL,
            hourly_rate REAL NOT NULL,
            effective_from TEXT NOT NULL,
            effective_to TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_number TEXT UNIQUE NOT NULL,
            owner_name TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS parking_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL UNIQUE,
            vehicle_id INTEGER NOT NULL,
            slot_id INTEGER NOT NULL,
            entry_worker_id INTEGER NOT NULL,
            exit_worker_id INTEGER,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            applied_hourly_rate REAL NOT NULL,
            chargeable_duration INTEGER NOT NULL DEFAULT 0,
            total_fee REAL NOT NULL DEFAULT 0,
            parking_status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
            FOREIGN KEY (slot_id) REFERENCES parking_slots(slot_id)
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'SUCCESS',
            processed_by INTEGER NOT NULL,
            payment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            transaction_reference TEXT,
            FOREIGN KEY (record_id) REFERENCES parking_records(record_id)
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            receipt_number TEXT NOT NULL UNIQUE,
            receipt_type TEXT NOT NULL,
            file_path TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (record_id) REFERENCES parking_records(record_id)
        );
        """)

        # Ensure default admin account exists
        admin_check = conn.execute("SELECT user_id FROM users WHERE username = 'admin'").fetchone()
        if not admin_check:
            admin_hash = hash_password("admin123")
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, role, plain_password) VALUES ('admin', ?, 'System Administrator', 'ADMIN', 'admin123')",
                (admin_hash,)
            )

        # Ensure default parking facility exists
        lot_check = conn.execute("SELECT lot_id FROM parking_lots WHERE created_by = 1").fetchone()
        if not lot_check:
            cur = conn.execute(
                "INSERT INTO parking_lots (lot_name, location, created_by) VALUES ('City Parking', 'Main Market', 1)"
            )
            default_lot_id = cur.lastrowid or 1

            # Insert default rates for CAR and BIKE
            conn.execute(
                "INSERT INTO parking_rates (lot_id, vehicle_type, hourly_rate, effective_from, is_active) VALUES (?, 'CAR', 30.0, datetime('now'), 1)",
                (default_lot_id,)
            )
            conn.execute(
                "INSERT INTO parking_rates (lot_id, vehicle_type, hourly_rate, effective_from, is_active) VALUES (?, 'BIKE', 15.0, datetime('now'), 1)",
                (default_lot_id,)
            )

            # Insert initial slots: 20 Cars, 30 Bikes
            for num in range(1, 21):
                conn.execute(
                    "INSERT OR IGNORE INTO parking_slots (lot_id, slot_number, slot_type, occupancy_status, is_active) VALUES (?, ?, 'CAR', 'AVAILABLE', 1)",
                    (default_lot_id, f"C-{num:02d}")
                )
            for num in range(1, 31):
                conn.execute(
                    "INSERT OR IGNORE INTO parking_slots (lot_id, slot_number, slot_type, occupancy_status, is_active) VALUES (?, ?, 'BIKE', 'AVAILABLE', 1)",
                    (default_lot_id, f"B-{num:02d}")
                )

        conn.commit()
    except Exception as e:
        print(f"Database Init Error: {e}")
    finally:
        conn.close()
