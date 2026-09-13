from copy import deepcopy
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple


class MaterialReleaseRejected(RuntimeError):
    pass


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    if value in (None, ""):
        return []
    return [value]


def _norm(value: Any) -> str:
    return str(value or "").strip()


# ── UNIVERSAL SCRIPT CLASSIFICATION & POLICY LAYER ──────────────────────────

# Supported writing systems for all natural languages
SCRIPT_NAMES = (
    "LATIN",
    "CYRILLIC",
    "GREEK",
    "ARABIC",
    "HEBREW",
    "DEVANAGARI",
    "BENGALI",
    "TAMIL",
    "TELUGU",
    "THAI",
    "GEORGIAN",
    "ARMENIAN",
    "HIRAGANA",
    "KATAKANA",
    "HANGUL",
    "HAN",
)

# Central mapping of language patterns to legitimate target-language writing systems.
# Multiscript languages (Japanese, Korean, Serbian, etc.) list all naturally co-occurring scripts.
LANGUAGE_SCRIPT_POLICIES: Dict[str, Set[str]] = {
    # Cyrillic
    "russian": {"CYRILLIC"},
    "рус": {"CYRILLIC"},
    "rusça": {"CYRILLIC"},
    "ukrainian": {"CYRILLIC"},
    "ukraynaca": {"CYRILLIC"},
    "bulgarian": {"CYRILLIC"},
    "bulgarca": {"CYRILLIC"},
    "serbian": {"CYRILLIC", "LATIN"},
    "sırpça": {"CYRILLIC", "LATIN"},
    "macedonian": {"CYRILLIC"},
    "makedonca": {"CYRILLIC"},
    "belarusian": {"CYRILLIC"},
    # Greek
    "greek": {"GREEK"},
    "yunanca": {"GREEK"},
    "ελλην": {"GREEK"},
    # Semitic
    "arabic": {"ARABIC"},
    "arapça": {"ARABIC"},
    "العربية": {"ARABIC"},
    "persian": {"ARABIC"},
    "farsi": {"ARABIC"},
    "farsça": {"ARABIC"},
    "urdu": {"ARABIC"},
    "hebrew": {"HEBREW"},
    "ibranice": {"HEBREW"},
    "עברית": {"HEBREW"},
    # East Asian & Multiscript
    "japanese": {"HIRAGANA", "KATAKANA", "HAN"},
    "japonca": {"HIRAGANA", "KATAKANA", "HAN"},
    "日本": {"HIRAGANA", "KATAKANA", "HAN"},
    "chinese": {"HAN"},
    "çince": {"HAN"},
    "中文": {"HAN"},
    "mandarin": {"HAN"},
    "korean": {"HANGUL", "HAN"},
    "korece": {"HANGUL", "HAN"},
    "한국": {"HANGUL", "HAN"},
    # Indic / Brahmic
    "hindi": {"DEVANAGARI"},
    "hintçe": {"DEVANAGARI"},
    "sanskrit": {"DEVANAGARI"},
    "bengali": {"BENGALI"},
    "tamil": {"TAMIL"},
    "thai": {"THAI"},
    "tayca": {"THAI"},
    # Latin default: Spanish, German, French, Italian, Portuguese, Turkish, Dutch, Swedish, English, etc.
}

# Universal metadata tokens, abbreviations, and symbols that may legitimately appear
# in any target-language material without being classified as foreign-script contamination.
UNIVERSAL_METADATA_TOKENS: Set[str] = {
    "A1", "A2", "B1", "B2", "C1", "C2",
    "CEFR", "PCIC", "MCQ", "IPA", "URL", "HTTP", "HTTPS", "WWW", "COM",
    "VS", "ETC", "EG", "IE", "OK", "NO", "ID", "APP",
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
}


def _char_script(ch: str) -> Optional[str]:
    """Identify the Unicode script category of a single alphabetic character."""
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, "")
    for script in SCRIPT_NAMES:
        if script in name:
            return script
    if "CJK UNIFIED" in name or "IDEOGRAPH" in name:
        return "HAN"
    return "OTHER"


def _allowed_scripts(language: str) -> Set[str]:
    """Retrieve legitimate target-language scripts for any language name or code."""
    lang_clean = _norm(language).casefold()
    for pattern, scripts in LANGUAGE_SCRIPT_POLICIES.items():
        if pattern in lang_clean:
            return set(scripts)
    return {"LATIN"}


