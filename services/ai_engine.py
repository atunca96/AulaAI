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
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from services.quiz_source_cache import get_content_hash
from services import question_contract as qc
from services.assessment_scope import SCOPE_TOPIC as _SCOPE_TOPIC, SCOPE_UNIT as _SCOPE_UNIT

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

# Output ceiling for one generated lesson, and the ceiling a retry may escalate to
# when the provider reports the previous attempt was cut off at the limit.
#
# The starting value is deliberately unchanged: most lessons finish well inside it
# and must not be charged for headroom they never use. Escalation is conditional on
# an observed truncation, so the extra budget is spent only on the lessons that
# demonstrably could not fit - which today burn three full attempts and then publish
# a review notice, producing no material at all for the same spend.
LESSON_OUTPUT_TOKENS = int(os.getenv("AULAAI_LESSON_OUTPUT_TOKENS", "8192"))
LESSON_OUTPUT_TOKENS_MAX = int(os.getenv("AULAAI_LESSON_OUTPUT_TOKENS_MAX", "24576"))

def _estimate_llm_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimates OpenRouter / API inference cost in USD based on model family and token counts."""
    m = str(model_name or "").lower()
    if any(k in m for k in ["flash-lite", "2.0-flash-lite", "2.5-flash-lite"]):
        inp_rate = 0.075 / 1_000_000
        out_rate = 0.30 / 1_000_000
    elif any(k in m for k in ["gemini-3.7", "gemini-2.5-flash", "gemini-1.5-flash", "flash"]):
        inp_rate = 1.25 / 1_000_000
        out_rate = 5.00 / 1_000_000
    elif any(k in m for k in ["gemini-3-pro", "gemini-1.5-pro", "claude-3-5-sonnet", "gpt-4o"]):
        inp_rate = 3.50 / 1_000_000
        out_rate = 10.50 / 1_000_000
    else:
        inp_rate = 1.00 / 1_000_000
        out_rate = 4.00 / 1_000_000
    return (float(prompt_tokens) * inp_rate) + (float(completion_tokens) * out_rate)

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

_AULAAI_LESSON_CACHE_SESSION_V47 = os.getenv('AULAAI_OPENROUTER_LESSON_SESSION') or ('aulaai-lesson-' + str(os.getpid()) + '-' + uuid.uuid4().hex[:12])

# Spend accounting. Imported under short names so the recording lines inside the
# request loop stay readable, and behind a fallback so a missing ledger can never
# be the reason a class fails to build - cost telemetry is never load-bearing.
try:
    from services.generation_cost import (
        record_call as _cost_record,
        mark_outcome as _cost_mark,
        extract_usage as _cost_extract_usage,
        extract_cache_discount as _cost_extract_discount,
        OUTCOME_OK as _COST_OK,
        OUTCOME_PARSE_FAILED as _COST_PARSE_FAILED,
        OUTCOME_REJECTED as _COST_REJECTED,
        STAGE_LESSON as _COST_STAGE_LESSON,
        STAGE_LESSON_PRIME as _COST_STAGE_PRIME,
        STAGE_CLAIM_REVIEW as _COST_STAGE_CLAIM,
        STAGE_QUESTIONS as _COST_STAGE_QUESTIONS,
        STAGE_CURRICULUM as _COST_STAGE_CURRICULUM,
        STAGE_TRANSLATION as _COST_STAGE_TRANSLATION,
    )
except Exception:  # pragma: no cover - ledger is observational only
    _COST_OK, _COST_PARSE_FAILED, _COST_REJECTED = "ok", "parse_failed", "rejected"
    _COST_STAGE_LESSON, _COST_STAGE_PRIME = "lesson", "lesson_prime"
    _COST_STAGE_CLAIM, _COST_STAGE_QUESTIONS = "claim_review", "questions"
    _COST_STAGE_CURRICULUM, _COST_STAGE_TRANSLATION = "curriculum", "translation"

    def _cost_record(**_kwargs):
        return None

    def _cost_mark(_entry, _outcome):
        return None

    def _cost_extract_usage(_response):
        return None

    def _cost_extract_discount(_response):
        return 0.0

def _cacheable_system_message(message: Dict) -> Dict:
    """Rewrite a system message so OpenRouter will actually cache it on Gemini.

    `session_id` (sent below) is sticky ROUTING ONLY: it pins repeat calls to the
    same upstream replica. It does not create a cache. Every provider OpenRouter
    fronts except Anthropic-style ones treats a plain string `content` as
    nothing to remember - Gemini in particular caches ONLY when the request
    itself marks a block as cacheable with an explicit `cache_control` breakpoint
    inside a content-parts array. A request built as `{"role": "system",
    "content": "<string>"}`, which is what every call in this file sent, carries
    no such breakpoint no matter how consistently `session_id` routes it: there
    was sticky routing to a replica that was never asked to keep anything.

    This turns the system message into the one-part array form OpenRouter's own
    documentation specifies and marks that part `ephemeral`. It is applied only
    to calls whose system prompt is genuinely class-invariant (the lesson call,
    the claim review call) - never blanket, so a call with a small or
    per-request-varying system prompt is untouched.
    """
    content = message.get("content")
    if not isinstance(content, str) or not content:
        return message
    return {
        "role": message.get("role", "system"),
        "content": [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}],
    }


def _call_ai(messages: List[Dict], model: str = MODEL_STRUCTURAL, max_tokens: int = 1000, temperature: float = 0.7, json_mode: bool = True, allow_fallback: bool = True, usage_dict: Optional[Dict[str, Any]] = None, cost_stage: str = "other", cost_subject: str = "", cache_system: bool = False) -> Optional[Dict]:
    """AI caller using OpenRouter exclusively. Gemini models get Google AI Studio BYOK routing for free quota.

    `cost_stage`/`cost_subject` label the call for the spend ledger. They do not
    change the request in any way; they exist because a charge the pipeline
    cannot attribute is a charge nobody can reduce.

    `cache_system` marks the first (system) message as an OpenRouter cache
    breakpoint - see `_cacheable_system_message`. Pass it only when the caller
    knows that system prompt repeats byte-for-byte across many calls in the same
    build; it is never on by default.
    """
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
        payload_messages = messages
        if cache_system and messages and isinstance(messages[0], dict) and messages[0].get("role") == "system":
            payload_messages = [_cacheable_system_message(messages[0])] + list(messages[1:])
        req_payload = {
            "model": target_model,
            "messages": payload_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if target_model == MODEL_LESSON:
            req_payload["session_id"] = _AULAAI_LESSON_CACHE_SESSION_V47
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

            max_attempts = 2 if (model == MODEL_LESSON or max_tokens <= 2500) else 4
            for attempt in range(max_attempts):
                try:
                    # Generous timeout for lesson generation (Gemini can take 60-120s for long outputs)
                    _timeout = 180 if max_tokens > 4000 else (90 if max_tokens > 2000 else 25)
                    with urllib.request.urlopen(req, timeout=_timeout) as response:
                        res_body = response.read().decode("utf-8")
                        res_json = json.loads(res_body)

                        # The provider has already charged for this response. Read
                        # its usage block here, before anything can decide the body
                        # is unusable, so a call that is paid for and thrown away is
                        # counted exactly like one that succeeds. Recording only on
                        # the success path is how retry and truncation waste stayed
                        # invisible: the more a topic failed, the less the books said.
                        _cost_usage = _cost_extract_usage(res_json)
                        _cost_entry = None
                        if _cost_usage:
                            _u_cost = res_json.get("usage", {}).get("cost")
                            _cost_entry = _cost_record(
                                stage=cost_stage,
                                model=target_model,
                                prompt_tokens=_cost_usage["prompt_tokens"],
                                completion_tokens=_cost_usage["completion_tokens"],
                                cached_tokens=_cost_usage["cached_tokens"],
                                cache_write_tokens=_cost_usage["cache_write_tokens"],
                                cache_discount=_cost_extract_discount(res_json),
                                reasoning_tokens=_cost_usage["reasoning_tokens"],
                                cost=float(_u_cost) if _u_cost is not None else _estimate_llm_cost(
                                    target_model,
                                    _cost_usage["prompt_tokens"],
                                    _cost_usage["completion_tokens"],
                                ),
                                outcome=_COST_PARSE_FAILED,
                                attempt=attempt + 1,
                                subject=cost_subject,
                            )
                            if usage_dict is not None and isinstance(usage_dict, dict):
                                # Handed to the caller so a lesson that parses but
                                # fails the release gate can reclassify its own spend.
                                usage_dict["cost_entry"] = _cost_entry

                        if "choices" in res_json and res_json["choices"]:
                            choice = res_json["choices"][0]
                            msg = choice.get("message", {})
                            raw_content = msg.get("content") or ""
                            if not raw_content and "reasoning" in msg and msg["reasoning"]:
                                raw_content = msg["reasoning"]
                            content = str(raw_content).strip()
                            # The provider tells us when it stopped because the ceiling
                            # was reached rather than because the answer was finished.
                            # That signal was previously discarded, so a lesson cut off
                            # mid-structure was indistinguishable from a genuinely short
                            # one: the JSON salvager recovered the complete pages, the
                            # rest was silently lost, and the release gate simply saw too
                            # little content. Surfacing it lets the caller respond to the
                            # actual problem instead of guessing.
                            if usage_dict is not None and isinstance(usage_dict, dict):
                                _reason = str(choice.get("finish_reason") or choice.get("native_finish_reason") or "")
                                usage_dict["finish_reason"] = _reason
                                usage_dict["truncated"] = _reason.strip().lower() in ("length", "max_tokens")
                            if content:
                                with open("pipeline.log", "a", encoding="utf-8") as f:
                                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-OK] {len(content)} chars ← {target_model}\n")

                                data = _extract_and_parse_json(content)
                                if data:
                                    if usage_dict is not None and isinstance(usage_dict, dict):
                                        u_info = res_json.get("usage", {})
                                        p_t = u_info.get("prompt_tokens") or (sum(len(str(m.get("content", ""))) for m in messages) // 4)
                                        c_t = u_info.get("completion_tokens") or (len(content) // 4)
                                        usage_dict["prompt_tokens"] = usage_dict.get("prompt_tokens", 0) + int(p_t)
                                        usage_dict["completion_tokens"] = usage_dict.get("completion_tokens", 0) + int(c_t)
                                        usage_dict["total_tokens"] = usage_dict.get("total_tokens", 0) + int(p_t + c_t)
                                        usage_dict["model"] = target_model
                                        _details = u_info.get("prompt_tokens_details") or {}
                                        _cached = _details.get("cached_tokens") or u_info.get("cached_tokens") or 0
                                        usage_dict["cached_tokens"] = usage_dict.get("cached_tokens", 0) + int(_cached)
                                        if "cost" in u_info and u_info["cost"] is not None:
                                            usage_dict["cost"] = usage_dict.get("cost", 0.0) + float(u_info["cost"])
                                        else:
                                            usage_dict["cost"] = usage_dict.get("cost", 0.0) + _estimate_llm_cost(target_model, int(p_t), int(c_t))
                                    _cost_mark(_cost_entry, _COST_OK)
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


def _is_same_batch_semantic_duplicate(item: dict, final_questions: list, topic_content: Any = None) -> bool:
    """
    Evaluates if candidate item is a semantic near-duplicate of any already-selected question in final_questions,
    or is an ungrounded definitional question for a grammatical/rhetorical/semantic/pragmatic concept.

    Rules enforced:
    1. Semantic near-duplicates: Treat two questions as duplicates when they assess essentially the same target
       through the same pragmatic situation, communicative purpose, expression, reasoning path, or answer distinction,
       even if their wording or format differs.
    2. Reusing learning objectives: Allowed ONLY when the new question genuinely tests a different application, context,
       contrast, or cognitive operation; never include two items that merely paraphrase the same scenario or ask for
       the same expression/function twice.
    3. Concept-definition grounding: For grammatical, rhetorical, semantic, pragmatic, discourse, or literary concepts,
       never synthesize a broad definition from examples or merge neighboring concepts into one another. A definitional
       question may test only properties explicitly supported by source-backed structured metadata. If the source does
       not clearly distinguish the target concept from closely related concepts, reject the definitional question so that
       candidate selection chooses an item assessing recognition or application in a source-supported context instead.
    """
    if not isinstance(item, dict):
        return True

    p = str(item.get("prompt", "")).strip()
    a = str(item.get("answer", "")).strip()
    if not p or not a:
        return True

    clean_a = _normalize_token(a)
    clean_p = _normalize_token(p)
    cand_cog = str(item.get("cognitive_task") or "").strip().lower()
    cand_ev = str(item.get("evidence") or "").strip().lower()
    cand_why = str(item.get("why") or "").strip().lower()
    cand_d = item.get("distractors", [])
    cand_opts = set(_normalize_token(str(x)) for x in ([a] + (cand_d if isinstance(cand_d, list) else [])) if str(x).strip())

    # 1. Surface-Independent Meta-Linguistic, Functional, Attitudinal & Definitional Grounding Check:
    # Any question assessing a meta-linguistic function, essential condition, speaker attitude,
    # grammatical claim, discourse/rhetorical property, or definition—regardless of surface wording—
    # MUST be strictly backed by explicit structured rules or comparisons with source evidence.
    meta_property_patterns = [
        r'\b(?:what is|was ist|qué es|que es|qu\'est-ce que|cos\'è|o que é|nedir|tanımı|definición|definition|définition|definizione)\b',
        r'\b(?:function|función|funcion|işlev|islev|görev|gorev|fonction|funktion|funzione|propósito|purpose|rolle|ruolo)\b',
        r'\b(?:indicate|indica|belirtir|gösterir|express|expresa|ifade eder|signify|significa|drückt aus|bezeichnet|denote)\b',
        r'\b(?:condition|condición|condicion|şart|sart|koşul|kosul|requirement|requisito|voraussetzung)\b',
        r'\b(?:attitude|actitud|tutum|tavır|tavir|stance|postura|haltung)\b',
        r'\b(?:sufijo|terminación|ending|suffix|ekinin|preposición|perífrasis|construcción)\b'
    ]
    asks_meta_property = any(re.search(pat, p, re.IGNORECASE) for pat in meta_property_patterns)
    is_meta_claim = False
    if asks_meta_property:
        form_cue_patterns = [
            r'\b(?:función|funcion|function|işlev|görev|funktion|fonction|funzione)\b',
            r'\b(?:condición|condicion|condition|şart|koşul|requisito|voraussetzung)\b',
            r'\b(?:actitud|attitude|tutum|tavır|stance|postura|haltung)\b',
            r'\b(?:definición|definition|tanımı|nedir|what is|qué es|que es)\b',
            r'\b(?:indica|indicate|indicates|belirtir|gösterir|significa|signify|expresa|express|expresses|drückt aus)\b.*?\b(?:forma|sufijo|terminación|estructura|construcción|marcador|ending|suffix|form|structure|marker|verb|verbo|palabra|word)\b',
            r'\b(?:forma|sufijo|terminación|estructura|construcción|marcador|ending|suffix|form|structure|marker|verb|verbo|palabra|word)\b.*?\b(?:indica|indicate|indicates|belirtir|gösterir|significa|signify|expresa|express|expresses|drückt aus)\b',
            r'\b(?:significado|meaning|bedeutung|anlamı)\b'
        ]
        if any(re.search(pat, p, re.IGNORECASE) for pat in form_cue_patterns) or cand_cog in ["meta_linguistic", "linguistic_discrimination"]:
            is_meta_claim = True

    if is_meta_claim and isinstance(topic_content, dict):
        has_backed_rule = False
        for pg in topic_content.get("pages", []):
            if not isinstance(pg, dict):
                continue
            for r in pg.get("rules", []):
                if isinstance(r, dict) and r.get("source_evidence"):
                    r_name = str(r.get("rule") or r.get("rule_tr") or "").lower()
                    r_expl = str(r.get("explanation") or r.get("explanation_tr") or "").lower()
                    r_tgt = str(r.get("source_taught") or "").lower()
                    if clean_a in r_name or (len(clean_a) >= 4 and clean_a in r_expl) or (len(clean_a) >= 4 and clean_a in r_tgt):
                        has_backed_rule = True
                        break
                    words_in_p = set(re.findall(r'\b[a-záéíóúñäöüßçàèìòùâêîôû]{4,}\b', clean_p))
                    rule_words = set(re.findall(r'\b[a-záéíóúñäöüßçàèìòùâêîôû]{4,}\b', r_name + " " + r_tgt))
                    if words_in_p.intersection(rule_words):
                        has_backed_rule = True
                        break
            if has_backed_rule:
                break
            for c in pg.get("comparisons", []):
                if isinstance(c, dict) and c.get("source_evidence"):
                    c_tgt = str(c.get("target") or "").lower()
                    c_note = str(c.get("note") or c.get("note_tr") or "").lower()
                    c_taught = str(c.get("source_taught") or "").lower()
                    if clean_a in c_tgt or (len(clean_a) >= 4 and clean_a in c_note) or (len(clean_a) >= 4 and clean_a in c_taught):
                        has_backed_rule = True
                        break
                    words_in_p = set(re.findall(r'\b[a-záéíóúñäöüßçàèìòùâêîôû]{4,}\b', clean_p))
                    comp_words = set(re.findall(r'\b[a-záéíóúñäöüßçàèìòùâêîôû]{4,}\b', c_tgt + " " + c_taught))
                    if words_in_p.intersection(comp_words):
                        has_backed_rule = True
                        break
            if has_backed_rule:
                break
        # If not explicitly supported by structured metadata, reject so candidate selection converts to contextual application
        if not has_backed_rule:
            return True

    # 2. In-batch semantic duplicate comparison against selected questions
    gen_stopwords = {
        "cuál", "cual", "opcion", "opción", "correcta", "correcto", "selecciona", "completa",
        "frase", "oracion", "oración", "pregunta", "respuesta", "indica", "mejor", "adecuada",
        "adecuado", "which", "what", "correct", "choose", "select", "complete", "sentence",
        "best", "welche", "welches", "richtig", "richtige", "quelle", "quel", "choisir",
        "quale", "qual", "hangisi", "doğru", "seçiniz", "cümleyi", "uygun", "seçenek"
    }
    cand_words = set(w for w in re.findall(r'\b[a-záéíóúñäöüßçàèìòùâêîôû]{4,}\b', clean_p) if w not in gen_stopwords)

    for f in final_questions:
        if not isinstance(f, dict):
            continue
        f_p = str(f.get("prompt", "")).strip()
        f_a = str(f.get("answer", "")).strip()
        f_clean_a = _normalize_token(f_a)
        f_clean_p = _normalize_token(f_p)
        f_cog = str(f.get("cognitive_task") or "").strip().lower()
        f_ev = str(f.get("evidence") or "").strip().lower()
        f_why = str(f.get("why") or "").strip().lower()
        f_opts = set(_normalize_token(str(x)) for x in f.get("options", []) if str(x).strip())
        f_words = set(w for w in re.findall(r'\b[a-záéíóúñäöüßçàèìòùâêîôû]{4,}\b', f_clean_p) if w not in gen_stopwords)

        # Exact target answer token match
        if f_clean_a and f_clean_a == clean_a:
            return True

        # Standalone expression vs. sentence-embedded expression assessing the same target/expression:
        # Check if one answer contains the other (e.g. 'Buenos días' in 'Buenos días, ¿cómo está usted?')
        if len(clean_a) >= 4 and len(f_clean_a) >= 4:
            if clean_a in f_clean_a or f_clean_a in clean_a:
                # Same cognitive task or source evidence
                if (cand_cog and f_cog and cand_cog == f_cog) or (cand_ev and f_ev and cand_ev == f_ev):
                    return True
                # Overlapping communicative scenario / context words
                if cand_words and f_words and (cand_words.intersection(f_words)):
                    return True
                # Standalone expression vs sentence-embedded frame (short expression <= 4 words)
                if len(clean_a.split()) <= 4 or len(f_clean_a.split()) <= 4:
                    return True
                # Overlapping reasoning or explanation
                if cand_why and f_why and (cand_why in f_why or f_why in cand_why):
                    return True

        # Target expression of one question embedded in the prompt sentence frame of the other
        if len(clean_a) >= 4 and len(clean_a.split()) <= 4 and clean_a in f_clean_p:
            if (cand_words and f_words and cand_words.intersection(f_words)) or (cand_cog and f_cog and cand_cog == f_cog):
                return True
        if len(f_clean_a) >= 4 and len(f_clean_a.split()) <= 4 and f_clean_a in clean_p:
            if (cand_words and f_words and cand_words.intersection(f_words)) or (cand_cog and f_cog and cand_cog == f_cog):
                return True

        # Same answer distinction: identical competing option set
        if cand_opts and f_opts and len(cand_opts) >= 3 and cand_opts == f_opts:
            return True

        # Same learning objective / specific evidence reference:
        # Reusing the same objective is allowed ONLY when genuinely testing a different application, context, contrast, or cognitive operation.
        if cand_ev and f_ev and cand_ev == f_ev:
            if cand_cog == f_cog:
                return True
            if cand_why and f_why and cand_why == f_why:
                return True

        # Same reasoning path on the same cognitive task
        if cand_why and f_why and len(cand_why) > 10 and cand_why == f_why and cand_cog == f_cog:
            return True

    return False


def _extract_source_backed_metadata(topic_content: Any, material_language: str = "en") -> str:
    """
    Extracts only authoritative, source-backed structured metadata (explicit rules, contrasts,
    and verified lexical items) needed by the Form/Function Attribution verifier.
    Excludes unsupported commentary and incidental conversational text.
    """
    if not isinstance(topic_content, dict):
        return ""
    
    sections = []
    
    # 1. Single-topic pages
    if "pages" in topic_content and isinstance(topic_content["pages"], list):
        for idx, page in enumerate(topic_content["pages"], 1):
            p_title = page.get("title", f"Part {idx}")
            lines = [f"--- SECTION {idx}: '{p_title}' ---"]
            
            # Explicit rules
            rules = page.get("rules", [])
            if isinstance(rules, list):
                for r in rules:
                    if isinstance(r, dict):
                        r_name = (r.get("rule_tr") if material_language == "tr" and r.get("rule_tr") else (r.get("rule") or "")).strip()
                        r_expl = (r.get("explanation_tr") if material_language == "tr" and r.get("explanation_tr") else (r.get("explanation") or "")).strip()
                        r_ex = (r.get("example") or "").strip()
                        r_ev = (r.get("source_evidence") or "").strip()
                        if r_name:
                            disp = f"* [RULE] {r_name}"
                            if r_expl: disp += f": {r_expl}"
                            if r_ex: disp += f" — Example: '{r_ex}'"
                            if r_ev: disp += f" [Source Evidence: '{r_ev}']"
                            lines.append(disp)
                            
            # Structural contrasts
            comps = page.get("comparisons", [])
            if isinstance(comps, list):
                for c in comps:
                    if isinstance(c, dict):
                        c_tgt = (c.get("target") or "").strip()
                        c_ctx = (c.get("context_tr") if material_language == "tr" and c.get("context_tr") else (c.get("context") or "")).strip()
                        c_note = (c.get("note_tr") if material_language == "tr" and c.get("note_tr") else (c.get("note") or "")).strip()
                        c_ev = (c.get("source_evidence") or "").strip()
                        if c_tgt:
                            disp = f"* [CONTRAST] '{c_tgt}'" + (f" ({c_ctx})" if c_ctx else "") + (f": {c_note}" if c_note else "")
                            if c_ev: disp += f" [Source Evidence: '{c_ev}']"
                            lines.append(disp)
                            
            # Lexical items
            items = page.get("items", [])
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        term = (it.get("term") or it.get("word") or "").strip()
                        tr = (it.get("translation_tr") if material_language == "tr" and it.get("translation_tr") else (it.get("translation_en") or it.get("translation") or "")).strip()
                        ex = (it.get("example") or "").strip()
                        it_ev = str(it.get("source_evidence") or "").strip()
                        it_prov = str(it.get("provenance") or "").strip().lower()
                        if term:
                            disp = f"* [LEXICON] {term}" + (f" ({tr})" if tr else "")
                            if ex: disp += f" — Example: '{ex}'"
                            if it_ev or it_prov == "source_explicit":
                                expl = (it.get("explanation_tr") if material_language == "tr" and it.get("explanation_tr") else (it.get("explanation_en") or it.get("explanation") or "")).strip()
                                if expl: disp += f" — Note: {expl}"
                                if it_ev: disp += f" [Source Evidence: '{it_ev}']"
                            lines.append(disp)
            if len(lines) > 1:
                sections.append("\n".join(lines))

    # 2. Multi-topic syllabus
    elif "topics" in topic_content and isinstance(topic_content["topics"], list):
        for idx, top in enumerate(topic_content["topics"], 1):
            t_title = top.get("title", "")
            lines = [f"--- TOPIC {idx}: '{t_title}' ---"]
            for g in top.get("key_grammar", []):
                lines.append(f"* [GRAMMAR] {g}")
            for v in top.get("key_vocab", []):
                lines.append(f"* [VOCAB] {v}")
            for txt in top.get("key_texts", []):
                lines.append(f"* [TEXT] {txt[:200]}")
            if len(lines) > 1:
                sections.append("\n".join(lines))

    return "\n\n".join(sections)


def ai_generate_questions(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, is_quiz=False, source_text_override=None, model_override=None, material_language="en", generation_seed=None, focus_directive=None, timing_ctx=None, scope=None, progression=None, coverage_plan="", forbidden_terms=None):
    c = int(count)
    gen_count = qc.overproduction_count(c)
    if timing_ctx is None:
        timing_ctx = {}

    with open("pipeline.log", "a", encoding="utf-8") as f:
        api_status = "Available" if is_ai_available() else "MISSING KEY"
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-START] {topic_title} count={count} gen_count={gen_count} seed={generation_seed} focus={focus_directive} API={api_status}\n")
    
    is_beginner = any(lvl in level.upper() for lvl in ["A1", "A2"])
    instruction_lang_name = "Turkish" if material_language == "tr" else "English"
    
    # Use override if provided, or preassembled string if provided, or cache lookup, or fallback
    if source_text_override:
        content_str = f"EXTRACTED TEXTBOOK CONTENT:\n{source_text_override[:8000]}"
    elif isinstance(topic_content, dict) and "_preassembled_content_str" in topic_content:
        content_str = topic_content["_preassembled_content_str"]
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
            t_texts = top.get("key_texts", [])
            
            lines = [f"[MODULE {idx}: '{t_title}' (Focus: {t_type})]"]
            if t_grammar:
                lines.append("  Explicit Taught Grammar Rules & Contrasts: " + " | ".join(t_grammar[:4]))
            # Note: Dialogues excluded from target selection to avoid incidental chatter poisoning question focus
            if t_vocab:
                lines.append("  Target Vocabulary & Lexicon: " + ", ".join(t_vocab[:8]))
            if t_texts:
                lines.append("  Reading Passage: " + t_texts[0][:250])
            parts.append("\n".join(lines))
        parts.append("================================================================================")
        module_total = len(topic_content.get("topics", [])[:8])
        if module_total > 1:
            parts.append(
                "UNIT COVERAGE REQUIREMENT:\n"
                f"- This review covers {module_total} modules. Spread the questions across ALL of them.\n"
                f"- If you generate at least {module_total} questions, every module must be represented by at least one question.\n"
                "- Allocate any remaining questions in proportion to how much teachable material each module actually contains.\n"
                "- Tag every question with its source module using the integer \"module\" field.\n"
                "- Do not spend two questions on the same learning objective while another module is unrepresented."
            )
        content_str = "\n\n".join(parts)
    elif isinstance(topic_content, dict) and "pages" in topic_content:
        from services.quiz_source_cache import get_or_assemble_quiz_source
        t_cache_start = time.perf_counter()
        q_src = get_or_assemble_quiz_source(str(topic_content.get("id") or topic_title), topic_title, topic_type, topic_content, material_language)
        if "structured_lesson_assembly" not in timing_ctx:
            timing_ctx["structured_lesson_assembly"] = time.perf_counter() - t_cache_start
            timing_ctx["provenance_resolution"] = 0.0001
        content_str = q_src["single_topic_content_str"]
    elif isinstance(topic_content, dict):
        pages = topic_content.get("pages", [])
        page_sections = []

        for idx, p in enumerate(pages, 1):
            p_title = p.get("title", f"Part {idx}")
            p_type = p.get("type", "content")
            
            p_lines = [f"[PART {idx}: '{p_title}' (Focus: {p_type})]"]
            
            has_explicit_rules = bool(p.get("rules") or p.get("comparisons"))
            has_items = bool(p.get("items"))

            # Explicit Taught Grammar Rules (Primary source for grammar/function)
            if p.get("rules") and isinstance(p["rules"], list):
                rule_lines = []
                for r in p["rules"][:5]:
                    if isinstance(r, dict):
                        r_name = (r.get("rule_tr") if material_language == "tr" and r.get("rule_tr") else (r.get("rule") or "")).strip()
                        r_expl = (r.get("explanation_tr") if material_language == "tr" and r.get("explanation_tr") else (r.get("explanation") or "")).strip()
                        r_ex = (r.get("example") or "").strip()
                        r_ev = (r.get("source_evidence") or "").strip()
                        if r_name and r_ev:
                            r_disp = f"  * [RULE] {r_name}"
                            if r_expl: r_disp += f": {r_expl[:180]}"
                            if r_ex: r_disp += f" — Example: '{r_ex}'"
                            r_disp += f" [Source: '{r_ev[:100]}']"
                            rule_lines.append(r_disp)
                if rule_lines:
                    p_lines.append("Explicit Taught Grammar Rules (Primary Grammar Source):\n" + "\n".join(rule_lines))

            # Structural Contrasts & Nuances (Primary source for grammatical distinctions)
            if p.get("comparisons") and isinstance(p["comparisons"], list):
                comp_lines = []
                for comp in p["comparisons"][:3]:
                    if isinstance(comp, dict):
                        c_tgt = (comp.get("target") or "").strip()
                        c_ctx = (comp.get("context_tr") if material_language == "tr" and comp.get("context_tr") else (comp.get("context") or "")).strip()
                        c_note = (comp.get("note_tr") if material_language == "tr" and comp.get("note_tr") else (comp.get("note") or "")).strip()
                        c_ev = (comp.get("source_evidence") or "").strip()
                        if c_tgt and c_ev:
                            c_disp = f"  * [CONTRAST] '{c_tgt}'" + (f" ({c_ctx})" if c_ctx else "") + (f": {c_note[:140]}" if c_note else "")
                            c_disp += f" [Source: '{c_ev[:100]}']"
                            comp_lines.append(c_disp)
                if comp_lines:
                    p_lines.append("Structural Contrasts & Nuances:\n" + "\n".join(comp_lines))

            # Explanatory text / Narrative / Reading
            # Budget-conscious: prioritize compact rules/comparisons over redundant narrative text
            if p.get("text"):
                txt = p.get("text").strip()
                if txt:
                    txt_limit = 250 if (has_explicit_rules or has_items) else 500
                    p_lines.append(f"Passage / Context (Lexical Evidence):\n{txt[:txt_limit]}")

            # Note: Dialogue exchanges are omitted from quiz source material to prevent
            # incidental conversational chatter or irrelevant filler vocabulary from confusing target objectives.

            # Items (Target Lexicon & Examples - Lexical/Contextual Evidence)
            if p.get("items") and isinstance(p["items"], list):
                item_lines = []
                for it in p["items"][:12]:
                    if isinstance(it, dict):
                        term = (it.get("term") or it.get("word") or it.get("rule") or "").strip()
                        tr = (it.get("translation_tr") if material_language == "tr" and it.get("translation_tr") else (it.get("translation_en") or it.get("translation") or it.get("meaning") or "")).strip()
                        ex = (it.get("example") or it.get("sample") or "").strip()
                        expl = (it.get("explanation_tr") if material_language == "tr" and it.get("explanation_tr") else (it.get("explanation_en") or it.get("explanation") or "")).strip()
                        it_ev = str(it.get("source_evidence") or "").strip()
                        it_prov = str(it.get("provenance") or "").strip().lower()
                        is_source_backed_expl = bool(it_ev or it_prov == "source_explicit")

                        if term:
                            item_display = f"  * {term}" + (f" ({tr})" if tr else "")
                            if ex: item_display += f" — Example: '{ex}'"
                            if is_source_backed_expl and expl: item_display += f" — Note: {expl[:120]}"
                            item_lines.append(item_display)
                if item_lines:
                    p_lines.append("Target Lexicon & Examples (Lexical Evidence):\n" + "\n".join(item_lines))

            if len(p_lines) > 1:
                page_sections.append("\n".join(p_lines))

        parts = [
            "================================================================================",
            "AUTHORITATIVE LESSON SOURCE MATERIAL (PRIMARY EVIDENCE SOURCE OF TRUTH):",
            "================================================================================",
            "The learner has studied the following lesson material. Your questions MUST be strictly",
            "material-dependent: test target vocabulary, grammar patterns, rules, relationships,",
            "and core concepts taught in THIS MATERIAL itself.",
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
    
    t_prompt_start = time.perf_counter()
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

2. ALLOW BROADER OBJECTIVE COVERAGE WITHOUT FORCED NOVELTY (SCENARIO-FRAME TRANSFER ONLY):
   - While avoiding redundant repetition of essentially the same question or item, the same broader learning objective, grammatical structure, or thematic area IS fully permitted to reappear in a genuinely different context or task.
   - Genuinely different context applies EXCLUSIVELY to the external scenario frame (speaker identity, setting, communicative goal, surrounding situation, and question format), NEVER to altering the internal head–argument, valency, complement, or selectional structure of the taught target.
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

    # ── THE CONTRACT ──
    # services/question_contract.py owns what a question must be. The system
    # half is class-invariant: target language, CEFR level and the two
    # conditioning blocks, all fixed for a course. Nothing per-topic,
    # per-batch or per-sub-batch may enter it, because that is exactly what
    # makes it a byte-identical prefix across every generation in a class and
    # lets the provider cache it (see cache_system= on the call below). Topic,
    # batch size, source material, rolling history and focus live in the user
    # half, which is small.
    system = qc.build_system_prompt(
        language=language,
        level=level,
        cefr_guidance=cefr_guidance,
        pedagogy_guidance=pedagogy_guidance,
    )
    seed = generation_seed if generation_seed is not None else (int(time.time() * 1000) % 999999)
    if scope in (_SCOPE_TOPIC, _SCOPE_UNIT):
        # A material-internal assessment. Same cached system prefix, same quality
        # rules; what differs is the boundary it may draw from and the language
        # budget it must phrase itself inside. Both arrive as short clauses.
        user = qc.build_material_user_prompt(
            language=language,
            level=level,
            scope=scope,
            title=topic_title,
            item_count=gen_count,
            content_str=content_str,
            progression=progression or "",
            coverage_plan=coverage_plan,
            request_id=f"{seed}_{py_random.random()}",
        )
    else:
        user = qc.build_user_prompt(
            language=language,
            level=level,
            topic_title=topic_title,
            topic_type=topic_type,
            gen_count=gen_count,
            content_str=content_str,
            variety_focus=selected_variety_focus,
            forbidden_prompts=forbidden_prompts,
            forbidden_answers=forbidden_answers,
            reference_data=ref_data,
            focus_directive=focus_directive,
            request_id=f"{seed}_{py_random.random()}",
        )
    prompt_chars = len(system) + len(user)
    prompt_tokens_est = int(prompt_chars / 4.0)
    t_prompt_duration = time.perf_counter() - t_prompt_start
    timing_ctx["prompt_construction"] = t_prompt_duration
    timing_ctx["prompt_chars"] = prompt_chars
    timing_ctx["prompt_tokens_est"] = prompt_tokens_est
    
    try:
        t_ai_duration = 0.0
        if model_override and str(model_override).lower() in ["none", "offline", "skip", "disabled"]:
            res = None
        else:
            target_model = model_override if model_override else MODEL_STRUCTURAL
            target_temp = 0.95 if existing_questions else 0.90
            calc_max_tokens = qc.output_token_budget(gen_count)
            t_ai_start = time.perf_counter()
            main_usage: Dict[str, Any] = {}
            res = _call_ai(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                model=target_model,
                max_tokens=calc_max_tokens,
                temperature=target_temp,
                json_mode=True,
                allow_fallback=True,
                usage_dict=main_usage,
                cost_stage=_COST_STAGE_QUESTIONS,
                cost_subject=str(topic_title),
                # Class-invariant by construction (see the contract above). Every
                # quiz, activity and assignment in a course sends this same
                # prefix, so marking it is what turns ~30 repeats of it per class
                # into one paid copy.
                cache_system=True,
            )
            t_ai_duration = time.perf_counter() - t_ai_start
            m_cost = main_usage.get("cost")
            if m_cost is None:
                m_cost = _estimate_llm_cost(target_model, int(main_usage.get("prompt_tokens", prompt_tokens_est)), int(main_usage.get("completion_tokens", 800)))
            timing_ctx["main_ai_cost"] = float(m_cost)
        timing_ctx["main_ai_generation"] = t_ai_duration
        
        t_parse_start = time.perf_counter()
        raw_list = []
        if isinstance(res, list):
            raw_list = res
        elif isinstance(res, dict):
            raw_list = res.get("data") or res.get("questions") or res.get("items") or res.get("quiz") or res.get("activities") or []
        t_parse_duration = time.perf_counter() - t_parse_start
        timing_ctx["parsing"] = t_parse_duration
        
        t_filter_start = time.perf_counter()
        # ── V5 RIGOROUS VALIDATION & ANTI-GIVEAWAY FILTER HELPER ──
        def _assemble_valid_candidate(item, current_final):
            if not isinstance(item, dict): return None
            p = str(item.get("prompt", "")).strip()
            a = str(item.get("answer", "")).strip()
            d = item.get("distractors", [])
            if not (p and a and isinstance(d, list)):
                return None

            # Deterministic assessment contract: translation drills, stems written
            # in the instructional language, giveaway glosses and scope leakage.
            # Run here rather than after assembly so a rejected candidate is
            # replaced from the pool exactly like any other rejection, instead of
            # silently shrinking a finished batch.
            try:
                from services.assessment_validation import violations as _av_violations, is_fatal as _av_fatal
                _probs = [x for x in _av_violations(
                    item,
                    instructional_track=material_language,
                    forbidden_terms=forbidden_terms,
                    require_rationale_track=False,
                ) if _av_fatal(x)]
                # Option-shape problems are repaired further down by distractor
                # supplementation, so they are not grounds for rejection here.
                _probs = [x for x in _probs if not x.startswith(("distractor_count_", "option_count_", "answer_not_in_options"))]
                if _probs:
                    return None
            except Exception:
                pass

            clean_a_token = _normalize_token(a)
            clean_p_token = _normalize_token(p)

            # IN-BATCH DEDUPLICATION: Reject same-batch semantic near-duplicates and ungrounded concept definitions
            if _is_same_batch_semantic_duplicate(item, current_final, topic_content):
                return None

            # IN-BATCH PATTERN & PROMPT DIVERSITY: Reject near-identical prompt stems or sentence templates
            if any(difflib.SequenceMatcher(None, clean_p_token, _normalize_token(f.get("prompt", ""))).ratio() > 0.85 for f in current_final):
                return None

            # COGNITIVE TASK VARIETY: Allow adequate fill-in-the-blank questions
            has_blank = "_" in p or "____" in p
            if has_blank:
                current_blanks = sum(1 for f in current_final if "_" in f.get("prompt", "") or "____" in f.get("prompt", ""))
                if current_blanks >= max(8, int(c * 0.75)):
                    return None

            # STRICT DIVERSITY FILTER: Absolute rejection of any repeated or near-duplicate prompt from previous rounds
            if forbidden_prompt_keys:
                if clean_p_token in forbidden_prompt_keys:
                    return None
                if any(difflib.SequenceMatcher(None, clean_p_token, fp_key).ratio() > 0.94 for fp_key in forbidden_prompt_keys):
                    return None

            # Reject prompts containing Turkish instructional words ONLY if target language is NOT Turkish
            if not any(k in language.lower() for k in ["turkish", "türkçe", "turkce"]):
                tr_prompt_markers = ["hangisidir", "aşağıdakilerden", "seçiniz", "cümleyi", "anlamına gelir", "karşılığı nedir", "boşluğu doldur", "uygun kelimeyi"]
                if any(m in p.lower() for m in tr_prompt_markers):
                    return None

            # GATE 1 COMMON SENSE & TRIVIAL CATEGORY MATCHING REJECTION
            clean_p_lower = p.lower()
            stereotypical_category_patterns = [
                r'\b(?:dónde|donde|where|wo|où|ou|dove)\s+(?:trabaja|trabajan|works?|arbeitet|travaille|lavora)\s+(?:un|una|el|la|a|an|the|ein|eine|der|die|das|un|une|le|la|uno)\s+(?:médico|médica|doctor|profesor|profesora|maestro|maestra|cocinero|cocinera|camarero|camarera|bombero|bombera|policía|arzt|ärztin|lehrer|lehrerin|koch|köchin|kellner|kellnerin|médecin|professeur|cuisinier|serveur|pompiers?|policier|medico|professore|cuoco|cameriere)\b',
                r'\b(?:qué|que|what|was|que|cosa)\s+(?:haces|hace|do you do|macht man|fais-tu|fai)\s+(?:si|cuando|when|wenn|quand|quando)\s+(?:tienes\s+hambre|tienes\s+sed|you are hungry|you are thirsty|man hunger hat|man durst hat)\b'
            ]
            if any(re.search(pat, clean_p_lower) for pat in stereotypical_category_patterns):
                return None

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
                            if not any(ch in oa for ch in ["(", ")", "/", "[", "]", "{", "}"]):
                                extra_candidates.append(oa)
                        for od in other_item.get("distractors", []):
                            ods = str(od).strip()
                            if ods and ods.lower() != a.lower() and ods.lower() not in [cd.lower() for cd in clean_d]:
                                if not any(ch in ods for ch in ["(", ")", "/", "[", "]", "{", "}"]):
                                    extra_candidates.append(ods)
                if isinstance(topic_content, dict):
                    for pg in topic_content.get("pages", []):
                        for it in pg.get("items", []):
                            if isinstance(it, dict) and it.get("term"):
                                t_str = str(it.get("term")).strip()
                                if any(ch in t_str for ch in ["(", ")", "/", "[", "]", "{", "}"]):
                                    continue
                                if t_str and t_str.lower() != a.lower() and t_str.lower() not in [cd.lower() for cd in clean_d]:
                                    extra_candidates.append(t_str)

                extra_candidates = [cand for cand in extra_candidates if abs(len(cand) - len(a)) <= max(len(a), 15)]
                py_random.shuffle(extra_candidates)
                for cand in extra_candidates:
                    if cand.lower() not in [cd.lower() for cd in clean_d]:
                        clean_d.append(cand)
                    if len(clean_d) >= 3:
                        break

            if len(clean_d) < 3:
                return None

            if is_arithmetic_question(p) or is_arithmetic_question(a):
                return None

            # Programmatic Anti-Giveaway & Anti-Trivia Verification
            clean_p = re.sub(r'[^\w\s]', ' ', p.lower())
            clean_a = re.sub(r'[^\w\s]', ' ', a.lower()).strip()
            
            is_giveaway = False
            if len(clean_a) >= 3:
                quoted_answer_pattern = rf"['\"«“]{re.escape(clean_a)}['\"»”]"
                if re.search(quoted_answer_pattern, clean_p):
                    is_giveaway = True
                if clean_p.strip() == clean_a.strip():
                    is_giveaway = True

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

            meta_accent_indicators = [
                "tilde grafica", "lleva tilde", "se escribe con tilde", "con tilde",
                "accent aigu", "accent grave", "con acento", "hat einen akzent",
                "hangi kelimede sapka", "which word has an accent", "has a tilde", "se escribe tradicionalmente con tilde"
            ]
            if any(mai in clean_p for mai in meta_accent_indicators):
                is_giveaway = True

            if any(w in clean_p for w in ["tilde", "acento", "accent"]):
                accent_opts = [o for o in [a] + clean_d[:3] if re.search(r'[áéíóúÁÉÍÓÚàèìòùÀÈÌÒÙâêîôûÂÊÎÔÛ]', o)]
                if len(accent_opts) > 1:
                    is_giveaway = True

            product_trivia = ["city ticket", "city-ticket", "bahncard", "abonnement general", "cartes de reduction"]
            if any(pt in clean_p for pt in product_trivia):
                is_giveaway = True

            if any(s in language.lower() for s in ["spanish", "español", "ispanyolca"]):
                if any("ç" in o.lower() for o in [a] + clean_d):
                    is_giveaway = True

            if all(len(re.sub(r'^(la letra|the letter|harf|harfi)\s*', '', opt.lower()).strip()) <= 2 for opt in [a] + clean_d[:3]):
                is_giveaway = True

            if clean_d and len(a) > 2.2 * max(len(dist) for dist in clean_d[:3]) and len(a) > 25:
                is_giveaway = True
            if clean_d and min(len(dist) for dist in clean_d[:3]) > 2.5 * len(a) and min(len(dist) for dist in clean_d[:3]) > 25:
                is_giveaway = True

            if is_transparent_cognate_giveaway(p, "", a, language):
                is_giveaway = True

            if ("______" in p or "____" in p) and not is_giveaway:
                if "turkish" not in language.lower() and "türkçe" not in language.lower():
                    blank_lines = [line for line in p.split("\n") if "____" in line]
                    for bl in blank_lines:
                        tr_unique_markers = [" için ", " sabah ", " çünkü ", " lütfen ", " hangisi ", " boşluğa ", " seçiniz "]
                        bl_lower = bl.lower()
                        if any(m in bl_lower for m in tr_unique_markers):
                            is_giveaway = True
                            break

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

            if "_" in p and len(clean_a.split()) == 1:
                trivial_verbs = {"fahren", "gehen", "machen", "haben", "sein", "ser", "estar", "haber", "hacer", "ir", "aller", "faire", "fare", "andare"}
                if clean_a in trivial_verbs:
                    pre_blank_match = re.search(r'(\w+)\s*_{2,}', p.lower())
                    if pre_blank_match:
                        pre_word = pre_blank_match.group(1)
                        if pre_word in ["geschwindigkeit", "tempo", "vitesse", "velocidad", "velocità", "zähne", "bett", "hause"]:
                            is_giveaway = True

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
                return None

            why_en = item.get("why", "Correct answer based on the material.")
            why_tr = item.get("why_tr", item.get("why", "Materyale göre doğru seçenek."))
            t_en = item.get("translation_en") or item.get("translation", "")
            t_tr = item.get("translation_tr") or item.get("translation", "")

            # If prompt has a blank, preserve the blank in translations
            if re.search(r'_{2,}', p):
                t_en, t_tr = _sanitize_blank_translations(p, a, t_en, t_tr, why_en, why_tr, topic_content)

            opts = [a] + clean_d[:3]
            py_random.shuffle(opts)

            return {
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
                "module": item.get("module"),
                "material_section": str(item.get("material_section", "")).strip()[:100],
                "cognitive_task": str(item.get("cognitive_task", "")).strip()[:50]
            }

        # Telemetry tracking for candidate selection, replacement, top-up, and fallback
        initial_candidate_count = len(raw_list)
        valid_after_filter_count = 0
        pool_replacements_used = 0
        topup_requested = 0
        topup_returned = 0
        topup_accepted = 0
        fallback_attempted = 0
        fallback_accepted = 0
        abort_reason = ""

        # Direct Candidate Selection from Main Pool
        final = []
        rejected_initial_count = 0
        for idx, item in enumerate(raw_list):
            cand = _assemble_valid_candidate(item, final)
            if cand:
                final.append(cand)
                if rejected_initial_count > 0 or idx >= c:
                    pool_replacements_used += 1
                else:
                    valid_after_filter_count += 1
                if len(final) >= c:
                    break
            else:
                if idx < c:
                    rejected_initial_count += 1

        t_filter_duration = time.perf_counter() - t_filter_start
        timing_ctx["filter_dedup"] = t_filter_duration

        # Hard invariant shortfall resolution: Perform at most ONE bounded top-up request ONLY if initial candidate pool is genuinely exhausted
        t_topup_start = time.perf_counter()
        t_topup = 0.0
        timing_ctx["topup_ai_cost"] = 0.0
        timing_ctx["topup_ai_calls"] = 0
        ai_active = not (model_override and str(model_override).lower() in ["none", "offline", "skip", "disabled"])

        if len(final) < c and ai_active:
            shortfall = c - len(final)
            topup_requested = shortfall
            cur_forbidden_prompts = list(forbidden_prompts)
            cur_forbidden_answers = list(forbidden_answers)
            for f in final:
                fp = str(f.get("prompt", "")).strip()
                fa = str(f.get("answer", "")).strip()
                if fp and fp not in cur_forbidden_prompts:
                    cur_forbidden_prompts.append(fp)
                if fa and fa not in cur_forbidden_answers:
                    cur_forbidden_answers.append(fa)

            topup_user = qc.build_topup_prompt(
                language=language,
                level=level,
                topic_title=topic_title,
                topic_type=topic_type,
                shortfall=shortfall,
                content_str=content_str,
                variety_focus=selected_variety_focus,
                rejected_prompts=cur_forbidden_prompts,
                request_id=f"{seed}_topup_1_{py_random.random()}",
            )

            topup_max_tokens = qc.output_token_budget(shortfall, ceiling=3000)
            topup_usage: Dict[str, Any] = {}
            topup_res = _call_ai(
                [{"role": "system", "content": system}, {"role": "user", "content": topup_user}],
                model=target_model,
                max_tokens=topup_max_tokens,
                temperature=target_temp,
                json_mode=True,
                allow_fallback=True,
                usage_dict=topup_usage,
                cost_stage=_COST_STAGE_QUESTIONS,
                cost_subject=str(topic_title),
                # Same prefix as the main call it follows, so the top-up pays for
                # its own short user message and nothing else.
                cache_system=True,
            )
            timing_ctx["topup_ai_calls"] = 1
            top_c = topup_usage.get("cost")
            if top_c is None:
                top_c = _estimate_llm_cost(target_model, int(topup_usage.get("prompt_tokens", 800)), int(topup_usage.get("completion_tokens", 400)))
            timing_ctx["topup_ai_cost"] = float(top_c)

            topup_list = []
            if isinstance(topup_res, list):
                topup_list = topup_res
            elif isinstance(topup_res, dict):
                topup_list = topup_res.get("data") or topup_res.get("questions") or topup_res.get("items") or topup_res.get("quiz") or topup_res.get("activities") or []
            
            topup_returned = len(topup_list)
            for item in topup_list:
                cand = _assemble_valid_candidate(item, final)
                if cand:
                    final.append(cand)
                    topup_accepted += 1
                    if len(final) >= c:
                        break

            t_topup = time.perf_counter() - t_topup_start
        timing_ctx["top_up"] = t_topup

        # ── DETERMINISTIC CONTENT FALLBACK (Safety Net if AI Provider Fails Completely) ──
        if len(final) < c and isinstance(topic_content, dict):
            fallback_attempted = c - len(final)
            lang_lower = language.lower()
            is_esp = any(s in lang_lower for s in ["spanish", "español", "ispanyolca"])
            is_de = any(s in lang_lower for s in ["german", "deutsch", "almanca"])
            is_fr = any(s in lang_lower for s in ["french", "français", "fransızca"])
            is_it = any(s in lang_lower for s in ["italian", "italiano", "italyanca"])
            is_ru = any(s in lang_lower for s in ["russian", "русский", "rusça"])
            is_tr = any(s in lang_lower for s in ["turkish", "türkçe", "turkce"])
            is_pt = any(s in lang_lower for s in ["portuguese", "português", "portekizce"])
            is_en = any(s in lang_lower for s in ["english", "ingilizce"])

            def _clean_fallback_term(raw_text: str) -> str:
                if not raw_text:
                    return ""
                # Strip bracketed annotations: [ex: ...], [note: ...], [RULE: ...], etc.
                txt = re.sub(r'\[.*?\]', '', str(raw_text))
                # Strip parenthesized translation/notes: (ticket), (der), etc.
                txt = re.sub(r'\(.*?\)', '', txt)
                # Strip leading bullet points, hyphens, or formatting artifacts
                txt = re.sub(r'^[\*\-\s•]+', '', txt)
                # Normalize whitespace
                txt = re.sub(r'\s+', ' ', txt).strip()
                return txt

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
                elif is_tr:
                    templates = [
                        f"Günlük iletişim bağlamında en uygun ifade hangisidir?: '______'",
                        f"Cümleyi doğal ve doğru bir şekilde tamamlayınız: '______'"
                    ]
                elif is_pt:
                    templates = [
                        f"Em uma conversa cotidiana autêntica, qual é a expressão mais adequada?: '______'",
                        f"Complete a frase de maneira natural e comunicativa: '______'"
                    ]
                elif is_en:
                    templates = [
                        f"Which expression is most appropriate in this communicative context?: '______'",
                        f"Complete the sentence naturally: '______'"
                    ]
                else:
                    return None
                return py_random.choice(templates)

            # 1. Pull pre-authored MCQs from topic content pages
            pages = list(topic_content.get("pages", []))
            py_random.shuffle(pages)
            for page in pages:
                if len(final) >= c: break
                if page.get("type") == "mcq" and page.get("prompt") and page.get("answer"):
                    prompt_txt = _clean_fallback_term(page.get("prompt", ""))
                    ans_txt = _clean_fallback_term(page.get("answer", ""))
                    if not prompt_txt or not ans_txt:
                        continue
                    if is_arithmetic_question(prompt_txt) or is_arithmetic_question(ans_txt):
                        continue
                    # Reject English prompt for non-English quiz
                    if not is_en and any(eng_w in prompt_txt.lower() for eng_w in ["which of the following", "choose the correct", "what does", "select the best"]):
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
                        raw_opts = list(page.get("options", []))
                        if not raw_opts:
                            raw_opts = [page.get("answer")] + page.get("distractors", [])
                        clean_opts = list(dict.fromkeys(_clean_fallback_term(o) for o in raw_opts if _clean_fallback_term(o)))
                        if ans_txt not in clean_opts:
                            clean_opts.insert(0, ans_txt)
                        clean_d = [o for o in clean_opts if _normalize_token(o) != a_tok][:3]
                        if len(clean_d) < 3:
                            continue
                        opts = [ans_txt] + clean_d
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
                            "answer": ans_txt,
                            "distractors": clean_d,
                            "options": opts,
                            "why": page.get("explanation", "Correct choice based on the lesson."),
                            "why_tr": page.get("explanation_tr", page.get("explanation", "Ders içeriğine göre doğru seçenek."))
                        })
                        fallback_accepted += 1

            # 2. In multi-topic or structured items, extract clean vocabulary
            if len(final) < c and "topics" in topic_content:
                all_clean_vocabs = []
                for t in topic_content.get("topics", []):
                    for x in t.get("key_vocab", []):
                        cln = _clean_fallback_term(x)
                        if cln and len(cln) >= 2 and not is_arithmetic_question(cln):
                            all_clean_vocabs.append(cln)
                all_clean_vocabs = list(dict.fromkeys(all_clean_vocabs))

                for top in topic_content.get("topics", []):
                    if len(final) >= c: break
                    vocabs = top.get("key_vocab", [])
                    for voc in vocabs:
                        if len(final) >= c: break
                        v_str = _clean_fallback_term(voc)
                        if not v_str or len(v_str) < 2 or is_arithmetic_question(v_str):
                            continue
                        v_tok = _normalize_token(v_str)
                        if any(_normalize_token(f.get("answer")) == v_tok for f in final):
                            continue
                        fallback_stem = _make_fallback_prompt(v_str)
                        if not fallback_stem:
                            continue
                        candidate_distractors = [
                            x for x in all_clean_vocabs
                            if _normalize_token(x) != v_tok and difflib.SequenceMatcher(None, _normalize_token(x), v_tok).ratio() < 0.85
                        ]
                        if len(candidate_distractors) >= 3:
                            selected_distractors = py_random.sample(candidate_distractors, 3)
                            opts = [v_str] + selected_distractors
                            py_random.shuffle(opts)
                            final.append({
                                "id": _uid(),
                                "type": "mcq",
                                "prompt": fallback_stem,
                                "translation": v_str,
                                "translation_en": v_str,
                                "translation_tr": v_str,
                                "answer": v_str,
                                "distractors": selected_distractors,
                                "options": opts,
                                "why": "Target vocabulary item from the lesson.",
                                "why_tr": "Ders içeriğindeki hedef kelime."
                            })
                            fallback_accepted += 1

        # Sanitize Turkish fields in generated questions
        for q in final:
            if q.get("translation_tr"):
                q["translation_tr"] = _sanitize_turkish_content(heal_turkish_syntax(q["translation_tr"]))
            if q.get("why_tr"):
                q["why_tr"] = _sanitize_turkish_content(heal_turkish_syntax(q["why_tr"]))
            if material_language == "tr" and q.get("translation"):
                q["translation"] = _sanitize_turkish_content(heal_turkish_syntax(q["translation"]))

        # ── HARD COMPLETION INVARIANT ──
        # If the requested count still cannot be satisfied after bounded top-up and clean fallback,
        # cleanly abort and surface a retryable failure (empty list) instead of returning a partial quiz.
        if len(final) < c:
            abort_reason = f"shortfall_after_bounded_topup: requested {c}, assembled {len(final)}"
            print(f"[QUIZ-ABORT] {abort_reason}. Returning empty list to enforce hard completion invariant.")
            final = []
        else:
            final = final[:c]

        t_filter_duration = timing_ctx.get("filter_dedup", 0.0)
        t_topup = timing_ctx.get("top_up", 0.0)
        topup_calls = timing_ctx.get("topup_ai_calls", 0)

        t_db = timing_ctx.get("db_loading", 0.0)
        t_assembly = timing_ctx.get("structured_lesson_assembly", 0.0)
        t_prov = timing_ctx.get("provenance_resolution", 0.0)
        t_persist = timing_ctx.get("persistence", 0.0)
        t_total = t_db + t_assembly + t_prov + t_prompt_duration + t_ai_duration + t_parse_duration + t_filter_duration + t_topup + t_persist
        timing_ctx["total_elapsed"] = t_total

        main_cost = timing_ctx.get("main_ai_cost", 0.0)
        topup_cost = timing_ctx.get("topup_ai_cost", 0.0)
        total_cost = main_cost + topup_cost
        timing_ctx["total_cost"] = total_cost

        status_str = "COMPLETED" if len(final) == c else f"ABORTED ({abort_reason})"
        perf_status_line = (
            f"[{datetime.now().strftime('%H:%M:%S')}] [QUIZ-STATUS] Topic: '{topic_title}' | "
            f"req={c} | init_cands={initial_candidate_count} | valid_filter={valid_after_filter_count} | "
            f"pool_replacements={pool_replacements_used} | topup_req={topup_requested} | "
            f"topup_ret={topup_returned} | topup_acc={topup_accepted} | fallback_att={fallback_attempted} | "
            f"fallback_acc={fallback_accepted} | final={len(final)} | status={status_str}"
        )
        print(perf_status_line)

        log_lines = [
            f"[{datetime.now().strftime('%H:%M:%S')}] [QUIZ-PERF] Topic: '{topic_title}' (req={c}, count={len(final)}):",
            f"  1. DB/Content Loading:       {t_db:.4f}s",
            f"  2. Structured Assembly:      {t_assembly:.4f}s",
            f"  3. Provenance Resolution:    {t_prov:.4f}s",
            f"  4. Prompt Construction:      {t_prompt_duration:.4f}s (size: {prompt_chars} chars, ~{prompt_tokens_est} toks)",
            f"  5. Main AI Generation:       {t_ai_duration:.4f}s (cost: ${main_cost:.6f})",
            f"  6. Response Parsing:         {t_parse_duration:.4f}s",
            f"  7. Filter / Selection:       {t_filter_duration:.4f}s (valid {valid_after_filter_count + pool_replacements_used} / {len(raw_list)} candidates)",
            f"  8. Top-up AI Call:           {t_topup:.4f}s (calls: {topup_calls}, cost: ${topup_cost:.6f})",
            f"  9. Persistence:              {t_persist:.4f}s",
            f"  Total Elapsed Time:          {t_total:.4f}s",
            f"  Total Generation Cost:       ${total_cost:.6f}"
        ]
        log_str = "\n".join(log_lines)
        print(log_str)

        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(perf_status_line + "\n")
            f.write(log_str + "\n")
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [QUIZ-STAGE-TIMING] DB: {t_db:.3f}s | Assembly: {t_assembly:.3f}s | Provenance: {t_prov:.3f}s | Prompt: {t_prompt_duration:.3f}s ({prompt_chars}c/~{prompt_tokens_est}t) | AI: {t_ai_duration:.2f}s (${main_cost:.6f}) | Parse: {t_parse_duration:.3f}s | Filter: {t_filter_duration:.3f}s | Topup: {t_topup:.2f}s (calls={topup_calls}, ${topup_cost:.6f}) | Persist: {t_persist:.3f}s | Total: {t_total:.2f}s | Cost: ${total_cost:.6f}\n")
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-DONE] topic={topic_title} requested={c} returned={len(final)}\n")
            
        # Assessments now cross a publication boundary too. This is deterministic
        # only and adds no model call: answer keys used to reach the learner with
        # no publication discipline of any kind.
        try:
            from services.publication_invariants import apply_assessment_invariants
            final = apply_assessment_invariants(final, language=language, material_language=material_language)
        except Exception as exc:
            print(f"[PUBLICATION] assessment invariants skipped: {exc}")
        return final
    except Exception as e:
        import traceback
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI-V2-CRASH] {e}\n{traceback.format_exc()}\n")
        return []

def generate_unit_assessment(unit_title, unit_topics, language, level="A1",
                             material_language="tr", unit_index=None, unit_total=None,
                             model_override=None, timing_ctx=None):
    """The ten-question assessment that closes a unit.

    `unit_topics` is [{"id","title","content"}, ...] for THIS unit only, already
    generated. Three things make this different from a standalone quiz over the
    same topics, and all three are structural rather than requested:

      * the evidence assembled is exactly this unit's topics, so a later unit
        cannot be drawn from even by accident;
      * the ten questions are apportioned across those topics by how much each
        actually teaches, so no substantial taught area is skipped and a
        thirty-item alphabet topic is not given the same weight as three polite
        formulas;
      * the language budget is built from what this unit's lessons really
        contain, so the questions are phrased inside the learner's repertoire at
        this point in the course.

    Returns a list of question dicts, or [] when the unit cannot support an
    assessment. Never returns a partial set: a unit assessment is ten questions
    or it is not a unit assessment.
    """
    from services.assessment_scope import (
        UNIT_ASSESSMENT_COUNT, plan_unit_coverage, coverage_plan_clause,
        build_envelope_from_topics, SCOPE_UNIT,
    )
    if timing_ctx is None:
        timing_ctx = {}
    usable = [t for t in (unit_topics or []) if isinstance(t, dict) and t.get("content")]
    if not usable:
        return []

    contents = []
    for t in usable:
        c = t.get("content")
        if isinstance(c, str):
            try:
                c = json.loads(c or "{}")
            except Exception:
                c = {}
        contents.append(c if isinstance(c, dict) else {})

    plan = plan_unit_coverage(
        [{"id": t.get("id"), "title": t.get("title"), "content": c} for t, c in zip(usable, contents)],
        total=UNIT_ASSESSMENT_COUNT,
    )
    if not plan:
        return []

    envelope = build_envelope_from_topics(
        level=level, language=language, prior_contents=contents,
        unit_index=unit_index, unit_total=unit_total,
    )

    # One assembled payload spanning the unit, labelled by topic so the model can
    # honour the plan and so attribution survives into the stored questions.
    parts = []
    for idx, (t, c) in enumerate(zip(usable, contents), 1):
        block = [f"[TOPIC {idx}: '{t.get('title')}']"]
        for page in c.get("pages", []) or []:
            if not isinstance(page, dict):
                continue
            items = [str(i.get("term") or "").strip() for i in (page.get("items") or [])
                     if isinstance(i, dict) and str(i.get("term") or "").strip()]
            if items:
                block.append("  Vocabulary: " + ", ".join(items[:14]))
            for r in (page.get("rules") or [])[:4]:
                if isinstance(r, dict) and str(r.get("rule") or "").strip():
                    line = "  [RULE] " + str(r.get("rule")).strip()
                    if str(r.get("example") or "").strip():
                        line += f" — e.g. '{str(r.get('example')).strip()}'"
                    block.append(line)
            for cmp_ in (page.get("comparisons") or [])[:3]:
                if isinstance(cmp_, dict) and str(cmp_.get("target") or "").strip():
                    block.append("  [CONTRAST] " + str(cmp_.get("target")).strip())
            txt = str(page.get("text") or "").strip()
            if txt and len(block) < 4:
                block.append("  Passage: " + txt[:220])
        if len(block) > 1:
            parts.append("\n".join(block))
    if not parts:
        return []
    content_str = "\n\n".join(parts)

    # Terms belonging to no topic in this unit are, by construction, unavailable
    # here — the payload IS the unit. The leakage check therefore has nothing to
    # forbid at this level; the caller supplies later-unit terms when it has them.
    questions = ai_generate_questions(
        topic_title=unit_title or "Unit Assessment",
        topic_type="unit_assessment",
        topic_content={"_preassembled_content_str": content_str},
        language=language,
        count=UNIT_ASSESSMENT_COUNT,
        level=level,
        is_quiz=True,
        material_language=material_language,
        model_override=model_override,
        timing_ctx=timing_ctx,
        scope=SCOPE_UNIT,
        progression=envelope,
        coverage_plan=coverage_plan_clause(plan),
    )
    if len(questions) < UNIT_ASSESSMENT_COUNT:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [UNIT-ASSESSMENT] '{unit_title}' "
                    f"produced {len(questions)}/{UNIT_ASSESSMENT_COUNT}; not published.\n")
        return []

    # Attribute each question to a topic in the unit, preferring what the model
    # reported and falling back to the plan rather than to chance.
    ids = [p.get("topic_id") for p in plan for _ in range(int(p.get("questions") or 0))]
    for i, q in enumerate(questions[:UNIT_ASSESSMENT_COUNT]):
        if not q.get("topic_id"):
            q["topic_id"] = ids[i] if i < len(ids) else (plan[0].get("topic_id"))
        q["assessment_scope"] = SCOPE_UNIT
    return questions[:UNIT_ASSESSMENT_COUNT]


def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, model_override=None, material_language="en"):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions, is_pdf_source=is_pdf_source, model_override=model_override, material_language=material_language)

def ai_generate_activity(topic_title, topic_type, topic_content, language, count=10, level='A1', existing_questions=None, is_pdf_source=False, material_language="en"):
    return ai_generate_questions(topic_title, topic_type, topic_content, language, count, level, existing_questions=existing_questions, is_pdf_source=is_pdf_source, material_language=material_language)

def ai_grade_open_response(question, student_answer, correct_answer):
    prompt = f"Grade: Q:{question}, C:{correct_answer}, S:{student_answer}. JSON: {{'score': 0..1, 'feedback': '...'}}"
    result = _call_ai([{"role": "user", "content": prompt}], max_tokens=150)
    return (result.get("score", 0.0), result.get("feedback", "")) if result else (0.0, "")

CURRICULUM_UNITS = 6
CURRICULUM_TOPICS_PER_UNIT = 5


def _curriculum_system(language, level, official_institution, cefr_guidance, audience):
    """Class-invariant half of the curriculum contract, so it can be cached.

    Varies only by language, level and institution. The Tier-1 fallback call and
    both expansion calls resend it byte-for-byte, so marking it as a cache
    breakpoint makes every call after the first one cheap.
    """
    return f"""You are a bilingual curriculum architect for {language}, working to the official syllabus of {official_institution} and the Council of Europe CEFR framework.

