import json
import uuid
import os
from pypdf import PdfReader
from database import db_connection
from services.ai_engine import detect_language, parse_toc, generate_topic_content, ai_generate_questions

def _uid():
    return str(uuid.uuid4())

def process_pdf_to_classroom(pdf_path, toc_range, lecturer_id):
    """
    Full pipeline: PDF -> Text -> Language -> TOC -> Content -> DB.
    toc_range is a string like "2-5" (1-indexed).
    """
    print(f"[PIPELINE] Starting PDF processing: {pdf_path}, Range: {toc_range}")
    
    # 1. Extract TOC Text
    try:
        reader = PdfReader(pdf_path)
        start_pg, end_pg = map(int, toc_range.split("-"))
        toc_text = ""
        for i in range(start_pg - 1, end_pg):
            if i < len(reader.pages):
                toc_text += reader.pages[i].extract_text() + "\n"
    except Exception as e:
        print(f"[PIPELINE] PDF Extraction error: {e}")
        return {"success": False, "error": f"Failed to read PDF: {e}"}

    if not toc_text.strip():
        return {"success": False, "error": "No text extracted from specified TOC range."}

    # 2. Detect Language
    language = detect_language(toc_text)
    print(f"[PIPELINE] Detected Language: {language}")

    # 3. Parse TOC
    chapters_data = parse_toc(toc_text, language)
    if not chapters_data:
        return {"success": False, "error": "Failed to parse Table of Contents."}
    print(f"[PIPELINE] Parsed {len(chapters_data)} chapters.")

    # 4. Create Course in DB
    course_name = os.path.basename(pdf_path).replace(".pdf", "")
    course_id = _uid()
    
    with db_connection() as db:
        db.execute("INSERT INTO courses (id, name, semester, textbook, language, lecturer_id) VALUES (?,?,?,?,?,?)",
                   (course_id, course_name, "Fall 2026", course_name, language, lecturer_id))
        
        # 5. Process Chapters and Topics
        for ch in chapters_data:
            chapter_id = _uid()
            db.execute("INSERT INTO chapters (id, course_id, number, title) VALUES (?,?,?,?)",
                       (chapter_id, course_id, ch.get("number", 0), ch.get("title", "Untitled Chapter")))
            
            for i, topic in enumerate(ch.get("topics", [])):
                topic_id = _uid()
                topic_title = topic.get("title", "Untitled Topic")
                topic_type = topic.get("type", "vocabulary")
                
                print(f"[PIPELINE] Generating content for: {topic_title} ({topic_type})")
                
                # Generate Topic Content (Vocabulary or Grammar)
                content = generate_topic_content(topic_title, topic_type, language)
                if not content:
                    content = {"words": {}} if topic_type == "vocabulary" else {"rules": [], "examples": []}
                
                db.execute("INSERT INTO topics (id, chapter_id, type, title, difficulty, content, sort_order) VALUES (?,?,?,?,?,?,?)",
                           (topic_id, chapter_id, topic_type, topic_title, "A1.1", json.dumps(content), i))
                
                # Generate Questions
                questions = ai_generate_questions(topic_title, topic_type, content, language, count=6)
                if questions:
                    for q in questions:
                        db.execute("INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) VALUES (?,?,?,?,?,?,?,1)",
                                   (_uid(), topic_id, q.get("type", "mcq"), q.get("prompt", ""), q.get("answer", ""), 
                                    json.dumps(q.get("distractors", [])), "A1.1"))
        
        db.commit()

    print(f"[PIPELINE] Finished. Course ID: {course_id}")
    return {"success": True, "course_id": course_id, "language": language}
