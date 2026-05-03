import os
import json
import hashlib
import requests
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
CHEAP_MODEL = "anthropic/claude-3.5-haiku"
FALLBACK_MODEL = "anthropic/claude-3.5-haiku"

CACHE_NAMESPACE = "pipeline_v2_v4"

# In-memory cache for repeated chunks/prompts
_llm_cache = {}

def get_cache_key(prompt: str) -> str:
    return hashlib.md5((CACHE_NAMESPACE + prompt).encode('utf-8')).hexdigest()

def call_llm(messages: List[Dict[str, str]], retries: int = 2) -> str:
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY is not set!")
        return "[]"

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
            # Add response format for JSON if supported, or rely on prompt
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=90
            )
            if response.status_code != 200:
                logger.error(f"OpenRouter Error {response.status_code}: {response.text}")
                response.raise_for_status()
                
            try:
                data = response.json()
            except Exception as json_e:
                logger.error(f"Failed to parse OpenRouter JSON. Raw response: {response.text[:500]}")
                raise json_e

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
6. Perform QA: check logical order, detect noise, detect missing basics, detect advanced topics
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
        logger.error(f"Failed to parse strict JSON: {e}")
    
    return {"units": []}
