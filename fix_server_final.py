import os

file_path = r"c:\Users\atunc\.gemini\antigravity\scratch\spanish-ai-system\server.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Locate the function and replace it entirely
start_marker = "    def _get_activity(self, topic_id):"
end_marker = "    def _get_quizzes(self, course_id, student_id=None):"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    new_func = """    def _get_activity(self, topic_id):
        if not topic_id: return self._send_error("topic_id required")
        
        with db_connection() as db:
            topic = db.execute(\"\"\"
                SELECT t.*, c.name as course_name, c.language as course_language
                FROM topics t
                JOIN chapters ch ON t.chapter_id = ch.id
                JOIN courses c ON ch.course_id = c.id
                WHERE t.id = ?
            \"\"\", (topic_id,)).fetchone()
        if not topic: return self._send_error("Topic not found", 404)

        topic_dict = dict(topic)
        lang_name = (topic_dict.get('course_language', '') or 'Spanish').title()
        lang_code = 'de' if 'German' in lang_name else ('fr' if 'French' in lang_name else 'es')

        print(f"[Activity] Requesting FRESH AI for {topic_dict['title']}...")
        from services.ai_engine import generate_activity
        activities = generate_activity(topic_dict, count=6)

        if not activities:
            print(f"[Activity] AI failed, falling back to DB pool")
            with db_connection() as db:
                existing = db.execute("SELECT * FROM questions WHERE topic_id=? ORDER BY RANDOM() LIMIT 6", (topic_id,)).fetchall()
            activities = [self._format_question(dict(q), lang_code) for q in existing] if existing else []
        else:
            # Grow pool asynchronously
            import threading
            threading.Thread(target=self._save_new_questions, args=(topic_id, activities)).start()

        return self._send_json({"topic": topic_dict, "activities": activities or []})

    def _format_question(self, qd, lang_code):
        try:
            import json, random
            d = qd.get('distractors', [])
            dist_list = json.loads(d) if isinstance(d, str) else d
            if not isinstance(dist_list, list) or len(dist_list) < 3:
                safety = ["Mutter", "Vater", "Schule", "Wasser"] if lang_code == 'de' else ["Madre", "Padre", "Escuela", "Agua"]
                if lang_code == 'fr': safety = ["Mre", "Pre", "cole", "Eau"]
                extra = [s for s in safety if s != qd.get('answer') and s not in (dist_list or [])]
                random.shuffle(extra)
                dist_list = (list(dist_list or []) + extra)[:3]
            qd['options'] = dist_list + [qd.get('answer', 'Answer')]
            random.shuffle(qd['options'])
        except: qd['options'] = [qd.get('answer', 'Answer'), "Ja", "Nein", "Danke"]
        return qd

    def _save_new_questions(self, topic_id, activities):
        try:
            import json
            with db_connection() as db:
                for a in activities:
                    if a['type'] == 'mcq':
                        ans = a['answer']
                        dist = [o for o in a.get('options', []) if o != ans]
                        db.execute("INSERT INTO questions (topic_id, type, prompt, answer, distractors) VALUES (?,?,?,?,?)",
                                  (topic_id, 'mcq', a['prompt'], ans, json.dumps(dist)))
                    else:
                        db.execute("INSERT INTO questions (topic_id, type, prompt, answer, hint) VALUES (?,?,?,?,?)",
                                  (topic_id, 'fill_blank', a['prompt'], a['answer'], a.get('hint', '')))
                db.commit()
                print(f"[DB] Saved {len(activities)} fresh questions for {topic_id}")
        except Exception as e: print(f"[DB] Error saving: {e}")

"""
    new_content = content[:start_idx] + new_func + content[end_idx:]
    with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    print("Success: Overwrote _get_activity")
else:
    print(f"Error: Markers not found. start={start_idx}, end={end_idx}")
