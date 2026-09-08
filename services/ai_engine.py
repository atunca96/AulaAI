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
import unicodedata
import difflib
from typing import List, Dict, Any, Optional

def _uid():
    return str(uuid.uuid4())

def normalize_text_for_cognate(text: str) -> str:
    """Strip diacritics and non-alphanumeric chars for cognate comparison."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(text).lower())
    clean = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', clean)

def is_transparent_cognate(word1: str, word2: str, threshold: float = 0.65) -> bool:
    """Check if two words are transparent cognates (too similar to test directly)."""
    w1 = normalize_text_for_cognate(word1)
    w2 = normalize_text_for_cognate(word2)
    if not w1 or not w2:
        return False
    if len(w1) >= 4 and len(w2) >= 4:
        if w1 in w2 or w2 in w1:
            return True
    min_len = min(len(w1), len(w2))
    if min_len >= 5:
        shared_prefix = 0
        while shared_prefix < min_len and w1[shared_prefix] == w2[shared_prefix]:
            shared_prefix += 1
        if shared_prefix >= 5 or (min_len <= 5 and shared_prefix >= 4):
            return True
    return difflib.SequenceMatcher(None, w1, w2).ratio() >= threshold

def is_transparent_cognate_giveaway(prompt: str, translation: str, answer: str) -> bool:
    """Detect if the prompt or translation contains an obvious cognate giveaway of the target answer."""
    clean_a = normalize_text_for_cognate(answer)
    if len(clean_a) < 4:
        return False
    ans_words = [normalize_text_for_cognate(w) for w in answer.split() if len(normalize_text_for_cognate(w)) >= 4]
    if not ans_words:
        ans_words = [clean_a]

    text_to_check = f"{prompt} {translation}"
    cand_words = re.findall(r'[a-zA-Z\u00C0-\u017F]{4,}', text_to_check)
    stopwords = {"what", "does", "mean", "which", "word", "sentence", "following", "translate", "choose", "correct",
                 "nasil", "nedir", "hangisi", "anlami", "asagidaki", "cumle", "dogru", "kelime", "ifade"}
    for cw in cand_words:
        if normalize_text_for_cognate(cw) in stopwords:
            continue
        for aw in ans_words:
            if is_transparent_cognate(cw, aw, threshold=0.65):
                return True
    return False

# Robust .env loading across execution contexts
if not os.getenv("OPENROUTER_API_KEY"):
    for env_path in [
        ".env",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    ]:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ.setdefault(k.strip(), v.strip())
                if os.getenv("OPENROUTER_API_KEY"):
                    break
            except Exception:
                pass

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
                    _timeout = 45 if max_tokens > 3000 else 30
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
                    sleep_time = 1.5 * (attempt + 1)
                    if "429" in str(e):
                        sleep_time = 3 * (attempt + 1)
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

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, is_quiz=False, source_text_override=None, model_override=None, material_language="en"):
    with open("pipeline.log", "a", encoding="utf-8") as f:
        api_status = "Available" if is_ai_available() else "MISSING KEY"
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-START] {topic_title} count={count} API={api_status}\n")
    
    c = int(count)
    gen_count = max(c + 4, int(c * 1.4))
    is_beginner = any(lvl in level.upper() for lvl in ["A1", "A2"])
    instruction_lang_name = "Turkish" if material_language == "tr" else "English"
    
    # Use override if provided (for speed during build), else use topic_content
    if source_text_override:
        content_str = f"EXTRACTED TEXTBOOK CONTENT:\n{source_text_override[:10000]}"
    else:
        content_str = json.dumps(topic_content, ensure_ascii=False)
    
    from services.language_data import get_reference_prompt, get_special_chars_prompt, get_pedagogical_guidelines
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

    pedagogy_guidance = get_pedagogical_guidelines(language, level)

    system = f"""You are the {language} Pedagogic Engine (V5). 
    Your mission: Using the provided textbook content as your source, generate questions that test genuine communicative and linguistic understanding. Never repeat the same question pattern twice in a single set.
    
    {pedagogy_guidance}
    
    PEDAGOGIC PROTOCOL & MANDATES:
    1. STRICT ANTI-GIVEAWAY MANDATE (CRITICAL):
       - The prompt MUST NEVER contain the correct answer or any stem/part of the correct answer.
       - NEVER ask shallow meta-trivia questions about letter names, string properties, or spelling of characters (e.g., NEVER ask 'Which letter name has the word X in it?', 'Which word ends in Y?', 'Which of these is a letter?').
       - For alphabet and pronunciation topics, test genuine sound-to-letter correspondences in authentic words, silent letters, or minimal pairs. NEVER ask about the spelling of a letter's name.
    2. STRICT ANTI-COGNATE & REAL-CHALLENGE MANDATE (CRITICAL):
       - NEVER ask questions where the target answer is an obvious transparent cognate or nearly identical to its English/Turkish counterpart (e.g., asking for 'multiplicación' when the prompt or translation says 'multiplication', or asking for 'doctor' from 'doctor', or 'música' from 'music', or 'información' from 'information'). Such questions are obvious giveaways and fail to assess genuine language learning!
       - For concepts that share common roots across languages (such as mathematics, science, technology, academic terms), frame questions through realistic communicative situations, procedural scenarios, or word problems (e.g., 'Si compras 3 libros de 4 euros cada uno, ¿qué operación matemática realizas?').
       - All 4 options (answer + 3 distractors) MUST be drawn from the exact same semantic domain (e.g., all 4 must be arithmetic operations: suma, resta, multiplicación, división) so the student cannot deduce the answer merely by recognizing English/Turkish spelling similarities.
    3. MATERIAL FIDELITY: Only use words and facts found in the SOURCE MATERIAL.
    4. HOMOGENEITY RULE (CRITICAL): All 4 options (answer + 3 distractors) MUST be the EXACT SAME grammatical type, sentence structure, and format.
       - If the correct answer is a QUESTION (e.g. "¿Cuánto cuesta?"), then ALL 3 distractors MUST ALSO be questions (e.g. "¿Dónde está?", "¿Cómo se llama?", "¿Qué hora es?").
       - If the correct answer is a STATEMENT, all distractors must also be statements.
       - If the correct answer is a VERB FORM, all distractors must also be verb forms.
       - If the correct answer is a NOUN, all distractors must also be nouns.
       - NEVER mix questions with statements, nouns with verbs, or phrases with single words. The student must NOT be able to identify the correct answer just by looking at the format.
    5. SITUATIONAL FLUENCY: Avoid 'Dictionary Definitions'. Instead of asking 'What is X?', create a scenario, dialogue, or communicative situation. 
    6. TRICKY DISTRACTORS: Each distractor must be a plausible alternative that a {level} student might genuinely confuse with the correct answer. Distractors should be from the SAME semantic domain (e.g. all food items, all question phrases, all time expressions).
    7. LINGUISTIC VERACITY: Logic must be 100% correct for {language}. Never hallucinate sound-to-letter or grammar rules.
    8. NO CLUES: The correct answer MUST NOT be distinguishable from distractors by length, formatting, punctuation, or grammatical type. A student should ONLY be able to answer correctly if they know the material.
    
    RESPONSE FORMAT:
    Output EXCLUSIVELY a JSON object. Every prompt MUST have a {instruction_lang_name} 'translation' in the 'translation' field."""

    user = f"""TASK: Generate EXACTLY {gen_count} unique {topic_type} questions.
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
          "translation": "{instruction_lang_name} translation",
          "answer": "...",
          "distractors": ["...", "...", "..."],
          "why": "{instruction_lang_name} explanation"
        }}
      ]
    }}"""
    
    if is_quiz and is_beginner:
        user += f"\n\nSTRICT {instruction_lang_name.upper()} PROMPT RULE: This is a QUIZ for {level} beginners. You MUST write the 'prompt' field in {instruction_lang_name}. The 'answer' and 'distractors' MUST be in {language}."
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
        
        # ── V5 RIGOROUS VALIDATION & ANTI-GIVEAWAY FILTER ──
        final = []
        for item in raw_list:
            if not isinstance(item, dict): continue
            
            p = str(item.get("prompt", "")).strip()
            a = str(item.get("answer", "")).strip()
            d = item.get("distractors", [])
            
            if not (p and a and isinstance(d, list) and len(d) >= 3):
                continue

            # Programmatic Anti-Giveaway & Anti-Trivia Verification
            clean_p = re.sub(r'[^\w\s]', ' ', p.lower())
            clean_a = re.sub(r'[^\w\s]', ' ', a.lower()).strip()
            
            is_giveaway = False
            if len(clean_a) >= 2:
                # Direct word match of the answer in prompt
                if f" {clean_a} " in f" {clean_p} ":
                    is_giveaway = True
                # Match any individual word in multi-word answer (excluding common stopwords)
                stopwords = {"el", "la", "los", "las", "un", "una", "de", "en", "a", "y", "o", "the", "a", "an", "of", "in", "to", "and", "or", "bir", "ve", "veya", "ile"}
                for w in clean_a.split():
                    if len(w) > 3 and w not in stopwords and f" {w} " in f" {clean_p} ":
                        is_giveaway = True
                        break
            
            # Reject meta-trivia about letter names or strings
            trivia_indicators = [
                "nombre que incluye", "se llama", "name includes", "includes the word",
                "harfinin adı", "kelimesini içerir", "which letter has the name",
                "cuál de estas letras tiene un nombre", "letter's name", "name of the letter",
                "how is the letter named", "harfi nasıl adlandırılır"
            ]
            if any(t in clean_p for t in trivia_indicators):
                is_giveaway = True

            # Reject transparent cognate giveaways (e.g. multiplication -> multiplicación)
            trans_text = str(item.get("translation", "")).strip()
            if is_transparent_cognate_giveaway(p, trans_text, a):
                is_giveaway = True
                print(f"[REJECTED COGNATE GIVEAWAY] Prompt: '{p}' | Translation: '{trans_text}' | Answer: '{a}'")
                
            if is_giveaway:
                print(f"[REJECTED GIVEAWAY/TRIVIA QUESTION] Prompt: '{p}' | Answer: '{a}'")
                continue

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
            if len(final) >= c:
                break
        
        if not final:
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-EMPTY] Gemini returned no valid questions for {topic_title}\n")
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

def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, model_override=None, material_language="en"):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions, is_pdf_source=is_pdf_source, model_override=model_override, material_language=material_language)

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, material_language="en"):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions, is_pdf_source=is_pdf_source, material_language=material_language)

def ai_grade_open_response(question, student_answer, correct_answer):
    prompt = f"Grade: Q:{question}, C:{correct_answer}, S:{student_answer}. JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150)
    return (result.get("score", 0.0), result.get("feedback", "")) if result else (0.0, "")

def ai_generate_curriculum(language, level, prompt_extra=""):
    """Generates course structure, creating both English and Turkish versions natively via AI."""
    # Only use blueprint cache if no custom course name / prompt_extra is provided
    if not prompt_extra:
        cache_file = _get_blueprint_path(language, level)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    if cached_data and "chapters" in cached_data:
                        from services.curriculum_translator import ensure_bilingual_curriculum
                        return ensure_bilingual_curriculum(cached_data["chapters"])
            except Exception: pass

    system = f"""You are a world-class bilingual curriculum architect and expert linguist specializing in the CEFR framework (A1-C2) for {language}. 
    Your mission: Design a comprehensive, pedagogically deep, and culturally rich roadmap for learning {language}.
    
    CRITICAL BILINGUAL GENERATION REQUIREMENT:
    You MUST generate BOTH language versions natively in the exact same output:
    1. 'title': The professional English curriculum title (e.g., 'Polite Expressions for Conversation', 'Everyday Survival Vocabulary').
    2. 'title_tr': The authentic, natural Turkish curriculum title (e.g., 'Sohbet İçin Nezaket İfadeleri', 'Günlük Hayatta Kalma Kelimeleri').
    
    STRICT LINGUISTIC RULES FOR 'title_tr':
    - Every 'title_tr' must be 100% natural, grammatically correct Turkish as written by an educated Turkish teacher.
    - NEVER leave English words in 'title_tr' (e.g. NEVER write 'Nazik İfadeler for Conversation' or 'Traveling İçin Temel Kelimeler').
    - NEVER duplicate words (e.g. NEVER write 'Günlük Hayatta Hayatta Kalma' or 've ve').
    - Target language verbs or grammatical markers (like 'ser', 'estar') stay in single quotes: e.g. "'Ser' Kullanarak Kimliği Tanımlama".
    - PEDAGOGIC DEPTH: Go beyond simple vocabulary. Each topic should feel like a real lesson that covers functional usage, nuances, and situational grammar."""
    
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

    user = f"""Create a comprehensive {level} {language} course syllabus{f' focusing on: {prompt_extra}' if prompt_extra else ''}.
