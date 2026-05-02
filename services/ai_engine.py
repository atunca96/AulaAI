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
MODEL_STRUCTURAL = "anthropic/claude-3-haiku" # Lowest cost per output
MODEL_NARRATIVE = "anthropic/claude-3-haiku"  # Legacy stable voice
MODEL_FALLBACK = "google/gemini-2.0-flash-lite-preview-02-05:free"

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
    models_to_try = [model, MODEL_FALLBACK]
    
    for target_model in models_to_try:
        try:
            req = urllib.request.Request(url, data=json.dumps({
                "model": target_model, "messages": messages, "max_tokens": max_tokens, 
                "temperature": temperature
            }).encode("utf-8"), headers=headers)
            
            with urllib.request.urlopen(req, timeout=45) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                
                if "choices" in res_json:
                    content = res_json["choices"][0]["message"]["content"].strip()
                    # LOGGING
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
                        json_str = "".join(ch for ch in json_str if ord(ch) >= 32 or ch in '\n\r\t')
                        try:
                            return json.loads(json_str, strict=False)
                        except Exception as je:
                            # Log the exact JSON that failed
                            with open("pipeline.log", "a", encoding="utf-8") as f:
                                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-JSON-FAIL] {target_model}: {str(je)}\n")
                                f.write(f"--- RAW JSON START ---\n{json_str[:1000]}...\n--- RAW JSON END ---\n")
                            try:
                                import ast
                                clean_json = json_str.replace('true', 'True').replace('false', 'False').replace('null', 'None')
                                return ast.literal_eval(clean_json)
                            except: pass
                    
                    if len(content) > 10 and '{' not in content:
                        return {"explanation": content}
                
                if "error" in res_json:
                    last_error = res_json["error"].get("message", "API Error")
                    with open("pipeline.log", "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-ERROR] {target_model}: {last_error}\n")
                        
        except Exception as e:
            last_error = str(e)
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-FAIL] {target_model}: {last_error}\n")
            
    return {"error_details": last_error}

def detect_language(text, hint=""):
    prompt = f"Detect language of: {text[:1000]} (Hint: {hint}). JSON: {{'language': '...'}}"
    res = _call_ai([{"role": "user", "content": prompt}])
    return res.get("language", "Unknown") if res else "Unknown"