{cefr_guidance}

Every chapter and every topic carries two titles: the professional English title, and the natural Turkish title as an educated Turkish teacher would write it.

'title_tr' rules: 100% Turkish, grammatically correct, no English left inside it, no duplicated words. Never carry English-specific metalanguage across ('Wh- Questions' becomes 'Soru Kelimeleri'; do not write 'Wh- Soruları', and do not use 'Wh- Questions' in the English title of a non-English course either - write 'Question Words (Who, What, Where)'). Target-language forms stay in single quotes: "'Ser' Kullanarak Kimliği Tanımlama".

Topics are real lessons, not labels: functional usage, nuance and situational grammar. Never 'Vocabulary', 'Grammar' or 'Exercises' as a title. Audience: {audience}.

Worked pairs, for calibration:
  'Polite Expressions for Conversation' -> 'Sohbet İçin Nezaket İfadeleri'
  'Everyday Survival Vocabulary'        -> 'Günlük Hayatta Kalma Kelimeleri'
  "Using 'Ser' to Describe Identity"    -> "'Ser' Kullanarak Kimliği Tanımlama"
"""


_LEVEL_GUIDELINES = {
    "A1": "absolute basics: alphabet/phonetics, greetings, numbers, basic present tense, survival vocabulary, personal information.",
    "A2": "routine tasks, past tenses (introduction), describing surroundings, simple social exchanges, shopping and work scenarios.",
    "B1": "travel situations, opinions/dreams/hopes, complex past tenses, future and conditional, giving reasons for plans.",
    "B2": "technical discussion, interacting with natives without strain, detailed text on diverse subjects, introductory subjunctive.",
    "C1": "complex subjects, implicit meaning, flexible academic/professional language, deep nuance, advanced idiom.",
    "C2": "near-native mastery, summarising complex sources, fine shades of meaning, spontaneous academic reconstruction.",
}


def _rows_to_chapters(unit_rows, topic_rows_by_unit):
    """Decode the compact row form back into the stored chapter shape."""
    chapters = []
    for idx, row in enumerate(unit_rows, 1):
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        topics = []
        for t in topic_rows_by_unit.get(idx, []):
            if not isinstance(t, (list, tuple)) or len(t) < 2:
                continue
            topics.append({
                "title": str(t[0]).strip(),
                "title_tr": str(t[1]).strip(),
                "type": (str(t[2]).strip() if len(t) > 2 and str(t[2]).strip() else "vocabulary"),
            })
        chapters.append({"number": idx, "title": str(row[0]).strip(),
                         "title_tr": str(row[1]).strip(), "topics": topics})
    return chapters


def ai_generate_curriculum(language, level, prompt_extra=""):
    """Course structure, generated as an arc plus two concurrent expansions.

    The previous pass cut this call's PROMPT and its ceiling, which helped, and
    then the remaining time did not move much. Measuring the path rather than
    guessing at it showed why: with a clean model response there is exactly ONE
    provider call and no hidden second round trip, so almost all the wall clock
    is the model DECODING ~1,300 tokens of syllabus JSON, one token at a time.
    Input size and call count were never the bottleneck; output length is, and
    output length is the one thing the earlier optimisation could not reduce
    without deleting curriculum.

    Two changes attack it directly, neither of which removes anything from the
    result:

      * The wire format is compact rows - ["English title","Türkçe başlık",
        "type"] - instead of an object per topic. The three key names repeated
        thirty times were roughly 300 tokens of pure JSON syntax being decoded
        at conversational speed. They are re-expanded to the stored shape here,
        deterministically.

      * The syllabus is written as a small ARC call (six chapter titles and a
        one-line progression) followed by two expansion calls that run
        CONCURRENTLY, each writing the topics for three chapters and each given
        the full arc. Half the tokens are now decoded in parallel with the other
        half. Both halves see all six chapter titles, so progression across the
        seam is explicit rather than hoped for - if anything this is a tighter
        constraint than asking one call to keep thirty topics coherent.

    Any failure in the staged path falls back to the original single call, so
    the worst case is the old behaviour rather than a broken syllabus.
    """
    from services.cefr_reference import get_cefr_conditioning, LANGUAGE_CEFR_STANDARDS
    from services.language_profiles import normalize_language, locked_track, instruction_language_name

    t_stage_start = time.perf_counter()
    lang_std = LANGUAGE_CEFR_STANDARDS.get(language, {})
    official_institution = lang_std.get("institution", f"Council of Europe Official CEFR Framework for {language}")
    cefr_curriculum_guidance = get_cefr_conditioning(language, level, "Curriculum Architecture", "syllabus")

    canonical = normalize_language(language)
    forced_track = locked_track(canonical)
    audience = "Turkish-speaking learners"
    if forced_track:
        audience = f"learners reading the course in {instruction_language_name(forced_track)}"

    system = _curriculum_system(language, level, official_institution, cefr_curriculum_guidance, audience)
    current_guideline = next((v for k, v in _LEVEL_GUIDELINES.items() if k in level.upper()),
                             "general CEFR progression.")
    focus = f" focusing on: {prompt_extra}" if prompt_extra else ""
    U, T = CURRICULUM_UNITS, CURRICULUM_TOPICS_PER_UNIT

    chapters = []
    source = "staged"
    t_primary = 0.0
    try:
        t_call = time.perf_counter()
        arc_user = f"""Design the SHAPE of a {level} {language} syllabus{focus} for {audience}.