LEVEL-SPECIFIC FOCUS: {current_guideline}

RULES:
1. PEDAGOGICAL ACCURACY: The topics MUST strictly reflect the {level} level requirements.
2. NO GENERIC TITLES: Do NOT use 'Vocabulary', 'Grammar', or 'Exercises'. Every topic must be descriptive (e.g., 'Navigating a Hospital', 'The Imperfect vs. Preterite', 'Debating Environmental Ethics').
3. PROGRESSION: Ensure units move logically from foundational to complex within the {level} bracket.
4. VARIETY: Mix functional language, grammar, and cultural context.
5. MANDATORY SCOPE: Generate EXACTLY 8 to 12 chapters to ensure full curriculum coverage. A roadmap with fewer than 8 units is unacceptable.
6. TOPIC DENSITY: Each chapter MUST have at least 3-4 descriptive topics.
7. BILINGUAL PAIRS (MANDATORY): For every chapter and topic, provide BOTH English ('title') and Turkish ('title_tr'):
   - Example 1: 'title': 'Polite Expressions for Conversation' -> 'title_tr': 'Sohbet İçin Nezaket İfadeleri'
   - Example 2: 'title': 'Basic Adjectives for Personal Description' -> 'title_tr': 'Kişisel Tanım İçin Temel Sıfatlar'
   - Example 3: 'title': 'Everyday Survival Vocabulary' -> 'title_tr': 'Günlük Hayatta Kalma Kelimeleri'
   - Example 4: 'title': 'Essential Vocabulary for Traveling' -> 'title_tr': 'Seyahat İçin Temel Kelimeler'
   - Example 5: 'title': "Using 'Ser' to Describe Identity" -> 'title_tr': "'Ser' Kullanarak Kimliği Tanımlama"
   - Every word in 'title_tr' must be 100% Turkish. No English leakages. No word duplications.

