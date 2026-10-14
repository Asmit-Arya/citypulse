import sqlite3

def initialize_database():
    conn = sqlite3.connect("citypulse.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

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

    # 2. Services Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        current_estimated_duration REAL NOT NULL,
        total_completed_count INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (business_id) REFERENCES businesses (id) ON DELETE CASCADE
    );
    """)

    # 3. Queue Tickets Table
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
        FOREIGN KEY (business_id) REFERENCES businesses (id) ON DELETE CASCADE,
        FOREIGN KEY (service_id) REFERENCES services (id) ON DELETE CASCADE
    );
    """)

    # Populate seed data if table is empty
    cursor.execute("SELECT COUNT(*) FROM businesses;")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO businesses (name, category, city, status, current_queue, active_counters)
            VALUES 
            ('Urban Cut Studio', 'Salon', 'Raipur', 'open', 2, 1),
            ('Apex Dental Clinic', 'Healthcare', 'Raipur', 'open', 1, 1),
            ('Metro Auto Workshop', 'Automotive', 'Bhilai', 'busy', 3, 2);
        """)
        
        # Add services for Urban Cut Studio (Business ID 1)
        cursor.execute("""
            INSERT INTO services (business_id, name, current_estimated_duration, total_completed_count)
            VALUES 
            (1, 'Standard Haircut', 20.0, 5),
            (1, 'Beard Trim & Lineup', 10.0, 5),
            (1, 'Hair Color & Styling', 45.0, 2);
        """)

        # Add initial queue tickets for Business ID 1
        cursor.execute("""
            INSERT INTO queue_tickets (business_id, service_id, customer_name, is_walkin, status, created_at)
            VALUES 
            (1, 1, 'Rahul Sharma', 0, 'waiting', datetime('now', '-10 minutes')),
            (1, 2, 'Walk-in Guest', 1, 'waiting', datetime('now', '-5 minutes'));
        """)
        conn.commit()
        print("Database schema and seed data created!")
    else:
        print("Database already populated.")

    conn.close()

if __name__ == "__main__":
    initialize_database()