"""Initialize or migrate the CityPulse SQLite database.

The application uses the same schema initialization at startup, so this script
can safely be run repeatedly.
"""
from app import ensure_schema

if __name__ == "__main__":
    ensure_schema()
    print("CityPulse database schema is ready.")
