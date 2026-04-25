import sqlite3
import json

db_path = "data/prototype.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get most recent course
course = cursor.execute("SELECT * FROM courses ORDER BY created_at DESC LIMIT 1").fetchone()

if course:
    print(f"Checking Course: {course['name']} ({course['id']})")
    print(json.dumps(dict(course), indent=2))
    
    print("\nTopics in this course:")
    topics = cursor.execute("SELECT id, chapter_id, title, type, content FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id = ?) LIMIT 10", (course['id'],)).fetchall()
    for t in topics:
        content_len = len(t['content']) if t['content'] else 0
        print(f"- {t['title']} ({t['type']}) | Content length: {content_len}")
        if content_len > 10:
            print(f"  Snippet: {t['content'][:100]}...")
else:
    print("No courses found")

conn.close()
