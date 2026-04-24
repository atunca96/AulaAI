"""
AI Engine — Groq API integration using only Python stdlib.
Zero external dependencies. Falls back to mock data if API key is missing.
"""

import os
import json
import urllib.request
import urllib.error

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o"


def is_ai_available():
    """Check if OpenRouter API key is configured."""
    return bool(OPENROUTER_API_KEY)


def _call_ai(messages, max_tokens=2000, temperature=0.7, response_json=True):
    """Call the OpenRouter API using urllib."""
    if not OPENROUTER_API_KEY:
        return None

    payload_dict = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_json:
        payload_dict["response_format"] = {"type": "json_object"}

    payload = json.dumps(payload_dict).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://aula-ai.com",  # Required by OpenRouter
            "X-Title": "AulaAI"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            if response_json:
                return json.loads(content)
            return content
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, Exception) as e:
        print(f"[AI] OpenRouter API error: {e}")
        return None


def detect_language(text):
    """Detect the language of the provided text."""
    prompt = f"Detect the language of the following text. Return ONLY a JSON object with a 'language' field (e.g., 'Spanish', 'French', 'German').\n\nText:\n{text[:2000]}"
    result = _call_ai([{"role": "user", "content": prompt}])
    return result.get("language", "Unknown") if result else "Unknown"


def parse_toc(text, language):
    """Parse a Table of Contents text into structured chapters and topics."""
    prompt = f"""You are a curriculum expert. Parse this Table of Contents from a {language} textbook.
Organize it into a list of chapters, each with a list of topics.
Each topic must have a title and a type ('vocabulary' or 'grammar').

Return ONLY valid JSON:
{{
  "chapters": [
    {{
      "number": 1,
      "title": "Chapter Title",
      "topics": [
        {{ "title": "Topic Title", "type": "vocabulary" }},
        {{ "title": "Topic Title", "type": "grammar" }}
      ]
    }}
  ]
}}

Text:
{text}"""
    result = _call_ai([{"role": "user", "content": prompt}])
    return result.get("chapters", []) if result else []


def generate_topic_content(topic_title, topic_type, language):
    """Generate vocabulary or grammar content for a topic in the specified language."""
    if topic_type == "vocabulary":
        prompt = f"""Generate a vocabulary list for the topic '{topic_title}' in {language}.
Include 10-15 essential words/phrases with their English translations.
Return ONLY valid JSON:
{{
  "words": {{
    "word in {language}": "translation in English"
  }}
}}"""
    else:
        prompt = f"""Generate grammar rules and examples for the topic '{topic_title}' in {language}.
Include 3-5 clear rules and 4 illustrative examples.
Return ONLY valid JSON:
{{
  "rules": ["rule 1", "rule 2"],
  "examples": ["example 1", "example 2"]
}}"""

    return _call_ai([{"role": "user", "content": prompt}])


def ai_generate_questions(topic_title, topic_type, topic_content, language, count=6):
    """Generate quiz/practice questions using AI in the specified language."""
    if topic_type == "vocabulary":
        words = topic_content.get("words", {})
        word_list = ", ".join([f"{k} = {v}" for k, v in list(words.items())])
        context = f"Vocabulary list: {word_list}"
    else:
        rules = topic_content.get("rules", [])
        examples = topic_content.get("examples", [])
        context = f"Grammar rules: {'; '.join(rules)}\nExamples: {'; '.join(examples)}"

    prompt = f"""You are a {language} teacher creating exercises for A1/A2 level students.
Topic: {topic_title}
Type: {topic_type}
Language: {language}
{context}

Generate exactly {count} questions. Mix:
- "mcq" (multiple choice with 3 distractors)
- "fill_blank" (fill in the blank)

Return ONLY valid JSON:
{{
  "questions": [
    {{
      "type": "mcq",
      "prompt": "question text in {language} or English depending on context",
      "answer": "correct answer",
      "distractors": ["wrong1", "wrong2", "wrong3"]
    }}
  ]
}}"""
    result = _call_ai([{"role": "user", "content": prompt}])
    return result.get("questions") if result else None


def ai_generate_activity(topic_title, topic_type, topic_content, language, count=6):
    """Generate interactive activities in the specified language."""
    # Similar to ai_generate_questions but for activities
    if topic_type == "vocabulary":
        words = topic_content.get("words", {})
        word_list = ", ".join([f"{k} = {v}" for k, v in list(words.items())])
        context = f"Vocabulary: {word_list}"
    else:
        rules = topic_content.get("rules", [])
        examples = topic_content.get("examples", [])
        context = f"Rules: {'; '.join(rules)}\nExamples: {'; '.join(examples)}"

    prompt = f"""You are a {language} teacher creating practice exercises for A1/A2 students.
Topic: {topic_title} ({topic_type})
Language: {language}
{context}

Generate {count} exercises. Each should be either:
- "mcq": multiple choice (4 options)
- "fill_blank": fill in the blank

Return ONLY valid JSON:
{{
  "activities": [
    {{
      "type": "mcq",
      "prompt": "...",
      "answer": "...",
      "options": ["...", "...", "...", "..."]
    }}
  ]
}}"""
    result = _call_ai([{"role": "user", "content": prompt}])
    return result.get("activities") if result else None


def ai_generate_report_insights(cohort_data):
    """Generate AI insights for reports."""
    prompt = f"Analyze this class performance data and provide insights. Return JSON.\n\nData:\n{json.dumps(cohort_data)}"
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=500)


def ai_grade_open_response(question, student_answer, correct_answer):
    """Grade open responses intelligently."""
    prompt = f"Grade this student's answer. Question: {question}, Correct: {correct_answer}, Student: {student_answer}. Return JSON with 'score' (0-1) and 'feedback'."
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150, temperature=0.2)
    if result and "score" in result:
        return (result["score"], result.get("feedback", ""))
    return (0.0, "Could not grade automatically.")