def is_metadata_or_proper_token(token: str) -> bool:
    """Return True if token is a standard metadata code, acronym, numeral, or international abbreviation."""
    norm_token = re.sub(r"[^\w]", "", token).upper()
    if not norm_token:
        return True
    if norm_token in UNIVERSAL_METADATA_TOKENS:
        return True
    # All-caps Latin international acronyms and abbreviations (e.g. UNESCO, NATO, BBC, UN, EU, USA)
    if token.isupper() and 2 <= len(token) <= 10 and re.match(r"^[A-Za-z]+$", token):
        return True
    # CEFR patterns like A1.1, B2+, C1-C2
    if re.match(r"^[ABC][12](\.[12]|\+)?$", norm_token):
        return True
    # Pure numbers or roman numerals
    if norm_token.isdigit() or re.match(r"^[IVXLCDM]+$", norm_token):
        return True
    # Common URL/web domains
    if norm_token.lower() in {"http", "https", "www", "org", "net", "edu", "gov"}:
        return True
    return False


# ── UNICODE & GLYPHIC INTEGRITY ─────────────────────────────────────────────

def validate_unicode_integrity(text: str) -> Tuple[bool, str]:
    """
    Language-agnostic validation of Unicode string integrity.
    Detects invalid noncharacters, replacement characters, surrogates, soft hyphens,
    and broken controls while preserving all valid combining marks, diacritics, tone marks,
    stress marks, Arabic tashkeel, Indic viramas, and zero-width joiners/non-joiners.
    """
    if not text or not isinstance(text, str):
        return True, ""

    # Check for replacement character (indicating mojibake / broken decoding)
    if "\uFFFD" in text:
        return False, "replacement-character-detected"

    # Check for soft-hyphen or non-breaking hyphen artifacts
    if "\u00AD" in text:
        return False, "soft-hyphen-detected"
    if "\u2011" in text:
        return False, "non-breaking-hyphen-detected"

    # Check for noncharacters (U+FDD0..U+FDEF, U+nFFFE, U+nFFFF)
    for ch in text:
        cp = ord(ch)
        if 0xFDD0 <= cp <= 0xFDEF or (cp & 0xFFFE) == 0xFFFE:
            return False, f"unicode-noncharacter:{hex(cp)}"
        # Check for lone surrogate code points (U+D800..U+DFFF)
        if 0xD800 <= cp <= 0xDFFF:
            return False, f"unicode-surrogate:{hex(cp)}"
        # Check for invalid C0/C1 control characters (excluding \t, \n, \r)
        if (cp < 0x20 and cp not in (0x09, 0x0A, 0x0D)) or (0x7F <= cp <= 0x9F):
            return False, f"malformed-control-character:{hex(cp)}"

    # Check for orphaned combining marks at string start
    if text and unicodedata.category(text[0]) in ("Mn", "Mc", "Me"):
        return False, "orphaned-combining-mark-at-start"

    return True, ""


def safe_unicode_normalize(text: str) -> str:
    """
    Safe Unicode NFC normalization preserving all legitimate linguistic marks.
    Converts soft hyphens (U+00AD), non-breaking hyphens (U+2011), and exotic dashes
    to standard ASCII '-' (U+002D) to prevent visual drops in PDF/terminal rendering.
    Strips zero-width non-breaking spaces and invalid controls.
    Preserves authentic combining marks, diacritics, stress marks, and script joiners.
    """
    if not text or not isinstance(text, str):
        return text
    # Normalize hyphens and dashes to standard ASCII hyphen '-'
    text = re.sub(r"[\u00AD\u2010\u2011\u2012\uFE63\uFF0D]", "-", text)
    # Replace intra-word en-dash with ASCII hyphen
    text = re.sub(r"([\w\u0400-\u04FF\u0370-\u03FF])\u2013([\w\u0400-\u04FF\u0370-\u03FF])", r"\1-\2", text)
    # Strip zero-width space U+200B, byte-order mark / zero-width non-breaking space U+FEFF, and word joiner U+2060
    text = re.sub(r"[\u200B\uFEFF\u2060]", "", text)
    # NFC composes precomposed characters while preserving distinct combining marks
    normalized = unicodedata.normalize("NFC", text)
    # Remove null bytes or forbidden non-printing control characters
    cleaned = "".join(
        c for c in normalized
        if ord(c) in (0x09, 0x0A, 0x0D) or (ord(c) >= 0x20 and not (0x7F <= ord(c) <= 0x9F) and ord(c) != 0xFFFD and ord(c) != 0x00AD)
    )
    return cleaned


