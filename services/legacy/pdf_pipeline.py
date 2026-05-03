# LEGACY - DO NOT USE
# TO BE REMOVED AFTER VALIDATION
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
                    
                    # OCR FALLBACK: If text extraction yielded nothing useful, try vision OCR
                    from services.legacy.ocr_fallback import is_image_based_page, ocr_pdf_pages
                    if is_image_based_page(toc_text):
                        _log("TOC text is empty/garbage — activating OCR fallback...")
                        ocr_toc = ocr_pdf_pages(pdf_path, start_page=start_p, end_page=end_p)
                        if ocr_toc and len(ocr_toc.strip()) > len(toc_text.strip()):
                            toc_text = ocr_toc
                            _log(f"OCR TOC extraction successful: {len(toc_text)} chars")
                        else:
                            _log("OCR fallback did not improve TOC extraction.")
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
                parse_source = manual_toc
            else:
                _log("Extracting curriculum from PDF TOC text.")
                parse_source = toc_text

            # PRIMARY: Fast deterministic parser (milliseconds)
            import time as _t
            _parse_start = _t.time()
            from services.legacy.fast_parser import fast_parse_curriculum
            chapters_data = fast_parse_curriculum(parse_source)
            _parse_ms = (_t.time() - _parse_start) * 1000
            _log(f"Fast parser completed in {_parse_ms:.0f}ms → {len(chapters_data)} chapters")

            # FALLBACK: AI parsing only if fast parser produced nothing
            if not chapters_data:
                _log("Fast parser returned 0 chapters — falling back to AI parsing...")
                prompt_lang = language if language and language != "Detecting..." else "the target"
                prompt = f"""
                Task: Convert this messy curriculum text into a structured JSON Roadmap for a {prompt_lang} course.
                Input can be: numbered lists, plain text, indented outlines, or comma-separated items.
                
                Rules:
                1. Identify Chapters/Units: Look for overarching grouping headers ('Chapter', 'Unit', 'Module', 'Lektion', 'Tema', 'Unidad', etc.).
                2. CHUNKING FLAT LISTS (CRITICAL): If the curriculum is just a long flat list of lessons/topics with no explicit chapters, YOU MUST group them into logical sequential chapters.
                3. Types: Assign a type ('vocabulary', 'grammar', or 'reading') to each topic based on its title.
                4. CRITICAL: Skip meta-sections like 'About', 'Authors', 'License', 'Preface', 'Index', 'Bibliography', 'Appendix', etc.
                5. ORDER: You MUST list chapters and topics in the exact sequential order they appear in the text (strictly ascending page numbers).
                6. LANGUAGE: If the language is unknown, focus on extracting the literal titles without translating them.
                
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
                {parse_source}
                """
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
                    _log(f"AI Parsing also failed ({e}).")
        
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
                    db.execute("INSERT INTO topics (id, chapter_id, type, title, difficulty, content, sort_order, page_number, pdf_url) VALUES (?,?,?,?,?,?,?,?,?)",
                               (topic_id, chapter_id, t_type, t_title, "A1.1", json.dumps({}), topic_idx, t_page, "/books/" + os.path.basename(pdf_path)))
            db.commit()
        _log("Structure creation complete.")
        bump_version()
        
        # Phase 2: Enrichment
        _log(f"Phase 1 Complete for {course_id}. Starting Phase 2...")
        
        # SURGICAL OCR: If no source markdown exists and the PDF is scanned,
        # generate source markdown via OCR for ONLY the pages mentioned in the topics
        if not source_markdown_path and pdf_path and pdf_path != "NONE":
            try:
                from services.legacy.ocr_fallback import is_image_based_pdf, ocr_pdf_pages
                if is_image_based_pdf(pdf_path):
                    _log("Image-based PDF detected — generating surgical OCR source markdown...")
                    
                    # 1. Collect all unique pages mentioned in topics
                    all_pages = set()
                    for ch in chapters_data:
                        for t in ch.get("topics", []):
                            p = t.get("page")
                            if p:
                                all_pages.add(p)
                                # Always take +1 page for context spillover
                                all_pages.add(p + 1)
                    
                    if all_pages:
                        page_list = sorted(list(all_pages))
                        _log(f"Phase 2: Target surgical OCR for {len(page_list)} unique pages")
                        
                        from database import BOOKS_DIR
                        ocr_md_path = os.path.join(BOOKS_DIR, f"ocr_{course_id}.md")
                        ocr_text = ocr_pdf_pages(pdf_path, page_list=page_list)
                        
                        if ocr_text and len(ocr_text) > 100:
                            with open(ocr_md_path, "w", encoding="utf-8") as f:
                                f.write(ocr_text)
                            source_markdown_path = ocr_md_path
                            _log(f"Surgical OCR source markdown saved: {len(ocr_text)} chars -> {ocr_md_path}")
                        else:
                            _log("Surgical OCR produced insufficient text.")
                    else:
                        _log("No page numbers found in topics, cannot perform surgical OCR.")
            except Exception as e:
                _log(f"OCR fallback error (non-fatal): {e}")
        
        enrich_classroom_phase2(course_id, pdf_path, source_markdown_path=source_markdown_path)
        
        # ── FINAL STEP: Release UI Lock ──
        # Only set is_building = 0 when EVERYTHING is finished (Lessons + Starter Questions)
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
            db.commit()
        _log(f"CRITICAL: Classroom {course_id} is now FULLY enriched and ready.")
        bump_version()

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
    page_chunks = {} # dictionary of page_num -> text
    if source_markdown_path and os.path.exists(source_markdown_path):
        try:
            with open(source_markdown_path, "r", encoding="utf-8") as f:
                source_markdown_content = f.read()
            _log(f"Phase 2: Loaded external source markdown ({len(source_markdown_content)} chars)")
            
            # Build Page Chunks for faster/better surgical context
            import re
            # Catch both physical [Page X] and semantic # Source Page X markers
            parts = re.split(r'(?:\[Page\s*(\d+)\]|#\s*Source Page\s*(\d+))', source_markdown_content)
            # re.split with 2 capturing groups will return [intro, p1, p2, text, p1, p2, text, ...]
            # If [Page X] matches, p1 is X and p2 is None. If # Source Page X matches, p1 is None and p2 is X.
            for i in range(1, len(parts), 3):
                try:
                    p1 = parts[i]
                    p2 = parts[i+1]
                    p_num = int(p1) if p1 else int(p2)
                    p_text = parts[i+2].strip()
                    page_chunks[p_num] = p_text
                except: pass
            _log(f"Phase 2: Indexed {len(page_chunks)} normalized page chunks.")
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
            with db_connection() as db:
                row = db.execute("SELECT content FROM topics WHERE id = ?", (t_id,)).fetchone()
                existing_content = json.loads(row[0]) if (row and row[0]) else {}

            if existing_content.get("pre_enriched"):
                _log(f"Topic '{t_title}' is pre-enriched. Using existing content.")
                content = existing_content
            else:
                lesson = generate_full_lesson(t_title, t_type, language, 6, level, source_text=source_text)
                pages = lesson.get("pages", [])
                content = {"pages": pages}
            
            step_up() # Progress marker for Lesson
            
            # 2. Generate a small starter set of questions in the background
            questions = []
            try:
                if pages:
                    # Generate 5 high-quality questions based on the new lesson content
                    questions = ai_generate_questions(
                        t_title, t_type, content, language, 
                        count=5, level=level, is_pdf_source=True
                    )
            except: pass
            
            step_up() # Progress marker for Questions
            
            return {"content": content, "questions": questions, "t_id": t_id, "t_title": t_title}

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Map each future to its metadata
            future_to_topic = {}
            # Context Surgery Helper: Extract relevant pages from source markdown
            def get_surgical_context(page_num, full_text, topic_title=""):
                if not full_text: return ""
                
                # Priority 1: Exact Normalized Page Chunk
                if page_num and page_num in page_chunks:
                    # Take the target page and 2 subsequent pages for full context
                    context_chunk = ""
                    for p in range(page_num, page_num + 3):
                        if p in page_chunks:
                            context_chunk += f"\n[Page {p}]\n{page_chunks[p]}\n"
                    if len(context_chunk) > 100:
                        return context_chunk
                
                # Priority 2: Page Marker Search (if not in indexed chunks)
                if page_num:
                    p_marker = f"Page {page_num}"
                    idx = full_text.find(p_marker)
                    if idx != -1:
                        start = max(0, idx - 200)
                        end = idx + 8000
                        return full_text[start:end]
                
                # Priority 3: Heading Match (Markdown or literal match)
                if topic_title and len(topic_title) > 3:
                    import re
                    h_pattern = rf"(?:^|\n)#+\s*.*{re.escape(topic_title)}.*"
                    h_match = re.search(h_pattern, full_text, re.IGNORECASE)
                    if h_match:
                        start = max(0, h_match.start() - 200)
                        end = h_match.start() + 8000
                        return full_text[start:end]
                    
                    idx = full_text.lower().find(topic_title.lower())
                    if idx != -1:
                        start = max(0, idx - 500)
                        end = idx + 6000
                        return full_text[start:end]
                
                # Priority 4: Final broad fallback (first 8k chars)
                return full_text[:8000]

            for ch in chapters_data:
                for topic in ch.get("topics", []):
                    if topic_count >= MAX_TOTAL_TOPICS: break
                    
                    # Apply Context Surgery
                    topic_page = topic.get("page")
                    surgical_text = get_surgical_context(topic_page, source_markdown_content, topic_title=topic.get("title"))
                    
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

