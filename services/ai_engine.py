import os
import json
import re
import requests
import time
from typing import List, Dict, Any, Optional

# Simple AI Engine Reset
MODEL_SPEED = "anthropic/claude-3-haiku" 
MODEL_QUALITY = "anthropic/claude-3-haiku"

def _call_ai(messages: List[Dict], model: str = MODEL_SPEED, max_tokens: int = 1000, temperature: float = 0.7) -> Optional[Dict]:
    """Simple OpenRouter caller."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            data=json.dumps({
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "response_format": { "type": "json_object" }
            }),
            timeout=30
        )
        res_json = response.json()
        if "choices" in res_json:
            content = res_json["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception as e:
        print(f"AI Error: {str(e)}")
    return None

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
