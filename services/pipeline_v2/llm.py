import os
import json
import hashlib
import requests
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "your_openrouter_api_key")
CHEAP_MODEL = "anthropic/claude-3-haiku"
FALLBACK_MODEL = "anthropic/claude-3-sonnet"

CACHE_NAMESPACE = "pipeline_v2_v3"

# In-memory cache for repeated chunks/prompts
_llm_cache = {}

def get_cache_key(prompt: str) -> str:
    return hashlib.md5((CACHE_NAMESPACE + prompt).encode('utf-8')).hexdigest()

def call_llm(messages: List[Dict[str, str]], retries: int = 2) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
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
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]
            
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
1. UNIT_TITLE detection: Even if the word 'Unit' or 'Chapter' is missing, look for major headers or repeating patterns that signal a new unit (e.g. if a list repeats 'Communication' then 'Grammar' every few lines, the line before that repetition might be a new unit).
2. TOPIC: These are the actual lessons or themes.
3. Return purely a JSON array of objects: [{"text": "...", "type": "TOPIC"}]
4. Remove NOISE lines entirely.
5. Be language-agnostic.

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
