import os
import sys

# Ensure Windows Python 3.8+ finds OpenSSL and extension DLLs
if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    for _p in [os.path.join(sys.base_prefix, "DLLs"), os.path.join(sys.exec_prefix, "DLLs")]:
        if os.path.exists(_p):
            try:
                os.add_dll_directory(_p)
            except Exception:
                pass

import json
import re
import urllib.request
import urllib.error
import time
import uuid
import random as py_random
from datetime import datetime

print(f"--- AI_ENGINE LOADED AT {datetime.now()} ---")
with open("pipeline.log", "a", encoding="utf-8") as f:
    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [INIT] ai_engine.py loaded\n")
import unicodedata
import difflib
from typing import List, Dict, Any, Optional

def _uid():
    return str(uuid.uuid4())

def normalize_text_for_cognate(text: str) -> str:
    """Strip diacritics and non-alphanumeric chars for cognate comparison."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(text).lower())
    clean = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', clean)

def _normalize_token(text: str) -> str:
    """
    Universal, language-agnostic text normalizer for cross-test deduplication.
    Decomposes Unicode characters (stripping combining diacritical marks, accents, stress marks
    across Latin, Cyrillic, Greek, etc.), lowercases, and strips non-alphanumeric punctuation.
    Works universally across all alphabets and languages.
    """
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(text).lower().strip())
    no_marks = ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^\w\s]', '', no_marks).strip()

def is_transparent_cognate(word1: str, word2: str, threshold: float = 0.65) -> bool:
    """Check if two words are transparent cognates (too similar to test directly)."""
    w1 = normalize_text_for_cognate(word1)
    w2 = normalize_text_for_cognate(word2)
    if not w1 or not w2:
        return False
    if len(w1) >= 4 and len(w2) >= 4:
        if w1 in w2 or w2 in w1:
            return True
    min_len = min(len(w1), len(w2))
    if min_len >= 5:
        shared_prefix = 0
        while shared_prefix < min_len and w1[shared_prefix] == w2[shared_prefix]:
            shared_prefix += 1
        if shared_prefix >= 5 or (min_len <= 5 and shared_prefix >= 4):
            return True
    return difflib.SequenceMatcher(None, w1, w2).ratio() >= threshold

def is_transparent_cognate_giveaway(prompt: str, translation: str, answer: str, language: str = "") -> bool:
    """Detect if the prompt itself contains an obvious cognate giveaway of the target answer.
    Applies ONLY when the prompt is written in the instructional language (English/Turkish)
    asking for a target language word that is practically identical in spelling."""
    if not prompt or not answer:
        return False

    # NEVER apply to target language immersion questions (prompts in the language being taught)
    if language:
        lang_lower = language.lower()
        if any(k in lang_lower for k in ["turkish", "türkçe", "turkce"]):
            return False

    # Applies ONLY when the prompt is written in the instructional language (English/Turkish)
    # asking for a translation. Authentic target-language immersion questions are NOT cognate giveaways.
    p_lower = str(prompt).lower()
    instructional_markers = [
        "what does", "what is the translation", "how do you say", "meaning of", "translate", "which of the following means",
        "anlamına gelir", "karşılığı nedir", "nasıl denir", "türkçe anlamı", "ne anlama gelir"
    ]
    if not any(m in p_lower for m in instructional_markers):
        return False

    clean_a = normalize_text_for_cognate(answer)
    if len(clean_a) < 4:
        return False
    ans_words = [normalize_text_for_cognate(w) for w in answer.split() if len(normalize_text_for_cognate(w)) >= 4]
    if not ans_words:
        ans_words = [clean_a]

    # ONLY check words in English/Turkish instructional prompts
    cand_words = re.findall(r'[a-zA-Z\u00C0-\u017F]{4,}', str(prompt))
    stopwords = {"what", "does", "mean", "which", "word", "sentence", "following", "translate", "choose", "correct",
                 "nasil", "nedir", "hangisi", "anlami", "asagidaki", "cumle", "dogru", "kelime", "ifade"}
    for cw in cand_words:
        cw_norm = normalize_text_for_cognate(cw)
        if cw_norm in stopwords:
            continue
        for aw in ans_words:
            # High threshold (0.88) to catch true cognate giveaways across languages (e.g. "information" vs "información")
            if is_transparent_cognate(cw_norm, aw, threshold=0.88):
                return True
    return False

SPANISH_NUMBER_WORDS = {
    "cero": ("zero", "sıfır"), "uno": ("one", "bir"), "un": ("one", "bir"), "una": ("one", "bir"),
    "dos": ("two", "iki"), "tres": ("three", "üç"), "cuatro": ("four", "dört"),
    "cinco": ("five", "beş"), "seis": ("six", "altı"), "siete": ("seven", "yedi"),
    "ocho": ("eight", "sekiz"), "nueve": ("nine", "dokuz"), "diez": ("ten", "on"),
    "once": ("eleven", "on bir"), "doce": ("twelve", "on iki"), "trece": ("thirteen", "on üç"),
    "catorce": ("fourteen", "on dört"), "quince": ("fifteen", "on beş"),
    "dieciséis": ("sixteen", "on altı"), "diecisiete": ("seventeen", "on yedi"),
    "dieciocho": ("eighteen", "on sekiz"), "diecinueve": ("nineteen", "on dokuz"),
    "veinte": ("twenty", "yirmi"), "veintiuno": ("twenty-one", "yirmi bir"),
    "veintidós": ("twenty-two", "yirmi iki"), "veintitrés": ("twenty-three", "yirmi üç"),
    "veinticuatro": ("twenty-four", "yirmi dört"), "veinticinco": ("twenty-five", "yirmi beş"),
    "veintiséis": ("twenty-six", "yirmi altı"), "veintisiete": ("twenty-seven", "yirmi yedi"),
    "veintiocho": ("twenty-eight", "yirmi sekiz"), "veintinueve": ("twenty-nine", "yirmi dokuz"),
    "treinta": ("thirty", "otuz"), "cuarenta": ("forty", "kırk"),
    "cincuenta": ("fifty", "elli"), "sesenta": ("sixty", "altmış"),
    "setenta": ("seventy", "yetmiş"), "ochenta": ("eighty", "seksen"),
    "noventa": ("ninety", "doksan"), "cien": ("one hundred", "yüz"),
    "ciento": ("one hundred", "yüz"), "quinientos": ("five hundred", "beş yüz"),
    "mil": ("one thousand", "bin")
}

MULTILINGUAL_NUMBER_WORDS = {
    # Spanish
    'cero', 'uno', 'una', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve', 'diez',
    'once', 'doce', 'trece', 'catorce', 'quince', 'dieciseis', 'diecisiete', 'dieciocho', 'diecinueve',
    'veinte', 'veintiuno', 'veintidos', 'veintitres', 'veinticuatro', 'veinticinco', 'veintiseis', 'veintisiete', 'veintiocho', 'veintinueve',
    'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta', 'ochenta', 'noventa', 'cien', 'ciento', 'mil',
    # English
    'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen',
    'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety', 'hundred', 'thousand',
    # German
    'null', 'eins', 'zwei', 'drei', 'vier', 'funf', 'sechs', 'sieben', 'acht', 'neun', 'zehn',
    'elf', 'zwolf', 'dreizehn', 'vierzehn', 'funfzehn', 'sechzehn', 'siebzehn', 'achtzehn', 'neunzehn',
    'zwanzig', 'dreissig', 'vierzig', 'funfzig', 'sechzig', 'siebzig', 'achtzig', 'neunzig', 'hundert', 'tausend',
    # French
    'zero', 'un', 'une', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix',
    'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante', 'cent', 'mille',
    # Russian
    'ноль', 'один', 'одна', 'два', 'две', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять', 'десять',
    'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать', 'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать',
    'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто', 'сто', 'тысяча',
    # Italian
    'zero', 'uno', 'una', 'due', 'tre', 'quattro', 'cinque', 'sei', 'sette', 'otto', 'nove', 'dieci',
    'undici', 'dodici', 'tredici', 'quattordici', 'quindici', 'sedici', 'diciassette', 'diciotto', 'diciannove',
    'venti', 'trenta', 'quaranta', 'cinquanta', 'sessanta', 'settanta', 'ottanta', 'novanta', 'cento', 'mille',
    # Turkish
    'sifir', 'bir', 'iki', 'uc', 'dort', 'bes', 'alti', 'yedi', 'sekiz', 'dokuz', 'on',
    'yirmi', 'otuz', 'kirk', 'elli', 'altmis', 'yetmis', 'seksen', 'doksan', 'yuz', 'bin'
}

MATH_OPERATORS = {
    'mas', 'menos', 'por', 'dividido',
    'plus', 'minus', 'times', 'divided',
    'mal', 'geteilt',
    'fois', 'divise',
    'плюс', 'минус', 'умножить', 'разделить',
    'piu', 'meno', 'diviso',
    'arti', 'eksi', 'carpi', 'bolu'
}

MATH_ACTION_VERBS = {
    'sumar', 'restar', 'multiplicar', 'dividir',
    'add', 'subtract', 'multiply', 'divide',
    'addieren', 'subtrahieren', 'multiplizieren', 'dividieren',
    'additionner', 'soustraire', 'multiplier', 'diviser',
    'сложить', 'вычесть', 'умножить', 'разделить', 'прибавить',
    'sommare', 'sottrarre', 'moltiplicare', 'dividere',
    'toplamak', 'cikarmak', 'carpmak', 'bolmek'
}

CALC_QUESTION_PATTERNS = [
    r'\bcuanto\s+es\b', r'\bcombien\s+font\b', r'\bwie\s+viel\s+ist\b',
    r'\bсколько\s+будет\b', r'\bwhat\s+is\b', r'\bquanto\s+fa\b',
    r'\bkac\s+eder\b', r'\btoplami\s+kactir\b', r'\bresultado\s+de\b'
]

def is_arithmetic_question(prompt: str) -> bool:
    """
    Language-agnostic detector for arithmetic and math drill questions.
    Catches pure calculations in both digits and spelled-out words across all languages:
    e.g. 'ocho más tres', 'multiplicar cinco por dos', 'sumar cincuenta más veinte',
    '¿Cuánto es setenta más treinta?', 'Wie viel ist fünf plus zwei?', etc.
    """
    if not prompt:
        return False
    
    # 1. Direct digits with math operators: 5 + 3, 10 / 2, 7 x 4
    if re.search(r'\b\d+\s*[\+\-\*\/×÷=]\s*\d+\b', prompt):
        return True
    
    clean = _normalize_token(prompt)
    words = clean.split()
    if not words:
        return False

    # 2. Math action verbs combined with numbers or calculation context
    for i, w in enumerate(words):
        if w in MATH_ACTION_VERBS:
            surrounding = words[max(0, i-4):min(len(words), i+6)]
            if any(sw in MULTILINGUAL_NUMBER_WORDS or sw.isdigit() for sw in surrounding):
                return True

    # 3. Calculation question stems combined with arithmetic operators
    for cq in CALC_QUESTION_PATTERNS:
        if re.search(cq, clean):
            if any(op in words for op in MATH_OPERATORS):
                return True

    # 4. Pattern: [number_word] [math_operator] [number_word] (e.g. 'ocho mas tres', 'cinco por dos')
    for i in range(len(words) - 2):
        w1, op, w2 = words[i], words[i+1], words[i+2]
        if (w1 in MULTILINGUAL_NUMBER_WORDS or w1.isdigit()) and op in MATH_OPERATORS and (w2 in MULTILINGUAL_NUMBER_WORDS or w2.isdigit()):
            return True

    return False

def _sanitize_blank_translations(prompt: str, answer: str, t_en: str, t_tr: str, why: str = "", why_tr: str = "", topic_content: dict = None):
    """
    Ensures that if the question prompt contains a blank (e.g. '_____'),
    the English and Turkish translations also contain a blank ('_____') and do NOT
    leak the answer.
    """
    if not prompt or not re.search(r'_{2,}', prompt):
        return t_en, t_tr

    has_b_en = bool(re.search(r'_{2,}', t_en or ""))
    has_b_tr = bool(re.search(r'_{2,}', t_tr or ""))

    if has_b_en and has_b_tr:
        return t_en, t_tr

    en_candidates = []
    tr_candidates = []
    ans_clean = str(answer or "").strip()
    ans_lower = ans_clean.lower()

    # 1. Number word mapping
    if ans_lower in SPANISH_NUMBER_WORDS:
        en_candidates.append(SPANISH_NUMBER_WORDS[ans_lower][0])
        tr_candidates.append(SPANISH_NUMBER_WORDS[ans_lower][1])

    # 2. Parenthetical translation in why / why_tr
    if ans_clean:
        m_en = re.search(rf'[\'\"«]?{re.escape(ans_clean)}[\'\"»]?\s*\(([^)]+)\)', why or '', re.IGNORECASE)
        if m_en:
            en_candidates.append(m_en.group(1).strip())
        m_tr = re.search(rf'[\'\"«]?{re.escape(ans_clean)}[\'\"»]?\s*\(([^)]+)\)', why_tr or '', re.IGNORECASE)
        if m_tr:
            tr_candidates.append(m_tr.group(1).strip())

    # 3. Topic content items
    if isinstance(topic_content, dict) and ans_clean:
        for pg in topic_content.get("pages", []):
            for it in pg.get("items", []):
                if isinstance(it, dict) and str(it.get("term", "")).strip().lower() == ans_lower:
                    if it.get("translation_en"): en_candidates.append(str(it["translation_en"]).strip())
                    if it.get("translation_tr"): tr_candidates.append(str(it["translation_tr"]).strip())
                    if it.get("translation"):
                        en_candidates.append(str(it["translation"]).strip())
                        tr_candidates.append(str(it["translation"]).strip())

    # Replace in English translation
    if t_en and not has_b_en:
        for cand in en_candidates + [ans_clean]:
            if cand and len(cand) >= 2:
                pat = rf'\b{re.escape(cand)}\b'
                if re.search(pat, t_en, re.IGNORECASE):
                    t_en = re.sub(pat, '_____', t_en, count=1, flags=re.IGNORECASE)
                    has_b_en = True
                    break

    # Replace in Turkish translation
    if t_tr and not has_b_tr:
        for cand in tr_candidates + [ans_clean]:
            if cand and len(cand) >= 2:
                pat = rf'\b{re.escape(cand)}\b'
                if re.search(pat, t_tr, re.IGNORECASE):
                    t_tr = re.sub(pat, '_____', t_tr, count=1, flags=re.IGNORECASE)
                    has_b_tr = True
                    break

    return t_en, t_tr


# Robust .env loading across execution contexts
for env_path in [
    ".env",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
]:
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip().lstrip('\ufeff')] = v.strip()
        except Exception:
            pass

MODEL_CURRICULUM = os.getenv("MODEL_CURRICULUM", "google/gemini-3.7-flash")
MODEL_LESSON = os.getenv("MODEL_LESSON", "google/gemini-3.7-flash")
MODEL_TRANSLATOR = os.getenv("MODEL_TRANSLATOR", "google/gemini-3.7-flash")
MODEL_STRUCTURAL = os.getenv("MODEL_STRUCTURAL", "google/gemini-3.7-flash")
MODEL_NARRATIVE = os.getenv("MODEL_NARRATIVE", "google/gemini-3.7-flash")
MODEL_FALLBACK = os.getenv("MODEL_FALLBACK", "google/gemini-3.7-flash")

def is_ai_available():
    """Checks if the system has AI capabilities configured (Groq or OpenRouter)."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    return (len(groq_key) > 10) or (len(openrouter_key) > 10)

def _extract_and_parse_json(content: str) -> Optional[Any]:
    """Robust JSON parser that handles markdown fences, unescaped characters, and truncated arrays."""
    if not content:
        return None
    clean = re.sub(r'^```(?:json)?\s*', '', content.strip(), flags=re.MULTILINE)
    clean = re.sub(r'```\s*$', '', clean, flags=re.MULTILINE).strip()
    
    start_obj = clean.find('{')
    start_list = clean.find('[')
    start = -1
    end = -1
    if start_obj != -1 and (start_list == -1 or start_obj < start_list):
        start = start_obj
        end = clean.rfind('}')
    elif start_list != -1:
        start = start_list
        end = clean.rfind(']')
        
    if start != -1 and end != -1 and end > start:
        json_str = clean[start:end+1]
        try:
            return json.loads(json_str, strict=False)
        except Exception:
            pass
        try:
            import ast
            c_s = json_str.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            return ast.literal_eval(c_s)
        except Exception:
            pass

    # Universal Truncation Recovery for any array field ("data", "questions", "items", "activities", "chapters", "pages")
    for arr_name in ["data", "questions", "items", "activities", "chapters", "pages"]:
        arr_key = f'"{arr_name}"'
        if arr_key in clean:
            try:
                arr_start = clean.find(arr_key)
                bracket_start = clean.find('[', arr_start)
                if bracket_start != -1:
                    last_brace = clean.rfind('}')
                    while last_brace > bracket_start:
                        candidate = clean[clean.find('{'):last_brace+1] + ']}'
                        try:
                            parsed = json.loads(candidate, strict=False)
                            if parsed and isinstance(parsed, dict) and parsed.get(arr_name) and len(parsed[arr_name]) >= 1:
                                return parsed
                        except Exception:
                            pass
                        last_brace = clean.rfind('}', 0, last_brace)
            except Exception:
                pass

    # Truncation Recovery for key-value dictionary (e.g. {"0": "...", "1": "..."})
    if start_obj != -1:
        try:
            pos = len(clean) - 1
            while pos > start_obj:
                if clean[pos] == '"':
                    candidate = clean[start_obj:pos+1] + '}'
                    try:
                        parsed = json.loads(candidate, strict=False)
                        if isinstance(parsed, dict) and len(parsed) > 0:
                            return parsed
                    except Exception:
                        pass
                pos -= 1
        except Exception:
            pass

    return None

def _call_ai(messages: List[Dict], model: str = MODEL_STRUCTURAL, max_tokens: int = 1000, temperature: float = 0.7, json_mode: bool = True, allow_fallback: bool = True) -> Optional[Dict]:
    """AI caller using OpenRouter exclusively. Gemini models get Google AI Studio BYOK routing for free quota."""
    if not model or str(model).lower() in ["none", "offline", "skip", "disabled"]:
        return None

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    if not openrouter_key:
        return {"error_details": "OPENROUTER_API_KEY Missing"}

    last_error = "Unknown"
    models_to_try = [model] if model else [MODEL_STRUCTURAL]
    if allow_fallback and MODEL_FALLBACK and MODEL_FALLBACK not in models_to_try:
        models_to_try.append(MODEL_FALLBACK)

    models_to_try = [m for m in models_to_try if m and str(m).lower() not in ["none", "offline", "skip", "disabled"]]
    if not models_to_try:
        return None

    for target_model in models_to_try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://aulaai.com",
            "X-Title": "AulaAI"
        }
        req_payload = {
            "model": target_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if json_mode:
            req_payload["response_format"] = {"type": "json_object"}

        # Gemini / Google models: route with fallbacks allowed and optimize reasoning effort
        is_gemini = "google" in str(target_model).lower() or "gemini" in str(target_model).lower()
        if is_gemini:
            req_payload["provider"] = {
                "order": ["Google AI Studio", "Google"],
                "allow_fallbacks": True
            }
            # OpenRouter requires effort to be at least "low" for gemini-3.7-flash (effort "none" returns HTTP 400 mandatory reasoning)
            req_payload["reasoning"] = {"effort": "low"}

        # Suppress reasoning tokens for other models where not needed
        if not is_gemini and any(x in str(target_model).lower() for x in ["luna", "mercury", "deepseek", "stepfun", "step-"]):
            req_payload["reasoning"] = {"effort": "none"}

        try:
            req = urllib.request.Request(url, data=json.dumps(req_payload).encode("utf-8"), headers=headers)

            max_attempts = 2 if max_tokens <= 2500 else 4
            for attempt in range(max_attempts):
                try:
                    # Generous timeout for lesson generation (Gemini can take 60-120s for long outputs)
                    _timeout = 180 if max_tokens > 4000 else (90 if max_tokens > 2000 else 25)
                    with urllib.request.urlopen(req, timeout=_timeout) as response:
                        res_body = response.read().decode("utf-8")
                        res_json = json.loads(res_body)

                        if "choices" in res_json and res_json["choices"]:
                            msg = res_json["choices"][0].get("message", {})
                            raw_content = msg.get("content") or ""
                            if not raw_content and "reasoning" in msg and msg["reasoning"]:
                                raw_content = msg["reasoning"]
                            content = str(raw_content).strip()
                            if content:
                                with open("pipeline.log", "a", encoding="utf-8") as f:
                                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-OK] {len(content)} chars ← {target_model}\n")

                                data = _extract_and_parse_json(content)
                                if data:
                                    return data
                            # JSON parse failed on this attempt; retry on the same model instead of falling back
                            with open("pipeline.log", "a", encoding="utf-8") as f:
                                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-PARSE-FAIL] Could not parse JSON from {target_model} (attempt {attempt+1}/{max_attempts}). Retrying {target_model}...\n")
                            time.sleep(1.0 * (attempt + 1))
                            continue
                except Exception as e:
                    err_str = str(e)
                    err_body = ""
                    if hasattr(e, "read"):
                        try:
                            err_body = e.read().decode("utf-8", errors="ignore")
                        except: pass
                    # If client error (invalid model, unauthorized, bad request), break immediately without retrying
                    if any(c in err_str for c in ["400", "401", "403", "404", "not a valid model"]):
                        with open("pipeline.log", "a", encoding="utf-8") as f:
                            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-CLIENT-ERROR] {target_model}: {err_str} | Body: {err_body}. Skipping retries.\n")
                        break

                    err_body = ""
                    if hasattr(e, "read"):
                        try:
                            err_body = e.read().decode("utf-8", errors="ignore")
                        except: pass
                    sleep_time = 2.0 * (attempt + 1)
                    if "429" in str(e) or "402" in str(e):
                        sleep_time = 3.0 * (attempt + 1)
                    with open("pipeline.log", "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-RETRY] Attempt {attempt+1}/{max_attempts} ({target_model}): {e} | Body: {err_body[:300]}. Sleep {sleep_time}s\n")
                    time.sleep(sleep_time)

        except Exception as e:
            last_error = str(e)
            try:
                with open("pipeline.log", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-FAIL] {target_model}: {last_error}\n")
            except: pass

    return {"error_details": last_error}

