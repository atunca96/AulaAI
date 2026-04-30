
import os
import random
import threading
import subprocess
import sys
import json
import concurrent.futures
import time
import urllib.request
import traceback
from datetime import datetime
from database import db_connection, _uid
from services.state import bump_version
from services.ai_engine import detect_language, generate_full_lesson, _call_ai

def file_log(msg):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [PIPELINE] {msg}\n")
            f.flush()
        # Also print to stdout for worker.py to capture if needed
        print(f"[{timestamp}] [PIPELINE] {msg}", flush=True)
    except: pass

def _log(msg):
    file_log(msg)

def generate_classroom_code():
    return "".join([str(random.randint(0, 9)) for _ in range(5)])

def start_pipeline_background(pdf_path, toc_range, lecturer_id, course_id, course_name, manual_toc=None, source_markdown_path=None, language=None):
    """
    Background worker that runs Phase 1 and Phase 2.
    """
    start_time = datetime.now()
    toc_text = ""
    # Use provided language or default to Detecting...
    if not language:
        language = "Detecting..."
    
    try:
        _log(f"Phase 1: Starting for {course_id} ({course_name})")
        
        # Initialize language from DB if already set (manual creation)
        with db_connection() as db:
            row = db.execute("SELECT language FROM courses WHERE id = ?", (course_id,)).fetchone()
            if row and row[0] and row[0] != "Detecting...":
                language = row[0]
                _log(f"Using pre-set language: {language}")

        chapters_data = []
        is_pre_parsed = False
        
        # Check if manual_toc is already a structured JSON
        if manual_toc and manual_toc.strip().startswith('{'):
            try:
                data = json.loads(manual_toc)
                if "chapters" in data:
                    _log("Pre-parsed JSON curriculum detected.")
                    chapters_data = data["chapters"]
                    is_pre_parsed = True
            except: pass

        if not is_pre_parsed:
            # 1. Extract TOC Text (if range provided)
            if pdf_path != "NONE" and toc_range:
                _log("Step 1: Extracting TOC text from PDF...")
                try:
                    import fitz # PyMuPDF
                    doc = fitz.open(pdf_path)
                    
                    start_p = 1
                    end_p = 1
                    
                    if "-" in toc_range:
                        sp, ep = toc_range.split("-")
                        start_p = int(sp)
                        end_p = int(ep)
                    elif toc_range.strip().isdigit():
                        start_p = int(toc_range.strip())
                        end_p = start_p

                    for p in range(start_p-1, min(end_p, len(doc))):
                        toc_text += doc[p].get_text()
                    doc.close()
                    _log(f"TOC Extraction complete. Length: {len(toc_text)} chars")
                except Exception as e:
                    _log(f"ERROR in TOC Extraction: {e}")

            # 2. Detect Language
            _log("Step 2: Detecting language...")
            language = "Unknown"
            
            # Get course name for hint
            course_name = "Unknown Course"
            with db_connection() as db:
                row = db.execute("SELECT name FROM courses WHERE id = ?", (course_id,)).fetchone()
                if row: course_name = row[0]

            text_for_lang = manual_toc if manual_toc else toc_text
            if text_for_lang and text_for_lang.strip():
                try:
                    language = detect_language(text_for_lang, hint=course_name)
                except:
                    language = "Unknown"
            _log(f"Language detected: {language}")
            with db_connection() as db:
                db.execute("UPDATE courses SET language = ? WHERE id = ?", (language, course_id))
                db.commit()
            
            bump_version()
            
            # 3. Parse Structure
            _log("Step 3: Analyzing curriculum structure...")
            
            # If we have a source markdown but no manual TOC, use the markdown to find structure
            if not manual_toc and source_markdown_path and os.path.exists(source_markdown_path):
                with open(source_markdown_path, "r", encoding="utf-8") as f:
                    manual_toc = f.read()
                _log("Using Source Markdown for structural analysis.")

            if manual_toc:
                _log(f"RAW MANUAL TOC RECEIVED ({len(manual_toc)} chars)")
                _log("Using Manual Curriculum provided by teacher.")
                prompt = f"""
                Task: Convert this messy curriculum text into a structured JSON Roadmap for a {language} course.
                Input can be: numbered lists, plain text, indented outlines, or comma-separated items.
                
                Rules:
                1. Identify Chapters/Units: Look for overarching grouping headers ('Chapter', 'Unit', 'Module', 'Lektion', 'Tema', 'Unidad', etc.).
                2. CHUNKING FLAT LISTS (CRITICAL): If the curriculum is just a long flat list of lessons/topics with no explicit chapters, YOU MUST group them into logical sequential chapters (e.g., "Unit 1: Foundations", "Unit 2: Daily Life") with roughly 3-5 topics per chapter. NEVER return a single massive chapter with 6+ topics.
                3. Types: Assign a type ('vocabulary', 'grammar', or 'reading') to each topic based on its title.
                4. CRITICAL: Skip meta-sections like 'About', 'Authors', 'License', 'Preface', 'Index', 'Bibliography', 'Introduction' (if just a welcome), 'Appendix', 'GNU', etc. Focus ONLY on lessons and teaching material.
                
                Return ONLY a valid JSON object with this exact structure:
                {{
                  "chapters": [
                    {{
                      "title": "Unit 1: ...",
                      "page": 12,
                      "topics": [
                        {{ "title": "Topic Name", "type": "vocabulary", "page": 13 }}
                      ]
                    }}
                  ]
                }}
                
                Manual Text to Parse:
                {manual_toc}
                """
            else:
                _log("Extracting curriculum from PDF TOC text.")
                prompt = f"Extract the curriculum (Table of Contents) from the following text. Language: {language}.\n\nReturn ONLY JSON with structure:\n{{ \"chapters\": [ {{ \"title\": \"...\", \"page\": 12, \"topics\": [ {{ \"title\": \"...\", \"type\": \"vocabulary/grammar/reading\", \"page\": 13 }} ] }} ] }}\n\nText:\n{toc_text}"
            
            resp = _call_ai([{"role": "user", "content": prompt}], max_tokens=4000)
            
            try:
                if isinstance(resp, dict):
                    chapters_data = resp.get("chapters", [])
                elif isinstance(resp, str) and resp.strip():
                    clean_resp = resp.replace("```json", "").replace("```", "").strip()
                    start_idx = clean_resp.find('{')
                    end_idx = clean_resp.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        clean_resp = clean_resp[start_idx:end_idx+1]
                    data = json.loads(clean_resp)
                    chapters_data = data.get("chapters", [])
            except Exception as e:
                _log(f"AI Parsing failed ({e}). Attempting manual fallback.")
            
        # Fallback Logic
        if not chapters_data and manual_toc:
            _log("Using line-by-line fallback for manual curriculum.")
            topics = []
            for line in manual_toc.split('\n'):
                t = line.strip().strip('-').strip('*').strip()
                if len(t) > 3:
                    # Simple heuristic for grammar
                    grammar_keys = ["verb", "conjugation", "grammar", "rule", "tense", "pronoun", "article", "preposition", "syntax", "order", "structure", "word order"]
                    t_type = "grammar" if any(k in t.lower() for k in grammar_keys) else "vocabulary"
                    topics.append({"title": t, "type": t_type})
            
            if topics:
                # Chunk into groups of 5
                chapters_data = []
                chunk_size = 5
                for i in range(0, len(topics), chunk_size):
                    chunk = topics[i:i + chunk_size]
                    unit_num = (i // chunk_size) + 1
                    chapters_data.append({
                        "title": f"Unit {unit_num}",
                        "topics": chunk
                    })
        
        if not chapters_data:
            _log("ERROR: All parsing attempts failed.")
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
                ch_page = ch.get("page")
                db.execute("INSERT INTO chapters (id, course_id, number, title, page_number) VALUES (?,?,?,?,?)",
                           (chapter_id, course_id, ch_num, ch_title, ch_page))
                for topic_idx, topic in enumerate(ch.get("topics", [])):
                    topic_id = _uid()
                    t_title = topic.get("title", "Untitled Topic")
                    t_type = topic.get("type", "vocabulary")
                    t_page = topic.get("page")
                    db.execute("INSERT INTO topics (id, chapter_id, type, title, difficulty, content, sort_order, page_number) VALUES (?,?,?,?,?,?,?,?)",
                               (topic_id, chapter_id, t_type, t_title, "A1.1", json.dumps({}), topic_idx, t_page))
            db.commit()
        _log("Structure creation complete.")
        bump_version()
        
        # Phase 2: Enrichment
        _log(f"Phase 1 Complete for {course_id}. Starting Phase 2...")
        enrich_classroom_phase2(course_id, pdf_path, source_markdown_path=source_markdown_path)

    except Exception as e:
        _log(f"CRITICAL ERROR in Phase 1: {e}")
        traceback.print_exc()
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
            db.commit()

def enrich_classroom_phase2(course_id, pdf_path, manual_toc_path=None, source_markdown_path=None):
    """
    Standalone entry point for Phase 2 enrichment.
    """
    start_time = datetime.now()
    manual_toc = None
    if manual_toc_path and os.path.exists(manual_toc_path):
        with open(manual_toc_path, "r", encoding="utf-8") as f:
            manual_toc = f.read()

    source_markdown_content = None
    if source_markdown_path and os.path.exists(source_markdown_path):
        try:
            with open(source_markdown_path, "r", encoding="utf-8") as f:
                source_markdown_content = f.read()
            _log(f"Phase 2: Loaded external source markdown ({len(source_markdown_content)} chars)")
        except Exception as e:
            _log(f"Phase 2 ERROR reading source markdown: {e}")

    try:
        # Get language and structure from DB
        with db_connection() as db:
            db.row_factory = lambda cursor, row: row # Standard tuple fallback
            course = db.execute("SELECT language, level FROM courses WHERE id = ?", (course_id,)).fetchone()
            language = course[0] if course else "Unknown"
            level = course[1] if course and len(course) > 1 else "A1"
            
            chapters = db.execute("SELECT id, title, number FROM chapters WHERE course_id = ? ORDER BY number", (course_id,)).fetchall()
            chapters_data = []
            for ch in chapters:
                topics = db.execute("SELECT id, title, type, page_number FROM topics WHERE chapter_id = ? ORDER BY sort_order", (ch[0],)).fetchall()
                chapters_data.append({
                    "id": ch[0],
                    "title": ch[1],
                    "topics": [{"id": t[0], "title": t[1], "type": t[2], "page": t[3]} for t in topics]
                })
        
        if not chapters_data:
            _log(f"WARNING: No chapters/topics found for {course_id}. Retrying...")
            time.sleep(2)
            with db_connection() as db:
                chapters = db.execute("SELECT id, title, number FROM chapters WHERE course_id = ? ORDER BY number", (course_id,)).fetchall()
                for ch in chapters:
                    topics = db.execute("SELECT id, title, type FROM topics WHERE chapter_id = ? ORDER BY sort_order", (ch[0],)).fetchall()
                    chapters_data.append({
                        "id": ch[0],
                        "title": ch[1],
                        "topics": [{"id": t[0], "title": t[1], "type": t[2]} for t in topics]
                    })

        _log(f"Phase 2: Loaded {len(chapters_data)} chapters. Starting enrichment...")
        with db_connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.commit()

        MAX_TOTAL_TOPICS = 250 
        topic_count = 0
        
        def process_topic_task(t_id, t_title, t_type, language, level, course_id, source_text=None):
            """Wrapper to ensure questions are generated FROM the textbook content."""
            from services.ai_engine import generate_full_lesson, ai_generate_questions
            def step_up():
                try:
                    with db_connection() as db:
                        db.execute("UPDATE courses SET progress = progress + 1 WHERE id = ?", (course_id,))
                        db.commit()
                except: pass

            # 1. Generate Textbook Content
            pages = []
            lesson = generate_full_lesson(t_title, t_type, language, 6, level, source_text=source_text)
            pages = lesson.get("pages", [])
            
            step_up() # Halfway point

            content = {"pages": pages}
            
            # 2. Skip initial question generation to save time & costs!
            # Questions will be lazily generated on-the-fly by content_engine.py when users take quizzes.
            questions = []
            
            step_up() # Final point for this task
            return {"content": content, "questions": questions, "t_id": t_id, "t_title": t_title}

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Map each future to its metadata
            future_to_topic = {}
            # Context Surgery Helper: Extract relevant pages from source markdown
            def get_surgical_context(page_num, full_text):
                if not page_num or not full_text: return full_text
                # Simple heuristic: Split by "Page X" or similar markers if present, 
                # or just take a proportional slice based on total pages.
                # Since we often don't have perfect page markers in markdown, 
                # we'll take the Topic's page and a small buffer.
                lines = full_text.split('\n')
                # If we can't find markers, we use the source_text as is but shortened
                if len(full_text) < 10000: return full_text
                
                # Try to find page markers like "Page 12"
                p_marker = f"Page {page_num}"
                idx = full_text.find(p_marker)
                if idx != -1:
                    start = max(0, idx - 1000) # 1000 chars before
                    end = idx + 4000 # 4000 chars after (approx 2 pages)
                    return full_text[start:end]
                
                return full_text[:8000] # Fallback to first 8k chars

            for ch in chapters_data:
                for topic in ch.get("topics", []):
                    if topic_count >= MAX_TOTAL_TOPICS: break
                    
                    # Apply Context Surgery
                    topic_page = topic.get("page")
                    surgical_text = get_surgical_context(topic_page, source_markdown_content)
                    
                    future = executor.submit(process_topic_task, topic.get("id"), topic.get("title"), topic.get("type"), language, level, course_id, source_text=surgical_text)
                    future_to_topic[future] = topic.get("title")
                    topic_count += 1
            
            total_queued = len(future_to_topic)
            total_steps = total_queued * 2
            
            with db_connection() as db:
                db.execute("UPDATE courses SET progress = 1, total_steps = ? WHERE id = ?", (total_steps, course_id))
                db.commit()

            completed_topics = 0
            for future in concurrent.futures.as_completed(future_to_topic):
                t_title = future_to_topic[future]
                try:
                    result = future.result()
                    t_id = result["t_id"]
                    # Batch Optimization: Reduce request count to prevent 'length' truncation
                    request_count = 12 
                    content = result["content"]
                    questions = result["questions"]
                    
                    with db_connection() as db:
                        if t_id:
                            content_json = json.dumps(content, ensure_ascii=False)
                            db.execute("UPDATE topics SET content = ? WHERE id = ?", (content_json, t_id))
                            db.execute("DELETE FROM questions WHERE topic_id = ?", (t_id,))
                            for q in questions:
                                p_val = q.get("prompt", "")
                                p_text = json.dumps(p_val, ensure_ascii=False) if isinstance(p_val, (list, dict)) else str(p_val)
                                a_val = q.get("answer", "")
                                a_text = json.dumps(a_val, ensure_ascii=False) if isinstance(a_val, (list, dict)) else str(a_val)
                                d_list = q.get("distractors", [])
                                if not isinstance(d_list, list): d_list = [d_list] if d_list else []
                                db.execute("INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, is_active) VALUES (?,?,?,?,?,?,?,1)",
                                           (_uid(), t_id, q.get("type", "mcq"), p_text, a_text, json.dumps(d_list, ensure_ascii=False), "A1.1"))
                        db.commit()
                    completed_topics += 1
                    _log(f"Topic {completed_topics}/{total_queued} fully finalized: {t_title}")
                    bump_version()
                except Exception as e:
                    _log(f"ERROR finalizing topic '{t_title}': {e}")

        _log(f"Phase 2 Complete for {course_id}.")
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

def process_pdf_to_classroom(pdf_path, toc_range, lecturer_id, course_name=None, manual_toc=None, source_markdown_path=None, language=None):
    if not course_name or course_name.strip() == "":
        course_name = os.path.basename(pdf_path).replace(".pdf", "").replace("course_", "")
    
    course_id = _uid()
    code = generate_classroom_code()
    textbook_url = "/books/" + os.path.basename(pdf_path)
    
    with db_connection() as db:
        db.execute("INSERT INTO courses (id, name, semester, textbook, language, code, is_building, lecturer_id) VALUES (?,?,?,?,?,?,?,?)",
                   (course_id, course_name, "Fall 2026", textbook_url, language or "Detecting...", code, 1, lecturer_id))
        db.commit()
    
    manual_toc_file = None
    if manual_toc:
        manual_toc_file = pdf_path.replace(".pdf", "_toc.txt")
        with open(manual_toc_file, "w", encoding="utf-8") as f:
            f.write(manual_toc)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    # Spawn worker to handle curriculum creation and enrichment
    _log(f"Spawning worker for Classroom {course_id}")
    log_file = open("pipeline.log", "a", encoding="utf-8")
    try:
        cmd = [sys.executable, "worker.py", pdf_path, toc_range or "0-0", str(lecturer_id), str(course_id), course_name]
        if manual_toc_file:
            cmd.append(manual_toc_file)
        else:
            cmd.append("NONE") # Placeholder for manual_toc_file
            
        if source_markdown_path:
            cmd.append(source_markdown_path)
        else:
            cmd.append("NONE")
            
        if language:
            cmd.append(language)
            
        if sys.platform == "win32":
            process = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT, 
                                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            process = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT, close_fds=True)
            
        log_file.close() # Child keeps its copy
            
        _log(f"Worker spawned successfully with PID {process.pid}")
    except Exception as e:
        _log(f"CRITICAL: Failed to spawn worker: {e}")
    
    return {"success": True, "course_id": course_id, "code": code, "name": course_name}


