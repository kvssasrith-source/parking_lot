'Database connection and setup for the parking system.'
import os
import re
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from helpers import hash_password

# Load environment variables from .env file
ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

# Database configuration settings
DB_HOST = os.getenv("SMART_PARKING_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("SMART_PARKING_DB_PORT", "3306"))
DB_USER = os.getenv("SMART_PARKING_DB_USER", "root")
DB_PASSWORD = os.getenv("SMART_PARKING_DB_PASSWORD", "")
DB_NAME = os.getenv("SMART_PARKING_DB_NAME", "smart_parking")

# Force SQLite by default unless an external cloud MySQL is explicitly provided
USE_MYSQL = False

SQLITE_PATH = ROOT_DIR / "smart_parking.db"


class MySQLRow(dict):
    "Allows accessing columns by name ('col') or by index (0)."
    def __init__(self, data):
        super().__init__(data)
        self._items_list = list(data.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._items_list[key]
        return super().__getitem__(key)


class MySQLCursorWrapper:
    'Wraps MySQL cursor to return dict rows compatible with SQLite row objects.'
    def __init__(self, cursor):
        self.cursor = cursor

    def fetchone(self):
        row = self.cursor.fetchone()
        return MySQLRow(row) if row is not None else None

    def fetchall(self):
        return [MySQLRow(row) for row in self.cursor.fetchall()]

    @property
    def lastrowid(self):
        return self.cursor.lastrowid


class MySQLConnectionWrapper:
    'Wraps MySQL connection for clean and simple execute/commit/rollback methods.'
    def __init__(self, raw_conn):
        self.conn = raw_conn

    def execute(self, query: str, params=()):
        # Replace ? placeholder with %s for MySQL compatibility
        clean_query = re.sub(r"\?", "%s", query)
        
        # Translate SQLite-specific expressions to MySQL
        clean_query = re.sub(r"^\s*BEGIN\s+IMMEDIATE\b", "START TRANSACTION", clean_query, flags=re.IGNORECASE)
        clean_query = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT IGNORE INTO", clean_query, flags=re.IGNORECASE)
        clean_query = re.sub(r"datetime\s*\(\s*'now'\s*\)", "CURRENT_TIMESTAMP", clean_query, flags=re.IGNORECASE)
        clean_query = re.sub(r"date\s*\(\s*'now'\s*,\s*'-7 days'\s*\)", "DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)", clean_query, flags=re.IGNORECASE)
        clean_query = re.sub(r"date\s*\(\s*'now'\s*,\s*'-30 days'\s*\)", "DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)", clean_query, flags=re.IGNORECASE)
        clean_query = re.sub(r"date\s*\(\s*'now'\s*\)", "CURRENT_DATE", clean_query, flags=re.IGNORECASE)
        clean_query = re.sub(r"date\s*\(\s*([A-Za-z_][\w.]*)\s*\)", r"DATE(\1)", clean_query, flags=re.IGNORECASE)

        cursor = self.conn.cursor(dictionary=True, buffered=True)
        cursor.execute(clean_query, params)
        return MySQLCursorWrapper(cursor)

    def commit(self):
        if hasattr(self.conn, "commit") and callable(getattr(self.conn, "commit")):
            try:
                self.conn.commit()
                return
            except Exception:
                pass
        try:
            cursor = self.conn.cursor()
            cursor.execute("COMMIT")
            cursor.close()
        except Exception:
            pass

    def rollback(self):
        if hasattr(self.conn, "rollback") and callable(getattr(self.conn, "rollback")):
            try:
                self.conn.rollback()
                return
            except Exception:
                pass
        try:
            cursor = self.conn.cursor()
            cursor.execute("ROLLBACK")
            cursor.close()
        except Exception:
            pass

    def close(self):
        self.conn.close()


def get_db():
    'Returns an active database connection (MySQL or SQLite fallback).'
    if USE_MYSQL:
        try:
            import mysql.connector

            # Connect to MySQL server and ensure database exists
            server_conn = mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD
            )
            cur = server_conn.cursor()
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4")
            server_conn.commit()
            server_conn.close()

            # Connect to the target database
            db_conn = mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            return MySQLConnectionWrapper(db_conn)
        except Exception as e:
            print(f"[Database] Notice: MySQL unavailable ({e}), using local SQLite fallback.")
            conn = sqlite3.connect(str(SQLITE_PATH))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
    else:
        # SQLite connection
        conn = sqlite3.connect(str(SQLITE_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def init_db():
    'Initializes tables and seeds default admin account and facility if empty.'
    conn = get_db()
    is_mysql = isinstance(conn, MySQLConnectionWrapper)
    try:
        if is_mysql:
            # Create MySQL tables
            conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                role ENUM('ADMIN', 'WORKER') NOT NULL,
                account_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                plain_password VARCHAR(255),
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB;
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS parking_lots (
                lot_id INT AUTO_INCREMENT PRIMARY KEY,
                lot_name VARCHAR(100) NOT NULL,
                location VARCHAR(150) NOT NULL,
                created_by INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB;
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS parking_slots (
                slot_id INT AUTO_INCREMENT PRIMARY KEY,
                lot_id INT NOT NULL,
                slot_number VARCHAR(20) NOT NULL,
                slot_type ENUM('CAR', 'BIKE') NOT NULL,
                occupancy_status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
                is_active TINYINT NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_lot_slot (lot_id, slot_number),
                FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id) ON DELETE CASCADE
            ) ENGINE=InnoDB;
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS parking_rates (
                rate_id INT AUTO_INCREMENT PRIMARY KEY,
                lot_id INT NOT NULL,
                vehicle_type ENUM('CAR', 'BIKE') NOT NULL,
                hourly_rate DECIMAL(10,2) NOT NULL,
                effective_from VARCHAR(50) NOT NULL,
                effective_to VARCHAR(50) NULL,
                is_active TINYINT NOT NULL DEFAULT 1,
                FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id) ON DELETE CASCADE
            ) ENGINE=InnoDB;
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                vehicle_id INT AUTO_INCREMENT PRIMARY KEY,
                vehicle_number VARCHAR(20) UNIQUE NOT NULL,
                owner_name VARCHAR(100) NOT NULL,
                vehicle_type ENUM('CAR', 'BIKE') NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB;
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS parking_records (
                record_id INT AUTO_INCREMENT PRIMARY KEY,
                ticket_id VARCHAR(30) UNIQUE NOT NULL,
                vehicle_id INT NOT NULL,
                slot_id INT NOT NULL,
                entry_worker_id INT NOT NULL,
                exit_worker_id INT NULL,
                entry_time VARCHAR(50) NOT NULL,
                exit_time VARCHAR(50) NULL,
                applied_hourly_rate DECIMAL(10,2) NOT NULL,
                chargeable_duration INT NOT NULL DEFAULT 0,
                total_fee DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                parking_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
                FOREIGN KEY (slot_id) REFERENCES parking_slots(slot_id)
            ) ENGINE=InnoDB;
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                payment_id INT AUTO_INCREMENT PRIMARY KEY,
                record_id INT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                payment_method ENUM('CASH', 'UPI', 'CARD') NOT NULL,
                payment_status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
                processed_by INT NOT NULL,
                payment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transaction_reference VARCHAR(100) NULL,
                FOREIGN KEY (record_id) REFERENCES parking_records(record_id)
            ) ENGINE=InnoDB;
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id INT AUTO_INCREMENT PRIMARY KEY,
                record_id INT NOT NULL,
                receipt_number VARCHAR(50) UNIQUE NOT NULL,
                receipt_type ENUM('ENTRY', 'EXIT') NOT NULL,
                file_path VARCHAR(255) NULL,
                created_by INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (record_id) REFERENCES parking_records(record_id)
            ) ENGINE=InnoDB;
            """)
        else:
            # Create SQLite tables
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
    finally:
        conn.close()