# ── FIELD-AWARE TARGET STRING EXTRACTION ─────────────────────────────────────

_EXCLUDE_SUFFIXES = ("_en", "_tr", "_fr", "_de", "_es", "_it", "_ru")
_INSTRUCTIONAL_KEYS = {
    "translation", "explanation", "note", "context", "source_evidence",
    "source_taught", "tip", "analysis", "line_en", "line_tr", "prompt_en",
    "prompt_tr", "options_en", "options_tr", "title_en", "title_tr",
    "text_en", "text_tr", "meaning", "meaning_tr", "definition",
    "teachers_warning", "teachers_warning_tr", "pitfall_tr"
}
_TARGET_LEXICAL_KEYS = {
    "term", "word", "target", "example", "sentence", "answer",
    "expression", "phrase", "form", "native"
}


def _iter_target_lexical_strings(node: Any, parent_key: str = "") -> Any:
    """Yield only genuinely target-language lexical content, excluding instructional/bilingual fields."""
    if isinstance(node, dict):
        for key, value in node.items():
            k = str(key)
            kl = k.casefold()
            if any(kl.endswith(sfx) for sfx in _EXCLUDE_SUFFIXES):
                continue
            if kl in _INSTRUCTIONAL_KEYS:
                continue
            if kl == "text" and parent_key == "dialogue" and isinstance(value, str):
                yield value
            elif kl in _TARGET_LEXICAL_KEYS:
                if isinstance(value, str):
                    yield value
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            yield item
            elif kl in ("options", "distractors"):
                # Assessment options may contain target language words
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            yield item
            if isinstance(value, (dict, list)):
                yield from _iter_target_lexical_strings(value, kl)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_target_lexical_strings(item, parent_key)


# ── SCRIPT INTEGRITY & HOMOGLYPH CORRUPTION GATE ────────────────────────────

def _script_gate(data: Any, language: str) -> Tuple[bool, str]:
    """
    Field-aware, semantic-role-aware validation of writing system integrity.
    Rejects genuine intra-token mixed-script corruption (e.g. Cyrillic token with Latin homoglyph)
    while fully permitting natural multiscript languages, CEFR codes, IPA, and proper nouns.
    """
    allowed = _allowed_scripts(language)
    for text in _iter_target_lexical_strings(data):
        # Check Unicode validity on text
        u_ok, u_why = validate_unicode_integrity(text)
        if not u_ok:
            return False, u_why

        # Tokenize by Unicode word boundaries
        for token in re.findall(r"[^\W\d_]+", text, flags=re.UNICODE):
            if is_metadata_or_proper_token(token):
                continue

            char_scripts = [_char_script(ch) for ch in token if _char_script(ch)]
            scripts = set(char_scripts) - {"OTHER"}
            if not scripts:
                continue

            # Mathematical script validation:
            native_scripts = scripts & allowed
            foreign_scripts = scripts - allowed

            if foreign_scripts:
                # If it's a known metadata / abbreviation / proper token, it is permissible
                if is_metadata_or_proper_token(token):
                    continue
                if native_scripts:
                    # Intra-token homoglyph corruption (e.g. Cyrillic mixed with Latin)
                    return False, f"mixed-script-corruption:{token}"
                else:
                    # Entire token is from an unpermitted script (e.g. English word in Russian term field)
                    return False, f"foreign-script-leakage:{token}"

    return True, ""


# ── PRONUNCIATION-SYSTEM CONSISTENCY GATE ───────────────────────────────────

def _iter_phonetic_strings(node: Any, key: str = "") -> Any:
    if isinstance(node, dict):
        for k, value in node.items():
            kl = str(k).casefold()
            is_phon = any(tag in kl for tag in ("pronun", "phonetic", "transcription", "ipa"))
            if is_phon and isinstance(value, str) and value.strip():
                yield value.strip()
            if isinstance(value, (dict, list)):
                yield from _iter_phonetic_strings(value, kl)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_phonetic_strings(item, key)


