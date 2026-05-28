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

CACHE_NAMESPACE = "pipeline_v2_v6"

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
* PRESERVE ORIGINAL NAMES: Use the EXACT topic/lesson titles as written in the source text. Do NOT translate, rename, summarize, or genericize them. If the source says "Wie heißt du?" output "Wie heißt du?", NOT "Hellos and Goodbyes".

---

📦 TASK & QUALITY RESTRICTIONS (ABSOLUTE)
1. FILTER OUT METADATA & FRONT MATTER: Absolutely do NOT extract introductory chapters, preface, foreword, textbook level overviews (e.g., "Beginning German Level I", "Basic German Level II"), general instructions, "How to Study German Using This Textbook", "Layout of Lessons", "Pronunciation Guide", or descriptions of the student manual. Only extract actual curriculum topics for lessons.
2. GROUP MICRO-GRAMMAR & EXAMPLES: Do NOT extract raw syntax snippets, conjugation forms, or short sentence examples as individual topics (e.g., do NOT extract "er -t", "sie -t", "ich spiele", "was machst du?", "to conjugate", "ich mache Hausaufgaben", "er macht Hausaufgaben" as separate topics). Instead, group these conjugations and examples into their parent grammar or vocabulary topic (e.g., group them into a single comprehensive topic like "Verb Conjugation: spielen & machen" or "Present Tense Conjugations").
3. DEDUPLICATION & MERGING: Ensure no redundant, identical, or overlapping topics exist. For example, do not extract "Wie heißt du?" twice. Merge duplicates.
4. Detect structure: UNIT_HEADER, TOPIC, NOISE (discard).
5. Extract ONLY the units and topics physically present in the document.
6. Tag each topic: grammar, vocabulary, functional, phonetics, communication, mixed. You MUST assign the most specific tag to each topic based on its title and what it teaches:
   - 'grammar' -> if it covers grammar structures, cases, tenses, syntax (e.g., 'Das Fest' covering Dative case, or modals, separable verbs, conjugation).
   - 'vocabulary' -> if it focuses on thematic word lists, nouns, adjectives (e.g., 'Freizeit' covering sports, 'Essen' covering food, 'Kleidung' covering clothes, 'Das Haus' covering furniture, 'Schule' covering subjects).
   - 'phonetics' -> if it covers pronunciation, spelling, alphabets, or sounds.
   - 'communication' -> if it focuses on conversation, greetings, hellos/goodbyes, expressions, dialogues, or speaking practice (e.g., 'Wie heißt du?').
   - 'mixed' -> ONLY as a last resort if a topic has absolutely no dominant theme. Do NOT use 'mixed' if the topic clearly matches one of the other categories. For example, topics about 'Essen' (food), 'Schule' (school), 'Wetter' (weather), or 'Das Haus' (furniture/house) are strictly 'vocabulary'. Topics about 'Privileg und Verantwortung' (modal verbs, rules) are strictly 'grammar'. Avoid 'mixed' at all costs unless there is zero clear language focus!
    🚨 CRITICAL TAGGING RULE: You MUST evaluate and decide the 'tag' based on the FULL original lesson line (including numbering and description/details after the '~' or ':') BEFORE you remove the numbering and description to produce the final 'name'! For example:
    * "Lesson 1.03 • Essen ~ Introduction to food, food-related verbs, intro to modals & möchten..." -> Even though this has modals, verbs, and polite conversation, its primary thematic core is food, so the tag is strictly "vocabulary" (NOT "mixed"), even though the final name is "Essen".
    * "Lesson 1.09 • Schule ~ School subjects..." -> Description has "School subjects", so the tag is strictly "vocabulary", even though the final name is "Schule".
    * "Lesson 1.12 • Wetter ~ Weather vocabulary..." -> Description has "Weather", so the tag is strictly "vocabulary", even though the final name is "Wetter".
    * "Lesson 1.08 • Das Haus ~ Rooms, furniture..." -> Description has "furniture, rooms", so the tag is strictly "vocabulary", even though the final name is "Das Haus".
    * "Lesson 1.07 • Privileg und Verantwortung ~ Modal verbs, rules..." -> Description has "Modal verbs", so the tag is strictly "grammar", even though the final name is "Privileg und Verantwortung".
    NEVER default to "mixed" when the description or lesson focus clearly indicates vocabulary, grammar, phonetics, or communication!