def detect_language(text, hint=""):
    prompt = f"Detect language of: {text[:1000]} (Hint: {hint}). JSON: {{'language': '...'}}"
    res = _call_ai([{"role": "user", "content": prompt}])
    return res.get("language", "Unknown") if res else "Unknown"

def get_language_profile(language):
    agglutinative = ["Turkish", "Korean", "Japanese", "Finnish", "Hungarian"]
    if language in agglutinative: return "agglutinative"
    return "inflected"

LANGUAGE_CALIBRATION_REGISTRY = {
    "german": {
        "banned_terms": ["platzkarte"],
        "b1_banned_terms": ["fahrzeugmangel"],
        "normalizers": []
    },
    "spanish": {
        "banned_terms": [],
        "b1_banned_terms": [],
        "normalizers": [
            (r'\bprofesora de colegio\b', 'profesora en un colegio'),
            (r'\bprofesor de colegio\b', 'profesor en un colegio'),
            (r'\bperiodista digital\b', 'periodista'),
            (r'\bmecánica oficial\b', 'mecánica'),
            (r'\bmecánico oficial\b', 'mecánico'),
        ]
    },
    "french": {
        "banned_terms": [],
        "b1_banned_terms": [],
        "normalizers": []
    },
    "italian": {
        "banned_terms": [],
        "b1_banned_terms": [],
        "normalizers": []
    },
    "russian": {
        "banned_terms": [],
        "b1_banned_terms": [],
        "normalizers": []
    },
    "turkish": {
        "banned_terms": [],
        "b1_banned_terms": [],
        "normalizers": []
    }
}

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, is_quiz=False, source_text_override=None, model_override=None, material_language="en", generation_seed=None, focus_directive=None):
    c = int(count)
    gen_count = max(c + 5, int(c * 1.5), 14)
    with open("pipeline.log", "a", encoding="utf-8") as f:
        api_status = "Available" if is_ai_available() else "MISSING KEY"
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-START] {topic_title} count={count} gen_count={gen_count} seed={generation_seed} focus={focus_directive} API={api_status}\n")
    
    is_beginner = any(lvl in level.upper() for lvl in ["A1", "A2"])
    instruction_lang_name = "Turkish" if material_language == "tr" else "English"
    
    # Use override if provided (for speed during build), else extract concise target material
    if source_text_override:
        content_str = f"EXTRACTED TEXTBOOK CONTENT:\n{source_text_override[:8000]}"
    elif isinstance(topic_content, dict) and "topics" in topic_content:
        parts = [
            "================================================================================",
            "AUTHORITATIVE MULTI-TOPIC REVIEW SYLLABUS (EVIDENCE SOURCE OF TRUTH):",
            "================================================================================"
        ]
        for idx, top in enumerate(topic_content.get("topics", [])[:8], 1):
            t_title = top.get("title", "")
            t_type = top.get("type", "concept")
            t_vocab = top.get("key_vocab", [])
            t_grammar = top.get("key_grammar", [])
            t_diag = top.get("key_dialogues", [])
            t_texts = top.get("key_texts", [])
            
            lines = [f"[MODULE TOPIC {idx}: '{t_title}' (Focus: {t_type})]"]
            if t_grammar:
                lines.append("  Grammar Rules: " + " | ".join(t_grammar[:4]))
            if t_diag:
                lines.append("  Dialogues: " + " || ".join(t_diag[:2]))
            if t_vocab:
                lines.append("  Target Vocabulary: " + ", ".join(t_vocab[:8]))
            if t_texts:
                lines.append("  Reading Passage: " + t_texts[0][:300])
            parts.append("\n".join(lines))
        parts.append("================================================================================")
        content_str = "\n\n".join(parts)
    elif isinstance(topic_content, dict):
        pages = topic_content.get("pages", [])
        page_sections = []

        for idx, p in enumerate(pages, 1):
            p_title = p.get("title", f"Part {idx}")
            p_type = p.get("type", "content")
            
            p_lines = [f"[PART {idx}: '{p_title}' (Focus: {p_type})]"]
            
            # Explanatory text / Narrative / Reading
            if p.get("text"):
                txt = p.get("text").strip()
                if txt:
                    p_lines.append(f"Passage / Explanations:\n{txt[:1200]}")

            # Dialogue exchanges
            if p.get("dialogue") and isinstance(p["dialogue"], list):
                diag_lines = []
                for d in p["dialogue"][:8]:
                    if isinstance(d, dict):
                        spk = d.get("speaker") or "Speaker"
                        txt = d.get("text") or d.get("line") or ""
                        trans = (d.get("line_tr") or d.get("translation_tr")) if material_language == "tr" else (d.get("line_en") or d.get("translation_en") or d.get("translation") or "")
                        if txt:
                            diag_lines.append(f"  {spk}: \"{txt}\"" + (f" ({trans})" if trans else ""))
                if diag_lines:
                    p_lines.append("Authentic Dialogue Exchanges:\n" + "\n".join(diag_lines))

            # Items (Vocabulary / Grammar / Examples)
            if p.get("items") and isinstance(p["items"], list):
                item_lines = []
                for it in p["items"][:15]:
                    if isinstance(it, dict):
                        term = (it.get("term") or it.get("word") or it.get("rule") or "").strip()
                        tr = (it.get("translation_tr") if material_language == "tr" and it.get("translation_tr") else (it.get("translation_en") or it.get("translation") or it.get("meaning") or "")).strip()
                        ex = (it.get("example") or it.get("sample") or "").strip()
                        expl = (it.get("explanation_tr") if material_language == "tr" and it.get("explanation_tr") else (it.get("explanation_en") or it.get("explanation") or "")).strip()
                        if term:
                            item_display = f"  * {term}" + (f" ({tr})" if tr else "")
                            if ex: item_display += f" — Example: '{ex}'"
                            if expl: item_display += f" — Rule/Note: {expl}"
                            item_lines.append(item_display)
                if item_lines:
                    p_lines.append("Target Lexicon, Patterns & Examples:\n" + "\n".join(item_lines))

            if len(p_lines) > 1:
                page_sections.append("\n".join(p_lines))

        parts = [
            "================================================================================",
            "AUTHORITATIVE LESSON SOURCE MATERIAL (PRIMARY EVIDENCE SOURCE OF TRUTH):",
            "================================================================================",
            "The learner has studied the following lesson material. Your questions MUST be strictly",
            "material-dependent: test information, dialogues, vocabulary, grammar patterns, relationships,",
            "and details that a learner needs to recall or understand from THIS MATERIAL itself.",
            "Do NOT ask questions that can be answered by generic common sense or world knowledge.",
            "--------------------------------------------------------------------------------"
        ]
        if page_sections:
            parts.extend(page_sections)
            parts.append("================================================================================")
            content_str = "\n\n".join(parts)
        else:
            content_str = json.dumps(topic_content, ensure_ascii=False)[:3500]
    else:
        content_str = str(topic_content)[:3500]
    
    from services.language_data import get_reference_prompt, get_special_chars_prompt, get_pedagogical_guidelines
    from services.cefr_reference import get_cefr_conditioning
    is_alphabet_topic = any(x in topic_title.lower() for x in ["alphabet", "alfabeto", "alfabe", "letters"])
    
    ref_data = ""
    if is_alphabet_topic:
        ref_data = get_reference_prompt(language)
    elif any(x in topic_title.lower() for x in ["accent", "character", "mark", "diacritic"]):
        ref_data = get_special_chars_prompt(language)
 
    forbidden_answers = []
    forbidden_prompts = []
    forbidden_answer_keys = set()
    forbidden_prompt_keys = set()

    if existing_questions and isinstance(existing_questions, list):
        for q in existing_questions:
            if isinstance(q, dict):
                p = str(q.get("prompt", "")).strip()
                a = str(q.get("answer", "")).strip()
                if a:
                    a_key = _normalize_token(a)
                    if a_key and a_key not in forbidden_answer_keys:
                        forbidden_answer_keys.add(a_key)
                        forbidden_answers.append(a)
                if p:
                    p_key = _normalize_token(p)
                    if p_key and p_key not in forbidden_prompt_keys:
                        forbidden_prompt_keys.add(p_key)
                        forbidden_prompts.append(p)

    forbidden_clause = ""
    if forbidden_prompts or forbidden_answers:
        prompts_list = "\n".join(f"- {p[:120]}" for p in forbidden_prompts[-30:])
        answers_str = ", ".join(f"'{ans}'" for ans in forbidden_answers[-30:])
        forbidden_clause = f"""
================================================================================
ROLLING-HISTORY CONTEXT & REPETITION PREVENTION MANDATE (ALL CEFR LEVELS):
================================================================================
Context from the two retained previous completed batches and the current test:
- Target answers previously tested: [{answers_str}]
- Stems/questions previously tested:
{prompts_list}

REPETITION & COVERAGE RULES:
1. AVOID EXACT OR EFFECTIVELY REPEATED QUESTIONS:
   - Within the current test and the two retained previous batches, avoid exact or effectively repeated questions, including the same target tested again with essentially the same context and cognitive task.
   - Do NOT duplicate question stems, scenarios, or identical cognitive drills.

2. ALLOW BROADER OBJECTIVE COVERAGE WITHOUT FORCED NOVELTY:
   - While avoiding redundant repetition of essentially the same question or item, the same broader learning objective, grammatical structure, or thematic area IS fully permitted to reappear in a genuinely different context or task.
   - Preserve strict material grounding, CEFR {level} appropriateness, broad unit coverage, and authentic usage; NEVER force novelty at the expense of quality or source fidelity.
================================================================================
"""

    clean_lvl = (level or "A1").upper().strip()
    is_a1_a2 = any(x in clean_lvl for x in ["A1", "A2"])
    is_b1 = "B1" in clean_lvl
    is_b2 = "B2" in clean_lvl

    if is_a1_a2:
        variety_focuses = [
            "Focus on real-world communicative dialogues: asking for assistance, public navigation, and travel exchanges.",
            "Focus on everyday domestic scenarios: home routines, appointments, schedules, and social interactions.",
            "Focus on practical transactional tasks: markets, shopping, dining, prices, and courteous customer requests.",
            "Focus on social introductions, describing people, personal hobbies, and expressing natural preferences.",
            "Focus on foundational phonological contrasts, clear pronunciation distinctions in real words, and sentence completion."
        ]
    elif is_b1:
        variety_focuses = [
            "Focus on authentic everyday travel & service communication: understanding standard announcements, finding alternatives, and asking conductors/staff for assistance.",
            "Focus on practical workplace interactions: clear and direct emails, daily coordination, and standard meeting exchanges.",
            "Focus on expressing personal opinions, everyday preferences, and simple justifications with standard connectors.",
            "Focus on navigating unexpected everyday travel disruptions: delays, platform changes, and missing connections in clear standard language.",
            "Focus on polite inquiries, checking information, confirming schedules, and resolving everyday misunderstandings."
        ]
    elif is_b2:
        variety_focuses = [
            "Focus on professional and workplace communication: nuanced emails, teamwork, problem-solving, and formal negotiation.",
            "Focus on structured argumentation, weighing pros and cons, and justifying complex perspectives.",
            "Focus on narrative discourse: recounting detailed experiences, unexpected complications, and hypothetical scenarios.",
            "Focus on communicative nuance: formal customer complaints, institutional procedures, and contractual/passenger rights.",
            "Focus on natural discourse connectors, sophisticated idiomatic collocations, and varied syntactic structures."
        ]
    else:  # C1 / C2 Advanced
        variety_focuses = [
            "Focus on natural advanced register precision, idiomatic mastery, and authentic contemporary discourse norms.",
            "Focus on pragmatic implicature, natural socio-cultural idioms, irony, and conversational subtext.",
            "Focus on complex argumentation, societal debates, abstract concepts, and multi-perspective reasoning.",
            "Focus on register flexibility: discriminating between natural formal, colloquial, journalistic, and literary expressions.",
            "Focus on advanced collocations, polysemous lexical subtleties, and authentic idiomatic usage."
        ]
    if generation_seed is not None:
        selected_variety_focus = variety_focuses[int(generation_seed) % len(variety_focuses)]
    else:
        selected_variety_focus = py_random.choice(variety_focuses)

    pedagogy_guidance = get_pedagogical_guidelines(language, level)
    cefr_guidance = get_cefr_conditioning(language, level, topic_title, topic_type)

    system = f"""You are the {language} Pedagogic Assessment Engine (V5). 
    Your mission: Using the provided textbook content as your source, generate questions that test genuine communicative and linguistic understanding in {language}.
    
    {cefr_guidance}
    
    {pedagogy_guidance}
    
    PEDAGOGIC PROTOCOL & MANDATES:
    1. 100% TARGET LANGUAGE PROMPTS (CRITICAL & ABSOLUTE REQUIREMENT):
       - The 'prompt' field MUST BE 100% IN {language}.
       - ABSOLUTELY ZERO Turkish or English carrier text in the 'prompt' field!
       - Frame ALL questions, instructions, and scenarios entirely in authentic {language}.
       - Valid prompt examples:
         * "¿Cuál es la respuesta adecuada y formal cuando un colega dice 'Mucho gusto'?"
         * "Completa la frase con la forma verbal correcta: 'Normalmente nosotros ______ en el centro antes de las ocho.'"
         * "En la pronunciación del español, ¿cuál de estas palabras contiene una 'h' completamente muda?"
         * "¿Qué expresión se utiliza habitualmente para pedir la cuenta en un restaurante?"
    2. DUAL TRANSLATION & BLANK PRESERVATION MANDATE (CRITICAL):
       - 'translation_en': Professional English translation of the prompt.
       - 'translation_tr': Natural, fluent Turkish translation of the prompt.
       - BLANK PRESERVATION: If the prompt contains a blank or fill-in-the-blank (e.g. '_____', '____', '___'), the translations ('translation_en' and 'translation_tr') MUST ALSO KEEP THE BLANK AS '_____'!
         * ABSOLUTELY NEVER insert, translate, or reveal the answer word inside 'translation_en' or 'translation_tr'!
         * WRONG: prompt="... Le devuelvo _____ euros." -> translation_en="... I return thirty euros to you." (REVEALS ANSWER!)
         * CORRECT: prompt="... Le devuelvo _____ euros." -> translation_en="... I return _____ euros to you."
         * CORRECT: prompt="... Le devuelvo _____ euros." -> translation_tr="... Size _____ euro para üstü veriyorum."
       - 'why': Concise pedagogical explanation in English.
       - 'why_tr': Concise pedagogical explanation in Turkish.
    3. STRICT ANTI-GIVEAWAY & BAN ON META-ORTHOGRAPHIC TRIVIA:
       - The prompt MUST NEVER contain the correct answer or any stem/part of the answer.
       - STRICT ZERO-TOLERANCE BAN ON META-ORTHOGRAPHIC & ALPHABET TRIVIA:
         * NEVER ask shallow meta-trivia questions about letter names, string properties, or spelling features (e.g. NEVER ask 'Which word has a tilde / graphic accent?', 'Which letter is silent?', 'Which word ends in Y?', 'Which number between 16 and 29 has a tilde?').
         * Testing "Which word has a tilde?" is shallow trivia and often creates multiple correct answers.
         * Test spelling, orthography, and accents EXCLUSIVELY in authentic communicative sentence contexts (e.g. "Tengo _____ años." where only ONE option is correctly spelled, and all 3 distractors are typical learner spelling errors).
       - For phonetics/alphabet topics, test genuine pronunciation in real words or minimal pairs.
    4. STRICT ANTI-COGNATE & REAL-CHALLENGE MANDATE:
       - NEVER ask questions where the target answer is an obvious transparent cognate identical to English/Turkish.
       - All 4 options (answer + 3 distractors) MUST be drawn from the exact same semantic domain.
     5. HOMOGENEITY, LINGUISTIC LEVEL, FUNCTIONAL CATEGORY & ANSWER-OPTION TYPE ALIGNMENT (CRITICAL):
        - All 4 options MUST be the EXACT SAME grammatical type (all verbs, all nouns, all clauses, or all questions).
        - KEEP ANSWER-OPTION TYPE ALIGNED WITH THE STEM: Keep the answer-option type strictly aligned with what the stem asks for: a term must be answered by a term, a function by a function, an interpretation by an interpretation, and a form by a form.
        - STEM AND KEYED ANSWER CONCEPT ALIGNMENT: The stem and keyed answer must test exactly the same concept, and the correct answer must satisfy every condition stated in the stem without adding unsupported implications.
        - SAME LINGUISTIC LEVEL & FUNCTIONAL CATEGORY: When possible, distractors should compete with the correct answer at the same linguistic level and functional category.
        - BAN ON OUT-OF-CATEGORY OPTIONS: Avoid making the answer obvious by mixing it with options from clearly different grammatical, pragmatic, or register categories (e.g. never mix casual conversational remarks with formal institutional prose, and never mix an abstract stance with a simple action).
    6. STRICT LESSON MATERIAL GROUNDING & TECHNICAL PRECISION (NOT LITERAL RECALL):
       - AUTHORITATIVE SOURCE OF LEARNING OBJECTIVES (PEDAGOGICAL GROUNDING):
         * The lesson material is the single authoritative source of truth and learning objectives.
         * Every question must be fully grounded in the source and technically precise: distinguish the inherent meaning/function of a grammatical form from meanings that arise only from sentence context, and never attribute contextual consequences such as continuity, completion, legal effect, certainty, intensity, or causality to a form unless the form itself genuinely encodes them and the source supports that analysis.
         * SAFE & DEFENSIBLE CLAIMS: Do not use broader, stronger, or more technical grammatical/pragmatic claims than can be safely defended. Avoid debatable linguistic terminology or unnecessarily fine-grained classifications unless explicitly supported by the material.
         * Every question MUST assess knowledge, vocabulary, grammar patterns, relationships, examples, or communicative functions explicitly taught or demonstrated in the lesson material.
         * CONTEXTUAL KNOWLEDGE TRANSFER: Questions MAY transfer taught linguistic knowledge, grammar structures, and vocabulary into fresh, realistic, CEFR-appropriate communicative contexts. Questions do NOT need to be literal verbatim recall tests.
         * BAN ON EXTERNAL FACTS & INVENTIONS: While transfer of taught rules/lexicon is encouraged, questions must NEVER require external facts, unstated assumptions, generic world knowledge, or invented lesson content.
       - STRICT BAN ON COMMON SENSE & OBVIOUS CATEGORY MATCHING (GATE 1 CRITERION):
         * A question FAILS when it primarily measures common sense, world knowledge, or obvious category matching rather than a material-supported learning objective.
         * Examples of forbidden generic questions: asking where a doctor works (hospital), what you do when hungry (eat), or generic train delay common sense that anyone knows without studying the lesson.
         * Questions MUST require understanding of the target language structures, collocations, dialogues, or distinctions taught in the lesson.
       - MULTI-PART & OBJECTIVE COVERAGE:
         * Across the {gen_count} questions in this batch, cover different parts, sections, and learning objectives from the material instead of repeatedly testing the same concept, sentence pattern, vocabulary item, or grammar rule.
         * Map questions across the different numbered PARTS/sections provided in the source material.

    7. DISTRACTOR PLAUSIBILITY, REALISTIC LEARNER CONFUSIONS & CEFR CALIBRATION (CRITICAL):
       - EXACTLY 4 OPTIONS: Every question MUST have 1 correct answer and EXACTLY 3 distinct distractors in the 'distractors' array. Total options must ALWAYS be 4.
       - STRICT CEFR {level} DIFFICULTY PRESERVATION:
         * Strictly respect CEFR {level} linguistic limits across all questions, prompts, and all 4 options.
         * Keep all target-language wording natural, idiomatic, and examiner-grade in {language}.
         * Avoid overly advanced vocabulary, dense bureaucracy, or complex syntax above CEFR {level}.
       - EXACTLY ONE DEFENSIBLE CORRECT ANSWER:
         * Every MCQ must have exactly one defensible correct answer in the full context.
         * The correct answer MUST be the ONE AND ONLY option that satisfies the question prompt, fully defensible from the lesson material.
         * The correct answer must satisfy every condition stated in the stem without adding unsupported implications.
         * All 3 distractors MUST be unequivocally and demonstrably false upon careful examination, and must not also satisfy the stem.
       - HIGH-CALIBER DISTRACTOR RIGOR & NEAR-MISS COMPETITIVENESS (NO EASY FILLERS):
         * Distractors must be authentic, grammatical, naturally usable, semantically plausible, and competitive, but must not also satisfy the stem.
         * NEVER invent, deform, or mechanically force word forms just to create parallel options. If natural same-form distractors do not exist, use plausible alternatives of the appropriate semantic or functional type instead.
         * ZERO easy 'throwaway' or filler options that a student can eliminate at a superficial glance without thinking.
         * EVERY OPTION MUST ITSELF BE GRAMMATICALLY NATURAL & AUTONOMOUSLY WELL-FORMED:
           - Every single option (the correct answer AND all 3 distractors) MUST ITSELF be a 100% grammatically natural, authentic, and attested expression in {language}.
           - A distractor must be incorrect solely because of the CONTEXT, MEANING, PRAGMATIC FIT, or SUBTLE COLLOCATIONAL MISMATCH with the scenario — NEVER because the option itself is ungrammatical gibberish, an impossible morphological invention, or an unnatural phrase in the language!
           - Avoid and reject any distractor that can be eliminated merely because it sounds unnatural, malformed, invented, or structurally impossible in isolation (e.g. NEVER fabricate artificial suffix combinations like "fark etmeksizinmiş", "gözetircisine", "öleceğince", non-existent verb forms, or broken morphological compounds).
         * At least 1-2 (and where appropriate at least TWO) distractors in EVERY question MUST be plausible near-miss options drawn from the exact same grammatical or semantic category as the answer:
           - In grammar: Use real, grammatically natural alternative forms (subtle agreement mismatches, correct tense but wrong grammatical person, subtle word-order inversion errors, or real, attested alternative converbs/suffixes).
           - In vocabulary/collocations: Use other real, natural words from the exact same semantic field or plausible near-synonyms that do not fit the specific collocational frame, register, or preposition.
           - In comprehension/dialogue: Distractors should describe other real, grammatically natural statements mentioned elsewhere in the text/dialogue (plausible misattributions), requiring careful reading rather than superficial elimination.
         * IDIOMS, FIXED EXPRESSIONS, COLLOCATIONS & FORMAL REGISTER:
           - For idioms, fixed expressions, collocations, and formal register, validate the complete expression in context, including natural argument structure, case marking, object choice, prepositions/postpositions, register, and pragmatic force.
           - NEVER construct a sentence that is technically interpretable but unnatural to a native speaker.
           - Validate collocational naturalness before accepting a question: a word may be semantically related yet must still be rejected if its argument, complement, or surrounding phrase is unnatural in real usage (for example, prefer natural constructions such as “Ekibinizi tenzih ederek...” rather than forcing “tenzih etmek” onto an unnatural abstract object). Do not make questions artificially harder.
         * REJECTION OF SUPERFICIALLY FORMAL BUT SEMANTICALLY MISSELECTED VOCABULARY:
           - Strictly reject words that sound superficially elevated, archaic, or formal but are semantically or idiomatically misselected in context (e.g. reject “salahiyet” where “selamet” is required).
           - Never use an elevated register or learned word merely for cosmetic formality if its actual definition, argument structure, or idiomatic domain does not fit the context with 100% precision.
         * IDIOMATIC PLAUSIBILITY IN THE EXACT SENTENCE FRAME:
           - Require distractors to be not only grammatically well-formed in isolation, but idiomatically plausible in the exact sentence frame of the question prompt.
           - A distractor must make sense syntactically and idiomatically within the frame, representing a genuine, plausible near-miss rather than an awkward or arbitrary substitution.
         * LINGUISTIC LEVEL & FUNCTIONAL CATEGORY MATCHING:
           - When possible, distractors should compete with the correct answer at the same linguistic level and functional category.
           - Avoid making the answer obvious by mixing it with options from clearly different grammatical, pragmatic, or register categories.
         * Distractors do NOT all need to appear verbatim in the source material: CEFR-appropriate real incorrect forms and common learner traps are explicitly welcomed when they produce a more competitive, natural, and pedagogically rigorous question.
         * ABSOLUTELY NEVER generate absurd, cartoonish, off-domain, or trivially dismissible choices.
       - LENGTH SYMMETRY: All 4 options (answer + 3 distractors) MUST be approximately the same character length (within ±25%). NEVER make the correct answer substantially longer or more explanatory.
       - ZERO SEMANTIC DUPLICATES: All 4 options must be distinct from one another. Zero duplicate learning objectives across the entire quiz batch or from recently tested questions.

    8. COGNITIVE TASK & QUESTION FORMAT VARIETY (AVOIDING REPETITIVE TESTING PATTERNS):
       - ABSOLUTE BAN ON REPETITIVE TESTING PATTERNS:
         * Across the {gen_count} questions in this batch, you MUST actively vary both the COGNITIVE TASK and the QUESTION FORMAT.
         * ABSOLUTELY NEVER repeatedly test the same rule, grammatical inflection, or vocabulary category through near-identical sentence templates (e.g. NEVER generate multiple questions that all use the exact same carrier pattern like "Completa la frase: [Person] [verb] [object]" or test the same verb conjugation repeatedly).
       - MANDATORY DISTRIBUTION OF COGNITIVE TASKS ACROSS EACH BATCH:
         Distribute the {gen_count} questions across diverse styles. At most 3-4 questions in the entire set may contain a blank ('_____'). The rest MUST be direct communicative questions WITHOUT any blanks:
         a) PRAGMATIC / SITUATIONAL DECISION (COMMUNICATIVE REACTION - NO BLANK):
            Real-world social interaction or dialogue from the lesson where the learner selects the natural, appropriate response or polite formula to say.
         b) FUNCTIONAL COMPREHENSION & DEDUCTION (DIALOGUE / READING UNDERSTANDING - NO BLANK):
            Testing specific meaning, speaker intentions, schedule/time details, or communicative purpose directly stated in the lesson material WITHOUT speculative leaps.
         c) CONTEXTUAL SENTENCE APPLICATION (WITH BLANK - AT MOST 3-4 PER BATCH):
            Rich communicative sentence testing a specific taught conjugation, preposition, or lexical distinction in context.
         d) LINGUISTIC DISCRIMINATION & GRAMMATICAL PRECISION (NO BLANK):
            Selecting which statement is grammatically correct and natural vs. incorrect based strictly on the rule taught in the lesson.
         e) COMMUNICATIVE INTENT & COLLOCATION IN CONTEXT (NO BLANK):
            Choosing the proper expression, question word, or natural collocation appropriate for a specific communicative goal taught in the lesson.
       - STRICT BAN ON SHALLOW TRANSLATION DRILLS: NEVER ask "What is the translation of X?", "What does X mean?", "How do you say X in {language}?", or shallow "Which option means X?".
       - STRICT ZERO-TOLERANCE BAN ON TRIVIAL 1-WORD COLLOCATION BLANKS:
         * NEVER test a fixed multi-word collocation by simply removing the single obvious verb.
       - STRICT BAN ON CIRCULAR TAUTOLOGIES & REPETITIVE DEFINITIONS:
         * NEVER ask shallow definition questions that define a word with its own stem or root.
       - STRICT BAN ON COMMERCIAL PRODUCT TRIVIA & INVENTED LEGAL THRESHOLDS:
         * NEVER test proprietary commercial product brand names, ticket portfolio specifics, or arbitrary legal thresholds.
       - IN-BATCH CONCEPT & OBJECTIVE DIVERSITY:
         * Every single question in this batch must target a fresh aspect of the theme with a different cognitive demand.

    9. STRICT ZERO-TOLERANCE BAN ON ARITHMETIC & MATH CALCULATIONS (CRITICAL):
       - NEVER ask math equations, addition, subtraction, multiplication, or division in words or numbers (e.g., NEVER ask math problems in {language}).
       - AulaAI is a LANGUAGE platform, NOT a mathematics quiz!
       - If the lesson covers numbers, currency, or time, test them EXCLUSIVELY in authentic communicative situations (e.g. asking prices, asking times, hotel room numbers, dates, schedules, or ages). NEVER ask the student to solve a math problem!
    
    10. NATURAL & AUTHENTIC LIVING COLLOCATIONS IN {language} (UNIVERSAL FOR ALL TOPICS & LEVELS):
        - All prompts, scenarios, dialogues, and answer options MUST reflect NATURAL, CONTEMPORARY, LIVING {language} as actually spoken and written by native speakers, public institutions, and professionals.
        - MODERN LIVING TERMINOLOGY & ACCURACY:
          * Use contemporary standard living vocabulary in {language}; ABSOLUTELY NEVER outdated, obsolete, or archaic terms.
          * For B1 and intermediate levels, use clear everyday standard expressions; ABSOLUTELY NEVER bureaucratic dispatch jargon, hyper-technical infrastructure terms, or officialese.
          * In workplace and personal descriptions, use natural authentic phrasing and standard prepositions native to {language}.
        - EVERYDAY SPOKEN REALISM: In time and daily expressions, use natural spoken terms customary to native speakers of {language} (e.g. natural expressions for midnight, noon, or daily routines), NEVER artificial mechanical formulas (like 'zero hours') in everyday conversation.
        - DOMAIN & FUNCTIONAL COLLOCATION PRECISION:
          * Use the genuine, authentic functional collocations native to {language} for the specific domain of '{topic_title}'.
          * Service notices and institutional announcements: Use authentic standard institutional terminology native to {language} (e.g. clearly distinguish between facilities/services being closed or unavailable vs. unstaffed; distinguish between scheduled stops/services that are not served vs. physically bypassing them).
          * In spoken/broadcast notices, use natural, concise native phrasing rather than stiff or artificial test-maker jargon.
          * Distinguish between professional actions, diagnostic terms, symptoms, treatments, commercial requests, and interpersonal norms relevant to '{topic_title}'.
          * Syntax, clause coordination, and elliptic phrasing must sound completely natural and idiomatic to a native speaker of {language}.
        - NATURAL CADENCE & EFFORTLESS IDIOMACY:
          * The phrasing of both the prompt question and the answer options must flow effortlessly with native rhythmic authenticity and examiner-grade poise.
          * Avoid rigid, robotic, or textbook-formulaic phrasing; use the lively, organic formulations that an educated native speaker naturally uses in everyday interactions.
        - ZERO MECHANICAL TRANSLATIONESE & CLUNKY LITERALISMS:
          * Use genuine native idioms, customary institutional/service formulas, and conversational patterns of {language} appropriate for the given topic.
          * Avoid mechanical word-for-word translation phrasing, robotic literalisms, or stiff pseudo-formal formulas that native speakers never use in real life.
          * In response options and dialogues, use natural, realistic human phrasing suited to CEFR {level}, NEVER stiff or artificial academic test-maker jargon.
        - SEMANTIC PRECISION OVER SUPERFICIAL FORMALITY:
          * Strictly reject semantically misselected but superficially formal vocabulary in context (e.g. “salahiyet” where “selamet” is required).
          * Distractors must be not only grammatical in isolation, but idiomatically plausible in the exact sentence frame of the prompt.
        - NATURALNESS, TECHNICAL PRECISION & PEDAGOGICAL APPROPRIATENESS (MANDATORY):
          * The model itself must produce fully natural and idiomatic questions, precise linguistic and domain terminology, exactly one defensible correct answer, plausible same-level distractors, and NO malformed or contextually unnatural wording.
          * Every question must be fully grounded in the source and technically precise: distinguish the inherent meaning/function of a grammatical form from meanings that arise only from sentence context, and never attribute contextual consequences such as continuity, completion, legal effect, certainty, intensity, or causality to a form unless the form itself genuinely encodes them and the source supports that analysis.
          * Do not use broader, stronger, or more technical grammatical/pragmatic claims than can be safely defended. Avoid debatable linguistic terminology or unnecessarily fine-grained classifications unless explicitly supported by the material.
          * The stem and keyed answer must test EXACTLY the same concept, and the correct answer must satisfy every condition stated in the stem without adding unsupported implications.
          * Keep the answer-option type aligned with what the stem asks for: a term must be answered by a term, a function by a function, an interpretation by an interpretation, and a form by a form.
          * For conjunctions and discourse markers, verify that the actual propositions on both sides create exactly the required relation such as contrast, confirmation, reinforcement, consequence, concession, or addition.
          * For idioms, fixed expressions, collocations, and formal register, validate the complete expression in context, including natural argument structure, case marking, object choice, prepositions/postpositions, register, and pragmatic force; NEVER construct a sentence that is technically interpretable but unnatural to a native speaker.
          * Ensure every complete sentence is idiomatic and realistic in its stated context, and avoid unnecessary repetition of the same expression, scenario, or effectively identical task across recent batches while still allowing the same learning objective to recur in a genuinely different context.
          * Distractors must be authentic, grammatical, naturally usable, semantically plausible, and competitive, but must not also satisfy the stem; never invent, deform, or mechanically force word forms just to create parallel options. If natural same-form distractors do not exist, use plausible alternatives of the appropriate semantic or functional type instead.
          * Stems, answers, and distractors must all be idiomatic, grammatically valid, functionally plausible, and mutually consistent, while avoiding artificial wording, misleading terminology, or options that are trivially eliminable for the wrong reason.
          * Within the current test and the two retained previous batches, avoid exact or effectively repeated questions, including the same target tested again with essentially the same context and cognitive task, while still allowing the same broader learning objective to reappear in a genuinely different context or task.
          * Preserve strict material grounding, CEFR {level} appropriateness, broad unit coverage, and authentic usage; never force novelty at the expense of quality or source fidelity.
          * Prompts, sentence completions, dialogues, and scenario stems must be fully coherent, idiomatic, and pragmatically grounded utterances rather than fragmented or artificial constructions.
          * Use precise linguistic and domain terminology when describing grammar, pronunciation, meaning, or usage (e.g. in questions, stem explanations, grammar labels, and phonetic/semantic descriptions).
          * Distractors must compete with the correct answer at the same grammatical, semantic, pragmatic, or register level rather than being trivially eliminable, while strictly ensuring no distractor is also valid for the stem.
          * Resolve all of this during generation itself so that every delivered item is fully natural, technically precise, and pedagogically appropriate.
        - Keep language vibrant, culturally authentic, and realistic across every theme.

    11. NO TRIVIAL META-PARAPHRASING ("WHAT DID THE SPEAKER JUST SAY / ASK?"):
        - NEVER ask shallow meta-questions that merely ask the student to parrot, quote, or trivially summarize what a speaker literally just uttered in the prompt.
        - Every question MUST test genuine communicative reasoning, situational reaction ("What should the person say or do?"), practical decision-making, or real-world consequence ("What does this information imply?").

    12. RIGOROUS LOGICAL FIDELITY & CEFR LEVEL CALIBRATION (UNIVERSAL):
        - B1 LEVEL CALIBRATION DIRECTIVE (CRITICAL):
          * Level B1 represents independent everyday communicative competence (clear standard everyday language).
          * STRICT BAN ON C1/B2 BUREAUCRATIC OVERLOAD AT B1:
            - NEVER flood a B1 lesson with dense infrastructure jargon, official technical dispatch terms, or hyper-complex compound nouns.
            - Use clear standard everyday expressions (e.g. general technical problem, schedule delay, polite staff inquiry).
            - Focus on the traveler's communicative actions and understanding of clear standard public notices, NOT technical engineering or corporate tariff law.
        - COMPLETE & SELF-CONTAINED CONTEXT & STRICT ANSWER UNIQUENESS:
          * The scenario MUST provide all necessary context so that every multiple-choice item has exactly one defensible correct answer in the full sentence and context.
          * Before finalizing, ensure no distractor is also grammatically, semantically, pragmatically, or factually valid for the same stem.
          * Resolve ambiguity during generation itself.
          * Never mention unexplained premises and expect the learner to guess.
        - STRICT LITERAL DEDUCTION & ZERO INFERENCE LEAPS:
          * The question stem and the correct answer MUST be strictly, mathematically, and directly verifiable from what is EXPLICITLY stated in the scenario.
          * ZERO SPECULATIVE INFERENCE: If the scenario states an event or incident occurs, NEVER infer an unstated consequence or cause (e.g. do NOT assert that duration, costs, schedules, or outcomes have changed unless the scenario explicitly mentions that change).
          * ACCURATE OPERATIONAL DESCRIPTIONS: Describe consequences using literal, factual statements directly derived from the scenario text without imaginative embellishments.
          * PRECISE TERMINOLOGICAL BOUNDARIES:
            - Do not over-narrow broad terms: A general policy, right, document, or procedure applies broadly, NOT solely to one specific sub-case unless specifically restricted in the prompt.
            - Do not over-generalize specific exceptions: If one specific service, item, or route is unavailable, do NOT assert that all options in that category are cancelled.
            - Do not over-specify categories: If an announcement or person refers generally to an alternative or solution, do NOT arbitrarily label it with a specific sub-category unless specified in the text.
          * ZERO CONDITIONAL ENTITLEMENT HALLUCINATIONS: Never present conditional or discretionary amenities/remedies as guaranteed automatic entitlements unless the scenario text explicitly states them as granted.
          * ZERO UNSTATED LOGISTICAL SPECIFICS: Do not hallucinate unannounced locations, specific facilities, or unmentioned procedural constraints unless explicitly stated in the scenario.
        - CONTEXTUAL ROLE & ENTITY ACCURACY: Strictly respect the exact roles, locations, statuses, and relationships stated in the scenario (e.g. do not confuse an intermediate transit/transfer point with a final destination; do not confuse a customer with staff; do not confuse a temporary delay with a complete cancellation).
        - CEFR PROFICIENCY BALANCE: All 4 options must strictly match the CEFR {level} proficiency tier without injecting out-of-level elevated vocabulary or childish simplifications.

    13. MANDATORY PRE-OUTPUT INTERNAL VERIFICATION (6 EVALUATION GATES):
        Before returning each question, internally verify it against these 6 evaluation gates:
        * GATE 1 - MATERIAL-SUPPORTED LEARNING OBJECTIVE & SOURCE BOUNDS: Does the question assess knowledge, vocabulary, grammar, or communicative functions taught in the material? Every question must be fully grounded in the source and technically precise: distinguish inherent meaning/function of a grammatical form from sentence context effects, and never attribute contextual consequences (continuity, completion, legal effect, certainty, intensity, causality) unless genuinely encoded by the form and supported by the source. Do not make broader or stronger grammatical claims than can be safely defended, and avoid debatable linguistic terminology. (A question FAILS ONLY when it primarily measures common sense or external knowledge rather than a material-supported learning objective).
        * GATE 2 - LEVEL FIT: Is the question strictly calibrated to CEFR {level}? (REJECT if too advanced or too simplistic).
        * GATE 3 - CONTEXTUAL NATURALNESS, TECHNICAL PRECISION & ACCURATE EXPLANATIONS: Is every generated question fully natural and idiomatic in context, technically precise in its linguistic and domain terminology, and pedagogically appropriate for the target CEFR {level}? Ensure there is NO malformed or contextually unnatural wording. Every complete sentence must be idiomatic and realistic in its stated context. The stem and keyed answer must test exactly the same concept, and the correct answer must satisfy every condition stated in the stem without adding unsupported implications. For conjunctions and discourse markers, verify that the actual propositions on both sides create exactly the required relation (contrast, confirmation, reinforcement, consequence, concession, addition). For idioms, fixed expressions, collocations, and formal register, validate the complete expression in context (natural argument structure, case marking, object choice, prepositions/postpositions, register, and pragmatic force); NEVER construct a sentence that is technically interpretable but unnatural to a native speaker. Reject semantically misselected but superficially formal vocabulary in context (e.g. “salahiyet” where “selamet” is required). (Resolve all issues during generation itself; REJECT if artificial, malformed, misleading, awkward, linguistically imprecise, or contextually unnatural).
        * GATE 4 - EXACTLY ONE DEFENSIBLE CORRECT ANSWER & ANSWER-OPTION TYPE ALIGNMENT: Does every multiple-choice item have exactly ONE defensible correct answer in the full sentence and context? Keep the answer-option type aligned with what the stem asks for: a term must be answered by a term, a function by a function, an interpretation by an interpretation, and a form by a form. The correct answer must satisfy every condition stated in the stem without adding unsupported implications. Before finalizing, ensure no distractor is also grammatically, semantically, pragmatically, or factually valid for the same stem. (Resolve ambiguity during generation itself; REJECT if ambiguous, open to multiple interpretations, or if any distractor could also be defended as valid).
        * GATE 5 - PLAUSIBLE SAME-LEVEL DISTRACTORS & AUTHENTIC OPTIONS: Does EVERY single option (the correct answer AND all 3 distractors) stand on its own as a completely natural, grammatically valid, and authentic expression in {language}, with zero malformed or contextually unnatural wording? Distractors must be authentic, grammatical, naturally usable, semantically plausible, and competitive, but must not also satisfy the stem; NEVER invent, deform, or mechanically force word forms just to create parallel options. If natural same-form distractors do not exist, use plausible alternatives of the appropriate semantic or functional type instead. Distractors must compete with the correct answer at the same grammatical, semantic, pragmatic, or register level rather than being trivially eliminable, while strictly ensuring no distractor is also valid for the stem. Distractors must be not only grammatical in isolation, but idiomatically plausible in the exact sentence frame of the prompt. A distractor must be wrong because of meaning, pragmatic fit, or context, NEVER because the option itself is ungrammatical, awkward, invented, or malformed! (ABSOLUTELY REJECT if any distractor is itself grammatically unnatural, malformed, invented, structurally/idiomatically implausible in the sentence frame, or trivially eliminable due to category mismatch). Where appropriate, are at least two distractors plausible near-miss options from the same grammatical or semantic category as the answer?
        * GATE 6 - REPETITION PREVENTION vs. OBJECTIVE COVERAGE: Within the current test and the two retained previous batches, avoid exact or effectively repeated questions, including the same target tested again with essentially the same context and cognitive task, and avoid unnecessary repetition of the same expression, scenario, or effectively identical task across recent batches, while still allowing the same broader learning objective to reappear in a genuinely different context or task. Preserve strict material grounding, CEFR appropriateness, broad unit coverage, and authentic usage; never force novelty at the expense of quality or source fidelity. (REJECT any question that effectively duplicates a previously tested target in essentially the same context and cognitive task).
        --> If any candidate question fails ANY check, DISCARD IT and REPLACE it with a fully compliant question before producing your JSON response!
    
    RESPONSE FORMAT:
    Output EXCLUSIVELY a JSON object."""

    if focus_directive == "focus_grammar":
        system += f"""

    ================================================================================
    SUB-BATCH SPECIALIZATION - GRAMMAR & SYNTACTIC STRUCTURES (STRICT MANDATE):
    ================================================================================
    Focus 100% on grammatical rules, syntactic patterns, verb conjugations, morphological suffixes,
    and formal clause coordination taught in the material.
    ABSOLUTELY DO NOT test colloquial idioms, slang phrases, or conversational metaphors in this sub-batch.
    Test distinct grammatical objectives across each of the {gen_count} questions."""
    elif focus_directive == "focus_lexicon":
        system += f"""

    ================================================================================
    SUB-BATCH SPECIALIZATION - IDIOMS, LEXICON & PRAGMATIC SITUATIONS (STRICT MANDATE):
    ================================================================================
    Focus 100% on rich lexical distinctions, authentic idioms, professional expressions, and
    situational communicative reactions taught in the material.
    ABSOLUTELY DO NOT test repetitive grammatical suffix drills or tense conjugations in this sub-batch.
    Test distinct idioms, vocabulary domains, and situations across each of the {gen_count} questions."""

    user = f"""TASK: Generate EXACTLY {gen_count} unique {topic_type} questions.
    TOPIC: {topic_title}
    LEVEL: {level}
    SOURCE MATERIAL: {content_str}
    {ref_data}
    {forbidden_clause}
    
    PEDAGOGICAL EMPHASIS: {selected_variety_focus}
    VARIETY INSTRUCTION: Vary format, difficulty, and context. Use different scenario styles for every question. Freely introduce relevant thematic expressions and natural dialogue patterns appropriate for CEFR {level} to ensure maximum novelty and zero repetition, while preferring clarity and authentic usage over artificial difficulty or forced variety.
    
    QUESTION FORMAT VARIETY MANDATE (CRITICAL):
    - Provide a RICH MIX of question types!
    - DO NOT make all questions fill-in-the-blank! At most 3-4 questions should have a blank ('_____').
    - The majority of questions MUST BE direct situational questions ("¿Qué dices cuando...?"), communicative reactions ("¿Cuál es la respuesta adecuada?"), or contextual understanding questions WITHOUT any blanks!
    - ABSOLUTELY ZERO ARITHMETIC: NEVER ask math operations (sumar, multiplicar, 'más', 'plus'). Test numbers only via time, prices, or schedules!
    
    JSON STRUCTURE:
    {{
      "data": [
        {{
          "type": "mcq",
          "material_section": "Concise section identifier (e.g. 'Part 2: Core Lexicon' or 'Part 4: Dialogue')",
          "evidence": "Concise source reference (sentence, rule, example, dialogue line, or vocabulary item - NO chain-of-thought)",
          "cognitive_task": "situational_decision | dialogue_comprehension | sentence_application | grammatical_discrimination | communicative_collocation",
          "prompt": "Authentic question 100% in {language}",
          "translation_en": "Natural English translation of the prompt",
          "translation_tr": "Doğal Türkçe çevirisi",
          "answer": "Correct answer in {language}",
          "distractors": ["Distractor 1 in {language}", "Distractor 2 in {language}", "Distractor 3 in {language}"],
          "why": "Short 1-sentence reason (max 15 words)",
          "why_tr": "Kısa 1 cümlelik pedagojik açıklama (en fazla 15 kelime)"
        }}
      ]
    }}
    
    CRITICAL MANDATES:
    1) STRICT MATERIAL GROUNDING & TECHNICAL PRECISION: Preserve strict material grounding, CEFR {level} appropriateness, broad unit coverage, and authentic usage; never force novelty at the expense of quality or source fidelity. Questions must assess knowledge, vocabulary, grammar patterns, relationships, or communicative functions explicitly taught or demonstrated in the material. Distinguish the inherent meaning/function of a grammatical form from meanings that arise only from sentence context, and never attribute contextual consequences (continuity, completion, legal effect, certainty, intensity, causality) to a form unless genuinely encoded and supported by the source. Do not use broader, stronger, or more technical grammatical claims than can be safely defended, and avoid debatable linguistic terminology or unnecessarily fine-grained classifications unless explicitly supported by the material. Questions may transfer taught knowledge into fresh CEFR-appropriate contexts, but must never require external facts, unstated assumptions, generic world knowledge, or invented lesson content.
    2) GATE 1 - COMMON SENSE REJECTION: A question FAILS only when it primarily measures common sense, world knowledge, or obvious category matching rather than a material-supported objective.
    3) COGNITIVE TASK & FORMAT VARIETY: Actively vary cognitive tasks across the batch (situational decisions, dialogue/reading comprehension, grammatical precision/discrimination, communicative collocations, and at most 3-4 sentence completions). ABSOLUTELY NEVER repeat the same carrier pattern or test the same rule repeatedly through near-identical sentence templates.
    4) STRICT CEFR {level} CALIBRATION: Strictly preserve CEFR {level} difficulty across questions and options. Never use overly advanced terminology or syntax above {level}.
    5) EXACTLY ONE DEFENSIBLE ANSWER & PLAUSIBLE SAME-LEVEL DISTRACTORS: Every multiple-choice item MUST have exactly one defensible correct answer in the full sentence and context. Ensure the stem and keyed answer test EXACTLY the same concept, and the correct answer must satisfy every condition stated in the stem without adding unsupported implications. Keep the answer-option type aligned with what the stem asks for: a term must be answered by a term, a function by a function, an interpretation by an interpretation, and a form by a form. For conjunctions and discourse markers, verify that the actual propositions on both sides create exactly the required relation (contrast, confirmation, reinforcement, consequence, concession, addition). Before finalizing, ensure no distractor is also grammatically, semantically, pragmatically, or factually valid for the same stem. Distractors must be authentic, grammatical, naturally usable, semantically plausible, and competitive, competing at the same grammatical, semantic, pragmatic, or register level rather than being trivially eliminable; never invent, deform, or mechanically force word forms just to create parallel options. If natural same-form distractors do not exist, use plausible alternatives of the appropriate semantic or functional type instead. Resolve ambiguity during generation itself. Ensure stems, answers, and distractors are all idiomatic, grammatically valid, functionally plausible, and mutually consistent, with NO malformed or contextually unnatural wording, avoiding artificial wording, misleading terminology, or options trivially eliminable for the wrong reason. For idioms, fixed expressions, collocations, and formal register, validate the complete expression in context, including natural argument structure, case marking, object choice, prepositions/postpositions, register, and pragmatic force; NEVER construct a sentence that is technically interpretable but unnatural to a native speaker. Strictly reject semantically misselected but superficially formal vocabulary in context (e.g. “salahiyet” where “selamet” is required). Collocational arguments, complements, and surrounding phrases must be 100% authentic in real living usage (e.g. “Ekibinizi tenzih ederek...”). ZERO easy throwaways, filler options, or trivially eliminable distractors.
    6) 100% TARGET LANGUAGE: 'prompt', 'answer', and 'distractors' MUST BE 100% IN {language}.
    7) AVOID EXACT/EFFECTIVE REPETITION & ALLOW BROADER OBJECTIVE COVERAGE: Within the current test and the two retained previous batches, avoid exact or effectively repeated questions, including the same target tested again with essentially the same context and cognitive task, and avoid unnecessary repetition of the same expression, scenario, or effectively identical task across recent batches, while still allowing the same broader learning objective to reappear in a genuinely different context or task. Preserve strict material grounding, CEFR appropriateness, broad unit coverage, and authentic usage; never force novelty at the expense of quality or source fidelity.
    8) BLANK TRANSLATION RULE: If and only if 'prompt' contains a blank ('_____'), 'translation_en' and 'translation_tr' MUST keep '_____' without revealing the answer word.
    9) STRICTLY NO ARITHMETIC: NEVER generate math calculations, equations, or addition/multiplication drills. Test numbers ONLY in authentic communicative contexts (time, prices, dates).
    10) CONCISE EXPLANATIONS & METADATA: 'why' and 'why_tr' MUST be 1 short concise sentence (max 15 words). 'evidence' and 'material_section' MUST be concise reference pointers (NO chain-of-thought).
    11) NATURALNESS, TECHNICAL PRECISION & AUTHENTIC USAGE: The model itself must produce fully natural and idiomatic questions, precise linguistic and domain terminology (when describing grammar, pronunciation, meaning, or usage), exactly one defensible correct answer, plausible same-level distractors, and NO malformed or contextually unnatural wording. Ensure every complete sentence is idiomatic and realistic in its stated context. Every linguistic, grammatical, pragmatic, or domain explanation must be technically precise and no broader than the source supports; never treat a contextual effect as an inherent meaning of a form, and never attribute contextual consequences (continuity, completion, legal effect, certainty, intensity, causality) to a form unless genuinely encoded. Do not use broader or stronger claims than can be safely defended, and avoid debatable linguistic terminology. Ensure the stem and keyed answer test exactly the same concept, satisfying all stem conditions. For conjunction/discourse-marker items, verify that the actual propositions create the exact required logical relation. Stems, scenarios, and all 4 options must flow with effortless native idiomacy, living contemporary vocabulary, and examiner-grade precision. Resolve all issues during generation itself.
    12) PRE-OUTPUT 6-GATE SELF-VERIFICATION: Internally verify each question against the 6 gates (Material grounding & source bounds distinguishing inherent from contextual meaning, Level fit, Natural context & technical precision with accurate explanations, no malformed wording, and verified complete expressions/idioms/relations, Exactly one defensible correct answer aligned with stem conditions and answer-option type, Plausible authentic same-level distractors with no deformed forms, Anti-repetition vs. broader objective coverage) before returning JSON. Every multiple-choice item must have exactly one defensible correct answer in the full sentence and context; ensure no distractor is valid for the same stem. Ensure every explanation is technically precise and no broader than the source supports, never treat a contextual effect as an inherent meaning, and ensure the stem and keyed answer test exactly the same concept. Distractors must be authentic, naturally usable, and compete at the same grammatical, semantic, pragmatic, or register level rather than being trivially eliminable. Within the current test and the two retained previous batches, avoid exact or effectively repeated questions and expressions (same target in essentially same context/task), while allowing the same broader learning objective to reappear in a genuinely different context or task. Preserve strict material grounding, CEFR appropriateness, broad unit coverage, and authentic usage; never force novelty at the expense of quality or source fidelity. Resolve ambiguity and all issues during generation itself."""

    # MAX VARIETY SEED: Uses generation_seed if provided to differentiate sub-batches, else high-precision timestamp
    seed = generation_seed if generation_seed is not None else (int(time.time() * 1000) % 999999)
    user += f"\n\nUNIQUE_REQUEST_ID: {seed}_{py_random.random()}"
    
    try:
        t_ai_duration = 0.0
        if model_override and str(model_override).lower() in ["none", "offline", "skip", "disabled"]:
            res = None
        else:
            target_model = model_override if model_override else MODEL_STRUCTURAL
            target_temp = 0.95 if existing_questions else 0.90
            calc_max_tokens = min(5000, max(1500, gen_count * 250))
            t_ai_start = time.time()
            res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=target_model, max_tokens=calc_max_tokens, temperature=target_temp, json_mode=True, allow_fallback=True)
            t_ai_duration = time.time() - t_ai_start
        
        raw_list = []
        if isinstance(res, list):
            raw_list = res
        elif isinstance(res, dict):
            raw_list = res.get("data") or res.get("questions") or res.get("items") or res.get("quiz") or res.get("activities") or []
        
        t_filter_start = time.time()
        # ── V5 RIGOROUS VALIDATION & ANTI-GIVEAWAY FILTER ──
        final = []
        for item in raw_list:
            if not isinstance(item, dict): continue
            
            p = str(item.get("prompt", "")).strip()
            a = str(item.get("answer", "")).strip()
            d = item.get("distractors", [])
            
            if not (p and a and isinstance(d, list)):
                continue

            clean_a_token = _normalize_token(a)
            clean_p_token = _normalize_token(p)

            # IN-BATCH DEDUPLICATION: Do not test the same target answer twice in the same batch
            if any(_normalize_token(f.get("answer")) == clean_a_token for f in final):
                continue

            # IN-BATCH PATTERN & PROMPT DIVERSITY: Reject near-identical prompt stems or sentence templates within the batch
            if any(difflib.SequenceMatcher(None, clean_p_token, _normalize_token(f.get("prompt", ""))).ratio() > 0.85 for f in final):
                continue

            # COGNITIVE TASK VARIETY: Allow adequate fill-in-the-blank questions
            has_blank = "_" in p or "____" in p
            if has_blank:
                current_blanks = sum(1 for f in final if "_" in f.get("prompt", "") or "____" in f.get("prompt", ""))
                if current_blanks >= max(8, int(gen_count * 0.75)):
                    continue

            # STRICT DIVERSITY FILTER: Absolute rejection of any repeated or near-duplicate prompt from previous rounds
            if forbidden_prompt_keys:
                if clean_p_token in forbidden_prompt_keys:
                    continue
                # Character similarity check: reject only if prompt is a true near-duplicate (>94% identical)
                if any(difflib.SequenceMatcher(None, clean_p_token, fp_key).ratio() > 0.94 for fp_key in forbidden_prompt_keys):
                    continue

            # Reject prompts containing Turkish instructional words ONLY if target language is NOT Turkish (must be 100% target language)
            if not any(k in language.lower() for k in ["turkish", "türkçe", "turkce"]):
                tr_prompt_markers = ["hangisidir", "aşağıdakilerden", "seçiniz", "cümleyi", "anlamına gelir", "karşılığı nedir", "boşluğu doldur", "uygun kelimeyi"]
                if any(m in p.lower() for m in tr_prompt_markers):
                    continue

            # GATE 1 COMMON SENSE & TRIVIAL CATEGORY MATCHING REJECTION:
            # Fails only when the question primarily measures generic common sense / world knowledge rather than a material-supported learning objective
            clean_p_lower = p.lower()
            stereotypical_category_patterns = [
                r'\b(?:dónde|donde|where|wo|où|ou|dove)\s+(?:trabaja|trabajan|works?|arbeitet|travaille|lavora)\s+(?:un|una|el|la|a|an|the|ein|eine|der|die|das|un|une|le|la|uno)\s+(?:médico|médica|doctor|profesor|profesora|maestro|maestra|cocinero|cocinera|camarero|camarera|bombero|bombera|policía|arzt|ärztin|lehrer|lehrerin|koch|köchin|kellner|kellnerin|médecin|professeur|cuisinier|serveur|pompiers?|policier|medico|professore|cuoco|cameriere)\b',
                r'\b(?:qué|que|what|was|que|cosa)\s+(?:haces|hace|do you do|macht man|fais-tu|fai)\s+(?:si|cuando|when|wenn|quand|quando)\s+(?:tienes\s+hambre|tienes\s+sed|you are hungry|you are thirsty|man hunger hat|man durst hat)\b'
            ]
            if any(re.search(pat, clean_p_lower) for pat in stereotypical_category_patterns):
                continue

            # Clean and deduplicate distractors (must not match answer and must be distinct)
            clean_d = []
            for dist in d:
                ds = str(dist).strip()
                if ds and ds.lower() != a.lower() and ds.lower() not in [cd.lower() for cd in clean_d]:
                    clean_d.append(ds)

            # If fewer than 3 distractors, supplement from raw_list or topic_content to reach exactly 3
            if len(clean_d) < 3:
                extra_candidates = []
                for other_item in raw_list:
                    if isinstance(other_item, dict):
                        oa = str(other_item.get("answer", "")).strip()
                        if oa and oa.lower() != a.lower() and oa.lower() not in [cd.lower() for cd in clean_d]:
                            extra_candidates.append(oa)
                        for od in other_item.get("distractors", []):
                            ods = str(od).strip()
                            if ods and ods.lower() != a.lower() and ods.lower() not in [cd.lower() for cd in clean_d]:
                                extra_candidates.append(ods)
                if isinstance(topic_content, dict):
                    for pg in topic_content.get("pages", []):
                        for it in pg.get("items", []):
                            if isinstance(it, dict) and it.get("term"):
                                t_str = str(it.get("term")).strip()
                                if t_str and t_str.lower() != a.lower() and t_str.lower() not in [cd.lower() for cd in clean_d]:
                                    extra_candidates.append(t_str)

                # Filter plausible length candidates
                extra_candidates = [cand for cand in extra_candidates if abs(len(cand) - len(a)) <= max(len(a), 15)]
                py_random.shuffle(extra_candidates)
                for cand in extra_candidates:
                    if cand.lower() not in [cd.lower() for cd in clean_d]:
                        clean_d.append(cand)
                    if len(clean_d) >= 3:
                        break

            # STRICT MANDATE: MUST have at least 3 distractors so total options is ALWAYS 4!
            if len(clean_d) < 3:
                continue

            # Reject pure math operations and arithmetic drill questions
            if is_arithmetic_question(p) or is_arithmetic_question(a):
                continue

            # Programmatic Anti-Giveaway & Anti-Trivia Verification
            clean_p = re.sub(r'[^\w\s]', ' ', p.lower())
            clean_a = re.sub(r'[^\w\s]', ' ', a.lower()).strip()
            
            is_giveaway = False
            if len(clean_a) >= 3:
                # Literal quote of answer inside prompt e.g. ' "¿cómo estás?" '
                quoted_answer_pattern = rf"['\"«“]{re.escape(clean_a)}['\"»”]"
                if re.search(quoted_answer_pattern, clean_p):
                    is_giveaway = True
                if clean_p.strip() == clean_a.strip():
                    is_giveaway = True
            
            # Reject meta-trivia about letter names, string properties, or alphabet exclusivity
            trivia_indicators = [
                "nombre que incluye", "se llama", "name includes", "includes the word",
                "harfinin adı", "kelimesini içerir", "which letter has the name",
                "cuál de estas letras tiene un nombre", "letter's name", "name of the letter",
                "how is the letter named", "harfi nasıl adlandırılır",
                "es exclusiva", "exclusiva del", "letra exclusiva", "unique to the", "exclusive to the",
                "alfabesinde bulunan tek", "alfabesine özgü", "exclusivo del alfabeto"
            ]
            if any(t in clean_p for t in trivia_indicators):
                is_giveaway = True

            # Reject meta-orthographic accent/spelling trivia (e.g. "Which word has a tilde?")
            meta_accent_indicators = [
                "tilde grafica", "lleva tilde", "se escribe con tilde", "con tilde",
                "accent aigu", "accent grave", "con acento", "hat einen akzent",
                "hangi kelimede sapka", "which word has an accent", "has a tilde", "se escribe tradicionalmente con tilde"
            ]
            if any(mai in clean_p for mai in meta_accent_indicators):
                is_giveaway = True

            # Multi-answer accent sanity check: If prompt asks about accents, never allow multiple options with accents
            if any(w in clean_p for w in ["tilde", "acento", "accent"]):
                accent_opts = [o for o in [a] + clean_d[:3] if re.search(r'[áéíóúÁÉÍÓÚàèìòùÀÈÌÒÙâêîôûÂÊÎÔÛ]', o)]
                if len(accent_opts) > 1:
                    is_giveaway = True

            # Reject proprietary commercial product trivia (e.g. City-Ticket, BahnCard rules)
            product_trivia = ["city ticket", "city-ticket", "bahncard", "abonnement general", "cartes de reduction"]
            if any(pt in clean_p for pt in product_trivia):
                is_giveaway = True

            # Reject non-target language characters in options (e.g., 'ç' in Spanish)
            if any(s in language.lower() for s in ["spanish", "español", "ispanyolca"]):
                if any("ç" in o.lower() for o in [a] + clean_d):
                    is_giveaway = True

            # Reject single-letter options for meta questions (like ['Ñ', 'Ç', 'W', 'K'] or ['La letra Ñ', 'La letra Ç'])
            if all(len(re.sub(r'^(la letra|the letter|harf|harfi)\s*', '', opt.lower()).strip()) <= 2 for opt in [a] + clean_d[:3]):
                is_giveaway = True

            # Reject extreme length disparity where the answer is giveaway long/short
            if clean_d and len(a) > 2.2 * max(len(dist) for dist in clean_d[:3]) and len(a) > 25:
                is_giveaway = True
            if clean_d and min(len(dist) for dist in clean_d[:3]) > 2.5 * len(a) and min(len(dist) for dist in clean_d[:3]) > 25:
                is_giveaway = True

            # Reject transparent cognate giveaways only if prompt itself gives away the answer
            if is_transparent_cognate_giveaway(p, "", a, language):
                is_giveaway = True

            # Reject hybrid Frankenstein questions where target language blank is inside instructional language sentence
            if ("______" in p or "____" in p) and not is_giveaway:
                if "turkish" not in language.lower() and "türkçe" not in language.lower():
                    blank_lines = [line for line in p.split("\n") if "____" in line]
                    for bl in blank_lines:
                        tr_unique_markers = [" için ", " sabah ", " çünkü ", " lütfen ", " hangisi ", " boşluğa ", " seçiniz "]
                        bl_lower = bl.lower()
                        if any(m in bl_lower for m in tr_unique_markers):
                            is_giveaway = True
                            break

            # Multilingual circular tautological definition detector
            def_question_patterns = [
                r'\bwas ist (?:eine?|der|das|die)?\s*([a-zäöüß]+)',
                r'\bqué es (?:el|la|un|una)?\s*([a-záéíóúñ]+)',
                r'\bwhat is (?:a|an|the)?\s*([a-z]+)',
                r'\bqu[\'’]est-ce qu(?:e|\')\s*(?:un|une|le|la|les)?\s*([a-zàâçéèêëîïôûùü]+)',
                r'\b(?:che\s+)?cos[\'’]è\s*(?:un|uno|una|il|lo|la)?\s*([a-zàèéìòóù]+)',
                r'\bo que é (?:um|uma|o|a)?\s*([a-zà-ú]+)',
                r'([a-zçğıöşü]+)\s+nedir\b'
            ]
            for pat in def_question_patterns:
                m = re.search(pat, clean_p)
                if m:
                    target_term = m.group(1).strip()
                    if len(target_term) >= 5:
                        stem = target_term[:5]
                        if stem in clean_a:
                            is_giveaway = True
                            break

            # Universal trivial 1-word collocation blank detector
            if "_" in p and len(clean_a.split()) == 1:
                trivial_verbs = {"fahren", "gehen", "machen", "haben", "sein", "ser", "estar", "haber", "hacer", "ir", "aller", "faire", "fare", "andare"}
                if clean_a in trivial_verbs:
                    pre_blank_match = re.search(r'(\w+)\s*_{2,}', p.lower())
                    if pre_blank_match:
                        pre_word = pre_blank_match.group(1)
                        if pre_word in ["geschwindigkeit", "tempo", "vitesse", "velocidad", "velocità", "zähne", "bett", "hause"]:
                            is_giveaway = True

            # Dynamic Language Calibration Registry (Clean, data-driven, language-agnostic runner)
            calib_key = next((k for k in LANGUAGE_CALIBRATION_REGISTRY if k in language.lower()), None)
            if calib_key:
                calib = LANGUAGE_CALIBRATION_REGISTRY[calib_key]
                for banned in calib.get("banned_terms", []):
                    if banned in clean_p or banned in clean_a or any(banned in d.lower() for d in clean_d):
                        is_giveaway = True
                        break
                if is_b1:
                    for b1_banned in calib.get("b1_banned_terms", []):
                        if b1_banned in clean_p or b1_banned in clean_a or any(b1_banned in d.lower() for d in clean_d):
                            is_giveaway = True
                            break
                for pat, repl in calib.get("normalizers", []):
                    p = re.sub(pat, repl, p, flags=re.IGNORECASE)
                    a = re.sub(pat, repl, a, flags=re.IGNORECASE)
                    clean_d = [re.sub(pat, repl, d, flags=re.IGNORECASE) for d in clean_d]
                clean_d = list(dict.fromkeys(clean_d))
                if len(clean_d) < 3:
                    is_giveaway = True
                
            if is_giveaway:
                continue

            why_en = item.get("why", "Correct answer based on the material.")
            why_tr = item.get("why_tr", item.get("why", "Materyale göre doğru seçenek."))
            t_en = item.get("translation_en") or item.get("translation", "")
            t_tr = item.get("translation_tr") or item.get("translation", "")

            # If prompt has a blank, preserve the blank in translations
            if re.search(r'_{2,}', p):
                t_en, t_tr = _sanitize_blank_translations(p, a, t_en, t_tr, why_en, why_tr, topic_content)

            # Assemble options with deduplicated distractors (ALWAYS 4 OPTIONS)
            opts = [a] + clean_d[:3]
            py_random.shuffle(opts)
            
            final.append({
                "id": _uid(),
                "type": "mcq",
                "prompt": p,
                "translation": t_tr if material_language == "tr" else t_en,
                "translation_en": t_en,
                "translation_tr": t_tr,
                "answer": a,
                "distractors": clean_d[:3],
                "options": opts,
                "why": why_en,
                "why_tr": why_tr,
                "evidence": str(item.get("evidence", "")).strip()[:180],
                "material_section": str(item.get("material_section", "")).strip()[:100],
                "cognitive_task": str(item.get("cognitive_task", "")).strip()[:50]
            })
            if len(final) >= gen_count:
                break
        
        # ── DETERMINISTIC CONTENT FALLBACK (Prevents Empty Questions & Loops) ──
        if len(final) < c and isinstance(topic_content, dict):
            # Helper for fallback target language questions
            is_esp = any(s in language.lower() for s in ["spanish", "español", "ispanyolca"])
            is_de = any(s in language.lower() for s in ["german", "deutsch", "almanca"])
            is_fr = any(s in language.lower() for s in ["french", "français", "fransızca"])
            is_it = any(s in language.lower() for s in ["italian", "italiano", "italyanca"])
            is_ru = any(s in language.lower() for s in ["russian", "русский", "rusça"])

            def _make_fallback_prompt(target_term):
                if is_esp:
                    templates = [
                        f"En una conversación cotidiana auténtica, ¿cuál es la expresión más adecuada?: '______'",
                        f"Completa el diálogo de manera natural y comunicativa: '______'",
                        f"Selecciona la opción correcta y más apropiada para esta situación: '______'"
                    ]
                elif is_de:
                    templates = [
                        f"Welcher Ausdruck passt am besten in diesen alltäglichen Kontext?: '______'",
                        f"Vervollständigen Sie den Satz auf natürliche Weise: '______'"
                    ]
                elif is_fr:
                    templates = [
                        f"Quelle expression est la plus appropriée dans ce contexte communicatif ?: « ______ »",
                        f"Complétez la phrase de manière naturelle: « ______ »"
                    ]
                elif is_it:
                    templates = [
                        f"Quale espressione è più adatta in questo contesto comunicativo?: « ______ »",
                        f"Completa la frase in modo naturale: « ______ »"
                    ]
                elif is_ru:
                    templates = [
                        f"Какое выражение лучше всего подходит в данной коммуникативной ситуации?: « ______ »",
                        f"Дополните предложение естественным образом: « ______ »"
                    ]
                else:
                    templates = [
                        f"Which expression is most appropriate in this communicative context?: '______'",
                        f"Complete the sentence naturally: '______'"
                    ]
                return py_random.choice(templates)

            # 1. Pull pre-authored MCQs from topic content pages
            pages = list(topic_content.get("pages", []))
            py_random.shuffle(pages)
            for page in pages:
                if len(final) >= c: break
                if page.get("type") == "mcq" and page.get("prompt") and page.get("answer"):
                    prompt_txt = str(page.get("prompt", "")).strip()
                    ans_txt = str(page.get("answer", "")).strip()
                    if is_arithmetic_question(prompt_txt) or is_arithmetic_question(ans_txt):
                        continue
                    p_tok = _normalize_token(prompt_txt)
                    a_tok = _normalize_token(ans_txt)
                    if forbidden_prompt_keys and p_tok in forbidden_prompt_keys:
                        continue
                    if forbidden_answer_keys and a_tok in forbidden_answer_keys:
                        continue
                    if any(_normalize_token(f.get("answer")) == a_tok for f in final):
                        continue
                    if not any(f.get("prompt") == prompt_txt for f in final):
                        opts = list(page.get("options", []))
                        if not opts:
                            opts = [page.get("answer")] + page.get("distractors", [])
                        py_random.shuffle(opts)
                        p_tr = page.get("prompt_tr") or page.get("translation_tr", "")
                        p_en = page.get("prompt") or page.get("translation_en", "")
                        final.append({
                            "id": _uid(),
                            "type": "mcq",
                            "prompt": prompt_txt,
                            "translation": p_tr if material_language == "tr" else p_en,
                            "translation_en": p_en,
                            "translation_tr": p_tr,
                            "answer": page.get("answer"),
                            "distractors": [x for x in opts if x != page.get("answer")][:3],
                            "options": opts,
                            "why": page.get("explanation", "Correct choice based on the lesson."),
                            "why_tr": page.get("explanation_tr", page.get("explanation", "Ders içeriğine göre doğru seçenek."))
                        })

            # Pre-authored MCQs are pulled if any exist in the topic pages; no broken dummy templates synthesized.
            pass

        # Sanitize Turkish fields in generated questions
        for q in final:
            if q.get("translation_tr"):
                q["translation_tr"] = _sanitize_turkish_content(heal_turkish_syntax(q["translation_tr"]))
            if q.get("why_tr"):
                q["why_tr"] = _sanitize_turkish_content(heal_turkish_syntax(q["why_tr"]))
            if material_language == "tr" and q.get("translation"):
                q["translation"] = _sanitize_turkish_content(heal_turkish_syntax(q["translation"]))

        t_filter_duration = time.time() - t_filter_start

        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [QUIZ-TIMING] {topic_title} (req={c}): Main AI call={t_ai_duration:.2f}s | Parsing/filtering/dedup={t_filter_duration:.3f}s | Valid={len(final)}/{len(raw_list)}\n")
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-DONE] topic={topic_title} requested={c} returned={len(final)}\n")
            
        return final[:gen_count]
    except Exception as e:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-CRASH] {e}\n")
        return []

