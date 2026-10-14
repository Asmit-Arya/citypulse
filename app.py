"""
=============================================================================
FILE: app.py
TIER: Application Server & REST API Routing Layer
-----------------------------------------------------------------------------
PURPOSE:
Coordinates HTTP network traffic, serves presentation templates, executes
parameterized database transactions against SQLite, and routes queue transitions.

ARCHITECTURAL PRINCIPLES:
1. Stateless REST Design:
   Every incoming HTTP request encapsulates all parameters required to process
   the transaction, returning standardized HTTP status codes (200, 201, 400, 404).
2. SQL Injection Prevention:
   All queries utilize parameterized placeholders (?) rather than string interpolation,
   neutralizing arbitrary SQL execution attacks.
3. Queue Lifecycle State Machine:
   Tickets progress: 'waiting' -> 'in_service' -> 'completed'.
=============================================================================
"""

import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from calibration import update_service_ema, calculate_dynamic_queue_wait
from ai_service import get_ai_ticket_modifier, estimate_wait_with_ai

# Initialize the Flask WSGI application instance
app = Flask(__name__)

def get_db():
    """Provides a connection handle to the relational persistence layer."""
    conn = sqlite3.connect("citypulse.db")
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------------------------------------------------------------
# ROUTE 1: Presentation Root
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    """Renders the single-page HTML interface from the templates folder."""
    return render_template("index.html")

# -----------------------------------------------------------------------------
# ROUTE 2: Merchant Queue Inspection API
# -----------------------------------------------------------------------------
@app.route("/api/businesses/<int:business_id>/queue", methods=["GET"])
def get_merchant_queue(business_id):
    """
    Returns the real-time operational state of an establishment, including
    the patron currently in the chair, the waiting queue, and calibrated wait times.
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Fetch the active customer currently receiving service
        cursor.execute("""
            SELECT q.*, s.name as service_name, s.current_estimated_duration
            FROM queue_tickets q
            JOIN services s ON q.service_id = s.id
            WHERE q.business_id = ? AND q.status = 'in_service'
            LIMIT 1
        """, (business_id,))
        active_row = cursor.fetchone()
        active_patron = dict(active_row) if active_row else None

        # Fetch all waiting tickets ordered by arrival time (FIFO - First In, First Out)
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
        active_patron = None
        waiting_list = []
    finally:
        conn.close()

    # Calculate calibrated wait interval using statistical engine
    try:
        wait_stats = calculate_dynamic_queue_wait(business_id)
    except Exception:
        wait_stats = {"min_wait": 0, "max_wait": 5, "display": "0–5 mins"}

    return jsonify({
        "active_patron": active_patron,
        "waiting_list": waiting_list,
        "wait_stats": wait_stats
    }), 200

# -----------------------------------------------------------------------------
# ROUTE 3: Register Walk-In Patron API
# -----------------------------------------------------------------------------
@app.route("/api/walkin", methods=["POST"])
def add_walkin():
    """
    Registers an in-person customer directly at the front desk into the queue.
    Sets is_walkin = 1 and status = 'waiting'.
    """
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
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    conn.close()
    return jsonify({"message": f"{customer_name} added to queue successfully."}), 201

# -----------------------------------------------------------------------------
# ROUTE 4: Online App Booking with Cognitive AI Triage API
# -----------------------------------------------------------------------------
@app.route("/api/appointments", methods=["POST"])
def book_appointment():
    """
    Allows online mobile users to join the virtual queue. Passes qualitative
    notes through the AI triage engine to compute dynamic complexity modifiers.
    """
    data = request.get_json() or {}
    business_id = data.get("business_id", 1)
    service_id = data.get("service_id", 1)
    customer_name = data.get("customer_name", "").strip()
    notes = data.get("notes", "").strip()

    if not customer_name:
        return jsonify({"error": "Customer name is required"}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM services WHERE id = ?", (service_id,))
        service_row = cursor.fetchone()
        service_name = service_row["name"] if service_row else "General Service"
    except sqlite3.OperationalError:
        service_name = "General Service"

    # Compute AI complexity modifier
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
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    conn.close()
    return jsonify({
        "message": f"{customer_name} enrolled in virtual queue.",
        "ai_modifier_applied": ai_modifier
    }), 201

# -----------------------------------------------------------------------------
# ROUTE 5: Seat Next Patron API
# -----------------------------------------------------------------------------
@app.route("/api/queue/<int:ticket_id>/start", methods=["PUT"])
def seat_customer(ticket_id):
    """
    Transitions a customer ticket from 'waiting' to 'in_service'.
    Records the precise UTC start timestamp to calculate duration upon completion.
    """
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

    return jsonify({"message": "Patron is now active in chair."}), 200

# -----------------------------------------------------------------------------
# ROUTE 6: Complete Service & Trigger Statistical Calibration API
# -----------------------------------------------------------------------------
@app.route("/api/queue/<int:ticket_id>/complete", methods=["PUT"])
def complete_service(ticket_id):
    """
    Marks a service completed, computes actual elapsed duration, and invokes
    the EMA calibration helper to update future duration predictions.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM queue_tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    if not ticket:
        conn.close()
        return jsonify({"error": "Ticket not found"}), 404

    now = datetime.utcnow()
    started_at_str = ticket["started_at"]

    # Calculate actual elapsed service duration
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

    # Trigger self-learning statistical calibration
    new_ema = update_service_ema(ticket["service_id"], duration_minutes)

    return jsonify({
        "message": "Service completed successfully.",
        "actual_duration_minutes": round(duration_minutes, 1),
        "calibrated_ema": new_ema
    }), 200

# -----------------------------------------------------------------------------
# ROUTE 7: AI Wait-Time Estimation Helper API
# -----------------------------------------------------------------------------
@app.route("/api/ai/estimate-wait", methods=["POST"])
def api_ai_estimate():
    data = request.get_json() or {}
    queue = int(data.get("queue", 1))
    wait_per_person = int(data.get("wait_per_person", 15))
    notes = data.get("notes", "")

    result = estimate_wait_with_ai(queue, wait_per_person, notes)
    return jsonify(result), 200

# Server launch entrypoint for local execution
if __name__ == "__main__":
    app.run(debug=True)