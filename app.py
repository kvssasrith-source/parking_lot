'Flask application for the smart parking system.'
import os
from functools import wraps
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    Response
)

from database import get_db, init_db
from helpers import (
    hash_password,
    check_password,
    clean_vehicle_number,
    is_valid_vehicle_number,
    calculate_parking_fee
)

# Initialize Flask web application
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "smart-parking-secret-key-2024")

# Set up database tables and default admin on startup
with app.app_context():
    init_db()


# ---------------------------------------------------------------------------
# Authentication Helper Decorators
# ---------------------------------------------------------------------------

def login_required(func):
    'Requires user to be signed in to view the page.'
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return decorated_function


def admin_required(func):
    'Requires the logged-in user to have an ADMIN role.'
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "ADMIN":
            flash("Administrator access required for this page.", "error")
            return redirect(url_for("worker_dashboard"))
        return func(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# Facility Helper: Multi-Tenant Lot Isolation
# ---------------------------------------------------------------------------

def get_user_parking_lot(user_id: int):
    'Returns the parking lot owned by this admin, or assigned to this worker.'
    conn = get_db()
    try:
        # Check current user's role
        user_row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user_row:
            admin_id = 1
            admin_name = "Admin"
        else:
            admin_name = user_row["full_name"] or user_row["username"]
            admin_id = user_id if user_row["role"] == "ADMIN" else (user_row["created_by"] or 1)

        # Look up existing lot for this admin
        lot = conn.execute(
            "SELECT * FROM parking_lots WHERE created_by = ? ORDER BY lot_id ASC LIMIT 1",
            (admin_id,)
        ).fetchone()

        # If fallback to default lot 1
        if not lot and admin_id == 1:
            lot = conn.execute("SELECT * FROM parking_lots ORDER BY lot_id ASC LIMIT 1").fetchone()

        # If new admin has no lot yet, create a fresh facility with default rates & slots
        if not lot:
            lot_name = f"{admin_name}'s Parking"
            cur = conn.execute(
                "INSERT INTO parking_lots (lot_name, location, created_by) VALUES (?, 'Main Facility', ?)",
                (lot_name, admin_id)
            )
            conn.commit()
            new_lot_id = cur.lastrowid
            lot = conn.execute("SELECT * FROM parking_lots WHERE lot_id = ?", (new_lot_id,)).fetchone()

            # Default rates
            conn.execute(
                "INSERT INTO parking_rates (lot_id, vehicle_type, hourly_rate, effective_from, is_active) VALUES (?, 'CAR', 30.0, datetime('now'), 1)",
                (lot["lot_id"],)
            )
            conn.execute(
                "INSERT INTO parking_rates (lot_id, vehicle_type, hourly_rate, effective_from, is_active) VALUES (?, 'BIKE', 15.0, datetime('now'), 1)",
                (lot["lot_id"],)
            )

            # Default slots: 10 cars and 15 bikes
            for i in range(1, 11):
                conn.execute(
                    "INSERT OR IGNORE INTO parking_slots (lot_id, slot_number, slot_type, occupancy_status, is_active) VALUES (?, ?, 'CAR', 'AVAILABLE', 1)",
                    (lot["lot_id"], f"C-{i:02d}")
                )
            for i in range(1, 16):
                conn.execute(
                    "INSERT OR IGNORE INTO parking_slots (lot_id, slot_number, slot_type, occupancy_status, is_active) VALUES (?, ?, 'BIKE', 'AVAILABLE', 1)",
                    (lot["lot_id"], f"B-{i:02d}")
                )
            conn.commit()

        lot_id = lot["lot_id"]

        # Calculate current capacity and rates
        car_count = conn.execute(
            "SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND slot_type = 'CAR' AND is_active = 1",
            (lot_id,)
        ).fetchone()[0]
        bike_count = conn.execute(
            "SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND slot_type = 'BIKE' AND is_active = 1",
            (lot_id,)
        ).fetchone()[0]

        car_rate_row = conn.execute(
            "SELECT hourly_rate FROM parking_rates WHERE lot_id = ? AND vehicle_type = 'CAR' AND is_active = 1 ORDER BY rate_id DESC LIMIT 1",
            (lot_id,)
        ).fetchone()
        bike_rate_row = conn.execute(
            "SELECT hourly_rate FROM parking_rates WHERE lot_id = ? AND vehicle_type = 'BIKE' AND is_active = 1 ORDER BY rate_id DESC LIMIT 1",
            (lot_id,)
        ).fetchone()

        return {
            "lot_id": lot_id,
            "lot_name": lot["lot_name"],
            "location": lot["location"],
            "car_capacity": car_count,
            "bike_capacity": bike_count,
            "car_rate": float(car_rate_row["hourly_rate"]) if car_rate_row else 30.0,
            "bike_rate": float(bike_rate_row["hourly_rate"]) if bike_rate_row else 15.0,
            "created_by": lot["created_by"]
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Home & Authentication Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    'Redirect to dashboard if logged in, else redirect to login.'
    if "user_id" in session:
        if session.get("role") == "ADMIN":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("worker_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    'Handles user sign-in for Admins and Workers.'
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND account_status = 'ACTIVE'",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password(password, user["password_hash"]):
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]

            if user["role"] == "ADMIN":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("worker_dashboard"))
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    'Logs out the user and clears session data.'
    session.clear()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    'Allows new users to register an account.'
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "WORKER").upper()

        if not full_name or not username or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if len(password) < 4:
            flash("Password must be at least 4 characters long.", "error")
            return render_template("register.html")

        if role not in ("WORKER", "ADMIN"):
            role = "WORKER"

        conn = get_db()
        existing_user = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if existing_user:
            conn.close()
            flash(f"Username '{username}' is already taken.", "error")
            return render_template("register.html")

        hashed = hash_password(password)
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, full_name, role, plain_password) VALUES (?, ?, ?, ?, ?)",
            (username, hashed, full_name, role, password)
        )
        conn.commit()
        new_user_id = cur.lastrowid
        conn.close()

        # If user registered as an Admin, create their initial parking facility
        if role == "ADMIN":
            get_user_parking_lot(new_user_id)

        flash(f"Account created successfully for {username}! Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    'Main administrative dashboard displaying live facility stats.'
    lot = get_user_parking_lot(session["user_id"])
    lot_id = lot["lot_id"]

    conn = get_db()

    # Slot availability counts
    car_total = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND slot_type = 'CAR' AND is_active = 1", (lot_id,)).fetchone()[0]
    bike_total = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND slot_type = 'BIKE' AND is_active = 1", (lot_id,)).fetchone()[0]
    car_occupied = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND slot_type = 'CAR' AND occupancy_status = 'OCCUPIED' AND is_active = 1", (lot_id,)).fetchone()[0]
    bike_occupied = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND slot_type = 'BIKE' AND occupancy_status = 'OCCUPIED' AND is_active = 1", (lot_id,)).fetchone()[0]

    car_available = car_total - car_occupied
    bike_available = bike_total - bike_occupied
    total_slots = car_total + bike_total
    occupied_slots = car_occupied + bike_occupied
    available_slots = car_available + bike_available

    # Today's revenue & activity for this facility
    today_revenue = conn.execute(
        "SELECT COALESCE(SUM(p.amount), 0) FROM payments p "
        "JOIN parking_records pr ON pr.record_id = p.record_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND p.payment_status = 'SUCCESS' AND date(p.payment_time) = date('now')",
        (lot_id,)
    ).fetchone()[0]

    active_records = conn.execute(
        "SELECT COUNT(*) FROM parking_records pr "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND pr.parking_status = 'ACTIVE'",
        (lot_id,)
    ).fetchone()[0]

    successful_payments = conn.execute(
        "SELECT COUNT(*) FROM payments p "
        "JOIN parking_records pr ON pr.record_id = p.record_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND p.payment_status = 'SUCCESS'",
        (lot_id,)
    ).fetchone()[0]

    stats = {
        "total_slots": total_slots,
        "occupied_slots": occupied_slots,
        "available_slots": available_slots,
        "car_total": car_total,
        "car_occupied": car_occupied,
        "car_available": car_available,
        "bike_total": bike_total,
        "bike_occupied": bike_occupied,
        "bike_available": bike_available,
        "today_revenue": float(today_revenue),
        "active_records": active_records,
        "successful_payments": successful_payments
    }

    # Live slot visual map
    slots = [dict(r) for r in conn.execute(
        "SELECT slot_number, slot_type, occupancy_status FROM parking_slots WHERE lot_id = ? AND is_active = 1 ORDER BY slot_type, slot_number",
        (lot_id,)
    ).fetchall()]

    # Recent vehicle entry activity
    recent = [dict(r) for r in conn.execute(
        "SELECT pr.ticket_id, v.vehicle_number, v.owner_name, pr.parking_status, pr.entry_time "
        "FROM parking_records pr "
        "JOIN vehicles v ON v.vehicle_id = pr.vehicle_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? "
        "ORDER BY pr.created_at DESC LIMIT 8",
        (lot_id,)
    ).fetchall()]

    conn.close()
    return render_template("admin_dashboard.html", stats=stats, slots=slots, recent=recent, lot=lot)


# ---------------------------------------------------------------------------
# Parking Setup & Slot Reconfiguration
# ---------------------------------------------------------------------------

@app.route("/admin/parking-setup", methods=["GET", "POST"])
@admin_required
def parking_setup():
    'Allows an administrator to configure facility name, slot capacities, and rates.'
    lot = get_user_parking_lot(session["user_id"])
    lot_id = lot["lot_id"]

    if request.method == "POST":
        lot_name = request.form.get("lot_name", "").strip()
        location = request.form.get("location", "").strip()
        car_capacity = int(request.form.get("car_capacity", 0))
        bike_capacity = int(request.form.get("bike_capacity", 0))
        car_rate = float(request.form.get("car_rate", 30.0))
        bike_rate = float(request.form.get("bike_rate", 15.0))

        if not lot_name or not location:
            flash("Facility name and location are required.", "error")
            return render_template("parking_setup.html", lot=lot)

        conn = get_db()
        try:
            # Update lot details
            conn.execute(
                "UPDATE parking_lots SET lot_name = ?, location = ? WHERE lot_id = ?",
                (lot_name, location, lot_id)
            )

            # Re-generate available slots to match new capacity
            conn.execute("DELETE FROM parking_slots WHERE lot_id = ? AND occupancy_status = 'AVAILABLE'", (lot_id,))
            for num in range(1, car_capacity + 1):
                conn.execute(
                    "INSERT OR IGNORE INTO parking_slots (lot_id, slot_number, slot_type, occupancy_status, is_active) VALUES (?, ?, 'CAR', 'AVAILABLE', 1)",
                    (lot_id, f"C-{num:02d}")
                )
            for num in range(1, bike_capacity + 1):
                conn.execute(
                    "INSERT OR IGNORE INTO parking_slots (lot_id, slot_number, slot_type, occupancy_status, is_active) VALUES (?, ?, 'BIKE', 'AVAILABLE', 1)",
                    (lot_id, f"B-{num:02d}")
                )

            # Update rates
            conn.execute("UPDATE parking_rates SET is_active = 0 WHERE lot_id = ? AND vehicle_type = 'CAR'", (lot_id,))
            conn.execute(
                "INSERT INTO parking_rates (lot_id, vehicle_type, hourly_rate, effective_from, is_active) VALUES (?, 'CAR', ?, datetime('now'), 1)",
                (lot_id, car_rate)
            )
            conn.execute("UPDATE parking_rates SET is_active = 0 WHERE lot_id = ? AND vehicle_type = 'BIKE'", (lot_id,))
            conn.execute(
                "INSERT INTO parking_rates (lot_id, vehicle_type, hourly_rate, effective_from, is_active) VALUES (?, 'BIKE', ?, datetime('now'), 1)",
                (lot_id, bike_rate)
            )

            conn.commit()
            flash(f"Parking facility '{lot_name}' updated successfully! Slots and rates reconfigured.", "success")
            return redirect(url_for("parking_setup"))
        finally:
            conn.close()

    return render_template("parking_setup.html", lot=lot)


@app.route("/admin/slots")
@admin_required
def slot_management():
    "Lists all parking slots for the logged-in admin's facility."
    lot = get_user_parking_lot(session["user_id"])
    conn = get_db()
    rows = conn.execute(
        "SELECT slot_number, slot_type, occupancy_status, is_active FROM parking_slots WHERE lot_id = ? ORDER BY slot_type, slot_number",
        (lot["lot_id"],)
    ).fetchall()
    conn.close()
    slots = [dict(r) for r in rows]
    return render_template("slot_management.html", slots=slots, lot=lot)


# ---------------------------------------------------------------------------
# Worker Management
# ---------------------------------------------------------------------------

@app.route("/admin/workers", methods=["GET", "POST"])
@admin_required
def manage_workers():
    'Lists workers belonging to this admin and handles adding new workers.'
    admin_id = session["user_id"]
    conn = get_db()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")

        if not username or not full_name or not password:
            flash("All fields are required.", "error")
        else:
            existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                flash(f"Username '{username}' already exists.", "error")
            else:
                hashed = hash_password(password)
                conn.execute(
                    "INSERT INTO users (username, password_hash, full_name, role, plain_password, created_by) VALUES (?, ?, ?, 'WORKER', ?, ?)",
                    (username, hashed, full_name, password, admin_id)
                )
                conn.commit()
                flash(f"Worker '{username}' created successfully!", "success")
                return redirect(url_for("manage_workers"))

    # Fetch workers for this admin
    if admin_id == 1:
        rows = conn.execute(
            "SELECT * FROM users WHERE role = 'WORKER' AND account_status = 'ACTIVE' AND (created_by = 1 OR created_by IS NULL) ORDER BY created_at"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM users WHERE role = 'WORKER' AND account_status = 'ACTIVE' AND created_by = ? ORDER BY created_at",
            (admin_id,)
        ).fetchall()

    conn.close()
    workers = [dict(r) for r in rows]
    return render_template("manage_workers.html", workers=workers)


@app.route("/admin/workers/get-password", methods=["POST"])
@admin_required
def get_worker_password():
    "Reveals the worker's plain password after admin verification."
    data = request.get_json() or {}
    worker_id = data.get("worker_id")
    admin_password = data.get("admin_password", "").strip()

    if not admin_password:
        return jsonify({"error": "Admin password is required."}), 400

    conn = get_db()
    admin_row = conn.execute("SELECT password_hash FROM users WHERE user_id = ?", (session["user_id"],)).fetchone()

    if not admin_row or not check_password(admin_password, admin_row["password_hash"]):
        conn.close()
        return jsonify({"error": "Incorrect admin password. Verification failed."}), 403

    # Find the worker
    admin_id = session["user_id"]
    if admin_id == 1:
        worker_row = conn.execute(
            "SELECT username, plain_password FROM users WHERE user_id = ? AND role = 'WORKER' AND (created_by = 1 OR created_by IS NULL)",
            (worker_id,)
        ).fetchone()
    else:
        worker_row = conn.execute(
            "SELECT username, plain_password FROM users WHERE user_id = ? AND role = 'WORKER' AND created_by = ?",
            (worker_id, admin_id)
        ).fetchone()

    conn.close()

    if not worker_row:
        return jsonify({"error": "Worker not found or not managed by you."}), 404

    return jsonify({
        "success": True,
        "username": worker_row["username"],
        "password": worker_row["plain_password"] or "(Set a new password below)"
    })


@app.route("/admin/workers/update-password", methods=["POST"])
@admin_required
def update_worker_password():
    "Changes a worker's password after verifying the admin password."
    data = request.get_json() or {}
    worker_id = data.get("worker_id")
    admin_password = data.get("admin_password", "").strip()
    new_password = data.get("new_password", "").strip()

    if not admin_password or not new_password:
        return jsonify({"error": "Admin password and new password are required."}), 400

    if len(new_password) < 4:
        return jsonify({"error": "New password must be at least 4 characters long."}), 400

    conn = get_db()
    admin_row = conn.execute("SELECT password_hash FROM users WHERE user_id = ?", (session["user_id"],)).fetchone()

    if not admin_row or not check_password(admin_password, admin_row["password_hash"]):
        conn.close()
        return jsonify({"error": "Incorrect admin password. Verification failed."}), 403

    new_hash = hash_password(new_password)
    conn.execute(
        "UPDATE users SET password_hash = ?, plain_password = ? WHERE user_id = ?",
        (new_hash, new_password, worker_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Worker password updated successfully!"})


@app.route("/admin/workers/remove", methods=["POST"])
@admin_required
def remove_worker():
    "Removes a worker after verifying that worker's specific password."
    data = request.get_json() or {}
    worker_id = data.get("worker_id")
    worker_password = data.get("worker_password", "").strip()

    if not worker_password:
        return jsonify({"error": "Worker password is required to confirm removal."}), 400

    admin_id = session["user_id"]
    conn = get_db()

    # Find worker record
    if admin_id == 1:
        worker_row = conn.execute(
            "SELECT user_id, username, password_hash FROM users WHERE user_id = ? AND role = 'WORKER' AND (created_by = 1 OR created_by IS NULL)",
            (worker_id,)
        ).fetchone()
    else:
        worker_row = conn.execute(
            "SELECT user_id, username, password_hash FROM users WHERE user_id = ? AND role = 'WORKER' AND created_by = ?",
            (worker_id, admin_id)
        ).fetchone()

    if not worker_row:
        conn.close()
        return jsonify({"error": "Worker not found or not managed by you."}), 404

    # Verify worker's password
    if not check_password(worker_password, worker_row["password_hash"]):
        conn.close()
        return jsonify({"error": "Incorrect worker password. Verification failed."}), 400

    worker_username = worker_row["username"]

    # Delete worker or deactivate if linked to existing parking history
    try:
        conn.execute("DELETE FROM users WHERE user_id = ?", (worker_id,))
        conn.commit()
    except Exception:
        conn.execute("UPDATE users SET account_status = 'INACTIVE' WHERE user_id = ?", (worker_id,))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "message": f"Worker '{worker_username}' has been removed successfully!"})


# ---------------------------------------------------------------------------
# Worker Dashboard
# ---------------------------------------------------------------------------

@app.route("/worker/dashboard")
@login_required
def worker_dashboard():
    'Daily operations overview for parking attendants.'
    lot = get_user_parking_lot(session["user_id"])
    lot_id = lot["lot_id"]

    conn = get_db()
    car_total = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND slot_type = 'CAR' AND is_active = 1", (lot_id,)).fetchone()[0]
    bike_total = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND slot_type = 'BIKE' AND is_active = 1", (lot_id,)).fetchone()[0]
    car_occupied = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND slot_type = 'CAR' AND occupancy_status = 'OCCUPIED' AND is_active = 1", (lot_id,)).fetchone()[0]
    bike_occupied = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND slot_type = 'BIKE' AND occupancy_status = 'OCCUPIED' AND is_active = 1", (lot_id,)).fetchone()[0]

    car_available = car_total - car_occupied
    bike_available = bike_total - bike_occupied
    total_slots = car_total + bike_total
    free_slots = car_available + bike_available

    parked = conn.execute(
        "SELECT COUNT(*) FROM parking_records pr "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND pr.parking_status = 'ACTIVE'",
        (lot_id,)
    ).fetchone()[0]

    stats = {
        "car_total": car_total,
        "car_occupied": car_occupied,
        "car_available": car_available,
        "bike_total": bike_total,
        "bike_occupied": bike_occupied,
        "bike_available": bike_available,
        "total_slots": total_slots,
        "free_slots": free_slots,
        "parked": parked
    }

    slots = [dict(r) for r in conn.execute(
        "SELECT slot_number, slot_type, occupancy_status FROM parking_slots WHERE lot_id = ? AND is_active = 1 ORDER BY slot_type, slot_number",
        (lot_id,)
    ).fetchall()]

    recent = [dict(r) for r in conn.execute(
        "SELECT pr.ticket_id, v.vehicle_number, pr.parking_status, pr.entry_time "
        "FROM parking_records pr "
        "JOIN vehicles v ON v.vehicle_id = pr.vehicle_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? "
        "ORDER BY pr.created_at DESC LIMIT 6",
        (lot_id,)
    ).fetchall()]

    conn.close()
    return render_template("worker_dashboard.html", stats=stats, slots=slots, recent=recent, lot=lot)


# ---------------------------------------------------------------------------
# Vehicle Entry
# ---------------------------------------------------------------------------

@app.route("/worker/vehicle-entry", methods=["GET", "POST"])
@login_required
def vehicle_entry():
    'Registers vehicle arrival, allocates available slot, and generates ticket.'
    result = None

    if request.method == "POST":
        vehicle_number = clean_vehicle_number(request.form.get("vehicle_number", ""))
        owner_name = request.form.get("owner_name", "").strip()
        vehicle_type = request.form.get("vehicle_type", "CAR").upper()

        if not vehicle_number or not owner_name:
            flash("Vehicle number and owner name are required.", "error")
            return render_template("vehicle_entry.html", result=result)

        if not is_valid_vehicle_number(vehicle_number):
            flash("Invalid vehicle number format. Example: MH12AB1234", "error")
            return render_template("vehicle_entry.html", result=result)

        lot = get_user_parking_lot(session["user_id"])
        lot_id = lot["lot_id"]

        conn = get_db()
        try:
            # Check if this vehicle is already parked inside this facility
            active_check = conn.execute(
                "SELECT pr.record_id FROM parking_records pr "
                "JOIN vehicles v ON v.vehicle_id = pr.vehicle_id "
                "JOIN parking_slots s ON s.slot_id = pr.slot_id "
                "WHERE v.vehicle_number = ? AND s.lot_id = ? AND pr.parking_status = 'ACTIVE'",
                (vehicle_number, lot_id)
            ).fetchone()

            if active_check:
                flash(f"Vehicle {vehicle_number} is already currently parked in this facility.", "error")
                return render_template("vehicle_entry.html", result=result)

            # Find or insert vehicle in vehicles table
            veh_row = conn.execute("SELECT vehicle_id FROM vehicles WHERE vehicle_number = ?", (vehicle_number,)).fetchone()
            if not veh_row:
                cur = conn.execute(
                    "INSERT INTO vehicles (vehicle_number, owner_name, vehicle_type) VALUES (?, ?, ?)",
                    (vehicle_number, owner_name, vehicle_type)
                )
                conn.commit()
                vehicle_id = cur.lastrowid
            else:
                vehicle_id = veh_row["vehicle_id"]
                conn.execute(
                    "UPDATE vehicles SET owner_name = ?, vehicle_type = ? WHERE vehicle_id = ?",
                    (owner_name, vehicle_type, vehicle_id)
                )
                conn.commit()

            # Allocate first available slot
            conn.execute("BEGIN IMMEDIATE")
            slot = conn.execute(
                "SELECT slot_id, slot_number FROM parking_slots "
                "WHERE lot_id = ? AND slot_type = ? AND is_active = 1 AND occupancy_status = 'AVAILABLE' "
                "ORDER BY slot_number LIMIT 1",
                (lot_id, vehicle_type)
            ).fetchone()

            if not slot:
                conn.rollback()
                flash(f"No available {vehicle_type.lower()} slots left in this facility.", "error")
                return render_template("vehicle_entry.html", result=result)

            # Mark slot as occupied
            conn.execute("UPDATE parking_slots SET occupancy_status = 'OCCUPIED' WHERE slot_id = ?", (slot["slot_id"],))
            conn.commit()

            # Get hourly rate
            rate_row = conn.execute(
                "SELECT hourly_rate FROM parking_rates WHERE lot_id = ? AND vehicle_type = ? AND is_active = 1 ORDER BY rate_id DESC LIMIT 1",
                (lot_id, vehicle_type)
            ).fetchone()
            hourly_rate = float(rate_row["hourly_rate"]) if rate_row else 30.0

            # Generate ticket ID and create parking record
            ticket_id = f"P{lot_id:02d}{vehicle_id:04d}"
            entry_time = datetime.now().isoformat(timespec="seconds")
            worker_id = session["user_id"]

            conn.execute(
                "INSERT INTO parking_records (ticket_id, vehicle_id, slot_id, entry_worker_id, entry_time, applied_hourly_rate, chargeable_duration, total_fee, parking_status) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, 0.00, 'ACTIVE')",
                (ticket_id, vehicle_id, slot["slot_id"], worker_id, entry_time, hourly_rate)
            )
            conn.commit()

            result = {
                "success": True,
                "ticket_id": ticket_id,
                "vehicle_number": vehicle_number,
                "owner_name": owner_name,
                "vehicle_type": vehicle_type,
                "slot_number": slot["slot_number"],
                "hourly_rate": hourly_rate
            }
        finally:
            conn.close()

    return render_template("vehicle_entry.html", result=result)


# ---------------------------------------------------------------------------
# Vehicle Exit & Fee Calculation
# ---------------------------------------------------------------------------

@app.route("/worker/vehicle-exit")
@login_required
def vehicle_exit():
    'Vehicle exit search and checkout screen.'
    return render_template("vehicle_exit.html")


@app.route("/worker/vehicle-exit/search", methods=["POST"])
@login_required
def vehicle_exit_search():
    'Searches for active parking record by ticket ID or vehicle number.'
    search_value = clean_vehicle_number(request.form.get("search_value", ""))
    if not search_value:
        return jsonify({"error": "Please enter a ticket ID or vehicle number."}), 400

    lot = get_user_parking_lot(session["user_id"])
    lot_id = lot["lot_id"]

    conn = get_db()
    row = conn.execute(
        "SELECT pr.record_id, pr.ticket_id, pr.entry_time, pr.applied_hourly_rate, "
        "v.vehicle_number, v.owner_name, v.vehicle_type, s.slot_number "
        "FROM parking_records pr "
        "JOIN vehicles v ON v.vehicle_id = pr.vehicle_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE (pr.ticket_id = ? OR v.vehicle_number = ?) AND s.lot_id = ? AND pr.parking_status = 'ACTIVE'",
        (search_value, search_value, lot_id)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "No active parking record found for this vehicle in your facility."}), 404

    return jsonify({
        "record_id": row["record_id"],
        "ticket_id": row["ticket_id"],
        "vehicle_number": row["vehicle_number"],
        "owner_name": row["owner_name"],
        "vehicle_type": row["vehicle_type"],
        "slot_number": row["slot_number"],
        "entry_time": row["entry_time"],
        "hourly_rate": float(row["applied_hourly_rate"])
    })


