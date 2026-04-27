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
                content = res_json["choices"][0]["message"]["content"].strip()
                # Universal extraction: find first/last '{' or '['
                braces_start = content.find('{')
                brackets_start = content.find('[')
                
                # Determine which comes first
                start = -1
                end = -1
                if braces_start != -1 and (brackets_start == -1 or braces_start < brackets_start):
                    start = braces_start
                    end = content.rfind('}')
                elif brackets_start != -1:
                    start = brackets_start
                    end = content.rfind(']')

                if start != -1 and end != -1 and end > start:
                    json_str = content[start:end+1]
                    try:
                        return json.loads(json_str)
                    except:
                        pass
                
                # Fallback to direct load
                return json.loads(content)
    except Exception as e:
        print(f"AI Error: {str(e)}")
    return None

def detect_language(text):
    prompt = f"Detect language. JSON: {{'language': '...'}}. Text: {text[:500]}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=50)
    return result.get("language", "English") if result else "English"

def generate_full_lesson(topic, topic_type, language, count=6, level='A1'):
    """Generates a complete structured lesson with vocab, grammar, and examples."""
    import json
    from services.language_data import get_reference_prompt
    
    # Only apply the "Complete set" requirement if the topic is actually about an alphabet
    # We include variations for Spanish, French, German, Italian, Portuguese, Turkish, etc.
    alphabet_keywords = [
        "alphabet", "syllabary", "hiragana", "katakana", "cyrillic", "pinyin", 
        "alfabeto", "abecedario", "alfabe", "abcto", "letters", "buchstaben"
    ]
    is_alphabet_topic = any(x in topic.lower() for x in alphabet_keywords)
    
    reference_data = ""
    if is_alphabet_topic:
        reference_data = get_reference_prompt(language)
    
    alphabet_rule = ""
    if is_alphabet_topic:
        alphabet_rule = f"""
    CRITICAL REQUIREMENT for Alphabets/Syllabaries:
    Since this topic is about the alphabet/syllabary in {language}, you MUST include EVERY SINGLE CHARACTER/PHONEME. 
    {reference_data}
    - For CHINESE: Use the Pinyin initials and finals from the reference data.
    - For JAPANESE: Use the Hiragana/Katakana from the reference data.
    Skipping characters from the reference data is a pedagogical failure. Use as many 'vocabulary' pages as needed to list the ENTIRE set.
    """
    
    explanation_rule = ""
    if level in ['A1', 'A2']:
        explanation_rule = f"1. EXPLANATION LANGUAGE: All grammar explanations, instructions, and descriptions MUST be in English. Only the actual {language} examples and vocabulary terms should be in {language}."
    else:
        explanation_rule = f"1. EXPLANATION LANGUAGE: You may use English, {language}, or a mix of both for explanations, as appropriate for {level} level immersion."

    prompt = f"""Write a professional {language} lesson for the topic: '{topic}' ({topic_type}).
    {alphabet_rule}
    
    Return ONLY a JSON object:
    {{
      "pages": [
        {{ "type": "vocabulary", "title": "...", "items": [ {{ "term": "...", "translation": "..." }} ] }},
        {{ "type": "grammar", "title": "...", "text": "..." }},
        {{ "type": "examples", "title": "...", "list": [ {{ "speaker": "...", "text": "..." }} ] }}
      ]
    }}
    
    Rules:
    {explanation_rule}
    2. Content must be level-appropriate ({level}).
    3. NO LITERAL TRANSLATIONS: Ensure all sentences follow natural {language} grammar.
    4. You can generate between 3 to 6 pages. 
    5. Each page must have a 'type' (vocabulary, grammar, or examples) and a 'title'.
    """
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=2500)
    return result if result else {}

# Agnostic Engine v1.1 - Diversity Quotas Restored
def is_ai_available():
    return os.getenv("OPENROUTER_API_KEY") is not None