def process_pdf_to_classroom(pdf_path, toc_range, lecturer_id, course_name=None, manual_toc=None, source_markdown_path=None, language=None, level="A1"):
    import logging
    logging.getLogger(__name__).warning("LEGACY PIPELINE IN USE")
    if not course_name or course_name.strip() == "":
        course_name = os.path.basename(pdf_path).replace(".pdf", "").replace("course_", "")
    
    course_id = _uid()
    code = generate_classroom_code()
    textbook_url = "/books/" + os.path.basename(pdf_path)
    
    with db_connection() as db:
        db.execute("INSERT INTO courses (id, name, semester, textbook, language, level, code, is_building, lecturer_id) VALUES (?,?,?,?,?,?,?,?,?)",
                   (course_id, course_name, "Fall 2026", textbook_url, language or "Detecting...", level or "A1", code, 1, lecturer_id))
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
        else:
            cmd.append("Detecting...")
            
        if level:
            cmd.append(level)
        else:
            cmd.append("A1")
            
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
    _log(f"Spawning AI Architect worker: Course {course_id} (Level: {level})")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    # Args: 0:worker.py, 1:pdf_path, 2:toc_range, 3:lecturer_id, 4:course_id, 5:course_name, 6:manual_toc_file, 7:source_markdown, 8:language, 9:level
    cmd = [sys.executable, "worker.py", "NONE", "0-0", str(lecturer_id), str(course_id), course_name, manual_toc_file, "NONE", language, level]
    
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