def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, model_override=None, material_language="en"):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions, is_pdf_source=is_pdf_source, model_override=model_override, material_language=material_language)

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, material_language="en"):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions, is_pdf_source=is_pdf_source, material_language=material_language)

def ai_grade_open_response(question, student_answer, correct_answer):
    prompt = f"Grade: Q:{question}, C:{correct_answer}, S:{student_answer}. JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150)
    return (result.get("score", 0.0), result.get("feedback", "")) if result else (0.0, "")

def ai_generate_curriculum(language, level, prompt_extra=""):
    """Generates course structure, creating both English and Turkish versions natively via AI, grounded in official authority standards."""
    from services.cefr_reference import get_cefr_conditioning, LANGUAGE_CEFR_STANDARDS
    lang_std = LANGUAGE_CEFR_STANDARDS.get(language, {})
    official_institution = lang_std.get("institution", f"Council of Europe Official CEFR Framework for {language}")
    cefr_curriculum_guidance = get_cefr_conditioning(language, level, "Curriculum Architecture", "syllabus")

    system = f"""You are a world-class bilingual curriculum architect and expert linguist operating under the official academic framework of {official_institution} and the Council of Europe CEFR standards (A1-C2) for {language}. 
    Your mission: Design an authoritative, pedagogically deep, and culturally rich roadmap for learning {language}, strictly adhering to the official syllabus requirements of {official_institution} for level {level}.
    
    {cefr_curriculum_guidance}
    
    CRITICAL BILINGUAL GENERATION REQUIREMENT:
    You MUST generate BOTH language versions natively in the exact same output:
    1. 'title': The professional English curriculum title (e.g., 'Polite Expressions for Conversation', 'Everyday Survival Vocabulary').
    2. 'title_tr': The authentic, natural Turkish curriculum title (e.g., 'Sohbet İçin Nezaket İfadeleri', 'Günlük Hayatta Kalma Kelimeleri').
    
    STRICT LINGUISTIC RULES FOR 'title_tr':
    - Every 'title_tr' must be 100% natural, grammatically correct Turkish as written by an educated Turkish teacher.
    - NEVER leave English words in 'title_tr' (e.g. NEVER write 'Nazik İfadeler for Conversation' or 'Traveling İçin Temel Kelimeler').
    - NEVER use English-specific terms like 'Wh- Questions' or 'Wh- Soruları'. In Turkish, use 'Soru Kelimeleri' or 'Soru Sözcükleri' (e.g., 'Soru Kelimeleri: Kim, Ne, Nerede').
    - In non-English target languages, do NOT write 'Wh- Questions' in English titles either; use 'Question Words (Who, What, Where)' or 'Information Questions'.
    - NEVER duplicate words (e.g. NEVER write 'Günlük Hayatta Hayatta Kalma' or 've ve').
    - Target language verbs or grammatical markers (like 'ser', 'estar') stay in single quotes: e.g. "'Ser' Kullanarak Kimliği Tanımlama".
    - PEDAGOGIC DEPTH: Go beyond simple vocabulary. Each topic should feel like a real lesson that covers functional usage, nuances, and situational grammar."""
    
    level_guidelines = {
        "A1": "Focus on absolute basics: alphabet/phonetics, greetings, numbers, basic present tense, immediate survival vocabulary, and personal info.",
        "A2": "Focus on routine tasks, past tenses (intro), describing surroundings, simple social exchanges, and common shopping/work scenarios.",
        "B1": "Focus on traveling situations, expressing opinions/dreams/hopes, complex past tenses, future/conditional, and providing reasons for plans.",
        "B2": "Focus on technical discussions, interacting with natives without strain, detailed text on diverse subjects, and introductory Subjunctive mood.",
        "C1": "Focus on complex subjects, implicit meaning, flexible/effective language for academic/professional use, deep nuance, and advanced idiomatic usage.",
        "C2": "Focus on near-native mastery, summarizing complex sources, precise expression of fine shades of meaning, and spontaneous academic reconstruction."
    }
    
    # Determine the closest CEFR guideline
    current_guideline = next((v for k, v in level_guidelines.items() if k in level.upper()), "Follow general CEFR progression.")

    user = f"""Create a comprehensive {level} {language} course syllabus{f' focusing on: {prompt_extra}' if prompt_extra else ''}.
LEVEL-SPECIFIC FOCUS: {current_guideline}

REASONING DIRECTIVE:
In your internal reasoning process, analyze the target CEFR requirements from {official_institution} for {level} {language}.
Formulate a strictly logical, pedagogically rich progression across exactly 6 chapters with 5 descriptive topics each (30 topics total).
Reflect on Turkish-speaking learners' linguistic profile, avoiding English interference.
Verify that every single 'title_tr' is authentic, grammatically pure Turkish.

RULES:
1. PEDAGOGICAL ACCURACY: The topics MUST strictly reflect the {level} level requirements.
2. NO GENERIC TITLES: Do NOT use 'Vocabulary', 'Grammar', or 'Exercises'. Every topic must be descriptive (e.g., 'Navigating a Hospital', 'The Imperfect vs. Preterite', 'Debating Environmental Ethics').
3. PROGRESSION: Ensure units move logically from foundational to complex within the {level} bracket.
4. VARIETY: Mix functional language, grammar, and cultural context.
5. MANDATORY SCOPE: Generate EXACTLY 6 chapters.
6. TOPIC DENSITY: Each chapter MUST have EXACTLY 5 descriptive topics (30 topics total).
7. BILINGUAL PAIRS (MANDATORY): For every chapter and topic, provide BOTH English ('title') and Turkish ('title_tr'):
   - Example 1: 'title': 'Polite Expressions for Conversation' -> 'title_tr': 'Sohbet İçin Nezaket İfadeleri'
   - Example 2: 'title': 'Basic Adjectives for Personal Description' -> 'title_tr': 'Kişisel Tanım İçin Temel Sıfatlar'
   - Example 3: 'title': 'Everyday Survival Vocabulary' -> 'title_tr': 'Günlük Hayatta Kalma Kelimeleri'
   - Example 4: 'title': 'Essential Vocabulary for Traveling' -> 'title_tr': 'Seyahat İçin Temel Kelimeler'
   - Example 5: 'title': "Using 'Ser' to Describe Identity" -> 'title_tr': "'Ser' Kullanarak Kimliği Tanımlama"
   - Example 6: 'title': 'Question Words: Who, What, Where' -> 'title_tr': 'Soru Kelimeleri: Kim, Ne, Nerede'
   - Every word in 'title_tr' must be 100% Turkish. No English leakages. No 'Wh- Soruları'. No word duplications.

Return ONLY valid JSON:
{{
  "chapters": [
    {{
      "number": 1,
      "title": "Everyday Survival Vocabulary",
      "title_tr": "Günlük Hayatta Kalma Kelimeleri",
      "topics": [
        {{
          "title": "Polite Expressions for Conversation",
          "title_tr": "Sohbet İçin Nezaket İfadeleri",
          "type": "vocabulary"
        }}
      ]
    }}
  ]
}}"""
    res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_CURRICULUM, max_tokens=4500, temperature=0.3)
    chapters = res.get("chapters", []) if res else []
    
    # Tier 1 Fallback: If primary model gave < 4 chapters, try MODEL_FALLBACK
    if (not chapters or len(chapters) < 4) and MODEL_FALLBACK != MODEL_CURRICULUM:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [CURRICULUM] Primary model gave <4 units. Trying fallback {MODEL_FALLBACK}...\n")
        res_fb = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_FALLBACK, max_tokens=4500, temperature=0.3)
        if res_fb and res_fb.get("chapters") and len(res_fb["chapters"]) >= 4:
            chapters = res_fb["chapters"]

    # Tier 2 Fallback: If still < 4 chapters, load verified blueprint cache
    if not chapters or len(chapters) < 4:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [CURRICULUM] AI generation returned <4 units. Loading verified blueprint fallback for {language} {level}.\n")
        cache_file = _get_blueprint_path(language, level)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    if cached_data and cached_data.get("chapters") and len(cached_data["chapters"]) >= 4:
                        from services.curriculum_translator import ensure_bilingual_curriculum
                        return ensure_bilingual_curriculum(cached_data["chapters"])
            except Exception:
                pass

    # Clean titles and re-index chapters
    for i, ch in enumerate(chapters):
        ch["number"] = i + 1
        if "title" in ch and isinstance(ch["title"], str):
            ch["title"] = re.sub(r'^Unit\s*\d+\s*[:\-]*\s*', '', ch["title"], flags=re.IGNORECASE).strip()
        if "title_tr" in ch and isinstance(ch["title_tr"], str):
            ch["title_tr"] = re.sub(r'^Ünite\s*\d+\s*[:\-]*\s*', '', ch["title_tr"], flags=re.IGNORECASE).strip()

    # ── ULTIMATE SAFETY GUARD: Never return fewer than 4 chapters ──
    if not chapters or len(chapters) < 4:
        cache_file = _get_blueprint_path(language, level)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    if cached_data and cached_data.get("chapters"):
                        from services.curriculum_translator import ensure_bilingual_curriculum
                        return ensure_bilingual_curriculum(cached_data["chapters"])
            except Exception:
                pass

    # ── BILINGUAL TITLE ENRICHMENT: Ensure both title (EN) and title_tr (TR) are populated cleanly ──
    from services.curriculum_translator import ensure_bilingual_curriculum
    chapters = ensure_bilingual_curriculum(chapters)

    return chapters
