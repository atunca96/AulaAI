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

# Triple-Threat Orchestration (V5.0-OPENAI-POWERED)
MODEL_STRUCTURAL = os.getenv("MODEL_STRUCTURAL", "openai/gpt-4o-mini")          # Default to gpt-4o-mini for speed & cost
MODEL_NARRATIVE = os.getenv("MODEL_NARRATIVE", "openai/gpt-4o-mini")               # Default to gpt-4o-mini for speed & cost
MODEL_FALLBACK = os.getenv("MODEL_FALLBACK", "openai/gpt-4o-mini")                 # Default to gpt-4o-mini for speed & cost

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
                    # Dynamic timeout: larger for high-token requests (lesson gen), shorter for structural
                    _timeout = 75 if max_tokens > 3000 else 45
                    with urllib.request.urlopen(req, timeout=_timeout) as response:
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
                    sleep_time = 3 * (attempt + 1)
                    if "429" in str(e):
                        sleep_time = 5 * (attempt + 1)
                    with open("pipeline.log", "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-RETRY] Attempt {attempt+1} failed/timed-out: {e}. Sleeping {sleep_time}s\n")
                    time.sleep(sleep_time)
            
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
    2. HOMOGENEITY RULE (CRITICAL): All 4 options (answer + 3 distractors) MUST be the EXACT SAME grammatical type, sentence structure, and format.
       - If the correct answer is a QUESTION (e.g. "¿Cuánto cuesta?"), then ALL 3 distractors MUST ALSO be questions (e.g. "¿Dónde está?", "¿Cómo se llama?", "¿Qué hora es?").
       - If the correct answer is a STATEMENT, all distractors must also be statements.
       - If the correct answer is a VERB FORM, all distractors must also be verb forms.
       - If the correct answer is a NOUN, all distractors must also be nouns.
       - NEVER mix questions with statements, nouns with verbs, or phrases with single words. The student must NOT be able to identify the correct answer just by looking at the format.
    3. SITUATIONAL FLUENCY: Avoid 'Dictionary Definitions'. Instead of asking 'What is X?', create a scenario, dialogue, or situation. 
    4. TRICKY DISTRACTORS: Each distractor must be a plausible alternative that a {level} student might genuinely confuse with the correct answer. Distractors should be from the SAME semantic domain (e.g. all food items, all question phrases, all time expressions).
    5. LINGUISTIC VERACITY: Logic must be 100% correct for {language}. Never hallucinate sound-to-letter or grammar rules.
    6. NO CLUES: The correct answer MUST NOT be distinguishable from distractors by length, formatting, punctuation, or grammatical type. A student should ONLY be able to answer correctly if they know the material.
    
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
        res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=target_model, max_tokens=3000, temperature=0.85)
        
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

    system = f"""You are a world-class curriculum architect and expert linguist specializing in the CEFR framework (A1-C2) for {language}. 
    Your mission: Design a comprehensive, pedagogically deep, and culturally rich roadmap for learning {language}.
    STRICT RULE: ALL unit titles and topic titles MUST be written in English.
    PEDAGOGIC DEPTH: Go beyond simple vocabulary. Each topic should feel like a real lesson that covers functional usage, nuances, and situational grammar."""
    
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
5. MANDATORY SCOPE: Generate EXACTLY 8 to 12 chapters to ensure full curriculum coverage. A roadmap with fewer than 8 units is unacceptable.
6. TOPIC DENSITY: Each chapter MUST have at least 3-4 descriptive topics.
5. ENGLISH TITLES ONLY: ALL unit titles ('title' field) and topic titles ('title' field) MUST be in English. Never use {language} for titles. Example: use 'Greetings and Introductions' NOT 'Saludos y Presentaciones'.

Return ONLY valid JSON: {{'chapters': [{{'number': 1, 'title': '...', 'topics': [{{'title': '...', 'type': 'vocabulary|grammar'}}]}}]}}"""
    res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=2500, temperature=0.7)
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
    
    # ── AUTO-CACHE: Save the generated blueprint so "Clear Cached Blueprints" works ──
    if chapters:
        save_blueprint_cache(language, level, chapters)
    
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

    min_pages = 5

    # ── PHONETIC & PEDAGOGICAL GUARDRAILS ──
    no_english_in_lists = """
