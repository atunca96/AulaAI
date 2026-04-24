import sqlite3

db = sqlite3.connect('data/prototype.db')
db.row_factory = sqlite3.Row

# 1. Identify the French Course
course = db.execute("SELECT id, name FROM courses WHERE language='French' OR name LIKE '%asd%' LIMIT 1").fetchone()
if not course:
    print("French course not found")
    exit()

cid = course['id']
print(f"Working on course: {course['name']} ({cid})")

# 2. Find duplicate chapter numbers
duplicates = db.execute("""
    SELECT number, COUNT(*) as cnt 
    FROM chapters 
    WHERE course_id = ? 
    GROUP BY number 
    HAVING cnt > 1
""", (cid,)).fetchall()

for dup in duplicates:
    num = dup['number']
    print(f"Cleaning duplicates for Unit {num}...")
    
    # Get all chapters for this number
    chaps = db.execute("""
        SELECT ch.id, COUNT(q.id) as qcount
        FROM chapters ch
        LEFT JOIN topics t ON t.chapter_id = ch.id
        LEFT JOIN questions q ON q.topic_id = t.id
        WHERE ch.course_id = ? AND ch.number = ?
        GROUP BY ch.id
        ORDER BY qcount DESC
    """, (cid, num)).fetchall()
    
    # Keep the one with the most questions, delete others
    best_id = chaps[0]['id']
    for row in chaps[1:]:
        bad_id = row['id']
        print(f"  Removing empty/duplicate chapter {bad_id}")
        db.execute("DELETE FROM questions WHERE topic_id IN (SELECT id FROM topics WHERE chapter_id = ?)", (bad_id,))
        db.execute("DELETE FROM topics WHERE chapter_id = ?", (bad_id,))
        db.execute("DELETE FROM chapters WHERE id = ?", (bad_id,))

db.commit()
print("Cleanup complete.")
