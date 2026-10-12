# File: init_db.py
# Purpose: Initialize SQLite tables and populate seed data

import sqlite3

def setup_database():
    conn = sqlite3.connect("citypulse.db")
    cursor = conn.cursor()

    # 1. Businesses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS businesses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        city TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        current_queue INTEGER NOT NULL DEFAULT 0,
        active_counters INTEGER NOT NULL DEFAULT 1
    );
    """)

    # 2. Services Table (with EMA duration tracking)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        current_estimated_duration REAL NOT NULL,
        total_completed_count INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (business_id) REFERENCES businesses (id)
    );
    """)

    # 3. Queue Tickets Table (Tracks walk-ins vs app users and timestamps)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS queue_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        service_id INTEGER NOT NULL,
        customer_name TEXT NOT NULL,
        notes TEXT,
        is_walkin INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'waiting',
        ai_duration_modifier REAL NOT NULL DEFAULT 0,
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (business_id) REFERENCES businesses (id),
        FOREIGN KEY (service_id) REFERENCES services (id)
    );
    """)

    # Insert default business if missing
    cursor.execute("SELECT COUNT(*) FROM businesses")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO businesses (name, category, city, status, current_queue, active_counters)
        VALUES ('Urban Cut Studio', 'Salon', 'Raipur', 'open', 2, 1)
        """)
        biz_id = cursor.lastrowid

        # Insert default services with initial estimated durations
        cursor.execute("""
        INSERT INTO services (business_id, name, current_estimated_duration, total_completed_count)
        VALUES 
        (?, 'Standard Haircut', 20.0, 5),
        (?, 'Beard Trim & Lineup', 10.0, 5),
        (?, 'Hair Color & Styling', 45.0, 2)
        """, (biz_id, biz_id, biz_id))

        # Insert sample waiting tickets
        cursor.execute("""
        INSERT INTO queue_tickets (business_id, service_id, customer_name, is_walkin, status, created_at)
        VALUES 
        (?, 1, 'Rahul Sharma', 0, 'waiting', datetime('now')),
        (?, 2, 'Walk-in Guest', 1, 'waiting', datetime('now'))
        """, (biz_id, biz_id))

        print("Database initialized with seed business, services, and queue tickets!")
    else:
        print("Database already contains data.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    setup_database()