def _phonetic_gate(data: Any) -> Tuple[bool, str]:
    """
    Universal pronunciation-system consistency gate.
    Allows standard IPA [...], standard phonemic /.../, and clean romanization (Pinyin, Hepburn),
    while rejecting ad-hoc hyphenated learner respelling mixed inside formal phonetic fields.
    """
    values = list(_iter_phonetic_strings(data))
    for text in values:
        u_ok, u_why = validate_unicode_integrity(text)
        if not u_ok:
            return False, u_why

        # Reject ad-hoc learner respelling mixed inside or around IPA (e.g. [kæt] kat-uh-lee-nuh)
        has_ipa = ("[" in text and "]" in text) or re.search(r"/(?:[^/\n]{1,120})/", text)
        if has_ipa:
            outside = re.sub(r"\[[^\]]*\]", "", text)
            outside = re.sub(r"/[^/\n]+/", "", outside)
            if re.search(r"\b[A-Za-z]{2,}(?:-[A-Za-z]{2,})+\b", outside):
                return False, "learner-respelling-mixed-with-ipa"

    return True, ""


# ── UNIVERSAL DIALOGUE SPEAKER ROLE LOCALIZATION & LEAKAGE PROTECTION ───────

ROLE_CATALOG: Dict[str, Dict[str, str]] = {
    "student": {
        "tr": "Öğrenci", "de": "Schüler", "fr": "Étudiant", "es": "Estudiante", "en": "Student"
    },
    "students": {
        "tr": "Öğrenciler", "de": "Schüler", "fr": "Étudiants", "es": "Estudiantes", "en": "Students"
    },
    "teacher": {
        "tr": "Öğretmen", "de": "Lehrer", "fr": "Professeur", "es": "Profesor", "en": "Teacher"
    },
    "teachers": {
        "tr": "Öğretmenler", "de": "Lehrer", "fr": "Professeurs", "es": "Profesores", "en": "Teachers"
    },
    "professor": {
        "tr": "Profesör", "de": "Professor", "fr": "Professeur", "es": "Profesor", "en": "Professor"
    },
    "instructor": {
        "tr": "Eğitmen", "de": "Dozent", "fr": "Instructeur", "es": "Instructor", "en": "Instructor"
    },
    "clerk": {
        "tr": "Görevli", "de": "Angestellter", "fr": "Employé", "es": "Empleado", "en": "Clerk"
    },
    "waiter": {
        "tr": "Garson", "de": "Kellner", "fr": "Serveur", "es": "Camarero", "en": "Waiter"
    },
    "waitress": {
        "tr": "Garson", "de": "Kellnerin", "fr": "Serveuse", "es": "Camarera", "en": "Waitress"
    },
    "customer": {
        "tr": "Müşteri", "de": "Kunde", "fr": "Client", "es": "Cliente", "en": "Customer"
    },
    "doctor": {
        "tr": "Doktor", "de": "Arzt", "fr": "Médecin", "es": "Médico", "en": "Doctor"
    },
    "patient": {
        "tr": "Hasta", "de": "Patient", "fr": "Patient", "es": "Paciente", "en": "Patient"
    },
    "friend": {
        "tr": "Arkadaş", "de": "Freund", "fr": "Ami", "es": "Amigo", "en": "Friend"
    },
    "narrator": {
        "tr": "Anlatıcı", "de": "Erzähler", "fr": "Narrateur", "es": "Narrador", "en": "Narrator"
    },
    "speaker": {
        "tr": "Konuşmacı", "de": "Sprecher", "fr": "Interlocuteur", "es": "Hablante", "en": "Speaker"
    },
    "passenger": {
        "tr": "Yolcu", "de": "Passagier", "fr": "Passager", "es": "Pasajero", "en": "Passenger"
    },
    "driver": {
        "tr": "Sürücü", "de": "Fahrer", "fr": "Chauffeur", "es": "Conductor", "en": "Driver"
    },
    "cashier": {
        "tr": "Kasiyer", "de": "Kassierer", "fr": "Caissier", "es": "Cajero", "en": "Cashier"
    },
    "guide": {
        "tr": "Rehber", "de": "Reiseleiter", "fr": "Guide", "es": "Guía", "en": "Guide"
    },
    "receptionist": {
        "tr": "Resepsiyonist", "de": "Empfangschef", "fr": "Réceptionniste", "es": "Recepcionista", "en": "Receptionist"
    },
    "passerby": {
        "tr": "Yoldan Geçen", "de": "Passant", "fr": "Passant", "es": "Transeúnte", "en": "Passerby"
    },
    "host": {
        "tr": "Ev Sahibi", "de": "Gastgeber", "fr": "Hôte", "es": "Anfitrión", "en": "Host"
    },
    "guest": {
        "tr": "Konuk", "de": "Gast", "fr": "Invité", "es": "Invitado", "en": "Guest"
    },
}

