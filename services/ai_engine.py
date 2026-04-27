import os
import json
import re
import urllib.request
import urllib.error
import time
from typing import List, Dict, Any, Optional

# Simple AI Engine Reset (No extra dependencies)
MODEL_SPEED = "anthropic/claude-3-haiku" 
MODEL_QUALITY = "anthropic/claude-3-haiku"

def _call_ai(messages: List[Dict], model: str = MODEL_SPEED, max_tokens: int = 1000, temperature: float = 0.7) -> Optional[Dict]:
    """Simple OpenRouter caller using built-in urllib."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": { "type": "json_object" }
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            if "choices" in res_json:
                content = res_json["choices"][0]["message"]["content"]
                return json.loads(content)
    except Exception as e:
        print(f"AI Error: {str(e)}")
    return None

def detect_language(text):
    """Simple language detection."""
    prompt = f"Detect the language of this text. Return a JSON object: {{'language': 'LanguageName'}}. Text: {text[:500]}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=50)
    return result.get("language", "English") if result else "English"

def generate_full_lesson(topic, language):
    """Simple full lesson generator."""
    prompt = f"Generate a comprehensive lesson about {topic} for students learning {language}. Provide detailed explanations and examples. Return a JSON object with a 'content' key."
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=3000)
    return result.get("content") if result else "Lesson content could not be generated."

def is_ai_available():
    return os.getenv("OPENROUTER_API_KEY") is not None

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=6, level='A1', use_quality=True):
    """Simple, direct question generator. No batching, no filtering."""
    prompt = f"""Generate {count} learning questions for {language} (Level: {level}). Topic: {topic_title}.
    Return a JSON object with a "data" key containing an array of objects.
    Each object should have:
    - type: "mcq" or "fill_blank"
    - prompt: The question text
    - answer: The correct answer
    - distractors: [3 wrong answers for mcq]
    - translation: English hint
    
    Return JSON ONLY.
    """
    
    result = _call_ai([{"role": "user", "content": prompt}])
    return result.get("data") if result else []

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=6, level='A1'):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level)

def ai_grade_open_response(question, student_answer, correct_answer):
    prompt = f"Grade Question: {question}, Correct: {correct_answer}, Student: {student_answer}. Return JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150)
    if result:
        return (result.get("score", 0.0), result.get("feedback", ""))
    return (0.0, "")

def ai_generate_report_insights(cohort_data):
    prompt = f"Analyze this class data and give 2 short insights: {json.dumps(cohort_data)}"
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=500)
