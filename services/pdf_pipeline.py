import json
import uuid
import os
import random
import concurrent.futures
import threading
import logging
from datetime import datetime
import urllib.request
import time
from database import db_connection
from services.ai_engine import parse_toc, generate_topic_content, ai_generate_questions
from services.state import bump_version

def _uid():
    return str(uuid.uuid4())

def _log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_line = f"[{timestamp}] [PIPELINE] {msg}"
    print(log_line, flush=True) # Mirror to stdout for Railway/Console
    with open("pipeline.log", "a", encoding="utf-8") as f:
        f.write(log_line + "\n")
        f.flush()

def generate_classroom_code():
    return "".join([str(random.randint(0, 9)) for _ in range(5)])

def start_pipeline_background(pdf_path, toc_range, lecturer_id, course_id, course_name):
    """
    Background worker that runs Phase 1 and Phase 2.
    """
    _log(f"Background worker started for {course_id} ({course_name})")
    
    # 1. Extract TOC Text
    _log("Step 1: Extracting TOC text from PDF...")
    try:
        if "-" in toc_range:
            parts = toc_range.split("-")
            start_pg = int(parts[0].strip())
            end_pg = int(parts[1].strip())
        else:
            start_pg = end_pg = int(toc_range.strip())

        # Try Primary Parser (pypdf)
        toc_text = ""
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            for i in range(start_pg - 1, end_pg):
                if i < len(reader.pages):
                    page_text = reader.pages[i].extract_text()
                    if page_text:
                        toc_text += page_text + "\n"
        except Exception as e:
            _log(f"pypdf failed: {e}. Trying fallback parser...")
            # Try Fallback Parser (pdfplumber)
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    for i in range(start_pg - 1, end_pg):
                        if i < len(pdf.pages):
                            page_text = pdf.pages[i].extract_text()
                            if page_text:
                                toc_text += page_text + "\n"
            except (ImportError, Exception) as e2:
                _log(f"Fallback parser failed: {e2}")
                toc_text = ""

        _log(f"TOC Extraction complete. Length: {len(toc_text)} chars")
        if len(toc_text) < 200:
            _log("WARNING: Very little text extracted. Check if TOC pages are correct (e.g. 1-10).")
    except Exception as e:
        _log(f"ERROR in TOC Extraction: {e}")
        # Error will be caught by the empty check below

    if not toc_text.strip():
        _log("ERROR: This PDF could not be read — try a different file or a text-based PDF.")
        # Update the DB record to show failure
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
            db.commit()
        return

    # 2. Detect Language
    _log("Step 2: Detecting language...")
    try:
        from services.ai_engine import detect_language
        language = detect_language(toc_text)
    except Exception as e:
        _log(f"Language detection failed: {e}. Defaulting to Unknown.")
        language = "Unknown"
    
    _log(f"Language detected: {language}")
    
    # 3. Parse TOC
    _log("Step 3: Parsing TOC with AI...")
    chapters_data = parse_toc(toc_text, language)
    if not chapters_data:
        _log("ERROR: AI failed to parse TOC.")
        return
    _log(f"TOC parsed. Found {len(chapters_data)} chapters.")

    # 4. Update Course and Create structure
    _log("Step 4: Creating classroom structure in DB...")
    with db_connection() as db:
        db.execute("UPDATE courses SET language = ? WHERE id = ?", (language, course_id))
        
        for idx, ch in enumerate(chapters_data):
            chapter_id = _uid()
            ch_num = idx + 1 # Force sequential numbering
            ch_title = str(ch.get("title", "Untitled Chapter"))
            _log(f"Inserting Chapter {ch_num}: {ch_title}")
            
            db.execute("INSERT INTO chapters (id, course_id, number, title) VALUES (?,?,?,?)",
                       (chapter_id, course_id, ch_num, ch_title))
            
            for topic_idx, topic in enumerate(ch.get("topics", [])):
                topic_id = _uid()
                t_title = topic.get("title", "Untitled Topic")
                t_type = topic.get("type", "vocabulary")
                db.execute("INSERT INTO topics (id, chapter_id, type, title, difficulty, content, sort_order) VALUES (?,?,?,?,?,?,?)",
                           (topic_id, chapter_id, t_type, t_title, "A1.1", json.dumps({}), topic_idx))
        db.commit()
        bump_version()
    _log("Structure creation complete.")

    # Start Phase 2: Enrichment
    _log("Phase 2: Starting content enrichment...")
    enrich_classroom_phase2(course_id, chapters_data, language)
    _log("Full Pipeline Complete.")