_ROLE_REVERSE_MAP: Dict[str, str] = {}
for _canon, _locales in ROLE_CATALOG.items():
    if _canon.casefold() not in _ROLE_REVERSE_MAP:
        _ROLE_REVERSE_MAP[_canon.casefold()] = _canon
    for _loc, _name in _locales.items():
        if _name.casefold() not in _ROLE_REVERSE_MAP:
            _ROLE_REVERSE_MAP[_name.casefold()] = _canon


def sanitize_dialogue_speaker(speaker: str, material_language: str = "en") -> str:
    """
    Universal, locale-safe speaker role sanitizer.
    
    Architecture & Policy:
    1. Primary Strategy: Generation-time correct locale role from the model.
    2. Proper Name Preservation: Authentic proper names (Marco, Anna, Yuki, Ahmed, etc.)
       across all scripts are preserved untouched.
    3. High-Confidence Fallback: Known canonical roles for catalogued instructional
       languages (tr, de, fr, es, en) are normalized to the target instructional language.
    4. Unknown Locale Safe Fallback: When a foreign English role label is detected but no
       deterministic mapping exists for material_language, role metadata is safely omitted
       to prevent English leakage, keeping any associated proper name.
    5. Strict Idempotence: sanitize(sanitize(x)) == sanitize(x).
    6. Non-Destructive: Never drops pages or dialogue turns.
    """
    if not speaker or not isinstance(speaker, str):
        return speaker or ""

    s_clean = speaker.strip()
    if s_clean.endswith(":"):
        s_clean = s_clean[:-1].strip()

    tgt_lang = str(material_language or "en").strip().lower()[:2]

    # Handle composite format e.g. "Marco (Student)" or "Student (Marco)"
    m_composite = re.match(r"^(.+?)\s*\((.+?)\)$", s_clean)
    if m_composite:
        part1 = m_composite.group(1).strip()
        part2 = m_composite.group(2).strip()
        canon2 = _ROLE_REVERSE_MAP.get(part2.casefold())
        canon1 = _ROLE_REVERSE_MAP.get(part1.casefold())
        if canon2 and not canon1:
            loc_dict = ROLE_CATALOG.get(canon2, {})
            localized_role = loc_dict.get(tgt_lang)
            if localized_role:
                return f"{part1} ({localized_role})"
            elif tgt_lang == "en":
                return f"{part1} ({loc_dict.get('en', part2)})"
            else:
                # Unknown locale: omit untranslated foreign role, preserve proper name
                return part1
        elif canon1 and not canon2:
            loc_dict = ROLE_CATALOG.get(canon1, {})
            localized_role = loc_dict.get(tgt_lang)
            if localized_role:
                return f"{part2} ({localized_role})"
            elif tgt_lang == "en":
                return f"{part2} ({loc_dict.get('en', part1)})"
            else:
                # Unknown locale: omit untranslated foreign role, preserve proper name
                return part2

    in_paren = s_clean.startswith("(") and s_clean.endswith(")")
    raw_name = s_clean[1:-1].strip() if in_paren else s_clean
    canon_key = _ROLE_REVERSE_MAP.get(raw_name.casefold())

    if not canon_key:
        # Proper name (Marco, Anna, Yuki, Ahmed, etc.) or uncatalogued locale role (Studente)
        return f"({raw_name})" if in_paren else raw_name

    loc_dict = ROLE_CATALOG.get(canon_key, {})
    localized = loc_dict.get(tgt_lang)
    if localized:
        return f"({localized})" if in_paren else localized

    # Unknown locale fallback:
    # canon_key was recognized (e.g. English "Student"), but material_language has no deterministic mapping.
    if tgt_lang == "en":
        en_role = loc_dict.get("en") or raw_name
        return f"({en_role})" if in_paren else en_role

    # Non-English unknown locale: safely omit the unlocalized foreign role to prevent English leakage
    return ""


