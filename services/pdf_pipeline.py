
import os
import random
import threading
import subprocess
import sys
import json
import concurrent.futures
import time
import urllib.request
from datetime import datetime
from database import db_connection, _uid
from services.state import bump_version
from services.ai_engine import detect_language, generate_full_lesson, _call_ai

def _log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [PIPELINE] {msg}", flush=True)

def generate_classroom_code():
    return "".join([str(random.randint(0, 9)) for _ in range(5)])

def start_pipeline_background(pdf_path, toc_range, lecturer_id, course_id, course_name, manual_toc=None):
    """
    Background worker that runs Phase 1 and Phase 2.
    """
    start_time = datetime.now()
    toc_text = ""
    language = "Unknown"
    
    try:
        _log(f"Phase 1: Starting for {course_id} ({course_name})")
        
        # 1. Extract TOC Text (if range provided)
        if toc_range and "-" in toc_range:
            _log("Step 1: Extracting TOC text from PDF...")
            try:
                import fitz # PyMuPDF
                doc = fitz.open(pdf_path)
                start_p, end_p = map(int, toc_range.split("-"))
                for p in range(start_p-1, min(end_p, len(doc))):
                    toc_text += doc[p].get_text()
                doc.close()
                _log(f"TOC Extraction complete. Length: {len(toc_text)} chars")
            except Exception as e:
                _log(f"ERROR in TOC Extraction: {e}")

        # 2. Detect Language
        _log("Step 2: Detecting language...")
        language = "Unknown"
        text_for_lang = manual_toc if manual_toc else toc_text
        if text_for_lang and text_for_lang.strip():
            try:
                language = detect_language(text_for_lang)
            except:
                language = "Unknown"
        _log(f"Language detected: {language}")
        
        # 3. Parse Structure
        _log("Step 3: Parsing curriculum structure...")
        if manual_toc:
            _log(f"RAW MANUAL TOC RECEIVED ({len(manual_toc)} chars):\n{manual_toc}")
            _log("Using Manual Curriculum provided by teacher.")
            prompt = f"""
            Task: Convert this messy curriculum text into a structured JSON Roadmap for a {language} course.
            Input can be: numbered lists, plain text, indented outlines, or comma-separated items.
            
            Rules:
            1. Identify Chapters/Units: Look for lines starting with 'Chapter', 'Unit', 'Tema', 'Section', or Roman Numerals.
            2. Identify Topics: Everything under a Chapter is a topic. If no chapters are found, treat the whole list as topics under one 'General Curriculum' chapter.
            3. Types: Assign a type ('vocabulary', 'grammar', or 'reading') to each topic based on its title.
            
            Return ONLY a valid JSON object with this exact structure:
            {{
              "chapters": [
                {{
                  "title": "Chapter 1: ...",
                  "topics": [
                    {{ "title": "Topic Name", "type": "vocabulary" }}
                  ]
                }}
              ]
            }}
            
            Manual Text to Parse:
            {manual_toc}
            """
        else:
            _log("Extracting curriculum from PDF TOC text.")
            prompt = f"Extract the curriculum (Table of Contents) from the following text. Language: {language}.\n\nReturn ONLY JSON with structure:\n{{ \"chapters\": [ {{ \"title\": \"...\", \"topics\": [ {{ \"title\": \"...\", \"type\": \"vocabulary/grammar/reading\" }} ] }} ] }}\n\nText:\n{toc_text}"
        
        resp = _call_ai([{"role": "user", "content": prompt}], max_tokens=4000)
        _log(f"RAW AI RESPONSE:\n{resp}")
        
        chapters_data = []
        try:
            if isinstance(resp, dict):
                _log("AI returned pre-parsed dictionary.")
                chapters_data = resp.get("chapters", [])
            elif isinstance(resp, str) and resp.strip():
                # Simple cleanup for AI markdown
                clean_resp = resp.replace("```json", "").replace("```", "").strip()
                # Find first { and last } to handle extra text
                start_idx = clean_resp.find('{')
                end_idx = clean_resp.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    clean_resp = clean_resp[start_idx:end_idx+1]
                
                data = json.loads(clean_resp)
                chapters_data = data.get("chapters", [])
        except Exception as e:
            _log(f"AI Parsing failed ({e}). Attempting manual fallback.")
            
        # Fallback Logic: If still empty, split manual_toc by newlines
        if not chapters_data and manual_toc:
            _log("Using line-by-line fallback for manual curriculum.")
            topics = []
            for line in manual_toc.split('\n'):
                t = line.strip().strip('-').strip('*').strip()
                if len(t) > 3:
                    topics.append({"title": t, "type": "vocabulary"})
            
            if topics:
                chapters_data = [{
                    "title": "Imported Curriculum",
                    "topics": topics
                }]
        
        if not chapters_data:
            _log("ERROR: All parsing attempts failed (including fallback).")
            with db_connection() as db:
                db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
                db.commit()
            return
            
        _log(f"Structure parsed. Found {len(chapters_data)} chapters.")

        # 4. Create structure in DB
        _log("Step 4: Creating classroom structure in DB...")
        with db_connection() as db:
            db.execute("UPDATE courses SET language = ? WHERE id = ?", (language, course_id))
            
            for idx, ch in enumerate(chapters_data):
                chapter_id = _uid()
                ch_num = idx + 1
                ch_title = str(ch.get("title", "Untitled Chapter"))
                ch["id"] = chapter_id
                _log(f"Inserting Chapter {ch_num}: {ch_title}")
                
                db.execute("INSERT INTO chapters (id, course_id, number, title) VALUES (?,?,?,?)",
                           (chapter_id, course_id, ch_num, ch_title))
                
                for topic_idx, topic in enumerate(ch.get("topics", [])):
                    topic_id = _uid()
                    topic["id"] = topic_id
                    t_title = topic.get("title", "Untitled Topic")
                    t_type = topic.get("type", "vocabulary")
                    db.execute("INSERT INTO topics (id, chapter_id, type, title, difficulty, content, sort_order) VALUES (?,?,?,?,?,?,?)",
                               (topic_id, chapter_id, t_type, t_title, "A1.1", json.dumps({}), topic_idx))
            db.commit()
        _log("Structure creation complete.")
        
        # Phase 2: Enrichment is now handled by worker.py calling enrich_classroom_phase2
        _log(f"Phase 1 Complete for {course_id}. Worker will now take over for Phase 2.")

    except Exception as e:
        _log(f"CRITICAL ERROR in Phase 1: {e}")
        traceback.print_exc()
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
            db.commit()

