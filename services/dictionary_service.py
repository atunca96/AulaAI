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
    Intelligent router: Natural Dictionary -> Translation -> Fallback.
    """
    word = word.strip().lower()
    lang_code = LANG_MAP.get(lang_name.lower(), "en")
    
    # A. Special Case: English words should get definitions, not translations
    # If the word is very common English or we are in an English context
    
    # 1. Primary: Free Dictionary API (Most Natural)
    try:
        # We try the specific lang first
        conn = http.client.HTTPSConnection("api.dictionaryapi.dev")
        conn.request("GET", f"/api/v2/entries/{lang_code}/{urllib.parse.quote(word)}")
        res = conn.getresponse()
        if res.status == 200:
            data = json.loads(res.read().decode())
            entry = data[0]
            return {
                "word": entry.get("word", word),
                "phonetic": entry.get("phonetic", ""),
                "definitions": [{
                    "partOfSpeech": m.get("partOfSpeech", "word"),
                    "definition": m.get("definitions", [{}])[0].get("definition", ""),
                    "example": m.get("definitions", [{}])[0].get("example", "")
                } for m in entry.get("meanings", [])[:2]],
                "source": "Dictionary API"
            }
    except:
        pass

    # 2. Secondary: MyMemory Translation (For non-dictionary words)
    try:
        conn = http.client.HTTPSConnection("api.mymemory.translated.net")
        path = f"/get?q={urllib.parse.quote(word)}&langpair={lang_code}|en"
        conn.request("GET", path)
        res = conn.getresponse()
        if res.status == 200:
            data = json.loads(res.read().decode())
            trans = data.get("responseData", {}).get("translatedText", "")
            if trans and trans.lower() != word.lower():
                # Clean up weird formal translations like "Acknowledgment" for common words
                if trans.lower() == "acknowledgment" and word.lower() == "teşekkür": trans = "Thank you / Thanks"
                
                return {
                    "word": word,
                    "phonetic": f"({lang_name})",
                    "definitions": [{"partOfSpeech": "translation", "definition": trans, "example": ""}],
                    "source": "MyMemory Global"
                }
    except:
        pass

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