Return ONLY valid JSON:
{{
  "chapters": [
    {{
      "number": 1,
      "title": "Everyday Survival Vocabulary",
      "title_tr": "Günlük Hayatta Kalma Kelimeleri",
      "topics": [
        {{
          "title": "Polite Expressions for Conversation",
          "title_tr": "Sohbet İçin Nezaket İfadeleri",
          "type": "vocabulary"
        }}
      ]
    }}
  ]
}}"""
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
            "title_tr": "Alfabe ve Temel Bilgiler",
            "topics": [
                {"title": "The Alphabet", "title_tr": "Alfabe", "type": "vocabulary"},
                {"title": "Vowels and Consonants", "title_tr": "Sesli ve Sessiz Harfler", "type": "grammar"},
                {"title": "Pronunciation and Phonetics", "title_tr": "Telaffuz ve Fonetik", "type": "grammar"}
            ]
        }
        filtered_chapters.insert(0, alphabet_unit)
        
        # 3. Re-index and Clean Titles
        for i, ch in enumerate(filtered_chapters):
            ch["number"] = i + 1
            if i > 0 and "title" in ch:
                ch["title"] = re.sub(r'^Unit\s*\d+\s*[:\-]*\s*', '', ch["title"], flags=re.IGNORECASE).strip()
        
        chapters = filtered_chapters
    
    # ── BILINGUAL TITLE ENRICHMENT: Ensure both title (EN) and title_tr (TR) are populated cleanly ──
    from services.curriculum_translator import ensure_bilingual_curriculum
    chapters = ensure_bilingual_curriculum(chapters)

    # ── AUTO-CACHE: Save the generated blueprint so "Clear Cached Blueprints" works ──
    if chapters:
        save_blueprint_cache(language, level, chapters)
    
    return chapters
def ai_generate_report_insights(cohort_data):
    """Generates high-level pedagogical insights for teacher reports."""
    prompt = f"Analyze student performance and provide 3 actionable teaching insights: {json.dumps(cohort_data)}"
    res = _call_ai([{"role": "user", "content": prompt}], max_tokens=600)
    return res.get("explanation", "Insufficient data for insights.") if res else "Connection Error."

def generate_full_lesson(topic, topic_type, language, count=6, level='A1', source_text=None, material_language="en"):
    """Generates a complete structured lesson, using source_text as the primary source if provided."""
    from services.language_data import get_reference_prompt, get_special_chars_prompt, get_pedagogical_guidelines, ALPHABETS
    
    is_alphabet_topic = any(x in topic.lower() for x in ["alphabet", "alfabeto", "alfabe", "letters"])
    is_beginner = any(lvl in level.upper() for lvl in ["A1", "A2"])
    instruction_lang_name = "Turkish" if material_language == "tr" else "English"
    
    pedagogy_guidance = get_pedagogical_guidelines(language, level)
    
    lang_guard = f"REQUIRED BILINGUAL SPLIT: All instructional text, titles, and grammar explanations MUST be in {instruction_lang_name}. All target language content (vocabulary, sentences, examples) MUST be in {language}."
    if is_beginner:
        lang_guard = f"STRICT BEGINNER REQUIREMENT: You are teaching {level} beginners. All titles, grammar explanations, and instructions MUST be in {instruction_lang_name}. NEVER explain {language} concepts using {language}. Use {instruction_lang_name} as the primary instructional medium."

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
        ref_data += f"\nPRONUNCIATION RULE: Explain how these marks affect sound using {instruction_lang_name} phonetics."

    min_pages = 5

    # ── PHONETIC & PEDAGOGICAL GUARDRAILS ──
    no_english_in_lists = f"""
