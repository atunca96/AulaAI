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

CACHE_NAMESPACE = "pipeline_v2_v10"

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
                "max_tokens": 16000,
                "messages": messages
            }
            
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=90) as response:
                res_body = response.read().decode("utf-8")
                data = json.loads(res_body)

            if "choices" not in data:
                logger.error(f"OpenRouter API Error: {res_body}")
                raise ValueError(f"No choices in OpenRouter response: {data.get('error', {}).get('message', 'Unknown Error')}")

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

            if "choices" not in data:
                logger.error(f"OpenRouter API PDF Error: {res_body}")
                raise ValueError(f"No choices in OpenRouter PDF response: {data.get('error', {}).get('message', 'Unknown Error')}")

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

Your ONLY task is to transform input text into valid JSON representing the curriculum structure.

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

🧠 BEHAVIOR & EXTRACTION RULES
1. FILTER OUT METADATA, BOOK STRUCTURE GUIDES & INTRODUCTIONS: Absolutely do NOT extract introductory chapters, preface, foreword, textbook level overviews, general instructions, or guide pages explaining how the book or units are organized (e.g. "Así son las unidades", "Para entender el manual", "Layout of Lessons", "Pronunciation Guide", "How to use this manual"). Ignore these guide pages, their section titles, and any example items shown on them. Only extract actual curriculum topics for lessons from the real body chapters or Table of Contents.
2. GROUP MICRO-GRAMMAR & EXAMPLES: Do NOT extract raw syntax snippets, conjugation forms, or short sentence examples as individual topics. Group them into their parent grammar or vocabulary topic (e.g. group "er -t", "sie -t" into "Present Tense Conjugations").
3. DEDUPLICATION & MERGING: Ensure no redundant, identical, or overlapping topics exist. Merge duplicates.
4. Detect structure: UNIT_HEADER, TOPIC, NOISE (discard).
5. Extract ONLY the units and topics physically present in the document.
6. Tag each topic: grammar, vocabulary, functional, phonetics, communication, mixed. Assign the most specific tag.
7. Group topics correctly into their respective units.
8. TOPIC NAME CLEANING & NO SUB-DETAILS: When extracting a topic name, discard description text after separators like '~', ':', or similar details that are just a sentence explaining what the topic is. Keep the core name of the topic. However, do NOT confuse sub-details with lists of distinct lesson subjects. If a line or section lists multiple distinct language subjects/lessons (e.g., separated by '•', ',', ';', or newlines), you MUST split and extract each item in that list as a separate individual topic.
9. EXTRACT BULLETED/LISTED TOPICS UNDER CATEGORY HEADERS: Do NOT extract generic structural labels or grouping headers (e.g., 'RECURSOS COMUNICATIVOS', 'RECURSOS GRAMATICALES', 'RECURSOS LÉXICOS', 'FONÉTICA', 'Grammar', 'Vocabulary', 'Skills', 'Exercises', 'Pronunciation', 'Communication', 'Léxico') as topic names. Instead, you MUST extract the actual, specific topics listed under or next to these headers. If there are multiple items listed (e.g., separated by dots '•', commas ',', semicolons ';', or newlines), each item is a separate topic and must be extracted individually.
10. IGNORE UNIT GOALS / SUMMARY SENTENCES: Many units have a high-level subtitle or summary sentence explaining the goal of the unit (e.g., 'APRENDER A PRESENTARNOS...', 'CONOCER LOS HÁBITOS...', 'CONOCER MEJOR A LAS OTRAS PERSONAS...', 'IMAGINAR Y DESCRIBIR UN BARRIO IDEAL'). Do NOT extract these summary sentences as topics. Skip them. Instead, extract the actual specific lessons/topics (vocabulary, grammar, communication, phonetics) listed underneath them.

---

📖 FEW-SHOT EXAMPLES (MATERIAL-AGNOSTIC)

Example 1: Book guide page (Should be skipped)
Input:
---
ASÍ SON LAS UNIDADES DE ESTE MANUAL
• Empezar: En esta primera doble página de la unidad...
Example Lesson:
1. CIUDADES QUE SE LLAMAN SANTIAGO
• Comprender: En esta doble página encontramos textos...
---
Output:
{{
  "units": []
}}

