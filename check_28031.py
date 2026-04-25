import sqlite3
import json

db_path = "data/prototype.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get course by code 28031
course = cursor.execute("SELECT * FROM courses WHERE code = '28031'").fetchone()

if course:
    print(f"Checking Course: {course['name']} ({course['id']})")
    print(json.dumps(dict(course), indent=2))
else:
    print("Course 28031 not found")

conn.close()