NO {instruction_lang_name.upper()} IN LISTS (CRITICAL): 
- NEVER include {instruction_lang_name} translations as separate items in a list of strings. 
- All items in a 'list' or 'items' array MUST be in the target language if they are strings. 
- If you want to provide a translation, use the OBJECT format: {{'term': '...', 'translation': '...', 'explanation': '...'}} or {{'text': '...', 'meaning': '...'}}. 
- ALWAYS generate: [{{'term': 'Word', 'translation': 'Translation', 'explanation': 'Brief 1-sentence pedagogical explanation'}}, ...]."""
    explanatory_items_mandate = f"""
PEDAGOGICALLY USEFUL ITEMS MANDATE (CRITICAL):
- In 'items' arrays, every item MUST provide practical language learning value.
- STRICT BAN ON TAUTOLOGICAL DEFINITIONS:
  * NEVER write circular dictionary definitions that explain basic human activities or physical reality!
  * FORBIDDEN EXAMPLES:
    - "Okumak: Kitap, makale vb. okumak eylemini ifade eder." (USELESS TAUTOLOGY)
    - "Çizmek: Bir yüzey üzerinde resim yaratmayı ifade eder." (USELESS TAUTOLOGY)
    - "Oynamak: Oyun veya spor etkinliklerini ifade etmek için kullanılır." (USELESS TAUTOLOGY)
    - "Refers to the act of reading/drawing/playing." (USELESS TAUTOLOGY)
  * Adult learners already know what reading, drawing, or playing means in real life.
- INSTEAD, every vocabulary item MUST include:
  1. 'example': A natural, authentic target-language example sentence in {language} showing the word in everyday context.
  2. 'example_en': Natural English translation of the example sentence.
  3. 'example_tr': Natural Turkish translation of the example sentence.
  4. 'explanation' (English) & 'explanation_tr' (Turkish): A PRACTICAL LINGUISTIC TIP ONLY (such as prepositions used with it e.g. 'jugar a', 'viajar en', irregular forms, common collocations, or false friends). If no special collocation applies, leave concise or provide a key phrase.
- ALPHABET & LETTER ITEMS:
  * For alphabet topics or letter items:
    - 'term': The uppercase letter (e.g. 'H', 'I', 'J', 'Ñ', 'Z')
    - 'name': Authentic native name of the letter (e.g. 'Hache', 'I', 'Jota', 'Eñe', 'Zeta')
    - 'phonetic_en': English-speaker phonetic pronunciation guide (e.g. '[AH-cheh] (silent)', '[ee]', '[HOH-tah]', '[EH-nyeh]', '[SEH-tah / THEH-tah]')
    - 'phonetic_tr': Turkish-speaker phonetic pronunciation guide (e.g. '[açe] (sessiz harf, okunmaz)', '[i]', '[hota] (boğazdan h)', '[enye]', '[seta / peltek s]')
    - 'example': An authentic target-language example word (e.g. 'Hola', 'Isla', 'Jardín', 'Niño')
    - 'translation': English meaning of the example word
    - 'translation_tr': Turkish meaning of the example word
"""
    density_mandate = """
CONTENT DENSITY MANDATE (CRITICAL): 
- VOCABULARY: Minimum 10 items per vocabulary page. Cover primary, secondary, and tertiary nuances.
- EXAMPLES: Minimum 10 example sentences or dialogue lines. Show the words in varied social contexts.
- EXPLANATIONS: Every 'explanation' or 'text' field MUST contain at least 5-8 detailed bullet points. Explain usage, cultural context, common learner mistakes, and pronunciation tips.
- NO THIN PAGES: If a page feels light, combine it or expand it. Every page must be packed with educational value. Aim for 'Smartboard Density' — enough to fill a large screen with useful info."""
    simplicity_rule = f"""