def get_language_profile(language):
    """Classifies languages into Pedagogical DNA profiles to drive agnostic generation."""
    logographic = ["Chinese"]
    syllabic = ["Japanese", "Russian", "Arabic", "Greek", "Korean"]
    agglutinative = ["Turkish", "Hungarian", "Finnish"]
    
    if language in logographic: return "logographic"
    if language in syllabic: return "syllabic"
    if language in agglutinative: return "agglutinative"
    return "inflected_latin" # Default for Spanish, French, German, etc.

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=6, level='A1', use_quality=True, existing_questions=None):
    """Agnostic Engine: Generates questions based on the language's specific Pedagogical DNA."""
    c = int(count)
    request_count = int((c + 1) * 1.5) if c % 2 != 0 else int(c * 1.5)
    
    # Level-Gated Immersion Rule
    is_beginner = any(lvl in level.upper() for lvl in ["A1", "A2"])
    instruction_lang = "English" if is_beginner else language
    
    # Language DNA Analysis
    dna = get_language_profile(language)
    
    # Sanitize content for prompt
    content_str = json.dumps(topic_content, ensure_ascii=False)
    
    # Handle non-redundancy
    # Handle non-redundancy (STRICT)
    forbidden_clause = ""
    if existing_questions and len(existing_questions) > 0:
        qs_list = "\n".join([f"- {q['prompt']}" for q in existing_questions])
        forbidden_clause = f"\nCRITICAL: DO NOT REPEAT or mimic these existing questions:\n{qs_list}\n"

    # DNA-Aware Pedagogical Instructions
    dna_instructions = ""
    diversity_quota = "Vary the question profile."
    
    # Contextual Quota Relaxation (Alphabet/Phonetics usually can't do sentence fills)
    is_phonetic_topic = any(x in topic_title.lower() for x in ["alphabet", "pinyin", "phonetic", "initial", "final", "script"])
    
    if dna == "logographic":
        if is_phonetic_topic:
            diversity_quota = "MIX: 3x 'Character to Sound', 3x 'Sound to Character'."
        else:
            diversity_quota = "MIX: 2x 'Character to Sound', 2x 'Sound to Character', 2x 'Contextual Sentence Fill'."
        
        dna_instructions = f"""
    PEDAGOGICAL DNA: LOGOGRAPHIC (Chinese Focus)
    1. ZERO-ENGLISH MANDATE: NEVER use English words to describe sounds (e.g., NO 'sounds like ah'). Use ONLY pure {language} phonetic marks (e.g., 'ā').
    2. TRIPLE-LINK MAPPING: Every item has [Character] + [Pinyin/Sound] + [Meaning].
    3. SCRIPT PURITY: If asking for 'Pinyin', answer MUST be Latin phonetic with tones (e.g., 'mā'). If asking for 'Character', answer MUST be Hanzi (e.g., '妈').
    4. NO ENGLISH CRUTCH: Favor mapping Sound ↔ Character over Translation.
    5. TONAL ACCURACY: Pinyin without tone marks is a failure. Always use ā, á, ǎ, à.
    """
    elif dna == "syllabic":
        if is_phonetic_topic:
            diversity_quota = "MIX: 3x 'Sound to Script', 3x 'Script to Sound'."
        else:
            diversity_quota = "MIX: 2x 'Sound to Script', 2x 'Script to Sound', 2x 'Vocabulary Meaning'."
        dna_instructions = f"""
    PEDAGOGICAL DNA: SYLLABIC/SCRIPT (Russian, Japanese, etc.)
    1. DECODING FOCUS: Focus on mapping the unique script (Cyrillic, Kana) to its sound.
    2. ROMAJI/TRANSCRIPTION: Use only as a secondary tool. The primary target is the native script.
    """
    elif dna == "agglutinative":
        diversity_quota = "MIX: 3x 'Suffix Stacking', 3x 'Sentence Meaning'."
        dna_instructions = f"""
    PEDAGOGICAL DNA: AGGLUTINATIVE (Turkish Focus)
    1. SUFFIX STACKING: Focus on how words change with suffixes (e.g., ev-de-ki).
    2. HARMONY: Test Vowel Harmony rules.
    """
    else:
        diversity_quota = "MIX: 2x 'Verb Conjugation', 2x 'Gender/Articles', 2x 'Translation'."
        dna_instructions = f"""
    PEDAGOGICAL DNA: INFLECTED LATIN (Spanish, French, etc.)
    1. MORPHOLOGY: Focus on Gender, Number, and Verb Conjugation.
    2. CONTEXTUAL USAGE: Use the textbook examples to test grammar in sentences.
    """

    prompt = f"""You are a master {language} architect. Generate {request_count} high-quality Multiple Choice Questions based ONLY on the SOURCE MATERIAL.
    
    SOURCE MATERIAL:
    {content_str}
    {forbidden_clause}
    
    CORE CONSTRAINTS:
    - TYPE: 100% Multiple Choice (type: 'mcq').
    - PROMPT: Write the question in {instruction_lang}.
    - NO FRANKENSTEIN: Never mix {language} and English in a single sentence string.
    - NO GHOSTS: Do NOT include the correct answer word inside the question text.
    - NO LATIN PHONETICS: Never use 'sounds like [English Word]' in options.
    
    {dna_instructions}
    
    DIVERSITY QUOTA: {diversity_quota}
    
    JSON structure: {{"data": [{{ "type": "mcq", "prompt": "...", "answer": "...", "distractors": ["...", "...", "..."] }}]}}
    Return JSON ONLY.
    """
    
    for attempt in range(2):
        # Increased tokens for batch generation to avoid truncation
        result = _call_ai([{"role": "user", "content": prompt}], max_tokens=2500)
        raw_list = result.get("data") if result else []
        
        print(f"[AI] Raw items received: {len(raw_list)}")
        
        final_questions = []
        seen_answers = set()
        
        for item in raw_list:
            try:
                # 1. Aggressive Universal Cleaning (RESTORED: Strips all brackets/hints)
                def deep_clean(text):
                    # Remove (...), [...], {...}, （...）, 「...」, 『...』, 【...】 and strip
                    t = re.sub(r'[\(\[\{（「『【].*?[\)\]\}）」』】]', '', str(text))
                    return t.strip()
    
                ans_clean = deep_clean(item.get("answer", ""))
                prompt_raw = str(item.get("prompt", "")).strip()
                prompt_clean = deep_clean(prompt_raw)
                
                # 2. Logic Check: Empty or Inside Prompt
                if not ans_clean or len(prompt_raw) < 5:
                    continue
    
                # 3. Script Consistency Rule (RESTORED: No mixing vibes)
                def get_vibe(t):
                    # Broad Latin check including accented characters (ā, ó, ü, etc.)
                    return "latin" if re.search('[a-zA-Z\u00C0-\u017F]', str(t)) else "native"
                
                ans_vibe = get_vibe(ans_clean)
                distractors = item.get("distractors", [])
                if not isinstance(distractors, list): distractors = []
                
                all_choices = {ans_clean.lower()}
                valid_distractors = []
                
                for d in distractors:
                    d_clean = deep_clean(d)
                    if d_clean and d_clean.lower() not in all_choices:
                        if get_vibe(d_clean) == ans_vibe:
                            valid_distractors.append(d_clean)
                            all_choices.add(d_clean.lower())
                
                # 4. Final Zero-Tolerance Validation
                if ans_clean and prompt_clean:
                    # GHOST CHECK: Reject if answer is inside the prompt
                    if ans_vibe == 'native':
                        if any(char in prompt_clean for char in ans_clean if char.strip()):
                            continue
                    else:
                        # Use word boundaries on the CLEAN prompt
                        pattern = r'\b' + re.escape(ans_clean.lower()) + r'\b'
                        if re.search(pattern, prompt_clean.lower()):
                            continue
                    
                    # MCQs need at least 2 valid distractors
                    if item.get("type", "mcq") == "mcq" and len(valid_distractors) < 2:
                        continue
    
                    # Check for global duplicates
                    if ans_clean.lower() in seen_answers:
                        continue
                    
                    item["prompt"] = prompt_clean
                    item["answer"] = ans_clean
                    item["distractors"] = valid_distractors[:3]
                    seen_answers.add(ans_clean.lower())
                    final_questions.append(item)
                
                if len(final_questions) >= c: break
            except: continue
        
        if len(final_questions) > 0:
            return final_questions
        
        # If we got 0, try once more with a sterner warning
        prompt += "\n\nRETRY WARNING: Your previous attempt was rejected for Ghost answers (answer word in prompt) or Script mixing. DO NOT repeat those mistakes."
        
    return []

