# File: calibration.py
# Purpose: Real-Time Dynamic Wait Time and EMA Calibration Engine

import sqlite3

def get_db_connection():
    """Establishes connection to the SQLite database with row-name access."""
    conn = sqlite3.connect("citypulse.db")
    conn.row_factory = sqlite3.Row
    return conn

def update_service_ema(service_id, actual_duration_minutes, alpha=0.2):
    """
    Applies Exponential Moving Average (EMA) to update baseline service durations.
    Filters out extreme operational outliers (< 3 mins or > 120 mins).
    """
    actual_duration = float(actual_duration_minutes)

    # 1. Outlier Filtering: Discard unrealistic or accidental clicks
    if actual_duration < 3.0 or actual_duration > 120.0:
        print(f"[Calibration] Outlier ignored: {actual_duration:.1f} mins for Service ID {service_id}")
        return None

    conn = get_db_connection()
    cursor = conn.cursor()

    # 2. Retrieve existing calibrated values for this service
    cursor.execute("""
        SELECT current_estimated_duration, total_completed_count 
        FROM services 
        WHERE id = ?
    """, (service_id,))
    service = cursor.fetchone()

    if not service:
        conn.close()
        return None

    old_ema = float(service["current_estimated_duration"])
    completed_count = int(service["total_completed_count"])

    # 3. Calculate new EMA value
    if completed_count == 0:
        # First completed service initializes the baseline
        new_ema = actual_duration
    else:
        new_ema = (alpha * actual_duration) + ((1.0 - alpha) * old_ema)

    new_ema = round(new_ema, 1)

    # 4. Persist updated values into the services table
    cursor.execute("""
        UPDATE services 
        SET current_estimated_duration = ?, 
            total_completed_count = total_completed_count + 1 
        WHERE id = ?
    """, (new_ema, service_id))

    conn.commit()
    conn.close()

    print(f"[Calibration] Service ID {service_id} updated: {old_ema}m -> {new_ema}m (Actual: {actual_duration:.1f}m)")
    return new_ema

def calculate_dynamic_queue_wait(business_id):
    """
    Calculates dynamic wait time for a newcomer by summing up baseline durations
    and AI modifiers of all pending tickets, distributed across active counters.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch active counter capacity
    cursor.execute("SELECT active_counters FROM businesses WHERE id = ?", (business_id,))
    biz = cursor.fetchone()
    active_counters = max(1, biz["active_counters"] if biz and biz["active_counters"] else 1)

    # 2. Fetch all tickets currently waiting or actively in service
    cursor.execute("""
        SELECT q.status, q.ai_duration_modifier, s.current_estimated_duration
        FROM queue_tickets q
        LEFT JOIN services s ON q.service_id = s.id
        WHERE q.business_id = ? AND q.status IN ('waiting', 'in_service')
    """, (business_id,))
    tickets = cursor.fetchall()
    conn.close()

    # If queue is empty, wait is effectively zero
    if not tickets:
        return {"min_wait": 0, "max_wait": 5, "display": "0–5 mins"}

    # 3. Sum total pending workload
    total_work_minutes = 0.0
    for t in tickets:
        base_duration = float(t["current_estimated_duration"] if t["current_estimated_duration"] else 15.0)
        modifier = float(t["ai_duration_modifier"] if t["ai_duration_modifier"] else 0.0)

        if t["status"] == "in_service":
            # For the customer currently in the chair, assume half of the cut remains
            total_work_minutes += (base_duration + modifier) * 0.5
        else:
            total_work_minutes += (base_duration + modifier)

    # 4. Divide across active workstations
    projected_wait = total_work_minutes / active_counters

    # Generate a realistic window (+/- 15%)
    min_wait = max(0, int(round(projected_wait * 0.85)))
    max_wait = max(min_wait + 5, int(round(projected_wait * 1.15)))

    return {
        "min_wait": min_wait,
        "max_wait": max_wait,
        "display": f"{min_wait}–{max_wait} mins"
    }

# Self-testing entrypoint
if __name__ == "__main__":
    print("Testing calibration logic...")
    print("Outlier check (< 3 mins):", update_service_ema(1, 1.5))
    print("Outlier check (> 120 mins):", update_service_ema(1, 130.0))