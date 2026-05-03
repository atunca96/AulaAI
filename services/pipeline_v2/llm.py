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
CHEAP_MODEL = "openai/gpt-4o-mini" # Switching default to GPT-4o Mini for better stability
FALLBACK_MODEL = "anthropic/claude-3-haiku"

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
                timeout=45
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

def detect_structure(chunk: List[str]) -> List[Dict[str, str]]:
    if not chunk:
        return []
        
    prompt = """Classify each line into exactly one of these types: UNIT_TITLE, SECTION_TITLE, TOPIC, NOISE.

IMPORTANT RULES:
1. UNIT_TITLE: Look for major pedagogical boundaries or numbered headers. 
   - These are often numbered (1, 2, 3...) or prefixed with terms like Unit, Lektion, Unidad, Tema, Chapter, Module, etc.
   - SEMANTIC FILTER: Ignore book titles, marketing blurbs, prefaces, or "About the Author" sections.
2. TOPIC: Actual lessons, themes, or learning objectives. 
3. NOISE: Page numbers, copyrights, marketing text, prefaces, and non-pedagogical introductory text.
4. AGNOSTIC: Handle all 14 languages (Spanish, German, Russian, Chinese, etc.) with equal priority.
5. Return purely a JSON array of objects: [{"text": "...", "type": "UNIT_TITLE"}]
5. Remove NOISE lines entirely.

Lines to classify:
""" + "\n".join(chunk)

    messages = [{"role": "user", "content": prompt}]
    logger.info("LLM: structure detection")
    result_text = call_llm(messages)
    try:
        data = json.loads(result_text)
        if isinstance(data, dict) and "lines" in data:
            data = data["lines"]
        elif isinstance(data, dict) and "output" in data:
            data = data["output"]
            
        if isinstance(data, list):
            return [item for item in data if item.get("type") != "NOISE"]
    except Exception as e:
        logger.error(f"Failed to parse structure JSON: {e}")
    return []

def tag_topics(topics: List[str]) -> List[Dict[str, str]]:
    if not topics:
        return []
        
    prompt = """Classify each topic into exactly one of these tags: grammar, vocabulary, communicative.
grammar: rules, structures, conjugations.
vocabulary: lexical items, themes.
communicative: functions (asking, describing, interacting).
Return purely a JSON array of objects.
The output must be valid JSON like: [{"text": "...", "tag": "grammar"}]
Topics to classify:
""" + "\n".join(topics)

    messages = [{"role": "user", "content": prompt}]
    logger.info("LLM: semantic tagging")
    result_text = call_llm(messages)
    try:
        data = json.loads(result_text)
        if isinstance(data, dict) and "topics" in data:
            data = data["topics"]
        elif isinstance(data, dict) and "output" in data:
            data = data["output"]
            
        if isinstance(data, list):
            return data
    except Exception as e:
        logger.error(f"Failed to parse tags JSON: {e}")
    return []
