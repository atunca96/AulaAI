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
                content = res_json["choices"][0]["message"]["content"]
                clean_content = re.sub(r'^```json\n?|\n?```$', '', content.strip(), flags=re.MULTILINE)
                return json.loads(clean_content)
    except Exception as e:
        print(f"AI Error: {str(e)}")
    return None

def detect_language(text):
    prompt = f"Detect language. JSON: {{'language': '...'}}. Text: {text[:500]}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=50)
    return result.get("language", "English") if result else "English"

def generate_full_lesson(topic, language):
    prompt = f"Detailed lesson for {topic} in {language}. JSON: {{'content': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=3000)
    return result.get("content", "Error") if result else "Error"

def is_ai_available():
    return os.getenv("OPENROUTER_API_KEY") is not None

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=6, level='A1', use_quality=True):
    """3/2 Rule + Python Filtering."""
    c = int(count)
    request_count = int((c + 1) * 1.5) if c % 2 != 0 else int(c * 1.5)
    
    prompt = f"""Generate {request_count} learning questions for {language} ({level}). Topic: {topic_title}.
    JSON structure: {{"data": [{{ "type": "mcq"|"fill_blank", "prompt": "...", "answer": "...", "distractors": ["...", "...", "..."] }}]}}
    Return JSON ONLY.
    """
    
    result = _call_ai([{"role": "user", "content": prompt}])
    raw_list = result.get("data") if result else []
    
    final_questions = []
    seen_answers = set()
    
    is_non_latin = any(x in language.lower() for x in ["japanese", "chinese", "arabic", "korean", "russian", "greek"])

    for item in raw_list:
        try:
            # 1. Universal Cleaning
            # Strip parenthetical hints like "(apple)" from both answers and distractors
            ans = str(item.get("answer", "")).strip()
            ans_clean = re.sub(r'\(.*?\)', '', ans).strip()
            
            prompt_text = str(item.get("prompt", "")).strip()
            distractors = item.get("distractors", [])
            if not isinstance(distractors, list): distractors = []
            
            # 2. The "Ghost" Rule (Agnostic Logic)
            # The answer and distractors MUST NOT appear in the prompt text.
            # This catches "flipped" questions in any language (Spanish, Japanese, etc).
            if ans_clean.lower() in prompt_text.lower() and len(ans_clean) > 0:
                continue
            
            # Ensure distractors don't contain the prompt word either
            if any(str(d).lower() in prompt_text.lower() for d in distractors if len(str(d)) > 1):
                continue

            # 3. Unique Choice Rule
            # Choices must be unique and non-empty
            all_choices = {ans_clean.lower()}
            valid_distractors = []
            for d in distractors:
                d_clean = re.sub(r'\(.*?\)', '', str(d)).strip()
                if d_clean and d_clean.lower() not in all_choices:
                    valid_distractors.append(d_clean)
                    all_choices.add(d_clean.lower())
            
            # 4. Duplicate Check (Global)
            if ans_clean.lower() in seen_answers:
                continue
                
            # Success!
            item["answer"] = ans_clean
            item["distractors"] = valid_distractors[:3]
            seen_answers.add(ans_clean.lower())
            final_questions.append(item)
            
            if len(final_questions) >= c: break
        except: continue
        
    return final_questions

def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=6, level='A1'):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level)

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=6, level='A1'):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level)

def ai_grade_open_response(question, student_answer, correct_answer):
    prompt = f"Grade: Q:{question}, C:{correct_answer}, S:{student_answer}. JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150)
    return (result.get("score", 0.0), result.get("feedback", "")) if result else (0.0, "")

def ai_generate_report_insights(cohort_data):
    prompt = f"Analyze: {json.dumps(cohort_data)}"
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=500)
