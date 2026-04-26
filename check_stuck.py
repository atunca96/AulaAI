import sqlite3
import os
import json

DB_PATH = os.path.normpath(os.path.join(os.getcwd(), "data", "prototype.db"))

def check():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT id, name, activity_status, activity_progress, activity_total FROM courses").fetchall()
        for r in rows:
            print(dict(r))
    finally:
        conn.close()

if __name__ == "__main__":
    check()
