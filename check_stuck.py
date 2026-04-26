from database import db_connection

with db_connection() as db:
    courses = db.execute("SELECT id, name, is_building FROM courses").fetchall()
    for c in courses:
        print(f"ID: {c['id']}, Name: {c['name']}, Building: {c['is_building']}")
        topics = db.execute("SELECT COUNT(*) FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id=?)", (c['id'],)).fetchone()
        print(f"  Topics: {topics[0]}")
