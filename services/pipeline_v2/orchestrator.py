import os
import logging
import json
from database import db_connection, _uid
from services.state import bump_version
from .pdf_processor import process_pdf, process_text

logger = logging.getLogger(__name__)

def start_pipeline_v2(pdf_path, course_id, lecturer_id, manual_toc=None, language="Detecting...", level="A1"):
    """
    V2 Pipeline Orchestrator that extracts data and populates the database.
    This is the modern replacement for start_pipeline_background.
    """
    try:
        logger.info(f"V2 Orchestrator starting for Course {course_id}")
        
        if manual_toc and (pdf_path == "NONE" or not pdf_path):
            logger.info("Manual TOC detected, skipping PDF extraction.")
            try:
                # Try JSON first (Legacy support)
                curriculum = json.loads(manual_toc)
                
                # Map legacy manual TOC structure (chapters/topics) to V2 (units/topics) if needed
                if "chapters" in curriculum:
                    units = []
                    for ch in curriculum["chapters"]:
                        unit = {"title": ch.get("title", "Untitled"), "topics": []}
                        for t in ch.get("topics", []):
                            if isinstance(t, dict):
                                unit["topics"].append({"text": t.get("title", ""), "tag": t.get("type", "vocabulary")})
                            else:
                                unit["topics"].append({"text": str(t), "tag": "vocabulary"})
                        units.append(unit)
                    curriculum = {"units": units}
            except json.JSONDecodeError:
                # It's raw text! Use the V2 pipeline logic on the text itself
                logger.info("Manual TOC is raw text, running V2 extraction logic on text.")
                lines = manual_toc.splitlines()
                curriculum = process_text(lines)
        else:
            # 1. Run the V2 extraction pipeline
            curriculum = process_pdf(pdf_path)
        
        # ── MANDATORY ALPHABET FOR A1 ──
        if level.upper().startswith("A1"):
            logger.info(f"A1 Level detected. Ensuring mandatory Alphabet lesson for {language}.")
            # 1. Remove any existing Alphabet topics to avoid duplicates
            for unit in curriculum.get("units", []):
                unit["topics"] = [t for t in unit.get("topics", []) if "alphabet" not in t.get("text", "").lower()]
            
            # 2. Ensure we have at least one unit
            if not curriculum.get("units"):
                curriculum["units"] = [{"title": "Unit 1", "topics": []}]
            
            # 3. Inject Alphabet as the first topic of the first unit
            alphabet_topic = {
                "text": "Alphabet and Pronunciation",
                "tag": "phonetics",
                "confidence": 1.0
            }
            curriculum["units"][0]["topics"].insert(0, alphabet_topic)

        # 2. Populate the Database
        with db_connection() as db:
            # We assume the course record already exists (created by server.py or main.py)
            
            # Clean up any existing structure for this course if we are re-running
            db.execute("DELETE FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id = ?)", (course_id,))
            db.execute("DELETE FROM chapters WHERE course_id = ?", (course_id,))
            
            for unit_idx, unit in enumerate(curriculum.get("units", [])):
                chapter_id = _uid()
                unit_title = unit.get("title", f"Unit {unit_idx + 1}")
                
                db.execute(
                    "INSERT INTO chapters (id, course_id, number, title, page_number) VALUES (?,?,?,?,?)",
                    (chapter_id, course_id, unit_idx + 1, unit_title, 0) # V2 currently lacks page numbers
                )
                
                for topic_idx, topic in enumerate(unit.get("topics", [])):
                    topic_id = _uid()
                    t_text = topic.get("text", "Untitled Topic")
                    t_tag = topic.get("tag", "vocabulary")
                    
                    # We use a default difficulty and empty content as V2 focus is structure
                    db.execute(
                        "INSERT INTO topics (id, chapter_id, type, title, difficulty, content, sort_order, page_number, pdf_url) VALUES (?,?,?,?,?,?,?,?,?)",
                        (topic_id, chapter_id, t_tag, t_text, level, json.dumps({}), topic_idx, 0, "/books/" + os.path.basename(pdf_path))
                    )
            
            # Finalize Structural Phase: Set progress = 20 (Phase 1 complete)
            # Do NOT set is_building = 0 yet, as we need to run enrichment (Phase 2)
            db.execute("UPDATE courses SET progress = 20 WHERE id = ?", (course_id,))
            db.commit()
            
        logger.info(f"V2 Orchestrator finished for Course {course_id}")
        bump_version()
        
    except Exception as e:
        logger.error(f"V2 Orchestrator FATAL ERROR: {e}")
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
            db.commit()
        raise e
