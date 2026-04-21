"""
AI Engine — Groq API integration using only Python stdlib.
Zero external dependencies. Falls back to mock data if API key is missing.
"""

import os
import json
import urllib.request
import urllib.error

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"


def is_ai_available():
    """Check if Groq API key is configured."""
    return bool(GROQ_API_KEY)


def _call_groq(messages, max_tokens=1500, temperature=0.7):
    """Call the Groq API using urllib (no pip dependencies)."""
    if not GROQ_API_KEY:
        return None

    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": {"type": "json_object"}
    }).encode("utf-8")

    req = urllib.request.Request(
        GROQ_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, Exception) as e:
        print(f"[AI] Groq API error: {e}")
        return None


def ai_generate_questions(topic_title, topic_type, topic_content, count=6):
    """
    Generate quiz/practice questions using AI.
    Returns a list of question dicts or None if AI is unavailable.
    """
    if topic_type == "vocabulary":
        words = topic_content.get("words", {})
        word_list = ", ".join([f"{k} = {v}" for k, v in list(words.items())[:12]])
        context = f"Vocabulary list: {word_list}"
    else:
        rules = topic_content.get("rules", [])
        examples = topic_content.get("examples", [])
        context = f"Grammar rules: {'; '.join(rules)}\nExamples: {'; '.join(examples)}"

    prompt = f"""You are a Spanish language teacher creating exercises for freshman college students (CEFR A1/A2 level).

Topic: {topic_title}
Type: {topic_type}
{context}

Generate exactly {count} questions. Mix these types:
- "mcq" (multiple choice with 3 distractors)  
- "fill_blank" (fill in the blank)

Return ONLY valid JSON:
{{
  "questions": [
    {{
      "type": "mcq",
      "prompt": "question text",
      "answer": "correct answer",
      "distractors": ["wrong1", "wrong2", "wrong3"]
    }},
    {{
      "type": "fill_blank", 
      "prompt": "sentence with ___ blank",
      "answer": "correct word",
      "distractors": null
    }}
  ]
}}

Rules:
- Questions must match A1/A2 level exactly
- Only use vocabulary and grammar from the given topic
- Make questions varied and interesting, not repetitive
- For vocabulary MCQs, mix both directions (Spanish→English and English→Spanish)
- For grammar fill-blanks, use realistic sentences
- Prompts should be clear and unambiguous"""

    result = _call_groq([{"role": "user", "content": prompt}], max_tokens=1500)
    if result and "questions" in result:
        return result["questions"]
    return None


def ai_generate_activity(topic_title, topic_type, topic_content, count=6):
    """
    Generate interactive classroom activities using AI.
    Returns a list of activity dicts or None.
    """
    if topic_type == "vocabulary":
        words = topic_content.get("words", {})
        word_list = ", ".join([f"{k} = {v}" for k, v in list(words.items())[:12]])
        context = f"Vocabulary: {word_list}"
    else:
        rules = topic_content.get("rules", [])
        examples = topic_content.get("examples", [])
        context = f"Rules: {'; '.join(rules)}\nExamples: {'; '.join(examples)}"

    prompt = f"""You are a Spanish teacher creating interactive practice exercises for A1/A2 students.

Topic: {topic_title} ({topic_type})
{context}

Generate {count} exercises. Each should be either:
- "mcq": multiple choice (4 options including correct answer)
- "fill_blank": fill in the blank

Return ONLY valid JSON:
{{
  "activities": [
    {{
      "type": "mcq",
      "prompt": "What does 'hola' mean?",
      "answer": "hello",
      "options": ["hello", "goodbye", "please", "thank you"]
    }},
    {{
      "type": "fill_blank",
      "prompt": "Yo ___ estudiante. (ser)",
      "answer": "soy",
      "hint": "First person singular of 'ser'"
    }}
  ]
}}

Rules:
- Keep everything at A1/A2 level
- Make exercises fun and engaging
- Vary the difficulty slightly within the set
- For MCQs, always include exactly 4 options
- Shuffle the correct answer position"""

    result = _call_groq([{"role": "user", "content": prompt}], max_tokens=1500)
    if result and "activities" in result:
        return result["activities"]
    return None


def ai_generate_report_insights(cohort_data):
    """
    Generate AI-powered insights for the weekly report.
    Returns a dict with insights or None.
    """
    prompt = f"""You are an educational data analyst. Analyze this Spanish class performance data and provide insights.

Data:
{json.dumps(cohort_data, indent=2, default=str)}

Return ONLY valid JSON:
{{
  "summary_text": "A 2-3 sentence overview of class performance in a warm, professional tone",
  "key_insight": "The single most important thing the lecturer should know",
  "recommendation": "One specific, actionable teaching recommendation",
  "praise_point": "Something positive to highlight about the class"
}}

Rules:
- Use educator-friendly language, not corporate
- Be specific and data-driven
- Keep each field under 50 words
- If data is limited, say so honestly"""

    return _call_groq([{"role": "user", "content": prompt}], max_tokens=500, temperature=0.5)


def ai_grade_open_response(question, student_answer, correct_answer):
    """
    Use AI to grade open-ended or fill-in-the-blank responses more intelligently.
    Returns (score, feedback) or None.
    """
    prompt = f"""You are grading a Spanish language student's answer. Be lenient with accents and minor typos.

Question: {question}
Correct answer: {correct_answer}  
Student's answer: {student_answer}

Return ONLY valid JSON:
{{
  "score": 0.0 to 1.0,
  "is_correct": true/false,
  "feedback": "brief encouraging feedback in English (max 15 words)"
}}

Rules:
- Accept answers without accents (e.g., "esta" for "está")
- Accept minor spelling variations
- Score 1.0 for correct, 0.5 for partially correct, 0.0 for wrong
- Be encouraging in feedback"""

    result = _call_groq([{"role": "user", "content": prompt}], max_tokens=150, temperature=0.2)
    if result and "score" in result:
        return (result["score"], result.get("feedback", ""))
    return None
