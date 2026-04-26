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
import threading

# Simple AI response cache to avoid redundant calls and speed up everything
AI_CACHE_FILE = os.path.join("data", "ai_cache.json")
_ai_memory_cache = {}
# Global lock for thread-safe cache access
_cache_lock = threading.Lock()

def load_ai_cache():
    global _ai_memory_cache
    if os.path.exists(AI_CACHE_FILE):
        try:
            with open(AI_CACHE_FILE, "r", encoding="utf-8") as f:
                with _cache_lock:
                    _ai_memory_cache = json.load(f)
        except:
            _ai_memory_cache = {}

_cache_changed = False

def save_ai_cache():
    global _cache_changed
    if not _cache_changed:
        return
    try:
        os.makedirs(os.path.dirname(AI_CACHE_FILE), exist_ok=True)
        with _cache_lock:
            with open(AI_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(_ai_memory_cache, f)
            _cache_changed = False
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
# Using Claude 3.5 Haiku for fast, high-quality, and logically sound generation
MODEL = "anthropic/claude-3.5-haiku"
file_log(f"AI ENGINE LOADED - PROVIDER: OpenRouter - MODEL: {MODEL}")
if not OPENROUTER_API_KEY:
    file_log("CRITICAL: OPENROUTER_API_KEY IS MISSING!")

import re
import random as py_random


def is_ai_available():
    """Check if OpenRouter API key is configured."""
    return bool(OPENROUTER_API_KEY)


def _call_ai(messages, max_tokens=2000, temperature=0.7, response_json=True, bypass_cache=False):
    """Call the OpenRouter API using urllib."""
    file_log(f"Calling _call_ai with model {MODEL}, response_json={response_json}")
    if not OPENROUTER_API_KEY:
        return None

    # Add a random seed to the prompt to force variety and avoid unintended cache hits
    seed = py_random.randint(1000, 999999)
    
    # Include seed in the messages BEFORE hashing to ensure unique cache keys for activities
    all_messages = messages + [{"role": "system", "content": f"Random Seed: {seed}"}]
    
    cache_messages = json.dumps(all_messages)
    cache_key = hashlib.md5(cache_messages.encode()).hexdigest()
    
    if not bypass_cache:
        with _cache_lock:
            if cache_key in _ai_memory_cache:
                file_log(f"Cache hit for key {cache_key}")
                return _ai_memory_cache[cache_key]

    payload_dict = {
        "model": MODEL,
        "messages": all_messages,
        "max_tokens": max_tokens,
        "temperature": temperature 
    }

    payload = json.dumps(payload_dict).encode("utf-8")
    print(f"[AI] Payload: {json.dumps(payload_dict)[:200]}...")

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
                        with _cache_lock:
                            _ai_memory_cache[cache_key] = parsed
                            global _cache_changed
                            _cache_changed = True
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
    prompt = f"""You are an elite, world-class language textbook author and master polyglot. 
    Generate a HIGH-LEVEL, CAPTIVATING, and COMPREHENSIVE lesson for the topic '{topic_title}' ({topic_type}) to teach {language} to an English speaker.
    
    1. CONTENT (The Study Guide): 
       - EXPLANATIONS: Grammar rules, usage notes, and common mistakes MUST be in ENGLISH. Use a friendly, encouraging, yet professional tone.
       - TARGET CONTENT: Vocabulary and examples must be in {language} (with English translations).
       - 'words': 20-25 HIGH-FREQUENCY words/phrases with English translations. Include gender for nouns if applicable.
       - 'rules': 5-7 CONCEPTUAL grammar rules in ENGLISH. Don't just list rules; explain the 'why' behind them.
       - 'examples': 10-12 NATURAL, REAL-WORLD examples in {language} (with English translations in parentheses).
       - 'usage_notes': Detailed cultural nuances, regional variations, or formal vs. informal tips in ENGLISH.
       - 'common_mistakes': 4-6 specific learner errors (e.g., false cognates, literal translations) explained in ENGLISH.
       - 'cheat_sheet': A punchy, 3-sentence "Mastery Summary" in ENGLISH.
    
    2. QUESTIONS: Generate exactly {question_count} professional, unambiguous interactive questions.
       
       STRICT PEDAGOGICAL RULES:
       - PROMPT LANGUAGE: The 'prompt' field MUST be written in ENGLISH (e.g. "How would you ask for the check?"). 
       - DO NOT TRANSLATE THE PROMPT into {language}.
       - OPTIONS: All answer choices (correct and distractors) MUST be 100% in {language}.
       - NO AMBIGUITY: There must be only ONE logical and grammatically correct answer.
       - CREATIVE DISTRACTORS: For 'mcq', distractors must be plausible, related words that a learner might confuse. Avoid "joke" options.
       - NO REPEATING OPTIONS: The 'answer' MUST NOT be part of the 'distractors' list.
       - FILL_BLANK CONTEXT: Provide a natural {language} sentence as context, then the English instruction.
         * GOOD: "En el restaurante. (At the restaurant.) Complete the sentence: La ____ por favor." -> Answer: "cuenta"
    
    Return ONLY valid JSON with this exact structure:
    {{
      "content": {{
         "words": {{ "word_in_{language}": "english_translation" }},
         "rules": ["..."], "examples": ["..."], "usage_notes": "...", "common_mistakes": ["..."], "cheat_sheet": "..."
      }},
      "questions": [ 
         {{ 
           "type": "mcq", 
           "prompt": "How do you say 'Where is the library?'", 
           "answer": "¿Dónde está la biblioteca?", 
           "distractors": ["¿Dónde está el baño?", "¿Qué hora es?", "¿Cómo te llamas?"] 
         }},
         {{ 
           "type": "fill_blank", 
           "prompt": "Complete the sentence: Yo ____ (beber) agua.", 
           "answer": "bebo" 
         }}
      ]
    }}"""
    
    # Use 3.5 Haiku as it is significantly smarter for logic/JSON
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=4000)


