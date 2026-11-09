'Helper functions used by the parking system.'
import hashlib
import os
import re
from datetime import datetime


def hash_password(password: str) -> str:
    'Creates a secure PBKDF2-HMAC-SHA256 password hash with salt.'
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 200000)
    return f"{salt}:{digest.hex()}"


def check_password(plain_password: str, stored_hash: str) -> bool:
    'Verifies if the entered password matches the stored hash.'
    if not stored_hash:
        return False
    
    if ":" in stored_hash:
        salt, expected_digest = stored_hash.split(":", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 200000)
        return candidate.hex() == expected_digest
    else:
        # Fallback for plain sha256
        return hashlib.sha256(plain_password.encode("utf-8")).hexdigest() == stored_hash


def clean_vehicle_number(plate: str) -> str:
    'Removes extra spaces, hyphens, and converts to uppercase.'
    if not plate:
        return ""
    return re.sub(r"[\s\-]", "", plate).upper()


def is_valid_vehicle_number(plate: str) -> bool:
    'Checks if a vehicle registration number has a valid format.'
    cleaned = clean_vehicle_number(plate)
    pattern = r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,2}[0-9]{4}$"
    return bool(re.match(pattern, cleaned))


def calculate_parking_fee(hourly_rate: float, entry_time_str: str, exit_time_str: str = None) -> tuple[int, float]:
    'Calculates duration in hours and the total fee.'
    entry_dt = datetime.fromisoformat(entry_time_str)
    exit_dt = datetime.fromisoformat(exit_time_str) if exit_time_str else datetime.now()

    if exit_dt < entry_dt:
        raise ValueError("Exit time cannot be earlier than entry time.")

    # Calculate total seconds
    total_seconds = int((exit_dt - entry_dt).total_seconds())
    
    # Round up to full hours (at least 1 hour)
    billable_hours = max(1, (total_seconds + 3599) // 3600)
    total_amount = float(hourly_rate) * billable_hours

    return billable_hours, round(total_amount, 2)
