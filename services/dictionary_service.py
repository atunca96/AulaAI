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
    Intelligent router with multi-layer fallback.
    """
    word = word.strip().lower()
    lang_code = LANG_MAP.get(lang_name.lower(), "en")
    
    # 1. Wiktionary Deep Scan
    wikt_result = _get_wiktionary_definition(word, lang_code)
    if not wikt_result.get("error") and wikt_result.get("definitions"):
        return wikt_result

    # 2. MyMemory Translation
    try:
        conn = http.client.HTTPSConnection("api.mymemory.translated.net")
        path = f"/get?q={urllib.parse.quote(word)}&langpair={lang_code}|en"
        conn.request("GET", path)
        res = conn.getresponse()
        if res.status == 200:
            data = json.loads(res.read().decode())
            trans = data.get("responseData", {}).get("translatedText", "")
            if trans and trans.lower() != word.lower():
                return {
                    "word": word,
                    "phonetic": f"({lang_name})",
                    "definitions": [{"partOfSpeech": "translation", "definition": trans, "example": ""}],
                    "source": "Translation Engine"
                }
    except:
        pass

    return {"error": "No definition found in standard sources. Try AI Explain!", "word": word}

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