def ai_generate_questions(topic_title, topic_type, topic_content, language, count=6, level='A1'):
    """Generate quiz/practice questions using AI in the specified language."""
    level_norm = (level or 'A1').upper()
    is_beginner = any(x in level_norm for x in ['A1', 'A2'])
    
    # Pedagogical Logic for Prompts
    if is_beginner:
        prompt_lang_instruction = "1. PROMPT LANGUAGE: Write the 'prompt' (the question) in 100% ENGLISH to help beginners grasp fundamentals."
        fill_blank_instruction = "5. FILL_BLANK STYLE: Use 'missing letter' style (e.g. 'H__a' for 'Hola') to help beginners with spelling/recognition."
    elif 'B1' in level_norm or 'B2' in level_norm:
        prompt_lang_instruction = "1. PROMPT LANGUAGE: Mix ENGLISH and target language instructions to gradually transition."
        fill_blank_instruction = "5. FILL_BLANK STYLE: Use full missing words in sentences."
    else: # C1/C2
        prompt_lang_instruction = f"1. PROMPT LANGUAGE: Write the 'prompt' (the question) in 100% {language}."
        fill_blank_instruction = "5. FILL_BLANK STYLE: Use complex missing words/phrases."
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
    prompt = f"""You are a professional language teacher creating HIGH-QUALITY exercises for A1/A2 level students.
    Topic: {topic_title}
    Type: {topic_type}
    Target Language: {language}
    {context}

    STRICT PEDAGOGICAL RULES:
    {prompt_lang_instruction}
    2. OPTION LANGUAGE: All answer choices (correct and distractors) MUST be in {language}.
    3. NO AMBIGUITY: There must be only ONE logically and grammatically correct answer.
    4. VARIETY: Test different words and grammar points. Do not repeat the same logic.
    {fill_blank_instruction}
    6. NO OPEN-ENDED TASKS: Every question must have a single concrete answer.
    7. CONSTRUCTIVE: Always build questions that help the student understand the topic further.
    8. DISTRACTORS: Do NOT overthink distractors. Just use options that are similar to the correct answer.
    9. NO OVERTHINKING: Function properly and efficiently. Do not try to be "smarter" than you are.
    10. NO AUDIO CUES: Do NOT use words like 'Listen' or 'Audio'.

    Generate exactly 12 unique questions. Mix 'mcq' and 'fill_blank'.
    Return ONLY valid JSON:
    {{
      "questions": [
        {{
          "type": "mcq",
          "prompt": "Which word is the correct article for 'Haus'?",
          "answer": "das",
          "distractors": ["der", "die"]
        }},
        {{
          "type": "fill_blank",
          "prompt": "I eat an apple. Ik ____ (eten) een appel.",
          "answer": "eet"
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
        
    # Deduplication and Validation Step
    seen_prompts = set()
    unique_questions = []
    for q in valid_questions:
        ans = str(q.get("answer", "")).strip()
        if not ans: continue
        
        if q.get("type") == "mcq":
            dist = q.get("distractors", [])
            if not isinstance(dist, list): dist = [str(dist)]
            # Filter out answer from distractors if AI slipped it in
            dist = [d for d in dist if str(d).strip().lower() != ans.lower()]
            q["distractors"] = dist[:3]
            # Create the combined options field for the UI
            opts = [ans] + q["distractors"]
            py_random.shuffle(opts)
            q["options"] = opts

        # Normalize prompt for deduplication
        raw_p = q.get("prompt", "")
        p_norm = re.sub(r'[^a-z0-9\u00C0-\u017F]', '', raw_p.lower())
        if p_norm and p_norm not in seen_prompts:
            seen_prompts.add(p_norm)
            unique_questions.append(q)

    # Shuffle for variety and slice to requested count
    py_random.shuffle(unique_questions)
    return unique_questions[:count] if unique_questions else None


def ai_generate_single_activity(topic_title, topic_type, topic_content, language, index=1, history=None, level='A1'):
    """Generate exactly ONE interactive activity with awareness of previous questions to ensure variety."""
    level_norm = (level or 'A1').upper()
    is_beginner = any(x in level_norm for x in ['A1', 'A2'])
    
    if is_beginner:
        prompt_lang_instruction = "1. PROMPT LANGUAGE: Write the 'prompt' in 100% ENGLISH."
        fb_style = "6. FILL_BLANK STYLE: Use 'missing letter' style (e.g. 'H__a' for 'Hola') for A1/A2."
    elif 'B1' in level_norm or 'B2' in level_norm:
        prompt_lang_instruction = "1. PROMPT LANGUAGE: Mix ENGLISH and target language."
        fb_style = "6. FILL_BLANK STYLE: Use full words."
    else:
        prompt_lang_instruction = f"1. PROMPT LANGUAGE: Use 100% {language}."
        fb_style = "6. FILL_BLANK STYLE: Use complex phrases."
    if topic_type == "vocabulary":
        words = topic_content.get("words", {})
        word_list = ", ".join([f"{k} = {v}" for k, v in list(words.items())])
        context = f"Vocabulary to focus on: {word_list}"
    else:
        rules = topic_content.get("rules", [])
        examples = topic_content.get("examples", [])
        context = f"Grammar Rules: {'; '.join(rules)}\nExamples: {'; '.join(examples)}"

    history_str = ""
    if history:
        history_str = f"\nDO NOT REPEAT THESE RECENT QUESTIONS:\n" + "\n".join([f"- {h}" for h in history])

    prompt = f"""You are a professional language teacher creating ONE unique practice exercise for an A1/A2 level student.
