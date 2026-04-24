import sqlite3, uuid, json

db = sqlite3.connect('data/prototype.db')
db.row_factory = sqlite3.Row

course = db.execute("SELECT id FROM courses WHERE language='French' OR name LIKE '%asd%' LIMIT 1").fetchone()
if not course:
    print("French course not found"); exit()

cid = course['id']
chapters = db.execute("""
    SELECT ch.* 
    FROM chapters ch 
    LEFT JOIN topics t ON t.chapter_id = ch.id 
    WHERE ch.course_id = ? 
    GROUP BY ch.id 
    HAVING COUNT(t.id) = 0
""", (cid,)).fetchall()

print(f"Initializing {len(chapters)} empty units...")

for ch in chapters:
    tid = str(uuid.uuid4())
    title = ch['title'].split(':', 1)[-1].strip() if ':' in ch['title'] else ch['title']
    db.execute("INSERT INTO topics VALUES (?,?,?,?,?,?,?)",
               (tid, ch['id'], 'grammar', title, 'A1.1', json.dumps({"rules":[], "examples":[]}), 0))

db.commit()
db.close()
print("Success. Chapters initialized.")
