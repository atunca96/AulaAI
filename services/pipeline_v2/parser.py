import re
from typing import List, Dict, Any

def clean_lines(lines: List[str]) -> List[str]:
    cleaned = []
    seen = set()
    for line in lines:
        if not line:
            continue
        line = line.strip()
        if not line:
            continue
        if len(line) < 2:
            continue
        
        # Remove OCR garbage (regex: non-alphanumeric dominant)
        # We calculate the ratio of alphanumeric characters.
        alnum_count = sum(c.isalnum() for c in line)
        if len(line) > 0 and (alnum_count / len(line)) < 0.3:
            continue
        
        # Remove page numbers (lines that are just digits)
        if line.isdigit():
            continue
            
        if line not in seen:
            seen.add(line)
            cleaned.append(line)
    return cleaned

def chunk_lines(lines: List[str], size: int = 40) -> List[List[str]]:
    return [lines[i:i + size] for i in range(0, len(lines), size)]

def build_curriculum(structured_lines: List[Dict[str, str]], tagged_topics: List[Dict[str, str]]) -> Dict[str, Any]:
    units = []
    current_unit = None
    
    # Map topics to tags for quick lookup
    topic_tags = {item["text"]: item.get("tag", "vocabulary") for item in tagged_topics}
    
    # Stop titles that are likely book noise, not units
    STOP_TITLES = [
        "AULA INTERNACIONAL", "AULA INTERNACIONAL PLUS", "AULA", 
        "INTRODUCCIÓN", "PREFACIO", "BIENVENIDOS", "ÍNDICE",
        "RECURSOS PARA ESTUDIANTES", "CAMPUS DIFUSIÓN"
    ]
    
    seen_text_in_current_unit = set()
    
    for item in structured_lines:
        item_type = item.get("type")
        text = item.get("text", "").strip()
        
        # 1. Clean and check for tags
        tag_match = re.search(r'\[(vocabulary|grammar|reading|culture|communicative)\]', text, re.IGNORECASE)
        explicit_tag = tag_match.group(1).lower() if tag_match else None
        clean_text = re.sub(r'\[.*?\]', '', text).strip()
        
        if not clean_text or len(clean_text) < 3:
            continue

        # 2. UNIT DETECTION
        is_unit_trigger = False
        
        # Type A: LLM Explicitly called it a UNIT_TITLE
        if item_type == "UNIT_TITLE":
            is_unit_trigger = True
            
        # Type B: Numbered unit pattern (e.g., "1. ME LLAMO", "UNIDAD 2")
        if re.match(r'^(?:\d+[\.\)]|UNIDAD\s*\d+)', clean_text.upper()):
            is_unit_trigger = True
            
        # Type C: Repeating major pattern (RECURSOS...)
        if clean_text in seen_text_in_current_unit and len(clean_text) > 10:
            is_unit_trigger = True
            
        # FILTER: Prevent noise from becoming units
        if is_unit_trigger:
            upper_text = clean_text.upper()
            if any(stop in upper_text for stop in STOP_TITLES):
                is_unit_trigger = False

        if is_unit_trigger:
            # Avoid duplicate units if the title is exactly the same as the last one
            if units and units[-1]["title"] == clean_text:
                continue
                
            current_unit = {"title": clean_text, "topics": []}
            units.append(current_unit)
            seen_text_in_current_unit = set()
            continue # Don't add the unit title as a topic

        # 3. TOPIC ADDITION
        if current_unit is None:
            # Only start Unit 1 if we actually have a topic
            current_unit = {"title": "Unit 1", "topics": []}
            units.append(current_unit)
            
        # Add to current unit
        tag = explicit_tag or topic_tags.get(text, "vocabulary")
        current_unit["topics"].append({"text": clean_text, "tag": tag})
        seen_text_in_current_unit.add(clean_text)
            
    if not units or (len(units) == 1 and not units[0]["topics"]):
        return {"units": []}
        
    return {"units": units}