Topic: {topic_title}
Target Language: {language}
Context: {context}
{history_str}

STRICT PEDAGOGICAL RULES:
{prompt_lang_instruction}
2. OPTION LANGUAGE: The 'answer' and 'distractors' MUST be entirely in {language}.
3. NO AMBIGUITY: Ensure there is only ONE logically and grammatically correct answer.
4. SIMPLE DISTRACTORS: Do NOT overthink distractors. Use options similar to the correct answer.
5. NO REPETITION: Do not use the same word for both 'answer' and 'distractors'.
{fb_style}
7. NO AUDIO CUES: Do NOT use words like 'Listen' or 'Audio'.
8. CONSTRUCTIVE: Build questions that help the student understand the topic further.
9. EFFICIENCY: Function properly and efficiently. Do not overthink.

Generate exactly ONE exercise (Exercise #{index}). Return ONLY JSON:
{{
  "type": "mcq",
  "prompt": "Which of these words means 'apple'?",
  "answer": "appel",
  "distractors": ["auto", "boek", "huis"]
}} OR
{{
  "type": "fill_blank",
  "prompt": "Complete the sentence: Ik ____ (eten) een appel.",
  "answer": "eet"
}}"""
    
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=1000)
    
    if result and "type" in result:
        # Normalize and validate
        ans = str(result.get("answer", "")).strip()
        if result["type"] == "mcq":
            dist = result.get("distractors", [])
            if not isinstance(dist, list): dist = [str(dist)]
            
            # Ensure answer is NOT in distractors
            dist = [d for d in dist if str(d).strip().lower() != ans.lower()]
            
            # Limit to 3 distractors
            result["distractors"] = dist[:3]
            
            # For backward compatibility with the current UI/Server, 
            # we also provide a shuffled "options" field containing everything
            opts = [ans] + result["distractors"]
            import random
            random.shuffle(opts)
            result["options"] = opts
            
        return result
    return None


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


def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=6):
    """Generate a cohesive batch of activities using a single AI call."""
    # Use a high-entropy seed to force variety
    seed = f"{time.time()}-{py_random.randint(1000, 9999)}"
    
    prompt = f"""You are a professional language teacher creating content for students.
Generate a COHESIVE, CREATIVE LEARNING JOURNEY of {count} unique activities for the topic: "{topic_title}".

Topic Content/Context (Study Guide):
{json.dumps(topic_content)}

STRICT PEDAGOGICAL REQUIREMENTS:
1. INSTRUCTIONAL LANGUAGE: For A1-A2, use 100% ENGLISH prompts. For B1-B2, mix English and {language}. For C1-C2, use 100% {language}.
2. TARGET LANGUAGE: All answer choices, {language} text, and {language} examples MUST be in {language}.
3. STRICT CONTEXT ADHERENCE: You MUST only use vocabulary, grammar, and concepts present in the provided "Topic Content/Context". Do NOT hallucinate external trivia.
4. PEDAGOGICAL DEPTH: Questions should test UNDERSTANDING, not just translation. Build constructive questions to help the student understand the topic further.
5. SIMPLE DISTRACTORS: For 'mcq', do NOT overthink distractors. Just use options that are similar to the correct answer.
6. NO SPANGLISH COMPLETIONS: Do NOT ask the student to complete an English sentence with a {language} word.
7. FILL_BLANK STYLE: For A1-A2, use 'missing letter' style (e.g. 'H__a'). For higher levels, use full words.
8. NO AUDIO CUES: Do NOT use words like 'Listen' or 'Audio'.
9. NO AMBIGUITY: Every question must have exactly one correct and logical answer.
10. TYPES: Mix 'mcq', 'fill_blank', and 'dialogue_order'.
11. EFFICIENCY: Function properly and efficiently. Do not overthink or try to be "smarter" than you are.

REQUIRED JSON STRUCTURES:
- 'mcq': {{ "type": "mcq", "prompt": "English instruction", "answer": "{language} Correct Word", "options": ["{language} Opt 1", "{language} Opt 2", "{language} Opt 3", "{language} Opt 4"] }}
- 'fill_blank': {{ "type": "fill_blank", "prompt": "English instruction with ____ (4 underscores)", "answer": "{language} Missing Word" }}
- 'dialogue_order': {{ "type": "dialogue_order", "prompt": "English instruction (e.g. 'Order this conversation')", "scrambled_lines": ["Line B", "Line A"], "speakers": {{ "Line A": "Persona 1", "Line B": "Persona 2" }}, "correct_order": ["Line A", "Line B"] }}

RANDOM VARIETY SEED: {seed}

Return ONLY a JSON object:
{{
  "activities": [
     // exactly {count} activity objects
  ]
}}

SELF-CORRECTION: Before returning, ensure every 'mcq' has an 'options' array and every 'dialogue_order' has 'scrambled_lines'.
"""
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=3000, temperature=0.9, bypass_cache=True)
    if result and "activities" in result:
        return result["activities"]
    return []
