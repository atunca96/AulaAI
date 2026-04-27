import os
import json
import re
import urllib.request
import urllib.error
import time
from typing import List, Dict, Any, Optional

# Simple AI Engine with Python Filtering
MODEL_SPEED = "anthropic/claude-3-haiku" 
MODEL_QUALITY = "anthropic/claude-3-haiku"

def _call_ai(messages: List[Dict], model: str = MODEL_SPEED, max_tokens: int = 1000, temperature: float = 0.7) -> Optional[Dict]:
    """OpenRouter caller with markdown cleaning."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key: return None

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = json.dumps({
        "model": model, "messages": messages, "max_tokens": max_tokens, 
        "temperature": temperature, "response_format": { "type": "json_object" }
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            if "choices" in res_json:
                content = res_json["choices"][0]["message"]["content"].strip()
                # Surgical extraction: find first '{' and last '}'
                start = content.find('{')
                end = content.rfind('}')
                if start != -1 and end != -1:
                    json_str = content[start:end+1]
                    return json.loads(json_str)
                # Fallback to direct load if no braces found (might be raw list or already clean)
                return json.loads(content)
    except Exception as e:
        print(f"AI Error: {str(e)}")
    return None

def detect_language(text):
    prompt = f"Detect language. JSON: {{'language': '...'}}. Text: {text[:500]}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=50)
    return result.get("language", "English") if result else "English"

def generate_full_lesson(topic, topic_type, language, count=6):
    """Generates a complete structured lesson with vocab, grammar, and examples."""
    prompt = f"""Write a professional {language} lesson for the topic: '{topic}' ({topic_type}).
    
    You must return ONLY a JSON object with this exact structure:
    {{
      "content": {{
        "words": [ {{ "term": "...", "translation": "..." }} ],
        "rules": [ "Grammar rule 1", "Grammar rule 2" ],
        "examples": [ {{ "speaker": "A", "text": "..." }}, {{ "speaker": "B", "text": "..." }} ]
      }},
      "questions": [
        {{ "type": "mcq", "prompt": "...", "answer": "...", "distractors": ["...", "...", "..."] }}
      ]
    }}
    
    Rules:
    1. Instructions must be in English.
    2. Content must be level-appropriate (A1/A2).
    3. Generate at least 5 words and 3 examples.
    """
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=3000)
    return result if result else {}

def is_ai_available():
    return os.getenv("OPENROUTER_API_KEY") is not None

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=6, level='A1', use_quality=True):
    """3/2 Rule + Python Filtering."""
    c = int(count)
    request_count = int((c + 1) * 1.5) if c % 2 != 0 else int(c * 1.5)
    
    # Level-Gated Immersion Rule
    is_beginner = any(lvl in level.upper() for lvl in ["A1", "A2"])
    instruction_lang = "English" if is_beginner else language
    
    prompt = f"""Generate {request_count} high-quality learning questions for {language} ({level}). Topic: {topic_title}.
    
    CRITICAL RULES for {language}:
    1. PROMPT LANGUAGE: The 'prompt' (the question/instruction) MUST be in {instruction_lang}.
    2. NO MIXED SENTENCES: NEVER mix {language} and English in a single sentence (e.g., NO "I ___ [Japanese word] to school").
    3. QUESTION FORMATS:
       - Vocabulary: "What is the {language} word for '[English]'?" (Only for beginners)
       - Contextual: Create a gap-fill or translation task suitable for {level}.
    4. CONTENT: All choices (answer + distractors) MUST be in the SAME language/script.
    5. NO GHOSTS: NEVER include the correct answer word inside the prompt text.
    
    JSON structure: {{"data": [{{ "type": "mcq"|"fill_blank", "prompt": "...", "answer": "...", "distractors": ["...", "...", "..."] }}]}}
    Return JSON ONLY.
    """
    
    for attempt in range(2):
        result = _call_ai([{"role": "user", "content": prompt}])
        raw_list = result.get("data") if result else []
        
        final_questions = []
        seen_answers = set()
        
        for item in raw_list:
            try:
                # 1. Aggressive Universal Cleaning (including Unicode brackets)
                def deep_clean(text):
                    # Remove (...), [...], {...}, （...）, 「...」, 『...』, 【...】 and strip
                    t = re.sub(r'[\(\[\{（「『【].*?[\)\]\}）」』】]', '', str(text))
                    return t.strip()
    
                ans_clean = deep_clean(item.get("answer", ""))
                prompt_raw = str(item.get("prompt", "")).strip()
                prompt_clean = deep_clean(prompt_raw)
                
                # SAFE AGNOSTIC STRIP: Remove EVERYTHING except words/characters
                def agnostic_strip(text):
                    return re.sub(r'[^\w]', '', str(text)).lower().strip()
    
                prompt_stripped = agnostic_strip(prompt_clean)
                ans_stripped = agnostic_strip(ans_clean)
                
                # 2. Logic Check: Empty or Inside Prompt
                if not ans_clean or not ans_stripped or len(prompt_raw) < 5:
                    continue
    
                # 3. Script Consistency Rule (Agnostic)
                def get_vibe(t):
                    return "latin" if re.search('[a-zA-Z]', str(t)) else "native"
                
                ans_vibe = get_vibe(ans_clean)
                distractors = item.get("distractors", [])
                if not isinstance(distractors, list): distractors = []
                
                all_choices = {ans_clean.lower()}
                valid_distractors = []
                
                for d in distractors:
                    d_clean = deep_clean(d)
                    d_stripped = agnostic_strip(d_clean)
                    # Rule: Choice must exist, share the vibe, and NOT be in the prompt
                    if d_clean and d_stripped and d_clean.lower() not in all_choices:
                        if d_stripped not in prompt_stripped and get_vibe(d_clean) == ans_vibe:
                            valid_distractors.append(d_clean)
                            all_choices.add(d_clean.lower())
                
                # 4. Final Zero-Tolerance Validation
                if ans_clean and prompt_clean:
                    # Reject if answer is a "ghost" inside the prompt (The Flipped Question Bug)
                    # For non-latin, be extra strict: no overlapping characters
                    if ans_vibe == 'native':
                        if any(char in prompt_clean for char in ans_clean if char.strip()):
                            continue
                    else:
                        if ans_stripped in prompt_stripped:
                            continue
                    
                    # MCQs need at least 2 valid distractors
                    if item.get("type", "mcq") == "mcq" and len(valid_distractors) < 2:
                        continue
    
                    # Check for global duplicates
                    if ans_clean.lower() in seen_answers:
                        continue
                    
                    item["prompt"] = prompt_clean
                    item["answer"] = ans_clean
                    item["distractors"] = valid_distractors[:3]
                    seen_answers.add(ans_clean.lower())
                    final_questions.append(item)
                
                if len(final_questions) >= c: break
            except: continue
        
        if len(final_questions) > 0:
            return final_questions
        
        # If we got 0, try once more with a sterner warning
        prompt += "\n\nRETRY WARNING: Your previous attempt was rejected for Ghost answers (answer word in prompt) or Script mixing. DO NOT repeat those mistakes."
        
    return []

def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=6, level='A1'):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level)

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=6, level='A1'):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level)

def ai_grade_open_response(question, student_answer, correct_answer):
    prompt = f"Grade: Q:{question}, C:{correct_answer}, S:{student_answer}. JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150)
    return (result.get("score", 0.0), result.get("feedback", "")) if result else (0.0, "")

def ai_generate_curriculum(language, level, prompt_extra=""):
    system = "You are a curriculum architect. Create a structured syllabus in JSON."
    user = f"Create a {level} level {language} course syllabus. {prompt_extra}\nReturn JSON: {{'chapters': [{{'number': 1, 'title': '...', 'topics': [{{'title': '...', 'type': 'vocabulary|grammar'}}]}}]}}"
    
    result = _call_ai([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ], model=MODEL_QUALITY, max_tokens=2000)
    
    if result and "chapters" in result:
        return result["chapters"]
    return []

def ai_generate_report_insights(cohort_data):
    prompt = f"Analyze: {json.dumps(cohort_data)}"
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=500)
