import http.client
import json
import urllib.parse
import re
import os

# Mapping for AulaAI's 14 Languages
LANG_MAP = {
    "turkish": "tr", "spanish": "es", "french": "fr", "german": "de",
    "italian": "it", "portuguese": "pt", "russian": "ru", "arabic": "ar",
    "greek": "el", "persian": "fa", "english": "en", "turkish (ispanyolca)": "tr"
}

# Cache for AI results to minimize costs
AI_CACHE_FILE = "services/ai_dict_cache.json"
def _load_cache():
    try:
        if os.path.exists(AI_CACHE_FILE):
            with open(AI_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return {}

def _save_cache(cache):
    try:
        with open(AI_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except: pass

AI_CACHE = _load_cache()

def get_definition(word, lang_name, context=None):
    """
    AI-First dictionary logic with persistent caching and high-priority sanity check.
    """
    word = word.strip().lower()
    lang_name = lang_name.split('(')[0].strip()
    cache_key = f"{lang_name}_{word}"
    
    # 0. HIGH PRIORITY SANITY (Bypass cache for most common words)
    SANITY = {
        "hola": "Hello / Hi", "gracias": "Thank you", "teşekkür": "Thank you",
        "teşekkür ederim": "I thank you / Thank you", "zayıf": "Weak / Thin / Slender",
        "güzel": "Beautiful / Good / Nice", "merhaba": "Hello", "tamam": "OK / Fine",
        "evet": "Yes", "hayır": "No", "bilgisayar": "Computer", "öğrenci": "Student",
        "okul": "School", "kitap": "Book"
    }
    if word in SANITY:
        return {
            "explanation": f"'{word}' means '{SANITY[word]}'.",
            "usage": f"Commonly used in daily interaction.",
            "tip": "This is a high-frequency word we've pre-verified for you!",
            "source": "AulaAI Core"
        }

    # 1. Check Cache
    if cache_key in AI_CACHE:
        cached = AI_CACHE[cache_key]
        # VALIDATION: If the cached result is just a fallback, ignore it and re-run
        expl = cached.get("explanation", "").lower()
        is_fallback = "daily interaction" in expl or "specific quality" in expl or "surrounding sentence" in expl or "no definition found" in expl
        if not is_fallback:
            return {**cached, "source": "AulaAI Memory"}
    
    # 2. Call AI Brain
    try:
        from services.ai_engine import ai_explain_word
        result = ai_explain_word(word, lang_name, context)
        if result and "explanation" in result:
            AI_CACHE[cache_key] = result
            _save_cache(AI_CACHE)
            return {**result, "source": "AulaAI Brain"}
    except Exception as e:
        print(f"[DICT] AI Brain failed: {e}")
        
    # 3. Last Resort Fallback (Wiktionary/Translation)
    lang_code = LANG_MAP.get(lang_name.lower(), "en")

    # Try Wiktionary Deep Scan
    wikt = _get_wiktionary_definition(word, lang_code)
    if not wikt.get("error"):
        return {
            "explanation": wikt["definitions"][0]["definition"],
            "usage": "Found via Wiktionary Premium.",
            "tip": "AI was busy, but we found this high-quality definition for you!",
            "source": "AulaAI Core"
        }

    # 2. MyMemory Translation (With Iron Curtain Filter)
    try:
        conn = http.client.HTTPSConnection("api.mymemory.translated.net")
        path = f"/get?q={urllib.parse.quote(word)}&langpair={lang_code}|en"
        conn.request("GET", path)
        res = conn.getresponse()
        if res.status == 200:
            data = json.loads(res.read().decode())
            trans = data.get("responseData", {}).get("translatedText", "")
            
            # IRON CURTAIN: Reject non-English 'hallucinations'
            bad_words = ["ciao", "mondo", "bonjour", "hallo", "salut"]
            is_hallucination = any(bw in trans.lower() for bw in bad_words) and lang_code not in ["it", "fr", "de"]
            
            if trans and trans.lower() != word.lower() and not is_hallucination:
                return {
                    "word": word,
                    "phonetic": f"({lang_name})",
                    "definitions": [{"partOfSpeech": "translation", "definition": trans, "example": ""}],
                    "source": "Translation Engine"
                }
    except:
        pass

    return {"error": "Deep lookup needed. Try AI Explain!", "word": word}

def _get_wiktionary_definition(word, lang_code):
    """
    Uses the structured Definition API with case-insensitive retry.
    """
    # Try lowercase first
    result = _wikt_api_call(word.lower(), lang_code)
    if not result.get("error"):
        return result
        
    # If fails, try capitalized (good for German/Proper nouns)
    result = _wikt_api_call(word.capitalize(), lang_code)
    return result

def _wikt_api_call(word, lang_code):
    try:
        conn = http.client.HTTPSConnection("en.wiktionary.org")
        path = f"/api/rest_v1/page/definition/{urllib.parse.quote(word)}"
        conn.request("GET", path)
        res = conn.getresponse()
        
        if res.status == 200:
            data = json.loads(res.read().decode())
            target_lang_name = next((k for k, v in LANG_MAP.items() if v == lang_code), "English").title()
            sections = data.get(target_lang_name, [])
            
            if sections:
                definitions = []
                for sec in sections[:2]:
                    pos = sec.get("partOfSpeech", "word")
                    for entry in sec.get("definitions", [])[:1]:
                        raw_def = entry.get("definition", "")
                        clean_def = re.sub(r'<[^>]*>', '', raw_def)
                        definitions.append({"partOfSpeech": pos, "definition": clean_def, "example": ""})
                
                if definitions:
                    return {"word": word, "phonetic": f"({target_lang_name})", "definitions": definitions, "source": "Wiktionary"}
    except:
        pass
    return {"error": "not found"}

def clean_word(text):
    return re.sub(r'[^\w\s]', '', text).strip()
