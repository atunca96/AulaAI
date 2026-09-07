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

def clean_lookup_word(w):
    if not w: return ""
    return re.sub(r'[\u200e\u200f]', '', str(w)).strip(' \t\n\r"\'“”«»`').strip()

def get_definition(word, lang_name, context=None, target_lang="en"):
    """
    AI-First dictionary logic with persistent caching and high-priority sanity check.
    Supports both English and Turkish target languages.
    """
    raw_word = word.strip()
    norm_word = clean_lookup_word(raw_word).lower()
    clean_word_val = clean_lookup_word(raw_word)
    lang_name = lang_name.split('(')[0].strip()
    is_tr = (target_lang == "tr")
    cache_key = f"{lang_name}_{norm_word}_{target_lang}"
    
    # 0. HIGH PRIORITY SANITY (Bypass cache for most common words)
    SANITY = {
        "hola": {"en": "Hello / Hi", "tr": "Merhaba / Selam"},
        "gracias": {"en": "Thank you", "tr": "Teşekkürler"},
        "teşekkür": {"en": "Thank you", "tr": "Teşekkür"},
        "teşekkür ederim": {"en": "I thank you / Thank you", "tr": "Teşekkür ederim"},
        "zayıf": {"en": "Weak / Thin / Slender", "tr": "Zayıf / İnce"},
        "güzel": {"en": "Beautiful / Good / Nice", "tr": "Güzel / Hoş"},
        "merhaba": {"en": "Hello", "tr": "Merhaba"},
        "tamam": {"en": "OK / Fine", "tr": "Tamam"},
        "evet": {"en": "Yes", "tr": "Evet"},
        "hayır": {"en": "No", "tr": "Hayır"},
        "bilgisayar": {"en": "Computer", "tr": "Bilgisayar"},
        "öğrenci": {"en": "Student", "tr": "Öğrenci"},
        "okul": {"en": "School", "tr": "Okul"},
        "kitap": {"en": "Book", "tr": "Kitap"}
    }
    if norm_word in SANITY:
        meaning = SANITY[norm_word].get(target_lang, SANITY[norm_word]["en"])
        if is_tr:
            return {
                "explanation": f"'{clean_word_val}', '{meaning}' anlamına gelir.",
                "usage": "Günlük iletişimde yaygın olarak kullanılır.",
                "tip": "Bu, sizin için önceden doğruladığımız yüksek frekanslı bir kelimedir!",
                "source": "AulaAI Core"
            }
        else:
            return {
                "explanation": f"'{clean_word_val}' means '{meaning}'.",
                "usage": "Commonly used in daily interaction.",
                "tip": "This is a high-frequency word we've pre-verified for you!",
                "source": "AulaAI Core"
            }

    # 1. Check Cache with target_lang
    if cache_key in AI_CACHE:
        cached = AI_CACHE[cache_key]
        expl = cached.get("explanation", "").lower()
        is_fallback = "daily interaction" in expl or "specific quality" in expl or "surrounding sentence" in expl or "no definition found" in expl
        if not is_fallback:
            return {**cached, "source": "AulaAI Memory"}

    # Also check without target_lang suffix for backwards compatibility
    legacy_key = f"{lang_name}_{raw_word}"
    legacy_norm_key = f"{lang_name}_{norm_word}"
    if not is_tr:
        for lk in [legacy_key, legacy_norm_key]:
            if lk in AI_CACHE:
                cached = AI_CACHE[lk]
                expl = cached.get("explanation", "").lower()
                is_fallback = "daily interaction" in expl or "specific quality" in expl or "surrounding sentence" in expl or "no definition found" in expl
                if not is_fallback:
                    return {**cached, "source": "AulaAI Memory"}
    
    # 2. Call AI Brain in target_lang
    try:
        from services.ai_engine import ai_explain_word
        result = ai_explain_word(clean_word_val or raw_word, lang_name, context, material_language=target_lang)
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