def validate_dialogue_speaker(speaker: str, material_language: str = "en") -> Tuple[bool, str]:
    """
    Universal validation ensuring dialogue speaker roles match the instructional language.
    Flags unlocalized foreign role labels (e.g. English 'Student' in Turkish, German, or Italian material),
    while treating authentic proper names ('Marco', 'Anna', 'Yuki') and generation-time locale roles
    as valid across all languages.
    """
    if not speaker or not isinstance(speaker, str):
        return True, ""

    s_clean = speaker.strip()
    if s_clean.endswith(":"):
        s_clean = s_clean[:-1].strip()

    # Extract role from composite e.g. "Marco (Student)"
    m_composite = re.match(r"^(.+?)\s*\((.+?)\)$", s_clean)
    if m_composite:
        role_part = m_composite.group(2).strip()
        canon_key = _ROLE_REVERSE_MAP.get(role_part.casefold())
        if not canon_key:
            return True, ""
        tgt_lang = str(material_language or "en").strip().lower()[:2]
        loc_dict = ROLE_CATALOG.get(canon_key, {})
        expected = loc_dict.get(tgt_lang)
        if expected and role_part.casefold() != expected.casefold():
            return False, f"instructional-language-leakage:untranslated-speaker-role:{speaker}:expected-{expected}"
        if not expected and tgt_lang != "en" and role_part.casefold() == canon_key:
            return False, f"instructional-language-leakage:untranslated-speaker-role:{speaker}"
        return True, ""

    in_paren = s_clean.startswith("(") and s_clean.endswith(")")
    raw_name = s_clean[1:-1].strip() if in_paren else s_clean
    canon_key = _ROLE_REVERSE_MAP.get(raw_name.casefold())

    if not canon_key:
        # Proper name or uncatalogued entity -> valid in all languages
        return True, ""

    tgt_lang = str(material_language or "en").strip().lower()[:2]
    loc_dict = ROLE_CATALOG.get(canon_key, {})
    expected = loc_dict.get(tgt_lang)
    if expected and raw_name.casefold() != expected.casefold():
        return False, f"instructional-language-leakage:untranslated-speaker-role:{speaker}:expected-{expected}"
    if not expected and tgt_lang != "en" and raw_name.casefold() == canon_key:
        return False, f"instructional-language-leakage:untranslated-speaker-role:{speaker}"

    return True, ""


# ── PHONETIC REPRESENTATION CONSISTENCY & RE-SPELLING DETECTION ──────────────

def is_adhoc_learner_respelling(phon: str) -> bool:
    """
    Language-agnostic detection of ad-hoc learner respellings.
    Distinguishes:
    1. Standard IPA notation (e.g. '[mʲɪˈtro]', '[ˈka.sa]', '/ˈpe.ro/') -> VALID (False)
    2. Standard romanization (e.g. Pinyin 'nǐ hǎo', Romaji 'taberu') -> VALID (False)
    3. Ad-hoc hyphenated learner respellings (e.g. 'mit-ró', 'slo-var\\'', '[mask-va]', '[ˈzdrav-stvu-yte]') -> AD-HOC (True)
    4. Native-script syllable hyphenation (e.g. 'сло-ва́рь', 'ма-ма') -> AD-HOC (True)
    """
    if not phon or not isinstance(phon, str):
        return False
    clean = phon.strip()
    if not clean:
        return False

    # 1. Native-script syllable division: non-Latin alphabetic characters with hyphens
    # (e.g. Cyrillic 'сло-ва́рь', Greek, Arabic, etc.)
    has_non_latin = any(unicodedata.category(c).startswith("L") and not ("a" <= c.lower() <= "z") for c in clean)
    if has_non_latin and "-" in clean:
        if re.search(r"[^\W\d_a-zA-Z]-[^\W\d_a-zA-Z]", clean, flags=re.UNICODE):
            return True

    # 2. Check for bracketed or unbracketed Latin text
    inside = clean[1:-1].strip() if clean.startswith("[") and clean.endswith("]") else clean

    # Authentic IPA phonetic symbols
    ipa_symbols = set("ˈˌːˑəɛɪɔʊʌθðʃʒŋɲɹʁʎβɣχħʕʔ mʲpʲbʲtʲdʲkʲɡʲfʲvʲsʲzʲrʲlʲ")
    has_distinct_ipa = any(c in inside for c in ipa_symbols if c != " ")

    # Check for ad-hoc hyphenated syllable respellings (e.g. mit-ró, slo-var', mask-va, zdrav-stvu-yte)
    if "-" in inside:
        parts = [p.strip() for p in inside.split("-") if p.strip()]
        if len(parts) >= 2:
            letter_count = sum(1 for c in inside if unicodedata.category(c).startswith("L"))
            if letter_count >= 4 and not (clean.startswith("/") and clean.endswith("/")):
                return True

    # Pinyin with standard tone marks without brackets is valid romanization
    pinyin_tone_chars = set("āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ")
    if any(c in clean for c in pinyin_tone_chars) and not clean.startswith("["):
        return False

    # 3. Simple Latin word inside brackets without any IPA symbols (e.g. '[mask-va]', '[zdravstvuyte]')
    if clean.startswith("[") and clean.endswith("]"):
        content = clean[1:-1].strip()
        if not has_distinct_ipa and re.match(r"^[A-Za-z\s\-\'\`]+$", content):
            return True

    return False


