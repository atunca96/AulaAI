import os
import json
import hashlib
import base64
import urllib.request
import urllib.error
import logging
import time
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
CHEAP_MODEL = os.getenv("CHEAP_MODEL", "meta-llama/llama-3.3-70b-instruct")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "meta-llama/llama-3.3-70b-instruct")

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
            sleep_time = 3 * (attempt + 1)
            logger.info(f"Sleeping {sleep_time}s before retrying due to error: {e}")
            time.sleep(sleep_time)
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

🚨 CRITICAL RULES (ABSOLUTE)
* You MUST return ONLY valid JSON
* NO explanations, NO markdown block wrappers (do NOT wrap in ```json or ```), NO text before or after the JSON.
* If you are unsure → still return valid JSON

---

🧠 BEHAVIOR & EXTRACTION RULES
1. IGNORE GENERAL GUIDE / TEMPLATE PAGES:
   Many textbooks contain introductory pages explaining "How to use this manual", "Structure of the units", or "Layout of lessons". These pages explain general unit sections (such as "Empezar", "Comprender", "Explorar y reflexionar", "Practicar y comunicar", "Video", "Más ejercicios", "Más gramática") with long descriptive paragraphs of text. You MUST completely ignore and filter out these guide pages, their section titles, and any example items shown on them.
2. IDENTIFY ACTUAL CURRICULUM UNITS:
   The real Table of Contents (TOC) is a concise list of chapters or units.
   Each actual curriculum unit/chapter is characterized by:
   - A unit/chapter number (e.g. 0, 1, 2, 3, 4, 5, 6, 7, 8, 9... or OCR variants like O/, 1/, 2/, 3/, 4/, 5/, 6/, 7/, 8/, 9/).
   - A unit title (e.g., "EN EL AULA", "NOSOTROS Y NOSOTRAS", "QUIERO APRENDER ESPAÑOL", "¿DÓNDE ESTÁ SANTIAGO?", etc.). If the title is split across consecutive lines in the raw text, you must combine them.
   🚨 CRITICAL FILTER: Supplementary chapters, workbook practice sections, or review sections (such as "MÁS EJERCICIOS", "MÁS GRAMÁTICA", "EJERCICIOS", "GRAMÁTICA", "INDEX", "BIBLIOGRAPHY", "GLOSARIO") are NOT teaching units. You MUST completely skip and ignore them.
3. IGNORE UNIT GOALS / SUMMARY SENTENCES:
   Under the unit title, there is often a high-level goal or summary sentence explaining what the student will learn (e.g., "APRENDER A PRESENTARNOS...", "CONOCER LOS HÁBITOS...", "CONOCER MEJOR A LAS OTRAS PERSONAS...", "IMAGINAR Y DESCRIBIR..."). Do NOT extract these summary sentences/goals as topic names. Skip them.
4. EXTRACT LESSON TOPICS UNDER CATEGORIES:
   Extract the actual, specific lesson topics listed under each unit. These are often grouped under category headers (e.g., "RECURSOS COMUNICATIVOS", "RECURSOS GRAMATICALES", "RECURSOS LÉXICOS", "FONÉTICA" or equivalent terms in other languages).
   - Do NOT extract the generic category headers/labels themselves as topics.
   - If a line lists multiple distinct lessons/subjects (e.g., separated by dots '•', commas ',', semicolons ';', or newlines), you MUST split them and extract each item as a separate individual topic.
5. HANDLE MULTI-COLUMN INTERLEAVING & SEQUENCING:
   Because Table of Contents pages are often formatted in multiple columns, the extracted raw text lines can be interleaved (e.g. reading across columns, placing Unit 0 topics followed by Unit 6 topics, then Unit 1, then Unit 7...).
   You MUST:
   - Group all extracted topics under their correct unit number.
   - De-scramble the mixed lines. Use your linguistic and academic domain knowledge of the textbook's language curriculum to correctly associate each topic with its actual logical unit (e.g., "el género en nacionalidades y profesiones" belongs to Unit 1 "NOSOTROS Y NOSOTRAS", not Unit 2 "QUIERO APRENDER ESPAÑOL").
   - SORT the final units list in ascending numerical order by their unit number (e.g., Unit 0, Unit 1, Unit 2, Unit 3, Unit 4, Unit 5, Unit 6, Unit 7, Unit 8, Unit 9).
   - Ensure NO units are skipped. You must extract all units present in the real Table of Contents.
