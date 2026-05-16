import os
import json
import hashlib
import base64
import urllib.request
import urllib.error
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Manual .env loader for local and worker stability
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ[k] = v

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CHEAP_MODEL = "openai/gpt-4o-mini"
FALLBACK_MODEL = "openai/gpt-4o-mini"

CACHE_NAMESPACE = "pipeline_v2_v4"

# In-memory cache for repeated chunks/prompts
_llm_cache = {}

def get_cache_key(prompt: str) -> str:
    return hashlib.md5((CACHE_NAMESPACE + prompt).encode('utf-8')).hexdigest()

def call_llm(messages: List[Dict[str, str]], retries: int = 2) -> str:
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY is not set!")
        return "[]"

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aulaai.com",
        "X-Title": "AulaAI"
    }
    
    prompt_str = json.dumps(messages)
    cache_key = get_cache_key(prompt_str)
    
    if cache_key in _llm_cache:
        logger.info("CACHE HIT")
        return _llm_cache[cache_key]
    
    models_to_try = [CHEAP_MODEL] + [FALLBACK_MODEL] * retries
    
    for attempt, model in enumerate(models_to_try):
        try:
            payload = {
                "model": model,
                "messages": messages
            }
            
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=90) as response:
                res_body = response.read().decode("utf-8")
                data = json.loads(res_body)

            result = data["choices"][0]["message"]["content"]
            
            # Basic validation that it contains JSON
            # Extract JSON block if surrounded by markdown
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()
                
            # Verify valid JSON parsing
            json.loads(result)
            
            _llm_cache[cache_key] = result
            return result
        except Exception as e:
            logger.warning(f"LLM call failed with model {model} (Attempt {attempt+1}/{len(models_to_try)}): {e}")
            if attempt == len(models_to_try) - 1:
                logger.error("All LLM attempts failed")
                return "[]"
    return "[]"

def call_llm_with_pdf(pdf_path: str, prompt: str, retries: int = 1) -> str:
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY is not set!")
        return "[]"

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aulaai.com",
        "X-Title": "AulaAI"
    }

    try:
        with open(pdf_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to read PDF for LLM: {e}")
        return "[]"

    # OpenRouter format for PDF input
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "file",
                    "file": {
                        "filename": "document.pdf",
                        "file_data": f"data:application/pdf;base64,{pdf_b64}"
                    }
                }
            ]
        }
    ]

    models_to_try = [CHEAP_MODEL] + [FALLBACK_MODEL] * retries
    
    for attempt, model in enumerate(models_to_try):
        try:
            payload = {
                "model": model,
                "max_tokens": 16000,
                "messages": messages,
                "plugins": [
                    {
                        "id": "file-parser",
                        "pdf": {
                            "engine": "mistral-ocr"
                        }
                    }
                ]
            }
            
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=120) as response:
                res_body = response.read().decode("utf-8")
                data = json.loads(res_body)

            result = data["choices"][0]["message"]["content"]
            
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()
                
            json.loads(result)
            return result
        except Exception as e:
            logger.warning(f"PDF LLM call failed with model {model} (Attempt {attempt+1}/{len(models_to_try)}): {e}")
            if attempt == len(models_to_try) - 1:
                logger.error("All PDF LLM attempts failed")
                return "[]"
    return "[]"

