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

# API helper imports
try:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
except ImportError:
    client = None

def _call_ai(messages, max_tokens=1000, temperature=0.7, bypass_cache=False):
    """Call Anthropic API and return parsed JSON."""
    if not client:
        print("[AI] Anthropic client not initialized (missing API key?)")
        return None
    
    try:
        # Check if we should use 3.5 Haiku or 3.5 Sonnet
        # Using 3.5 Haiku as default for cost/speed
        model = "claude-3-5-haiku-20241022"
        
        # Clean messages
        clean_msgs = []
        for m in messages:
            clean_msgs.append({"role": m["role"], "content": str(m["content"])})
            
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=clean_msgs,
            system="You are a professional language education assistant. Respond ONLY with valid JSON."
        )
        
        text = response.content[0].text
        # Extract JSON if wrapped in markdown
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
            
        return json.loads(text.strip())
    except Exception as e:
        print(f"[AI Error] {e}")
        return None

def is_ai_available():
    return client is not None

def format_activity_by_template(data, level, language):
    """
    Assembles raw AI data into a consistent, un-breakable student activity.
    Ensures that underscores, instructions, and levels are handled deterministically in code.
    """
    atype = data.get("type", "mcq")
    level_norm = (level or "A1").upper()
    is_beginner = any(x in level_norm for x in ["A1", "A2"])
    
    # Standard Instructions based on level
    if is_beginner:
        instr_pfx = "Type the full word to complete: "
        mcq_instr = f"Which of these {language} words means "
    elif "B1" in level_norm or "B2" in level_norm:
        instr_pfx = "Completa la palabra: "
        mcq_instr = f"¿Qué palabra significa "
    else:
        instr_pfx = f"Completa la frase en {language}: "
        mcq_instr = f"Selecciona la opción correcta: "

    # 1. Missing Letter Template (A1-A2 Focused)
    if atype == "fill_blank" and is_beginner and data.get("word") and not data.get("sentence"):
        word = data["word"]
        translation = data.get("translation", "")
        if len(word) > 3:
            display = word[0] + ("_" * (len(word)-2)) + word[-1]
        else:
            display = word[0] + "_" + (word[2] if len(word) > 2 else "")
        
        return {
            "type": "fill_blank",
            "prompt": f"Complete the {language} word for '{translation}': {display}",
            "answer": word,
            "metadata": {"template": "missing_letter"}
        }

    # 2. Sentence Context Template
    if atype == "fill_blank" and "sentence" in data:
        sentence = data["sentence"]
        word = data.get("word", data.get("answer", ""))
        translation = data.get("translation", "")
        if "____" not in sentence:
            sentence = sentence.replace(word, "____") if word in sentence else sentence + " ____"
        hint = f" ({translation})" if translation else ""
        return {
            "type": "fill_blank",
            "prompt": f"Complete the sentence{hint}: {sentence}",
            "answer": word,
            "metadata": {"template": "sentence_context"}
        }

    # 3. Multiple Choice: Pragmatic Response
    if atype == "mcq" and data.get("scenario"):
        scenario = data["scenario"]
        target = data.get("answer", data.get("word", ""))
        return {
            "type": "mcq",
            "prompt": f"In this situation: '{scenario}', what would you say in {language}?",
            "answer": target,
            "distractors": data.get("distractors", []),
            "metadata": {"template": "pragmatic_response"}
        }

    # 4. Multiple Choice: Definition / Meaning
    if atype == "mcq" and data.get("definition"):
        definition = data["definition"]
        target = data.get("answer", data.get("word", ""))
        return {
            "type": "mcq",
            "prompt": f"Which {language} word matches this description: '{definition}'?",
            "answer": target,
            "distractors": data.get("distractors", []),
            "metadata": {"template": "definition_match"}
        }

    # 5. Multiple Choice: Opposites
    if atype == "mcq" and data.get("opposite"):
        opposite_of = data["opposite"]
        target = data.get("answer", data.get("word", ""))
        return {
            "type": "mcq",
            "prompt": f"What is the opposite of the {language} word '{opposite_of}'?",
            "answer": target,
            "distractors": data.get("distractors", []),
            "metadata": {"template": "opposite_match"}
        }

    # 6. Multiple Choice: Categorization
    if atype == "mcq" and data.get("category"):
        category = data["category"]
        target = data.get("answer", data.get("word", ""))
        return {
            "type": "mcq",
            "prompt": f"Which of these is a type of '{category}' in {language}?",
            "answer": target,
            "distractors": data.get("distractors", []),
            "metadata": {"template": "categorization"}
        }

    # 7. Standard Multiple Choice: Translation (Default MCQ)
    if atype == "mcq":
        target = data.get("word", data.get("answer", ""))
        translation = data.get("translation", "")
        return {
            "type": "mcq",
            "prompt": f"{mcq_instr} '{translation}'?",
            "answer": target,
            "distractors": data.get("distractors", []),
            "metadata": {"template": "mcq_translation"}
        }

    # Fallback to whatever AI sent if no template matched
    return data

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=6, level='A1'):
    """Generate quiz/practice questions using the Template Factory approach."""
    level_norm = (level or 'A1').upper()
    
    prompt = f"Create 12 raw data objects for {level_norm} students. Topic: {topic_title}. Content: {json.dumps(topic_content)}. Vary the types (mcq, fill_blank) and the internal logic (use keys like: word/translation, sentence/word, scenario/answer, definition/answer, opposite/answer, category/answer). Return JSON: {{ 'data': [ ... ] }}."
    
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=4000)
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
            final_questions.append(assembled)
            
    py_random.shuffle(final_questions)
    return final_questions[:count]

def ai_generate_single_activity(topic_title, topic_type, topic_content, language, index=1, history=None, level='A1'):
    """Generate one interactive activity using the Template Factory."""
    level_norm = (level or 'A1').upper()
    prompt = f"Create one raw data object for a {level_norm} activity. Topic: {topic_title}. Content: {json.dumps(topic_content)}. Vary the logic (word/translation, sentence/word, scenario/answer, definition/answer, opposite/answer, category/answer). Return JSON ONLY."
    
    data = _call_ai([{"role": "user", "content": prompt}], max_tokens=1000)
    if not data: return None
    
    assembled = format_activity_by_template(data, level, language)
    if assembled and assembled.get("type") == "mcq":
        ans = str(assembled["answer"]).strip()
        dist = assembled.get("distractors", [])
        if not isinstance(dist, list): dist = [str(dist)]
        dist = [d for d in dist if str(d).strip().lower() != ans.lower()]
        import random
        opts = [ans] + dist[:3]
        random.shuffle(opts)
        assembled["options"] = opts
        
    return assembled

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=6):
    """Sequential generator with history tracking."""
    results = []
    history = []
    for i in range(count):
        act = ai_generate_single_activity(topic_title, topic_type, topic_content, language, i+1, history)
        if act:
            results.append(act)
            history.append(act.get("prompt"))
    return results

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

def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=6):
    """Batch generator (legacy, refactored to use single gen for live bars)."""
    return ai_generate_activity(topic_title, topic_type, topic_content, language, count)