6. TAGGING TOPICS:
   Tag each topic as one of: grammar, vocabulary, functional, phonetics, communication, mixed. Assign the most specific tag.
7. RECONSTRUCT CORRUPTED CHARACTERS & ACCENTS:
   Text extraction or OCR can produce corrupted letters, spelling, or Unicode replacement characters (like the black diamond question mark symbol \uFFFD or similar glyphs, or 'nmeros' instead of 'números'). You MUST reconstruct and correct these back to clean, valid spelling and proper punctuation in the target language (e.g. reconstruct "n\uFFFDmeros" or "nmeros" to "números", "espa\uFFFDol" or "espaol" to "español", "entonaci\uFFFDn" or "entonacin" to "entonación", "\uFFFDd\uFFFDnde est\uFFFD santiago?" or "DNDE EST SANTIAGO?" to "¿DÓNDE ESTÁ SANTIAGO?"). Never output raw \uFFFD or corrupt letters.

---

📖 FEW-SHOT EXAMPLES (MATERIAL-AGNOSTIC)

Example 1: Book guide page (Should be skipped)
Input:
---
ASÍ SON LAS UNIDADES DE AULA INTERNACIONAL PLUS
EMPEZAR
En esta primera doble página de la unidad, se explica qué tarea vamos a realizar al final de la unidad...
1. CIUDADES QUE SE LLAMAN SANTIAGO
COMPRENDER
En esta doble página encontramos textos y documentos muy variados...
2. TRES CIUDADES CON EL MISMO NOMBRE
---
Output:
{{
  "units": []
}}

Example 2: Real Curriculum Table of Contents with multi-column interleaved text
Input:
---
PÁG.10
0/
EN EL AULA
APRENDER A PRESENTARNOS, A PREGUNTAR COSAS EN CLASE Y A SALUDAR Y DESPEDIRNOS
saludos y despedidas • las cosas de la clase
• los números del 1 al 10 • el abecedario
FONÉTICA
entonación de preguntas parciales

PÁG.84
6/
DÍA A DÍA
CONOCER LOS HÁBITOS DE LAS PERSONAS DE LA CLASE Y DAR PREMIOS
RECURSOS COMUNICATIVOS
hablar de hábitos • expresar frecuencia
RECURSOS GRAMATICALES
el presente de indicativo de algunos verbos irregulares • los verbos pronominales