def enrich_classroom_phase2(course_id, pdf_path, manual_toc_path=None):
    """
    Standalone entry point for Phase 2 enrichment.
    Called by worker.py.
    """
    import traceback
    start_time = datetime.now()
    manual_toc = None
    if manual_toc_path and os.path.exists(manual_toc_path):
        with open(manual_toc_path, "r", encoding="utf-8") as f:
            manual_toc = f.read()

    try:
        # Get language and structure from DB
        with db_connection() as db:
            course = db.execute("SELECT language FROM courses WHERE id = ?", (course_id,)).fetchone()
            language = course["language"] if course else "Unknown"
            
            chapters = db.execute("SELECT id, title, number FROM chapters WHERE course_id = ? ORDER BY number", (course_id,)).fetchall()
            chapters_data = []
            for ch in chapters:
                topics = db.execute("SELECT id, title, type FROM topics WHERE chapter_id = ? ORDER BY sort_order", (ch["id"],)).fetchall()
                chapters_data.append({
                    "id": ch["id"],
                    "title": ch["title"],
                    "topics": [dict(t) for t in topics]
                })

        _log(f"Phase 2: Starting content enrichment for {course_id} ({language})...")
        with db_connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.commit()

        MAX_TOTAL_TOPICS = 250 
        topic_count = 0
        
        print(f"[PIPELINE] Starting Phase 2 Enrichment with 10 workers for {len(chapters_data)} chapters...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for ch in chapters_data:
                chapter_id = ch.get("id")
                topics = ch.get("topics", [])
                for topic in topics:
                    if topic_count >= MAX_TOTAL_TOPICS: break
                    t_title = topic.get("title", "Untitled Topic")
                    t_type = topic.get("type", "vocabulary")
                    t_id = topic.get("id")
                    
                    _log(f"Queueing topic: {t_title}")
                    f_lesson = executor.submit(generate_full_lesson, t_title, t_type, language, 8)
                    futures.append((t_id, t_title, f_lesson))
                    topic_count += 1
            
            completed = 0
            for t_id, t_title, f_lesson in futures:
                _log(f"Finalizing topic: {t_title}...")
                try:
                    lesson = f_lesson.result() or {}
                    content = lesson.get("content", {})
                    questions = lesson.get("questions", [])
                    
                    with db_connection() as db:
                        if t_id:
                            db.execute("UPDATE topics SET content = ? WHERE id = ?", (json.dumps(content, ensure_ascii=False), t_id))
                            for q in questions:
                                p_val = q.get("prompt", "")
                                p_text = json.dumps(p_val, ensure_ascii=False) if isinstance(p_val, (list, dict)) else str(p_val)
                                a_val = q.get("answer", "")
                                a_text = json.dumps(a_val, ensure_ascii=False) if isinstance(a_val, (list, dict)) else str(a_val)
                                d_list = q.get("distractors", [])
                                if not isinstance(d_list, list): d_list = [d_list] if d_list else []
                                
                                db.execute("INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) VALUES (?,?,?,?,?,?,?,1)",
                                           (_uid(), t_id, q.get("type", "mcq"), p_text, a_text, json.dumps(d_list, ensure_ascii=False), "A1.1"))
                        db.commit()
                    completed += 1
                    print(f"[PIPELINE] Topic {completed}/{len(futures)} finalized: {t_title}")
                    sys.stdout.flush()
                except Exception as e:
                    _log(f"ERROR finalizing topic '{t_title}': {e}")

        _log(f"Phase 2 Complete. Duration: {(datetime.now() - start_time).total_seconds():.1f}s")
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
            db.commit()
        bump_version()

    except Exception as e:
        _log(f"FATAL ERROR in Phase 2: {e}")
        traceback.print_exc()
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
            db.commit()
        
    except Exception as e:
        _log(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        try:
            with db_connection() as db:
                db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
                db.commit()
        except: pass

def process_pdf_to_classroom(pdf_path, toc_range, lecturer_id, course_name=None, manual_toc=None):
    """Initializes the classroom and spawns the background worker process."""
    if not course_name or course_name.strip() == "":
        course_name = os.path.basename(pdf_path).replace(".pdf", "").replace("course_", "")
    
    course_id = _uid()
    code = generate_classroom_code()
    textbook_url = "/" + pdf_path.split("public" + os.sep)[-1].replace(os.sep, "/")
    
    with db_connection() as db:
        db.execute("INSERT INTO courses (id, name, semester, textbook, language, code, is_building, lecturer_id) VALUES (?,?,?,?,?,?,?,?)",
                   (course_id, course_name, "Fall 2026", textbook_url, "Detecting...", code, 1, lecturer_id))
        db.commit()
    
    # Save manual_toc to file if it exists to pass to worker
    manual_toc_file = None
    if manual_toc:
        manual_toc_file = pdf_path.replace(".pdf", "_toc.txt")
        with open(manual_toc_file, "w", encoding="utf-8") as f:
            f.write(manual_toc)

    # Spawn worker.py
    python_exe = sys.executable
    cmd = [python_exe, "worker.py", pdf_path, toc_range or "0-0", lecturer_id, course_id, course_name]
    if manual_toc_file:
        cmd.append(manual_toc_file)
        
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    _log(f"Spawning worker: {' '.join(cmd)}")
    subprocess.Popen(cmd, env=env, close_fds=True)
    
    return {"success": True, "course_id": course_id, "code": code, "name": course_name}
