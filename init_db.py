"""Initialize the configured CityPulse database (SQLite locally or PostgreSQL when DATABASE_URL is set)."""
from app import ensure_schema

if __name__ == "__main__":
    ensure_schema()
    print("CityPulse database schema is ready.")
