import os
import logging
import json
from database import db_connection, _uid
from services.state import bump_version
from .pdf_processor import process_pdf, process_text

logger = logging.getLogger(__name__)

def parse_markdown_toc(text: str) -> dict:
    import re
    units = []
    current_unit = None
    
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
            
        # Detect unit title (starts with #)
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            current_unit = {"title": title, "topics": []}
            units.append(current_unit)
            continue
            
        # Check if it is a bullet point
        is_bullet = False
        clean_line = line
        if line.startswith(("-", "*", "+")):
            is_bullet = True
            clean_line = line.lstrip("-*+ ").strip()
        elif re.match(r'^\d+[\.\)]\s+', line):
            is_bullet = True
            clean_line = re.sub(r'^\d+[\.\)]\s+', '', line).strip()
            
        if is_bullet:
            tag_match = re.search(r'\[(vocabulary|grammar|reading|culture|communication|phonetics|mixed|communicative)\]', clean_line, re.IGNORECASE)
            tag = "vocabulary"
            if tag_match:
                tag = tag_match.group(1).lower()
                if tag == "communicative":
                    tag = "communication"
                clean_line = re.sub(r'\[.*?\]', '', clean_line).strip()
                
            if current_unit is None:
                current_unit = {"title": "Unit 1", "topics": []}
                units.append(current_unit)
                
            current_unit["topics"].append({"text": clean_line, "tag": tag})
        else:
            # Check if it matches a Unit pattern
            if re.match(r'^(?:Unit|Unidad|Lektion|Chapter|Kapitel|Tema)\s*\d+', line, re.IGNORECASE):
                current_unit = {"title": line, "topics": []}
                units.append(current_unit)
                
    return {"units": units}

def start_pipeline_v2(pdf_path, course_id, lecturer_id, manual_toc=None, language="Detecting...", level="A1", gen_id="LEGACY", toc_range=None):
    """
    V2 Pipeline Orchestrator that extracts data and populates the database.
    This is the modern replacement for start_pipeline_background.
    """
    try:
        logger.info(f"V2 Orchestrator starting for Course {course_id}")
        
        if manual_toc:
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
                # Try structured markdown parsing first to avoid LLM calls
                logger.info("Parsing manual TOC as structured markdown...")
                curriculum = parse_markdown_toc(manual_toc)
                
                # Fallback to LLM extraction if markdown parsing yields zero topics
                total_parsed_topics = sum(len(u.get("topics", [])) for u in curriculum.get("units", []))
                if total_parsed_topics == 0:
                    logger.info("Structured markdown parsing yielded 0 topics. Falling back to LLM extraction.")
                    lines = manual_toc.splitlines()
                    curriculum = process_text(lines)
                else:
                    logger.info(f"Successfully parsed {total_parsed_topics} topics from structured markdown (0 LLM calls used).")
        else:
            # 1. Run the V2 extraction pipeline
            curriculum = process_pdf(pdf_path, toc_range=toc_range)
        
        # ── MANDATORY ALPHABET FOR A1 (AI Architect only, NOT PDF extraction) ──
        is_ai_architect = manual_toc and (pdf_path == "NONE" or not pdf_path)
        if level.upper().startswith("A1") and is_ai_architect:
            logger.info(f"[ALPHABET] A1 Level detected for Course {course_id}. Prepending mandatory Alphabet unit.")
            # 1. Ensure we have a dict with a 'units' list
            if not isinstance(curriculum, dict):
                curriculum = {"units": []}
            if "units" not in curriculum:
                curriculum["units"] = []
                
            # 2. Remove any existing Alphabet/Phonetic topics from all units to avoid duplicates
            keywords = ["alphabet", "vowel", "consonant", "pronunciation", "phonetic", "sound", "alfabeto", "alfabe"]
            for unit in curriculum["units"]:
                unit["topics"] = [t for t in unit.get("topics", []) if not any(kw in t.get("text", "").lower() for kw in keywords)]
            
            # 3. Create the dedicated Alphabet Unit
            alphabet_unit = {
                "title": "Unit 1: Alphabet and Foundations",
                "topics": [
                    {"text": "The Alphabet", "tag": "phonetics", "confidence": 1.0},
                    {"text": "Vowels and Consonants", "tag": "grammar", "confidence": 1.0},
                    {"text": "Pronunciation and Phonetics", "tag": "grammar", "confidence": 1.0}
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
                    # Remove any existing "Unit X" prefix to avoid "Unit 1: Unit 1: ..."
                    clean_title = re.sub(r'^Unit\s*\d+\s*[:\-]*\s*', '', unit_title, flags=re.IGNORECASE).strip()
                    unit_title = clean_title # UI handles the numbering header

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
            # Only update if our generation_id is still current
            db.execute("UPDATE courses SET progress = 20 WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')", (course_id, gen_id, gen_id))
            db.commit()
            
        logger.info(f"V2 Orchestrator finished for Course {course_id}")
        bump_version()
        
    except Exception as e:
        logger.error(f"V2 Orchestrator FATAL ERROR: {e}")
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')", (course_id, gen_id, gen_id))
            db.commit()
        raise e