def enrich_classroom_phase2(course_id, chapters_data, language):
    """
    Phase 2: Async. Enriches topics with content and questions.
    """
    with open("pipeline.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [PIPELINE] PHASE2 THREAD STARTED\n")
        f.flush()
    try:
        _log(f"Phase 2 Enrichment started for {course_id}")
        
        with db_connection() as db:
            chapters = db.execute("SELECT id, title FROM chapters WHERE course_id = ?", (course_id,)).fetchall()
            chapter_map = {c["title"]: c["id"] for c in chapters}
            
        # Increase limit to cover full curriculum (typically 9-12 chapters, 20-30 topics)
        # Allow up to 250 topics for massive textbooks
        MAX_TOTAL_TOPICS = 250 
        topic_count = 0
        
        _log(f"Phase 2: Generating content for topics (limit: {MAX_TOTAL_TOPICS})...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for ch in chapters_data:
                chapter_id = chapter_map.get(str(ch.get("title")))
                if not chapter_id: continue
                
                for i, topic in enumerate(ch.get("topics", [])):
                    if topic_count >= MAX_TOTAL_TOPICS: break
                    
                    t_title = topic.get("title", "Untitled Topic")
                    t_type = topic.get("type", "vocabulary")
                    
                    _log(f"Queueing topic: {t_title} ({t_type})")
                    f_content = executor.submit(generate_topic_content, t_title, t_type, language)
                    f_questions = executor.submit(ai_generate_questions, t_title, t_type, {}, language, 8)
                    
                    futures.append((chapter_id, t_title, f_content, f_questions))
                    topic_count += 1
                if topic_count >= MAX_TOTAL_TOPICS: break

            completed = 0
            for chapter_id, t_title, f_content, f_questions in futures:
                _log(f"Waiting for results: {t_title}...")
                content = f_content.result() or {}
                questions = f_questions.result() or []
                
                with db_connection() as db:
                    topic_row = db.execute("SELECT id FROM topics WHERE chapter_id = ? AND title = ?", (chapter_id, t_title)).fetchone()
                    if topic_row:
                        topic_id = topic_row["id"]
                        db.execute("UPDATE topics SET content = ? WHERE id = ?", (json.dumps(content), topic_id))
                        
                        for q in questions:
                            db.execute("INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) VALUES (?,?,?,?,?,?,?,1)",
                                       (_uid(), topic_id, q.get("type", "mcq"), q.get("prompt", ""), q.get("answer", ""), 
                                        json.dumps(q.get("distractors", [])), "A1.1"))
                    db.commit()
                completed += 1
                _log(f"✓ Topic finalized: {t_title} ({completed}/{len(futures)})")

        # Mark as complete
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
            db.commit()
        bump_version()
        _log(f"Phase 2 Complete. Course {course_id} is now fully built.")
    except Exception as e:
        import traceback
        _log(f"CRITICAL ERROR in Phase 2 Enrichment for {course_id}: {e}")
        traceback.print_exc()
        # Ensure we at least try to mark it as not building so it doesn't stay ghosted forever (though it might be broken)
        try:
            with db_connection() as db:
                db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
                db.commit()
        except: pass

def process_pdf_to_classroom(pdf_path, toc_range, lecturer_id, course_name=None):
    # This is now the entry point that initializes the DB and kicks off the background thread
    _log(f"Initializing Phase 1 for {pdf_path}")
    
    if not course_name or course_name.strip() == "" or "course_" in course_name:
        course_name = os.path.basename(pdf_path).replace(".pdf", "").replace("course_", "").replace("upload_", "")
    
    textbook_url = "/" + pdf_path.split("public" + os.sep)[-1].replace(os.sep, "/")
    course_id = _uid()
    code = generate_classroom_code()
    
    # Create the record IMMEDIATELY so it's visible in the UI
    with db_connection() as db:
        db.execute("INSERT INTO courses (id, name, semester, textbook, language, code, is_building, lecturer_id) VALUES (?,?,?,?,?,?,?,?)",
                   (course_id, course_name, "Fall 2026", textbook_url, "Detecting...", code, 1, lecturer_id))
        db.commit()
    
    _log(f"Initial record created. Course ID: {course_id}, Code: {code}")

    # Kick off background process using a separate OS process for reliability on Linux/Railway
    import subprocess
    import sys
    
    # Use the same python interpreter
    python_exe = sys.executable
    cmd = [
        python_exe, "worker.py",
        pdf_path,
        toc_range,
        lecturer_id,
        course_id,
        course_name
    ]
    
    # We use Popen and don't wait for it.
    # We set PYTHONUNBUFFERED to ensure logs show up immediately in Railway
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    _log(f"Spawning background process: {' '.join(cmd)}")
    subprocess.Popen(cmd, stdout=None, stderr=None, close_fds=True, env=env)

    return {"success": True, "course_id": course_id, "code": code, "name": course_name}