Example 2: Real Curriculum Unit with Goal and Category headers
Input:
---
PÁG. 12
UNIT 1: AT THE CAFE
GOAL: ORDERING FOOD AND DRINKS AND TALKING TO THE WAITER
COMMUNICATIVE RESOURCES
order a coffee • ask for the menu • pay the bill
GRAMMATICAL RESOURCES
present tense of verbs like to want and to like • singular and plural nouns
LEXICAL RESOURCES
food and drinks • numbers 1-20
PRONUNCIATION
word stress
---
Output:
{{
  "units": [
    {{
      "unit": 1,
      "title": "AT THE CAFE",
      "topics": [
        {{
          "name": "order a coffee",
          "tag": "communication"
        }},
        {{
          "name": "ask for the menu",
          "tag": "communication"
        }},
        {{
          "name": "pay the bill",
          "tag": "communication"
        }},
        {{
          "name": "present tense of verbs like to want and to like",
          "tag": "grammar"
        }},
        {{
          "name": "singular and plural nouns",
          "tag": "grammar"
        }},
        {{
          "name": "food and drinks",
          "tag": "vocabulary"
        }},
        {{
          "name": "numbers 1-20",
          "tag": "vocabulary"
        }},
        {{
          "name": "word stress",
          "tag": "phonetics"
        }}
      ]
    }}
  ]
}}