def get_language_profile(language):
    agglutinative = ["Turkish", "Korean", "Japanese", "Finnish", "Hungarian"]
    if language in agglutinative: return "agglutinative"
    return "inflected"

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=10, level='A1', use_quality=True, existing_questions=None, is_pdf_source=False, is_quiz=False):
    with open("pipeline.log", "a", encoding="utf-8") as f:
        api_status = "Available" if is_ai_available() else "MISSING KEY"
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-START] {topic_title} count={count} API={api_status}\n")
    
    c = int(count)
    request_count = max(c * 3, 20) 
    is_beginner = any(lvl in level.upper() for lvl in ["A1", "A2"])
    
    if is_pdf_source or is_quiz:
        instruction_lang = language
    else:
        instruction_lang = "English" if is_beginner else language
    content_str = json.dumps(topic_content, ensure_ascii=False)
    
    forbidden_clause = ""
    if existing_questions and len(existing_questions) > 0:
        qs_list = "\n".join([f"- Answer: '{q.get('answer', '')}' (Prompt: '{q.get('prompt', '')[:40]}...')" for q in existing_questions])
        forbidden_clause = f"\nEXISTING QUESTIONS TO AVOID (DO NOT TEST THESE EXACT CONCEPTS):\n{qs_list}\n"

    translation_rule = '12. TRANSLATION: Add a "translation" field containing the English translation of the prompt.' if (is_beginner and not is_quiz) else ""
    translation_field = '"translation": "...", ' if (is_beginner and not is_quiz) else ""

    prompt = f"""Write {request_count} high-quality, creative multiple-choice questions for a {language} lesson.
TOPIC: {topic_title} ({topic_type})
LEVEL: {level}
SOURCE MATERIAL: {content_str}
{forbidden_clause}
RULES:
1. CREATIVITY: Do NOT use repetitive patterns. Vary the question styles (fill-in-the-blank, translation, context-based, grammar usage).
2. Write each question prompt in {instruction_lang}.
3. ALL 4 OPTIONS IN THE SAME LANGUAGE.
4. STRUCTURAL INVISIBILITY: All options must look similar in length and complexity.
5. ONE BLANK ONLY if using blanks.
6. NO COMMA LISTS.
7. CATEGORY LOCK: All distractors must belong to the same semantic category as the answer.
8. MAXIMUM VARIETY & RANDOMIZATION.
9. PLAUSIBLE WRONG ANSWERS: Distractors must be common mistakes or similar-sounding words.
10. NO META.
11. JSON SYNTAX: Escape all quotes.
12. EXPLANATION: Add a "why" field with a 1-sentence pedagogical explanation in English.
{translation_rule}
Return ONLY valid JSON:
{{"data": [{{"type": "mcq", "prompt": "...", {translation_field}"answer": "...", "distractors": ["...", "...", "..."], "why": "..."}}]}}"""

    seed = py_random.randint(1000, 9999)
    prompt += f"\n\nSEED: {seed}"
    
    try:
        # TRY PRIMARY MODEL
        res = _call_ai([{"role": "user", "content": prompt}], model=MODEL_STRUCTURAL, max_tokens=8000, temperature=0.8)
        raw_list = (res.get("data") if (res and isinstance(res, dict)) else []) or []
        
        # TRY FALLBACK MODEL IF PRIMARY PRODUCED NOTHING
        if not raw_list:
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-RETRY] Primary model failed, trying fallback model...\n")
            res = _call_ai([{"role": "user", "content": prompt}], model=MODEL_FALLBACK, max_tokens=8000, temperature=0.9)
            raw_list = (res.get("data") if (res and isinstance(res, dict)) else []) or []
        
        def _validate_question(item, seen_answers, used_dist_sets, has_rich_vocab):
            if not isinstance(item, dict): return None
            ans = str(item.get("answer", "")).strip()
            prompt_text = str(item.get("prompt", "")).strip()
            distractors = item.get("distractors", [])
            if not isinstance(distractors, list) or len(distractors) < 3: return None
            distractors = [str(d).strip() for d in distractors[:3] if str(d).strip()]
            if len(distractors) < 3: return None
            
            if not ans or not prompt_text or len(prompt_text) < 5: return None
            ans_lower = ans.lower()
            prompt_lower = prompt_text.lower()
            if len(ans) > 4 and ans_lower in prompt_lower:
                # Relaxed: only reject if it's obviously the same word wrapped in quotes
                if f'"{ans_lower}"' in prompt_lower or f"'{ans_lower}'" in prompt_lower: return None
                # Otherwise, allow it (could be "Which word means 'X'?")
                pass
            
            ans_key = re.sub(r'[^\w]', '', ans_lower).strip()
            if ans_key in seen_answers: return None
            
            dist_set = frozenset(d.lower().strip() for d in distractors)
            if has_rich_vocab:
                if any(len(dist_set & prev) >= 2 for prev in used_dist_sets): return None

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
            msg = f"Generation failed for {topic_title} in {language}."
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-FALLBACK] {msg}\n")
            
            clean_lang = language if language and language.lower() != "unknown" else "this language"

            # Artificial delay to make fallback feel more 'real' and less 'instant error'
            time.sleep(py_random.uniform(2.5, 4.5))
            
            # Create 'count' distinct fallbacks
            placeholders = [
                ("concept", "Definition A", "Definition B", "Definition C"),
                ("usage", "Usage A", "Usage B", "Usage C"),
                ("context", "Context A", "Context B", "Context C"),
                ("term", "Synonym A", "Synonym B", "Synonym C"),
                ("application", "Example A", "Example B", "Example C")
            ]
            
            for i in range(c):
                kind, w1, w2, w3 = placeholders[i % len(placeholders)]
                ans = f"Correct {kind} of {topic_title} #{i+1}"
                final.append({
                    "id": _uid() + f"_{i}", "type": "mcq", 
                    "prompt": f"({i+1}) Which of the following describes the {kind} of '{topic_title}' in {clean_lang}?",
                    "answer": ans, 
                    "distractors": [f"{w1} {i+1}", f"{w2} {i+1}", f"{w3} {i+1}"],
                    "options": py_random.sample([ans, f"{w1} {i+1}", f"{w2} {i+1}", f"{w3} {i+1}"], 4),
                    "why": f"This is a fallback explanation for '{topic_title}' while the AI is warming up."
                })

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

    system = "You are a curriculum architect for a language learning platform. Create a highly structured and pedagogical syllabus in JSON."
    user = f"""Create a comprehensive {level} {language} course syllabus. {prompt_extra}
RULES:
1. DO NOT use generic topic titles like 'Vocabulary', 'Grammar', 'Exercises', or 'Conversation'.
2. Each topic MUST have a specific, descriptive name (e.g., 'Ordering at a Cafe', 'Regular -AR Verbs', 'Family Members').
3. Ensure logical progression from basic to complex.
Return JSON: {{'chapters': [{{'number': 1, 'title': '...', 'topics': [{{'title': '...', 'type': 'vocabulary|grammar'}}]}}]}}"""
    res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=2000)
    return res.get("chapters", []) if res else []