def process_manual_to_classroom(chapters, language, level, lecturer_id, course_name, existing_course_id=None):
    if existing_course_id:
        course_id = existing_course_id
        # Preserve existing code, but update everything else
        with db_connection() as db:
            course = db.execute("SELECT code FROM courses WHERE id = ?", (course_id,)).fetchone()
            code = course[0] if course else generate_classroom_code()
            db.execute("UPDATE courses SET name = ?, language = ?, level = ?, is_building = 1, semester = ?, textbook = 'AI Generated' WHERE id = ?",
                       (course_name, language, level, f"{level} Level", course_id))
            db.commit()
    else:
        course_id = _uid()
        code = generate_classroom_code()
        with db_connection() as db:
            db.execute("INSERT INTO courses (id, name, semester, textbook, language, code, is_building, lecturer_id, level) VALUES (?,?,?,?,?,?,?,?,?)",
                       (course_id, course_name, f"{level} Level", "AI Generated", language, code, 1, lecturer_id, level))
            db.commit()

    # Process the nested chapters into the worker's expected format
    worker_chapters = []
    for i, chap in enumerate(chapters):
        topics_processed = []
        for j, t in enumerate(chap.get("topics", [])):
            if isinstance(t, dict):
                topics_processed.append({"title": t.get("title", "Untitled Topic"), "type": t.get("type", "vocabulary")})
            else:
                topics_processed.append({"title": str(t), "type": "vocabulary" if j % 2 == 0 else "grammar"})
                
        worker_chapters.append({
            "number": i + 1,
            "title": chap["title"],
            "topics": topics_processed
        })
    
    manual_toc_data = {"chapters": worker_chapters}
        
    # Write the manual TOC to a file for the worker
    # We use data/books directory for consistency with persistence
    from database import BOOKS_DIR
    os.makedirs(BOOKS_DIR, exist_ok=True)
    manual_toc_file = os.path.join(BOOKS_DIR, f"toc_{course_id}.json")
    with open(manual_toc_file, "w", encoding="utf-8") as f:
        json.dump(manual_toc_data, f)
        
    # Spawn worker to handle curriculum creation and enrichment
    _log(f"Spawning AI Architect worker: Course {course_id}")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [sys.executable, "worker.py", "NONE", "0-0", str(lecturer_id), str(course_id), course_name, manual_toc_file]
    
    log_file = open("pipeline.log", "a", encoding="utf-8")
    try:
        if sys.platform == "win32":
            process = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT, 
                                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            process = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT, close_fds=True)
        
        log_file.close() # Child keeps its copy
        _log(f"Worker process started with PID {process.pid}")
    except Exception as e:
        _log(f"CRITICAL: Failed to spawn AI Architect worker: {e}")
    
    return {"success": True, "course_id": course_id, "code": code, "name": course_name}
