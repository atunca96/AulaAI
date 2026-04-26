"""
AI Engine — OpenRouter API integration using only Python stdlib.
Zero external dependencies. Falls back to mock data if API key is missing.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime
import time
import hashlib

# Simple AI response cache to avoid redundant calls and speed up everything
AI_CACHE_FILE = os.path.join("data", "ai_cache.json")
_ai_memory_cache = {}

def load_ai_cache():
    global _ai_memory_cache
    if os.path.exists(AI_CACHE_FILE):
        try:
            with open(AI_CACHE_FILE, "r", encoding="utf-8") as f:
                _ai_memory_cache = json.load(f)
        except:
            _ai_memory_cache = {}

def save_ai_cache():
    try:
        os.makedirs(os.path.dirname(AI_CACHE_FILE), exist_ok=True)
        with open(AI_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_ai_memory_cache, f)
    except:
        pass

# Initial load
load_ai_cache()

def file_log(msg):
    with open("pipeline.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI] {msg}\n")
        f.flush()

# Railway uses environment variables for security
# Load .env file manually (zero dependencies)
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if "=" in line:
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Using Claude 3.5 Haiku for fast, high-quality, and up-to-date generation
MODEL = "anthropic/claude-3.5-haiku"
file_log(f"AI ENGINE LOADED - PROVIDER: OpenRouter - MODEL: {MODEL}")
if not OPENROUTER_API_KEY:
    file_log("CRITICAL: OPENROUTER_API_KEY IS MISSING!")

import re
import random as py_random


def is_ai_available():
    """Check if OpenRouter API key is configured."""
    return bool(OPENROUTER_API_KEY)


def _call_ai(messages, max_tokens=2000, temperature=0.7, response_json=True):
    """Call the OpenRouter API using urllib."""
    file_log(f"Calling _call_ai with model {MODEL}, response_json={response_json}")
    if not OPENROUTER_API_KEY:
        return None

    # Add a random seed to the prompt to force variety and avoid unintended cache hits
    messages.append({"role": "system", "content": f"Random Seed: {py_random.randint(1000, 999999)}"})

    # Caching logic - now includes the random seed in the hash
    cache_key = hashlib.md5(json.dumps(messages).encode()).hexdigest()
    if cache_key in _ai_memory_cache:
        file_log(f"Cache hit for key {cache_key}")
        return _ai_memory_cache[cache_key]

    payload_dict = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.9 # Even higher temperature for maximum variety
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

    MAX_RETRIES = 2
    for attempt in range(MAX_RETRIES):
        try:
            print(f"[AI] Requesting {MODEL} (Attempt {attempt+1}/{MAX_RETRIES})...")
            
            # Bypass Windows proxy auto-detection which can deadlock in background threads
            proxy_handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(proxy_handler)
            
            with opener.open(req, timeout=30) as resp:
                file_log("AI Request returned.")
                resp_body = resp.read().decode("utf-8")
                
                try:
                    data = json.loads(resp_body)
                except json.JSONDecodeError as e:
                    print(f"[AI] FATAL: OpenRouter returned non-JSON response. Snippet: {resp_body[:500]}")
                    raise Exception(f"Invalid API response (not JSON): {e}")

                if "choices" not in data:
                    raise Exception(f"OpenRouter API Error: {resp_body}")
                content = data["choices"][0]["message"]["content"]
                if response_json:
                    # Robust cleaning for JSON responses
                    clean_content = content.strip()
                    if "```" in clean_content:
                        # Extract content from markdown code block
                        parts = clean_content.split("```")
                        for p in parts:
                            if p.strip().startswith("{") or p.strip().startswith("["):
                                clean_content = p.strip()
                                # Remove language hints like "json"
                                if clean_content.startswith("json"):
                                    clean_content = clean_content[4:].strip()
                                break
                    try:
                        parsed = json.loads(clean_content)
                        # Save to cache
                        _ai_memory_cache[cache_key] = parsed
                        save_ai_cache()
                        return parsed
                    except json.JSONDecodeError as jde:
                        # Handle "Extra data" (valid JSON followed by trailing text)
                        if "Extra data" in str(jde):
                            try:
                                obj, _ = json.JSONDecoder().raw_decode(clean_content)
                                _ai_memory_cache[cache_key] = obj
                                save_ai_cache()
                                return obj
                            except: pass

                        # Attempt to salvage truncated JSON by finding the last closing brace/bracket
                        if clean_content.endswith("...") or len(clean_content) > 1000:
                            print("[AI] Attempting to salvage truncated JSON...")
                            last_brace = clean_content.rfind("}")
                            last_bracket = clean_content.rfind("]")
                            last_valid = max(last_brace, last_bracket)
                            if last_valid > 0:
                                try:
                                    salvaged = json.loads(clean_content[:last_valid+1])
                                    _ai_memory_cache[cache_key] = salvaged
                                    save_ai_cache()
                                    return salvaged
                                except: pass
                        
                        print(f"[AI] JSON Decode Error: {jde}. Raw content: {content[:200]}...")
                        if clean_content.startswith("["): return []
                        raise Exception(f"Malformed JSON from AI: {jde}")
                
                # Save plain text to cache
                _ai_memory_cache[cache_key] = content
                save_ai_cache()
                return content
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            if e.code in [429, 502, 503, 504] and attempt < MAX_RETRIES - 1:
                # Aggressive backoff for rate limits: 10s, 20s, 40s...
                wait_time = 10 * (2 ** attempt)
                file_log(f"HTTP {e.code} (Rate Limit/Busy) received. Waiting {wait_time}s before retry...")
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


def ai_generate_curriculum(language, level, course_name):
    """Generate a structured unit-based curriculum for a specific language and level."""
    prompt = f"""You are a professional curriculum designer for language learning.
    Create a comprehensive curriculum for a {language} course at the {level} level.
    The course name is '{course_name}'.
    
    Structure the curriculum into 4-5 thematic units. Each unit should have a descriptive title and 3-4 specific topics.
    
    Return ONLY a JSON object with a 'chapters' field:
    {{
      "chapters": [
         {{
           "title": "Unit 1: Greetings & Basics",
           "topics": ["Alphabet & Sounds", "Personal Pronouns", "Greetings"]
         }},
         ...
      ]
    }}"""
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=2000)
    
    # Fallback curriculum if AI fails or returns malformed data
    fallback = {
      "chapters": [
        {
          "title": "Unit 1: First Steps",
          "topics": ["Greetings", "Numbers 1-100", "Alphabet"]
        },
        {
          "title": "Unit 2: Daily Life",
          "topics": ["Family Members", "Colors & Clothing", "Telling Time"]
        },
        {
          "title": "Unit 3: Eating & Shopping",
          "topics": ["Food Vocabulary", "At the Restaurant", "Money & Prices"]
        },
        {
          "title": "Unit 4: Moving Around",
          "topics": ["Directions", "City Locations", "Weather"]
        }
      ]
    }

    if not result or not isinstance(result, dict) or "chapters" not in result:
        return fallback
    return result


def detect_language(text):
    """Detect the language of the provided text."""
    prompt = f"Detect the language of the following text. Return ONLY a JSON object with a 'language' field (e.g., 'Spanish', 'French', 'German').\n\nText:\n{text[:2000]}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=4000)
    return result.get("language", "Unknown") if result else "Unknown"


def parse_toc(text, language):
    """Parse a Table of Contents text into structured chapters and topics."""
    prompt = f"""You are an exhaustive curriculum extractor. Parse this Table of Contents from a {language} textbook.
