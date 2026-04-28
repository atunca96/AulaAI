import http.client
import json
import urllib.parse
import re

# Mapping for AulaAI's 14 Languages
LANG_MAP = {
    "turkish": "tr", "spanish": "es", "french": "fr", "german": "de",
    "italian": "it", "portuguese": "pt", "russian": "ru", "arabic": "ar",
    "greek": "el", "persian": "fa", "english": "en", "turkish (ispanyolca)": "tr"
}

def get_definition(word, lang_name):
    """
    Intelligent router: Natural Dictionary -> English Wiktionary -> Translation.
    """
    word = word.strip().lower()
    lang_code = LANG_MAP.get(lang_name.lower(), "en")
    
    # 1. Primary: English Wiktionary (Highest Accuracy for Word -> English Definition)
    # This is the best source because it has sections for almost all 14 languages IN English.
    wikt_result = _get_wiktionary_definition(word, lang_code)
    if not wikt_result.get("error") and len(wikt_result.get("definitions", [])) > 0:
        # Check if the definition actually looks like a definition (not a 'No results' page)
        if "not found" not in wikt_result["definitions"][0]["definition"].lower():
            return wikt_result

    # 2. Secondary: MyMemory Translation (With 'Strict English' Filter)
    try:
        conn = http.client.HTTPSConnection("api.mymemory.translated.net")
        path = f"/get?q={urllib.parse.quote(word)}&langpair={lang_code}|en"
        conn.request("GET", path)
        res = conn.getresponse()
        if res.status == 200:
            data = json.loads(res.read().decode())
            trans = data.get("responseData", {}).get("translatedText", "")
            
            # Filter out non-English results (like 'Ciao Mondo')
            # Simple check: If the translation contains Italian/Spanish/etc words that aren't in common English
            if trans and trans.lower() != word.lower():
                # Hardcoded sanity for common errors
                if "ciao" in trans.lower() or "mondo" in trans.lower() and lang_code != "it":
                    pass # Ignore this result
                else:
                    return {
                        "word": word,
                        "phonetic": f"({lang_name})",
                        "definitions": [{"partOfSpeech": "translation", "definition": trans, "example": ""}],
                        "source": "Translation Engine"
                    }
    except:
        pass

    # 3. Last Resort: AI Explanation fallback
    return {"error": "Deep lookup needed", "word": word}

def _get_wiktionary_definition(word, lang_code):
    try:
        # We check English Wiktionary as it has the best foreign language sections
        conn = http.client.HTTPSConnection("en.wiktionary.org")
        path = f"/api/rest_v1/page/summary/{urllib.parse.quote(word)}"
        conn.request("GET", path)
        res = conn.getresponse()
        
        if res.status == 200:
            data = json.loads(res.read().decode())
            return {
                "word": data.get("title", word),
                "phonetic": "",
                "definitions": [{
                    "partOfSpeech": "definition",
                    "definition": data.get("extract", "No definition found."),
                    "example": ""
                }],
                "source": "Wiktionary"
            }
    except:
        pass
    
    return {"error": "Definition not found", "word": word}

def clean_word(text):
    return re.sub(r'[^\w\s]', '', text).strip()
