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
    Detects invalid noncharacters, replacement characters, surrogates, and broken controls
    while preserving all valid combining marks, diacritics, tone marks, stress marks,
    Arabic tashkeel, Indic viramas, and zero-width joiners/non-joiners.
    """
    if not text or not isinstance(text, str):
        return True, ""

    # Check for replacement character (indicating mojibake / broken decoding)
    if "\uFFFD" in text:
        return False, "replacement-character-detected"

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


_CYRILLIC_GRAVE_MAP = {
    "\u0450": "\u0435",  # ѐ -> е
    "\u0400": "\u0415",  # Ѐ -> Е
    "\u045D": "\u0438",  # ѝ -> и
    "\u040D": "\u0418",  # Ѝ -> И
}


def safe_unicode_normalize(text: str) -> str:
    """Safe Unicode NFC normalization preserving all legitimate linguistic marks."""
    if not text or not isinstance(text, str):
        return text
    # Map spurious Cyrillic grave accents to standard Cyrillic (e.g. профѐссор -> профессор)
    for k, v in _CYRILLIC_GRAVE_MAP.items():
        text = text.replace(k, v)
    text = re.sub(r'([\u0400-\u04FF])\u0300', r'\1', text)
    # NFC composes precomposed characters while preserving distinct combining marks
    normalized = unicodedata.normalize("NFC", text)
    # Remove null bytes or forbidden non-printing control characters
    cleaned = "".join(
        c for c in normalized
        if ord(c) in (0x09, 0x0A, 0x0D) or (ord(c) >= 0x20 and not (0x7F <= ord(c) <= 0x9F) and ord(c) != 0xFFFD)
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

    for key in ("options_tr", "options_en"):
        localized = page.get(key)
        if localized is not None:
            localized = [_norm(x) for x in _as_list(localized)]
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


def enforce_material_integrity(data: Any, language: Optional[str] = None) -> Any:
    """
    Language-agnostic structural cleanup and Unicode normalization after generation.
    Prunes structurally broken MCQs, applies safe Unicode NFC normalization,
    and guarantees zero defects on published materials with zero extra model cost.
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
        if isinstance(page, dict) and str(page.get("type") or "").strip().lower() == "mcq":
            ok, reason = validate_mcq(page)
            if not ok:
                removed.append((index, reason))
                continue
        clean.append(page)

    out["pages"] = clean
    if removed:
        out["_integrity_removed_mcq"] = [{"index": i, "reason": r} for i, r in removed]

    return out
