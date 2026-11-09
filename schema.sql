-- ============================================================
-- Smart Parking Lot Management System - MySQL Database Schema
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role VARCHAR(16) NOT NULL,
    account_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    plain_password VARCHAR(255),
    created_by INT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_created_by FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS parking_lots (
    lot_id INT AUTO_INCREMENT PRIMARY KEY,
    lot_name VARCHAR(150) NOT NULL,
    location VARCHAR(255) NOT NULL,
    created_by INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_parking_lots_created_by FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS parking_slots (
    slot_id INT AUTO_INCREMENT PRIMARY KEY,
    lot_id INT NOT NULL,
    slot_number VARCHAR(32) NOT NULL,
    slot_type VARCHAR(16) NOT NULL,
    occupancy_status VARCHAR(16) NOT NULL DEFAULT 'AVAILABLE',
    is_active TINYINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_parking_slots_lot_number (lot_id, slot_number),
    CONSTRAINT fk_parking_slots_lot FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_number VARCHAR(32) NOT NULL UNIQUE,
    owner_name VARCHAR(150) NOT NULL,
    vehicle_type VARCHAR(16) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS parking_rates (
    rate_id INT AUTO_INCREMENT PRIMARY KEY,
    lot_id INT NOT NULL,
    vehicle_type VARCHAR(16) NOT NULL,
    hourly_rate DOUBLE NOT NULL,
    effective_from VARCHAR(32) NOT NULL,
    effective_to VARCHAR(32),
    is_active TINYINT NOT NULL DEFAULT 1,
    CONSTRAINT fk_parking_rates_lot FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS parking_records (
    record_id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id VARCHAR(80) NOT NULL UNIQUE,
    vehicle_id INT NOT NULL,
    slot_id INT NOT NULL,
    entry_worker_id INT NOT NULL,
    exit_worker_id INT,
    entry_time VARCHAR(32) NOT NULL,
    exit_time VARCHAR(32),
    applied_hourly_rate DOUBLE NOT NULL,
    chargeable_duration INT DEFAULT 0,
    total_fee DOUBLE DEFAULT 0,
    parking_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_parking_records_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
    CONSTRAINT fk_parking_records_slot FOREIGN KEY (slot_id) REFERENCES parking_slots(slot_id),
    CONSTRAINT fk_parking_records_entry_worker FOREIGN KEY (entry_worker_id) REFERENCES users(user_id),
    CONSTRAINT fk_parking_records_exit_worker FOREIGN KEY (exit_worker_id) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    record_id INT NOT NULL,
    amount DOUBLE NOT NULL,
    payment_method VARCHAR(16) NOT NULL,
    payment_status VARCHAR(16) NOT NULL,
    processed_by INT NOT NULL,
    payment_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    transaction_reference VARCHAR(255),
    CONSTRAINT fk_payments_record FOREIGN KEY (record_id) REFERENCES parking_records(record_id),
    CONSTRAINT fk_payments_processed_by FOREIGN KEY (processed_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS receipts (
    receipt_id INT AUTO_INCREMENT PRIMARY KEY,
    record_id INT NOT NULL,
    receipt_number VARCHAR(80) NOT NULL UNIQUE,
    receipt_type VARCHAR(16) NOT NULL,
    file_path VARCHAR(512),
    created_by INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_receipts_record FOREIGN KEY (record_id) REFERENCES parking_records(record_id),
    CONSTRAINT fk_receipts_created_by FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