def extract_curriculum(text: str) -> Dict[str, Any]:
    if not text:
        return {"units": []}

    prompt = f"""You are a strict JSON generator.

Your ONLY task is to transform input text into valid JSON.

---

🚨 CRITICAL RULES (ABSOLUTE)
* You MUST return ONLY valid JSON
* NO explanations
* NO markdown
* NO text before JSON
* NO text after JSON
* NO comments
* NO trailing commas
* NO partial output
* If you are unsure → still return valid JSON

---

🧠 BEHAVIOR RULES
* Ignore OCR noise
* Ignore unreadable lines
* Fix broken words if obvious
* Merge split lines
* Work in ANY language (language-agnostic)

---

📦 TASK
1. Detect structure: UNIT_HEADER, TOPIC, NOISE (discard)
2. Extract ONLY meaningful topics
3. Tag each topic: grammar, vocabulary, functional, phonetics, communication, mixed
4. Group into units
5. Remove duplicates
6. Perform QA: check logical order, detect noise. Do NOT invent missing basics or foundational units. Strictly stick to the text.
7. Auto-fix: remove garbage, fix wrong tags, mark unclear items as "needs_review"

---

📤 OUTPUT FORMAT (STRICT)
{{
"units": [
{{
"unit": 1,
"topics": [
{{
"name": "string",
"tag": "grammar | vocabulary | functional | phonetics | communication | mixed",
"confidence": 0.0
}}
]
}}
],
"qa_report": {{
"level": "A1",
"issues": [],
"fixes_applied": []
}}
}}

---

INPUT:
{text}
"""
    messages = [{"role": "user", "content": prompt}]
    logger.info("LLM: Full Curriculum Extraction (Strict Mode)")
    result_text = call_llm(messages)
    
    try:
        data = json.loads(result_text)
        
        # Force into a dictionary format if it's just a list
        if isinstance(data, list):
            data = {"units": [{"unit": 1, "topics": data}]}
            
        # Normalize keys for app compatibility
        if isinstance(data, dict) and "units" in data:
            normalized_units = []
            for u in data["units"]:
                if not isinstance(u, dict):
                    continue
                    
                if "unit" in u and "title" not in u:
                    u["title"] = f"Unit {u['unit']}"
                elif "title" not in u:
                    u["title"] = f"Unit {len(normalized_units) + 1}"
                    
                if "topics" in u:
                    normalized_topics = []
                    for t in u["topics"]:
                        if isinstance(t, dict):
                            if "name" in t:
                                t["text"] = t["name"]
                            normalized_topics.append(t)
                        elif isinstance(t, str):
                            normalized_topics.append({"text": t, "tag": "vocabulary"})
                    u["topics"] = normalized_topics
                normalized_units.append(u)
            data["units"] = normalized_units
        return data
    except Exception as e:
        logger.error(f"Failed to parse strict JSON: {e}")
    
    return {"units": []}

def extract_curriculum_from_pdf_direct(pdf_path: str) -> Dict[str, Any]:
    prompt = """You are a strict JSON generator.

Your ONLY task is to transform the attached PDF document into a structured curriculum in valid JSON format.

---

🚨 CRITICAL RULES (ABSOLUTE)
* You MUST return ONLY valid JSON
* NO explanations
* NO markdown
* NO text before JSON
* NO text after JSON
* NO comments
* NO trailing commas
* NO partial output
* If you are unsure → still return valid JSON

---

🧠 BEHAVIOR RULES
* Ignore OCR noise or formatting artifacts
* Ignore unreadable lines
* Fix broken words if obvious
* Work in ANY language (language-agnostic)

---

📦 TASK
1. Read the PDF content, focusing specifically on the Table of Contents or chapter breakdowns.
2. Detect structure: UNIT_HEADER (e.g., Unit 1, Lektion 2, Chapter 3), TOPIC, NOISE (discard).
3. Extract EVERY SINGLE UNIT and EVERY SINGLE TOPIC found in the document. Do not summarize or skip any units.
4. Tag each topic: grammar, vocabulary, functional, phonetics, communication, mixed
5. Group them correctly into their respective units as shown in the book.
6. Remove duplicates
7. Perform QA: check logical order, detect noise. Do NOT invent missing basics (e.g. alphabet) or foundational units. Strictly stick to the PDF.
8. Auto-fix: remove garbage, fix wrong tags, mark unclear items as "needs_review"
9. DROPPING EMPTY/UNDEVELOPED UNITS: Do not include topics that represent missing, blank, or undeveloped content (e.g., "Undeveloped", "Blank", "TBD"). If a unit has no valid topics after dropping these, REMOVE the entire unit. Do NOT output empty units.
10. CULTURAL & REVIEW FILTER: Do NOT extract generic "Review" chapters, test sections, or purely geographical/cultural notes (e.g., "Berlin, Germany"). Only extract actionable language lessons (grammar, vocabulary, conversation).

---

📤 OUTPUT FORMAT (STRICT)
{
"units": [
{
"unit": 1,
"title": "[Exact name of the first unit as written in the book]",
"topics": [
{
"name": "[Topic name from book]",
"tag": "grammar | vocabulary | functional | phonetics | communication | mixed",
"confidence": 0.0
}
]
},
{
"unit": 2,
"title": "[Exact name of the second unit as written in the book]",
"topics": [
{
"name": "[Topic name from book]",
"tag": "vocabulary"
}
]
}
// Generate ALL units exactly as they appear in the document! DO NOT invent titles!
],
"qa_report": {
"level": "A1",
"issues": [],
"fixes_applied": []
}
}
"""
    logger.info("LLM: Direct PDF Curriculum Extraction (OpenRouter Mistral OCR)")
    result_text = call_llm_with_pdf(pdf_path, prompt)
    
    try:
        data = json.loads(result_text)
        
        # Force into a dictionary format if it's just a list
        if isinstance(data, list):
            data = {"units": [{"unit": 1, "topics": data}]}
            
        # Normalize keys for app compatibility
        if isinstance(data, dict) and "units" in data:
            normalized_units = []
            for u in data["units"]:
                if not isinstance(u, dict):
                    continue
                    
                if "unit" in u and "title" not in u:
                    u["title"] = f"Unit {u['unit']}"
                elif "title" not in u:
                    u["title"] = f"Unit {len(normalized_units) + 1}"
                    
                if "topics" in u:
                    normalized_topics = []
                    for t in u["topics"]:
                        if isinstance(t, dict):
                            if "name" in t:
                                t["text"] = t["name"]
                            normalized_topics.append(t)
                        elif isinstance(t, str):
                            normalized_topics.append({"text": t, "tag": "vocabulary"})
                    u["topics"] = normalized_topics
                normalized_units.append(u)
            data["units"] = normalized_units
        return data
    except Exception as e:
        logger.error(f"Failed to parse strict JSON from PDF: {e}")
    
    return {"units": []}