def ai_generate_report_insights(cohort_data):
    """Generates high-level pedagogical insights for teacher reports."""
    prompt = f"Analyze student performance and provide 3 actionable teaching insights: {json.dumps(cohort_data)}"
    res = _call_ai([{"role": "user", "content": prompt}], max_tokens=600)
    return res.get("explanation", "Insufficient data for insights.") if res else "Connection Error."

def universal_sanitize_english(text: str) -> str:
    """Sanitizes English pedagogical fields, replacing inadvertent Turkish comparisons with pure English phonetic anchors."""
    if not isinstance(text, str) or not text.strip():
        return text

    s = text

    # If it's pure nationality/country vocabulary, skip changing nationality terms
    is_vocab_nationality = any(ct in s.lower() for ct in ["turkey / turkish", "soy turco", "de turquía", "from turkey"])

    # 1. B/V fixes:
    s = re.sub(
        r'\b(?:the\s+)?spanish\s+v\b',
        "Spanish 'b' and 'v' (identical bilabial sound [b]/[β], unlike English 'v')",
        s, flags=re.I
    )

    # 2. Vowels:
    s = re.sub(r'identical to Turkish \'i\'', "similar to 'ee' in English 'see' but shorter and without a glide [i]", s, flags=re.I)
    s = re.sub(r'pure Turkish \'[iuoae]\'', lambda m: f"pure Spanish vowel {m.group(0)[-3:]}, crisp and without an English diphthong glide", s, flags=re.I)
    s = re.sub(r'pure Turkish [iuoae]', lambda m: f"pure Spanish {m.group(0)[-1]}, crisp and without a glide", s, flags=re.I)
    s = re.sub(r'clean(?:ly)?(?:, short)? (?:as in )?Turkish \'e\'', "clean, pure vowel [e] as in English 'bet'", s, flags=re.I)
    s = re.sub(r'as in Turkish \'okul\'', "as in English 'for'", s, flags=re.I)

    # 3. Consonants:
    s = re.sub(r'(?:digraph is |is )?(?:pronounced )?(?:exactly |identically |identical )?(?:to |like )?(?:the )?Turkish (?:letter |sound )?\'[çc]\'(?: sound)?(?: \[[^\]]+\])?(?: in \'çay\')?', "like English 'ch' in 'chocolate' [tʃ]", s, flags=re.I)
    s = re.sub(r'like (?:the )?\'[çc]\' in Turkish \'çay\'', "like English 'ch' in 'chocolate'", s, flags=re.I)
    s = re.sub(r'(?:exactly |similarly )?like (?:the )?Turkish \'g\'(?: in \'gül\')?', "like hard English 'g' in 'go'", s, flags=re.I)
    s = re.sub(r'like (?:the )?\'g\' in Turkish \'gül\'', "like hard English 'g' in 'go'", s, flags=re.I)
    s = re.sub(r'(?:pronounced )?(?:similarly |identical )?to (?:the )?Turkish \'y\'(?: sound)?(?:,\s*pronounced cleanly without an English glide)?', "like English 'y' in 'yellow'", s, flags=re.I)
    s = re.sub(r'like Turkish \'y\'', "like English 'y' in 'yellow'", s, flags=re.I)
    s = re.sub(r'(?:exactly |identically )?identical to (?:the single )?Turkish (?:single )?\'r\'(?: sound in \'(?:kara|ara)\')?', "an alveolar flap [ɾ], like the quick 'tt' in American English 'butter'", s, flags=re.I)
    s = re.sub(r'pronounced like (?:the single )?Turkish \'r\'', "pronounced as an alveolar flap [ɾ], like 'tt' in 'butter'", s, flags=re.I)
    s = re.sub(r'identical to standard Turkish \'r\'', "an alveolar tap [ɾ], like 'tt' in 'butter'", s, flags=re.I)
    s = re.sub(r'identical to (?:the )?(?:English and )?Turkish \'f\'', "identical to English 'f'", s, flags=re.I)
    s = re.sub(r'identical to (?:the )?(?:Turkish and )?English \'m\'', "identical to English 'm'", s, flags=re.I)
    s = re.sub(r'identical to standard Turkish \'n\'', "identical to English 'n'", s, flags=re.I)
    s = re.sub(r'(?:exactly )?like (?:the )?Turkish \'k\'', "like English 'k' in 'skip'", s, flags=re.I)
    s = re.sub(r'pure Turkish \'k\' \[[^\]]+\]', "hard 'k' sound [k] as in English 'skip'", s, flags=re.I)
    s = re.sub(r'(?:pronounced )?(?:exactly |similarly )?like the Turkish (?:sound |letter )?(?:combination |sequence )?\'ny\'(?: \([^\)]+\))?', "like 'ny' in English 'canyon'", s, flags=re.I)
    s = re.sub(r'similar to \'ny\' in Turkish \([^\)]+\)', "like 'ny' in English 'canyon'", s, flags=re.I)
    s = re.sub(r'the Turkish \'ny\' combination in \'banyo\'', "'ny' in English 'canyon'", s, flags=re.I)
    s = re.sub(r'or the Turkish \'n\' followed smoothly by \'y\'', "or 'ni' in 'onion'", s, flags=re.I)
    s = re.sub(r'like (?:a raspy|the) Turkish (?:gırtlaksı sert )?\'h\'', "like guttural 'ch' in Scottish 'loch' [x]", s, flags=re.I)
    s = re.sub(r'like Turkish gırtlaksı sert \'h\'', "like guttural 'ch' in Scottish 'loch' [x]", s, flags=re.I)

    # 4. Grammar clauses and pedagogical references:
    if not is_vocab_nationality:
        s = re.sub(r',? but for Turkish speakers[^\.\,\;]*', "", s, flags=re.I)
        s = re.sub(r'with correct pronunciation for Turkish speakers', "with clear pronunciation guidelines", s, flags=re.I)
        s = re.sub(r'\(identical to Turkish verb conjugation\)', "(since Spanish verb conjugation clearly identifies the subject)", s, flags=re.I)
        s = re.sub(r'exactly like Turkish personal suffixes', "as verb conjugation clearly marks the person", s, flags=re.I)
        s = re.sub(r'or Turkish \'Efendim\?\'', "", s, flags=re.I)
        s = re.sub(r'Unlike Turkish \'[^\']+\' [^\,\.]*\,', "Note that", s, flags=re.I)
        s = re.sub(r'Turkish (?:speakers|learners) often (?:wrongly |mistakenly )?omit', "Beginner learners often omit", s, flags=re.I)
        s = re.sub(r'Turkish (?:speakers|learners) often wrongly conjugate', "Beginner learners often wrongly conjugate", s, flags=re.I)
        s = re.sub(r'In Turkish, both \'[^\']+\' and \'[^\']+\' correspond[^\.]*\.', "", s, flags=re.I)
        s = re.sub(r'Turkish speakers have a major natural advantage:[^\.]*\.', "", s, flags=re.I)
        s = re.sub(r'or the planned future tense \(\'\-ecek \/ \-acak\'\) in Turkish', "", s, flags=re.I)
        s = re.sub(r'from English or Turkish!', "literally from your native language!", s, flags=re.I)
        s = re.sub(r'vs\.\s*Turkish Ek-eylem', "", s, flags=re.I)
        s = re.sub(r'where English and Turkish use adjectives[^\.]*\.', "where English uses adjectives.", s, flags=re.I)
        s = re.sub(r'\(Turkish \'\-de\/\-da\' eki\)', "", s, flags=re.I)
        s = re.sub(r'and Turkish \(onun vs onların\)', "", s, flags=re.I)
        s = re.sub(r'CRITICAL TRAP F SPEAKERS: Turkish uses locative case suffixes[^\.]*\.', "CRITICAL PREPOSITION TRAP: Always use the proper linking preposition.", s, flags=re.I)

    s = re.sub(r'\s{2,}', ' ', s)
    s = re.sub(r'\s+([\,\.\;\:])', r'\1', s)
    s = re.sub(r'\(\s*\)', '', s)
    return s.strip()

