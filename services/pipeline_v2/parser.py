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
    
    seen_text_in_current_unit = set()
    
    for item in structured_lines:
        item_type = item.get("type")
        text = item.get("text", "").strip()
        
        # Check for explicit tags in the text like [grammar] or [vocabulary]
        tag_match = re.search(r'\[(vocabulary|grammar|reading|culture)\]', text, re.IGNORECASE)
        explicit_tag = tag_match.group(1).lower() if tag_match else None
        
        # Clean the text of the tag for the final title
        clean_text = re.sub(r'\[.*?\]', '', text).strip()
        
        # HEURISTIC: If we see a line of text we've already seen in this unit,
        # it's a strong signal of a new unit starting (e.g. repeating "RECURSOS...")
        is_repeating_pattern = clean_text in seen_text_in_current_unit and len(clean_text) > 5
        
        if item_type == "UNIT_TITLE" or is_repeating_pattern:
            # Create new unit. If it was a repeating pattern, use a generic name or the title if it's a UNIT_TITLE
            new_title = clean_text if item_type == "UNIT_TITLE" else f"Unit {len(units) + 1}"
            current_unit = {"title": new_title, "topics": []}
            units.append(current_unit)
            seen_text_in_current_unit = set()
            
        if item_type in ["TOPIC", "SECTION_TITLE"]:
            if current_unit is None:
                current_unit = {"title": "Unit 1", "topics": []}
                units.append(current_unit)
            
            # Priority: Explicit tag in text > LLM tag > default
            tag = explicit_tag or topic_tags.get(text, "vocabulary")
            current_unit["topics"].append({"text": clean_text, "tag": tag})
            seen_text_in_current_unit.add(clean_text)
            
    if not units:
        units.append({"title": "Unit 1", "topics": []})
        
    return {"units": units}
