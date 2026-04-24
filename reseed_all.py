import sqlite3, json, uuid, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.ai_engine import ai_generate_questions, is_ai_available

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'prototype.db')

def safe(s, length=45):
    return s[:length].encode('ascii', 'replace').decode('ascii')

def uid(): return str(uuid.uuid4())

def reseed(language='French', pdf_text=None):
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")

    course = db.execute("SELECT * FROM courses WHERE (language=? OR name LIKE ?) ORDER BY created_at DESC LIMIT 1", (language, f"%{language}%")).fetchone()
    if not course:
        print("No course found for language:", language); return

    print(f"Course: '{course['name']}' lang={course['language']}")

    topics = db.execute("""
        SELECT t.id, t.title, t.type, t.content
        FROM topics t JOIN chapters ch ON t.chapter_id=ch.id
        WHERE ch.course_id=?
    """, (course['id'],)).fetchall()

    print(f"Topics: {len(topics)}  AI OK: {is_ai_available()}\n")

    total_topics = len(topics)
    total = 0
    for i, topic in enumerate(topics):
        # UPDATE PROGRESS
        progress = int(((i) / total_topics) * 100)
        db.execute("UPDATE courses SET seeding_progress=? WHERE id=?", (progress, course['id']))
        db.commit()

        existing = db.execute("SELECT COUNT(*) FROM questions WHERE topic_id=?", (topic['id'],)).fetchone()[0]
        if existing >= 20:
            print(f"  [{i+1}/{len(topics)}] SKIP '{safe(topic['title'])}' ({existing} q)")
            continue

        # FIND RELEVANT CONTEXT IN PDF
        context_snippet = ""
        if pdf_text:
            # Fuzzy search: try original title, then simpler chunks
            search_title = topic['title'].split('•')[-1].strip() if '•' in topic['title'] else topic['title']
            search_title = search_title.split('(')[0].strip() # Remove (0-20) etc
            
            pos = pdf_text.lower().find(search_title.lower())
            if pos == -1:
                # Try even simpler: first two words
                words = search_title.split()
                if len(words) > 1:
                    simple = f"{words[0]} {words[1]}"
                    pos = pdf_text.lower().find(simple.lower())
            
            if pos != -1:
                # Take a large chunk around the title (5000 chars) for context
                context_snippet = pdf_text[max(0, pos-500):pos+8000]
                print(f" [Context found for {safe(search_title)}]", end='')

        # Fallback if content is empty
        content = json.loads(topic['content']) if isinstance(topic['content'], str) else {}
        if not content or not content.get('words'):
            # Use the PDF snippet as the primary source of truth!
            content_for_ai = {"rules": [f"Source Text: {context_snippet}"], "examples": []}
            eff_type = 'vocabulary' # Treat as vocab to extract words from text
        else:
            content_for_ai = content
            eff_type = topic['type'] or 'vocabulary'

        print(f"  [{i+1}/{len(topics)}] '{safe(topic['title'])}'...", end='', flush=True)

        questions = None
        if is_ai_available():
            for attempt in range(3):
                try:
                    questions = ai_generate_questions(
                        topic_title=topic['title'], topic_type=eff_type,
                        topic_content=content_for_ai, count=20, language=language)
                    if questions: break
                except Exception as e:
                    print(f" (retry {attempt+1})", end='', flush=True)
                    time.sleep(2)
        else:
            # SMART MOCK GENERATOR (Offline Fallback)
            # Try to extract more from the PDF text or content
            print(f" (mocking)", end='', flush=True)
            mock_questions = []
            
            # If it's vocabulary, try to find more words in context_snippet
            if eff_type == 'vocabulary' and context_snippet:
                import re
                # Simple regex to find "Spanish - English" patterns
                found = re.findall(r'([A-Z][a-zñáéíóúü]+) [-–—] ([A-Z][a-z ]+)', context_snippet)
                if not found:
                    # Try common word lists if no pattern found
                    words_in_topic = content_for_ai.get('words', {})
                    found = list(words_in_topic.items())
                
                for s, e in found[:15]:
                    mock_questions.append({
                        "type": "mcq", "prompt": f"What does '{s}' mean?", 
                        "answer": e, "distractors": ["wrong1", "wrong2", "wrong3"]
                    })
            
            # If it's grammar, try to find sentences with common markers
            elif eff_type == 'grammar' and context_snippet:
                import re
                # Split by sentence markers
                sentences = re.split(r'[.!?]\s+', context_snippet)
                sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
                
                # Look for common verb/grammar patterns to blank out
                markers = [' es ', ' está ', ' hay ', ' tiene ', ' son ', ' están ', ' tienen ', ' soy ', ' estoy ']
                for s in sentences:
                    best_marker = None
                    for m in markers:
                        if m in s.lower():
                            best_marker = m
                            break
                    
                    if best_marker:
                        # Create a blank around the marker
                        prompt = s.replace(best_marker, " ___ ")
                        mock_questions.append({
                            "type": "fill_blank", "prompt": prompt, "answer": best_marker.strip()
                        })
                    
                    if len(mock_questions) >= 20: break

            # Final fallback to existing seed logic if still empty
            if len(mock_questions) < 10:
                from database import _generate_seed_questions
                topic_data = {"type": eff_type, "title": topic['title'], "content": content_for_ai, "language_name": language}
                extra_mocks = _generate_seed_questions(topic_data)
                mock_questions.extend(extra_mocks)
                
            questions = mock_questions

        if questions:
            for q in questions:
                # Distractor cleanup
                distractors = q.get('distractors') or []
                if isinstance(distractors, str): distractors = [distractors]
                
                db.execute("INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,1,datetime('now'))",
                    (uid(), topic['id'], q.get('type','mcq'), q.get('prompt',''), q.get('answer',''),
                     json.dumps(distractors), 'A1.1', None, None))
            db.commit()
            total += len(questions)
            print(f" OK {len(questions)}q")
        else:
            print(f" FAILED")

        time.sleep(0.1) 

    db.execute("UPDATE courses SET seeding_progress=100 WHERE id=?", (course['id'],))
    db.commit()
    print(f"\n[DONE] Seeded {total} questions total.")
    db.close()

