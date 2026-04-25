import sqlite3
import json

db_path = "data/prototype.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Recent Classrooms (Last 10 mins):")
rows = cursor.execute("SELECT id, name, language, is_building, created_at FROM courses ORDER BY created_at DESC LIMIT 10").fetchall()
for row in rows:
    print(f"ID: {row['id']} | Name: {row['name']} | Lang: {row['language']} | Build: {row['is_building']} | Created: {row['created_at']}")

conn.close()
