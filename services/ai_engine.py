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

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, is_quiz=False, source_text_override=None):
    with open("pipeline.log", "a", encoding="utf-8") as f:
        api_status = "Available" if is_ai_available() else "MISSING KEY"
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-START] {topic_title} count={count} API={api_status}\n")
    
    c = int(count)
    request_count = c + 5 # Small buffer for validation fallout
    # IMMERSION POLICY: Always use target language for prompts, even for A1/A2
    instruction_lang = language
    
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

    translation_rule = '12. TRANSLATION: Add a "translation" field containing the English translation of the prompt.' if is_beginner else ""
    translation_field = '"translation": "...", ' if is_beginner else ""

    system = f"""You are a master {language} teacher and expert curriculum designer. 
    STRICT IDENTITY: You always provide structured, pedagogical content without any conversational filler, intro, or outro. 
    EXPLANATION RULE: All 'why' fields MUST be in English.
    OUTPUT RULE: Your response must be EXCLUSIVELY a valid JSON object. No markdown code blocks unless requested, no preamble."""

    user = f"""TASK: Generate {request_count} high-quality, creative multiple-choice questions for: {topic_title} ({topic_type}).
    LEVEL: {level}
    SOURCE MATERIAL: {content_str}
    {ref_data}
    {forbidden_clause}

    PEDAGOGICAL REQUIREMENTS:
    1. SCENARIO-BASED: Use real-world situations (e.g., 'At a cafe', 'Talking to a neighbor').
    2. VARY FORMATS: Mix fill-in-the-blanks, dialogue completion, and semantic odd-one-out.
    3. CATEGORY LOCK (STRICT): If the answer is a Verb, ALL 4 options must be Verbs. If an Adjective, ALL 4 must be Adjectives.
    4. SCRIPT CONSISTENCY: The answer and all distractors MUST use the same script (Cyrillic, Arabic, or Latin).
    5. SIMPLICITY & DEPTH: Questions should be clear but test actual nuance.

    TECHNICAL SPECS:
    - Language for prompts: {instruction_lang}
    - Options: 4 total (1 answer, 3 distractors)
    - Punctuation: Standard for {language}
    {translation_rule}

    RESPONSE FORMAT (JSON ONLY):
    {{
      "data": [
        {{
          "type": "mcq",
          "prompt": "...",
          {translation_field}"answer": "...",
          "distractors": ["...", "...", "..."],
          "why": "1-sentence English explanation"
        }}
      ]
    }}"""

    seed = py_random.randint(1000, 9999)
    user += f"\n\nSEED: {seed}"
    
    try:
        # ACTIVITY TUNING: Use 2000 tokens for speed
        res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=2000, temperature=0.85)
        if isinstance(res, list):
            raw_list = res
        else:
            raw_list = (res.get("data") if (res and isinstance(res, dict)) else []) or []
        
        def _validate_question(item, seen_answers, used_dist_sets, has_rich_vocab):
            if not isinstance(item, dict): return None
            ans = str(item.get("answer", "")).strip()
            prompt_text = str(item.get("prompt", "")).strip()
            distractors = item.get("distractors", [])
            if not isinstance(distractors, list) or len(distractors) < 3: return None
            distractors = [str(d).strip() for d in distractors[:3] if str(d).strip()]
            if len(distractors) < 3: return None
            
            if not ans or not prompt_text or len(prompt_text) < 2: return None
            ans_lower = ans.lower()
            prompt_lower = prompt_text.lower()
            # ALLOW answer in prompt (e.g. 'What does [word] mean?')
            pass
            
            ans_key = ans_lower.strip()
            if ans_key in seen_answers: return None
            
            # REMOVED dist_set check to allow more questions through

            return {
                "id": _uid(), "type": "mcq", "prompt": prompt_text, 
                "answer": ans, "distractors": distractors,
                "translation": item.get("translation")
            }

        all_raw_words = set()
        for item in raw_list:
            if isinstance(item, dict):
                for d in item.get("distractors", []):
                    all_raw_words.add(str(d).lower().strip())
        
        has_rich_vocab = len(all_raw_words) >= 15
        final = []
        seen_answers = set()
        used_dist_sets = []
        
        for item in raw_list:
            valid = _validate_question(item, seen_answers, used_dist_sets, has_rich_vocab)
            if valid:
                opts = [valid["answer"]] + valid["distractors"]
                py_random.shuffle(opts)
                valid["options"] = opts
                final.append(valid)
                seen_answers.add(re.sub(r'[^\w]', '', valid["answer"].lower()).strip())
                used_dist_sets.append(frozenset(d.lower().strip() for d in valid["distractors"]))
                if len(final) >= c: break

        if not final:
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-FAIL] No valid questions generated for {topic_title}\n")
            return [] # No fallback questions as per user request

        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-DONE] requested={c} returned={len(final)}\n")
        return final[:c]
    except Exception as e:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-CRASH] {e}\n")
        return []