You MUST capture EVERY single chapter and EVERY single topic mentioned in the text. Do not skip or summarize.
Organize it into a list of chapters, each with a list of topics.
Each topic must have a title and a type ('vocabulary' or 'grammar').

Return ONLY valid JSON:
{{
  "chapters": [
    {{
      "number": 1,
      "title": "Exact Unit Title from Text",
      "topics": [
        {{ "title": "Topic Title", "type": "vocabulary" }},
        {{ "title": "Topic Title", "type": "grammar" }}
      ]
    }}
  ]
}}

Text:
{text}"""
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=4000)
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

    # Increase max_tokens for detailed topic descriptions
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=4000)


def generate_full_lesson(topic_title, topic_type, language, question_count=8):
    """Generate both content, study guide, and questions in a single LLM call."""
    lang_instruction = f"in {language}" if language and language != "Unknown" else "in the native language of the topic title"
    
    if topic_type == "vocabulary":
        detail = """
        - 'words': A dictionary of 15-20 essential words/phrases with English translations.
        - 'usage_notes': A few tips on how to use these words in real life.
        - 'cheat_sheet': A 2-sentence summary of the most important takeaways.
        """
    else:
        detail = """
        - 'rules': 4-6 detailed grammar rules with clear explanations.
        - 'examples': 6 illustrative examples with English translations.
        - 'common_mistakes': 2-3 things students usually get wrong.
        - 'cheat_sheet': A 2-sentence summary of the core grammar pattern.
        """

    prompt = f"""You are an elite language textbook author specializing in {language}. 
    Generate a COMPREHENSIVE immersive lesson for the topic '{topic_title}' ({topic_type}).
    
    IMPORTANT: All rules, examples, usage notes, and questions MUST be written in {language}. 
    Only use English for the word translations in the 'words' dictionary and 'examples' translations if helpful.
    
    1. CONTENT (The Study Guide): 
       {detail}
    
    2. QUESTIONS: Generate exactly {question_count} professional, unambiguous interactive questions.
       
       CRITICAL QUALITY RULES:
       - IMMERSION: All prompts and answers MUST be 100% in {language}. No English in the questions.
       - NO GUESSING: For 'fill_blank', you MUST provide a "context setup" sentence before the question so the answer is the ONLY logical choice.
         * INCORRECT: "Benim ____ çok sevimli." (Guessing game)
         * CORRECT: "Küçük bir kedim var. Benim kedim çok sevimli." (Logical follow-up)
       - GRAMMAR HINTS: 
         * For 'grammar/conjugation', provide the base word in parentheses. (e.g. "Dün okula ____. (gitmek)")
         * For 'vocabulary', DO NOT provide the answer in parentheses. Instead, provide a short definition or synonym in {language} as a hint. (e.g. "Bu ____ çok büyük. [Oturduğumuz yer]")
       - MCQ QUALITY: Distractors MUST be plausible but clearly wrong.
    
    Return ONLY valid JSON with this exact structure:
    {{
      "content": {{
         "words": {{ "word_in_{language}": "english_translation" }},
         "rules": ["... rules in {language} ..."],
         "examples": ["... example in {language} (English translation) ..."],
         "usage_notes": "... in {language} ...",
         "common_mistakes": ["... in {language} ..."],
         "cheat_sheet": "... in {language} ..."
      }},
      "questions": [ 
         {{ "type": "mcq", "prompt": "... context-rich question in {language} ...", "answer": "... in {language} ...", "distractors": ["...", "...", "..."] }},
         {{ "type": "fill_blank", "prompt": "... Context Sentence. Question sentence with ____ and (hint word). ...", "answer": "..." }},
         ... 
      ]
    }}"""
    
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=4000)


def ai_generate_questions(topic_title, topic_type, topic_content, language, count=6):
    """Generate quiz/practice questions using AI in the specified language."""
    if not topic_content:
        topic_content = {}
        
    if topic_type == "vocabulary":
        words = topic_content.get("words", {})
        word_list = ", ".join([f"{k} = {v}" for k, v in list(words.items())])
        context = f"Vocabulary list: {word_list}" if word_list else "Generate common words for this topic."
    else:
        rules = topic_content.get("rules", [])
        examples = topic_content.get("examples", [])
        context = f"Grammar rules: {'; '.join(rules)}\nExamples: {'; '.join(examples)}" if (rules or examples) else "Generate basic grammar rules for this level."

    lang_context = f"Target Language: {language}" if language and language != "Unknown" else "Target Language: Infer from the context"
    prompt = f"""You are a professional language teacher creating HIGH-QUALITY immersive exercises for A1/A2 level students.
    Topic: {topic_title}
    Type: {topic_type}
    {lang_context}
    {context}

    STRICT PEDAGOGICAL RULES:
    1. VARIETY: This is the MOST IMPORTANT rule. Every single question must be unique. Test different words, different grammar points, and use different sentence structures. NEVER repeat the same logic.
    2. IMMERSION: Both the 'prompt' and the 'answer' MUST be written entirely in {language}.
    3. FILL_BLANK MUST HAVE BLANKS: For 'fill_blank', you MUST include exactly one '____' (4 underscores) in the prompt where the answer goes.
       * GOOD: "Ich ____ (heißen) Michael." -> Answer: "heiße"
    4. NO OPEN-ENDED TASKS: Every question must have a single, concrete, short correct answer.
    5. NO MATCHING: Only MCQ or Fill-in-the-blank.
    6. UNAMBIGUOUS: There must be only one correct answer.
    7. TRUE/FALSE AS MCQ: Use type 'mcq' with 2 options ('Richtig'/'Falsch', etc.).

    Generate exactly 10 high-quality, unique questions. Mix:
    - "mcq" (multiple choice with 1 to 3 distractors)
    - "fill_blank" (fill in the blank)

    Return ONLY valid JSON:
    {{
      "questions": [
        {{
          "type": "mcq",
          "prompt": "... context-rich prompt in {language} ...",
          "answer": "...",
          "distractors": ["...", "...", "..."]
        }},
        {{
          "type": "fill_blank",
          "prompt": "... Context. Sentence with ____ (hint). ...",
          "answer": "..."
        }}
      ]
    }}"""
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=4000)
    questions = result.get("questions") if result else None
    
    if not questions: return None
    
    # Validation step: Filter out broken questions
    valid_questions = []
    for q in questions:
        q_type = q.get("type")
        q_prompt = (q.get("prompt") or "").strip()
        q_answer = (q.get("answer") or "").strip()
        
        if not q_prompt or not q_answer:
            continue
            
        if q_type == "fill_blank" and "____" not in q_prompt:
            continue
            
        # Filter out obvious "descriptive" or "matching" prompts that the AI slipped in
        forbidden_keywords = ["describe", "beschreibe", "write", "schreibe", "match", "verbinde", "pair", "connect"]
        if any(word in q_prompt.lower() for word in forbidden_keywords):
            continue
            
        valid_questions.append(q)
        
    # Deduplication Step: Ensure no two questions have the same prompt (normalized)
    seen_prompts = set()
    unique_questions = []
    for q in valid_questions:
        # Normalize prompt: lowercase and remove all non-alphanumeric characters
        raw_p = q.get("prompt", "")
        p_norm = re.sub(r'[^a-z0-9\u00C0-\u017F]', '', raw_p.lower())
        if p_norm and p_norm not in seen_prompts:
            seen_prompts.add(p_norm)
            unique_questions.append(q)
        else:
            file_log(f"Discarding duplicate question: {raw_p[:50]}...")

    # Shuffle for variety and slice to requested count
    py_random.shuffle(unique_questions)
    return unique_questions[:count] if unique_questions else None


def ai_generate_single_activity(topic_title, topic_type, topic_content, language, index=1, history=None):
    """Generate exactly ONE interactive activity with awareness of previous questions to ensure variety."""
    if topic_type == "vocabulary":
        words = topic_content.get("words", {})
        word_list = ", ".join([f"{k} = {v}" for k, v in list(words.items())])
        context = f"Vocabulary: {word_list}"
    else:
        rules = topic_content.get("rules", [])
        examples = topic_content.get("examples", [])
        context = f"Rules: {'; '.join(rules)}\nExamples: {'; '.join(examples)}"

    history_str = ""
    if history:
        history_str = f"\nALREADY GENERATED QUESTIONS (DO NOT REPEAT THESE):\n" + "\n".join([f"- {h}" for h in history])

    lang_context = f"Language: {language}" if language and language != "Unknown" else "Language: Infer from the context"
    prompt = f"""You are a professional language teacher creating ONE unique practice exercise for A1/A2 students.