def ai_generate_report_insights(cohort_data):
    """Generates high-level pedagogical insights for teacher reports."""
    prompt = f"Analyze student performance and provide 3 actionable teaching insights: {json.dumps(cohort_data)}"
    res = _call_ai([{"role": "user", "content": prompt}], max_tokens=600)
    return res.get("explanation", "Insufficient data for insights.") if res else "Connection Error."

def generate_full_lesson(topic, topic_type, language, count=6, level='A1', source_text=None):
    """Generates a complete structured lesson, using source_text as the primary source if provided."""
    from services.language_data import get_reference_prompt, get_special_chars_prompt
    
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

    primary_command = f"Write a comprehensive {level} lesson to teach {language} topic: '{topic}' ({topic_type})."
    
    prompt = f"""
    {primary_command}
    {source_rule}
    INSTRUCTIONS:
    1. {lang_guard}
    2. SUBJECT FOCUS: The lesson must be about {language}. If teaching grammar, explain {language} rules.
    3. REQUIREMENT: 2 to 4 high-quality pages.
    3. Return ONLY JSON:
    {{
      "pages": [
        {{ "type": "vocabulary", "title": "...", "items": [ {{ "term": "...", "translation": "..." }} ] }},
        {{ "type": "grammar", "title": "...", "text": "..." }},
        {{ "type": "examples", "title": "...", "list": [ {{ "speaker": "...", "text": "..." }} ] }}
      ]
    }}
    """
    return _call_ai([{"role": "user", "content": prompt}], model=MODEL_NARRATIVE, max_tokens=2500, temperature=0.4) or {"pages": []}

def ai_explain_word(word, language, context=None):
    prompt = f"Explain '{word}' in {language}. Context: {context}. JSON: {{'explanation': '...', 'usage': '...', 'tip': '...'}}"
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=400)

def ai_explain_activity(prompt, correct_answer, student_answer, language):
    clean_lang = language.split('(')[0].strip()
    system = f"You are a helpful {clean_lang} teacher. Explain the mistake in English."
    user = f"Q: {prompt}\nC: {correct_answer}\nS: {student_answer}\nExplain JSON: {{'explanation': '...'}}"
    return _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=200)

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