7. Group them correctly into their respective units.

8. Perform QA: check logical order, detect noise. Do NOT invent missing basics (e.g. alphabet) or foundational units. Strictly stick to the text.
9. Auto-fix: remove garbage, fix wrong tags, mark unclear items as "needs_review".
10. SECTION/LESSON PATTERN: Many textbooks structure content as: a higher-level SECTION or CHAPTER header (e.g. "Section 1.01 ~ Starting Point", "Section 1.02 ~ Berlin, Germany", "Unit 3") which acts as the UNIT, and individual LESSONS or sub-chapters within it (e.g. "Lesson 1.01 • Wie heißt du?", "Lesson 1.02 • Freizeit") which act as the TOPICS. Always group lessons/sub-chapters as topics INSIDE their parent section/chapter unit. Do NOT promote individual lesson names to become unit titles.
11. REVIEW FILTER: Do NOT extract "Review" lessons, test sections, quizzes, or exam pages (e.g. "Review 1.01 • Review of Lessons 1-3"). These are noise. However, do NOT discard main unit/section titles or lessons that happen to contain city or country names (e.g., "Berlin, Germany", "Vienna, Austria", "Berne, Switzerland") — these are valid unit/section titles and must be preserved!
12. NO TOPIC SUBDIVISION (ABSOLUTE): Each lesson or chapter name is ONE topic. Do NOT split a lesson/chapter name (e.g., 'Lesson 1.01 • Wie heißt du?') into multiple sub-topics based on its descriptions, comma-separated details, or sub-points. Discard the '~ description text' when extracting the topic name, or keep it in the name as a whole, but NEVER split it into separate topics.
13. GERMAN TEXTBOOK TOC PATTERN (STRICT):
  * The document has exactly 4 sections acting as units:
    - Unit 1: Section 1.01 ~ Starting Point
    - Unit 2: Section 1.02 ~ Berlin, Germany
    - Unit 3: Section 1.03 ~ Vienna, Austria
    - Unit 4: Section 1.04 ~ Berne, Switzerland
  * You MUST create exactly 4 units corresponding to these 4 sections! Do NOT group everything under a single unit or use any other header as a unit.
  * Each section contains exactly 3 lessons acting as topics.
  * For each lesson, the topic name MUST be ONLY the lesson title itself, with the numbering (e.g. 'Lesson 1.01 •') and the description text after the '~' or ':' completely removed!
    - Example: For 'Lesson 1.01 • Wie heißt du? ~ Hellos/Goodbyes...' -> the topic name MUST be exactly 'Wie heißt du?'.
    - Example: For 'Lesson 1.02 • Freizeit ~ Sports and...' -> the topic name MUST be exactly 'Freizeit'.
    - Example: For 'Lesson 1.10 : Zu Hause Essen ~ Food...' -> the topic name MUST be exactly 'Zu Hause Essen'.




---

