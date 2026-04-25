import sqlite3
import json

db = sqlite3.connect('data/prototype.db')
db.row_factory = sqlite3.Row
c = db.cursor()

# Get the most recent quiz
quiz = c.execute("SELECT * FROM quizzes ORDER BY created_at DESC LIMIT 1").fetchone()
if quiz:
    print(f"Quiz: {quiz['title']} ({quiz['id']})")
    questions = c.execute("""
        SELECT q.* FROM questions q
        JOIN quiz_questions qq ON q.id = qq.question_id
        WHERE qq.quiz_id = ?
        ORDER BY qq.sort_order
    """, (quiz['id'],)).fetchall()
    
    for q in questions:
        print(f"--- Question: {q['prompt']} ---")
        print(f"Type: {q['type']}")
        print(f"Answer: {q['answer']}")
        print(f"Distractors: {q['distractors']}")
else:
    print("No quizzes found")