PÁG.14
1/
NOSOTROS Y
NOSOTRAS
CONOCER MEJOR A LAS OTRAS PERSONAS DE LA CLASE
RECURSOS COMUNICATIVOS
dar y pedir datos personales • saludar y despedirse
---
Output:
{{
  "units": [
    {{
      "unit": 0,
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
          "tag": "vocabulary"
        }},
        {{
          "name": "entonación de preguntas parciales",
          "tag": "phonetics"
        }}
      ]
    }},
    {{
      "unit": 1,
      "title": "NOSOTROS Y NOSOTRAS",
      "topics": [
        {{
          "name": "dar y pedir datos personales",
          "tag": "communication"
        }},
        {{
          "name": "saludar y despedirse",
          "tag": "communication"
        }}
      ]
    }},
    {{
      "unit": 6,
      "title": "DÍA A DÍA",
      "topics": [
        {{
          "name": "hablar de hábitos",
          "tag": "communication"
        }},
        {{
          "name": "expresar frecuencia",
          "tag": "communication"
        }},
        {{
          "name": "el presente de indicativo de algunos verbos irregulares",
          "tag": "grammar"
        }},
        {{
          "name": "los verbos pronominales",
          "tag": "grammar"
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
        
        # Post-process to fix unicode spelling corruption
        data = clean_curriculum_spelling(data)
        return data
    except Exception as e:
        logger.error(f"Failed to parse strict JSON: {e}")
    
    return {"units": []}

def extract_curriculum_from_pdf_direct(pdf_path: str) -> Dict[str, Any]:
    prompt = """You are a strict JSON generator.

Your ONLY task is to transform the attached PDF document into a structured curriculum in valid JSON format.

🚨 CRITICAL RULES (ABSOLUTE)
* You MUST return ONLY valid JSON
* NO explanations, NO markdown block wrappers (do NOT wrap in ```json or ```), NO text before or after the JSON.
* If you are unsure → still return valid JSON

---

🧠 BEHAVIOR & EXTRACTION RULES
1. IGNORE GENERAL GUIDE / TEMPLATE PAGES:
   Many textbooks contain introductory pages explaining "How to use this manual", "Structure of the units", or "Layout of lessons". These pages explain general unit sections (such as "Empezar", "Comprender", "Explorar y reflexionar", "Practicar y comunicar", "Video", "Más ejercicios", "Más gramática") with long descriptive paragraphs of text. You MUST completely ignore and filter out these guide pages, their section titles, and any example items shown on them.
2. IDENTIFY ACTUAL CURRICULUM UNITS:
   The real Table of Contents (TOC) is a concise list of chapters or units.
   Each actual curriculum unit/chapter is characterized by:
   - A unit/chapter number (e.g. 0, 1, 2, 3, 4, 5, 6, 7, 8, 9... or OCR variants like O/, 1/, 2/, 3/, 4/, 5/, 6/, 7/, 8/, 9/).
   - A unit title (e.g., "EN EL AULA", "NOSOTROS Y NOSOTRAS", "QUIERO APRENDER ESPAÑOL", "¿DÓNDE ESTÁ SANTIAGO?", etc.). If the title is split across consecutive lines in the raw text, you must combine them.
   🚨 CRITICAL FILTER: Supplementary chapters, workbook practice sections, or review sections (such as "MÁS EJERCICIOS", "MÁS GRAMÁTICA", "EJERCICIOS", "GRAMÁTICA", "INDEX", "BIBLIOGRAPHY", "GLOSARIO") are NOT teaching units. You MUST completely skip and ignore them.
3. IGNORE UNIT GOALS / SUMMARY SENTENCES:
   Under the unit title, there is often a high-level goal or summary sentence explaining what the student will learn (e.g., "APRENDER A PRESENTARNOS...", "CONOCER LOS HÁBITOS...", "CONOCER MEJOR A LAS OTRAS PERSONAS...", "IMAGINAR Y DESCRIBIR..."). Do NOT extract these summary sentences/goals as topic names. Skip them.
4. EXTRACT LESSON TOPICS UNDER CATEGORIES:
   Extract the actual, specific lesson topics listed under each unit. These are often grouped under category headers (e.g., "RECURSOS COMUNICATIVOS", "RECURSOS GRAMATICALES", "RECURSOS LÉXICOS", "FONÉTICA" or equivalent terms in other languages).
   - Do NOT extract the generic category headers/labels themselves as topics.
   - If a line lists multiple distinct lessons/subjects (e.g., separated by dots '•', commas ',', semicolons ';', or newlines), you MUST split them and extract each item as a separate individual topic.
5. HANDLE MULTI-COLUMN INTERLEAVING & SEQUENCING:
   Because Table of Contents pages are often formatted in multiple columns, the extracted raw text lines can be interleaved (e.g. reading across columns, placing Unit 0 topics followed by Unit 6 topics, then Unit 1, then Unit 7...).
   You MUST:
   - Group all extracted topics under their correct unit number.
   - De-scramble the mixed lines. Use your linguistic and academic domain knowledge of the textbook's language curriculum to correctly associate each topic with its actual logical unit (e.g., "el género en nacionalidades y profesiones" belongs to Unit 1 "NOSOTROS Y NOSOTRAS", not Unit 2 "QUIERO APRENDER ESPAÑOL").
   - SORT the final units list in ascending numerical order by their unit number (e.g., Unit 0, Unit 1, Unit 2, Unit 3, Unit 4, Unit 5, Unit 6, Unit 7, Unit 8, Unit 9).
   - Ensure NO units are skipped. You must extract all units present in the real Table of Contents.
6. TAGGING TOPICS:
   Tag each topic as one of: grammar, vocabulary, functional, phonetics, communication, mixed. Assign the most specific tag.
7. RECONSTRUCT CORRUPTED CHARACTERS & ACCENTS:
   Text extraction or OCR can produce corrupted letters, spelling, or Unicode replacement characters (like the black diamond question mark symbol \uFFFD or similar glyphs, or 'nmeros' instead of 'números'). You MUST reconstruct and correct these back to clean, valid spelling and proper punctuation in the target language (e.g. reconstruct "n\uFFFDmeros" or "nmeros" to "números", "espa\uFFFDol" or "espaol" to "español", "entonaci\uFFFDn" or "entonacin" to "entonación", "\uFFFDd\uFFFDnde est\uFFFD santiago?" or "DNDE EST SANTIAGO?" to "¿DÓNDE ESTÁ SANTIAGO?"). Never output raw \uFFFD or corrupt letters.
8. STRICT NO-EMPTY-UNITS RULE:
   If a unit has no valid lessons/topics after noise removal, it MUST NOT be included in the JSON. Never output an empty "topics": [] array.
9. CULTURAL & REVIEW FILTER:
   Do NOT extract generic "Review" chapters, test sections, or exam pages. These are noise. However, do NOT discard main unit/section titles or lessons that happen to contain city or country names — these are valid unit/section titles and must be preserved!
10. UNIVERSAL TEXTBOOK PATTERN (STRICT):
    The number of units and topics MUST match EXACTLY what is physically present in the PDF. Do NOT assume any fixed number of units or topics. Do NOT import, hallucinate, or copy unit titles or topic names from any other document or your training data. ONLY use what you can directly read in the attached PDF!

---

📖 FEW-SHOT EXAMPLES (MATERIAL-AGNOSTIC)

Example 1: Book guide page (Should be skipped)
Input:
---
ASÍ SON LAS UNIDADES DE AULA INTERNACIONAL PLUS
EMPEZAR
En esta primera doble página de la unidad, se explica qué tarea vamos a realizar al final de la unidad...
1. CIUDADES QUE SE LLAMAN SANTIAGO
COMPRENDER
En esta doble página encontramos textos y documentos muy variados...
2. TRES CIUDADES CON EL MISMO NOMBRE
---
Output:
{{
  "units": []
}}

Example 2: Real Curriculum Table of Contents with multi-column interleaved text
Input:
---
PÁG.10
0/
EN EL AULA
APRENDER A PRESENTARNOS, A PREGUNTAR COSAS EN CLASE Y A SALUDAR Y DESPEDIRNOS
saludos y despedidas • las cosas de la clase
• los números del 1 al 10 • el abecedario
FONÉTICA
entonación de preguntas parciales

PÁG.84
6/
DÍA A DÍA
CONOCER LOS HÁBITOS DE LAS PERSONAS DE LA CLASE Y DAR PREMIOS
RECURSOS COMUNICATIVOS
hablar de hábitos • expresar frequency
RECURSOS GRAMATICALES
el presente de indicativo de algunos verbos irregulares • los verbos pronominales

PÁG.14
1/
NOSOTROS Y
NOSOTRAS
CONOCER MEJOR A LAS OTRAS PERSONAS DE LA CLASE
RECURSOS COMUNICATIVOS
dar y pedir datos personales • saludar y despedirse
---
Output:
{{
  "units": [
    {{
      "unit": 0,
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
          "tag": "vocabulary"
        }},
        {{
          "name": "entonación de preguntas parciales",
          "tag": "phonetics"
        }}
      ]
    }},
    {{
      "unit": 1,
      "title": "NOSOTROS Y NOSOTRAS",
      "topics": [
        {{
          "name": "dar y pedir datos personales",
          "tag": "communication"
        }},
        {{
          "name": "saludar y despedirse",
          "tag": "communication"
        }}
      ]
    }},
    {{
      "unit": 6,
      "title": "DÍA A DÍA",
      "topics": [
        {{
          "name": "hablar de hábitos",
          "tag": "communication"
        }},
        {{
          "name": "expresar frecuencia",
          "tag": "communication"
        }},
        {{
          "name": "el presente de indicativo de algunos verbos irregulares",
          "tag": "grammar"
        }},
        {{
          "name": "los verbos pronominales",
          "tag": "grammar"
        }}
      ]
    }}
  ]
}}

---

OUTPUT FORMAT (STRICT)
{{
"units": [
{{
"unit": 1,
"title": "[Exact name of the first unit as written in the book]",
"topics": [
{{
"name": "[Topic name from book]",
"tag": "grammar | vocabulary | functional | phonetics | communication | mixed",
"confidence": 0.0
}}
]
}}
]
}}
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
7. CULTURAL & REVIEW FILTER: Do NOT extract generic "Review" chapters, test sections, workbook practice sections, or exam pages (e.g. skip "MÁS EJERCICIOS", "MÁS GRAMÁTICA", "EJERCICIOS", "GRAMÁTICA", "Review", "Test", "Exam"). These are noise and should not be teaching units. However, do NOT discard main unit/section titles or lessons that happen to contain city or country names (e.g., "Berlin, Germany", "Vienna, Austria", "Berne, Switzerland") — these are valid unit/section titles and must be preserved!
8. NO HALLUCINATIONS: Do NOT add units that were not in the input. If the input ends at Level 3, the output MUST end at Level 3.
9. FINAL CLEANUP: No duplicate topics anywhere. No empty units. No hallucinated levels.
10. PRESERVE EXISTING TOPIC BOUNDARIES: Keep the topics exactly as they are structured in the input. Do not split them further, and do not merge distinct topics together.
11. RESOLVE COLUMN-SCRAMBLED MAPPING: If any units or topics are cross-associated or jumbled because they were read horizontally across columns, correctly re-group and associate them with their actual units using logical curriculum structure (e.g. ensure Unit 1 "NOSOTROS Y NOSOTRAS" gets its correct topics and does not spill into Unit 2). Ensure Unit titles are correctly matched to their index (Unit 0 through Unit 9).



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
        
        # Post-process to fix unicode spelling corruption
        data = clean_curriculum_spelling(data)
        return data
    except Exception as e:
        logger.error(f"Normalization failed, returning original data: {e}")
        return clean_curriculum_spelling(curriculum_data)


def clean_curriculum_spelling(curriculum: dict) -> dict:
    if not curriculum or not curriculum.get("units"):
        return curriculum
        
    # Serialize to JSON string
    json_str = json.dumps(curriculum, ensure_ascii=False)
    
    # Check if there are any replacement characters (like \uFFFD)
    if "\uFFFD" not in json_str:
        return curriculum # no corruption detected, skip API call to save cost
        
    logger.info("Unicode replacement character (\\uFFFD) detected in curriculum. Launching post-processing spelling fixer LLM.")
    
    prompt = f"""You are a curriculum spelling and accent corrector.
Your only task is to take a JSON curriculum structure that contains Unicode replacement characters (like \\uFFFD) due to PDF text extraction errors, and reconstruct the correct spelling, tildes, and punctuation in the target language (e.g. Spanish).

🚨 CRITICAL RULES:
1. Reconstruct all words with correct letters, accents, and punctuation (e.g. reconstruct "n\\uFFFDmeros" to "números", "espa\\uFFFDol" to "español", "entonaci\\uFFFDn" to "entonación", "relaci\\uFFFDn" to "relación", "g\\uFFFDnero" to "género", "art\\uFFFDculos" to "artículos", "d\\uFFFDa" to "día", "m\\uFFFDs" to "más", "pretr\\uFFFDrito" to "pretérito", "informaci\\uFFFDn" to "información", "car\\uFFFDcter" to "carácter", "\\uFFFDd\\uFFFDnde est\\uFFFD santiago?" to "¿DÓNDE ESTÁ SANTIAGO?", "\\uFFFDcu\\uFFFDl prefieres?" to "¿CUÁL PREFIERES?", "\\uFFFD a comer!" to "¡A COMER!").
2. Maintain the exact JSON structure. Do NOT change key names, do NOT change the number of units or topics. Only correct the spelling of string values.
3. Return ONLY valid JSON. Do NOT wrap in ```json or ```, do NOT add any markdown, do NOT add any text before or after the JSON.

Input JSON:
{json_str}
"""
    messages = [{"role": "user", "content": prompt}]
    result = call_llm(messages)
    
    try:
        cleaned_data = json.loads(result)
        # Verify the structure has not changed drastically
        if isinstance(cleaned_data, dict) and "units" in cleaned_data:
            # Sync back text to name or name to text to preserve normalization
            for u in cleaned_data["units"]:
                for t in u.get("topics", []):
                    if isinstance(t, dict):
                        if "name" in t:
                            t["text"] = t["name"]
                        elif "text" in t:
                            t["name"] = t["text"]
            return cleaned_data
    except Exception as e:
        logger.error(f"Spelling fixer failed to parse JSON response: {e}. Returning original.")
    
    return curriculum

