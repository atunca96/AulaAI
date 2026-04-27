"""
AI Engine — Logic for calling Claude and processing educational outputs.
This module uses a Template Factory approach to ensure consistent, unbreakable question formats.
"""

import json
import re
import os
import time
import random as py_random
import logging
from datetime import datetime

# Try to load .env if it exists
if os.path.exists(".env"):
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v
    except Exception as e:
        print(f"[WARN] Failed to load .env: {e}")

# API helper imports
try:
    import anthropic
    ant_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=ant_key) if ant_key else None
except ImportError:
    client = None

# MODEL CONSTANTS
MODEL_SPEED = "anthropic/claude-3.5-haiku"
MODEL_QUALITY = "anthropic/claude-3.5-sonnet"

# Direct Anthropic mapping
ANT_MODEL_MAP = {
    MODEL_SPEED: "claude-3-5-haiku-20241022",
    MODEL_QUALITY: "claude-3-5-sonnet-20241022"
}

def _call_openrouter(messages, model=MODEL_SPEED, max_tokens=1000, temperature=0.7):
    """Call OpenRouter API (supports Haiku) as a fallback/alternative."""
    import http.client
    import json
    
    or_key = os.environ.get("OPENROUTER_API_KEY")
    if not or_key: return None
    
    try:
        conn = http.client.HTTPSConnection("openrouter.ai")
        headers = {
            "Authorization": f"Bearer {or_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "AulaAI"
        }
        
        # Use Claude 3.5 Haiku via OpenRouter
        # Include PEDAGOGY_INSTRUCTION as a system message if possible, 
        # but OpenRouter usually takes it as the first message or in a 'system' field depending on the provider.
        # We'll use the 'system' field which is standard for Claude.
        payload = {
            "model": model,
            "messages": messages,
            "system": PEDAGOGY_INSTRUCTION,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        conn.request("POST", "/api/v1/chat/completions", json.dumps(payload), headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        
        resp_json = json.loads(data)
        if "choices" in resp_json:
            text = resp_json["choices"][0]["message"]["content"]
            # Clean up potential markdown formatting
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        else:
            print(f"[OpenRouter Error] {data}")
            return None
    except Exception as e:
        print(f"[OpenRouter Exception] {e}")
        return None

def _call_ai(messages, model=MODEL_SPEED, max_tokens=1000, temperature=0.7, bypass_cache=False):
    """Call AI (OpenRouter or Anthropic) and return parsed JSON."""
    # 1. Try OpenRouter first if key exists
    if os.environ.get("OPENROUTER_API_KEY"):
        res = _call_openrouter(messages, model, max_tokens, temperature)
        if res: return res
        
    # 2. Fallback to direct Anthropic if configured
    if not client:
        print("[AI] No AI provider available (check ANTHROPIC_API_KEY or OPENROUTER_API_KEY)")
        return None
    
    try:
        # Map OpenRouter model names to direct Anthropic names if needed
        ant_model = ANT_MODEL_MAP.get(model, "claude-3-5-haiku-20241022")
        clean_msgs = []
        for m in messages:
            clean_msgs.append({"role": m["role"], "content": str(m["content"])})
            
        response = client.messages.create(
            model=ant_model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=clean_msgs,
            system=PEDAGOGY_INSTRUCTION + "\nRespond ONLY with valid JSON."
        )
        
        text = response.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        return json.loads(text.strip())
    except Exception as e:
        print(f"[AI Error] {e}")
        return None

def is_ai_available():
    return (client is not None) or (os.environ.get("OPENROUTER_API_KEY") is not None)

def detect_language(text):
    """Detect the language of the provided text."""
    if not client: return "Spanish"
    try:
        prompt = f"Identify the primary language of this text. Respond with ONLY the language name (e.g. 'Spanish', 'French'). Text: {text[:500]}"
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except:
        return "Spanish"

def ai_generate_curriculum(language, level, course_name):
    """AI drafts a detailed curriculum based on topic, level, and language."""
    prompt = f"Create a comprehensive, full-semester language learning curriculum for a course called '{course_name}' at {level} level in {language}. Return a JSON object with a 'chapters' key containing an array of EXACTLY 10 chapters to ensure a complete learning path. Each chapter must have 'number', 'title', and 'topics' (an array of 3-5 distinct objects with 'title', 'type' (vocabulary/grammar/culture), 'difficulty', 'sort_order'). Respond ONLY with valid JSON."
    return _call_ai([{"role": "user", "content": prompt}], model=MODEL_QUALITY, max_tokens=4000)

PEDAGOGY_INSTRUCTION = """
# MANDATORY INSTRUCTIONS (DO NOT DEVIATE)
1. LANGUAGE RULES:
   - MODE A (Word Identification): Native prompt -> Target options. (All 4 options MUST be in Target Language).
   - MODE B (Meaning Identification): Target prompt -> Native options. (All 4 options MUST be in English or Turkish).
   - NEVER MIX Target and Native languages in the same option list.
   - For beginners (A1-A2), keep instructions in ENGLISH.

2. AVOID SELF-REFERENCE:
   - If the question is "What does [WORD] mean?", the answer CANNOT be [WORD]. It must be the translation.
   - A question is a FAILURE if the correct answer is already visible in the prompt.
"""

def generate_full_lesson(topic_title, topic_type, language, question_count=8):
    """Generate both content and questions in a single LLM call for maximum speed."""
    lang_instruction = f"in {language}" if language and language != "Unknown" else "in the native language of the topic title"
    
    if topic_type == "vocabulary":
        structure = """
          "content": { "words": { "word": "translation" } },
          "questions": [ { "type": "mcq", "answer": "...", "distractors": ["...", "...", "..."], "prompt": "..." } ]
        """
        detail = "Include 10-15 essential words/phrases with their English translations."
    else:
        structure = """
          "content": { "rules": ["..."], "examples": ["..."] },
          "questions": [ { "type": "fill_blank", "sentence": "...", "answer": "...", "translation": "..." } ]
        """
        detail = "Include 3-5 clear rules and 4 illustrative examples."

    prompt = f"""
    Generate a full educational lesson for the topic '{topic_title}' ({topic_type}) {lang_instruction}.
    
    1. CONTENT: {detail}
    2. QUESTIONS: Generate exactly {question_count} interactive questions following the SYSTEM rules.
    
    Return ONLY valid JSON with this exact structure:
    {{
      "content": {{ ... }},
      "questions": [
        {{ "type": "mcq", "answer": "...", "distractors": ["opt1", "opt2", "opt3"], "prompt": "..." }},
        {{ "type": "fill_blank", "sentence": "sentence with ____", "answer": "word", "translation": "hint" }}
      ]
    }}"""
    
    result = _call_ai([{"role": "user", "content": prompt}], model=MODEL_QUALITY, max_tokens=4000)
    # ... (rest of logic) ...
    if not result: return None
    
    # Process the questions through the template factory
    raw_qs = result.get("questions", [])
    final_qs = []
    for q in raw_qs:
        assembled = format_activity_by_template(q, "A1", language) # Default A1 for lesson generation
        if assembled:
            if assembled["type"] == "mcq":
                ans = str(assembled["answer"]).strip()
                dist = assembled.get("distractors", [])
                if not isinstance(dist, list): dist = [str(dist)]
                dist = [d for d in dist if str(d).strip().lower() != ans.lower()]
                import random
                opts = [ans] + dist[:3]
                random.shuffle(opts)
                assembled["options"] = opts
                if len(opts) < 4: continue
            final_qs.append(assembled)
    
    result["questions"] = final_qs
    return result

def format_activity_by_template(data, level, language):
    """Assembles raw AI data into a consistent, un-breakable student activity."""
    atype = data.get("type", "mcq")
    level_norm = (level or "A1").upper()
    is_beginner = any(x in level_norm for x in ["A1", "A2"])
    
    if is_beginner:
        instr_pfx = "Type the full word to complete: "
        mcq_instr = f"Which of these {language} words means "
    else:
        # For intermediate+ we still use English instructions as requested
        instr_pfx = f"Complete the sentence in {language}: "
        mcq_instr = f"Select the correct {language} option for "

    if atype == "fill_blank" and is_beginner and data.get("word") and not data.get("sentence"):
        word = data["word"]
        translation = data.get("translation", "")
        display = word[0] + ("_" * (len(word)-2)) + word[-1] if len(word) > 3 else word[0] + "_" + (word[2] if len(word) > 2 else "")
        return {
            "type": "fill_blank",
            "prompt": f"Complete the {language} word for '{translation}': {display}",
            "answer": word,
            "metadata": {"template": "missing_letter"}
        }

    if atype == "fill_blank" and "sentence" in data:
        sentence = data["sentence"]
        word = data.get("word") or data.get("answer") or data.get("target") or "???"
        translation = data.get("translation") or data.get("meaning") or data.get("english") or ""
        if "____" not in sentence:
            # Try to hide the word if it's there
            if word != "???" and word in sentence:
                sentence = sentence.replace(word, "____")
            else:
                sentence = sentence + " ____"
        hint = f" ({translation})" if translation else ""
        if not sentence or sentence.strip() == "" or "____" not in sentence:
            return None
        return {
            "type": "fill_blank",
            "prompt": f"Complete the sentence{hint}: {sentence}",
            "answer": word,
            "metadata": {"template": "sentence_context"}
        }

    if atype == "mcq" and data.get("scenario"):
        return {
            "type": "mcq",
            "prompt": f"In this situation: '{data['scenario']}', what would you say in {language}?",
            "answer": data.get("answer", data.get("word", "")),
            "distractors": data.get("distractors", []),
            "metadata": {"template": "pragmatic_response"}
        }

    if atype == "mcq" and data.get("definition"):
        return {
            "type": "mcq",
            "prompt": f"Which {language} word matches this description: '{data['definition']}'?",
            "answer": data.get("answer", data.get("word", "")),
            "distractors": data.get("distractors", []),
            "metadata": {"template": "definition_match"}
        }

    if atype == "mcq" and data.get("opposite"):
        return {
            "type": "mcq",
            "prompt": f"What is the opposite of the {language} word '{data['opposite']}'?",
            "answer": data.get("answer", data.get("word", "")),
            "distractors": data.get("distractors", []),
            "metadata": {"template": "opposite_match"}
        }

    if atype == "mcq" and data.get("category"):
        return {
            "type": "mcq",
            "prompt": f"Which of these is a type of '{data['category']}' in {language}?",
            "answer": data.get("answer", data.get("word", "")),
            "distractors": data.get("distractors", []),
            "metadata": {"template": "categorization"}
        }

    if atype == "mcq":
        target = data.get("word") or data.get("answer") or data.get("target") or "???"
        translation = data.get("translation") or data.get("meaning") or data.get("english") or "???"
        
        # If we have a prompt or question already, use it
        final_prompt = data.get("prompt") or data.get("question")
        if not final_prompt:
            final_prompt = f"{mcq_instr} '{translation}'?"
            
        # Validation: If the answer is already in the prompt, it's a hallucination
        if target and target.lower() in final_prompt.lower():
            # This is only okay if the prompt is asking for an opposite or something complex.
            # But for simple "What does X mean?", it's a fail.
            if "mean" in final_prompt.lower() or "anlamı" in final_prompt.lower():
                return None

        if not final_prompt or final_prompt == "???" or not target or target == "???":
            return None
            
        return {
            "type": "mcq",
            "prompt": final_prompt,
            "answer": target,
            "distractors": data.get("distractors", []),
            "metadata": {"template": "mcq_translation"}
        }

    return data

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=6, level='A1', use_quality=True):
    """Generate quiz/practice questions using the Template Factory approach."""
    level_norm = (level or 'A1').upper()
    prompt = f"""{PEDAGOGY_INSTRUCTION}
    
    TASK: Generate 12 interactive questions for {level_norm} students learning {language}.
    
    You MUST provide a mix of these 3 types:
    1. MCQ MODE A (Target word identification): 
       - Prompt: "Which {language} word means 'Apple'?"
       - Answer: "{language} word for Apple"
       - Distractors: [3 other {language} words]
    2. MCQ MODE B (Meaning identification):
       - Prompt: "What does the {language} word '{language}Word' mean?"
       - Answer: "Native (English/Turkish) meaning"
       - Distractors: [3 other Native meanings]
    3. FILL BLANK:
       - Sentence: "{language} sentence with ____"
       - Answer: "Correct {language} word"
       - Translation: "English/Turkish hint"

    IMPORTANT: ALL 4 options in an MCQ must be in the SAME language. Never mix {language} and English/Turkish in the options.
    Return a JSON object with a "data" key containing an array of objects.
    Each object must have "type" ('mcq' or 'fill_blank') and the appropriate keys from the logic above.
    
    Return JSON ONLY.
"""
    
    target_model = MODEL_QUALITY if use_quality else MODEL_SPEED
    result = _call_ai([{"role": "user", "content": prompt}], model=target_model, max_tokens=4000)
    print(f"[AI] Raw data for {topic_title}: {json.dumps(result)[:200]}...")
    raw_list = result.get("data") if result else None
    if not raw_list: return None
    
    final_questions = []
    for item in raw_list:
        assembled = format_activity_by_template(item, level, language)
        if assembled:
            if assembled["type"] == "mcq":
                ans = str(assembled["answer"]).strip()
                dist = assembled.get("distractors", [])
                if not isinstance(dist, list): dist = [str(dist)]
                dist = [d for d in dist if str(d).strip().lower() != ans.lower()]
                import random
                opts = [ans] + dist[:3]
                random.shuffle(opts)
                assembled["options"] = opts
                if len(opts) < 4: continue
            final_questions.append(assembled)
            
    py_random.shuffle(final_questions)
    return final_questions[:count]

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=6, level='A1'):
    """Definitive Unified Generator: Activities use the fast model."""
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, use_quality=False)

def ai_generate_report_insights(cohort_data):
    """Generate detailed AI insights for reports."""
    prompt = f"Analyze class data and generate report JSON with 'en' and 'tr' keys. Data: {json.dumps(cohort_data)}"
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=3500)

def ai_grade_open_response(question, student_answer, correct_answer):
    """Grade responses."""
    prompt = f"Grade Question: {question}, Correct: {correct_answer}, Student: {student_answer}. Return JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150, temperature=0.2)
    if result and "score" in result:
        return (result["score"], result.get("feedback", ""))
    return (0.0, "Could not grade automatically.")

def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=6, level='A1'):
    """Batch generator (legacy, refactored to use single gen for live bars)."""
    return ai_generate_activity(topic_title, topic_type, topic_content, language, count, level)