def _sanitize_turkish_content(s: str) -> str:
    """Post-generation cleanup for Turkish pedagogical fields.
    Removes robotic AI artifacts: parenthetical glosses, gender hacks, tense calques,
    ungradable 'çok', food article calques, body-part 'sahiptir'.
    """
    if not isinstance(s, str) or not s.strip():
        return s

    # 1. Remove parenthetical origin glosses: (Meksika'dan), (e sahiptir), vb.
    s = re.sub(
        r"\s*\([A-Za-z\u00C0-\u024F\s''\-\u2013]+(?:['']dan|['']den|dan|den|ten|tan|e sahiptir|a sahiptir)\)",
        "", s
    )
    # Catch English parenthetical glosses in TR field e.g. (thirty-one days)
    s = re.sub(r"\s*\(\s*(?:thirty|forty|fifty|sixty|one|two|three|has|with)\s[^)]{1,40}\)", "", s, flags=re.I)

    # 2. Remove clumsy gender hacks: '; o bir Meksikali kadindir.' or standalone at end
    # Also handle with ASCII-transliterated Turkish chars (test data has them)
    s = re.sub(r"[;,]?\s*o\s+bir\s+\S+\s+(?:kadındır|erkektir|kadindir|erkektir)\.?", ".", s)
    s = re.sub(r"\s+o\s+bir\s+\S+\s+(?:kadındır|erkektir|kadindir|erkektir)\.?", ".", s)
    # Strip trailing semicolons left after removal
    s = re.sub(r";\s*\.", ".", s)

    # 3. Fix ungradable adjectives with 'çok'
    s = re.sub(r"(?i)\bçok\s+devasa\b", "devasa", s)
    s = re.sub(r"(?i)\bçok\s+muazzam\b", "muazzam", s)
    s = re.sub(r"(?i)\bçok\s+mükemmel\b", "mükemmel", s)
    s = re.sub(r"(?i)\bçok\s+benzersiz\b", "benzersiz", s)
    s = re.sub(r"(?i)\bçok\s+eşsiz\b", "eşsiz", s)

    # 4. Tense calque: polite ordering formula
    s = re.sub(r"(?i)\brica\s+ediyordum\b", "rica ediyorum", s)

    # 5. Literal 'bir kızarmış ekmek'
    s = re.sub(r"(?i)\bbir\s+kızarmış\s+ekmek\b", "kızarmış ekmek", s)

    # 6. Body-part possession 'sahiptir' -> predicate adjective
    # Use lambda to build replacement with matched group
    def _eye_repl(m):
        return m.group(1) + " gözlüdür"
    s = re.sub(r"(?i)\b(yeşil|mavi|kahverengi|ela|kara|lacivert)\s+gözlere\s+sahiptir\b", _eye_repl, s)

    def _hair_repl(m):
        return m.group(1) + " saçlıdır"
    s = re.sub(r"(?i)\b(kıvırcık|düz|dalgalı|uzun|kısa|siyah|sarı|kumral|kızıl|gri)\s+saçlara\s+sahiptir\b", _hair_repl, s)

    # 7. Calendar parenthetical 'sahiptir' glosses
    s = re.sub(r"\(otuz\s+bir\s+güne\s+sahiptir\)", "", s, flags=re.I)
    s = re.sub(r"\(yirmi\s+sekiz(?:\s+veya\s+yirmi\s+dokuz)?\s+güne\s+sahiptir\)", "", s, flags=re.I)
    s = re.sub(r"\(otuz\s+güne\s+sahiptir\)", "", s, flags=re.I)

    # 8. Punctuation cleanup
    s = re.sub(r"\s*\.\s*\.", ".", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    if s.endswith(";"):
        s = s[:-1].strip() + "."

    return s


def _sanitize_deep_bilingual(obj):
    """Recursively applies universal_sanitize_english to English fields and
    _sanitize_turkish_content to Turkish (_tr) fields."""
    if isinstance(obj, dict):
        new_d = {}
        for k, v in obj.items():
            if k.endswith('_tr') and isinstance(v, str):
                new_d[k] = _sanitize_turkish_content(v)
            elif not k.endswith('_tr') and isinstance(v, str):
                new_d[k] = universal_sanitize_english(v)
            else:
                new_d[k] = _sanitize_deep_bilingual(v)
        return new_d
    elif isinstance(obj, list):
        return [_sanitize_deep_bilingual(x) for x in obj]
    return obj

def _normalize_lesson_pages(data, topic, language, level):
    """Ensures lesson dictionary conforms strictly to {"pages": [...]} format, normalizing flexible AI output."""
    if isinstance(data, dict) and isinstance(data.get("pages"), list) and len(data["pages"]) > 0:
        for p in data["pages"]:
            if not isinstance(p, dict):
                continue
            # Flatten nested "content" dict if Luna wraps properties inside it
            if isinstance(p.get("content"), dict):
                c_dict = p.pop("content")
                for ck, cv in c_dict.items():
                    if ck not in p:
                        p[ck] = cv
            # Normalize overview list of objects into text
            if "overview" in p and "text" not in p:
                ov = p.pop("overview")
                if isinstance(ov, list):
                    p["text"] = "\n".join(f"• {x.get('text', '') if isinstance(x, dict) else str(x)}" for x in ov)
                else:
                    p["text"] = str(ov)
            # Normalize dialogues / dialogue
            if "dialogues" in p and "dialogue" not in p:
                p["dialogue"] = p.pop("dialogues")
            if isinstance(p.get("dialogue"), list) and len(p["dialogue"]) > 0 and isinstance(p["dialogue"][0], dict) and "dialogue" in p["dialogue"][0]:
                flat_turns = []
                for scen in p["dialogue"]:
                    if isinstance(scen, dict):
                        scen_ctx = scen.get("context", "")
                        if scen_ctx and not p.get("context"):
                            p["context"] = scen_ctx
                        for turn in scen.get("dialogue", []):
                            if isinstance(turn, dict):
                                flat_turns.append(turn)
                p["dialogue"] = flat_turns
            # Normalize teacher_pitfalls into pitfall string
            if "teacher_pitfalls" in p and "pitfall" not in p:
                tp = p.pop("teacher_pitfalls")
                p["pitfall"] = ("• " + "\n• ".join(tp)) if isinstance(tp, list) else str(tp)
            # Normalize activities into formative assessment mcq
            if "activities" in p and "prompt" not in p:
                acts = p.pop("activities")
                if acts and isinstance(acts, list) and isinstance(acts[0], dict):
                    p["prompt"] = acts[0].get("prompt", "")
                    p["options"] = acts[0].get("options", [])
                    p["distractors"] = acts[0].get("distractors", [])
                    p["answer"] = acts[0].get("answer", "")
                    p["explanation"] = acts[0].get("explanation", "")
            # Normalize list text into formatted bullet string
            if isinstance(p.get("text"), list):
                p["text"] = "\n".join(f"• {x.get('text', '') if isinstance(x, dict) else str(x)}" for x in p["text"])
            # Deduce or correct page type based on actual contents
            if p.get("items") or p.get("vocabulary"):
                p["type"] = "vocabulary"
            elif p.get("rules") or p.get("grammar"):
                p["type"] = "grammar"
            elif p.get("dialogue") or p.get("conversations"):
                p["type"] = "examples"
            elif p.get("prompt") or p.get("options") or p.get("distractors"):
                p["type"] = "mcq"
            elif not p.get("type") or p.get("type") in ["custom", "lesson"]:
                p["type"] = "overview"

            # Synchronize MCQ options and distractors so both are always fully available
            if p.get("type") == "mcq" or p.get("prompt"):
                p["type"] = "mcq"
                ans = str(p.get("answer", "")).strip()
                opts = p.get("options")
                distrs = p.get("distractors")
                if opts and isinstance(opts, list) and len(opts) > 1:
                    clean_opts = [str(o).strip() for o in opts if str(o).strip()]
                    p["options"] = clean_opts
                    if not distrs or not isinstance(distrs, list) or len(distrs) == 0:
                        p["distractors"] = [o for o in clean_opts if o != ans]
                    if not ans and clean_opts:
                        ans = clean_opts[0]
                        p["answer"] = ans
                elif distrs and isinstance(distrs, list) and len(distrs) > 0:
                    clean_distrs = [str(d).strip() for d in distrs if str(d).strip()]
                    p["distractors"] = clean_distrs
                    if ans and ans not in clean_distrs:
                        p["options"] = [ans] + clean_distrs
                    else:
                        p["options"] = clean_distrs

            # Preserve authentic descriptive title if present, otherwise assign a clean title
            p_type = p.get("type", "")
            raw_title = str(p.get("title", "")).strip()
            if not raw_title or raw_title.lower() in ["untitled", "slide", "page", "custom", "overview"]:
                if p_type == "overview":
                    p["title"] = "1. Conceptual Foundations"
                elif p_type == "vocabulary":
                    p["title"] = "2. Core Vocabulary & Forms"
                elif p_type == "grammar":
                    p["title"] = "3. Structural Architecture & Rules"
                elif p_type in ["examples", "dialogue"]:
                    p["title"] = "4. Real-World Situational Dialogue"
                elif p_type == "mcq":
                    p["title"] = "5. Formative Quick-Check"
            else:
                p["title"] = raw_title

            # Preserve authentic descriptive Turkish title if present, otherwise assign a clean title
            raw_title_tr = str(p.get("title_tr", "")).strip()
            if not raw_title_tr or raw_title_tr.lower() in ["untitled", "slide", "page", "custom", "overview"]:
                if p_type == "overview":
                    p["title_tr"] = "1. Kavramsal Temeller"
                elif p_type == "vocabulary":
                    p["title_tr"] = "2. Temel Kelimeler ve Yapılar"
                elif p_type == "grammar":
                    p["title_tr"] = "3. Yapısal Kurallar"
                elif p_type in ["examples", "dialogue"]:
                    p["title_tr"] = "4. Gerçek Yaşam Diyaloğu"
                elif p_type == "mcq":
                    p["title_tr"] = "5. Hızlı Değerlendirme"
            else:
                p["title_tr"] = raw_title_tr

            # Ensure vocabulary items have well-formed fields including bilingual pairs
            if "items" in p and isinstance(p["items"], list):
                clean_items = []
                for it in p["items"]:
                    if isinstance(it, dict):
                        clean_items.append({
                            "term": it.get("term") or it.get("word") or "",
                            "phonetic": it.get("phonetic") or "",
                            "translation": it.get("translation") or it.get("meaning") or it.get("english") or "",
                            "translation_tr": it.get("translation_tr") or "",
                            "example": it.get("example") or "",
                            "example_en": it.get("example_en") or it.get("translation_example") or "",
                            "example_tr": it.get("example_tr") or "",
                            "explanation": it.get("explanation") or it.get("tip") or "",
                            "explanation_tr": it.get("explanation_tr") or ""
                        })
                p["items"] = clean_items

            # Ensure comparisons is always a list of well-formed objects with bilingual support
            if "comparisons" in p and isinstance(p["comparisons"], list):
                norm_comps = []
                for c in p["comparisons"]:
                    if isinstance(c, dict):
                        norm_comps.append({
                            "context": c.get("context") or "Register & Nuance Contrast",
                            "context_tr": c.get("context_tr") or "Kullanım ve Anlam Karşılaştırması",
                            "target": c.get("target") or c.get("sentence") or c.get("text") or "",
                            "translation": c.get("translation") or c.get("meaning") or "",
                            "translation_tr": c.get("translation_tr") or "",
                            "note": c.get("note") or c.get("explanation") or "",
                            "note_tr": c.get("note_tr") or ""
                        })
                    elif isinstance(c, str) and c.strip():
                        parts = c.split("=")
                        if len(parts) >= 2:
                            norm_comps.append({
                                "context": "Register & Nuance Contrast",
                                "context_tr": "Kullanım ve Anlam Karşılaştırması",
                                "target": parts[0].strip().strip("'\""),
                                "translation": "",
                                "translation_tr": "",
                                "note": parts[1].strip().strip("'\""),
                                "note_tr": ""
                            })
                        else:
                            norm_comps.append({
                                "context": "Register & Nuance Contrast",
                                "context_tr": "Kullanım ve Anlam Karşılaştırması",
                                "target": c.strip().strip("'\""),
                                "translation": "",
                                "translation_tr": "",
                                "note": "",
                                "note_tr": ""
                            })
                p["comparisons"] = norm_comps

            # Ensure grammar rules have distinct, meaningful titles and explanations
            if "rules" in p and isinstance(p["rules"], list):
                for r_idx, r in enumerate(p["rules"]):
                    if isinstance(r, dict):
                        r_rule = str(r.get("rule", "")).strip()
                        if not r_rule or len(r_rule) < 3:
                            r["rule"] = f"Grammar Principle {r_idx + 1}"
                        if not r.get("explanation"):
                            r_ex = r.get("example") or r.get("target") or ""
                            if r_ex:
                                r["explanation"] = f"Key grammatical pattern illustrated by '{r_ex}'."
                            elif r_rule:
                                r["explanation"] = f"Focus on understanding the structural role of {r_rule}."
                            else:
                                r["explanation"] = "Examine the grammatical structure and sentence pattern."
                        if "rule_tr" in r:
                            r["rule_tr"] = str(r["rule_tr"]).strip()
                        if "explanation_tr" in r:
                            r["explanation_tr"] = str(r["explanation_tr"]).strip()
                        if "example_tr" in r:
                            r["example_tr"] = str(r["example_tr"]).strip()
                        if "analysis_tr" in r:
                            r["analysis_tr"] = str(r["analysis_tr"]).strip()

            # Ensure dialogue preserves translations
            if "dialogue" in p and isinstance(p["dialogue"], list):
                for d in p["dialogue"]:
                    if isinstance(d, dict):
                        if not d.get("line_en") and d.get("translation"):
                            d["line_en"] = d.get("translation")
                        if not d.get("line_tr") and d.get("translation_tr"):
                            d["line_tr"] = d.get("translation_tr")

            # Ensure MCQ preserves bilingual prompt and explanation
            if p.get("type") == "mcq" or p.get("prompt"):
                if "prompt_en" in p:
                    p["prompt_en"] = str(p["prompt_en"]).strip()
                if "prompt_tr" in p:
                    p["prompt_tr"] = str(p["prompt_tr"]).strip()
                if "explanation_tr" in p:
                    p["explanation_tr"] = str(p["explanation_tr"]).strip()

        return _sanitize_deep_bilingual(data)

    if not isinstance(data, dict) or "error_details" in data or not data:
        return {"pages": []}

    # Only construct fallback pages if there is genuine educational content
    has_content = any(k in data for k in ["vocabulary", "items", "words", "grammar_rules", "rules", "dialogue", "conversations", "mcq", "assessment", "question"])
    if not has_content:
        return {"pages": []}

    pages = []
    # 1. Overview page
    overview_text = data.get("cefr_can_do") or data.get("overview") or data.get("description") or f"Comprehensive guide to {topic} in {language} for {level} learners."
    pages.append({
        "type": "overview",
        "title": data.get("title") or f"{topic} Overview",
        "title_tr": data.get("title_tr") or f"{topic} Genel Bakış",
        "text": overview_text,
        "text_tr": data.get("text_tr") or data.get("overview_tr") or ""
    })

    # 2. Vocabulary page
    vocab_items = data.get("vocabulary") or data.get("items") or data.get("words") or []
    if vocab_items:
        clean_items = []
        for v in vocab_items:
            if isinstance(v, dict):
                clean_items.append({
                    "term": v.get("term") or v.get("word") or "",
                    "phonetic": v.get("phonetic") or "",
                    "translation": v.get("translation") or v.get("meaning") or "",
                    "translation_tr": v.get("translation_tr") or "",
                    "example": v.get("example") or "",
                    "example_en": v.get("example_en") or v.get("translation_example") or "",
                    "example_tr": v.get("example_tr") or "",
                    "explanation": v.get("explanation") or v.get("tip") or "",
                    "explanation_tr": v.get("explanation_tr") or ""
                })
        if clean_items:
            pages.append({
                "type": "vocabulary",
                "title": f"Essential Vocabulary: {topic}",
                "title_tr": f"Temel Kelimeler: {topic}",
                "items": clean_items
            })

    # 3. Grammar page
    rules = data.get("grammar_rules") or data.get("rules") or []
    comparisons = data.get("grammar_contrast_pairs") or data.get("comparisons") or []
    pitfall = data.get("teachers_warning") or data.get("pitfall") or ""
    pitfall_tr = data.get("teachers_warning_tr") or data.get("pitfall_tr") or ""
    if rules or comparisons or pitfall:
        clean_rules = []
        for r in rules:
            if isinstance(r, dict):
                clean_rules.append({
                    "rule": r.get("rule") or r.get("title") or "",
                    "rule_tr": r.get("rule_tr") or "",
                    "explanation": r.get("explanation") or "",
                    "explanation_tr": r.get("explanation_tr") or "",
                    "example": r.get("example") or "",
                    "example_en": r.get("example_en") or "",
                    "example_tr": r.get("example_tr") or "",
                    "analysis": r.get("analysis") or "",
                    "analysis_tr": r.get("analysis_tr") or ""
                })
        pages.append({
            "type": "grammar",
            "title": f"Grammar Mechanics: {topic}",
            "title_tr": f"Dilbilgisi Kuralları: {topic}",
            "text": "• Core grammatical rules and usage patterns.",
            "text_tr": "• Temel dilbilgisi kuralları ve kullanım kalıpları.",
            "rules": clean_rules,
            "comparisons": comparisons if isinstance(comparisons, list) else [],
            "pitfall": pitfall,
            "pitfall_tr": pitfall_tr
        })

    # 4. Situational Dialogue page
    dialogue = data.get("dialogue") or data.get("conversations") or []
    if dialogue:
        clean_diag = []
        for d in dialogue:
            if isinstance(d, dict):
                clean_diag.append({
                    "speaker": d.get("speaker") or "Speaker",
                    "text": d.get("text") or d.get("line") or "",
                    "line_en": d.get("line_en") or d.get("translation") or "",
                    "line_tr": d.get("line_tr") or d.get("translation_tr") or ""
                })
        if clean_diag:
            pages.append({
                "type": "examples",
                "title": "Situational Dialogue",
                "title_tr": "Durumsal Diyalog",
                "context": data.get("context") or f"Authentic communicative context for {topic}.",
                "context_tr": data.get("context_tr") or "",
                "dialogue": clean_diag
            })

    # 5. Formative Assessment / MCQ page
    mcq = data.get("mcq") or data.get("assessment") or data.get("question")
    if isinstance(mcq, dict):
        ans = str(mcq.get("answer", "")).strip()
        opts = mcq.get("options") or []
        distrs = mcq.get("distractors") or []
        if opts and not distrs:
            distrs = [o for o in opts if o != ans]
        elif distrs and not opts:
            opts = ([ans] if ans else []) + distrs
        pages.append({
            "type": "mcq",
            "title": mcq.get("title") or "Formative Assessment",
            "title_tr": mcq.get("title_tr") or "Hızlı Değerlendirme",
            "prompt": mcq.get("prompt") or mcq.get("question") or "",
            "prompt_en": mcq.get("prompt_en") or "",
            "prompt_tr": mcq.get("prompt_tr") or "",
            "options": opts,
            "distractors": distrs,
            "answer": ans,
            "explanation": mcq.get("explanation") or "",
            "explanation_tr": mcq.get("explanation_tr") or ""
        })

    return _sanitize_deep_bilingual({"pages": pages})

def translate_lesson_to_turkish(lesson_dict, language="Spanish"):
    """
    Surgically extracts English pedagogical strings from a lesson dictionary,
    translates them in a single fast call to DeepSeek V4 Flash (0.4s),
    and injects the Turkish translations back into the lesson dictionary.
    Target language text (Spanish, German, etc.), IPA phonetics, and codes are never altered.
    """
    if not lesson_dict or not isinstance(lesson_dict, dict) or not lesson_dict.get("pages"):
        return lesson_dict

    # 1. Surgical string extraction
    ref_map = []  # list of (path_in_dict, text)
    for p_idx, page in enumerate(lesson_dict.get("pages", [])):
        if page.get("title"):
            ref_map.append((f"pages.{p_idx}.title_tr", page["title"]))
        if page.get("text"):
            ref_map.append((f"pages.{p_idx}.text_tr", page["text"]))
        if page.get("context"):
            ref_map.append((f"pages.{p_idx}.context_tr", page["context"]))
        if page.get("pitfall"):
            ref_map.append((f"pages.{p_idx}.pitfall_tr", page["pitfall"]))
        if page.get("prompt"):
            ref_map.append((f"pages.{p_idx}.prompt_tr", page["prompt"]))
        if page.get("explanation"):
            ref_map.append((f"pages.{p_idx}.explanation_tr", page["explanation"]))
        
        # Items / Vocabulary
        for i_idx, item in enumerate(page.get("items", [])):
            if isinstance(item, dict):
                item_trans = item.get("translation") or item.get("meaning") or item.get("english")
                if item_trans and not item.get("translation_tr"):
                    ref_map.append((f"pages.{p_idx}.items.{i_idx}.translation_tr", item_trans))
                item_ex_en = item.get("example_en") or item.get("sentence_en")
                if item_ex_en and not item.get("example_tr"):
                    ref_map.append((f"pages.{p_idx}.items.{i_idx}.example_tr", item_ex_en))
                if item.get("explanation") and not item.get("explanation_tr"):
                    ref_map.append((f"pages.{p_idx}.items.{i_idx}.explanation_tr", item["explanation"]))
                if item.get("phonetic") and not item.get("phonetic_tr"):
                    ref_map.append((f"pages.{p_idx}.items.{i_idx}.phonetic_tr", item["phonetic"]))
                
        # Rules
        for r_idx, rule in enumerate(page.get("rules", [])):
            if isinstance(rule, dict):
                if rule.get("rule") and not rule.get("rule_tr"):
                    ref_map.append((f"pages.{p_idx}.rules.{r_idx}.rule_tr", rule["rule"]))
                if rule.get("explanation") and not rule.get("explanation_tr"):
                    ref_map.append((f"pages.{p_idx}.rules.{r_idx}.explanation_tr", rule["explanation"]))
                rule_ex_en = rule.get("example_en") or rule.get("sentence_en")
                if rule_ex_en and not rule.get("example_tr"):
                    ref_map.append((f"pages.{p_idx}.rules.{r_idx}.example_tr", rule_ex_en))
                if rule.get("analysis") and not rule.get("analysis_tr"):
                    ref_map.append((f"pages.{p_idx}.rules.{r_idx}.analysis_tr", rule["analysis"]))
                
        # Comparisons
        for c_idx, comp in enumerate(page.get("comparisons", [])):
            if isinstance(comp, dict):
                if comp.get("context"):
                    ref_map.append((f"pages.{p_idx}.comparisons.{c_idx}.context_tr", comp["context"]))
                if comp.get("translation"):
                    ref_map.append((f"pages.{p_idx}.comparisons.{c_idx}.translation_tr", comp["translation"]))
                if comp.get("note"):
                    ref_map.append((f"pages.{p_idx}.comparisons.{c_idx}.note_tr", comp["note"]))
            elif isinstance(comp, str) and comp.strip():
                ref_map.append((f"pages.{p_idx}.comparisons.{c_idx}", comp))
                
        # Dialogue
        for d_idx, d in enumerate(page.get("dialogue", [])):
            if isinstance(d, dict) and d.get("line_en"):
                ref_map.append((f"pages.{p_idx}.dialogue.{d_idx}.line_tr", d["line_en"]))

    if not ref_map:
        return lesson_dict

    input_dict = {str(i): text for i, (_, text) in enumerate(ref_map)}

    # 2. Batch Translation in chunks of 20 items to prevent token truncation
    system_ds = (
        f"You are an expert pedagogical translator and linguist for adult {language} learners.\n"
        "Translate each English educational phrase into natural, fluent, professional academic Turkish.\n"
        "CRITICAL TERMINOLOGY & LOCALIZATION RULES:\n"
        "1. Strict zero-calque: Translate meaning and pedagogical intent naturally, never word-for-word.\n"
        "2. REGISTER & PROFESSIONAL CONTEXT (CRITICAL): When you encounter references to 'business English', 'in business contexts', 'corporate register', or workplace settings, NEVER translate literally as 'iş İngilizcesi'. Always translate idiomatically in context as 'kurumsal dilde', 'meslek hayatında', 'iş dünyasında' or 'profesyonel iletişimde'.\n"
        "3. Natural Turkish grammar terminology: 'koşul kipi', 'istek kipi', 'geçmiş zaman', 'özne zamiri', 'dönüşlü fiil', 'mastar fiil', 'nesne zamiri'.\n"
        "4. Preserve all foreign terms (e.g. {language} words in quotes or italics) and IPA brackets exactly as they are.\n"
        "5. TURKISH PHONETICS (CRITICAL): In Spanish (or any target language) phonetics, NEVER translate Castilian [th] sound as '[th]' or refer to 'th'. In Turkish language education, Castilian 'c' (before e/i) and 'z' [θ] sound is strictly known and taught as 'peltek s'. Always translate [th] to 'peltek s' (veya 'peltek s [θ]').\n"
        "6. NATURAL PEDAGOGICAL NARRATIVE: In communicative settings and scene descriptions, write natural, engaging educational Turkish. Avoid stiff, robot-like machine translation.\n"
        "7. STRICT ANTI-PATTERNS (ZERO TOLERANCE):\n"
        "   - NEVER add parenthetical origin or country glosses e.g. (Meksika'dan), (İspanya'dan).\n"
        "   - NEVER use gender markers like 'kadındır' or 'erkektir' for nationalities or identities (Turkish is gender-neutral).\n"
        "   - NEVER translate ordering speech acts using past continuous e.g. 'rica ediyordum' or 'istiyordum' (use 'rica ediyorum' or 'alabilir miyim').\n"
        "   - NEVER use 'sahiptir' for personal/physical possession (use 'var' or adjective suffixes like 'yeşil gözlüdür').\n"
        "   - NEVER use 'çok' with ungradable adjectives ('çok devasa' -> 'devasa').\n"
        "   - NEVER add indefinite articles before food items in ordering phrases ('bir kızarmış ekmek' -> 'kızarmış ekmek').\n"
        "8. CAPITALIZATION: Always ensure every translated bullet point, rule, and explanatory sentence begins with a capitalized letter.\n"
        "9. Return ONLY valid JSON mapping the string index to the translated Turkish string: {{\"0\": \"...\", \"1\": \"...\"}}"
    )

    translations = {}
    chunk_size = 20
    for chunk_start in range(0, len(ref_map), chunk_size):
        chunk = ref_map[chunk_start:chunk_start + chunk_size]
        input_dict = {str(chunk_start + i): text for i, (_, text) in enumerate(chunk)}
        user_ds = f"Translate these educational phrases into Turkish:\n{json.dumps(input_dict, ensure_ascii=False)}"
        try:
            batch_res = _call_ai(
                [{"role": "system", "content": system_ds}, {"role": "user", "content": user_ds}],
                model=MODEL_TRANSLATOR,
                max_tokens=4000,
                temperature=0.1,
                json_mode=True
            )
            if isinstance(batch_res, dict):
                translations.update(batch_res)
        except Exception as e:
            print(f"[TRANSLATION] Error for chunk {chunk_start}: {e}")

    # 3. Injection into lesson dictionary
    for i, (path, _) in enumerate(ref_map):
        tr_val = translations.get(str(i), "")
        if not tr_val:
            continue
        tr_val = _sanitize_turkish_content(heal_turkish_syntax(tr_val))
        parts = path.split(".")
        target = lesson_dict
        for part in parts[:-1]:
            if part.isdigit():
                target = target[int(part)]
            else:
                target = target[part]
        if parts[-1].isdigit():
            target[int(parts[-1])] = tr_val
        else:
            target[parts[-1]] = tr_val

    return _sanitize_deep_bilingual(lesson_dict)

def generate_full_lesson(topic, topic_type, language, count=6, level='A1', source_text=None, material_language="tr"):
    """
    Generates a maximum-detail, textbook-quality lesson using Gemini 2.5 Flash.
    No fixed page count — the AI determines the optimal structure based on topic depth.
    Targets all 14 languages and CEFR A1-C2 with level-appropriate pedagogical depth.
    """
    from services.language_data import get_reference_prompt, get_special_chars_prompt, get_pedagogical_guidelines
    from services.cefr_reference import get_cefr_conditioning, LANGUAGE_CEFR_STANDARDS
    lang_std = LANGUAGE_CEFR_STANDARDS.get(language, {})
    official_institution = lang_std.get("institution", f"Council of Europe Official CEFR Framework for {language}")

    is_alphabet_topic = any(x in topic.lower() for x in [
        "alphabet", "alfabeto", "alfabe", "letters", "abecedario", "letra", "harf",
        "pronunciation", "pronunciación", "telaffuz", "vowel", "consonant",
        "vocal", "consonante", "sound", "fonetik", "sesli", "sessiz", "phonetic"
    ])
    is_numbers_topic = any(x in topic.lower() for x in [
        "number", "número", "sayı", "sayılar", "count", "contar", "telling time",
        "hora", "hours", "dates", "fechas", "rakam", "numeral"
    ])
    is_grammar_topic = (topic_type == "grammar") or any(x in topic.lower() for x in [
        "verb", "tense", "conjugat", "grammar", "gramática", "dilbilgisi", "fiil",
        "zaman", "pronoun", "ser", "estar", "haber", "tener", "subjunctive",
        "subyuntivo", "preposition", "article", "article", "adjective", "adverb",
        "clause", "mood", "aspect", "participle", "gerund", "infinitive", "passive",
        "conditional", "imperative", "indicative", "case", "declension", "gender"
    ])
    is_culture_topic = any(x in topic.lower() for x in [
        "culture", "kültür", "cuisine", "food", "tradition", "festival", "history",
        "society", "customs", "politeness", "etiquette", "formality", "register"
    ])

    # Source material if provided
    source_rule = f"\n\nPRIMARY SOURCE MATERIAL (use this as reference):\n{source_text[:8000]}" if source_text else ""

    # Build clean, universal, professor-level prompt with full pedagogical freedom
    system_prompt = f"""<role>You are a distinguished university professor and master pedagogue specializing in {language} language education, authoring authoritative, textbook-quality lessons strictly adhering to the standards of {official_institution} and the Council of Europe CEFR framework for CEFR Level {level} adult learners. You respond ONLY with valid JSON — no markdown fences, no text outside JSON.</role>

<official_authority_directive>
AUTHORITATIVE CURRICULUM MANDATE ({official_institution}):
This lesson must strictly follow the official competency descriptors, lexical inventories, grammar progressions, and communicative milestones established by {official_institution} for CEFR Level {level}.
- Maintain high academic rigor, first-principles explanations, and exhaustive educational depth.
- Never write shallow, brief summaries or placeholder content. Treat every topic with the depth of a university textbook chapter.
</official_authority_directive>

<pedagogical_freedom>
PEDAGOGICAL INITIATIVE & ARCHITECTURE:
As a master professor, you have complete pedagogical freedom and academic initiative over how to structure, format, and teach '{topic}'.
- Decide the optimal combination and number of pages (overview, vocabulary cards, grammar rules, comparisons, authentic dialogues, or formative assessments) that best serve this specific topic.
- Completeness Mandate: If a topic covers a defined structural inventory (such as the complete alphabet/writing system of {language} or a specific number range like 0 to 30), you MUST provide a complete, unbroken, consecutive inventory without skipping any items.
- Teach with engaging, adult, real-life relevance.
</pedagogical_freedom>

<natural_authenticity_mandate>
AUTHENTICITY, NATURAL PROSE & TEXTBOOK QUALITY (TOP PEDAGOGICAL DIRECTIVE):
Every sentence, dialogue utterance, explanation, and translation MUST sound completely natural, organic, lively, and idiomatic—just like a modern published language textbook (e.g., Cambridge University Press, Oxford, Assimil, Instituto Cervantes).
1. STRICT BAN ON MECHANICAL / ROBOTIC SENTENCES:
   - Forbid stiff, formulaic clichés (e.g. NEVER generate sterile robotic tropes like "The entity possesses an apple", "The boy goes to the store", "He speaks with aptitude").
   - Every single example sentence must be authentic, situational, and reflect what real native speakers actually say in daily life.
   - Ground examples in realistic modern scenarios: friendly banter, cafe and restaurant orders, genuine workplace situations, travel dilemmas, spontaneous questions, humor, emotion, and everyday cultural context.
2. NATURAL BILINGUAL VOICING (NO CALQUES, NO LITERAL MACHINE TRANSLATIONS):
   - TURKISH FIELDS ('title_tr', 'text_tr', 'explanation_tr', 'example_tr', 'rule_tr', 'analysis_tr', 'context_tr', 'note_tr', 'pitfall_tr'):
     * Must sound like a warm, articulate, experienced Turkish language teacher speaking directly to adult students.
     * Translations must use natural Turkish syntax and real Turkish idiom.
     * NEVER use unnatural word-for-word translation calques (e.g. NEVER write "Ben bir kitaba sahibim" -> write "Bir kitabım var"; NEVER write "O yapar kahve içmeyi" -> write "Kahve içmeyi sever").
     * Grammatical explanations must be intuitive, vivid, and helpful—never dry, impenetrable linguistics jargon.
   - ENGLISH FIELDS ('title', 'text', 'explanation', 'example_en', 'rule', 'analysis', 'context', 'note', 'pitfall'):
     * Must read as 100% natural, fluent, modern idiomatic English.
3. AUTHENTIC DIALOGUES:
   - Dialogue lines must feel like two living human beings having a real conversation (with natural greetings, reactions, conversational pauses, and authentic tone), not robotic mannequins reading grammar tables aloud.
4. PRACTICAL COMMUNICATIVE VALUE:
   - Prioritize phrases and structures that the student can immediately use when traveling, speaking with friends, or navigating life in a country where {language} is spoken.
</natural_authenticity_mandate>

<anti_patterns_strictly_forbidden>
ZERO TOLERANCE — STRICTLY FORBIDDEN OUTPUT PATTERNS (read every rule and obey without exception):

RULE A — NO FORCED PHONETIC SENTENCES:
When teaching pronunciation (e.g. soft-g 'g', silent-h, j-sound), NEVER pack ALL target sounds artificially into one sentence just to illustrate them.
  ❌ BAD: "El gato de Guillermo es muy gigante." (forces 'g'/'G'/'g' into nonsensical "very giant" context)
  ❌ BAD: "Guillermo's cat is very giant." (ungradable adjective — giants cannot be 'very' giant)
  ❌ BAD: "Guillermo'nun kedisi çok devasa." (ungradable adjective rendered with 'çok')
  ✅ GOOD: "Guillermo tiene un gato gris muy gordo." (natural, gradable adjective, sounds real)
  ✅ GOOD (EN): "Guillermo has a very fat grey cat." (natural)
  ✅ GOOD (TR): "Guillermo'nun çok şişman gri bir kedisi var." (natural Turkish possession)

RULE B — NO PARENTHETICAL METALINGUISTIC GLOSSES IN TURKISH TRANSLATIONS:
Turkish translations must be clean, direct, natural translations — NOT grammar lectures embedded inside parentheses.
  ❌ BAD: "O Meksikalıdır (Meksika'dan); o bir Meksikalı kadındır."
  ❌ BAD: "Ocak ayı otuz bir güne sahiptir (otuz bir çeker)."
  ✅ GOOD: "O Meksikalıdır."
  ✅ GOOD: "Ocak otuz bir gün çeker."
Turkish has NO grammatical gender. NEVER write "kadındır" or "erkektir" to explain a female or male subject's nationality. Turkish nationality adjectives are gender-neutral.
  ❌ BAD: "O bir Meksikalı kadındır." (Turkish has no gender — redundant and wrong)
  ✅ GOOD: "O Meksikalı." or "O, Meksika'dan."

RULE C — NO TENSE CALQUES FOR COMMUNICATIVE SPEECH ACTS:
When the target language uses a conventionalized politeness form (e.g. Spanish imperfect 'quería', 'quisiera'; French conditional 'je voudrais'; German Konjunktiv II 'ich hätte gern'), translate its COMMUNICATIVE FUNCTION into Turkish using the natural Turkish speech-act formula — NOT a literal tense-for-tense calque.
  ❌ BAD: "Günaydın, bir sütlü kahve ve bir kızarmış ekmek rica ediyordum." (past continuous calque of imperfect — unnatural in Turkish ordering)
  ❌ BAD: "Bir kahve istiyordum." (same problem — literal imperfect calque for ordering)
  ✅ GOOD: "Günaydın, bir sütlü kahve ve kızarmış ekmek alabilir miyim?" (natural Turkish ordering formula)
  ✅ GOOD: "Bir kahve rica ediyorum." or "Bir kahve alabilir miyim?" (present or modal — natural)
Also: 'bir kızarmış ekmek' is unnatural — real Turkish says 'kızarmış ekmek' without the article for food items in ordering contexts.

RULE D — NO 'SAHİPTİR' / 'SAHİBİM' FOR POSSESSION (USE VAR/YOK STRUCTURES):
When the target language uses 'tener' (Spanish), 'avoir' (French), 'haben' (German), 'have' (English) to express possession, NEVER translate into Turkish using 'sahiptir', 'sahibim', 'sahipsin', etc. This is an archaic, bureaucratic Turkish calque.
  ❌ BAD: "Bir arabam sahibim." / "Güzel gözlere sahiptir."
  ✅ GOOD: "Bir arabam var." / "Güzel gözleri var."
  ✅ GOOD: "Yeşil gözlüdür." (predicate adjective for eye color is natural)
Exception: 'sahiptir' is acceptable ONLY in formal, bureaucratic, or institutional contexts (e.g., "Bu pozisyon X şartına sahiptir").

RULE E — NO UNNATURAL 'ÇOK' WITH UNGRADABLE ADJECTIVES:
  ❌ BAD: "çok devasa", "çok muazzam", "çok mükemmel", "çok benzersiz", "çok eşsiz"
  ✅ GOOD: "devasa", "muazzam", "mükemmel", "benzersiz", "eşsiz"

RULE F — ENGLISH EXAMPLE SENTENCES MUST BE NATURAL ENGLISH:
  ❌ BAD: "Guillermo's cat is very giant." (not a real English phrase)
  ❌ BAD: "She is from Mexico; she is a Mexican woman." (redundant and mechanical)
  ✅ GOOD: "Guillermo's cat is enormous." / "She's from Mexico — she's Mexican."
</anti_patterns_strictly_forbidden>

<bilingual_pedagogical_tracks>
STRICT TWO-TRACK SEPARATION & PHONOLOGICAL GROUNDING:
You are authoring two completely independent, self-contained pedagogical tracks simultaneously in the exact same output:

TRACK 1 — ENGLISH PEDAGOGICAL TRACK ('title', 'text', 'explanation', 'example_en', 'rule', 'analysis', 'context', 'note', 'pitfall'):
- Target Learner: Native English speaker learning {language}.
- Reference Frame: Explain grammar and pronunciation exclusively from an English-speaker's linguistic perspective, using natural English phonetic anchors and articulatory descriptions.
- Natural Voice: Flowing, idiomatic English textbook prose.
- ABSOLUTE BAN IN ENGLISH TRACK: NEVER mention the Turkish language, Turkish letters, Turkish words, or Turkish phonetics in ANY English field. ZERO references to Turkish. The English track must read as a 100% native English textbook.

TRACK 2 — TURKISH PEDAGOGICAL TRACK ('title_tr', 'text_tr', 'explanation_tr', 'example_tr', 'rule_tr', 'analysis_tr', 'context_tr', 'note_tr', 'pitfall_tr'):
- Target Learner: Native Turkish speaker learning {language}.
- Reference Frame: Explain grammar and pronunciation exclusively from a Turkish-speaker's linguistic perspective, using natural Turkish linguistic and phonetic reference points.
- REGISTER & STYLE: Turkish explanations must be natural, warm, fluent, and professional (avoid stiff machine translation or robot calques).
- ABSOLUTE BAN IN TURKISH TRACK: NEVER compare target sounds to English reference words (e.g. never write "'Father'daki a", "'Cat'teki a").
</bilingual_pedagogical_tracks>
{source_rule}

<output_schema>
Return ONLY valid JSON matching this schema:
{{
  "pages": [
    {{
      "type": "overview" | "vocabulary" | "grammar" | "examples" | "mcq",
      "title": "Page title in English",
      "title_tr": "Page title in Turkish",
      "text": "Detailed pedagogical text in English (for overview/grammar)",
      "text_tr": "Detailed pedagogical text in Turkish (for overview/grammar)",
      "items": [
        {{
          "term": "Word, character, or phrase in {language}",
          "phonetic": "[IPA / phonetic guide]",
          "translation": "English meaning or name",
          "translation_tr": "Turkish meaning or name",
          "example": "Authentic example in {language}",
          "example_en": "English translation",
          "example_tr": "Turkish translation",
          "explanation": "Pronunciation cue or usage note in English",
          "explanation_tr": "Pronunciation cue or usage note in Turkish"
        }}
      ],
      "rules": [
        {{
          "rule": "Grammar rule in English",
          "rule_tr": "Grammar rule in Turkish",
          "explanation": "Pedagogical breakdown in English",
          "explanation_tr": "Pedagogical breakdown in Turkish",
          "example": "Example in {language}",
          "example_en": "English translation",
          "example_tr": "Turkish translation",
          "analysis": "Analysis in English",
          "analysis_tr": "Analysis in Turkish"
        }}
      ],
      "comparisons": [
        {{
          "context": "Contrast context in English",
          "context_tr": "Karşılaştırma bağlamı Türkçe",
          "target": "Structure in {language}",
          "translation": "English contrast",
          "translation_tr": "Turkish contrast",
          "note": "English note",
          "note_tr": "Turkish note"
        }}
      ],
      "dialogue": [
        {{
          "speaker": "Speaker",
          "text": "Utterance in {language}",
          "line_en": "English translation",
          "line_tr": "Turkish translation"
        }}
      ],
      "prompt": "Question in {language}",
      "prompt_en": "Question stem/instruction in English (e.g. 'Complete the sentence:', 'Which sentence is grammatically correct?')",
      "prompt_tr": "Question in Turkish",
      "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
      "answer": "Correct answer",
      "distractors": ["Distractor 1", "Distractor 2", "Distractor 3"],
      "explanation": "Explanation in English",
      "explanation_tr": "Explanation in Turkish"
    }}
  ]
}}
</output_schema>"""

    user_prompt = f"""Generate a complete, exhaustive, textbook-quality {level} {language} lesson on: <topic>{topic} ({topic_type})</topic>

Requirement: Simultaneous bilingual generation (both English and Turkish fields in all pages).
{f'<source_material>{source_text[:6000]}</source_material>' if source_text else ''}

REASONING DIRECTIVE:
In your internal reasoning process, plan the pedagogical arc for this {level} {language} lesson:
1. Target communicative competencies and grammatical structures based on {official_institution} CEFR {level} standards.
2. Structure the pages with complete academic freedom to best teach this topic.
3. Authentic & Natural Phrasing (CRITICAL — check EVERY sentence against anti_patterns_strictly_forbidden):
   - Example sentences: choose realistic, everyday situations; never force multiple sounds into one contrived sentence.
   - Turkish translations: clean and direct. No parenthetical glosses. No gender hacks ('kadındır'/'erkektir'). No 'sahiptir' for possession ('var' instead). No tense calques for ordering ('rica ediyordum' → 'rica ediyorum' / 'alabilir miyim?').
   - English translations: idiomatic modern English only. No "very giant", no mechanical parallel constructions.
4. Strict Two-Track Isolation:
   - English fields: Explain strictly for English speakers. Zero Turkish mentions.
   - Turkish fields: Explain strictly for Turkish speakers. Natural, authentic Turkish. Zero English word comparisons.
5. Completeness: Never skip items in a defined sequence (e.g. alphabets or number ranges).
Then generate the complete, exhaustive JSON lesson structure.

CRITICAL: Do NOT summarize. Do NOT write brief pages. Generate the FULL, DEEP, AUTHENTIC educational content.
Generate as many pages as this topic requires to be covered at the highest textbook quality.
Respond with ONLY the JSON object. No markdown, no prose outside the JSON."""

    lesson_dict = None
    for attempt_idx in range(1, 4):
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-START] '{topic}' ({topic_type}) {level} {language} (attempt {attempt_idx}/3) → {MODEL_LESSON}\n")

        temp = 0.2 if attempt_idx == 1 else (0.25 if attempt_idx == 2 else 0.3)
        raw_dict = _call_ai(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            model=MODEL_LESSON,
            max_tokens=8192,
            temperature=temp,
            json_mode=True,
            allow_fallback=False
        )
        norm_dict = _normalize_lesson_pages(raw_dict, topic, language, level)
        if norm_dict and isinstance(norm_dict, dict) and len(norm_dict.get("pages", [])) >= 3:
            lesson_dict = norm_dict
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-RESULT] '{topic}' → {len(lesson_dict['pages'])} pages on attempt {attempt_idx}\n")
            break
        else:
            page_count = len(norm_dict.get("pages", [])) if isinstance(norm_dict, dict) else 0
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-RETRY] '{topic}' yielded {page_count} pages on attempt {attempt_idx}/3. Retrying same model {MODEL_LESSON}...\n")
            time.sleep(2.0 * attempt_idx)

    if not lesson_dict or not isinstance(lesson_dict, dict) or not lesson_dict.get("pages") or len(lesson_dict.get("pages", [])) < 3:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-ABORT] '{topic}' failed after 3 attempts on {MODEL_LESSON}.\n")
        return {"pages": []}

    # Step 2: Check if native Turkish fields are already present (simultaneous bilingual generation)
    has_turkish = False
    pages = lesson_dict.get("pages", [])
    if pages:
        first_page = pages[0]
        if first_page.get("title_tr") or first_page.get("text_tr"):
            has_turkish = True
        else:
            for p in pages:
                if any(it.get("translation_tr") for it in p.get("items", []) if isinstance(it, dict)):
                    has_turkish = True
                    break

    # Only run secondary translation fallback if Turkish was not provided natively
    if material_language in ["tr", "all"] and not has_turkish:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-TRANSLATE-FALLBACK] '{topic}' lacks native Turkish, running translator...\n")
        lesson_dict = translate_lesson_to_turkish(lesson_dict, language=language)

    return lesson_dict
    