NO ENGLISH IN LISTS (CRITICAL): 
- NEVER include English translations as separate items in a list of strings. 
- All items in a 'list' or 'items' array MUST be in the target language if they are strings. 
- If you want to provide a translation, use the OBJECT format: {'term': '...', 'translation': '...'} or {'text': '...', 'meaning': '...'}. 
- DO NOT generate: ['Word', 'Translation', 'Word2', 'Translation2']. This is incorrect. 
- ALWAYS generate: [{'term': 'Word', 'translation': 'Translation'}, ...] or ['Word', 'Word2', ...]."""
    density_mandate = """
CONTENT DENSITY MANDATE (CRITICAL): 
- VOCABULARY: Minimum 10 items per vocabulary page. Cover primary, secondary, and tertiary nuances.
- EXAMPLES: Minimum 10 example sentences or dialogue lines. Show the words in varied social contexts.
- EXPLANATIONS: Every 'explanation' or 'text' field MUST contain at least 5-8 detailed bullet points. Explain usage, cultural context, common learner mistakes, and pronunciation tips.
- NO THIN PAGES: If a page feels light, combine it or expand it. Every page must be packed with educational value. Aim for 'Smartboard Density' — enough to fill a large screen with useful info."""
    simplicity_rule = """
BEGINNER SIMPLICITY RULE (A1-A2): 
1. NO TECHNICAL JARGON: Avoid linguistics terms like 'voiced/voiceless', 'front/back vowels', or 'agglutinative' unless you explain them with simple physical metaphors (e.g., instead of 'voiceless', say 'a soft breathy sound').
2. PHYSICAL CUES: For sounds with no English equivalent (like Turkish 'ı', German 'ü', or French 'r'), provide physical instructions. Example for 'ı': 'Keep your mouth slightly open and teeth together, like the sound you make when you see something gross (ugh!) but shorter.'
3. RELATABILITY: Always relate foreign concepts to something a native English speaker does naturally. Every single letter or grammar rule must have a 'Student-Friendly Tip' that makes it feel easy, not academic."""
    contrast_rule = """
TOPIC CONTRAST RULE (MANDATORY): 
- If the topic is 'Alphabet', focus EXCLUSIVELY on letter names and sequences. DO NOT ask about pronunciation or phonetics.
- If the topic is 'Pronunciation', focus EXCLUSIVELY on phonetic sounds, silent letters, and stress. DO NOT ask about the names of letters.
- If the topic is 'Greetings', focus on cultural social hierarchies. DO NOT ask about grammar rules unless they change the greeting.
- REPETITION CHECK: Before generating a question, ask yourself: 'Is this the most obvious/generic question for this topic?'. If yes, DISCARD it and create something more specific and clever."""
    differentiation_rule = """
TOPIC DIFFERENTIATION RULE (CRITICAL): 
- UNIQUE QUESTIONS: NEVER reuse generic questions across related topics. Questions must be 'Laser-Focused' on the specific title of the topic.
- NUANCE: For 'Alphabet' topics, focus on letter names, recognition, and alphabetical order. For 'Pronunciation' topics, focus strictly on phonetic sounds, vowel length, oral stress, and English-related sound comparisons.
- VARIETY: Use clever, varied scenarios. For pronunciation, use 'Which word sounds like the English word X?' or 'Which letter is silent in word Y?'. For alphabet, use 'Which letter comes after Z?' or 'Identify the uppercase version of letter A'."""
    depth_rule = """
MCQ EXPLANATION DEPTH (CRITICAL): 
- NEVER restate the question or the answer (e.g., DO NOT say 'Choose the correct greeting').
- ALWAYS provide a 'Linguistic Reasoning': Explain WHY the correct answer fits the context and briefly WHY the distractors are incorrect for that specific context.
- Example: Instead of 'Choose the name phrase', say '• Benim adım... literally means My name is... and is the standard way to introduce yourself. • Nasılsınız? is used to ask How are you? and is not an introduction.'"""
    accuracy_rule = """