BEGINNER SIMPLICITY RULE (A1-A2): 
1. NO TECHNICAL JARGON: Avoid linguistics terms like 'voiced/voiceless', 'front/back vowels', or 'agglutinative' unless you explain them with simple physical metaphors (e.g., instead of 'voiceless', say 'a soft breathy sound').
2. PHYSICAL CUES: For sounds with no English/Turkish equivalent (like Turkish 'ı', German 'ü', or French 'r'), provide physical instructions. Example for 'ı': 'Keep your mouth slightly open and teeth together, like the sound you make when you see something gross (ugh!) but shorter.'
3. RELATABILITY: Always relate foreign concepts to something a native {instruction_lang_name} speaker does naturally. Every single letter or grammar rule must have a '{instruction_lang_name}-Friendly Tip' that makes it feel easy, not academic."""
    contrast_rule = """
TOPIC CONTRAST RULE (MANDATORY): 
- If the topic is 'Alphabet', focus on sound-to-letter correspondence, recognizing characters in authentic vocabulary words, and distinguishing tricky letter pairs. NEVER ask shallow trivia about the names of letters or string patterns.
- If the topic is 'Pronunciation', focus on phonetic sounds, silent letters, minimal pairs, and stress patterns in real words.
- If the topic is 'Greetings', focus on pragmatic competence, social hierarchies, and communicative context (formal vs. informal, time of day).
- REPETITION CHECK: Before generating a question, ensure it tests authentic linguistic competence and never gives away the answer."""
    differentiation_rule = """