def ai_explain_word(word, language, context=None, material_language="en"):
    instruction_lang_name = "Turkish" if material_language == "tr" else "English"
    system = f"You are a helpful {language} language teacher. Explain terms to students clearly and concisely in {instruction_lang_name}."
    user = f"""Explain the {language} term: '{word}'. 
    CONTEXT: {context}
    
    STRICT RULES:
    1. The 'explanation', 'usage', and 'tip' fields MUST be written in {instruction_lang_name}.
    2. Only the target word itself can be in {language}.
    3. Keep it brief and pedagogical (2-3 sentences max).
    
    Return ONLY valid JSON: {{'explanation': '...', 'usage': '...', 'tip': '...'}}"""
    return _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_STRUCTURAL, max_tokens=500, json_mode=True)

def ai_explain_activity(prompt, correct_answer, student_answer, language, material_language="en"):
    clean_lang = language.split('(')[0].strip()
    instruction_lang_name = "Turkish" if material_language == "tr" else "English"
    system = f"""You are a helpful {clean_lang} language teacher explaining mistakes to students.
CRITICAL LANGUAGE RULES:
1. Your explanation text MUST be written ENTIRELY in {instruction_lang_name}.
2. You may quote specific {clean_lang} words (e.g., the answer or question terms) but ALL explanatory sentences MUST be in {instruction_lang_name}.
3. NEVER write full sentences in {clean_lang}.
4. Keep the explanation concise (2-3 sentences max)."""
    user = f"""A student got a {clean_lang} question wrong. Explain the mistake and the correct logic.

Question: {prompt}
Correct Answer: {correct_answer}
Student's Answer: {student_answer}

Return ONLY valid JSON: {{"explanation": "Your {instruction_lang_name} explanation here"}}"""
    return _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}], model=MODEL_STRUCTURAL, max_tokens=400, json_mode=True)

