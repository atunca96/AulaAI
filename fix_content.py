import re

with open('services/content_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add is_quiz=False to the signature
content = content.replace(
    'def generate_quiz(topic_ids, student_mastery=None, count=10, progress_callback=None):',
    'def generate_quiz(topic_ids, student_mastery=None, count=10, progress_callback=None, is_quiz=False):'
)

# 2. Skip pulling DB questions if is_quiz is True
# We find the block:
old_db_block = '''        # Pull existing approved questions to fill part of the quota
        for tid in topic_ids:
            rows = c.execute(
                "SELECT * FROM questions WHERE topic_id = ? AND approved = 1 AND type = 'mcq' ORDER BY RANDOM()",
                (tid,)
            ).fetchall()
            for r in rows:
                if len(questions) >= count: break
                try:
                    q = dict(r)
                    q["distractors"] = json.loads(q["distractors"]) if isinstance(q["distractors"], str) else q["distractors"]
                    q["options"] = [q["answer"]] + q["distractors"]
                    import random as _r; _r.shuffle(q["options"])
                    questions.append(q)
                except:
                    pass
            if len(questions) >= count: break'''

new_db_block = '''        # Pull existing approved questions to fill part of the quota
        # IF it's a quiz, we SKIP the database pool because we need fresh target-language questions, 
        # and existing questions might be in English (for A1/A2 Practice).
        if not is_quiz:
            for tid in topic_ids:
                rows = c.execute(
                    "SELECT * FROM questions WHERE topic_id = ? AND approved = 1 AND type = 'mcq' ORDER BY RANDOM()",
                    (tid,)
                ).fetchall()
                for r in rows:
                    if len(questions) >= count: break
                    try:
                        q = dict(r)
                        q["distractors"] = json.loads(q["distractors"]) if isinstance(q["distractors"], str) else q["distractors"]
                        q["options"] = [q["answer"]] + q["distractors"]
                        import random as _r; _r.shuffle(q["options"])
                        questions.append(q)
                    except:
                        pass
                if len(questions) >= count: break'''

content = content.replace(old_db_block, new_db_block)

# 3. Pass is_quiz to ai_generate_questions
old_ai_call = '''        extra_qs = ai_generate_questions(
            topic_title="Quiz/Review",
            topic_type="mixed_curriculum",
            topic_content={"topics": topics_summary},
            language=base_lang,
            count=still_needed,
            existing_questions=questions  # forbidden list grows each pass
        )'''

new_ai_call = '''        extra_qs = ai_generate_questions(
            topic_title="Quiz/Review",
            topic_type="mixed_curriculum",
            topic_content={"topics": topics_summary},
            language=base_lang,
            count=still_needed,
            existing_questions=questions,  # forbidden list grows each pass
            is_quiz=is_quiz
        )'''

content = content.replace(old_ai_call, new_ai_call)

with open('services/content_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