TOPIC DIFFERENTIATION RULE (CRITICAL): 
- UNIQUE QUESTIONS: NEVER reuse generic questions across related topics. Questions must be 'Laser-Focused' on the specific title of the topic.
- NUANCE: For 'Alphabet' topics, test recognition of letters within authentic words, sound-symbol mappings, and diacritics. For 'Pronunciation' topics, focus strictly on phonetic sounds, vowel length, oral stress, and sound comparisons.
- STRICT ANTI-GIVEAWAY MANDATE: The prompt must NEVER contain the answer word, and NEVER ask what word is contained in a letter's name (e.g. NEVER ask which letter has 'doble' in its name)."""
    depth_rule = f"""
MCQ EXPLANATION DEPTH (CRITICAL): 
- NEVER restate the question or the answer (e.g., DO NOT say 'Choose the correct greeting').
- ALWAYS provide a 'Linguistic Reasoning': Explain WHY the correct answer fits the context and briefly WHY the distractors are incorrect for that specific context.
- Example: Instead of 'Choose the name phrase', explain the correct choice and why alternatives do not fit in {instruction_lang_name}."""
    accuracy_rule = """
PEDAGOGICAL ACCURACY RULE (CRITICAL): 
1. NO AMBIGUITY: When creating MCQs, ensure distractors are CLEARLY incorrect. Avoid 'trick' questions where multiple answers could be technically correct (e.g., don't mark a neutral greeting wrong in a formal context unless a strictly formal option is the ONLY correct choice).
2. CONTEXT-RICH PROMPTS: Questions must provide enough context (time of day, social setting, relationship) to make the correct answer the ONLY logical choice.
3. LANGUAGE-AGNOSTIC PRECISION: This rule applies to all languages. Do not use generic greetings as distractors for specific questions if they could be used correctly in that scenario."""
    phonetic_rule = f"""
PHONETIC APPROXIMATION RULE (CRITICAL): When explaining how letters or words sound, 
NEVER use target language spellings to describe the sound (e.g., DO NOT say 'Ç sounds like çe'). 
Instead, ALWAYS use common {instruction_lang_name} word approximations that a student can understand 
(e.g., 'Ç sounds like the ch in church', or 'Ş sounds like the sh in sheep' for English-speakers; or Turkish equivalents for Turkish-speakers). 
This rule is language-agnostic: always relate sounds to common, accessible words in {instruction_lang_name}."""

    natural_pragmatics_rule = f"""
NATURAL PRAGMATICS & CULTURAL LOCALIZATION (MANDATORY):
- When translating greetings to {instruction_lang_name} (e.g. Turkish), NEVER use unnatural literal translations or word-for-word calques (e.g. NEVER use 'İyi öğleden sonra' or 'İyi öğleden sonraları' in Turkish). ALWAYS use culturally authentic, native greetings in {instruction_lang_name} (e.g. for Turkish: 'Tünaydın', 'Günaydın', 'İyi akşamlar', 'İyi geceler'; for English: 'Good afternoon', 'Good morning', etc.).
- PRONOUN VS AUXILIARY VERB DISTINCTION: Subject pronouns (Spanish 'Yo', German 'ich', French 'je', Italian 'io', English 'I') translate to 'Ben' in Turkish (never 'I'). Conjugated auxiliary verbs (Spanish 'Soy', German 'bin', French 'suis', Italian 'sono', English 'I am') translate to '(Ben) ...yim / ...yım', NEVER bare 'Ben'. Always maintain clear pedagogical separation between personal pronouns and verb conjugations.
- CEFR LEVEL RIGOR:
  * A1/A2: Explicit phonetic guidance, clean vocabulary, foundational morphological markers, everyday communicative situations.
  * B1/B2: Nuanced grammatical contrasts (indicative vs subjunctive, past aspectual contrasts), discourse connectors, authentic dialogues.
  * C1/C2: Advanced stylistic sophistication, native idioms, colloquialisms vs academic register, nuanced pragmatics, rhetorical mastery, and complex syntactic subordination.
- In instructional texts, always use native, idiomatic phrasing suitable for professional educational textbooks.
"""

    dual_bilingual_mandate = f"""
DUAL-NATIVE BILINGUAL PEDAGOGY MANDATE (CRITICAL):
- You MUST author BOTH natural English and natural Turkish pedagogical content in EVERY page of the lesson.
- Both language versions must be authored with authentic educational depth as an experienced language educator:
  * English fields: 'title', 'text', 'explanation', 'translation', 'explanation' (in items), 'prompt' (in mcq).
  * Turkish fields: 'title_tr', 'text_tr', 'explanation_tr', 'translation_tr', 'explanation_tr' (in items), 'prompt_tr' (in mcq).
- STRICT ZERO-CALQUE MANDATE FOR TURKISH:
  * NEVER write literal, robotic word-for-word machine translations!
  * Write authentic Turkish grammar explanations using proper educational terminology:
    - Example for 'gustar':
      * Good Turkish: "• Sevilen veya hoşlanılan eylemleri belirtirken 'me gusta' kalıbından sonra mastar fiil (infinitive) kullanılır (örneğin: 'me gusta leer')."
      * Good Turkish: "• Daha güçlü bir beğeni veya tutkuyu belirtmek için 'me encanta' ifadesi tercih edilir (örneğin: 'me encanta viajar')."
      * Good Turkish: "• Hoşlanılan nesne çoğul olduğunda fiil 'me gustan' şeklinde çoğul kullanılır (örneğin: 'me gustan las películas')."
      * Good Turkish: "• Gustar yapısında fiil çekiminin (gusta/gustan), beğenen kişiye göre değil, beğenilen nesnenin tekil ya da çoğul olmasına göre belirlendiğini unutmayın."
    - Bad calques to strictly avoid: "me gusta + mastar fiil kullanarak keyif almak için ifade edin", "Fiil formunu öznenin tercihine göre eşleştirmeyi unutmayın".
"""

    system = f"""You are a master {language} pedagogical designer. 
    STRICT IDENTITY: You write high-quality, CEFR-aligned lessons. Your goal is MEANINGFUL TEACHING, not meeting a page count.
    
    {pedagogy_guidance}
    
    DUAL BILINGUAL MANDATE: {dual_bilingual_mandate}
    FORMATTING RULE: All explanations MUST be formatted as concise BULLET POINTS. No walls of text.
    SMARTBOARD RULE: Lessons are taught on large smartboards. You MUST break all paragraphs into clear, scannable bullet points so students can read them from the back of a classroom. 
    EXPLANATORY RULE: Every page MUST include helpful bullet-point explanations in BOTH English ('explanation' / 'text') and Turkish ('explanation_tr' / 'text_tr').
    FORBIDDEN CONTENT: Never create a page named "Material" or use "Material" as a title. No filler or nonsense pages. NO LONG PARAGRAPHS.
    PEDAGOGICAL TYPES: Only use "vocabulary", "grammar", "examples", and "mcq" types.
    MCQ RULE: In 'mcq' pages, 'explanation' and 'explanation_tr' are pedagogical post-answer feedback explaining the underlying grammar or vocabulary rule. NEVER write meta-phrases like 'The correct answer is...' or 'Doğru cevap...'.
    STRICT ANTI-GIVEAWAY MANDATE: The question prompt MUST NEVER contain the correct answer or give away the answer. Distractors must be homogeneous and plausible. NEVER ask shallow trivia about what string is inside a letter name.
    NATURAL PRAGMATICS RULE: {natural_pragmatics_rule}
    EXPLANATORY ITEMS MANDATE: {explanatory_items_mandate}
    PHONETIC RULE: {phonetic_rule}
    ACCURACY RULE: {accuracy_rule}
    DEPTH RULE: {depth_rule}
    DIFFERENTIATION RULE: {differentiation_rule}
    CONTRAST RULE: {contrast_rule}
    SIMPLICITY RULE: {simplicity_rule}
    DENSITY MANDATE: {density_mandate}
    NO {instruction_lang_name.upper()} IN LISTS: {no_english_in_lists}
    JSON EFFICIENCY: Return MINIFIED JSON only (no whitespace, no indentation).
    NO CONVERSATION: Provide ONLY the JSON structure."""

    user = f"""Write a comprehensive {level} lesson to teach {language} topic: '{topic}' ({topic_type}).
    {source_rule}
    {alphabet_rule}
    {ref_data}

    TECHNICAL SPECS:
    1. DUAL BILINGUAL AUTHORING: Provide both English and natural Turkish pedagogical content for EVERY page.
    2. TARGET LANGUAGE ENFORCEMENT: 'term' and 'text' in example lists MUST be in {language}.
    3. BULLET POINTS ONLY: Format all grammar and context 'text' / 'text_tr' or 'explanation' / 'explanation_tr' fields as concise bullet points.
    4. SCRIPT CONSISTENCY: Use the correct alphabet for {language}.
    5. MEANINGFUL LENGTH: Generate 4-6 high-density, essential pages.
    6. NO FILLER: Every page must be packed with pedagogical value.
    7. ZERO CALQUES: Ensure all Turkish explanations are authentic, idiomatic, and educational.
    8. EXPLANATORY ITEMS: For every item in 'items', provide both 'explanation' (English) and 'explanation_tr' (Turkish).
    
    RESPONSE FORMAT (VALID JSON ONLY):
    {{
      "pages": [
        {{ 
          "type": "vocabulary", 
          "title": "Essential Vocabulary", 
          "title_tr": "Temel Kelimeler", 
          "explanation": "• Deep English explanation of how to use these terms\\n• Cultural or grammatical nuances", 
          "explanation_tr": "• Bu terimlerin kullanımını ve dilbilgisel inceliklerini açıklayan doğal Türkçe pedagojik rehber", 
          "items": [ 
            {{ 
              "term": "...", 
              "translation": "English meaning", 
              "translation_tr": "Doğal Türkçe anlamı", 
              "example": "Natural example sentence in {language}",
              "example_en": "Natural English translation of the example sentence",
              "example_tr": "Örnek cümlenin doğal Türkçe çevirisi",
              "explanation": "Practical tip: prepositions, collocations, or irregular forms (NEVER say 'refers to the act of...')", 
              "explanation_tr": "Kullanım püf noktası: edatlar, kalıplar veya kural (ASLA '... eylemini ifade eder' gibi gereksiz tanımlar yazmayın)" 
            }}
          ] 
        }},
        {{ 
          "type": "grammar", 
          "title": "Structural Focus", 
          "title_tr": "Yapısal Dilbilgisi Kuralları", 
          "text": "• Clear bullet-point Rule 1 in English\\n• Rule 2 with English context", 
          "text_tr": "• Net ve anlaşılır Türkçe kural maddesi 1\\n• Doğal öğretmen üslubuyla yazılmış Türkçe kural maddesi 2" 
        }},
        {{ 
          "type": "examples", 
          "title": "Practical Application", 
          "title_tr": "Pratik Uygulama", 
          "explanation": "• How these sentences work in real life", 
          "explanation_tr": "• Bu cümlelerin günlük hayattaki kullanımını anlatan Türkçe açıklama", 
          "list": [ 
            {{ 
              "speaker": "A", 
              "text": "Sentence in {language}", 
              "translation": "English translation", 
              "translation_tr": "Doğal Türkçe çeviri" 
            }}, 
            {{ 
              "speaker": "B", 
              "text": "Response in {language}", 
              "translation": "English translation", 
              "translation_tr": "Doğal Türkçe çeviri" 
            }} 
          ] 
        }},
        {{ 
          "type": "mcq", 
          "prompt": "Question prompt in English", 
          "prompt_tr": "Doğal Türkçe soru metni", 
          "explanation": "• Reasoning in English", 
          "explanation_tr": "• Doğru cevabın dilbilgisel gerekçesini açıklayan Türkçe pedagojik açıklama", 
          "answer": "...", 
          "distractors": ["...", "...", "..."] 
        }}
      ]
    }}"""

    def _clean_pages(lesson_dict):
        if not lesson_dict or "pages" not in lesson_dict: return lesson_dict
        from services.concept_explanations import heal_concept_item, heal_pragmatic_item
        cleaned = []
        for p in lesson_dict.get("pages", []):
            if p.get("type") == "mcq":
                prompt_txt = str(p.get("prompt", "")).lower()
                ans_txt = str(p.get("answer", "")).lower().strip()
                clean_p = re.sub(r'[^\w\s]', ' ', prompt_txt)
                clean_a = re.sub(r'[^\w\s]', ' ', ans_txt).strip()
                if len(clean_a) > 2 and f" {clean_a} " in f" {clean_p} ":
                    continue  # Skip giveaway
                if is_transparent_cognate_giveaway(prompt_txt, "", ans_txt):
                    continue  # Skip transparent cognate giveaway
                trivia_indicators = ["nombre que incluye", "se llama", "name includes", "includes the word", "harfinin adı", "kelimesini içerir", "cuál de estas letras tiene un nombre"]
                if any(x in clean_p for x in trivia_indicators):
                    continue  # Skip trivia

                # Clean MCQ feedback in both languages
                for expl_field in ["explanation", "explanation_tr"]:
                    if expl_field in p and isinstance(p[expl_field], str):
                        expl_val = p[expl_field]
                        expl_val = re.sub(r"(?i)\bthe\s+correct\s+answer\s+is\s+.*?(?:\.|$)", "", expl_val).strip()
                        expl_val = re.sub(r"(?i)\bthe\s+alternatives?\s+(?:do\s+not|are)\s+.*?(?:\.|$)", "", expl_val).strip()
                        expl_val = re.sub(r"(?i)\bdoğru\s+cevap\s+.*?(?:\.|$)", "", expl_val).strip()
                        p[expl_field] = expl_val

            # Ensure both title and title_tr exist
            if not p.get("title_tr") and p.get("title"):
                from services.language_data import _get_bm_title_map
                bm_titles = _get_bm_title_map()
                p["title_tr"] = bm_titles.get(p["title"], p["title"])

            # Ensure both text and text_tr / explanation and explanation_tr exist
            if p.get("text") and not p.get("text_tr"):
                p["text_tr"] = p["text"]
            if p.get("explanation") and not p.get("explanation_tr"):
                p["explanation_tr"] = p["explanation"]

            # Pedagogical item explanation enrichment & self-healing
            from services.language_data import get_letter_phonetics, get_vocab_example
            tautology_re = re.compile(
                r'(?i)\b(?:eylemini\s+ifade\s+eder|etkinliğini\s+ifade\s+eder|ifade\s+etmek\s+için\s+kullanılır|'
                r'eylemidir|yapma\s+eylemi|resim\s+yaratmayı|üretme\s+eylemidir|gitmeyi\s+içerir|'
                r'refers?\s+to\s+the\s+act\s+of|means?\s+the\s+act\s+of|is\s+the\s+act\s+of|used\s+to\s+express\s+the\s+action\s+of)\b'
            )

            for list_key in ["items", "vocabulary", "words", "list", "dialogue", "examples"]:
                arr = p.get(list_key)
                if isinstance(arr, list):
                    filtered_arr = []
                    for it in arr:
                        if isinstance(it, dict):
                            heal_concept_item(it, lang="en")
                            heal_concept_item(it, lang="tr")

                            term_str = str(it.get("term") or it.get("word") or it.get("letter") or "").strip()
                            # 1. Letter healing: alphabet phonetics & eliminate pronoun bleed
                            if is_alphabet_topic or len(term_str) == 1:
                                phon_data = get_letter_phonetics(language, term_str)
                                if phon_data:
                                    it["name"] = phon_data["name"]
                                    it["phonetic_en"] = phon_data["phonetic_en"]
                                    it["phonetic_tr"] = phon_data["phonetic_tr"]
                                    if not it.get("example") and phon_data.get("example"):
                                        it["example"] = phon_data["example"]
                                # Strip pronoun bleed from letter I
                                if term_str.upper() == "I":
                                    for k in ["explanation", "explanation_en", "explanation_tr"]:
                                        if "pronoun" in str(it.get(k, "")).lower() or "zamir" in str(it.get(k, "")).lower():
                                            it[k] = ""
                                    if it.get("translation") == "Ben":
                                        it["translation"] = "i"
                                    if it.get("translation_tr") == "Ben":
                                        it["translation_tr"] = "i"

                            # 2. Strip tautologies
                            for k in ["explanation", "explanation_en", "explanation_tr"]:
                                if k in it and isinstance(it[k], str) and tautology_re.search(it[k]):
                                    it[k] = ""

                            # 3. Enrich vocabulary with authentic example sentence & practical tip if missing
                            bank_hit = get_vocab_example(language, term_str)
                            if bank_hit:
                                if not it.get("example"):
                                    it["example"] = bank_hit["example"]
                                if not it.get("example_en"):
                                    it["example_en"] = bank_hit["example_en"]
                                if not it.get("example_tr"):
                                    it["example_tr"] = bank_hit["example_tr"]
                                if not it.get("explanation") or tautology_re.search(str(it.get("explanation", ""))):
                                    it["explanation"] = bank_hit["tip_en"]
                                if not it.get("explanation_tr") or tautology_re.search(str(it.get("explanation_tr", ""))):
                                    it["explanation_tr"] = bank_hit["tip_tr"]

                            filtered_arr.append(it)
                        elif isinstance(it, str):
                            s = it.strip()
                            # If it is a sentence or bullet rule, move it out of vocabulary items into text
                            if s.startswith(('•', '-', '*')) or len(s.split()) > 4 or len(s) > 35:
                                existing_text = p.get("text") or p.get("explanation") or ""
                                if s not in existing_text:
                                    p["text"] = f"{existing_text}\n{s}".strip()
                            else:
                                filtered_arr.append(it)
                    p[list_key] = filtered_arr

            cleaned.append(p)
        lesson_dict["pages"] = cleaned
        return lesson_dict

    res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=4000, temperature=0.4)
    if res and "pages" in res:
        return _clean_pages(res)
    # If primary model failed entirely, try fallback once
    if MODEL_FALLBACK:
        res2 = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_FALLBACK, max_tokens=4000, temperature=0.4)
        if res2 and "pages" in res2:
            return _clean_pages(res2)
    return {"pages": []}

