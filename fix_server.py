f = open('server.py', 'r', encoding='utf-8')
content = f.read()
f.close()

# In _auto_generate_quiz
content = content.replace(
    'questions = generate_quiz(topic_ids, count=count)', 
    'questions = generate_quiz(topic_ids, count=count, is_quiz=True)'
)

# Wait, the replace above replaces ALL three occurrences!
# Let's fix _draft_generate first. 
# In _draft_generate, we have: `pub_type = body.get("type", "quiz")` earlier.
# But it's inside a background thread where pub_type is captured!
# So we can replace the second occurrence with `is_quiz=(pub_type == 'quiz')`.
# The easiest way is using regex or exact block replacement.

old_draft = '''                questions = generate_quiz(topic_ids, count=count, is_quiz=True)
            finally:
                state.is_done = True'''
new_draft = '''                questions = generate_quiz(topic_ids, count=count, is_quiz=(pub_type == "quiz"))
            finally:
                state.is_done = True'''
content = content.replace(old_draft, new_draft)

# Now fix _auto_generate_assignment
old_assign = '''        from services.content_engine import generate_quiz
        questions = generate_quiz(topic_ids, count=count, is_quiz=True)
        
        with db_connection() as db:
            for i, q in enumerate(questions):
                db.execute("INSERT OR IGNORE INTO assignment_questions VALUES (?,?,?)",
                           (assignment_id, q["id"], i))'''
new_assign = '''        from services.content_engine import generate_quiz
        questions = generate_quiz(topic_ids, count=count, is_quiz=False)
        
        with db_connection() as db:
            for i, q in enumerate(questions):
                db.execute("INSERT OR IGNORE INTO assignment_questions VALUES (?,?,?)",
                           (assignment_id, q["id"], i))'''
content = content.replace(old_assign, new_assign)

f = open('server.py', 'w', encoding='utf-8')
f.write(content)
f.close()
