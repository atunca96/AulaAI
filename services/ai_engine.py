import os
import sys
import json
import re
import urllib.request
import urllib.error
import time
import uuid
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
MODEL_STRUCTURAL = "anthropic/claude-3-haiku" # Lowest cost per output
MODEL_NARRATIVE = "anthropic/claude-3-haiku"  # Legacy stable voice
MODEL_FALLBACK = "google/gemini-2.0-flash-lite-preview-02-05:free"

def _call_ai(messages: List[Dict], model: str = MODEL_STRUCTURAL, max_tokens: int = 1000, temperature: float = 0.7) -> Optional[Dict]:
    """OpenRouter caller with markdown cleaning and automatic retries."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key: return {"error_details": "API Key Missing"}

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}", 
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aulaai.com", # Mandatory for some OpenRouter models
        "X-Title": "AulaAI"
    }

    last_error = "Unknown"
    models_to_try = [model, MODEL_FALLBACK]
    
    for target_model in models_to_try:
        for attempt in range(2):
            try:
                if attempt > 0 or target_model != model: 
                    print(f"[AI] Switching/Retrying with {target_model}...")
                
                req = urllib.request.Request(url, data=json.dumps({
                    "model": target_model, "messages": messages, "max_tokens": max_tokens, 
                    "temperature": temperature
                }).encode("utf-8"), headers=headers)
                
                with urllib.request.urlopen(req, timeout=120) as response:
                    res_body = response.read().decode("utf-8")
                    res_json = json.loads(res_body)
                    
                    if "choices" in res_json:
                        content = res_json["choices"][0]["message"]["content"].strip()
                        # PERSISTENCE: Save raw AI output for inspection
                        try:
                            if not os.path.exists("scratch"): os.makedirs("scratch")
                            with open("scratch/last_ai_response.txt", "w", encoding="utf-8") as f:
                                f.write(content)
                        except: pass
                        
                        # LOGGING: Capture the raw content length for debugging
                        with open("pipeline.log", "a", encoding="utf-8") as f:
                            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-DEBUG] Received {len(content)} chars from {target_model}\n")
                        
                        # IRON-CLAD JSON EXTRACTION (Objects or Lists)
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
                            # SUPER SANITIZER: Remove invalid control characters (0-31) except 9, 10, 13
                            json_str = "".join(ch for ch in json_str if ord(ch) >= 32 or ch in '\n\r\t')
                            
                            def deep_clean_result(data):
                                """Recursively nukes backslashes from AI strings."""
                                if isinstance(data, str):
                                    return data.replace("\\'", "'").replace('\\"', '"').replace("\\", "").strip()
                                elif isinstance(data, list):
                                    return [deep_clean_result(i) for i in data]
                                elif isinstance(data, dict):
                                    return {k: deep_clean_result(v) for k, v in data.items()}
                                return data

                            try:
                                parsed = json.loads(json_str, strict=False)
                                return deep_clean_result(parsed)
                            except Exception as je:
                                with open("pipeline.log", "a", encoding="utf-8") as f:
                                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-ERROR] JSON Parse Error: {je}\n")
                                try:
                                    import ast
                                    parsed = ast.literal_eval(json_str)
                                    return deep_clean_result(parsed)
                                except: pass
                        
                        if len(content) > 10 and '{' not in content:
                            return {"explanation": content, "usage": "N/A", "tip": "N/A"}
                    
                    if "error" in res_json:
                        last_error = res_json["error"].get("message", "API Error")
                    else:
                        last_error = "Empty Response (No choices)"
                        
            except Exception as e:
                last_error = str(e)
                with open("pipeline.log", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-FATAL] {last_error}\n")
                time.sleep(0.5)
            
    return {"error_details": last_error}

def detect_language(text, hint=""):
    prompt = f"""
    Identify the TARGET language being taught in this textbook or curriculum. 
    For example, if this is an English book teaching German, the target language is 'German'. 
    If it's teaching Spanish to French speakers, the target language is 'Spanish'.
    Return ONLY a JSON object: {{"language": "..."}}
    
    Text: {text[:1000]}
    """
    if hint:
        prompt += f"\n(Hint: The course is named '{hint}')"
    result = _call_ai([{"role": "user", "content": prompt}], model=MODEL_STRUCTURAL, max_tokens=50)
    
    try:
        if isinstance(result, dict) and "language" in result:
            return result["language"]
        elif isinstance(result, str):
            import json
            clean_str = result.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_str)
            return parsed.get("language", "English")
    except:
        pass
    return "English"

def generate_full_lesson(topic, topic_type, language, count=6, level='A1', source_text=None):
    """Generates a complete structured lesson, using source_text as the primary source if provided."""
    import json
    from services.language_data import get_reference_prompt, get_special_chars_prompt
    
    # Match topics that need verified alphabet data
    alphabet_keywords = [
        "alphabet", "syllabary", "hiragana", "katakana", "cyrillic", "pinyin", 
        "alfabeto", "abecedario", "alfabe", "abcto", "letters", "buchstaben"
    ]
    is_alphabet_topic = any(x in topic.lower() for x in alphabet_keywords)
    
    # Match topics that need verified special character / accent / phonetics data
    special_char_keywords = [
        "accent", "special character", "diacritic", "umlaut", "trema", "diaeresis",
        "cedilla", "tilde", "circumflex", "eszett", "dakuten", "tone mark",
        "vowel sound", "consonant sound", "pronunciation", "phonetic", "phonolog"
    ]
    is_special_char_topic = any(x in topic.lower() for x in special_char_keywords)
    
    reference_data = ""
    if is_alphabet_topic:
        reference_data = get_reference_prompt(language)
    
    special_char_data = ""
    if is_special_char_topic or is_alphabet_topic:
        special_char_data = get_special_chars_prompt(language)
    
    alphabet_rule = ""
    if is_alphabet_topic and reference_data:
        alphabet_rule = f"""
    CRITICAL REQUIREMENT for Alphabets/Syllabaries:
    Since this topic is about the alphabet/syllabary in {language}, you MUST include EVERY SINGLE CHARACTER/PHONEME using the ground truth provided below. 
    {reference_data}
    - For CHINESE: Use the Pinyin initials and finals from the reference data.
    - For JAPANESE: Use the Hiragana/Katakana from the reference data.
    Skipping characters from the reference data is a pedagogical failure. Use as many 'vocabulary' pages as needed to list the ENTIRE set.
    """
    elif is_alphabet_topic:
        alphabet_rule = f"""
    This topic is about the {language} alphabet and phonetics. 
    INSTRUCTIONS:
    1. Provide a comprehensive overview: list the letters/characters, their phonetic IPA equivalents, and pronunciation guides.
    2. For isolated diacritics (like Fatha, Kasra, etc.), use a placeholder dotted circle (◌) so they are visible (e.g., ◌َ instead of just َ ).
    3. Draw on your deep knowledge of {language} phonology (IPA, stress, tones) to ensure native-level accuracy.
    4. Group characters logically across multiple 'vocabulary' pages if needed.
    """
    
    # Inject special character constraints for accent/phonetic topics
    if is_special_char_topic and special_char_data:
        alphabet_rule += f"""
    LANGUAGE-SPECIFIC CONSTRAINT:
    {special_char_data}
    You MUST use ONLY the characters listed in the reference data above. 
    Do NOT invent or include characters from other languages. This is a {language}-specific lesson.
    """
    
    level_guidance = ""
    if level == 'B1':
        level_guidance = f"IMPORTANT: This is a B1 (Intermediate) lesson. Avoid simple A1-level sentences. Use complex structures, {language} nuances, and professional/narrative vocabulary. Explanations should be more in-depth."
    elif level == 'B2':
        level_guidance = f"IMPORTANT: This is a B2 (Upper-Intermediate) lesson. Focus on advanced grammar, formal/academic register, and idiomatic expressions. Challenge the student with professional-level content."
    elif level in ['C1', 'C2']:
        level_guidance = f"IMPORTANT: This is a {level} (Advanced/Proficient) lesson. Content MUST be highly sophisticated and 100% accurate. Use professional, academic, or literary {language}. Focus on subtle nuances, complex abstractions, and near-native fluency. ZERO TOLERANCE for basic structures or inaccurate/clunky idioms."

    # BILINGUAL GUARD: Force English explanations for all levels
    lang_guard = f"REQUIRED BILINGUAL SPLIT: ALL instructional/explanatory text must be in English (including instructions, grammar explanations, teacher notes, student guidance, and activity directions). The ACTUAL learning content MUST remain in {language} (including vocabulary, examples, dialogues, model phrases, answer choices, and forms being taught)."

    source_rule = ""
    if source_text:
        source_rule = f"""
        SOURCE TEXT REQUIREMENT:
        You MUST use the following text as your EXCLUSIVE source. Format the relevant section for '{topic}'.
        
        SOURCE TEXT:
        {source_text[:10000]}
        """
    else:
        source_rule = "NO SOURCE TEXT: Use your internal knowledge to create a concise, high-value lesson. Avoid filler text. Focus on pure vocabulary and grammar facts."

    # Always use English for explanations and instructions
    primary_command = f"Write an English-instruction {level} lesson teaching {language} for: '{topic}' ({topic_type})."
    json_language_rule = f"8. JSON LANGUAGE: For 'title' and 'text' fields, you MUST use English. For 'term', 'translation', and 'speaker'/'text' inside examples, use {language} where appropriate."

    prompt = f"""
    {primary_command}
    
    {source_rule}
    
    INSTRUCTIONS:
    1. {lang_guard}
    2. {alphabet_rule}
    3. {level_guidance}
    4. REQUIREMENT: 2 to 4 high-quality pages.
    5. NO EMPTY SECTIONS: Every page MUST have detailed content.
    6. MINIMUM CONTENT: Grammar pages MUST have 3+ sentences of explanation.
    7. VARIETY: Do not repeat examples.
    {json_language_rule}
    
    Return ONLY JSON:
    {{
      "pages": [
        {{ "type": "vocabulary", "title": "...", "items": [ {{ "term": "...", "translation": "..." }} ] }},
        {{ "type": "grammar", "title": "...", "text": "..." }},
        {{ "type": "examples", "title": "...", "list": [ {{ "speaker": "...", "text": "..." }} ] }}
      ]
    }}
    """
    try:
        # ATTEMPT 1: High Detail (Using Narrative Engine)
        result = _call_ai([{"role": "user", "content": prompt}], model=MODEL_NARRATIVE, max_tokens=2500, temperature=0.4)
        if result and result.get("pages"):
            return result
            
        # ATTEMPT 2: Recovery Mode (Simplified)
        print(f"[AI] Recovery mode for {topic}...")
        recovery_cmd = f"Create a basic A1 English-instruction lesson teaching {language} about {topic}. Explanations and titles MUST be in English. Return JSON with 'pages' array containing vocabulary and grammar." if level in ['A1', 'A2'] else f"Create a basic {level} {language} lesson about {topic}. Return JSON with 'pages' array containing vocabulary and grammar."
        recovery_prompt = recovery_cmd
        result = _call_ai([{"role": "user", "content": recovery_prompt}], model=MODEL_STRUCTURAL, max_tokens=1500, temperature=0.1)
        if result and result.get("pages"):
            return result
    except Exception as e:
        print(f"Lesson Gen Error: {e}")

    return {
        "pages": [
            {
                "type": "grammar", 
                "title": "Lesson Overview", 
                "text": f"Welcome to the lesson on {topic}. In this section, we will explore the foundational concepts and essential vocabulary of {topic} in {language}.\n\n(Note: This lesson is currently in basic mode. Please refresh or check back later for the full deep-dive content)."
            }
        ]
    }

# Agnostic Engine v1.1 - Diversity Quotas Restored
def is_ai_available():
    return os.getenv("OPENROUTER_API_KEY") is not None

def get_language_profile(language):
    """Classifies languages into Pedagogical DNA profiles to drive agnostic generation."""
    logographic = ["Chinese"]
    syllabic = ["Japanese", "Russian", "Arabic", "Greek", "Korean"]
    agglutinative = ["Turkish", "Hungarian", "Finnish"]
    
    if language in logographic: return "logographic"
    if language in syllabic: return "syllabic"
    if language in agglutinative: return "agglutinative"
    return "inflected" # Default for Spanish, French, German, English, etc.

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=10, level='A1', use_quality=True, existing_questions=None, is_pdf_source=False):
    """V2: Clean activity question generator built from scratch."""
    with open("pipeline.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-START] {topic_title} count={count}\n")
    
    c = int(count)
    # Latency Optimization: Request 2x surplus instead of 4x to reduce response time
    request_count = max(c * 2, 12) 
    
    dna = get_language_profile(language)
    is_beginner = any(lvl in level.upper() for lvl in ["A1", "A2"])
    
    # PDF Rule: For PDF-based classrooms, we favor the target language for prompts 
    # to provide a more immersive experience, even at beginner levels.
    if is_pdf_source:
        instruction_lang = language
    else:
        instruction_lang = "English" if is_beginner else language
    content_str = json.dumps(topic_content, ensure_ascii=False)
    
    forbidden_clause = ""
    if existing_questions and len(existing_questions) > 0:
        qs_list = "\n".join([f"- Answer: '{q.get('answer', '')}' (Prompt: '{q.get('prompt', '')[:40]}...')" for q in existing_questions])
        forbidden_clause = f"\nEXISTING QUESTIONS TO AVOID (DO NOT TEST THESE EXACT CONCEPTS):\n{qs_list}\n"

    prompt = f"""Generate {request_count} multiple-choice questions for a {language} lesson.
    