def ai_explain_word(word, language, context=None, material_language="en"):
    instruction_lang_name = "Turkish" if material_language == "tr" else "English"
    system = f"You are a helpful {language} language teacher. Explain terms to students clearly and concisely in {instruction_lang_name}."
    user = f"""Explain the {language} term: '{word}'. 
    CONTEXT: {context}
    
    STRICT RULES:
    1. The 'explanation', 'usage', and 'tip' fields MUST be written in {instruction_lang_name}.
    2. Only the target word itself can be in {language}.
    3. Keep it brief and pedagogical.
    
    Return ONLY valid JSON: {{'explanation': '...', 'usage': '...', 'tip': '...'}}"""
    return _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=600)

def ai_explain_activity(prompt, correct_answer, student_answer, language, material_language="en"):
    clean_lang = language.split('(')[0].strip()
    instruction_lang_name = "Turkish" if material_language == "tr" else "English"
    system = f"""You are a helpful {clean_lang} language teacher explaining mistakes to students.
CRITICAL LANGUAGE RULES:
1. Your explanation text MUST be written ENTIRELY in {instruction_lang_name}.
2. You may quote specific {clean_lang} words (e.g., the answer or question terms) but ALL explanatory sentences MUST be in {instruction_lang_name}.
3. NEVER write full sentences in {clean_lang}.
4. Keep the explanation concise (2-3 sentences max)."""
    user = f"""A student got a {clean_lang} question wrong. Explain the mistake and the correct logic.

Question: {prompt}
Correct Answer: {correct_answer}
Student's Answer: {student_answer}

Return ONLY valid JSON: {{"explanation": "Your {instruction_lang_name} explanation here"}}"""
    return _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_NARRATIVE, max_tokens=300)

def _get_blueprint_path(language, level):
    cache_dir = os.path.join("services", "blueprints")
    if not os.path.exists(cache_dir): os.makedirs(cache_dir)
    clean_lang = "".join(filter(str.isalnum, language.split('(')[0])).lower()
    clean_level = "".join(filter(str.isalnum, level)).lower()
    return os.path.join(cache_dir, f"{clean_lang}_{clean_level}.json")

def save_blueprint_cache(language, level, chapters):
    try:
        from services.curriculum_translator import ensure_bilingual_curriculum
        clean_chapters = ensure_bilingual_curriculum(chapters)
        cache_file = _get_blueprint_path(language, level)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"chapters": clean_chapters}, f, ensure_ascii=False, indent=2)
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
