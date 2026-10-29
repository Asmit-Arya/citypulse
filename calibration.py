"""
=============================================================================
FILE: calibration.py
TIER: Intelligence & Statistical Calibration Layer
-----------------------------------------------------------------------------
PURPOSE:
This module provides dynamic wait-time estimation and runtime self-correction
using an Exponential Moving Average (EMA) algorithm combined with outlier
filtering and multi-station workload distribution.

ARCHITECTURAL ROLE & SYSTEM INTERACTION:
- Called by `app.py` when a merchant completes a service (/api/queue/<id>/complete)
  to dynamically update historical service benchmarks in SQLite.
- Called by `app.py` when querying /api/businesses/<id>/queue to generate
  accurate wait intervals (e.g., '20–30 mins') for the customer interface.

MATHEMATICAL FORMULATION:
1. Outlier Rejection: 
   Discard actual durations t if t < 3.0 minutes (accidental clicks)
   or t > 120.0 minutes (abandoned tickets).
2. Exponential Moving Average:
   EMA_new = alpha * t_actual + (1 - alpha) * EMA_old
   where alpha = 0.2 grants 20% weight to recent merchant pace and 80%
   to historical baseline data.
3. Multi-Station Wait Allocation:
   T_wait = (Sum of Service Durations + AI Modifiers) / ActiveCounters
=============================================================================
"""

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("CITYPULSE_DB_PATH", str(Path(__file__).resolve().with_name("citypulse.db"))))

def get_db_connection():
    """
    Establishes a connection to the local SQLite database file.
    
    Setting row_factory = sqlite3.Row configures SQLite to return rows as
    dictionary-like objects, allowing column access by field name (e.g., row['name'])
    instead of arbitrary zero-based numeric indices.
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=8)
    conn.row_factory = sqlite3.Row
    return conn

def update_service_ema(service_id, actual_duration_minutes, alpha=0.2):
    """
    Dynamically updates the baseline estimated duration of a service using
    Exponential Moving Average (EMA).

    Parameters:
        service_id (int): Primary key of the service being calibrated.
        actual_duration_minutes (float): Real-world elapsed execution time.
        alpha (float): Smoothing factor between 0.0 and 1.0 (default 0.2).

    Returns:
        float: The newly calibrated duration, or None if the input was filtered.
    """
    actual_duration = float(actual_duration_minutes)

    # -------------------------------------------------------------------------
    # STEP 1: Defensive Data Sanitization (Outlier Filtering)
    # Prevents accidental premature clicks (<3 min) or merchant lunch breaks
    # (>120 min) from skewing the statistical baseline.
    # -------------------------------------------------------------------------
    if actual_duration < 3.0 or actual_duration > 120.0:
        print(f"[Calibration Alert] Outlier ignored: {actual_duration:.1f} mins for Service ID {service_id}")
        return None

    conn = get_db_connection()
    cursor = conn.cursor()

    # -------------------------------------------------------------------------
    # STEP 2: Fetch Current Calibration State from SQLite
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # STEP 3: Compute the New EMA Value
    # If no services were previously recorded, set the baseline directly to
    # the actual duration; otherwise apply the weighted smoothing formula.
    # -------------------------------------------------------------------------
    if completed_count == 0:
        new_ema = actual_duration
    else:
        new_ema = (alpha * actual_duration) + ((1.0 - alpha) * old_ema)

    new_ema = round(new_ema, 1)

    # -------------------------------------------------------------------------
    # STEP 4: Persist the Calibrated Benchmark Back to SQLite
    # -------------------------------------------------------------------------
    cursor.execute("""
        UPDATE services 
        SET current_estimated_duration = ?, 
            total_completed_count = total_completed_count + 1 
        WHERE id = ?
    """, (new_ema, service_id))

    conn.commit()
    conn.close()

    print(f"[Calibration Success] Service #{service_id}: {old_ema}m -> {new_ema}m (Actual: {actual_duration:.1f}m)")
    return new_ema

def calculate_dynamic_queue_wait(business_id):
    """
    Calculates dynamic wait time for an incoming patron by aggregating the
    calibrated durations and AI modifiers of all active queue tickets,
    distributed across concurrent active workstations.

    Parameters:
        business_id (int): Primary key of the target business establishment.

    Returns:
        dict: Minimum wait, maximum wait, and a UI-ready display string.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # -------------------------------------------------------------------------
    # STEP 1: Query Business Operational Capacity
    # -------------------------------------------------------------------------
    cursor.execute("SELECT active_counters FROM businesses WHERE id = ?", (business_id,))
    biz = cursor.fetchone()
    # Guard against division by zero if active_counters is null or zero
    active_counters = max(1, biz["active_counters"] if biz and biz["active_counters"] else 1)

    # -------------------------------------------------------------------------
    # STEP 2: Fetch Active and Waiting Tickets
    # Performs a SQL LEFT JOIN between queue_tickets and services to pull
    # calibrated baseline durations alongside individual ticket AI modifiers.
    # -------------------------------------------------------------------------
    cursor.execute("""
        SELECT q.status, q.ai_duration_modifier, s.current_estimated_duration
        FROM queue_tickets q
        LEFT JOIN services s ON q.service_id = s.id
        WHERE q.business_id = ? AND q.status IN ('waiting', 'in_service')
    """, (business_id,))
    tickets = cursor.fetchall()
    conn.close()

    # If the queue is empty, the customer can be seated almost immediately
    if not tickets:
        return {"min_wait": 0, "max_wait": 5, "display": "0–5 mins"}

    # -------------------------------------------------------------------------
    # STEP 3: Aggregate Pending Workload
    # -------------------------------------------------------------------------
    total_work_minutes = 0.0
    for t in tickets:
        base_duration = float(t["current_estimated_duration"] if t["current_estimated_duration"] else 15.0)
        modifier = float(t["ai_duration_modifier"] if t["ai_duration_modifier"] else 0.0)

        if t["status"] == "in_service":
            # For the customer currently in the chair, assume 50% of the cut remains
            total_work_minutes += (base_duration + modifier) * 0.5
        else:
            # Full duration for tickets waiting in line
            total_work_minutes += (base_duration + modifier)

    # -------------------------------------------------------------------------
    # STEP 4: Workload Distribution Across Stations
    # -------------------------------------------------------------------------
    projected_wait = total_work_minutes / active_counters

    # Generate a realistic statistical window (+/- 15%)
    min_wait = max(0, int(round(projected_wait * 0.85)))
    max_wait = max(min_wait + 5, int(round(projected_wait * 1.15)))

    return {
        "min_wait": min_wait,
        "max_wait": max_wait,
        "display": f"{min_wait}–{max_wait} mins"
    }

# -----------------------------------------------------------------------------
# Standalone Unit Test Block
# Executes only when running `python calibration.py` directly from the terminal.
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("Testing calibration logic...")
    print("Outlier check (< 3 mins):", update_service_ema(1, 1.5))
    print("Outlier check (> 120 mins):", update_service_ema(1, 130.0))