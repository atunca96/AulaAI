import os
import sys
import json
import re
import urllib.request
import urllib.error
import time
import uuid
import random as py_random
from datetime import datetime

print(f"--- AI_ENGINE LOADED AT {datetime.now()} ---")
with open("pipeline.log", "a", encoding="utf-8") as f:
    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [INIT] ai_engine.py loaded\n")
from typing import List, Dict, Any, Optional

def _uid():
    return str(uuid.uuid4())

# LOCAL DEV: Load .env if it exists
if os.path.exists(".env"):
    try:
        with open(".env", "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v
    except: pass

# Triple-Threat Orchestration (V3.0-SUPER-THRIFT)
MODEL_STRUCTURAL = "anthropic/claude-3-haiku"     # For Curriculum & Tap-Translations
MODEL_NARRATIVE = "deepseek/deepseek-v4-flash"    # For High-Quality Content (Lessons/Classrooms)
MODEL_FALLBACK = None 

def is_ai_available():
    """Checks if the system has AI capabilities configured."""
    return os.getenv("OPENROUTER_API_KEY") is not None and len(os.getenv("OPENROUTER_API_KEY", "")) > 10

def _call_ai(messages: List[Dict], model: str = MODEL_STRUCTURAL, max_tokens: int = 1000, temperature: float = 0.7) -> Optional[Dict]:
    """OpenRouter caller with markdown cleaning and automatic retries."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key: return {"error_details": "API Key Missing"}

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aulaai.com",
        "X-Title": "AulaAI"
    }

    last_error = "Unknown"
    models_to_try = [model] if model else [MODEL_STRUCTURAL]
    
    for target_model in models_to_try:
        try:
            req = urllib.request.Request(url, data=json.dumps({
                "model": target_model, "messages": messages, "max_tokens": max_tokens, 
                "temperature": temperature
            }).encode("utf-8"), headers=headers)
            
            # AGGRESSIVE RETRY LOOP for 'Straggler' prevention
            for attempt in range(3):
                try:
                    # Shortened 40s timeout to pivot quickly if a node is slow
                    with urllib.request.urlopen(req, timeout=40) as response:
                        res_body = response.read().decode("utf-8")
                        res_json = json.loads(res_body)
                        
                        if "choices" in res_json:
                            content = res_json["choices"][0]["message"]["content"].strip()
                            with open("pipeline.log", "a", encoding="utf-8") as f:
                                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-SPEED] Received {len(content)} chars from {target_model}\n")
                            
                            # ROBUST JSON EXTRACTION
                            start_obj = content.find('{')
                            start_list = content.find('[')
                            start = -1
                            end = -1
                            if start_obj != -1 and (start_list == -1 or start_obj < start_list):
                                start = start_obj
                                end = content.rfind('}')
                            elif start_list != -1:
                                start = start_list
                                end = content.rfind(']')
                                
                            if start != -1 and end != -1 and end > start:
                                json_str = content[start:end+1]
                                
                                def _try_parse(s):
                                    try: return json.loads(s, strict=False)
                                    except:
                                        try:
                                            import ast
                                            c_s = s.replace('true', 'True').replace('false', 'False').replace('null', 'None')
                                            return ast.literal_eval(c_s)
                                        except: return None

                                data = _try_parse(json_str)
                                if data: return data
                except Exception as e:
                    with open("pipeline.log", "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-RETRY] Attempt {attempt+1} failed/timed-out: {e}\n")
                    # Immediate retry for speed (0.5s instead of 2s)
                    time.sleep(0.5)
            
            return None
                        
        except Exception as e:
            last_error = str(e)
            try:
                with open("pipeline.log", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-FAIL] {target_model}: {last_error}\n")
            except: pass
            
    return {"error_details": last_error}

def detect_language(text, hint=""):
    prompt = f"Detect language of: {text[:1000]} (Hint: {hint}). JSON: {{'language': '...'}}"
    res = _call_ai([{"role": "user", "content": prompt}])
    return res.get("language", "Unknown") if res else "Unknown"

def get_language_profile(language):
    agglutinative = ["Turkish", "Korean", "Japanese", "Finnish", "Hungarian"]
    if language in agglutinative: return "agglutinative"
    return "inflected"

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, is_quiz=False, source_text_override=None, model_override=None):
    with open("pipeline.log", "a", encoding="utf-8") as f:
        api_status = "Available" if is_ai_available() else "MISSING KEY"
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-START] {topic_title} count={count} API={api_status}\n")
    
    c = int(count)
    is_beginner = any(lvl in level.upper() for lvl in ["A1", "A2"])
    
    # Use override if provided (for speed during build), else use topic_content
    if source_text_override:
        content_str = f"EXTRACTED TEXTBOOK CONTENT:\n{source_text_override[:10000]}"
    else:
        content_str = json.dumps(topic_content, ensure_ascii=False)
    
    from services.language_data import get_reference_prompt, get_special_chars_prompt
    is_alphabet_topic = any(x in topic_title.lower() for x in ["alphabet", "alfabeto", "alfabe", "letters"])
    
    ref_data = ""
    if is_alphabet_topic:
        ref_data = get_reference_prompt(language)
    elif any(x in topic_title.lower() for x in ["accent", "character", "mark", "diacritic"]):
        ref_data = get_special_chars_prompt(language)

    forbidden_clause = ""
    if existing_questions and len(existing_questions) > 0:
        qs_list = "\n".join([f"- Answer: '{q.get('answer', '')}' (Prompt: '{q.get('prompt', '')[:40]}...')" for q in existing_questions])
        forbidden_clause = f"\nEXISTING QUESTIONS TO AVOID (DO NOT TEST THESE EXACT CONCEPTS):\n{qs_list}\n"

    system = f"""You are the {language} Pedagogic Engine (V5). 
    Your mission: Using the provided textbook content as your source, generate questions that test genuine understanding of the material — use real examples from the text, plausible distractors drawn from related concepts, and varied formats. Never repeat the same question pattern twice in a single set.
    
    PEDAGOGIC PROTOCOL:
    1. MATERIAL FIDELITY: Only use words and facts found in the SOURCE MATERIAL.
    2. HOMOGENEITY: All 4 options (answer + distractors) MUST share the same structure and part-of-speech.
    3. SITUATIONAL FLUENCY: Avoid 'Dictionary Definitions'. Instead of asking 'What is X?', create a scenario, dialogue, or situation. 
    4. TRICKY DISTRACTORS: Ensure distractors are plausible and related to the topic, making the answer NOT 'obvious'.
    5. LINGUISTIC VERACITY: Logic must be 100% correct for {language}. Never hallucinate sound-to-letter or grammar rules.
    6. NO CLUES: The correct answer MUST NOT be visible or hinted at in the prompt text.
    
    RESPONSE FORMAT:
    Output EXCLUSIVELY a JSON object. Every prompt MUST have an English 'translation'."""

    user = f"""TASK: Generate EXACTLY {c} unique {topic_type} questions.
    TOPIC: {topic_title}
    LEVEL: {level}
    SOURCE MATERIAL: {content_str}
    {ref_data}
    {forbidden_clause}
    
    VARIETY INSTRUCTION: Vary format, difficulty, and context. Use different scenario styles for every question.
    MIXED CURRICULUM RULE: If topic_type is 'mixed_curriculum', ensure questions are balanced across all provided topics.
    
    JSON STRUCTURE:
    {{
      "data": [
        {{
          "type": "mcq",
          "prompt": "...",
          "translation": "English translation",
          "answer": "...",
          "distractors": ["...", "...", "..."],
          "why": "English explanation"
        }}
      ]
    }}"""
    
    if is_quiz and is_beginner:
        user += f"\n\nSTRICT ENGLISH PROMPT RULE: This is a QUIZ for {level} beginners. You MUST write the 'prompt' field in English. The 'answer' and 'distractors' MUST be in {language}."
    else:
        user += f"\n\nLANGUAGE MEDIUM: Write the 'prompt' field in {language} to immerse the student."

    # MAX VARIETY SEED: Uses high-precision timestamp to ensure Gemini never repeats
    seed = int(time.time() * 1000) % 999999
    user += f"\n\nUNIQUE_REQUEST_ID: {seed}_{py_random.random()}"
    
    try:
        # GEMINI 2.5 FLASH TUNING: High variety (0.7)
        target_model = model_override if model_override else "google/gemini-2.5-flash"
        res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=target_model, max_tokens=3000, temperature=0.7)
        
        raw_list = []
        if isinstance(res, list):
            raw_list = res
        else:
            raw_list = (res.get("data") if (res and isinstance(res, dict)) else []) or []
        
        # ── V4 ZERO-FILTER CATASTROPHE GUARD ──
        # We trust Gemini 2.0 Flash to follow the pedagogy. 
        # We only check for missing keys to prevent UI crashes.
        final = []
        for item in raw_list[:count]:
            if not isinstance(item, dict): continue
            
            p = str(item.get("prompt", "")).strip()
            a = str(item.get("answer", "")).strip()
            d = item.get("distractors", [])
            
            if p and a and len(d) >= 3:
                # Basic shuffle and assembly
                opts = [a] + [str(x).strip() for x in d[:3]]
                py_random.shuffle(opts)
                
                final.append({
                    "id": _uid(),
                    "type": "mcq",
                    "prompt": p,
                    "translation": item.get("translation", ""),
                    "answer": a,
                    "distractors": d[:3],
                    "options": opts,
                    "why": item.get("why", "Correct answer based on the material.")
                })
        
        if not final:
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-EMPTY] Gemini 2.0 returned no valid questions for {topic_title}\n")
            return []
            
        return final

        if not final:
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-EMPTY] RawLen={len(raw_list)} for {topic_title}\n")
            return [] 

        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-DONE] requested={c} returned={len(final)}\n")
        return final[:c]
    except Exception as e:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-CRASH] {e}\n")
        return []

def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, model_override=None):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions, is_pdf_source=is_pdf_source, model_override=model_override)

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions, is_pdf_source=is_pdf_source)

def ai_grade_open_response(question, student_answer, correct_answer):
    prompt = f"Grade: Q:{question}, C:{correct_answer}, S:{student_answer}. JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150)
    return (result.get("score", 0.0), result.get("feedback", "")) if result else (0.0, "")

def ai_generate_curriculum(language, level, prompt_extra=""):
    """Generates course structure, using a local blueprint cache to eliminate recurring costs."""
    cache_file = _get_blueprint_path(language, level)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                if cached_data and "chapters" in cached_data:
                    return cached_data["chapters"]
        except: pass

    system = f"You are a master curriculum architect specializing in the CEFR framework (A1-C2) for {language}."
    
    level_guidelines = {
        "A1": "Focus on absolute basics: alphabet/phonetics, greetings, numbers, basic present tense, immediate survival vocabulary, and personal info.",
        "A2": "Focus on routine tasks, past tenses (intro), describing surroundings, simple social exchanges, and common shopping/work scenarios.",
        "B1": "Focus on traveling situations, expressing opinions/dreams/hopes, complex past tenses, future/conditional, and providing reasons for plans.",
        "B2": "Focus on technical discussions, interacting with natives without strain, detailed text on diverse subjects, and introductory Subjunctive mood.",
        "C1": "Focus on complex subjects, implicit meaning, flexible/effective language for academic/professional use, deep nuance, and advanced idiomatic usage.",
        "C2": "Focus on near-native mastery, summarizing complex sources, precise expression of fine shades of meaning, and spontaneous academic reconstruction."
    }
    
    # Determine the closest CEFR guideline
    current_guideline = next((v for k, v in level_guidelines.items() if k in level.upper()), "Follow general CEFR progression.")

    user = f"""Create a comprehensive {level} {language} course syllabus.
LEVEL-SPECIFIC FOCUS: {current_guideline}

RULES:
1. PEDAGOGICAL ACCURACY: The topics MUST strictly reflect the {level} level requirements.
2. NO GENERIC TITLES: Do NOT use 'Vocabulary', 'Grammar', or 'Exercises'. Every topic must be descriptive (e.g., 'Navigating a Hospital', 'The Imperfect vs. Preterite', 'Debating Environmental Ethics').
3. PROGRESSION: Ensure units move logically from foundational to complex within the {level} bracket.
4. VARIETY: Mix functional language, grammar, and cultural context.

Return ONLY valid JSON: {{'chapters': [{{'number': 1, 'title': '...', 'topics': [{{'title': '...', 'type': 'vocabulary|grammar'}}]}}]}}"""
    res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_STRUCTURAL, max_tokens=2500)
    chapters = res.get("chapters", []) if res else []
    
    # ── MANDATORY ALPHABET FOR A1 ROADMAPS ──
    if level.upper().startswith("A1"):
        # 1. Remove duplicates (including phonetics, vowels, etc. which are now merged into Unit 1)
        keywords = ["alphabet", "vowel", "consonant", "pronunciation", "phonetic", "sound", "alfabeto", "alfabe", "letters"]
        
        filtered_chapters = []
        for ch in chapters:
            # Check if the CHAPTER TITLE itself is an alphabet unit
            if any(kw in ch.get("title", "").lower() for kw in keywords):
                continue
            
            if "topics" in ch:
                # Remove alphabet topics from other units
                ch["topics"] = [t for t in ch["topics"] if not any(kw in t.get("title", "").lower() for kw in keywords)]
            
            # Only keep chapters that still have content
            if ch.get("topics"):
                filtered_chapters.append(ch)
        
        # 2. Inject Unit 1 with comprehensive topics
        alphabet_unit = {
            "number": 1,
            "title": "The Alphabet and Foundations",
            "topics": [
                {"title": "The Alphabet", "type": "vocabulary"},
                {"title": "Vowels and Consonants", "type": "grammar"},
                {"title": "Pronunciation and Phonetics", "type": "grammar"}
            ]
        }
        filtered_chapters.insert(0, alphabet_unit)
        
        # 3. Re-index and Clean Titles
        for i, ch in enumerate(filtered_chapters):
            ch["number"] = i + 1
            if i > 0 and "title" in ch:
                ch["title"] = re.sub(r'^Unit\s*\d+\s*[:\-]*\s*', '', ch["title"], flags=re.IGNORECASE).strip()
        
        chapters = filtered_chapters
    
    return chapters

def ai_generate_report_insights(cohort_data):
    """Generates high-level pedagogical insights for teacher reports."""
    prompt = f"Analyze student performance and provide 3 actionable teaching insights: {json.dumps(cohort_data)}"
    res = _call_ai([{"role": "user", "content": prompt}], max_tokens=600)
    return res.get("explanation", "Insufficient data for insights.") if res else "Connection Error."

def generate_full_lesson(topic, topic_type, language, count=6, level='A1', source_text=None):
    """Generates a complete structured lesson, using source_text as the primary source if provided."""
    from services.language_data import get_reference_prompt, get_special_chars_prompt, ALPHABETS
    
    is_alphabet_topic = any(x in topic.lower() for x in ["alphabet", "alfabeto", "alfabe", "letters"])
    is_beginner = any(lvl in level.upper() for lvl in ["A1", "A2"])
    
    lang_guard = f"REQUIRED BILINGUAL SPLIT: All instructional text, titles, and grammar explanations MUST be in English. All target language content (vocabulary, sentences, examples) MUST be in {language}."
    if is_beginner:
        lang_guard = f"STRICT BEGINNER REQUIREMENT: You are teaching {level} beginners. All titles, grammar explanations, and instructions MUST be in English. NEVER explain {language} concepts using {language}. Use English as the primary instructional medium."

    source_rule = ""
    if source_text:
        source_rule = f"SOURCE TEXT REQUIREMENT:\nYou MUST use the following text as your core source: {source_text[:10000]}"
    else:
        source_rule = "NO SOURCE TEXT: Use your internal knowledge."

    # ── ALPHABET & SPECIAL CHARACTER REINFORCEMENT ──
    # Refined Alphabet Guard: Only force the full list for the PRIMARY alphabet topic.
    is_primary_alphabet = any(x == topic.lower().strip() for x in ["the alphabet", "alphabet", "alfabeto", "alfabe"])
    is_sub_alphabet = not is_primary_alphabet and any(x in topic.lower() for x in ["alphabet", "vowel", "consonant", "pronunciation", "phonetic", "letter"])
    
    alphabet_rule = ""
    ref_data = ""
    if is_primary_alphabet:
        alphabet_list = get_reference_prompt(language)
        alphabet_rule = f"\nSTRICT RULE: The FIRST page of this lesson MUST include the following complete list of characters for {language} to serve as the master reference:\n{alphabet_list}\n"
    elif is_sub_alphabet:
        alphabet_rule = f"\nCONTEXT: The user has already seen the full alphabet list in the previous topic. DO NOT provide a full character list here. Focus EXCLUSIVELY on the {topic} nuances."

    if any(x in topic.lower() for x in ["accent", "character", "mark", "diacritic"]):
        ref_data = get_special_chars_prompt(language)
        ref_data += f"\nPRONUNCIATION RULE: Explain how these marks affect sound using English phonetics."

    min_pages = 4 if (is_primary_alphabet or is_sub_alphabet) else 3

    # ── PHONETIC & PEDAGOGICAL GUARDRAILS ──
    phonetic_rule = (
        "\nPHONETIC APPROXIMATION RULE (CRITICAL): When explaining how letters or words sound, "
        "NEVER use target language spellings to describe the sound (e.g., DO NOT say 'Ç sounds like çe'). "
        "Instead, ALWAYS use English word approximations that an A1 student can understand "
        "(e.g., 'Ç sounds like the ch in church', or 'Ş sounds like the sh in sheep'). "
        "This rule is language-agnostic: always relate sounds to common English words."
    )

    system = f"""You are a master {language} pedagogical designer. 
    STRICT IDENTITY: You write high-quality, CEFR-aligned lessons. Your goal is MEANINGFUL TEACHING, not meeting a page count.
    FORMATTING RULE: All explanations MUST be formatted as concise BULLET POINTS. No walls of text.
    SMARTBOARD RULE: Lessons are taught on large smartboards. You MUST break all paragraphs into clear, scannable bullet points so students can read them from the back of a classroom. 
    EXPLANATORY RULE: Every page MUST include helpful bullet-point explanations in English.
    FORBIDDEN CONTENT: Never create a page named "Material" or use "Material" as a title. No filler or nonsense pages. NO LONG PARAGRAPHS.
    PEDAGOGICAL TYPES: Only use "vocabulary", "grammar", "examples", and "mcq" types.
    PHONETIC RULE: {phonetic_rule}
    JSON EFFICIENCY: Return MINIFIED JSON only (no whitespace, no indentation).
    NO CONVERSATION: Provide ONLY the JSON structure."""

    user = f"""Write a comprehensive {level} lesson to teach {language} topic: '{topic}' ({topic_type}).
    {source_rule}
    {alphabet_rule}
    {ref_data}

    TECHNICAL SPECS:
    1. {lang_guard}
    2. TARGET LANGUAGE ENFORCEMENT: 'term' and 'text' in example lists MUST be in {language}. For A1-A2, 'title', 'text' (in grammar blocks), and 'prompt' MUST be in English.
    3. BULLET POINTS ONLY: Format all grammar and context 'text' or 'explanation' fields as a list of bullet points. NO LONG PARAGRAPHS.
    4. SCRIPT CONSISTENCY: Use the correct alphabet for {language}.
    5. MEANINGFUL LENGTH: Generate ONLY as many pages as are naturally required to teach this topic meaningfully. There is no minimum and no maximum page count. Prioritize quality and depth over length.
    6. NO FILLER: Do not create nonsense or thin pages just to add length. Every page must be a core part of the lesson.
    7. EXPLANATION ON EVERY PAGE: Every page type (vocabulary, examples, mcq) must include an explanatory bullet-point list in English.
    8. ALPHABET SPECIAL: If this is an alphabet topic, the first page MUST be the complete master list.
    9. PEDAGOGICAL DEPTH: Use practical, everyday scenarios. Explain 'why' using bullets.
    RESPONSE FORMAT (VALID JSON ONLY):
    {{
      "pages": [
        {{ "type": "vocabulary", "title": "Specific Topic Vocabulary", "explanation": "• Bullet 1\\n• Bullet 2", "items": [ {{ "term": "...", "translation": "..." }} ] }},
        {{ "type": "grammar", "title": "Specific Grammar Focus", "text": "• Rule 1\\n• Rule 2" }},
        {{ "type": "examples", "title": "Practical Usage & Dialogue", "explanation": "• Context 1\\n• Context 2", "list": [ {{ "speaker": "A", "text": "Target language sentence" }}, {{ "speaker": "B", "text": "Target language response" }} ] }},
        {{ "type": "mcq", "prompt": "...", "explanation": "• Why this answer is correct", "answer": "...", "distractors": ["...", "...", "..."] }}
      ]
    }}"""

    res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=4000, temperature=0.4)
    if res and "pages" in res:
        return res
    return {"pages": []}

def ai_explain_word(word, language, context=None):
    prompt = f"Explain '{word}' in {language}. Context: {context}. JSON: {{'explanation': '...', 'usage': '...', 'tip': '...'}}"
    return _call_ai([{"role": "user", "content": prompt}], model=MODEL_NARRATIVE, max_tokens=400)

def ai_explain_activity(prompt, correct_answer, student_answer, language):
    clean_lang = language.split('(')[0].strip()
    system = f"You are a helpful {clean_lang} teacher. STRICT RULE: Your response MUST be in English. Do NOT use {clean_lang} for the explanation text."
    user = f"A student got a {clean_lang} question wrong. Explain the mistake and the correct logic in English.\nQ: {prompt}\nCorrect Answer: {correct_answer}\nStudent Answer: {student_answer}\n\nReturn JSON: {{'explanation': '...'}}"
    return _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=250)

def _get_blueprint_path(language, level):
    cache_dir = os.path.join("services", "blueprints")
    if not os.path.exists(cache_dir): os.makedirs(cache_dir)
    clean_lang = "".join(filter(str.isalnum, language.split('(')[0])).lower()
    clean_level = "".join(filter(str.isalnum, level)).lower()
    return os.path.join(cache_dir, f"{clean_lang}_{clean_level}.json")

def save_blueprint_cache(language, level, chapters):
    try:
        cache_file = _get_blueprint_path(language, level)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"chapters": chapters}, f, ensure_ascii=False, indent=2)
        return True
    except: return False

def delete_blueprint_cache(language, level):
    try:
        cache_file = _get_blueprint_path(language, level)
        if os.path.exists(cache_file): os.remove(cache_file); return True
        return False
    except: return False

def list_blueprint_cache():
    cache_dir = os.path.join("services", "blueprints")
    if not os.path.exists(cache_dir): return []
    return [{"language": f.split('_')[0], "level": f.split('_')[1].replace('.json','')} for f in os.listdir(cache_dir) if f.endswith('.json')]