def normalize_curriculum(curriculum_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Final polish pass to deduplicate topics, fix numbering, and normalize tags.
    """
    if not curriculum_data or not curriculum_data.get("units"):
        return curriculum_data

    prompt = f"""You are a STRICT curriculum normalizer and deduplication engine.

You will receive a structured curriculum JSON that may contain:
* duplicated units
* duplicated topics
* inconsistent unit numbering
* mixed languages
* repeated concepts with different wording

Your job is to FIX the structure.

---

🚨 HARD RULES
* Output ONLY valid JSON
* Do NOT explain anything
* Do NOT add text before or after JSON
* Do NOT change topic meaning
* Do NOT invent new topics

---

🧠 TASK
1. FIX UNIT STRUCTURE: Units MUST be sequential (Unit 1, Unit 2...). Merge duplicates.
2. DEDUPLICATE TOPICS: Keep ONLY ONE version of a topic, even if wording/language differs.
3. REMOVE NOISE: Delete meaningless lines or broken OCR text.
4. NORMALIZE TOPICS: Keep names SHORT and concise. Tag each as grammar, vocabulary, functional, phonetics, communication, or mixed.
5. UNIT BALANCING: Distribute topics logically.
6. DROPPING EMPTY/UNDEVELOPED UNITS: Do not include topics that represent missing, blank, or undeveloped content (e.g., "Undeveloped", "Blank", "TBD"). If a unit has no valid topics after dropping these, REMOVE the entire unit.
7. CULTURAL & REVIEW FILTER: Do NOT extract generic "Review" chapters, test sections, or purely geographical/cultural notes (e.g., "Berlin, Germany"). Only extract actionable language lessons (grammar, vocabulary, conversation).
8. FINAL CLEANUP: No empty units, no duplicate topics anywhere.

---

📤 OUTPUT FORMAT
{{
"units": [
{{
"unit": 1,
"title": "[Exact name of the first unit]",
"topics": [
{{
"name": "string",
"tag": "..."
}}
]
}},
{{
"unit": 2,
"title": "[Exact name of the second unit]",
"topics": [
{{
"name": "string",
"tag": "..."
}}
]
}}
// Keep all units from the input! Do NOT use example titles!
]
}}

---

INPUT:
{json.dumps(curriculum_data, indent=2)}
"""
    messages = [{"role": "user", "content": prompt}]
    logger.info("LLM: Final Curriculum Normalization (Polish Pass)")
    result_text = call_llm(messages)
    
    try:
        data = json.loads(result_text)
        # Normalize keys for app compatibility
        if "units" in data:
            for u in data["units"]:
                if "unit" in u and "title" not in u:
                    u["title"] = f"Unit {u['unit']}"
                if "topics" in u:
                    for t in u["topics"]:
                        if "name" in t:
                            t["text"] = t["name"]
        return data
    except Exception as e:
        logger.error(f"Normalization failed, returning original data: {e}")
        return curriculum_data
