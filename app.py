# File: app.py
# Purpose: Core Flask Server with Queue Lifecycle & Calibration Hooks

import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from calibration import update_service_ema, calculate_dynamic_queue_wait
from ai_service import get_ai_ticket_modifier

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect("citypulse.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- 1. Home Page Route ---
@app.route("/")
def home():
    return render_template("index.html")

# --- 2. Merchant Queue Inspection Endpoint ---
@app.route("/api/businesses/<int:business_id>/queue", methods=["GET"])
def get_merchant_queue(business_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Retrieve the patron currently in the chair
        cursor.execute("""
            SELECT q.*, s.name as service_name, s.current_estimated_duration
            FROM queue_tickets q
            JOIN services s ON q.service_id = s.id
            WHERE q.business_id = ? AND q.status = 'in_service'
            LIMIT 1
        """, (business_id,))
        active_row = cursor.fetchone()
        active_patron = dict(active_row) if active_row else None

        # Retrieve all waiting customers in order of arrival
        cursor.execute("""
            SELECT q.*, s.name as service_name, s.current_estimated_duration
            FROM queue_tickets q
            JOIN services s ON q.service_id = s.id
            WHERE q.business_id = ? AND q.status = 'waiting'
            ORDER BY q.created_at ASC
        """, (business_id,))
        waiting_rows = cursor.fetchall()
        waiting_list = [dict(r) for r in waiting_rows]
    except sqlite3.OperationalError:
        # Fallback if database tables are still being set up by Teammate 2
        active_patron = None
        waiting_list = []
    finally:
        conn.close()

    # Calculate real-time dynamic wait window using calibration engine
    try:
        wait_stats = calculate_dynamic_queue_wait(business_id)
    except Exception:
        wait_stats = {"min_wait": 0, "max_wait": 5, "display": "0–5 mins"}

    return jsonify({
        "active_patron": active_patron,
        "waiting_list": waiting_list,
        "wait_stats": wait_stats
    }), 200

# --- 3. Add In-Person Walk-In Customer Endpoint ---
@app.route("/api/walkin", methods=["POST"])
def add_walkin():
    data = request.get_json() or {}
    business_id = data.get("business_id", 1)
    service_id = data.get("service_id", 1)
    customer_name = data.get("customer_name", "").strip() or "Walk-in Guest"

    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    try:
        cursor.execute("""
            INSERT INTO queue_tickets (business_id, service_id, customer_name, is_walkin, status, created_at)
            VALUES (?, ?, ?, 1, 'waiting', ?)
        """, (business_id, service_id, customer_name, now_str))

        cursor.execute("UPDATE businesses SET current_queue = current_queue + 1 WHERE id = ?", (business_id,))
        conn.commit()
    except sqlite3.OperationalError as e:
        conn.close()
        return jsonify({"error": f"Database table error: {str(e)}"}), 500

    conn.close()
    return jsonify({"message": f"{customer_name} added to queue successfully."}), 201

# --- 4. Online App Customer Booking with AI Triage ---
@app.route("/api/appointments", methods=["POST"])
def book_appointment():
    data = request.get_json() or {}
    business_id = data.get("business_id", 1)
    service_id = data.get("service_id", 1)
    customer_name = data.get("customer_name", "").strip()
    notes = data.get("notes", "").strip()

    if not customer_name:
        return jsonify({"error": "Customer name is required"}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Fetch service name for AI context
    try:
        cursor.execute("SELECT name FROM services WHERE id = ?", (service_id,))
        service_row = cursor.fetchone()
        service_name = service_row["name"] if service_row else "General Service"
    except sqlite3.OperationalError:
        service_name = "General Service"

    # Calculate AI modifier based on customer notes
    ai_modifier = get_ai_ticket_modifier(service_name, notes)
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    try:
        cursor.execute("""
            INSERT INTO queue_tickets (business_id, service_id, customer_name, notes, is_walkin, status, ai_duration_modifier, created_at)
            VALUES (?, ?, ?, ?, 0, 'waiting', ?, ?)
        """, (business_id, service_id, customer_name, notes, ai_modifier, now_str))

        cursor.execute("UPDATE businesses SET current_queue = current_queue + 1 WHERE id = ?", (business_id,))
        conn.commit()
    except sqlite3.OperationalError as e:
        conn.close()
        return jsonify({"error": f"Database table error: {str(e)}"}), 500

    conn.close()
    return jsonify({
        "message": f"{customer_name} enrolled in virtual queue.",
        "ai_modifier_applied": ai_modifier
    }), 201

# --- 5. Seat Next Customer Endpoint ---
@app.route("/api/queue/<int:ticket_id>/start", methods=["PUT"])
def seat_customer(ticket_id):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE queue_tickets 
        SET status = 'in_service', started_at = ? 
        WHERE id = ?
    """, (now_str, ticket_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Patron is now in chair."}), 200

# --- 6. Complete Service & Trigger EMA Calibration ---
@app.route("/api/queue/<int:ticket_id>/complete", methods=["PUT"])
def complete_service(ticket_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM queue_tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    if not ticket:
        conn.close()
        return jsonify({"error": "Ticket not found"}), 404

    now = datetime.utcnow()
    started_at_str = ticket["started_at"]

    # Calculate duration in minutes
    if started_at_str:
        try:
            started_at = datetime.strptime(started_at_str, "%Y-%m-%d %H:%M:%S")
            duration_minutes = (now - started_at).total_seconds() / 60.0
        except ValueError:
            duration_minutes = 20.0
    else:
        duration_minutes = 20.0

    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE queue_tickets 
        SET status = 'completed', completed_at = ? 
        WHERE id = ?
    """, (now_str, ticket_id))

    cursor.execute("""
        UPDATE businesses 
        SET current_queue = MAX(0, current_queue - 1) 
        WHERE id = ?
    """, (ticket["business_id"],))

    conn.commit()
    conn.close()

    # Trigger EMA calibration from calibration.py
    new_ema = update_service_ema(ticket["service_id"], duration_minutes)

    return jsonify({
        "message": "Service completed successfully.",
        "actual_duration_minutes": round(duration_minutes, 1),
        "calibrated_ema": new_ema
    }), 200

if __name__ == "__main__":
    app.run(debug=True)