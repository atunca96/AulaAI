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
            logger.info(f"[ALPHABET] A1 Level detected for Course {course_id}. Prepending mandatory Alphabet unit.")
            # 1. Ensure we have a dict with a 'units' list
            if not isinstance(curriculum, dict):
                curriculum = {"units": []}
            if "units" not in curriculum:
                curriculum["units"] = []
                
            # 2. Remove any existing Alphabet topics from all units to avoid duplicates
            for unit in curriculum["units"]:
                unit["topics"] = [t for t in unit.get("topics", []) if "alphabet" not in t.get("text", "").lower()]
            
            # 3. Create the dedicated Alphabet Unit
            alphabet_unit = {
                "title": "Unit 1: Alphabet and Foundations",
                "topics": [
                    {
                        "text": "The Alphabet", # Manually requested name
                        "tag": "phonetics",
                        "confidence": 1.0
                    }
                ]
            }
            
            # 4. Prepend to curriculum and ensure no empty units were left behind
            curriculum["units"].insert(0, alphabet_unit)
            # Cleanup: remove any units that are now empty (except our new one at index 0)
            curriculum["units"] = [u for i, u in enumerate(curriculum["units"]) if i == 0 or u.get("topics")]
            logger.info(f"[ALPHABET] Injection complete. Unit 1 is now: {curriculum['units'][0]['title']}")

        # 2. Populate the Database
        with db_connection() as db:
            # We assume the course record already exists (created by server.py or main.py)
            
            # Clean up any existing structure for this course if we are re-running
            db.execute("DELETE FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id = ?)", (course_id,))
            db.execute("DELETE FROM chapters WHERE course_id = ?", (course_id,))
            
            for unit_idx, unit in enumerate(curriculum.get("units", [])):
                chapter_id = _uid()
                unit_title = unit.get("title", f"Unit {unit_idx + 1}")
                
                # Standardize Unit Numbering for A1 (especially after alphabet injection)
                if level.upper().startswith("A1"):
                    import re
                    # Remove any existing "Unit X" prefix to avoid "Unit 2: Unit 1: Greetings"
                    clean_title = re.sub(r'^Unit\s*\d+\s*[:\-]*\s*', '', unit_title, flags=re.IGNORECASE).strip()
                    unit_title = f"Unit {unit_idx + 1}: {clean_title}"

                db.execute(
                    "INSERT INTO chapters (id, course_id, number, title, page_number) VALUES (?,?,?,?,?)",
                    (chapter_id, course_id, unit_idx + 1, unit_title, 0) # V2 currently lacks page numbers
                )
                
                for topic_idx, topic in enumerate(unit.get("topics", [])):
                    topic_id = _uid()
                    t_text = topic.get("text", "Untitled Topic")
                    t_tag = topic.get("tag", "vocabulary")
                    
                    # ── PRE-ENRICH ALPHABET TOPIC ──
                    t_content = {}
                    if t_text == "The Alphabet":
                        from services.language_data import ALPHABETS
                        lang_key = next((k for k in ALPHABETS.keys() if k.lower() in language.lower()), None)
                        if lang_key:
                            logger.info(f"[ALPHABET] Pre-enriching '{t_text}' with static data for {lang_key}")
                            data = ALPHABETS[lang_key]
                            items = []
                            if "items" in data:
                                items = data["items"]
                            elif "sets" in data:
                                # Flatten sets (e.g. for Chinese/Japanese)
                                for s in data["sets"]:
                                    items.extend(s.get("items", []))
                            
                            t_content = {
                                "pages": [
                                    {
                                        "type": "vocabulary",
                                        "title": f"The {lang_key} Alphabet",
                                        "items": items
                                    }
                                ],
                                "pre_enriched": True # Flag for Phase 2 to skip
                            }

                    # We use a default difficulty and empty content as V2 focus is structure
                    db.execute(
                        "INSERT INTO topics (id, chapter_id, type, title, difficulty, content, sort_order, page_number, pdf_url) VALUES (?,?,?,?,?,?,?,?,?)",
                        (topic_id, chapter_id, t_tag, t_text, level, json.dumps(t_content), topic_idx, 0, "/books/" + os.path.basename(pdf_path))
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