PEDAGOGICAL ACCURACY RULE (CRITICAL): 
1. NO AMBIGUITY: When creating MCQs, ensure distractors are CLEARLY incorrect. Avoid 'trick' questions where multiple answers could be technically correct (e.g., don't mark a neutral greeting wrong in a formal context unless a strictly formal option is the ONLY correct choice).
2. CONTEXT-RICH PROMPTS: Questions must provide enough context (time of day, social setting, relationship) to make the correct answer the ONLY logical choice.
3. LANGUAGE-AGNOSTIC PRECISION: This rule applies to all languages. Do not use generic greetings as distractors for specific questions if they could be used correctly in that scenario."""
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
    ACCURACY RULE: {accuracy_rule}
    DEPTH RULE: {depth_rule}
    DIFFERENTIATION RULE: {differentiation_rule}
    CONTRAST RULE: {contrast_rule}
    SIMPLICITY RULE: {simplicity_rule}
    DENSITY MANDATE: {density_mandate}
    NO ENGLISH IN LISTS: {no_english_in_lists}
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
    5. MEANINGFUL LENGTH: Generate ONLY as many pages as are naturally required. For most topics, 3-4 pages are sufficient. Aim for 4-6 high-density pages. Prioritize quality and density over quantity.
    6. NO FILLER: Do not create nonsense or thin pages. Every page must be essential.
    7. ENGLISH-ONLY EXPLANATIONS: ALL instructional text, tips, and explanations MUST be in English. NEVER use {language} to explain {language}.
    8. ALPHABET SPECIAL: If this is an alphabet topic, the first page MUST be the complete master list.
    9. PEDAGOGICAL DEPTH: Use practical, everyday scenarios. Explain 'why' using bullets.
    RESPONSE FORMAT (VALID JSON ONLY):
    {{
      "pages": [
        {{ 
          "type": "vocabulary", 
          "title": "Essential Vocabulary", 
          "explanation": "• Deep English explanation of how to use these terms\\n• Cultural or grammatical nuances", 
          "items": [ 
            {{ "term": "...", "translation": "..." }},
            {{ "term": "...", "translation": "..." }}
          ] 
        }},
        {{ 
          "type": "grammar", 
          "title": "Structural Focus", 
          "text": "• Clear bullet-point Rule 1\\n• Rule 2 with English context" 
        }},
        {{ 
          "type": "examples", 
          "title": "Practical Application", 
          "explanation": "• How these sentences work in real life", 
          "list": [ 
            {{ "speaker": "A", "text": "Sentence in {language}" }}, 
            {{ "speaker": "B", "text": "Response in {language}" }} 
          ] 
        }},
        {{ "type": "mcq", "prompt": "...", "explanation": "• Reasoning", "answer": "...", "distractors": ["...", "...", "..."] }}
      ]
    }}"""

    res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=8000, temperature=0.4)
    if res and "pages" in res:
        pages = res["pages"]
        # QUALITY GATE: If the AI returned fewer than 2 real pages, retry with fallback model
        real_pages = [p for p in pages if p.get("type") in ("vocabulary", "grammar", "examples", "mcq") and (p.get("items") or p.get("text") or p.get("list") or p.get("prompt"))]
        if len(real_pages) < 2 and MODEL_FALLBACK:
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-RETRY] Only {len(real_pages)} real pages for '{topic}', retrying with fallback...\n")
            res2 = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_FALLBACK, max_tokens=8000, temperature=0.4)
            if res2 and "pages" in res2:
                fallback_real = [p for p in res2["pages"] if p.get("type") in ("vocabulary", "grammar", "examples", "mcq") and (p.get("items") or p.get("text") or p.get("list") or p.get("prompt"))]
                if len(fallback_real) > len(real_pages):
                    return res2
        return res
    # If primary model failed entirely, try fallback
    if MODEL_FALLBACK:
        res2 = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_FALLBACK, max_tokens=8000, temperature=0.4)
        if res2 and "pages" in res2:
            return res2
    return {"pages": []}

def ai_explain_word(word, language, context=None):
    system = f"You are a helpful {language} language teacher. Explain terms to students clearly and concisely."
    user = f"""Explain the {language} term: '{word}'. 
    CONTEXT: {context}
    
    STRICT RULES:
    1. The 'explanation', 'usage', and 'tip' fields MUST be written in English.
    2. Only the target word itself can be in {language}.
    3. Keep it brief and pedagogical.
    
    Return ONLY valid JSON: {{'explanation': '...', 'usage': '...', 'tip': '...'}}"""
    return _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=600)

def ai_explain_activity(prompt, correct_answer, student_answer, language):
    clean_lang = language.split('(')[0].strip()
    system = f"""You are a helpful {clean_lang} language teacher explaining mistakes to students.
CRITICAL LANGUAGE RULES:
1. Your explanation text MUST be written ENTIRELY in English.
2. You may quote specific {clean_lang} words (e.g., the answer or question terms) but ALL explanatory sentences MUST be in English.
3. NEVER write full sentences in {clean_lang}.
4. Keep the explanation concise (2-3 sentences max)."""
    user = f"""A student got a {clean_lang} question wrong. Explain the mistake and the correct logic.

Question: {prompt}
Correct Answer: {correct_answer}
Student's Answer: {student_answer}

Return ONLY valid JSON: {{"explanation": "Your English explanation here"}}"""
    return _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=300)

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
