import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), 'data', 'prototype.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE courses ADD COLUMN seeding_progress INTEGER DEFAULT 0")
        print("Success: Added seeding_progress to courses")
    except Exception as e:
        print(f"Info: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
