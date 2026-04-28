import http.client
import json
import urllib.parse
import re

def get_definition(word, lang_code):
    """
    Routes lookups to the best available API for the given language.
    Supports 14+ languages via Free Dictionary API and Wiktionary fallback.
    """
    word = word.strip().lower()
    
    # 1. Primary: Free Dictionary API (Supports EN, ES, FR, DE, IT, PT, RU, TR, etc.)
    # Note: TR support is hit-or-miss, so we handle fallback.
    try:
        conn = http.client.HTTPSConnection("api.dictionaryapi.dev")
        conn.request("GET", f"/api/v2/entries/{lang_code}/{urllib.parse.quote(word)}")
        res = conn.getresponse()
        if res.status == 200:
            data = json.loads(res.read().decode())
            return _format_free_dict(data[0])
    except:
        pass

    # 2. Secondary: Wiktionary Fallback (Universal)
    return _get_wiktionary_definition(word, lang_code)

def _format_free_dict(entry):
    """Standardizes the Free Dictionary API response."""
    return {
        "word": entry.get("word", ""),
        "phonetic": entry.get("phonetic", ""),
        "definitions": [
            {
                "partOfSpeech": m.get("partOfSpeech", ""),
                "definition": m.get("definitions", [{}])[0].get("definition", ""),
                "example": m.get("definitions", [{}])[0].get("example", "")
            } for m in entry.get("meanings", [])[:2] # Top 2 meanings
        ],
        "source": "Free Dictionary API"
    }

def _get_wiktionary_definition(word, lang_code):
    """Scrapes/Requests basic definition from Wiktionary's REST API."""
    try:
        # Wiktionary REST API is very reliable for definitions
        conn = http.client.HTTPSConnection(f"{lang_code}.wiktionary.org")
        path = f"/api/rest_v1/page/summary/{urllib.parse.quote(word)}"
        conn.request("GET", path)
        res = conn.getresponse()
        
        if res.status == 200:
            data = json.loads(res.read().decode())
            return {
                "word": data.get("title", word),
                "phonetic": "",
                "definitions": [{
                    "partOfSpeech": "word",
                    "definition": data.get("extract", "No definition found."),
                    "example": ""
                }],
                "source": "Wiktionary"
            }
    except Exception as e:
        print(f"[DICT ERROR] Wiktionary failed: {e}")
    
    return {"error": "Definition not found", "word": word}

def clean_word(text):
    """Cleans punctuation from captured words."""
    return re.sub(r'[^\w\s]', '', text).strip()