@app.route("/worker/vehicle-exit/process", methods=["POST"])
@login_required
def vehicle_exit_process():
    'Completes payment, frees the slot, and finishes parking session.'
    data = request.get_json() or {}
    record_id = int(data.get("record_id", 0))
    payment_method = data.get("payment_method", "CASH").upper()
    entry_time = data.get("entry_time")
    hourly_rate = float(data.get("hourly_rate", 30.0))

    exit_time = datetime.now().isoformat(timespec="seconds")
    billable_hours, total_fee = calculate_parking_fee(hourly_rate, entry_time, exit_time)

    conn = get_db()
    try:
        # Find record
        rec = conn.execute("SELECT slot_id, ticket_id FROM parking_records WHERE record_id = ?", (record_id,)).fetchone()
        if not rec:
            return jsonify({"error": "Parking record not found."}), 404

        worker_id = session["user_id"]

        # Record payment
        conn.execute(
            "INSERT INTO payments (record_id, amount, payment_method, payment_status, processed_by) VALUES (?, ?, ?, 'SUCCESS', ?)",
            (record_id, total_fee, payment_method, worker_id)
        )

        # Update parking record status
        conn.execute(
            "UPDATE parking_records SET exit_worker_id = ?, exit_time = ?, chargeable_duration = ?, total_fee = ?, parking_status = 'COMPLETED' WHERE record_id = ?",
            (worker_id, exit_time, billable_hours, total_fee, record_id)
        )

        # Free the parking slot
        conn.execute("UPDATE parking_slots SET occupancy_status = 'AVAILABLE' WHERE slot_id = ?", (rec["slot_id"],))
        conn.commit()

        return jsonify({
            "success": True,
            "ticket_id": rec["ticket_id"],
            "exit_time": exit_time,
            "amount": total_fee,
            "payment_method": payment_method
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Parking History & Reports
# ---------------------------------------------------------------------------

@app.route("/history")
@login_required
def parking_history():
    'Displays parking logs and past transactions for this facility.'
    lot = get_user_parking_lot(session["user_id"])
    lot_id = lot["lot_id"]

    conn = get_db()
    rows = conn.execute(
        "SELECT pr.ticket_id, v.vehicle_number, v.owner_name, s.slot_number, "
        "pr.parking_status, pr.entry_time, pr.exit_time "
        "FROM parking_records pr "
        "JOIN vehicles v ON v.vehicle_id = pr.vehicle_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? "
        "ORDER BY pr.created_at DESC LIMIT 30",
        (lot_id,)
    ).fetchall()
    conn.close()

    records = [dict(r) for r in rows]
    return render_template("parking_history.html", records=records, lot=lot)


@app.route("/admin/reports")
@admin_required
def reports():
    'Displays financial and occupancy summary reports.'
    lot = get_user_parking_lot(session["user_id"])
    lot_id = lot["lot_id"]

    conn = get_db()

    # Revenue summaries
    today_rev = conn.execute(
        "SELECT COALESCE(SUM(p.amount),0) FROM payments p "
        "JOIN parking_records pr ON pr.record_id = p.record_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND p.payment_status = 'SUCCESS' AND date(p.payment_time) = date('now')",
        (lot_id,)
    ).fetchone()[0]

    week_rev = conn.execute(
        "SELECT COALESCE(SUM(p.amount),0) FROM payments p "
        "JOIN parking_records pr ON pr.record_id = p.record_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND p.payment_status = 'SUCCESS' AND p.payment_time >= date('now','-7 days')",
        (lot_id,)
    ).fetchone()[0]

    month_rev = conn.execute(
        "SELECT COALESCE(SUM(p.amount),0) FROM payments p "
        "JOIN parking_records pr ON pr.record_id = p.record_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND p.payment_status = 'SUCCESS' AND p.payment_time >= date('now','-30 days')",
        (lot_id,)
    ).fetchone()[0]

    txn_count = conn.execute(
        "SELECT COUNT(*) FROM payments p "
        "JOIN parking_records pr ON pr.record_id = p.record_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND p.payment_status = 'SUCCESS'",
        (lot_id,)
    ).fetchone()[0]

    revenue = {
        "today": float(today_rev),
        "week": float(week_rev),
        "month": float(month_rev),
        "successful_transactions": txn_count
    }

    # Payment method breakdown
    cash_amount = conn.execute(
        "SELECT COALESCE(SUM(p.amount),0) FROM payments p "
        "JOIN parking_records pr ON pr.record_id = p.record_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND p.payment_status='SUCCESS' AND p.payment_method='CASH'",
        (lot_id,)
    ).fetchone()[0]

    upi_amount = conn.execute(
        "SELECT COALESCE(SUM(p.amount),0) FROM payments p "
        "JOIN parking_records pr ON pr.record_id = p.record_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND p.payment_status='SUCCESS' AND p.payment_method='UPI'",
        (lot_id,)
    ).fetchone()[0]

    card_amount = conn.execute(
        "SELECT COALESCE(SUM(p.amount),0) FROM payments p "
        "JOIN parking_records pr ON pr.record_id = p.record_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "WHERE s.lot_id = ? AND p.payment_status='SUCCESS' AND p.payment_method='CARD'",
        (lot_id,)
    ).fetchone()[0]

    breakdown = {
        "cash": float(cash_amount),
        "upi": float(upi_amount),
        "card": float(card_amount)
    }

    # Occupancy statistics
    total_slots = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND is_active = 1", (lot_id,)).fetchone()[0]
    occupied_slots = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND is_active = 1 AND occupancy_status = 'OCCUPIED'", (lot_id,)).fetchone()[0]
    available_slots = total_slots - occupied_slots

    cars_total = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND is_active = 1 AND slot_type = 'CAR'", (lot_id,)).fetchone()[0]
    cars_occ = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND is_active = 1 AND slot_type = 'CAR' AND occupancy_status = 'OCCUPIED'", (lot_id,)).fetchone()[0]

    bikes_total = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND is_active = 1 AND slot_type = 'BIKE'", (lot_id,)).fetchone()[0]
    bikes_occ = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE lot_id = ? AND is_active = 1 AND slot_type = 'BIKE' AND occupancy_status = 'OCCUPIED'", (lot_id,)).fetchone()[0]

    conn.close()

    occupancy = {
        "total_slots": total_slots,
        "available_slots": available_slots,
        "occupied_slots": occupied_slots,
        "car_occupancy": round((cars_occ / cars_total * 100), 2) if cars_total else 0,
        "bike_occupancy": round((bikes_occ / bikes_total * 100), 2) if bikes_total else 0,
        "overall_occupancy": round((occupied_slots / total_slots * 100), 2) if total_slots else 0
    }

    return render_template("reports.html", revenue=revenue, occupancy=occupancy, breakdown=breakdown, lot=lot)


# ---------------------------------------------------------------------------
# Printable Slips & Text File Downloads
# ---------------------------------------------------------------------------

@app.route("/slip/entry/<ticket_id>")
@login_required
def entry_slip(ticket_id):
    'Generates printable thermal slip or downloadable text slip for vehicle entry.'
    conn = get_db()
    row = conn.execute(
        "SELECT pr.ticket_id, pr.entry_time, pr.applied_hourly_rate, "
        "v.vehicle_number, v.owner_name, v.vehicle_type, "
        "s.slot_number, u.full_name as attendant_name, l.lot_name, l.location "
        "FROM parking_records pr "
        "JOIN vehicles v ON v.vehicle_id = pr.vehicle_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "JOIN parking_lots l ON l.lot_id = s.lot_id "
        "LEFT JOIN users u ON u.user_id = pr.entry_worker_id "
        "WHERE pr.ticket_id = ?",
        (ticket_id,)
    ).fetchone()
    conn.close()

    if not row:
        flash("Parking record not found.", "error")
        return redirect(url_for("parking_history"))

    slip_data = dict(row)

    if request.args.get("download"):
        slip_text = (
            "========================================\n"
            "     SMART PARKING LOT MANAGEMENT       \n"
            "========================================\n"
            f"Facility   : {slip_data['lot_name']} ({slip_data['location']})\n"
            f"Slip Type  : VEHICLE ENTRY SLIP\n"
            f"Ticket ID  : {slip_data['ticket_id']}\n"
            f"Entry Time : {slip_data['entry_time']}\n"
            "----------------------------------------\n"
            f"Vehicle No : {slip_data['vehicle_number']}\n"
            f"Owner Name : {slip_data['owner_name']}\n"
            f"Type       : {slip_data['vehicle_type']}\n"
            f"Slot No    : {slip_data['slot_number']}\n"
            f"Rate       : ₹{slip_data['applied_hourly_rate']} / hour\n"
            f"Attendant  : {slip_data['attendant_name'] or 'Staff'}\n"
            "----------------------------------------\n"
            "* Please retain this slip until exit.\n"
            "* Parking at vehicle owner's risk.\n"
            "========================================\n"
        )
        return Response(
            slip_text,
            mimetype="text/plain",
            headers={"Content-Disposition": f"attachment; filename=Parking_Slip_{ticket_id}.txt"}
        )

    return render_template("entry_slip_print.html", slip=slip_data)


@app.route("/slip/exit/<ticket_id>")
@login_required
def exit_receipt(ticket_id):
    'Generates printable thermal receipt or downloadable text receipt for exit/payment.'
    conn = get_db()
    row = conn.execute(
        "SELECT pr.ticket_id, pr.entry_time, pr.exit_time, pr.chargeable_duration, pr.total_fee, "
        "pr.applied_hourly_rate, v.vehicle_number, v.owner_name, v.vehicle_type, "
        "s.slot_number, u.full_name as attendant_name, l.lot_name, l.location, "
        "p.amount as paid_amount, p.payment_method, p.payment_time "
        "FROM parking_records pr "
        "JOIN vehicles v ON v.vehicle_id = pr.vehicle_id "
        "JOIN parking_slots s ON s.slot_id = pr.slot_id "
        "JOIN parking_lots l ON l.lot_id = s.lot_id "
        "LEFT JOIN users u ON u.user_id = pr.exit_worker_id "
        "LEFT JOIN payments p ON p.record_id = pr.record_id AND p.payment_status = 'SUCCESS' "
        "WHERE pr.ticket_id = ?",
        (ticket_id,)
    ).fetchone()
    conn.close()

    if not row:
        flash("Exit record not found.", "error")
        return redirect(url_for("parking_history"))

    receipt_data = dict(row)

    if request.args.get("download"):
        receipt_text = (
            "========================================\n"
            "     SMART PARKING LOT MANAGEMENT       \n"
            "========================================\n"
            f"Facility   : {receipt_data['lot_name']} ({receipt_data['location']})\n"
            f"Slip Type  : PAYMENT & EXIT RECEIPT\n"
            f"Ticket ID  : {receipt_data['ticket_id']}\n"
            f"Exit Time  : {receipt_data['exit_time'] or '-'}\n"
            "----------------------------------------\n"
            f"Vehicle No : {receipt_data['vehicle_number']}\n"
            f"Owner Name : {receipt_data['owner_name']}\n"
            f"Type       : {receipt_data['vehicle_type']}\n"
            f"Slot No    : {receipt_data['slot_number']}\n"
            f"Entry Time : {receipt_data['entry_time']}\n"
            f"Duration   : {receipt_data['chargeable_duration']} hour(s)\n"
            f"Total Paid : ₹{receipt_data['paid_amount'] or receipt_data['total_fee']}\n"
            f"Method     : {receipt_data['payment_method'] or 'CASH'}\n"
            f"Processed  : {receipt_data['attendant_name'] or 'Staff'}\n"
            "----------------------------------------\n"
            "      Thank You! Visit Again.\n"
            "========================================\n"
        )
        return Response(
            receipt_text,
            mimetype="text/plain",
            headers={"Content-Disposition": f"attachment; filename=Exit_Receipt_{ticket_id}.txt"}
        )

    return render_template("exit_receipt_print.html", receipt=receipt_data)


# ---------------------------------------------------------------------------
# Run Application
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
