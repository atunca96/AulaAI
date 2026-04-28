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
    Advanced translation-first router for 14 languages.
    """
    word = word.strip().lower()
    lang_code = LANG_MAP.get(lang_name.lower(), "en")
    
    # 1. Primary: MyMemory Translation API (Excellent for all 14 langs Word-to-Word)
    try:
        # Search Word -> English
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
                    "definitions": [{
                        "partOfSpeech": "translation",
                        "definition": trans,
                        "example": ""
                    }],
                    "source": "MyMemory Global"
                }
    except:
        pass

    # 2. Fallback: Wiktionary REST API (Standard Dictionary)
    return _get_wiktionary_definition(word, lang_code)

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
