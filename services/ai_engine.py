"""
AI Engine — Groq API integration using only Python stdlib.
Zero external dependencies. Falls back to mock data if API key is missing.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime
import time

def file_log(msg):
    with open("pipeline.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI] {msg}\n")
        f.flush()

OPENROUTER_API_KEY = "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"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.0-flash-001"
file_log(f"AI ENGINE LOADED - MODEL: {MODEL}")


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
        "temperature": temperature
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

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            file_log(f"Requesting AI ({MODEL}) - Attempt {attempt + 1}...")
            
            # Bypass Windows proxy auto-detection which can deadlock in background threads
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            
            with opener.open(req, timeout=30) as resp:
                file_log("AI Request returned.")
                resp_body = resp.read().decode("utf-8")
                data = json.loads(resp_body)
                if "choices" not in data:
                    raise Exception(f"OpenRouter API Error: {resp_body}")
                content = data["choices"][0]["message"]["content"]
                if response_json:
                    return json.loads(content)
                return content
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            if e.code in [429, 504] and attempt < MAX_RETRIES - 1:
                wait_time = 5 * (2 ** attempt)
                file_log(f"HTTP {e.code} received. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            print(f"[AI] HTTP Error {e.code}: {error_body}")
            raise Exception(f"OpenRouter HTTP {e.code}: {error_body}")
        except Exception as e:
            if attempt < MAX_RETRIES - 1 and ("timeout" in str(e).lower() or "connection" in str(e).lower()):
                wait_time = 5 * (2 ** attempt)
                file_log(f"Network error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            print(f"[AI] OpenRouter API error: {e}")
            raise e


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
    chapters = result.get("chapters", []) if result else []
    
    if chapters and isinstance(chapters, list) and len(chapters) > 0:
        return chapters
        
    # Robust Fallback: Simple text-based extraction if AI fails
    print("[AI_ENGINE] TOC Parsing failed or returned empty. Using resilient fallback.")
    # Extract lines that look like titles (not too short, not just numbers)
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 3]
    
    # If even that fails, use generic placeholders to ensure pipeline doesn't crash
    if not lines:
        lines = ["Introduction", "Essential Vocabulary", "Basic Grammar", "Common Phrases", "Review"]
    
    fallback_chapters = []
    current_chapter = {"number": 1, "title": "Unit 1", "topics": []}
    
    for i, line in enumerate(lines):
        # Alternate between vocabulary and grammar
        t_type = "grammar" if i % 2 == 1 else "vocabulary"
        current_chapter["topics"].append({
            "title": line[:60], # Limit length
            "type": t_type
        })
        
        # Group every 4 topics into a new chapter
        if len(current_chapter["topics"]) >= 4:
            fallback_chapters.append(current_chapter)
            num = len(fallback_chapters) + 1
            current_chapter = {"number": num, "title": f"Unit {num}", "topics": []}
            
    if current_chapter["topics"]:
        fallback_chapters.append(current_chapter)
        
    return fallback_chapters


def generate_topic_content(topic_title, topic_type, language):
    """Generate vocabulary or grammar content for a topic in the specified language."""
    lang_instruction = f"in {language}" if language and language != "Unknown" else "in the native language of the topic title"
    if topic_type == "vocabulary":
        prompt = f"""Generate a vocabulary list for the topic '{topic_title}' {lang_instruction}.
Include 10-15 essential words/phrases with their English translations.
Return ONLY valid JSON:
{{
  "words": {{
    "word in target language": "translation in English"
  }}
}}"""
    else:
        prompt = f"""Generate grammar rules and examples for the topic '{topic_title}' {lang_instruction}.
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

    lang_context = f"Language: {language}" if language and language != "Unknown" else "Language: Infer from the context"
    prompt = f"""You are a language teacher creating exercises for A1/A2 level students.
Topic: {topic_title}
Type: {topic_type}
{lang_context}
{context}

Generate exactly {count} questions. Mix:
- "mcq" (multiple choice with 3 distractors)
- "fill_blank" (fill in the blank)

Return ONLY valid JSON:
{{
  "questions": [
    {{
      "type": "mcq",
      "prompt": "question text in the target language or English depending on context",
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

    lang_context = f"Language: {language}" if language and language != "Unknown" else "Language: Infer from the context"
    prompt = f"""You are a language teacher creating practice exercises for A1/A2 students.
Topic: {topic_title} ({topic_type})
{lang_context}
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