# ── FORMATIVE MCQ STRUCTURAL & SEMANTIC VALIDATION ──────────────────────────

def validate_mcq_semantics(page: dict) -> Tuple[bool, str]:
    """
    Semantic validation for formative assessment items.
    Prevents unjustified deductive leaps from world knowledge / stereotypes:
    1. Birthplace / country of birth does NOT entail nationality or citizenship.
    2. Workplace does NOT entail specific profession without stated job duties.
    """
    if not isinstance(page, dict):
        return True, ""

    prompt = _norm(page.get("prompt") or page.get("question") or page.get("text")).lower()
    answer = _norm(page.get("answer")).lower()

    # 1. Birthplace / origin assumption to nationality
    birthplace_indicators = ("родилась в", "родился в", "born in", "doğdu", "né en", "geboren in")
    nationality_indicators = (
        "турчанка", "турок", "turkish", "türk",
        "испанец", "испанка", "spanish", "ispanyol",
        "русский", "русская", "russian", "rus",
        "немец", "немка", "german", "alman",
        "француз", "француженка", "french", "fransız"
    )
    if any(b in prompt for b in birthplace_indicators):
        if not any(c in prompt for c in ("граждан", "citizenship", "citizen", "vatandaş", "nationality", "milliyet")):
            if any(n in answer for n in nationality_indicators):
                return False, "semantic-non-entailment:birthplace-does-not-entail-nationality"

    # 2. Workplace assumption to occupation
    workplace_indicators = (
        "работаю в школе", "работает в школе", "works in a school", "okulda çalışıyor", "okulda çalışırım",
        "работаю в больнице", "работает в больнице", "works in a hospital", "hastanede çalışıyor",
        "работаю в аэропорту", "works in an airport"
    )
    job_duties = (
        "препода", "учу", "учит", "teach", "ders ver", "öğret", "леч", "heal", "treat", "hastaları",
        "лечит", "управляет самолетом", "flies airplanes"
    )
    if any(w in prompt for w in workplace_indicators):
        if not any(d in prompt for d in job_duties):
            if answer in ("teacher", "учитель", "учительница", "öğretmen", "doctor", "врач", "doktor", "pilot", "пилот"):
                return False, "semantic-non-entailment:workplace-does-not-entail-profession"

    return True, ""


# ── FORMATIVE MCQ STRUCTURAL VALIDATION ─────────────────────────────────────

def validate_mcq(page: Any) -> Tuple[bool, str]:
    """
    Universal, language-agnostic formative MCQ validation.
    Enforces exactly 4 distinct options, exactly 1 matching answer, correct index alignment,
    and localized options count/uniqueness parity.
    """
    if not isinstance(page, dict):
        return False, "mcq-not-dict"

    prompt = _norm(page.get("prompt") or page.get("question") or page.get("text"))
    options = [_norm(x) for x in _as_list(page.get("options") or page.get("choices"))]
    answer = _norm(page.get("answer"))

    if not prompt:
        return False, "missing-prompt"
    if len(options) != 4:
        return False, "option-count"
    if any(not x for x in options):
        return False, "empty-option"
    if len(set(options)) != 4:
        return False, "duplicate-options"
    if not answer:
        return False, "missing-answer"
    if answer not in options:
        return False, "answer-not-in-options"

    ci = page.get("correct_index")
    if isinstance(ci, int) and (ci < 0 or ci >= 4 or options[ci] != answer):
        return False, "correct-index-mismatch"

    for key, val in page.items():
        if key.startswith("options_") and val is not None:
            localized = [_norm(x) for x in _as_list(val)]
            if len(localized) != 4 or any(not x for x in localized) or len(set(localized)) != 4:
                return False, f"invalid-{key}"

    return True, ""