📤 OUTPUT FORMAT (STRICT)
{{
"units": [
{{
"unit": 1,
"title": "[Exact name of the first unit/chapter as written in the book/text]",
"topics": [
{{
"name": "[Topic/lesson name from book/text]",
"tag": "grammar | vocabulary | functional | phonetics | communication | mixed",
"confidence": 0.0
}}
]
}},
{{
"unit": 2,
"title": "[Exact name of the second unit/chapter as written in the book/text]",
"topics": [
{{
"name": "[Topic/lesson name from book/text]",
"tag": "vocabulary"
}}
]
}}
// Generate ALL units/chapters exactly as they appear in the text! DO NOT invent titles!
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
* PRESERVE ORIGINAL NAMES: Use the EXACT topic/lesson titles as written in the PDF. Do NOT translate, rename, summarize, or genericize them. If the PDF says "Wie heißt du?" output "Wie heißt du?", NOT "Hellos and Goodbyes". If it says "Freizeit" output "Freizeit", NOT "Sports and Activities".
* GERMAN ENCODING SAFETY: German PDFs often contain special characters like ß, ä, ö, ü. OCR engines sometimes misinterpret these as Arabic characters (e.g. 'ى' instead of 'ßt'). You MUST detect and CORRECT these back to valid German spelling based on context.

---

📦 TASK & QUALITY RESTRICTIONS (ABSOLUTE)
1. FILTER OUT METADATA & FRONT MATTER: Absolutely do NOT extract introductory chapters, preface, foreword, textbook level overviews (e.g., "Beginning German Level I", "Basic German Level II"), general instructions, "How to Study German Using This Textbook", "Layout of Lessons", "Pronunciation Guide", or descriptions of the student manual. Only extract actual curriculum topics for lessons.
2. GROUP MICRO-GRAMMAR & EXAMPLES: Do NOT extract raw syntax snippets, conjugation forms, or short sentence examples as individual topics (e.g., do NOT extract "er -t", "sie -t", "ich spiele", "was machst du?", "to conjugate", "ich mache Hausaufgaben", "er macht Hausaufgaben" as separate topics). Instead, group these conjugations and examples into their parent grammar or vocabulary topic (e.g., group them into a single comprehensive topic like "Verb Conjugation: spielen & machen" or "Present Tense Conjugations").
3. DEDUPLICATION & MERGING: Ensure no redundant, identical, or overlapping topics exist. For example, do not extract "Wie heißt du?" twice. Merge duplicates.
4. Read the PDF content, focusing specifically on the Table of Contents or chapter breakdowns.
5. Detect structure: UNIT_HEADER (e.g., Unit 1, Lektion 2, Chapter 3), TOPIC, NOISE (discard).
6. Extract ONLY the units and topics physically present in the document. Do NOT infer, predict, or add "future" levels.
7. Tag each topic: grammar, vocabulary, functional, phonetics, communication, mixed. You MUST assign the most specific tag to each topic based on its title and what it teaches:
   - 'grammar' -> if it covers grammar structures, cases, tenses, syntax (e.g., 'Das Fest' covering Dative case, or modals, separable verbs, conjugation).
   - 'vocabulary' -> if it focuses on thematic word lists, nouns, adjectives (e.g., 'Freizeit' covering sports, 'Essen' covering food, 'Kleidung' covering clothes, 'Das Haus' covering furniture, 'Schule' covering subjects).
   - 'phonetics' -> if it covers pronunciation, spelling, alphabets, or sounds.
   - 'communication' -> if it focuses on conversation, greetings, hellos/goodbyes, expressions, dialogues, or speaking practice (e.g., 'Wie heißt du?').
   - 'mixed' -> ONLY as a last resort if a topic has absolutely no dominant theme. Do NOT use 'mixed' if the topic clearly matches one of the other categories. For example, topics about 'Essen' (food), 'Schule' (school), 'Wetter' (weather), or 'Das Haus' (furniture/house) are strictly 'vocabulary'. Topics about 'Privileg und Verantwortung' (modal verbs, rules) are strictly 'grammar'. Avoid 'mixed' at all costs unless there is zero clear language focus!
   🚨 CRITICAL TAGGING RULE: You MUST evaluate and decide the 'tag' based on the FULL original lesson line (including numbering and description/details after the '~' or ':') BEFORE you remove the numbering and description to produce the final 'name'! For example:
   * "Lesson 1.03 • Essen ~ Introduction to food, food-related verbs, intro to modals & möchten..." -> Even though this has modals, verbs, and polite conversation, its primary thematic core is food, so the tag is strictly "vocabulary" (NOT "mixed" and NOT "communication"), even though the final name is "Essen".
   * "Lesson 1.09 • Schule ~ School subjects..." -> Description has "School subjects", so the tag is strictly "vocabulary", even though the final name is "Schule".
   * "Lesson 1.12 • Wetter ~ Weather vocabulary..." -> Description has "Weather", so the tag is strictly "vocabulary", even though the final name is "Wetter".
   * "Lesson 1.08 • Das Haus ~ Rooms, furniture..." -> Description has "furniture, rooms", so the tag is strictly "vocabulary", even though the final name is "Das Haus".
   * "Lesson 1.07 • Privileg und Verantwortung ~ Modal verbs, rules..." -> Description has "Modal verbs", so the tag is strictly "grammar", even though the final name is "Privileg und Verantwortung".
   NEVER default to "mixed" when the description or lesson focus clearly indicates vocabulary, grammar, phonetics, or communication!
8. Group them correctly into their respective units as shown in the book.

9. Perform QA: check logical order, detect noise. Do NOT invent missing basics (e.g. alphabet) or foundational units. Strictly stick to the PDF.
10. Auto-fix: remove garbage, fix wrong tags, mark unclear items as "needs_review".
11. STRICT NO-EMPTY-UNITS RULE: If a unit has no valid lessons/topics after noise removal, it MUST NOT be included in the JSON. Never output an empty "topics": [] array.
12. CULTURAL & REVIEW FILTER: Do NOT extract generic "Review" chapters, test sections, or exam pages (e.g. "Review 1.01 • Review of Lessons 1-3"). These are noise. However, do NOT discard main unit/section titles or lessons that happen to contain city or country names (e.g., "Berlin, Germany", "Vienna, Austria", "Berne, Switzerland") — these are valid unit/section titles and must be preserved!
13. SECTION/LESSON PATTERN: Many textbooks structure content as: a higher-level SECTION or CHAPTER header (e.g. "Section 1.01 ~ Starting Point", "Section 1.02 ~ Berlin, Germany", "Unit 3") which acts as the UNIT, and individual LESSONS or sub-chapters within it (e.g. "Lesson 1.01 • Wie heißt du?", "Lesson 1.02 • Freizeit") which act as the TOPICS. Always group lessons/sub-chapters as topics INSIDE their parent section/chapter unit. Do NOT promote individual lesson names to become unit titles.
14. NO TOPIC SUBDIVISION (ABSOLUTE): Each lesson or chapter name is ONE topic. Do NOT split a lesson/chapter name (e.g., 'Lesson 1.01 • Wie heißt du?') into multiple sub-topics based on its descriptions, comma-separated details, or sub-points. Discard the '~ description text' when extracting the topic name, or keep it in the name as a whole, but NEVER split it into separate topics.
15. GERMAN TEXTBOOK TOC PATTERN (STRICT):
  * The document has exactly 4 sections acting as units:
    - Unit 1: Section 1.01 ~ Starting Point
    - Unit 2: Section 1.02 ~ Berlin, Germany
    - Unit 3: Section 1.03 ~ Vienna, Austria
    - Unit 4: Section 1.04 ~ Berne, Switzerland
  * You MUST create exactly 4 units corresponding to these 4 sections! Do NOT group everything under a single unit or use any other header as a unit.
  * Each section contains exactly 3 lessons acting as topics.
  * For each lesson, the topic name MUST be ONLY the lesson title itself, with the numbering (e.g. 'Lesson 1.01 •') and the description text after the '~' or ':' completely removed!
    - Example: For 'Lesson 1.01 • Wie heißt du? ~ Hellos/Goodbyes...' -> the topic name MUST be exactly 'Wie heißt du?'.
    - Example: For 'Lesson 1.02 • Freizeit ~ Sports and...' -> the topic name MUST be exactly 'Freizeit'.
    - Example: For 'Lesson 1.10 : Zu Hause Essen ~ Food...' -> the topic name MUST be exactly 'Zu Hause Essen'.




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