def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions, is_pdf_source=is_pdf_source)

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
    
    lang_guard = f"REQUIRED BILINGUAL SPLIT: All instructional text, explanations, and titles MUST be in English. All target language content (words, sentences, examples) MUST be in {language}."
    if is_beginner:
        lang_guard = f"STRICT BEGINNER REQUIREMENT: You are teaching {level} beginners. Explain {language} concepts using English. DO NOT explain English grammar; explain {language} grammar using English as the medium."

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
    STRICT IDENTITY: You write high-quality, CEFR-aligned lessons.
    REDUNDANCY GUARD: Do not repeat basic tables or lists if the topic is a sub-specialization (e.g. Vowels, Pronunciation).
    PHONETIC RULE: {phonetic_rule}
    SPEED PRIORITY: Be surgically concise with word choice and JSON structure.
    JSON EFFICIENCY: Return MINIFIED JSON only (no whitespace, no indentation) to ensure maximum speed.
    NO CONVERSATION: Provide ONLY the JSON structure. No intro, no chat, no markdown blocks."""

    user = f"""Write a comprehensive {level} lesson to teach {language} topic: '{topic}' ({topic_type}).
    {source_rule}
    {alphabet_rule}
    {ref_data}

    TECHNICAL SPECS:
    1. {lang_guard}
    2. TARGET LANGUAGE ENFORCEMENT: Every single 'term', 'text', 'prompt', and 'answer' field MUST be in {language}.
    3. NO PLACEHOLDERS: Do not use generic sentences like "I like sports". Use specific {language} sentences.
    4. SCRIPT CONSISTENCY: Use the correct alphabet for {language}.
    5. STRICT 3-PAGE CAP: You MUST generate EXACTLY 3 RICH and DENSE pages. 
       - Page 1: Vocabulary/Foundation.
       - Page 2: Grammar/Phonetic Deep-Dive.
       - Page 3: Real-world Examples or Dialogue.
       DO NOT generate 4th or 5th pages. If you have extra content, pack it into Page 3.
    6. NO THIN PAGES: Every page must be packed with content. NEVER provide a page with only 2-3 items.
    7. ALPHABET SPECIAL: If this is an alphabet topic, Page 1 MUST be the complete master list.
    RESPONSE FORMAT (VALID JSON ONLY):
    {{
      "pages": [
        {{ "type": "vocabulary", "title": "...", "items": [ {{ "term": "...", "translation": "..." }} ] }},
        {{ "type": "grammar", "title": "...", "text": "Detailed English explanation of target grammar" }},
        {{ "type": "examples", "title": "...", "list": [ {{ "speaker": "A", "text": "Target language sentence" }}, {{ "speaker": "B", "text": "Target language response" }} ] }},
        {{ "type": "mcq", "prompt": "...", "answer": "...", "distractors": ["...", "...", "..."] }}
      ]
    }}"""

    res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=4000, temperature=0.4)
    if res and "pages" in res:
        # MANUAL TRIM: Physically prevent more than 3 pages
        res["pages"] = res["pages"][:3]
        return res
    return {"pages": []}

def ai_explain_word(word, language, context=None):
    prompt = f"Explain '{word}' in {language}. Context: {context}. JSON: {{'explanation': '...', 'usage': '...', 'tip': '...'}}"
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=400)

def ai_explain_activity(prompt, correct_answer, student_answer, language):
    clean_lang = language.split('(')[0].strip()
    system = f"You are a helpful {clean_lang} teacher. STRICT RULE: Your response MUST be in English. Do NOT use {clean_lang} for the explanation text."
    user = f"A student got a {clean_lang} question wrong. Explain the mistake and the correct logic in English.\nQ: {prompt}\nCorrect Answer: {correct_answer}\nStudent Answer: {student_answer}\n\nReturn JSON: {{'explanation': '...'}}"
    return _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=250)

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