Example 3: Real Curriculum Unit with simple bullet list and no category headers
Input:
---
PÁG. 10
0/ EN EL AULA
APRENDER A PRESENTARNOS, A PREGUNTAR COSAS EN CLASE Y A SALUDAR Y DESPEDIRNOS
saludos y despedidas • las cosas de la clase • los números del 1 al 10 • el abecedario • recursos para desenvolverse en la clase de español
FONÉTICA
entonación de preguntas parciales y su respuesta
---
Output:
{{
  "units": [
    {{
      "unit": 1,
      "title": "EN EL AULA",
      "topics": [
        {{
          "name": "saludos y despedidas",
          "tag": "communication"
        }},
        {{
          "name": "las cosas de la clase",
          "tag": "vocabulary"
        }},
        {{
          "name": "los números del 1 al 10",
          "tag": "vocabulary"
        }},
        {{
          "name": "el abecedario",
          "tag": "phonetics"
        }},
        {{
          "name": "recursos para desenvolverse en la clase de español",
          "tag": "communication"
        }},
        {{
          "name": "entonación de preguntas parciales y su respuesta",
          "tag": "phonetics"
        }}
      ]
    }}
  ]
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

🧠 BEHAVIOR & EXTRACTION RULES
1. FILTER OUT METADATA, BOOK STRUCTURE GUIDES & INTRODUCTIONS: Absolutely do NOT extract introductory chapters, preface, foreword, textbook level overviews, general instructions, or guide pages explaining how the book or units are organized (e.g. "Así son las unidades", "Para entender el manual", "Layout of Lessons", "Pronunciation Guide", "How to use this manual"). Ignore these guide pages, their section titles, and any example items shown on them. Only extract actual curriculum topics for lessons from the real body chapters or Table of Contents.
2. GROUP MICRO-GRAMMAR & EXAMPLES: Do NOT extract raw syntax snippets, conjugation forms, or short sentence examples as individual topics. Group them into their parent grammar or vocabulary topic.
3. DEDUPLICATION & MERGING: Ensure no redundant, identical, or overlapping topics exist. Merge duplicates.
4. Read the PDF content, focusing specifically on the Table of Contents or chapter breakdowns.
5. Detect structure: UNIT_HEADER (e.g. Unit 1, Lektion 2, Chapter 3), TOPIC, NOISE (discard).
6. Extract ONLY the units and topics physically present in the document. Do NOT infer, predict, or add "future" levels.
7. Tag each topic: grammar, vocabulary, functional, phonetics, communication, mixed. Assign the most specific tag.
8. Group topics correctly into their respective units as shown in the book.
9. TOPIC NAME CLEANING & NO SUB-DETAILS: When extracting a topic name, discard description text after separators like '~', ':', or similar details that are just a sentence explaining what the topic is. Keep the core name of the topic. However, do NOT confuse sub-details with lists of distinct lesson subjects. If a line or section lists multiple distinct language subjects/lessons (e.g., separated by '•', ',', ';', or newlines), you MUST split and extract each item in that list as a separate individual topic.
10. EXTRACT BULLETED/LISTED TOPICS UNDER CATEGORY HEADERS: Do NOT extract generic structural labels or grouping headers (e.g., 'RECURSOS COMUNICATIVOS', 'RECURSOS GRAMATICALES', 'RECURSOS LÉXICOS', 'FONÉTICA', 'Grammar', 'Vocabulary', 'Skills', 'Exercises', 'Pronunciation', 'Communication', 'Léxico') as topic names. Instead, you MUST extract the actual, specific topics listed under or next to these headers. If there are multiple items listed (e.g., separated by dots '•', commas ',', semicolons ';', or newlines), each item is a separate topic and must be extracted individually.
11. IGNORE UNIT GOALS / SUMMARY SENTENCES: Many units have a high-level subtitle or summary sentence explaining the goal of the unit (e.g., 'APRENDER A PRESENTARNOS...', 'CONOCER LOS HÁBITOS...', 'CONOCER MEJOR A LAS OTRAS PERSONAS...', 'IMAGINAR Y DESCRIBIR UN BARRIO IDEAL'). Do NOT extract these summary sentences as topics. Skip them. Instead, extract the actual specific lessons/topics (vocabulary, grammar, communication, phonetics) listed underneath them.
12. GERMAN ENCODING SAFETY: German PDFs often contain special characters like ß, ä, ö, ü. OCR engines sometimes misinterpret these as Arabic characters (e.g. 'ы' instead of 'ßt'). You MUST detect and CORRECT these back to valid German spelling based on context.
13. STRICT NO-EMPTY-UNITS RULE: If a unit has no valid lessons/topics after noise removal, it MUST NOT be included in the JSON. Never output an empty "topics": [] array.
14. CULTURAL & REVIEW FILTER: Do NOT extract generic "Review" chapters, test sections, or exam pages. These are noise. However, do NOT discard main unit/section titles or lessons that happen to contain city or country names — these are valid unit/section titles and must be preserved!
15. UNIVERSAL TEXTBOOK PATTERN (STRICT): The number of units and topics MUST match EXACTLY what is physically present in the PDF. Do NOT assume any fixed number of units or topics. Do NOT import, hallucinate, or copy unit titles or topic names from any other document or your training data. ONLY use what you can directly read in the attached PDF!

---

📖 FEW-SHOT EXAMPLES (MATERIAL-AGNOSTIC)

Example 1: Book guide page (Should be skipped)
Input:
---
ASÍ SON LAS UNIDADES DE ESTE MANUAL
• Empezar: En esta primera doble página de la unidad...
Example Lesson:
1. CIUDADES QUE SE LLAMAN SANTIAGO
• Comprender: En esta doble página encontramos textos...
---
Output:
{
  "units": []
}

Example 2: Real Curriculum Unit with Goal and Category headers
Input:
---
PÁG. 12
UNIT 1: AT THE CAFE
GOAL: ORDERING FOOD AND DRINKS AND TALKING TO THE WAITER
COMMUNICATIVE RESOURCES
order a coffee • ask for the menu • pay the bill
GRAMMATICAL RESOURCES
present tense of verbs like to want and to like • singular and plural nouns
LEXICAL RESOURCES
food and drinks • numbers 1-20
PRONUNCIATION
word stress
---
Output:
{
  "units": [
    {
      "unit": 1,
      "title": "AT THE CAFE",
      "topics": [
        {
          "name": "order a coffee",
          "tag": "communication"
        },
        {
          "name": "ask for the menu",
          "tag": "communication"
        },
        {
          "name": "pay the bill",
          "tag": "communication"
        },
        {
          "name": "present tense of verbs like to want and to like",
          "tag": "grammar"
        },
        {
          "name": "singular and plural nouns",
          "tag": "grammar"
        },
        {
          "name": "food and drinks",
          "tag": "vocabulary"
        },
        {
          "name": "numbers 1-20",
          "tag": "vocabulary"
        },
        {
          "name": "word stress",
          "tag": "phonetics"
        }
      ]
    }
  ]
}

Example 3: Real Curriculum Unit with simple bullet list and no category headers
Input:
---
PÁG. 10
0/ EN EL AULA
APRENDER A PRESENTARNOS, A PREGUNTAR COSAS EN CLASE Y A SALUDAR Y DESPEDIRNOS
saludos y despedidas • las cosas de la clase • los números del 1 al 10 • el abecedario • recursos para desenvolverse en la clase de español
FONÉTICA
entonación de preguntas parciales y su respuesta
---
Output:
{
  "units": [
    {
      "unit": 1,
      "title": "EN EL AULA",
      "topics": [
        {
          "name": "saludos y despedidas",
          "tag": "communication"
        },
        {
          "name": "las cosas de la clase",
          "tag": "vocabulary"
        },
        {
          "name": "los números del 1 al 10",
          "tag": "vocabulary"
        },
        {
          "name": "el abecedario",
          "tag": "phonetics"
        },
        {
          "name": "recursos para desenvolverse en la clase de español",
          "tag": "communication"
        },
        {
          "name": "entonación de preguntas parciales y su respuesta",
          "tag": "phonetics"
        }
      ]
    }
  ]
}

---

OUTPUT FORMAT (STRICT)
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
}
]
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
4. PRESERVE ORIGINAL NAMES: Do NOT translate, rename, summarize, or genericize topic titles. Keep the EXACT original names from the input. Only fix obvious OCR errors. Tag each as grammar, vocabulary, functional, phonetics, communication, or mixed.
5. PRESERVE UNIT STRUCTURE: Do NOT merge, split, rebalance, or remove units. Keep the EXACT same number of units as the input. A unit with only 2-3 topics is fine — do NOT merge it into another unit.
6. PRUNING EMPTY UNITS: If a unit has NO valid topics, it MUST be removed. A "Unit" with zero lessons is useless.
7. CULTURAL & REVIEW FILTER: Do NOT extract generic "Review" chapters, test sections, or exam pages. Only extract actionable language lessons (grammar, vocabulary, conversation). Skip anything that says "Review", "Test", or "Exam". However, do NOT discard main unit/section titles or lessons that happen to contain city or country names (e.g., "Berlin, Germany", "Vienna, Austria", "Berne, Switzerland") — these are valid unit/section titles and must be preserved!
8. NO HALLUCINATIONS: Do NOT add units that were not in the input. If the input ends at Level 3, the output MUST end at Level 3.
9. FINAL CLEANUP: No duplicate topics anywhere. No empty units. No hallucinated levels.
10. NO TOPIC SUBDIVISION (ABSOLUTE): Each lesson or chapter name is ONE topic. Do NOT split a lesson/chapter name into multiple sub-topics based on its descriptions, comma-separated details, or sub-points. Keep only the main lesson/chapter title as a single, complete topic name.


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
            cleaned_units = []
            for u in data["units"]:
                # Python-level Safety Filter: Prune units with 0 valid topics
                topics = u.get("topics", [])
                if not topics or not isinstance(topics, list) or len(topics) == 0:
                    logger.warning(f"Pruning empty unit during normalization: {u.get('title', 'Untitled')}")
                    continue
                
                if "unit" in u and "title" not in u:
                    u["title"] = f"Unit {u['unit']}"
                
                for t in topics:
                    if isinstance(t, dict) and "name" in t:
                        name = t["name"]
                        # Post-processing fix for common German OCR/Mojibake errors
                        # Specifically fixing the 'ى' (Arabic) instead of 'ß' or 'ßt' issue
                        if "ى" in name:
                            logger.info(f"Fixing possible German OCR corruption in: {name}")
                            name = name.replace("hei ى t", "heißt")
                            name = name.replace("hei ىt", "heißt")
                            name = name.replace("hei ى", "heißt")
                            name = name.replace(" ى ", " ß ")
                            name = name.replace("ى", "ß")         # general case
                        t["text"] = name
                
                cleaned_units.append(u)
            data["units"] = cleaned_units
        return data
    except Exception as e:
        logger.error(f"Normalization failed, returning original data: {e}")
        return curriculum_data