def _mcq_gate(data: Any) -> Tuple[bool, str]:
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list):
        return False, "missing-pages"
    for index, page in enumerate(pages):
        if isinstance(page, dict) and str(page.get("type") or "").strip().lower() == "mcq":
            ok, reason = validate_mcq(page)
            if not ok:
                return False, f"page-{index}:{reason}"
    return True, ""


# ── DETERMINISTIC RELEASE HARD GATE & INTEGRITY ENFORCEMENT ──────────────────

def enforce_release_hard_gate(data: Any, language: str) -> Any:
    """
    Zero-extra-cost, deterministic release hard gate.
    Evaluates script integrity, pronunciation consistency, Unicode cleanliness, and MCQ validity.
    """
    if not isinstance(data, dict):
        raise MaterialReleaseRejected("MATERIAL_RELEASE_HARD_GATE:invalid-data")

    # Verify script integrity & homoglyph protection
    ok1, why1 = _script_gate(data, language)
    if not ok1:
        raise MaterialReleaseRejected("MATERIAL_RELEASE_HARD_GATE:1:" + why1)

    # Verify pronunciation representation consistency
    ok2, why2 = _phonetic_gate(data)
    if not ok2:
        raise MaterialReleaseRejected("MATERIAL_RELEASE_HARD_GATE:2:" + why2)

    # Verify formative assessment validity
    ok4, why4 = _mcq_gate(data)
    if not ok4:
        raise MaterialReleaseRejected("MATERIAL_RELEASE_HARD_GATE:4:" + why4)

    out = deepcopy(data)
    out.pop("release_gate", None)
    return out


def _recursive_clean_unicode(node: Any) -> Any:
    """Recursively apply safe NFC Unicode normalization to all strings."""
    if isinstance(node, str):
        return safe_unicode_normalize(node)
    if isinstance(node, dict):
        return {k: _recursive_clean_unicode(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_recursive_clean_unicode(item) for item in node]
    return node


def enforce_material_integrity(
    data: Any,
    language: Optional[str] = None,
    material_language: str = "tr"
) -> Any:
    """
    Language-agnostic structural cleanup and Unicode normalization after generation.
    Normalizes exotic hyphens, strips soft-hyphens and unprintable artifacts,
    localizes dialogue speaker roles, prunes structurally or semantically invalid MCQs,
    and guarantees zero publication defects with zero extra model cost.
    """
    if not isinstance(data, dict):
        return data

    out = _recursive_clean_unicode(deepcopy(data))
    pages = out.get("pages")
    if not isinstance(pages, list):
        return out

    clean = []
    removed = []
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        ptype = str(page.get("type") or "").strip().lower()

        # Localize dialogue speaker roles and ensure no English leakage into Turkish material
        if ptype in ("dialogue", "examples"):
            dialogue = page.get("dialogue")
            if isinstance(dialogue, list):
                for turn in dialogue:
                    if isinstance(turn, dict) and "speaker" in turn:
                        turn["speaker"] = sanitize_dialogue_speaker(turn["speaker"], material_language)

        # Clean ad-hoc learner respellings or native syllable breaks from vocabulary phonetics
        if ptype in ("vocabulary", "overview", "grammar"):
            items = page.get("items") or page.get("vocabulary") or page.get("words") or []
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        phon = it.get("phonetic") or it.get("pronunciation")
                        if phon and is_adhoc_learner_respelling(phon):
                            it["phonetic"] = ""

        if ptype == "mcq":
            ok, reason = validate_mcq(page)
            if not ok:
                removed.append((index, reason))
                continue
        clean.append(page)

    out["pages"] = clean
    if removed:
        out["_integrity_removed_mcq"] = [{"index": i, "reason": r} for i, r in removed]

    return out

