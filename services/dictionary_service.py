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
    AI-First dictionary logic with persistent caching.
    """
    word = word.strip().lower()
    lang_name = lang_name.split('(')[0].strip()
    cache_key = f"{lang_name}_{word}"
    
    # 1. Check Cache
    if cache_key in AI_CACHE:
        cached = AI_CACHE[cache_key]
        # VALIDATION: If the cached result is just a fallback, ignore it and re-run
        is_fallback = "daily interaction" in cached.get("explanation", "").lower() or "simple sentence" in cached.get("usage", "").lower()
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
    
    # 0. Hardcoded Sanity (For the most common student words in major languages)
    SANITY = {
        "tr": {"merhaba": "Hello / Hi", "teşekkür": "Thank you", "günaydın": "Good morning", "nasılsınız": "How are you?"},
        "es": {"hola": "Hello / Hi", "gracias": "Thank you", "buenos días": "Good morning", "cómo estás": "How are you?"},
        "fr": {"bonjour": "Hello / Good morning", "merci": "Thank you", "ça va": "How are you? / It's going well"},
        "it": {"ciao": "Hello / Hi / Goodbye", "grazie": "Thank you", "buongiorno": "Good morning / Good day"}
    }
    
    lang_sanity = SANITY.get(lang_code, {})
    if word in lang_sanity:
        return {
            "word": word, "phonetic": f"({lang_name})",
            "definitions": [{"partOfSpeech": "greeting", "definition": lang_sanity[word], "example": ""}],
            "source": "AulaAI Core"
        }

    # 1. Wiktionary Deep Scan
    wikt_result = _get_wiktionary_definition(word, lang_code)
    if not wikt_result.get("error") and wikt_result.get("definitions"):
        return wikt_result

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
    Uses the structured Definition API to find the specific language section.
    """
    try:
        conn = http.client.HTTPSConnection("en.wiktionary.org")
        path = f"/api/rest_v1/page/definition/{urllib.parse.quote(word)}"
        conn.request("GET", path)
        res = conn.getresponse()
        
        if res.status == 200:
            data = json.loads(res.read().decode())
            
            # data is a dict where keys are language names
            # We need to map our lang_code back to a full name for Wiktionary
            target_lang_name = next((k for k, v in LANG_MAP.items() if v == lang_code), "English").title()
            
            # Scan for the correct language section
            # Wiktionary uses full names like "Turkish", "Spanish", etc.
            sections = data.get(target_lang_name, [])
            if not sections and target_lang_name == "Turkish": 
                # Fallback for common naming variations
                sections = data.get("Turkish", []) or data.get("Ottoman Turkish", [])

            if sections:
                # Get the first definition from the first part of speech
                definitions = []
                for sec in sections[:2]:
                    pos = sec.get("partOfSpeech", "word")
                    for entry in sec.get("definitions", [])[:1]:
                        # Strip HTML tags from definition
                        raw_def = entry.get("definition", "")
                        clean_def = re.sub(r'<[^>]*>', '', raw_def)
                        definitions.append({
                            "partOfSpeech": pos,
                            "definition": clean_def,
                            "example": ""
                        })
                
                if definitions:
                    return {
                        "word": word,
                        "phonetic": f"({target_lang_name})",
                        "definitions": definitions,
                        "source": "Wiktionary Premium"
                    }
    except Exception as e:
        print(f"[DICT] Wiktionary Deep Scan failed: {e}")
    
    return {"error": "Definition not found", "word": word}

def clean_word(text):
    return re.sub(r'[^\w\s]', '', text).strip()