TOPIC: {topic_title} ({topic_type})
LEVEL: {level}

SOURCE MATERIAL:
{content_str}
{forbidden_clause}
RULES:
1. Write each question prompt in {instruction_lang}.
2. ALL 4 OPTIONS IN THE SAME LANGUAGE: The answer and all 3 distractors must ALL be in the same language. Either all in {language} or all in {instruction_lang}. NEVER mix languages across options. 
   - If the correct answer is in {instruction_lang}, all 3 distractors MUST be in {instruction_lang}.
   - If the correct answer is in {language}, all 3 distractors MUST be in {language}.
   - This applies especially to translation questions. Never mix the target word and its translation in the same options list.
3. STRUCTURAL INVISIBILITY: The correct answer must be visually indistinguishable from the distractors. Same word count, same format, same grammatical category, same language. A student should NOT be able to guess the answer by looking at which option "looks different".
4. ONE BLANK ONLY: If testing with a fill-in sentence, use exactly ONE blank (___). The answer must be ONE word or ONE short phrase. Never use two blanks.
5. NO COMMA LISTS: Never join multiple words with commas as a single option. Each option is ONE coherent unit.
6. CATEGORY LOCK: If the answer is a noun, all distractors are nouns. If a verb, all verbs. If an article+noun, all are article+noun with the SAME noun. If a sentence, all are sentences of similar length.
7. NO GIVEAWAYS: Don't put the answer word inside the question. Don't make one option obviously longer/shorter than the others.
8. MAXIMUM VARIETY & RANDOMIZATION: Do NOT test items in the sequential order they appear in the source material. Pick concepts randomly from across the entire material. Vary question styles: meaning, translation, fill-in-blank, grammar selection. NEVER use the exact same set of distractors twice.
9. PLAUSIBLE WRONG ANSWERS: Distractors must be real {language} words (if options are in {language}) or real {instruction_lang} words (if options are in {instruction_lang}) that a student might confuse with the answer. Use words from the same semantic category (e.g. if the answer is a color, all distractors are colors).
10. NO META: Don't ask about dialogues, speakers, or examples. Test the language itself.
11. JSON SYNTAX: If you use quotation marks inside your prompt or answer strings, you MUST escape them (e.g., \\").

Return ONLY valid JSON:
{{"data": [{{"type": "mcq", "prompt": "...", "answer": "...", "distractors": ["...", "...", "..."]}}]}}"""

    import random
    seed = random.randint(1000, 9999)
    prompt += f"\n\nSEED: {seed}"
    
    try:
        res = _call_ai([{"role": "user", "content": prompt}], model=MODEL_STRUCTURAL, max_tokens=8000, temperature=0.9)
        raw_list = (res.get("data") if res else []) or []
        
        print(f"[AI-V2] Raw batch: {len(raw_list)} items")
            # ── VALIDATION HELPER ──
        def _validate_question(item, seen_answers, used_dist_sets, has_rich_vocab):
            if not isinstance(item, dict): return None
            
            ans = str(item.get("answer", "")).strip()
            prompt_text = str(item.get("prompt", "")).strip()
            distractors = item.get("distractors", [])
            if not isinstance(distractors, list): return None
            distractors = [str(d).strip() for d in distractors if str(d).strip()]
            
            # Hard Rejects
            if not ans or not prompt_text or len(prompt_text) < 5: return None
            if len(distractors) < 3: return None
            distractors = distractors[:3]
            
            all_opts = [ans] + distractors
            
            # Comma-joined option check
            if any("," in opt and len(opt.split(",")) >= 2 for opt in all_opts):
                print(f"[V2-REJECT] Comma-joined option")
                return None
            
            # Answer word inside prompt (Ghost)
            if len(ans) > 3 and ans.lower() in prompt_text.lower():
                return None
            
            # Meta-question labels
            combined = (prompt_text + " " + " ".join(all_opts)).lower()
            if any(mk in combined for mk in ["person 1", "person 2", "speaker a", "speaker b"]):
                return None

            # ── UNIVERSAL OUTLIER DETECTOR ──
            def _option_fingerprint(text):
                words = text.split()
                ascii_chars = sum(1 for c in text if ord(c) < 128)
                total_chars = max(len(text), 1)
                has_special = any(c.lower() in "áéíóúñü¡¿" for c in text)
                return {
                    'word_count': len(words),
                    'char_len': len(text),
                    'ascii_ratio': round(ascii_chars / total_chars, 1),
                    'has_special': has_special,
                    'has_upper_mid': any(c.isupper() for c in text[1:]) if len(text) > 1 else False,
                    'has_punctuation': any(c in text for c in '.,!?;:…'),
                    'starts_upper': text[0].isupper() if text else False,
                }
            
            fingerprints = [_option_fingerprint(o) for o in all_opts]
            
            # Numeric and Structural Outliers
            for key in ['word_count', 'ascii_ratio', 'has_punctuation']:
                values = [fp[key] for fp in fingerprints]
                for i in range(4):
                    others = [v for j, v in enumerate(values) if j != i]
                    if len(set(others)) == 1 and values[i] != others[0]:
                        if key == 'word_count' and abs(values[i] - others[0]) >= 1: return None
                        if key == 'ascii_ratio' and abs(values[i] - others[0]) >= 0.3: return None
                        if key == 'has_punctuation': return None
            
            char_lens = [fp['char_len'] for fp in fingerprints]
            for i, cl in enumerate(char_lens):
                others_avg = sum(cl2 for j, cl2 in enumerate(char_lens) if j != i) / 3
                if others_avg > 0 and (cl / others_avg > 2.5 or cl / others_avg < 0.3):
                    return None

            # Mixed 2-word categories
            word_counts = [len(o.split()) for o in all_opts]
            if all(wc == 2 for wc in word_counts):
                firsts = set(o.split()[0].lower() for o in all_opts)
                seconds = set(o.split()[1].lower() for o in all_opts)
                if len(firsts) == 4 and len(seconds) == 4: return None

            # Dedup
            ans_key = re.sub(r'[^a-z0-9]', '', ans.lower()).strip()
            if ans_key in seen_answers: return None
            
            # Distractor recycling
            dist_set = frozenset(d.lower().strip() for d in distractors)
            if has_rich_vocab:
                if any(len(dist_set & prev) >= 2 for prev in used_dist_sets): return None

            return {
                "id": _uid(),
                "type": "mcq",
                "prompt": prompt_text,
                "answer": ans,
                "distractors": distractors,
                "ans_key": ans_key,
                "dist_set": dist_set
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
                import random as _r
                opts = [valid["answer"]] + valid["distractors"]
                _r.shuffle(opts)
                valid["options"] = opts
                final.append(valid)
                seen_answers.add(valid["ans_key"])
                used_dist_sets.append(valid["dist_set"])
                if len(final) >= c: break

        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2] generated={len(raw_list)} validated={len(final)} requested={c}\n")
        print(f"[AI-V2] Pass 1: generated={len(raw_list)} validated={len(final)} requested={c}")

        # ── TOP-UP LOOP ── If validation rejected too many items, request more ──
        MAX_TOPUP_PASSES = 3
        topup_pass = 0
        while len(final) < c and topup_pass < MAX_TOPUP_PASSES:
            topup_pass += 1
            still_needed = c - len(final)
            topup_request = max(still_needed * 2, 8)  # small efficient batch
            new_seed = random.randint(1000, 9999)
            topup_prompt = f"""Generate {topup_request} multiple-choice questions for a {language} lesson.

TOPIC: {topic_title} ({topic_type})
LEVEL: {level}

SOURCE MATERIAL:
{content_str}
{forbidden_clause}
RULES:
1. Write each question prompt in {instruction_lang}.
2. ALL 4 OPTIONS IN THE SAME LANGUAGE: answer and all 3 distractors must ALL be in the same language. If answer is {instruction_lang}, all distractors must be {instruction_lang}. If answer is {language}, all distractors must be {language}.
3. STRUCTURAL INVISIBILITY: The correct answer must be visually indistinguishable from the distractors.
4. ONE BLANK ONLY: If testing with fill-in sentence, use exactly ONE blank (___). Answer = one word/phrase.
5. NO COMMA LISTS: Each option is ONE coherent unit.
6. CATEGORY LOCK: noun→nouns, verb→verbs, etc.
7. NO GIVEAWAYS: Don't put answer word inside the question.
8. MAXIMUM VARIETY: Pick different concepts from the source than those already accepted.
9. PLAUSIBLE WRONG ANSWERS: Distractors must be real words in the SAME language as the answer.
10. NO META: Don't ask about dialogues or speakers.
11. JSON SYNTAX: Escape any internal quotation marks.

ALREADY GENERATED (do NOT repeat these answers):
{chr(10).join([f"- {q['answer']}" for q in final])}

Return ONLY valid JSON:
{{"data": [{{"type": "mcq", "prompt": "...", "answer": "...", "distractors": ["...", "...", "..."]}}]}}

SEED: {new_seed}"""

            print(f"[AI-V2] Top-up pass {topup_pass}: requesting {topup_request} more (need {still_needed})")
            topup_res = _call_ai([{"role": "user", "content": topup_prompt}], model=MODEL_STRUCTURAL, max_tokens=4000, temperature=0.95)
            topup_raw = (topup_res.get("data") if topup_res else []) or []

            for item in topup_raw:
                if len(final) >= c: break
                valid = _validate_question(item, seen_answers, used_dist_sets, has_rich_vocab)
                if valid:
                    import random as _r2
                    opts = [valid["answer"]] + valid["distractors"]
                    _r2.shuffle(opts)
                    valid["options"] = opts
                    final.append(valid)
                    seen_answers.add(valid["ans_key"])
                    used_dist_sets.append(valid["dist_set"])

            print(f"[AI-V2] After top-up pass {topup_pass}: have {len(final)}/{c}")
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-TOPUP-{topup_pass}] topup_raw={len(topup_raw)} now_have={len(final)}/{c}\n")

        final_count = len(final[:c])
        print(f"[AI-V2] FINAL: requested={c} returned={final_count}")
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-DONE] requested={c} returned={final_count}\n")
        # Strip internal tracking keys before returning (frozenset is not JSON-serializable)
        for q in final:
            q.pop("ans_key", None)
            q.pop("dist_set", None)
        return final[:c]
    except Exception as e:
        print(f"[AI-V2] Error: {e}")
        return []


def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False):
    return ai_generate_questions(
        topic_title=topic_title, 
        topic_type=topic_type, 
        topic_content=topic_content, 
        language=language, 
        count=count, 
        level=level, 
        existing_questions=existing_questions,
        is_pdf_source=is_pdf_source
    )

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False):
    return ai_generate_questions(
        topic_title=topic_title, 
        topic_type=topic_type, 
        topic_content=topic_content, 
        language=language, 
        count=count, 
        level=level, 
        existing_questions=existing_questions,
        is_pdf_source=is_pdf_source
    )

def ai_grade_open_response(question, student_answer, correct_answer):
    prompt = f"Grade: Q:{question}, C:{correct_answer}, S:{student_answer}. JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150)
    return (result.get("score", 0.0), result.get("feedback", "")) if result else (0.0, "")

def _get_blueprint_path(language, level):
    """Returns the cache file path for a language/level combo."""
    cache_dir = os.path.join("services", "blueprints")
    if not os.path.exists(cache_dir): os.makedirs(cache_dir)
    clean_lang = "".join(filter(str.isalnum, language.split('(')[0])).lower()
    clean_level = "".join(filter(str.isalnum, level)).lower()
    return os.path.join(cache_dir, f"{clean_lang}_{clean_level}.json")

def save_blueprint_cache(language, level, chapters):
    """Explicitly saves a blueprint to cache. Called only when user commits to building."""
    try:
        cache_file = _get_blueprint_path(language, level)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"chapters": chapters}, f, ensure_ascii=False, indent=2)
        print(f"[CACHE] Blueprint for {language} {level} saved to library.")
        return True
    except Exception as e:
        print(f"[CACHE] Failed to save blueprint: {e}")
        return False

def delete_blueprint_cache(language, level):
    """Deletes a cached blueprint so the next generation creates a fresh one."""
    try:
        cache_file = _get_blueprint_path(language, level)
        if os.path.exists(cache_file):
            os.remove(cache_file)
            print(f"[CACHE] Deleted blueprint for {language} {level}.")
            return True
        return False
    except Exception as e:
        print(f"[CACHE] Failed to delete blueprint: {e}")
        return False

def list_blueprint_cache():
    """Lists all cached blueprints."""
    cache_dir = os.path.join("services", "blueprints")
    if not os.path.exists(cache_dir): return []
    blueprints = []
    for f in os.listdir(cache_dir):
        if f.endswith(".json"):
            parts = f.replace(".json", "").rsplit("_", 1)
            if len(parts) == 2:
                blueprints.append({"language": parts[0].capitalize(), "level": parts[1].upper(), "file": f})
    return blueprints

def ai_generate_curriculum(language, level, prompt_extra=""):
    """Generates course structure, using a local blueprint cache to eliminate recurring costs.
    Caching is READ-ONLY here. Writing to cache only happens via save_blueprint_cache() when user builds."""
    
    # 1. Check Blueprint Cache (The Thrift Strategy)
    cache_file = _get_blueprint_path(language, level)
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                if cached_data and "chapters" in cached_data:
                    print(f"[CACHE] Serving blueprint for {language} {level} from disk ($0.00 cost).")
                    return cached_data["chapters"]
        except Exception as e:
            print(f"[CACHE] Error reading cache: {e}")

    # 2. AI Architect Generation (The "One-Time" Cost)
    system = "You are a curriculum architect. Create a structured syllabus in JSON. Focus on logical progression."
    alphabet_rule = (
        "CRITICAL A1 REQUIREMENT: Chapter 1 MUST be titled 'The Alphabet and Phonetics' (or similar) and focus exclusively on the sounds, "
        "writing system, and pronunciation rules of the language. This must be a detailed deep-dive: cover every character, phonetics, "
        "pronunciations, and language-specific 'must-knows' (e.g., special characters, accent marks, or tone rules). "
        "SUBSEQUENT CHAPTERS must NOT repeat basic alphabet instruction; they should transition immediately to context-rich vocabulary and grammar."
    ) if level == 'A1' else ""
    level_exclusion = ""
    if level in ['B1', 'B2', 'C1', 'C2']:
        level_exclusion = f"EXCLUSION: DO NOT include absolute beginner topics like 'Greetings', 'Colors', 'Numbers 1-10', or 'The Alphabet'. These students are {level} level and need advanced topics appropriate for their proficiency (e.g., 'Abstract Concepts', 'Nuanced Debate', 'Complex Professional Scenarios')."

    user = f"Create a comprehensive {level} level {language} course syllabus with at least 4 or 5 Units (Chapters). {prompt_extra}\n" \
           f"{alphabet_rule}\n" \
           f"{level_exclusion}\n" \
           f"Return JSON: {{'chapters': [{{'number': 1, 'title': '...', 'topics': [{{'title': '...', 'type': 'vocabulary|grammar'}}]}}]}}"
    
    result = _call_ai([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ], model=MODEL_STRUCTURAL, max_tokens=2000)
    
    if result and "chapters" in result:
        return result["chapters"]
    return []

def ai_generate_report_insights(cohort_data):
    prompt = f"Analyze: {json.dumps(cohort_data)}"
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=500)
def ai_explain_word(word: str, language: str, context: Optional[str] = None) -> Dict[str, str]:
    """Generates a quick, concise linguistic explanation for a word.
    When 'context' (the lesson topic title) is provided, the AI explains the word
    within that educational context instead of potentially dismissing it."""
    clean_lang = language.split('(')[0].strip()
    word = word.strip()
    
    # Context-Aware System Prompt: If the student is in a lesson, the AI must teach, not contradict
    if context:
        system_prompt = (
            f"You are a helpful {clean_lang} language teacher. "
            f"The student is currently studying the lesson: '{context}'. "
            f"They clicked on '{word}' to learn more about it. "
            "Your job is to EXPLAIN this word/phrase/character within the context of what they are studying. "
            "NEVER say a word is 'fake', 'not part of the language', or 'non-standard' if it appears in the lesson material — "
            "the lesson put it there for a pedagogical reason. Instead, explain WHAT it is, HOW it's used, and WHY it's relevant to the lesson. "
            "For characters, letters, or symbols: explain their pronunciation, usage patterns, and any rules associated with them. "
            "Keep your response educational and encouraging."
        )
    else:
        system_prompt = (
            f"You are a linguistic expert for {clean_lang}. STRICT TRUTH ONLY. "
            "NEVER invent morphemes or fake words. If unidentified, say 'Needs more context.' "
            "SELECTIVE FALSE-FRIEND RULE: If a word is a strong, common, and genuinely misleading false cognate (e.g., Turkish 'patron' vs English 'patron'), "
            "you MUST include a specific 'FALSE FRIEND WARNING' and use a natural equivalent translation (e.g., 'boss'). "
            "DO NOT create warnings for weak or accidental spelling similarities (e.g., do NOT warn about boğaz/bogey). "
            "Keep the 'tip' section focused on general usage, register, or common mistakes by default."
        )
    
    if context:
        user_prompt = f"The student is studying '{context}' and clicked on '{word}'. Explain it in the context of this lesson."
    else:
        user_prompt = f"Analyze '{word}' in {clean_lang}. If it is a partial fragment or fake, say so."
    
    user_prompt += '\nReturn JSON: {"explanation": "...", "usage": "...", "tip": "..."}'
    
    result = _call_ai([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], max_tokens=400, temperature=0.3)
    
    if result and "explanation" in result:
        return result
    
    # If we have error details, pass them along
    error_note = result.get("error_details", "Unknown API Error") if result else "Connection Failure"
    
    # EMERGENCY HYBRID FALLBACK: Use Wiktionary/Translation if AI fails
    try:
        # We call the internal Wiktionary scan directly to avoid recursion
        from services.dictionary_service import _get_wiktionary_definition, LANG_MAP
        lang_code = LANG_MAP.get(clean_lang.lower(), "en")
        wikt = _get_wiktionary_definition(word, lang_code)
        
        if not wikt.get("error") and wikt.get("definitions"):
            return {
                "explanation": wikt["definitions"][0]["definition"],
                "usage": "Found via Deep Dictionary Scan.",
                "tip": f"AI Brain was busy ({error_note}), so we found this for you!"
            }
    except Exception as e:
        print(f"[AI] Emergency fallback failed: {e}")
        
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-DONE] requested={c} returned={final_count}\n")
        # Strip internal tracking keys before returning (frozenset is not JSON-serializable)
        for q in final:
            q.pop("ans_key", None)
            q.pop("dist_set", None)
        return final[:c]
    except Exception as e:
        print(f"[AI-V2] Error: {e}")
        return []


def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False):
    return ai_generate_questions(
        topic_title=topic_title, 
        topic_type=topic_type, 
        topic_content=topic_content, 
        language=language, 
        count=count, 
        level=level, 
        existing_questions=existing_questions,
        is_pdf_source=is_pdf_source
    )

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False):
    return ai_generate_questions(
        topic_title=topic_title, 
        topic_type=topic_type, 
        topic_content=topic_content, 
        language=language, 
        count=count, 
        level=level, 
        existing_questions=existing_questions,
        is_pdf_source=is_pdf_source
    )

def ai_grade_open_response(question, student_answer, correct_answer):
    prompt = f"Grade: Q:{question}, C:{correct_answer}, S:{student_answer}. JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150)
    return (result.get("score", 0.0), result.get("feedback", "")) if result else (0.0, "")

def _get_blueprint_path(language, level):
    """Returns the cache file path for a language/level combo."""
    cache_dir = os.path.join("services", "blueprints")
    if not os.path.exists(cache_dir): os.makedirs(cache_dir)
    clean_lang = "".join(filter(str.isalnum, language.split('(')[0])).lower()
    clean_level = "".join(filter(str.isalnum, level)).lower()
    return os.path.join(cache_dir, f"{clean_lang}_{clean_level}.json")

def save_blueprint_cache(language, level, chapters):
    """Explicitly saves a blueprint to cache. Called only when user commits to building."""
    try:
        cache_file = _get_blueprint_path(language, level)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"chapters": chapters}, f, ensure_ascii=False, indent=2)
        print(f"[CACHE] Blueprint for {language} {level} saved to library.")
        return True
    except Exception as e:
        print(f"[CACHE] Failed to save blueprint: {e}")
        return False

def delete_blueprint_cache(language, level):
    """Deletes a cached blueprint so the next generation creates a fresh one."""
    try:
        cache_file = _get_blueprint_path(language, level)
        if os.path.exists(cache_file):
            os.remove(cache_file)
            print(f"[CACHE] Deleted blueprint for {language} {level}.")
            return True
        return False
    except Exception as e:
        print(f"[CACHE] Failed to delete blueprint: {e}")
        return False

def list_blueprint_cache():
    """Lists all cached blueprints."""
    cache_dir = os.path.join("services", "blueprints")
    if not os.path.exists(cache_dir): return []
    blueprints = []
    for f in os.listdir(cache_dir):
        if f.endswith(".json"):
            parts = f.replace(".json", "").rsplit("_", 1)
            if len(parts) == 2:
                blueprints.append({"language": parts[0].capitalize(), "level": parts[1].upper(), "file": f})
    return blueprints

def ai_generate_curriculum(language, level, prompt_extra=""):
    """Generates course structure, using a local blueprint cache to eliminate recurring costs.
    Caching is READ-ONLY here. Writing to cache only happens via save_blueprint_cache() when user builds."""
    
    # 1. Check Blueprint Cache (The Thrift Strategy)
    cache_file = _get_blueprint_path(language, level)
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                if cached_data and "chapters" in cached_data:
                    print(f"[CACHE] Serving blueprint for {language} {level} from disk ($0.00 cost).")
                    return cached_data["chapters"]
        except Exception as e:
            print(f"[CACHE] Error reading cache: {e}")

    # 2. AI Architect Generation (The "One-Time" Cost)
    system = "You are a curriculum architect. Create a structured syllabus in JSON. Focus on logical progression."
    alphabet_rule = (
        "CRITICAL A1 REQUIREMENT: Chapter 1 MUST be titled 'The Alphabet and Phonetics' (or similar) and focus exclusively on the sounds, "
        "writing system, and pronunciation rules of the language. This must be a detailed deep-dive: cover every character, phonetics, "
        "pronunciations, and language-specific 'must-knows' (e.g., special characters, accent marks, or tone rules). "
        "SUBSEQUENT CHAPTERS must NOT repeat basic alphabet instruction; they should transition immediately to context-rich vocabulary and grammar."
    ) if level == 'A1' else ""
    level_exclusion = ""
    if level in ['B1', 'B2', 'C1', 'C2']:
        level_exclusion = f"EXCLUSION: DO NOT include absolute beginner topics like 'Greetings', 'Colors', 'Numbers 1-10', or 'The Alphabet'. These students are {level} level and need advanced topics appropriate for their proficiency (e.g., 'Abstract Concepts', 'Nuanced Debate', 'Complex Professional Scenarios')."

    user = f"Create a comprehensive {level} level {language} course syllabus with at least 4 or 5 Units (Chapters). {prompt_extra}\n" \
           f"{alphabet_rule}\n" \
           f"{level_exclusion}\n" \
           f"Return JSON: {{'chapters': [{{'number': 1, 'title': '...', 'topics': [{{'title': '...', 'type': 'vocabulary|grammar'}}]}}]}}"
    
    result = _call_ai([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ], model=MODEL_STRUCTURAL, max_tokens=2000)
    
    if result and "chapters" in result:
        return result["chapters"]
    return []

def ai_generate_report_insights(cohort_data):
    prompt = f"Analyze: {json.dumps(cohort_data)}"
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=500)
def ai_explain_word(word: str, language: str, context: Optional[str] = None) -> Dict[str, str]:
    """Generates a quick, concise linguistic explanation for a word.
    When 'context' (the lesson topic title) is provided, the AI explains the word
    within that educational context instead of potentially dismissing it."""
    clean_lang = language.split('(')[0].strip()
    word = word.strip()
    
    # Context-Aware System Prompt: If the student is in a lesson, the AI must teach, not contradict
    if context:
        system_prompt = (
            f"You are a helpful {clean_lang} language teacher. "
            f"The student is currently studying the lesson: '{context}'. "
            f"They clicked on '{word}' to learn more about it. "
            "Your job is to EXPLAIN this word/phrase/character within the context of what they are studying. "
            "NEVER say a word is 'fake', 'not part of the language', or 'non-standard' if it appears in the lesson material — "
            "the lesson put it there for a pedagogical reason. Instead, explain WHAT it is, HOW it's used, and WHY it's relevant to the lesson. "
            "For characters, letters, or symbols: explain their pronunciation, usage patterns, and any rules associated with them. "
            "Keep your response educational and encouraging."
        )
    else:
        system_prompt = (
            f"You are a linguistic expert for {clean_lang}. STRICT TRUTH ONLY. "
            "NEVER invent morphemes or fake words. If unidentified, say 'Needs more context.' "
            "SELECTIVE FALSE-FRIEND RULE: If a word is a strong, common, and genuinely misleading false cognate (e.g., Turkish 'patron' vs English 'patron'), "
            "you MUST include a specific 'FALSE FRIEND WARNING' and use a natural equivalent translation (e.g., 'boss'). "
            "DO NOT create warnings for weak or accidental spelling similarities (e.g., do NOT warn about boğaz/bogey). "
            "Keep the 'tip' section focused on general usage, register, or common mistakes by default."
        )
    
    if context:
        user_prompt = f"The student is studying '{context}' and clicked on '{word}'. Explain it in the context of this lesson."
    else:
        user_prompt = f"Analyze '{word}' in {clean_lang}. If it is a partial fragment or fake, say so."
    
    user_prompt += '\nReturn JSON: {"explanation": "...", "usage": "...", "tip": "..."}'
    
    result = _call_ai([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], max_tokens=400, temperature=0.3)
    
    if result and "explanation" in result:
        return result
    
    # If we have error details, pass them along
    error_note = result.get("error_details", "Unknown API Error") if result else "Connection Failure"
    
    # EMERGENCY HYBRID FALLBACK: Use Wiktionary/Translation if AI fails
    try:
        # We call the internal Wiktionary scan directly to avoid recursion
        from services.dictionary_service import _get_wiktionary_definition, LANG_MAP
        lang_code = LANG_MAP.get(clean_lang.lower(), "en")
        wikt = _get_wiktionary_definition(word, lang_code)
        
        if not wikt.get("error") and wikt.get("definitions"):
            return {
                "explanation": wikt["definitions"][0]["definition"],
                "usage": "Found via Deep Dictionary Scan.",
                "tip": f"AI Brain was busy ({error_note}), so we found this for you!"
            }
    except Exception as e:
        print(f"[AI] Emergency fallback failed: {e}")
        
    return {
        "explanation": f"'{word}' is a {clean_lang} word. In this context, it usually refers to a specific quality or action.",
        "usage": "Try looking at the surrounding sentence for more context.",
        "tip": f"AI Diagnostic: {error_note}. Please try again later!"
    }

def ai_explain_activity(prompt: str, correct_answer: str, student_answer: str, language: str) -> Dict[str, str]:
    """Generates a brief educational explanation for why a student's answer is incorrect in an MCQ/Fill-in-the-blank activity."""
    clean_lang = language.split('(')[0].strip()
    
    system_prompt = (
        f"You are a helpful {clean_lang} language teacher. "
        "Your student just answered a question incorrectly. Explain the mistake DIRECTLY to them "
        "(use 'you', not 'the student'). Be warm, encouraging, and conversational. "
        "Explain WHY their answer is wrong and WHY the correct answer is right in a simple, learner-friendly way. "
        "Keep it extremely concise (1-2 short sentences max). Avoid sounding robotic or overly academic. "
        "CRITICAL: You MUST write your explanation entirely in English, regardless of the language being taught."
    )
    
    user_prompt = (
        f"Question: {prompt}\n"
        f"Correct Answer: {correct_answer}\n"
        f"Student Answer: {student_answer}\n"
        "Explain the mistake."
    )
    
    user_prompt += '\nReturn JSON: {"explanation": "..."}'
    
    result = _call_ai([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], max_tokens=200, temperature=0.3)
    
    if result and "explanation" in result:
        return result
        
    return {"explanation": f"The correct answer is {correct_answer}. Your answer was {student_answer}."}