def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=6, level='A1', existing_questions=None):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions)

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=6, level='A1', existing_questions=None):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions)

def ai_grade_open_response(question, student_answer, correct_answer):
    prompt = f"Grade: Q:{question}, C:{correct_answer}, S:{student_answer}. JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150)
    return (result.get("score", 0.0), result.get("feedback", "")) if result else (0.0, "")

def ai_generate_curriculum(language, level, prompt_extra=""):
    system = "You are a curriculum architect. Create a structured syllabus in JSON."
    alphabet_rule = "CRITICAL REQUIREMENT: The very first topic of Unit 1 MUST be exactly 'The Alphabet'. " if level == 'A1' else ""
    user = f"Create a comprehensive {level} level {language} course syllabus with at least 4 or 5 Units (Chapters). {prompt_extra}\n" \
           f"{alphabet_rule}" \
           f"Return JSON: {{'chapters': [{{'number': 1, 'title': '...', 'topics': [{{'title': '...', 'type': 'vocabulary|grammar'}}]}}]}}"
    
    result = _call_ai([
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ], model=MODEL_QUALITY, max_tokens=2000)
    
    if result and "chapters" in result:
        return result["chapters"]
    return []

def ai_generate_report_insights(cohort_data):
    prompt = f"Analyze: {json.dumps(cohort_data)}"
    return _call_ai([{"role": "user", "content": prompt}], max_tokens=500)