def reseed_single_topic(topic, pdf_text=None):
    """Reseed a specific topic (used by the 'Regenerate' button)."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    
    # Check if we should delete existing ones first to ensure variety
    # For manual reseed, we always add more
    
    language = topic.get('language', 'Spanish')
    eff_type = topic['type']
    
    try:
        content_for_ai = json.loads(topic['content'])
    except:
        content_for_ai = {}

    context_snippet = ""
    if pdf_text:
        search_title = topic['title'].split('•')[-1].strip() if '•' in topic['title'] else topic['title']
        search_title = search_title.split('(')[0].strip()
        pos = pdf_text.lower().find(search_title.lower())
        if pos != -1:
            context_snippet = pdf_text[max(0, pos-500):pos+8000]

    questions = None
    if is_ai_available():
        try:
            questions = ai_generate_questions(
                topic_title=topic['title'], topic_type=eff_type,
                topic_content=content_for_ai, count=20, language=language)
        except: pass
    
    if not questions:
        # Fallback to smart mocking
        mock_questions = []
        if eff_type == 'vocabulary' and context_snippet:
            import re
            found = re.findall(r'([A-Z][a-zñáéíóúü]+) [-–—] ([A-Z][a-z ]+)', context_snippet)
            if not found:
                words_in_topic = content_for_ai.get('words', {})
                found = list(words_in_topic.items())
            for s, e in found[:15]:
                mock_questions.append({
                    "type": "mcq", "prompt": f"What does '{s}' mean?", 
                    "answer": e, "distractors": ["wrong1", "wrong2", "wrong3"]
                })
        elif eff_type == 'grammar' and context_snippet:
            import re
            sentences = re.split(r'[.!?]\s+', context_snippet)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 15]
            markers = [' es ', ' está ', ' hay ', ' tiene ', ' son ', ' están ', ' tienen ', ' soy ', ' estoy ']
            for s in sentences:
                best_marker = None
                for m in markers:
                    if m in s.lower():
                        best_marker = m
                        break
                if best_marker:
                    mock_questions.append({
                        "type": "fill_blank", "prompt": s.replace(best_marker, " ___ "), "answer": best_marker.strip()
                    })
                if len(mock_questions) >= 20: break
        
        if len(mock_questions) < 10:
            from database import _generate_seed_questions
            topic_data = {"type": eff_type, "title": topic['title'], "content": content_for_ai, "language_name": language}
            mock_questions.extend(_generate_seed_questions(topic_data))
        
        questions = mock_questions

    if questions:
        for q in questions:
            distractors = q.get('distractors') or []
            if isinstance(distractors, str): distractors = [distractors]
            db.execute("INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,1,datetime('now'))",
                (uid(), topic['id'], q.get('type','mcq'), q.get('prompt',''), q.get('answer',''),
                 json.dumps(distractors), 'A1.1', None, None))
        db.commit()
    db.close()

if __name__ == '__main__':
    reseed(language='French')