Topic: {topic_title} ({topic_type})
{lang_context}
{context}
{history_str}

STRICT RULES:
1. IMMERSION: ALL text (prompt, answer, options) MUST be written entirely in {language}.
2. NO TRANSLATIONS: Do NOT ask for translations to English, Turkish, or any other language.
3. STRICT MONOLINGUALISM: Use ONLY {language}. Do NOT include any English or Turkish words in the distractors or prompt.
4. TYPE: Only "mcq" or "fill_blank".
5. NO MATCHING: Never generate "Match" or "Pair" instructions.
6. BLANKS: "fill_blank" MUST contain '____'.
7. UNIQUE: The question MUST be different from the history above. Test a different word or concept.

Generate exactly ONE exercise (Exercise #{index}). Return ONLY JSON:
{{
  "type": "mcq",
  "prompt": "...",
  "answer": "...",
  "options": ["...", "...", "...", "..."]
}} OR
{{
  "type": "fill_blank",
  "prompt": "... ____ (hint) ...",
  "answer": "..."
}}"""
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=1000)
    if result and result.get("type") == "mcq" and "options" in result:
        import random
        random.shuffle(result["options"])
    return result if result and "type" in result else None


def ai_generate_activity(topic_title, topic_type, topic_content, language, count=6):
    """Fallback generator that calls single activity generation with history tracking."""
    results = []
    history = []
    for i in range(count):
        act = ai_generate_single_activity(topic_title, topic_type, topic_content, language, i+1, history)
        if act:
            results.append(act)
            history.append(act.get("prompt"))
    return results

def ai_generate_report_insights(cohort_data):
    """Generate detailed AI insights for reports in both English and Turkish."""
    prompt = f"""You are an expert educational consultant. Analyze the following class performance data and generate a DETAILED weekly report.
    
    Data:
    {json.dumps(cohort_data)}
    
    Requirements:
    1. Provide an executive summary of the class performance.
    2. Identify specific 'Flawed Topics' with detailed breakdowns of why students are struggling (e.g. specific grammar confusion, vocabulary retention).
    3. Provide actionable recommendations for the lecturer.
    4. Provide individual 'Student Spotlights' for at-risk students with personalized original commentaries.
    
    YOU MUST GENERATE THE ENTIRE REPORT IN BOTH ENGLISH AND TURKISH.
    
    Return ONLY a JSON object with this structure:
    {{
      "en": {{
        "summary": "Detailed English summary",
        "topic_breakdown": [{{ "topic": "Topic Name", "analysis": "Detailed Analysis", "recommendation": "Step-by-step advice" }}],
        "at_risk_commentaries": [{{ "name": "Student Name", "commentary": "Personalized commentary" }}],
        "general_advice": "Overall advice for next week"
      }},
      "tr": {{
        "summary": "Detaylı Türkçe özet",
        "topic_breakdown": [{{ "topic": "Konu Adı", "analysis": "Detaylı Analiz", "recommendation": "Adım adım tavsiye" }}],
        "at_risk_commentaries": [{{ "name": "Öğrenci Adı", "commentary": "Kişiselleştirilmiş yorum" }}],
        "general_advice": "Gelecek hafta için genel tavsiye"
      }}
    }}
    """
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=3500)


def ai_grade_open_response(question, student_answer, correct_answer):
    """Grade open responses intelligently."""
    prompt = f"Grade this student's answer. Question: {question}, Correct: {correct_answer}, Student: {student_answer}. Return JSON with 'score' (0-1) and 'feedback'."
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150, temperature=0.2)
    if result and "score" in result:
        return (result["score"], result.get("feedback", ""))
    return (0.0, "Could not grade automatically.")