LEVEL FOCUS: {current_guideline}

Give EXACTLY {U} chapter titles that progress from foundational to complex, and one line describing the progression as a whole. Do not write topics yet.

Return ONLY this JSON, using compact rows ["English title","Türkçe başlık"]:
{{"arc": "one sentence describing how the {U} chapters progress",
  "units": [["Everyday Survival Vocabulary","Günlük Hayatta Kalma Kelimeleri"]]}}"""
        arc_res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": arc_user}],
                           model=MODEL_CURRICULUM, max_tokens=700, temperature=0.3,
                           cost_stage=_COST_STAGE_CURRICULUM, cost_subject=f"{language} {level} arc",
                           cache_system=True)
        unit_rows = (arc_res or {}).get("units") or []
        arc_text = str((arc_res or {}).get("arc") or "").strip()
        if len(unit_rows) < 4:
            raise ValueError(f"arc returned {len(unit_rows)} units")
        unit_rows = unit_rows[:U]

        listing = "\n".join(f"  {i}. {r[0]} / {r[1]}" for i, r in enumerate(unit_rows, 1)
                             if isinstance(r, (list, tuple)) and len(r) >= 2)
        half = (len(unit_rows) + 1) // 2
        spans = [(1, half), (half + 1, len(unit_rows))]

        def _expand(span):
            lo, hi = span
            want = "\n".join(f'  "{i}": [["English topic title","Türkçe konu başlığı","vocabulary"]]'
                              for i in range(lo, hi + 1))
            user = f"""The {level} {language} syllabus{focus} has these {len(unit_rows)} chapters, in order:
{listing}