def _get_blueprint_path(language, level):
    cache_dir = os.path.join("services", "blueprints")
    if not os.path.exists(cache_dir): os.makedirs(cache_dir)
    clean_lang = "".join(filter(str.isalnum, language.split('(')[0])).lower()
    clean_level = "".join(filter(str.isalnum, level)).lower()
    return os.path.join(cache_dir, f"{clean_lang}_{clean_level}.json")

def save_blueprint_cache(language, level, chapters):
    try:
        from services.curriculum_translator import ensure_bilingual_curriculum
        clean_chapters = ensure_bilingual_curriculum(chapters)
        cache_file = _get_blueprint_path(language, level)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"chapters": clean_chapters}, f, ensure_ascii=False, indent=2)
        return True
    except: return False

def delete_blueprint_cache(language, level):
    try:
        cache_file = _get_blueprint_path(language, level)
        if os.path.exists(cache_file): os.remove(cache_file); return True
        return False
    except: return False

def list_blueprint_cache():
    cache_dir = os.path.join("services", "blueprints")
    if not os.path.exists(cache_dir): return []
    return [{"language": f.split('_')[0], "level": f.split('_')[1].replace('.json','')} for f in os.listdir(cache_dir) if f.endswith('.json')]

def heal_turkish_syntax(text: str) -> str:
    if not text or not isinstance(text, str):
        return text

    def repl_concessive(m):
        prefix = m.group(1)
        stem = m.group(2)
        comma = m.group(3) or ''
        return f"{prefix}{stem} olsa da{comma}"

    concessive_pat = r'(?i)\b(her\s+ne\s+kadar\s+(?:.*?\s+)?)([a-zçğıöşüA-ZÇĞİÖŞÜ]+?)(?:y(?:dı|di|du|dü)|dı|di|du|dü|tı|ti|tu|tü)(,)?(?=\s+(?:yine\s+de|ancak|fakat|hâlâ|hala|ama)|\s+[a-zçğıöşüA-ZÇĞİÖŞÜ])'
    text = re.sub(concessive_pat, repl_concessive, text)
    text = re.sub(r'(?i)\b(her\s+ne\s+kadar\s+.*?)\s+olsa(?!\s+da|\s+de)(,)?', r'\1 olsa da\2', text)

    calques = [
        (r'(?i)\bzaman\s+yapmak\b', 'vakit ayırmak'),
        (r'(?i)\bzaman\s+yaptı\b', 'vakit ayırdı'),
        (r'(?i)\bzaman\s+yapıyor\b', 'vakit ayırıyor'),
        (r'(?i)\bzaman\s+yapacağız\b', 'vakit ayıracağız'),
        (r'(?i)\banlam\s+yapmak\b', 'mantıklı gelmek'),
        (r'(?i)\banlam\s+yapmıyor\b', 'mantıklı gelmiyor'),
        (r'(?i)\banlam\s+yapıyor\b', 'mantıklı geliyor'),
        (r'(?i)\bdikkat\s+ödemek\b', 'dikkat etmek'),
        (r'(?i)\bdikkat\s+ödeyin\b', 'dikkat edin'),
        (r'(?i)\bbir\s+bakış\s+almak\b', 'göz atmak'),
        (r'(?i)\bbir\s+duş\s+almak\b', 'duş almak'),
        (r'(?i)\bbanyo\s+almak\b', 'banyo yapmak'),
        (r'(?i)\bbir\s+karar\s+yapmak\b', 'karar vermek'),
        (r'(?i)\bkarar\s+yapmak\b', 'karar vermek'),
        (r'(?i)\biyi\s+öğleden\s+sonralar\b', 'Tünaydın'),
        (r'(?i)\biyi\s+öğleden\s+sonra\b', 'Tünaydın'),
        (r'(?i)\böğleden\s+sonralar\b', 'Tünaydın'),
        # Ordering formula tense calque
        (r'(?i)\brica\s+ediyordum\b', 'rica ediyorum'),
        # Common Turkish calques of physical possession/description
        (r'(?i)\bsaçları\s+var\s+ve\s+gözleri\b', 'saçlı ve gözlü'),  # partial
        # English calques that slip into Turkish
        (r'(?i)\bçok\s+devasa\b', 'devasa'),
        (r'(?i)\bçok\s+muazzam\b', 'muazzam'),
        (r'(?i)\bçok\s+mükemmel\b', 'mükemmel'),
        (r'(?i)\bçok\s+eşsiz\b', 'eşsiz'),
        (r'(?i)\bçok\s+benzersiz\b', 'benzersiz'),
        # Food/item ordering unnatural article
        (r'(?i)\bbir\s+kızarmış\s+ekmek\b', 'kızarmış ekmek')
    ]
    for cp, repl in calques:
        text = re.sub(cp, repl, text)

    def repl_doktor(m):
        suffix = m.group(1)
        if not suffix:
            return 'doktor'
        suffix_lower = suffix.lower()
        suffix_map = {
            'sın': 'sun', 'sin': 'sun',
            'sınız': 'sunuz', 'siniz': 'sunuz',
            'ım': 'um', 'im': 'um',
            'ız': 'uz', 'iz': 'uz',
            'dır': 'dur', 'dir': 'dur',
            'lar': 'lar', 'ler': 'lar',
            'a': 'a', 'e': 'a',
            'dan': 'dan', 'den': 'dan',
            'ı': 'u', 'i': 'u',
            'un': 'un', 'in': 'un'
        }
        return 'doktor' + suffix_map.get(suffix_lower, suffix_lower)

    text = re.sub(r'(?i)\bdoktar(sınız|siniz|sın|sin|ım|im|ız|iz|dır|dir|lar|ler|[a-zçğıöşü]+)?\b', repl_doktor, text)

    # Phonetic normalization: English [th] -> Turkish 'peltek s'
    text = re.sub(r"(?i)\bveya\s+\[th\]('dir|'dır)?", r"veya peltek s [θ]\1", text)
    text = re.sub(r"(?i)\[th\]('dir|'dır|'dur|'dür|dir|dır|dur|dür)", r"peltek s\1", text)
    text = re.sub(r"(?i)\[th\]", r"peltek s [θ]", text)
    text = re.sub(r"(?i)\bth\s+sesi\b", r"peltek s sesi", text)

    # Clean double punctuation (e.g. 'tanımlar.;' -> 'tanımlar.')
    text = re.sub(r'\.\s*;\s*', '. ', text)
    text = re.sub(r';\s*\.\s*', '. ', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()

    # Capitalize first character if lowercase letter
    if text and len(text) > 0 and text[0].islower():
        text = text[0].upper() + text[1:]

    return text
