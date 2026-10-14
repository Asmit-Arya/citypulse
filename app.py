import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from calibration import update_service_ema, calculate_dynamic_queue_wait
from ai_service import get_ai_ticket_modifier, estimate_wait_with_ai

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect("citypulse.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def home():
    return render_template("index.html")

# 1. List Businesses with optional city/category filters
@app.route("/api/businesses", methods=["GET"])
def api_get_businesses():
    city = request.args.get("city")
    category = request.args.get("category")
    conn = get_db()
    query = "SELECT * FROM businesses WHERE 1=1"
    params = []
    if city:
        query += " AND city = ?"
        params.append(city)
    if category:
        query += " AND category = ?"
        params.append(category)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows]), 200

# 2. Get Merchant Queue & Active Patron
@app.route("/api/businesses/<int:business_id>/queue", methods=["GET"])
def get_merchant_queue(business_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Active patron in chair
    cursor.execute("""
        SELECT q.*, s.name as service_name, s.current_estimated_duration
        FROM queue_tickets q
        JOIN services s ON q.service_id = s.id
        WHERE q.business_id = ? AND q.status = 'in_service'
        LIMIT 1;
    """, (business_id,))
    active = cursor.fetchone()

    # Waiting patrons
    cursor.execute("""
        SELECT q.*, s.name as service_name, s.current_estimated_duration
        FROM queue_tickets q
        JOIN services s ON q.service_id = s.id
        WHERE q.business_id = ? AND q.status = 'waiting'
        ORDER BY q.created_at ASC;
    """, (business_id,))
    waiting = cursor.fetchall()
    conn.close()

    wait_stats = calculate_dynamic_queue_wait(business_id)

    return jsonify({
        "active_patron": dict(active) if active else None,
        "waiting_list": [dict(r) for r in waiting],
        "wait_stats": wait_stats
    }), 200

# 3. Add Walk-In Customer
@app.route("/api/walkin", methods=["POST"])
def add_walkin():
    data = request.get_json() or {}
    b_id = data.get("business_id", 1)
    s_id = data.get("service_id", 1)
    name = data.get("customer_name", "").strip() or "Walk-in Guest"

    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO queue_tickets (business_id, service_id, customer_name, is_walkin, status, created_at)
        VALUES (?, ?, ?, 1, 'waiting', ?);
    """, (b_id, s_id, name, now_str))
    cursor.execute("UPDATE businesses SET current_queue = current_queue + 1 WHERE id = ?;", (b_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"{name} added to queue."}), 201

# 4. Book Appointment (Online User)
@app.route("/api/appointments", methods=["POST"])
def book_appointment():
    data = request.get_json() or {}
    b_id = data.get("business_id", 1)
    s_id = data.get("service_id", 1)
    name = data.get("customer_name", "").strip()
    notes = data.get("notes", "").strip()

    if not name:
        return jsonify({"error": "Customer name is required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM services WHERE id = ?;", (s_id,))
    s_row = cursor.fetchone()
    service_name = s_row["name"] if s_row else "Standard Service"

    ai_mod = get_ai_ticket_modifier(service_name, notes)
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO queue_tickets (business_id, service_id, customer_name, notes, is_walkin, status, ai_duration_modifier, created_at)
        VALUES (?, ?, ?, ?, 0, 'waiting', ?, ?);
    """, (b_id, s_id, name, notes, ai_mod, now_str))
    cursor.execute("UPDATE businesses SET current_queue = current_queue + 1 WHERE id = ?;", (b_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": f"{name} enrolled in virtual queue.", "ai_modifier": ai_mod}), 201

# 5. Seat Next Customer
@app.route("/api/queue/<int:ticket_id>/start", methods=["PUT"])
def seat_customer(ticket_id):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE queue_tickets SET status = 'in_service', started_at = ?
        WHERE id = ? AND status = 'waiting';
    """, (now_str, ticket_id))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Ticket #{ticket_id} seated in chair."}), 200

# 6. Complete Service & Calibrate
@app.route("/api/queue/<int:ticket_id>/complete", methods=["PUT"])
def complete_service(ticket_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM queue_tickets WHERE id = ?;", (ticket_id,))
    ticket = cursor.fetchone()
    if not ticket:
        conn.close()
        return jsonify({"error": "Ticket not found"}), 404

    now = datetime.utcnow()
    started_at_str = ticket["started_at"]
    if started_at_str:
        try:
            started = datetime.strptime(started_at_str, "%Y-%m-%d %H:%M:%S")
            duration = (now - started).total_seconds() / 60.0
        except ValueError:
            duration = 20.0
    else:
        duration = 20.0

    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE queue_tickets SET status = 'completed', completed_at = ? WHERE id = ?;", (now_str, ticket_id))
    cursor.execute("UPDATE businesses SET current_queue = MAX(0, current_queue - 1) WHERE id = ?;", (ticket["business_id"],))
    conn.commit()
    conn.close()

    new_ema = update_service_ema(ticket["service_id"], duration)
    return jsonify({"message": "Service completed", "duration": round(duration, 1), "new_ema": new_ema}), 200

if __name__ == "__main__":
    app.run(debug=True)