PROGRESSION: {arc_text}
LEVEL FOCUS: {current_guideline}

Write EXACTLY {T} descriptive topics for chapters {lo}-{hi} ONLY. Keep them consistent with the chapters you are NOT writing, so the course does not repeat itself or jump ahead. 'type' is one of vocabulary, grammar, communication, functional, phonetics, mixed.

Return ONLY this JSON, using compact rows ["English title","Türkçe başlık","type"]:
{{"topics": {{
{want}
}}}}"""
            return _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}],
                            model=MODEL_CURRICULUM, max_tokens=1500, temperature=0.3,
                            cost_stage=_COST_STAGE_CURRICULUM,
                            cost_subject=f"{language} {level} units {lo}-{hi}",
                            cache_system=True)

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            halves = list(pool.map(_expand, spans))

        topic_rows = {}
        for res in halves:
            for key, rows in ((res or {}).get("topics") or {}).items():
                try:
                    topic_rows[int(str(key).strip())] = rows
                except (TypeError, ValueError):
                    continue
        t_primary = time.perf_counter() - t_call
        chapters = _rows_to_chapters(unit_rows, topic_rows)
        if len([c for c in chapters if c.get("topics")]) < 4:
            raise ValueError("expansion produced too few populated units")
    except Exception as exc:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [CURRICULUM] staged path unavailable ({exc}); "
                    f"falling back to the single-call syllabus.\n")
        chapters = []
        source = "single"

    if not chapters or len(chapters) < 4:
        t_call = time.perf_counter()
        user = f"""Design a {level} {language} syllabus{focus} for {audience}.
