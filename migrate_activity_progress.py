import sqlite3
import os

DB_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "data", "prototype.db"))

def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    cols = [
        ("activity_progress", "INTEGER DEFAULT 0"),
        ("activity_total", "INTEGER DEFAULT 0"),
        ("activity_status", "TEXT DEFAULT 'idle'"),
        ("activity_result", "TEXT")
    ]
    
    for col, spec in cols:
        try:
            c.execute(f"ALTER TABLE courses ADD COLUMN {col} {spec}")
            print(f"Added column {col}")
        except sqlite3.OperationalError:
            print(f"Column {col} already exists")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