LEVEL FOCUS: {current_guideline}

EXACTLY {U} chapters, EXACTLY {T} descriptive topics each. Both titles on every chapter and every topic.

Return ONLY this JSON, using compact rows:
{{"units": [["English unit title","Türkçe ünite başlığı",
   [["English topic title","Türkçe konu başlığı","vocabulary"]]]]}}"""
        res = _call_ai([{"role": "system", "content": system}, {"role": "user", "content": user}],
                       model=MODEL_CURRICULUM, max_tokens=2400, temperature=0.3,
                       cost_stage=_COST_STAGE_CURRICULUM, cost_subject=f"{language} {level}",
                       cache_system=True)
        rows = (res or {}).get("units") or []
        unit_rows, topic_rows = [], {}
        for i, row in enumerate(rows[:U], 1):
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                unit_rows.append([row[0], row[1]])
                topic_rows[i] = row[2] if len(row) > 2 and isinstance(row[2], list) else []
        chapters = _rows_to_chapters(unit_rows, topic_rows)
        t_primary += time.perf_counter() - t_call
        source = "single"

    # Tier 2 Fallback: verified blueprint cache.
    if not chapters or len([c for c in chapters if c.get("topics")]) < 4:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [CURRICULUM] generation returned <4 populated units. "
                    f"Loading verified blueprint fallback for {language} {level}.\n")
        cached = _load_blueprint_chapters(language, level)
        if cached:
            from services.curriculum_translator import ensure_bilingual_curriculum
            return _finish_curriculum(ensure_bilingual_curriculum(cached), language, level,
                                      t_stage_start, t_primary, "blueprint")

    for i, ch in enumerate(chapters):
        ch["number"] = i + 1
        if isinstance(ch.get("title"), str):
            ch["title"] = re.sub(r'^Unit\s*\d+\s*[:\-]*\s*', '', ch["title"], flags=re.IGNORECASE).strip()
        if isinstance(ch.get("title_tr"), str):
            ch["title_tr"] = re.sub(r'^Ünite\s*\d+\s*[:\-]*\s*', '', ch["title_tr"], flags=re.IGNORECASE).strip()

    if not chapters or len(chapters) < 4:
        cached = _load_blueprint_chapters(language, level, require_four=False)
        if cached:
            from services.curriculum_translator import ensure_bilingual_curriculum
            return _finish_curriculum(ensure_bilingual_curriculum(cached), language, level,
                                      t_stage_start, t_primary, "blueprint")

    from services.curriculum_translator import ensure_bilingual_curriculum
    chapters = ensure_bilingual_curriculum(chapters)
    return _finish_curriculum(chapters, language, level, t_stage_start, t_primary, source)


def _load_blueprint_chapters(language, level, require_four=True):
    """Verified blueprint cache for a language/level, or None."""
    cache_file = _get_blueprint_path(language, level)
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cached_data = json.load(f)
    except Exception:
        return None
    chapters = (cached_data or {}).get("chapters") or []
    if not chapters or (require_four and len(chapters) < 4):
        return None
    return chapters


def _finish_curriculum(chapters, language, level, t_stage_start, t_primary, source):
    """Mark the syllabus as already healed, and record where the time went.

    `_aulaai_bilingual_healed` lets the HTTP layer skip a second full
    `ensure_bilingual_curriculum` pass over the same chapters - that pass was
    pure duplicate work, and when its heuristics disagreed with themselves it
    could also fire a second round of translation calls for titles the first
    pass had already translated.
    """
    total = time.perf_counter() - t_stage_start
    try:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(
                f"[{datetime.now().strftime('%H:%M:%S')}] [CURRICULUM-TIMING] {language} {level} "
                f"source={source} units={len(chapters)} provider={t_primary:.1f}s "
                f"bilingual={max(0.0, total - t_primary):.1f}s total={total:.1f}s\n"
            )
    except Exception:
        pass
    if isinstance(chapters, list):
        for ch in chapters:
            if isinstance(ch, dict):
                ch["_aulaai_bilingual_healed"] = True
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
            # Normalize alternative overview containers into text
            if not p.get("text"):
                for t_key in ("summary", "description", "content", "introduction"):
                    val = p.get(t_key)
                    if isinstance(val, str) and val.strip():
                        p["text"] = p.pop(t_key).strip()
                        break
                    elif isinstance(val, list) and val:
                        p["text"] = "\n".join(f"• {x}" for x in p.pop(t_key) if str(x).strip())
                        break
            # Normalize alternative vocabulary containers into items
            if not p.get("items"):
                for v_key in ("vocabulary", "words", "terms", "cards", "lexicon"):
                    if isinstance(p.get(v_key), list) and p[v_key]:
                        p["items"] = p.pop(v_key)
                        break
                    elif isinstance(p.get(v_key), dict) and p[v_key]:
                        p["items"] = list(p.pop(v_key).values())
                        break
            # Normalize alternative grammar containers into rules
            if not p.get("rules"):
                for r_key in ("grammar_rules", "grammar", "grammar_points", "points", "patterns"):
                    if isinstance(p.get(r_key), list) and p[r_key]:
                        p["rules"] = p.pop(r_key)
                        break
            # Normalize alternative contrast containers into comparisons
            if not p.get("comparisons"):
                for c_key in ("contrasts", "contrast_pairs", "grammar_contrast_pairs"):
                    if isinstance(p.get(c_key), list) and p[c_key]:
                        p["comparisons"] = p.pop(c_key)
                        break
            # Normalize dialogues / dialogue
            if "dialogues" in p and "dialogue" not in p:
                p["dialogue"] = p.pop("dialogues")
            if not p.get("dialogue"):
                for d_key in ("conversations", "conversation", "turns", "lines"):
                    if isinstance(p.get(d_key), list) and p[d_key]:
                        p["dialogue"] = p.pop(d_key)
                        break
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
            if p.get("rules") or p.get("grammar") or p.get("comparisons"):
                p["type"] = "grammar"
            elif p.get("items") or p.get("vocabulary"):
                p["type"] = "vocabulary"
            elif p.get("dialogue") or p.get("conversations"):
                p["type"] = "examples"
            elif p.get("prompt") or p.get("options") or p.get("distractors"):
                p["type"] = "mcq"
            elif not p.get("type") or p.get("type") in ["custom", "lesson"]:
                p["type"] = "overview"

            # Synchronize MCQ options, bilingual display labels, and answer position.
            # Canonical `options` are used for grading; localized arrays are display-only.
            if p.get("type") == "mcq" or p.get("prompt"):
                p["type"] = "mcq"
                ans = str(p.get("answer", "")).strip()
                opts = p.get("options")
                distrs = p.get("distractors")

                if opts and isinstance(opts, list) and len(opts) > 1:
                    clean_opts = [str(o).strip() for o in opts if str(o).strip()]
                elif distrs and isinstance(distrs, list) and len(distrs) > 0:
                    clean_distrs = [str(d).strip() for d in distrs if str(d).strip()]
                    clean_opts = ([ans] if ans else []) + clean_distrs
                else:
                    clean_opts = []

                # Recover answer from an explicit index if the model supplied one.
                raw_idx = p.get("correct_index")
                if not ans and isinstance(raw_idx, int) and 0 <= raw_idx < len(clean_opts):
                    ans = clean_opts[raw_idx]
                if not ans and clean_opts:
                    ans = clean_opts[0]
                if ans and ans not in clean_opts:
                    clean_opts = [ans] + clean_opts

                # Keep localized arrays aligned with the pre-shuffle canonical option order.
                opts_en = p.get("options_en") if isinstance(p.get("options_en"), list) else []
                opts_tr = p.get("options_tr") if isinstance(p.get("options_tr"), list) else []
                opts_en = [str(x).strip() for x in opts_en] if len(opts_en) == len(clean_opts) else list(clean_opts)
                opts_tr = [str(x).strip() for x in opts_tr] if len(opts_tr) == len(clean_opts) else list(clean_opts)

                # Stable deterministic shuffle: avoids the historical all-A pattern while
                # producing the same persisted order for the same generated question.
                if len(clean_opts) > 1:
                    seed = f"{topic}|{p.get('prompt','')}|{ans}"
                    order = sorted(
                        range(len(clean_opts)),
                        key=lambda i: hashlib.sha256(f"{seed}|{i}".encode("utf-8")).hexdigest(),
                    )
                    clean_opts = [clean_opts[i] for i in order]
                    opts_en = [opts_en[i] for i in order]
                    opts_tr = [opts_tr[i] for i in order]

                p["options"] = clean_opts
                p["options_en"] = opts_en
                p["options_tr"] = opts_tr
                p["answer"] = ans
                p["correct_index"] = clean_opts.index(ans) if ans in clean_opts else -1
                p["distractors"] = [o for o in clean_opts if o != ans]

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
                        _expl_en = it.get("explanation_en") or it.get("explanation") or it.get("tip") or ""
                        clean_items.append({
                            "term": it.get("term") or it.get("word") or "",
                            "phonetic": it.get("phonetic") or it.get("phonetic_en") or "",
                            "phonetic_en": it.get("phonetic_en") or it.get("phonetic") or "",
                            "phonetic_tr": it.get("phonetic_tr") or "",
                            "translation": it.get("translation") or it.get("meaning") or it.get("english") or "",
                            "translation_en": it.get("translation_en") or it.get("translation") or it.get("meaning") or it.get("english") or "",
                            "translation_tr": it.get("translation_tr") or "",
                            "example": it.get("example") or "",
                            "example_en": it.get("example_en") or it.get("translation_example") or "",
                            "example_tr": it.get("example_tr") or "",
                            "explanation": _expl_en,
                            "explanation_en": _expl_en,
                            "explanation_tr": it.get("explanation_tr") or ""
                        })
                p["items"] = clean_items

            # Ensure comparisons is always a list of well-formed objects with bilingual support (no synthetic metadata)
            if "comparisons" in p and isinstance(p["comparisons"], list):
                norm_comps = []
                for c in p["comparisons"]:
                    if isinstance(c, dict):
                        tgt = str(c.get("target") or c.get("sentence") or c.get("text") or "").strip()
                        ev = str(c.get("source_evidence") or "").strip()
                        prov = str(c.get("provenance") or "").strip()
                        if tgt:
                            if not ev:
                                ev = f"Pedagogical contrast for {tgt}"
                            if prov not in ("source_explicit", "source_inherent"):
                                prov = "source_inherent" if "Pedagogical contrast" in ev else "source_explicit"
                            norm_comps.append({
                                "context": str(c.get("context") or "").strip(),
                                "context_tr": str(c.get("context_tr") or "").strip(),
                                "target": tgt,
                                "translation": str(c.get("translation") or c.get("meaning") or "").strip(),
                                "translation_tr": str(c.get("translation_tr") or "").strip(),
                                "note": str(c.get("note") or c.get("explanation") or "").strip(),
                                "note_tr": str(c.get("note_tr") or "").strip(),
                                "scope": str(c.get("scope") or "").strip().lower(),
                                "source_evidence": ev,
                                "source_taught": str(c.get("source_taught") or tgt).strip(),
                                "provenance": prov
                            })
                p["comparisons"] = norm_comps

            # Ensure grammar rules preserve authentic, non-synthetic fields with source provenance
            if "rules" in p and isinstance(p["rules"], list):
                norm_rules = []
                for r in p["rules"]:
                    if isinstance(r, dict):
                        r_name = str(r.get("rule") or "").strip()
                        r_expl = str(r.get("explanation") or "").strip()
                        ev = str(r.get("source_evidence") or "").strip()
                        prov = str(r.get("provenance") or "").strip()
                        if (r_name or r_expl):
                            if not ev:
                                ev = f"Core pedagogical rule for {r_name or topic}"
                            if prov not in ("source_explicit", "source_inherent"):
                                prov = "source_inherent" if "Core pedagogical rule" in ev else "source_explicit"
                            norm_rules.append({
                                "rule": r_name,
                                "rule_tr": str(r.get("rule_tr") or "").strip(),
                                "explanation": r_expl,
                                "explanation_tr": str(r.get("explanation_tr") or "").strip(),
                                "example": str(r.get("example") or "").strip(),
                                "example_en": str(r.get("example_en") or "").strip(),
                                "example_tr": str(r.get("example_tr") or "").strip(),
                                "analysis": str(r.get("analysis") or "").strip(),
                                "analysis_tr": str(r.get("analysis_tr") or "").strip(),
                                "scope": str(r.get("scope") or "").strip().lower(),
                                "source_evidence": ev,
                                "source_taught": str(r.get("source_taught") or r_name).strip(),
                                "provenance": prov
                            })
                p["rules"] = norm_rules

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

        # AULA_BILINGUAL_PRONUNCIATION_GATE_V21
        _topic_l = str(topic or '').lower()
        _is_pronunciation_topic = any(k in _topic_l for k in (
            'alphabet', 'alfabeto', 'alfabe', 'letter', 'letters', 'harf',
            'pronunciation', 'pronunciación', 'telaffuz', 'phonetic', 'fonetik',
            'vowel', 'consonant', 'vocal', 'consonante', 'sound', 'sesli', 'sessiz'
        ))
        if _is_pronunciation_topic:
            _missing = []
            for _pg in data.get('pages', []):
                if not isinstance(_pg, dict):
                    continue
                for _it in _pg.get('items', []) if isinstance(_pg.get('items', []), list) else []:
                    if not isinstance(_it, dict):
                        continue
                    _term = str(_it.get('term') or _it.get('word') or '').strip()
                    if not _term:
                        continue
                    _en = str(_it.get('explanation_en') or _it.get('explanation') or '').strip()
                    _tr = str(_it.get('explanation_tr') or '').strip()
                    if not _en or not _tr:
                        _missing.append(_term)
                        if not _en:
                            _it['explanation_en'] = str(_it.get('explanation') or f"Authoritative sound value and pronunciation for '{_term}'.").strip()
                        if not _tr:
                            _it['explanation_tr'] = f"'{_term}' ifadesinin standart ses değeri ve telaffuz rehberi."
            if _missing:
                print(f"[LESSON-GATE] Infilled persisted bilingual pronunciation for {len(_missing)} items: {_missing[:8]}", flush=True)

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
                _expl_en = v.get("explanation_en") or v.get("explanation") or v.get("tip") or ""
                clean_items.append({
                    "term": v.get("term") or v.get("word") or "",
                    "phonetic": v.get("phonetic") or v.get("phonetic_en") or "",
                    "phonetic_en": v.get("phonetic_en") or v.get("phonetic") or "",
                    "phonetic_tr": v.get("phonetic_tr") or "",
                    "translation": v.get("translation") or v.get("meaning") or "",
                    "translation_en": v.get("translation_en") or v.get("translation") or v.get("meaning") or "",
                    "translation_tr": v.get("translation_tr") or "",
                    "example": v.get("example") or "",
                    "example_en": v.get("example_en") or v.get("translation_example") or "",
                    "example_tr": v.get("example_tr") or "",
                    "explanation": _expl_en,
                    "explanation_en": _expl_en,
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
            "options_en": mcq.get("options_en") or opts,
            "options_tr": mcq.get("options_tr") or opts,
            "distractors": distrs,
            "answer": ans,
            "correct_index": (opts.index(ans) if ans in opts else -1),
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

        # MCQ options (when options are instructional explanations in English)
        raw_opts = page.get("options") or page.get("choices")
        if isinstance(raw_opts, list) and len(raw_opts) >= 2:
            existing_tr = page.get("options_tr")
            if not existing_tr or not isinstance(existing_tr, list) or len(existing_tr) != len(raw_opts):
                english_indicators = {
                    "as", "a", "an", "the", "in", "on", "of", "to", "for", "with", "is", "are",
                    "by", "that", "this", "it", "not", "when", "indicates", "denotes", "functions",
                    "used", "pronounced", "vowel", "consonant", "noun", "verb", "sound", "stress",
                    "letter", "syllable", "always", "never", "only", "shows", "expresses"
                }
                is_metalang = any(
                    isinstance(opt, str) and (
                        len(opt.split()) >= 3 or
                        any(w.lower().strip(".,!?:;\"'()") in english_indicators for w in opt.split())
                    )
                    for opt in raw_opts
                )
                if is_metalang:
                    page["options_tr"] = [str(o) for o in raw_opts]
                    for o_idx, opt in enumerate(raw_opts):
                        if isinstance(opt, str) and opt.strip():
                            ref_map.append((f"pages.{p_idx}.options_tr.{o_idx}", opt))
        
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

def _content_length(value) -> int:
    """Length of a string measured in information, not codepoints.

    The release gates below ask whether a page carries enough teaching content.
    Counting characters answers that question differently depending on the script:
    a logographic or syllabic character carries roughly a whole morpheme, so one
    sentence of Chinese or Japanese is a third the length of the same sentence in
    an alphabetic script. Measured in raw codepoints, identical content passed the
    gate in German and Russian and failed it in Chinese and Japanese - a lesson
    could fall back to a review notice purely because of the writing system.

    Weighting by script density removes that bias without knowing any language:
    alphabetic text is unchanged (so no existing behaviour moves), and dense
    scripts are counted at the rate at which they actually carry meaning.
    """
    text = str(value or "")
    if not text:
        return 0
    total = 0
    for ch in text:
        cp = ord(ch)
        dense = (
            0x3040 <= cp <= 0x30FF      # Hiragana, Katakana
            or 0x3400 <= cp <= 0x4DBF   # CJK Unified Extension A
            or 0x4E00 <= cp <= 0x9FFF   # CJK Unified Ideographs
            or 0xF900 <= cp <= 0xFAFF   # CJK Compatibility Ideographs
            or 0xAC00 <= cp <= 0xD7AF   # Hangul syllables
            or 0x20000 <= cp <= 0x2FA1F  # CJK Extensions B-F
        )
        total += 3 if dense else 1
    return total


def _is_substantive_page(page: dict) -> bool:
    """Checks if a page contains genuine educational content rather than only titles/blank shells."""
    if not isinstance(page, dict):
        return False
    # Overview / Grammar text
    text = str(page.get("text") or page.get("text_tr") or page.get("text_en") or "").strip()
    if _content_length(text) >= 20:
        return True
    # Vocabulary items
    items = page.get("items") or page.get("vocabulary") or page.get("words")
    if isinstance(items, list):
        valid_items = [it for it in items if isinstance(it, dict) and (it.get("term") or it.get("word"))]
        if len(valid_items) >= 2:
            return True
    # Grammar rules or comparisons
    rules = page.get("rules") or page.get("grammar_rules")
    if isinstance(rules, list):
        valid_rules = [r for r in rules if isinstance(r, dict) and (r.get("rule") or r.get("explanation"))]
        if len(valid_rules) >= 1:
            return True
    comps = page.get("comparisons") or page.get("contrasts")
    if isinstance(comps, list) and len(comps) >= 1:
        return True
    # Dialogue turns
    dialogue = page.get("dialogue") or page.get("conversations")
    if isinstance(dialogue, list):
        valid_turns = [d for d in dialogue if isinstance(d, dict) and (d.get("text") or d.get("line"))]
        if len(valid_turns) >= 2:
            return True
    # Formative Assessment / MCQ
    prompt = page.get("prompt") or page.get("prompt_tr") or page.get("prompt_en") or page.get("question")
    opts = page.get("options") or page.get("choices")
    if prompt and isinstance(opts, list) and len(opts) >= 2:
        return True
    return False

# How many pages of real content a lesson must carry to be publishable.
#
# ONE number, read by both the gate that decides whether to retry a generation and
# the assembler that decides whether the result is complete. They used to disagree
# - the gate accepted two pages, the assembler required three - so a lesson that
# produced exactly two landed in the gap between them: accepted without retrying,
# then immediately marked review-required and published with a review notice
# stapled to the real content it had produced. That is the worst of both outcomes,
# and it spent none of the three attempts the topic was entitled to. A lesson the
# assembler will not accept is now one the gate retries.
MIN_SUBSTANTIVE_PAGES = 3


def _is_substantive_lesson(data: dict) -> bool:
    """Checks if a lesson structure has real educational substance across multiple pages."""
    if not isinstance(data, dict):
        return False
    pages = data.get("pages")
    if not isinstance(pages, list) or len(pages) == 0:
        return False
    substantive_pages = [p for p in pages if _is_substantive_page(p)]
    if len(substantive_pages) < MIN_SUBSTANTIVE_PAGES:
        return False
    # Must contain at least one page with items, rules, or text
    has_core = any(
        (p.get("items") or p.get("rules") or p.get("dialogue")
         or _content_length(str(p.get("text", "")).strip()) >= 30)
        for p in substantive_pages
    )
    return has_core

def _lesson_retry_note(norm_dict, truncated: bool) -> str:
    """Say what the rejected attempt was missing, in the schema's own terms.

    Lives beside `_is_substantive_lesson` so the description and the gate that
    produced it cannot drift: if the gate changes what it requires, this changes
    with it. It names only structural facts the gate itself measured - how many
    pages came back, how many carried content, whether the output was cut off -
    and never anything about the target language, so it is as true for Japanese
    as for Spanish and needs no per-language knowledge to write.
    """
    if truncated:
        return (
            "Your previous answer was cut off before the JSON closed, so none of it could be used. "
            "The output limit has been raised. Return the same lesson, complete and valid JSON, "
            "and if the topic is a large closed inventory, keep it complete rather than padding "
            "any single entry."
        )
    if not isinstance(norm_dict, dict):
        return (
            "Your previous answer could not be parsed as JSON and was discarded. "
            "Return one valid JSON object only: no markdown fences, no commentary outside the JSON."
        )
    pages = norm_dict.get("pages")
    if not isinstance(pages, list) or not pages:
        return (
            "Your previous answer contained no `pages` array and was discarded. "
            "Return the full lesson under `pages`, following the output schema exactly."
        )
    substantive = sum(1 for p in pages if _is_substantive_page(p))
    return (
        f"Your previous answer was discarded: it returned {len(pages)} page(s), of which "
        f"{substantive} carried actual teaching content. Every page must carry real content in "
        "its own right - explanatory `text`, or `items` with terms, or `rules`, or `dialogue` - "
        "not a title with an empty body. Teach the topic fully this time."
    )


def _ensure_minimum_lesson_structure(lesson_dict: dict, topic: str, language: str, level: str = 'A1', material_language: str = "tr") -> dict:
    """Keep every substantive page a real generation produced; never pad a real
    lesson with synthesized filler.

    Padding a partially successful lesson with generic scaffolding used to publish
    structurally valid but pedagogically empty pages (topic titles used as
    vocabulary rows, "Basic form", CEFR-meta MCQs). A short real lesson plus an
    explicit review notice is honest; a padded one is not.
    """
    if not isinstance(lesson_dict, dict) or not isinstance(lesson_dict.get("pages"), list):
        return synthesize_substantive_lesson(topic, "concept", language, level, material_language=material_language)

    pages = [p for p in lesson_dict["pages"] if isinstance(p, dict) and _is_substantive_page(p)]
    lesson_dict["pages"] = pages
    if len(pages) >= MIN_SUBSTANTIVE_PAGES:
        return lesson_dict

    if pages:
        lesson_dict["_review_required"] = True
        lesson_dict["_review_reason"] = "incomplete-generation"
        if not any(p.get("type") == "notice" for p in pages):
            pages.append(_review_notice_page(topic, language, level, material_language, reason="incomplete"))
        return lesson_dict

    return synthesize_substantive_lesson(topic, "concept", language, level, material_language=material_language)


def _review_notice_page(topic: str, language: str, level: str, material_language: str = "tr", reason: str = "unavailable") -> dict:
    """An honest, clearly-labelled teacher-facing notice.

    States plainly that automatic generation did not produce publishable material.
    Contains NO invented vocabulary, pronunciation, rules or assessment items:
    fabricated scaffolding is worse than an acknowledged gap, because a teacher
    cannot tell it apart from real content.
    """
    t_clean = str(topic or "").strip() or "this topic"
    body_en = (
        f"Automatic generation did not produce publishable {language} material for '{t_clean}' at CEFR {level}.\n"
        "This page is a placeholder for the teacher: no vocabulary, pronunciation, rules or exercises "
        "have been invented for it.\n"
        "Regenerate this topic, or author it manually before classroom use."
    )
    body_tr = (
        f"'{t_clean}' konusu için CEFR {level} düzeyinde yayımlanabilir {language} materyali otomatik olarak üretilemedi.\n"
        "Bu sayfa öğretmen için bir yer tutucudur: bu konu adına hiçbir kelime, telaffuz, kural veya alıştırma uydurulmamıştır.\n"
        "Sınıfta kullanmadan önce bu konuyu yeniden üretin veya elle hazırlayın."
    )
    return {
        "type": "notice",
        "title": f"Review required: {t_clean}",
        "title_tr": f"İnceleme gerekli: {t_clean}",
        "text": body_en,
        "text_tr": body_tr,
        "_review_required": True,
        "_review_reason": reason,
    }


def synthesize_substantive_lesson(topic: str, topic_type: str, language: str, level: str = 'A1', source_text: str = None, material_language: str = "tr") -> dict:
    """Deterministic $0 fallback, used only when model generation produced nothing usable.

    Historically this emitted four pages of confident-looking scaffolding
    ("Basic form", topic titles used as vocabulary rows, invented IPA, and an MCQ
    whose keyed answer described the CEFR level rather than the language). That is
    structurally substantive but pedagogically empty, and it published as though it
    were real teaching material.

    The fallback now does exactly two things: it surfaces whatever genuine source
    material was supplied, and it states clearly that the rest requires review. It
    never invents target-language content.
    """
    t_clean = str(topic or "").strip() or "Core Concepts"

    pages = [_review_notice_page(t_clean, language, level, material_language, reason="generation-failed")]

    # Real source text supplied by the teacher is genuine content: preserve it
    # verbatim, clearly labelled as an unprocessed extract.
    if source_text and isinstance(source_text, str) and len(source_text.strip()) > 30:
        lines = [ln.strip() for ln in source_text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        if lines:
            excerpt = "\n".join(f"\u2022 {ln}" for ln in lines[:8])
            pages.append({
                "type": "overview",
                "title": f"Source extract: {t_clean}",
                "title_tr": f"Kaynak alıntısı: {t_clean}",
                "text": "Unprocessed extract from the supplied source material:\n" + excerpt,
                "text_tr": "Yüklenen kaynak materyalden işlenmemiş alıntı:\n" + excerpt,
                "_review_required": True,
            })

    lesson_dict = {
        "pages": pages,
        "_review_required": True,
        "_review_reason": "generation-failed",
        "_synthetic_placeholder": True,
    }
    return _sanitize_deep_bilingual(lesson_dict)


def _claim_verifier_enabled() -> bool:
    """Bounded claim verification is on by default and can be disabled per deployment."""
    return str(os.getenv("AULAAI_CLAIM_VERIFIER", "1")).strip().lower() not in ("0", "false", "off", "no")


def _verify_absolute_claims(data, claims, language, level, material_language="tr"):
    """One bounded model call that checks ONLY claims a deterministic pass flagged
    as scope-risky: hard absolute or deontic wording, a near-universal/exception-framed
    claim whose named exception set the lesson's own evidence shows is incomplete,
    or a categorical claim that nearby lesson content materially weakens.

    Deterministic code can detect the SHAPE of these claims, can detect a genuine
    contradiction against the lesson's own evidence, and can tell a structural
    rule from a contextual convention well enough to route them differently. It
    cannot compose the linguistically correct restatement, and it cannot know
    whether a given social convention is truly universal in the target culture.
    This is the one place where that gap is closed, and it is deliberately narrow:

      * it runs only when a deterministic detector found a claim it could not
        itself certify, so an ordinary, internally-consistent lesson pays nothing;
      * it is ONE call for every flagged claim in the lesson, never one per claim;
      * the payload carries only the flagged claim strings, their claim domain and
        same-lesson evidence, never the whole lesson;
      * the model may only rescope or correct a flagged claim - it cannot add
        pages, vocabulary, rules or examples;
      * a failed or malformed response leaves the lesson exactly as generated.

    The prompt and payload are built in services.publication_invariants, next to
    the detectors that decide what gets flagged, so the metadata a detector
    attaches and the instructions the reviewer reads cannot drift apart.
    """
    if not claims:
        return data
    try:
        from services.publication_invariants import build_claim_review_request
    except Exception as exc:
        print(f"[CLAIM-SCOPE] verification skipped, request builder unavailable: {exc}")
        return data
    system, items = build_claim_review_request(claims, language, level)
    payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    try:
        review = _call_ai(
            [{"role": "system", "content": system},
             {"role": "user", "content": payload}],
            model=MODEL_STRUCTURAL,
            max_tokens=1000,
            temperature=0.0,
            json_mode=True,
            allow_fallback=False,
            cost_stage=_COST_STAGE_CLAIM,
            cost_subject=f"{len(items)} claim(s)",
            # Templated on language and level only - the flagged claims travel in
            # the user payload - so this prompt repeats across every lesson in the
            # class that trips a detector, and clears the caching threshold.
            cache_system=True,
        )
    except Exception as exc:
        print(f"[CLAIM-SCOPE] verification skipped after error: {exc}")
        return data
    if not isinstance(review, dict):
        return data

    from services.publication_invariants import normalize_claim_record, set_by_path

    applied = 0
    for verdict in (review.get("verdicts") or [])[:24]:
        if not isinstance(verdict, dict):
            continue
        action = str(verdict.get("action") or "").strip().lower()
        if action not in ("rescope", "correct", "omit"):
            continue
        try:
            claim = normalize_claim_record(claims[int(verdict.get("id"))])
        except Exception:
            continue

        # An unconfirmable field is better absent than invented. This is the only
        # way a repair may shorten a field to nothing, and only where the detector
        # said so - a transcription the reviewer cannot complete honestly.
        if action == "omit":
            if claim["repair"] != "omit_ok":
                continue
            if set_by_path(data, claim.get("path", ""), ""):
                applied += 1
            continue

        value = verdict.get("value")
        if not isinstance(value, str) or not value.strip():
            continue

        # Size the repair against the text that will actually be OVERWRITTEN, not
        # against the context the reviewer was shown. For prose they are the same
        # string; for a data field they are not, and measuring against the context
        # rejected correct repairs for being "too short".
        original = claim["field_value"] or claim.get("text") or ""
        floor = 1 if claim["repair"] == "omit_ok" else 12
        if len(value) < max(floor, int(len(original) * 0.5)) or len(value) > int(len(original) * 1.6) + 60:
            continue
        if set_by_path(data, claim.get("path", ""), value):
            applied += 1
    if applied:
        print(f"[CLAIM-SCOPE] rescoped {applied} absolute claim(s) out of {len(claims)} flagged")
    return data


def _material_publication_release(lesson_dict, topic, language, level, material_language="tr"):
    """Canonical deterministic publication boundary for generated material."""
    try:
        from services.publication_invariants import (
            apply_publication_invariants,
            collect_reviewable_claims,
        )
    except Exception as exc:
        print(f"[PUBLICATION] invariants unavailable: {exc}")
        return lesson_dict
    if not isinstance(lesson_dict, dict):
        return lesson_dict
    data = apply_publication_invariants(
        lesson_dict, language=language, material_language=material_language, topic=topic, copy=False
    )
    if _claim_verifier_enabled() and is_ai_available():
        # Every deterministic scope detector feeds ONE aggregated, de-duplicated
        # list: absolute/deontic wording that the generator may not certify itself,
        # a named exception set narrower than the lesson's own evidence, and a
        # categorical claim that nearby lesson content contradicts. One bounded
        # call reviews all of them together - never one call per detector.
        claims = collect_reviewable_claims(data, material_language=material_language)
        # A word this class has already taught, transcribed differently here, is a
        # question about the language that only the reviewer can answer - and this
        # lesson is the last moment anyone can ask it before the disagreement is
        # persisted. It joins the SAME bounded call, so cross-lesson consistency
        # costs no extra request. The established transcription travels as a rival
        # candidate rather than as the answer: it is exactly as likely to be the
        # wrong one, and anchoring the reviewer on it would spread an early error.
        try:
            from services.class_lexicon import collect_class_phonetic_conflicts
            conflicts = collect_class_phonetic_conflicts(data)
        except Exception as exc:
            print(f"[CLASS-LEXICON] conflict detection unavailable: {exc}")
            conflicts = []
        if conflicts:
            print(f"[CLASS-LEXICON] {len(conflicts)} cross-lesson transcription conflict(s) for '{topic}'")
        claims = (claims or []) + conflicts
        if claims:
            data = _verify_absolute_claims(data, claims, language, level, material_language)
            # Re-run deterministic invariants so any rescoped prose is re-checked.
            data = apply_publication_invariants(
                data, language=language, material_language=material_language, topic=topic, copy=False
            )
    # Register only after review, so what this class treats as established is the
    # reviewed value wherever there was one to review.
    try:
        from services.class_lexicon import register_lesson
        register_lesson(data, source=str(topic))
    except Exception as exc:
        print(f"[CLASS-LEXICON] registration skipped: {exc}")
    return data



def _material_clean_scalar(value):
    """Deterministic last-mile cleanup for generated lesson strings."""
    if not isinstance(value, str):
        return value
    text = value
    text = text.replace("\ufffe", "").replace("\uffff", "").replace("\u200b", "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"(?i)\bO\s+PHYSIK\b", "", text)
    text = re.sub(r"(?i)\bPHYSIK\b", "", text)
    text = re.sub(r"(?i)\b(?:DEBUG_ARTIFACT|PLACEHOLDER_TEXT|LOREM_IPSUM)\b", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def _material_deterministic_guard(lesson_dict):
    """Apply zero-cost structural QA without inventing linguistic content."""
    if not isinstance(lesson_dict, dict) or not isinstance(lesson_dict.get("pages"), list):
        return lesson_dict

    def clean_deep(obj):
        if isinstance(obj, dict):
            return {k: clean_deep(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean_deep(v) for v in obj]
        if isinstance(obj, str):
            return _material_clean_scalar(obj)
        return obj

    data = clean_deep(lesson_dict)
    clean_pages = []
    seen_mcq_prompts = set()

    for page in data.get("pages", []):
        if not isinstance(page, dict):
            continue

        is_mcq = page.get("type") == "mcq" or bool(page.get("prompt"))
        if is_mcq:
            prompt = str(page.get("prompt") or "").strip()
            answer = str(page.get("answer") or "").strip()
            options = page.get("options") or []
            distractors = page.get("distractors") or []

            if not options and answer and isinstance(distractors, list):
                options = [answer] + list(distractors)

            uniq = []
            seen = set()
            for opt in options if isinstance(options, list) else []:
                txt = str(opt).strip()
                key = unicodedata.normalize("NFKC", txt).casefold()
                if txt and key not in seen:
                    seen.add(key)
                    uniq.append(txt)

            ans_key = unicodedata.normalize("NFKC", answer).casefold()
            if answer and ans_key not in seen:
                uniq.insert(0, answer)

            if not prompt or not answer or len(uniq) != 4:
                continue

            prompt_key = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", prompt).casefold()).strip()
            if prompt_key in seen_mcq_prompts:
                continue
            seen_mcq_prompts.add(prompt_key)

            page["options"] = uniq
            page["distractors"] = [o for o in uniq if unicodedata.normalize("NFKC", o).casefold() != ans_key]
            if len(page["distractors"]) != 3:
                continue

        clean_pages.append(page)

    data["pages"] = clean_pages
    return data


# _apply_material_patch lived here: it existed only to apply that audit's patches
# _material_publication_audit lived here: a second, independent semantic pass over
# the whole lesson that patched arbitrary fields by path. It has had no caller since
# the publication boundary became the single reviewed surface, and dead code that
# makes a paid model call is not free - it is one accidental call site away from
# doubling the semantic cost of every lesson. Removed rather than left loaded.

def _material_release_integrity_v37(data, language, level, material_language="tr"):
    """Deterministic final fail-closed validation; semantic work is done by the single publication audit."""
    from services.material_quality_guard import enforce_material_integrity
    return enforce_material_integrity(data, language=language, material_language=material_language) if isinstance(data, dict) else data

def generate_full_lesson(topic, topic_type, language, count=6, level='A1', source_text=None, material_language="tr", unit_index=None, unit_total=None, topics_completed=0):
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
    # AULAAI_CANONICAL_MATERIAL_PROMPT
    from services.material_generation_prompt import build_material_prompts
    # The language budget for this lesson's own assessment items. Derived from
    # CEFR and position in the course - deterministic, no model call, and no
    # dependency on other topics, which matters because topics are generated
    # concurrently and no sibling lesson exists yet when this one is written.
    from services.assessment_scope import progression_envelope
    assessment_budget = progression_envelope(
        level=level, language=language,
        unit_index=unit_index, unit_total=unit_total,
        topics_completed=topics_completed,
    )
    system_prompt, user_prompt = build_material_prompts(
        language=language,
        level=level,
        topic=topic,
        topic_type=topic_type,
        official_institution=official_institution,
        source_text=source_text,
        assessment_budget=assessment_budget,
    )

    lesson_dict = None
    budget = LESSON_OUTPUT_TOKENS
    retry_note = ""
    for attempt_idx in range(1, 4):
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-START] '{topic}' ({topic_type}) {level} {language} (attempt {attempt_idx}/3, max_tokens={budget}) → {MODEL_LESSON}\n")

        temp = 0.2 if attempt_idx == 1 else (0.25 if attempt_idx == 2 else 0.3)
        call_stats: Dict[str, Any] = {}
        # A retry that resends the identical prompt asks the same question again
        # and is answered the same way: a topic that failed the release gate once
        # failed it three times and still published a fallback, at three times the
        # price of a lesson that worked. Telling the next attempt which part of the
        # schema came back empty costs a few dozen tokens and is the only thing in
        # the retry that carries new information. It is appended AFTER the system
        # prompt so the cacheable prefix every topic shares is left untouched.
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        if retry_note:
            messages.append({"role": "user", "content": retry_note})
        raw_dict = _call_ai(
            messages,
            model=MODEL_LESSON,
            max_tokens=budget,
            temperature=temp,
            json_mode=True,
            allow_fallback=False,
            usage_dict=call_stats,
            cost_stage=_COST_STAGE_LESSON,
            cost_subject=str(topic),
            # The system prompt is identical for every topic in a class: it
            # interpolates language, level and institution, all fixed for the
            # build. It is ~8.1k tokens and is sent 30+ times per class, which
            # makes it the single largest repeated input the pipeline pays for.
            cache_system=True,
        )
        norm_dict = _normalize_lesson_pages(raw_dict, topic, language, level)
        # An assessment item that cannot state its task in the language being
        # published is a generation defect the generator can still fix, and at this
        # point it has attempts left in which to fix it. Treated as a failed
        # attempt so those attempts are spent, rather than as a publishable lesson
        # whose questions a reader of this track cannot read. No extra call and no
        # extra attempt: this only decides how the attempts already budgeted are used.
        _track_gaps = []
        if norm_dict and isinstance(norm_dict, dict):
            try:
                from services.publication_invariants import assessment_track_violations
                _track_gaps = assessment_track_violations(norm_dict, material_language)
            except Exception:
                _track_gaps = []
        if norm_dict and isinstance(norm_dict, dict) and _is_substantive_lesson(norm_dict) and not _track_gaps:
            lesson_dict = _ensure_minimum_lesson_structure(norm_dict, topic, language, level, material_language=material_language)
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-RESULT] '{topic}' → {len(lesson_dict['pages'])} pages on attempt {attempt_idx}\n")
            break
        else:
            # This attempt was paid for and is about to be discarded. Say so in
            # the ledger: a topic that burns three generations and still publishes
            # a fallback costs three lessons, and that has to be visible as waste
            # rather than as three ordinary lesson calls.
            _cost_mark(call_stats.get("cost_entry"), _COST_REJECTED)
            page_count = len(norm_dict.get("pages", [])) if isinstance(norm_dict, dict) else 0
            # A lesson that was cut off at the ceiling does not fail because the
            # model is unwilling or the topic is hard - it fails because the answer
            # did not fit. Retrying at the same ceiling reproduces that outcome
            # exactly, which is how a whole class of topic (paradigm tables, closed
            # inventories, anything whose point is a large set) failed identically
            # on every attempt and fell back. Give the next attempt the room the
            # answer needed instead of nudging temperature, which cannot help.
            truncated = bool(call_stats.get("truncated"))
            retry_note = _lesson_retry_note(norm_dict, truncated)
            if _track_gaps and not truncated:
                retry_note = (
                    "Your previous answer was discarded: %d multiple-choice item(s) gave their "
                    "question only in a language this course does not use for instructions. "
                    "Every assessment item needs its question written in the instructional "
                    "language of this course, in the `prompt_tr` and `prompt_en` fields. Keep "
                    "the answer options exactly as they are - they belong in the target "
                    "language." % len(_track_gaps)
                )
            if truncated and budget < LESSON_OUTPUT_TOKENS_MAX:
                budget = min(budget * 2, LESSON_OUTPUT_TOKENS_MAX)
                reason = f"output truncated at the ceiling; raising max_tokens to {budget}"
            else:
                reason = f"yielded {page_count} substantive page(s)"
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-RETRY] '{topic}' {reason} on attempt {attempt_idx}/3 "
                        f"(finish_reason={call_stats.get('finish_reason') or 'unknown'}). Retrying {MODEL_LESSON}...\n")
            time.sleep(0.75 * attempt_idx)

    if not lesson_dict or not isinstance(lesson_dict, dict) or not _is_substantive_lesson(lesson_dict):
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-SYNTHESIZE] '{topic}' failed model generation; creating guaranteed substantive fallback.\n")
        lesson_dict = synthesize_substantive_lesson(topic, topic_type, language, level, source_text=source_text, material_language=material_language)

    # Structural + Unicode integrity runs BEFORE semantic review, not after it.
    # Running it afterwards (as this pipeline used to) meant a guard could rewrite
    # lexical fields and prune pages after the bounded reviewer had already passed
    # judgement on the text, so what shipped was not what was reviewed.
    lesson_dict = _material_release_integrity_v37(lesson_dict, language, level, material_language=material_language)
    lesson_dict = _material_publication_release(lesson_dict, topic, language, level, material_language=material_language)

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

    # Native bilingual lesson fields are authoritative. A second translation
    # model pass is intentionally disabled: it adds cost/latency and can overwrite
    # the pedagogy produced by the lesson model.
    if material_language in ["tr", "all"] and not has_turkish:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-BILINGUAL-NATIVE] '{topic}' has incomplete native Turkish fields; no secondary translator will run.\n")

    # Nothing runs after the publication boundary. Text-layer sanitation used to
    # live here as a separate final step; it is now one of the publication
    # invariants, so it also covers material that reaches the renderer without
    # passing through generation at all.
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

# AULAAI_RELEASE_HARDENING_V52
