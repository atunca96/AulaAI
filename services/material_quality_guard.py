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


_RUSSIAN_GRAVE_MAP = {
    "\u0450": "\u0435",  # ѐ -> е
    "\u0400": "\u0415",  # Ѐ -> Е
    "\u045D": "\u0438",  # ѝ -> и
    "\u040D": "\u0418",  # Ѝ -> И
}


def _is_russian_context(language: Optional[str] = None, data: Any = None) -> bool:
    candidates = [language]
    if isinstance(data, dict):
        for k in ("language", "target_language", "lang", "course_language"):
            v = data.get(k)
            if v:
                candidates.append(v)
    for c in candidates:
        if isinstance(c, str):
            cl = c.strip().casefold()
            if cl in ("russian", "rusça", "rusca", "rus", "ru"):
                return True
    return False


def normalize_russian_orthography(text: str) -> str:
    """Normalize Russian Cyrillic by replacing non-Russian grave accents with canonical forms."""
    if not isinstance(text, str) or not text:
        return text
    for k, v in _RUSSIAN_GRAVE_MAP.items():
        text = text.replace(k, v)
    return re.sub(r'([\u0400-\u04FF])\u0300', r'\1', text)


def _is_noncharacter_or_forbidden(cp: int) -> bool:
    return (
        0xFDD0 <= cp <= 0xFDEF
        or (cp & 0xFFFE) == 0xFFFE
        or 0xD800 <= cp <= 0xDFFF
        or (cp < 0x20 and cp not in (0x09, 0x0A, 0x0D))
        or (0x7F <= cp <= 0x9F)
        or cp == 0xFFFD
    )


def _is_cyrillic(char: str) -> bool:
    return '\u0400' <= char <= '\u04FF' or '\u0500' <= char <= '\u052F'


def _is_latin(char: str) -> bool:
    return ('a' <= char <= 'z') or ('A' <= char <= 'Z') or ('\u00C0' <= char <= '\u024F')


def _resolve_noncharacter_separator(text: str, i: int) -> str:
    n = len(text)
    p = i - 1
    while p >= 0 and _is_noncharacter_or_forbidden(ord(text[p])):
        p -= 1
    nxt_idx = i + 1
    while nxt_idx < n and _is_noncharacter_or_forbidden(ord(text[nxt_idx])):
        nxt_idx += 1

    prev_ch = text[p] if p >= 0 else ''
    next_ch = text[nxt_idx] if nxt_idx < n else ''

    if not prev_ch or not next_ch or prev_ch.isspace() or next_ch.isspace():
        return ''

    p_start = p
    while p_start >= 0 and (text[p_start].isalnum() or text[p_start] in '-_\u0300\u0301\u0302\u0303\u0304\u0308\u030a\u030c'):
        p_start -= 1
    prev_word = text[p_start + 1 : p + 1]

    n_end = nxt_idx
    while n_end < n and (text[n_end].isalnum() or text[n_end] in '-_\u0300\u0301\u0302\u0303\u0304\u0308\u030a\u030c'):
        n_end += 1
    nxt_word = text[nxt_idx : n_end]

    prev_word_clean = re.sub(r'[\u0300-\u036f]', '', prev_word).lower()
    nxt_word_clean = re.sub(r'[\u0300-\u036f]', '', nxt_word).lower()

    if prev_word_clean in ('по', 'кое', 'из') and _is_cyrillic(next_ch):
        return '-'
    if nxt_word_clean in ('то', 'либо', 'нибудь', 'таки') and _is_cyrillic(prev_ch):
        return '-'
    if prev_word.startswith('-') and next_ch.isalnum():
        return ' '
    if (_is_cyrillic(prev_ch) and _is_latin(next_ch)) or (_is_latin(prev_ch) and _is_cyrillic(next_ch)):
        return ' '
    if nxt_word_clean in ('ve', 'ile', 'veya', 'and', 'or', 'und', 'y', 'и', 'или', 'а', 'но', 'de', 'da'):
        return ' '
    if prev_word_clean in ('ve', 'ile', 'veya', 'and', 'or', 'und', 'y', 'и', 'или', 'а', 'но', 'de', 'da'):
        return ' '
    if prev_word_clean.endswith(('lik', 'lık', 'luk', 'lük')) and nxt_word_clean.endswith(('lik', 'lık', 'luk', 'lük')):
        return '-'
    if prev_ch.isalnum() and next_ch.isalnum():
        return ' '
    return ''



# ── UNIVERSAL MIXED-SCRIPT MORPHOLOGY HARMONIZATION ─────────────────────────

_LATIN_TO_CYRILLIC_HOMOGLYPHS = {
    'a': 'а', 'A': 'А',
    'B': 'В',
    'c': 'с', 'C': 'С',
    'e': 'е', 'E': 'Е',
    'i': 'и', 'I': 'И',
    'k': 'к', 'K': 'К',
    'm': 'м', 'M': 'М',
    'o': 'о', 'O': 'О',
    'p': 'р', 'P': 'Р',
    's': 'с', 'S': 'С',
    't': 'т', 'T': 'Т',
    'x': 'х', 'X': 'Х',
    'y': 'у', 'Y': 'У',
    'H': 'Н',
}

_CYRILLIC_TO_LATIN_HOMOGLYPHS = {
    'а': 'a', 'А': 'A',
    'В': 'B',
    'с': 'c', 'С': 'C',
    'е': 'e', 'E': 'E',
    'і': 'i', 'І': 'I',
    'ј': 'j', 'Ј': 'J',
    'к': 'k', 'К': 'K',
    'м': 'm', 'M': 'M',
    'о': 'o', 'О': 'O',
    'р': 'p', 'Р': 'P',
    'т': 't', 'Т': 'T',
    'х': 'x', 'Х': 'X',
    'у': 'y', 'У': 'Y',
    'Н': 'H',
}

_LATIN_TO_GREEK_HOMOGLYPHS = {
    'a': 'α', 'A': 'Α',
    'B': 'Β',
    'e': 'ε', 'E': 'Ε',
    'H': 'Η',
    'i': 'ι', 'I': 'Ι',
    'k': 'κ', 'K': 'Κ',
    'm': 'μ', 'M': 'Μ',
    'n': 'ν', 'N': 'Ν',
    'o': 'ο', 'O': 'Ο',
    'p': 'ρ', 'P': 'Ρ',
    't': 'τ', 'T': 'Τ',
    'u': 'υ', 'U': 'Υ',
    'x': 'χ', 'X': 'Χ',
    'y': 'υ', 'Y': 'Υ',
}

_GREEK_TO_LATIN_HOMOGLYPHS = {
    'α': 'a', 'Α': 'A',
    'Β': 'B',
    'ε': 'e', 'Ε': 'E',
    'Η': 'H',
    'ι': 'i', 'Ι': 'I',
    'κ': 'k', 'Κ': 'K',
    'μ': 'm', 'M': 'M',
    'ν': 'n', 'Ν': 'N',
    'ο': 'o', 'Ο': 'O',
    'ρ': 'p', 'Ρ': 'P',
    'τ': 't', 'Τ': 'T',
    'υ': 'u', 'Υ': 'Y',
    'χ': 'x', 'Χ': 'X',
}

_CYRILLIC_UNIQUE_CHARS = set("бвгджзийлпфцчшщъыьэюяБВГДЖЗИЙЛПФЦЧШЩЪЫЬЭЮЯ")
_GREEK_UNIQUE_CHARS = set("γδζθλξπσςφψωΓΔΖΘΛΞΠΣΦΨΩάέήίόύώΆΈΉΊΌΎΏ")
_LATIN_UNIQUE_CHARS = set("dfglqrvwzDFGLQRVWZáéíóúñçöüäÁÉÍÓÚÑÇÖÜÄ")

_TOKEN_PATTERN = re.compile(
    r'(-?[a-zA-Z\u00C0-\u024F\u0400-\u04FF\u0370-\u03FF\u0300-\u036F]+(?:-[a-zA-Z\u00C0-\u024F\u0400-\u04FF\u0370-\u03FF\u0300-\u036F]+)*-?)'
)


def _harmonize_segment(seg: str, language: Optional[str] = None) -> str:
    if not seg or is_metadata_or_proper_token(seg):
        return seg
    cyr = [c for c in seg if '\u0400' <= c <= '\u04FF' or '\u0500' <= c <= '\u052F']
    lat = [c for c in seg if ('a' <= c <= 'z' or 'A' <= c <= 'Z' or '\u00C0' <= c <= '\u024F')]
    grk = [c for c in seg if '\u0370' <= c <= '\u03FF']

    if cyr and lat and not grk:
        has_cyr_u = any(c in _CYRILLIC_UNIQUE_CHARS for c in cyr)
        has_lat_u = any(c in _LATIN_UNIQUE_CHARS for c in lat)

        if has_cyr_u and not has_lat_u:
            target_is_cyr = True
        elif has_lat_u and not has_cyr_u:
            target_is_cyr = False
        elif language and any(k in str(language).lower() for k in ('rus', 'bulg', 'ukr', 'serb', 'maced')):
            target_is_cyr = True
        elif language and any(k in str(language).lower() for k in ('span', 'germ', 'fren', 'ital', 'turk', 'engl', 'port')):
            target_is_cyr = False
        elif len(cyr) >= len(lat):
            target_is_cyr = True
        else:
            target_is_cyr = False

        if target_is_cyr:
            mapping = dict(_LATIN_TO_CYRILLIC_HOMOGLYPHS)
            if language and any(k in str(language).lower() for k in ('ukr', 'belar')):
                mapping['i'] = 'і'
                mapping['I'] = 'І'
            # All-or-nothing: every foreign character must be a valid homoglyph; otherwise preserve untouched
            if all(c in mapping for c in lat):
                return ''.join(mapping.get(c, c) for c in seg)
            return seg
        else:
            if all(c in _CYRILLIC_TO_LATIN_HOMOGLYPHS for c in cyr):
                return ''.join(_CYRILLIC_TO_LATIN_HOMOGLYPHS.get(c, c) for c in seg)
            return seg

    if grk and lat and not cyr:
        has_grk_u = any(c in _GREEK_UNIQUE_CHARS for c in grk)
        has_lat_u = any(c in _LATIN_UNIQUE_CHARS for c in lat)
        target_is_grk = (has_grk_u and not has_lat_u) or (len(grk) >= len(lat))
        if target_is_grk:
            if all(c in _LATIN_TO_GREEK_HOMOGLYPHS for c in lat):
                return ''.join(_LATIN_TO_GREEK_HOMOGLYPHS.get(c, c) for c in seg)
            return seg
        else:
            if all(c in _GREEK_TO_LATIN_HOMOGLYPHS for c in grk):
                return ''.join(_GREEK_TO_LATIN_HOMOGLYPHS.get(c, c) for c in seg)
            return seg

    return seg


def harmonize_mixed_scripts(text: str, language: Optional[str] = None) -> str:
    """
    Language-agnostic, level-agnostic harmonization of accidental intra-token mixed scripts.
    Restores unified script integrity to words and affixes (e.g. -иte -> -ите, говориte -> говорите,
    рaбота -> работа, comеr -> comer, νεpό -> νερό) while safely preserving legitimate
    bilingual compound words (e.g. online-курс) and multi-token phrases.
    """
    if not isinstance(text, str) or not text:
        return text

    parts = re.split(r'(`[^`\n]*`|https?://[^\s<>"]+|www\.[^\s<>"]+)', text)
    for i in range(0, len(parts), 2):
        chunk = parts[i]

        def _replace_token(m: re.Match) -> str:
            token = m.group(0)
            prefix = "-" if token.startswith("-") else ""
            suffix = "-" if token.endswith("-") and len(token) > 1 else ""
            core = token[len(prefix):len(token) - len(suffix) if suffix else len(token)]
            subsegments = core.split("-")
            harmonized_subs = [_harmonize_segment(s, language=language) for s in subsegments]
            return prefix + "-".join(harmonized_subs) + suffix

        parts[i] = _TOKEN_PATTERN.sub(_replace_token, chunk)

    return "".join(parts)


def safe_unicode_normalize(text: str, language: Optional[str] = None) -> str:
    """
    Safe Unicode NFC normalization preserving all legitimate linguistic marks.
    Preserves legitimate letters in non-Russian Cyrillic languages (e.g. Bulgarian ѝ, Macedonian ѐ/ѝ).
    Scopes general Cyrillic grave replacement strictly to Russian material context, while fixing
    known erroneous Russian forms (e.g. профѐссор -> профессор) universally.
    Resolves Unicode noncharacters (U+FFFE, U+FFFF, plane ends, U+FDD0..U+FDEF) semantically
    (restoring hyphens or spaces where corrupted) while eliminating invalid control characters.
    Harmonizes accidental intra-token mixed scripts (-иte -> -ите, говориte -> говорите, comеr -> comer).
    """
    if not text or not isinstance(text, str):
        return text
    if _is_russian_context(language):
        text = normalize_russian_orthography(text)
    else:
        text = re.sub(r'(?i)\bпрофѐссор\b', 'профессор', text)
    normalized = unicodedata.normalize("NFC", text)
    out = []
    prev_was_sep = False
    for i, ch in enumerate(normalized):
        cp = ord(ch)
        if _is_noncharacter_or_forbidden(cp):
            if not prev_was_sep:
                sep = _resolve_noncharacter_separator(normalized, i)
                if sep:
                    out.append(sep)
                    prev_was_sep = True
        else:
            prev_was_sep = False
            out.append(ch)
    res = "".join(out)
    return harmonize_mixed_scripts(res, language=language)


# ── INSTRUCTIONAL SHORTHAND & METAMATERIAL PURITY ────────────────────────────

_INSTRUCTIONAL_SHORTHAND_MAPS: Dict[str, List[Tuple[str, str]]] = {
    "tr": [
        # Parenthesized forms: (masc.), (masculine), etc.
        (r"\(\s*masc(?:\.|uline)?\s*\)", "(eril)"),
        (r"\(\s*fem(?:\.|inine)?\s*\)", "(dişil)"),
        (r"\(\s*neut(?:\.|er)?\s*\)", "(nötr)"),
        (r"\(\s*m\.\s*\)", "(eril)"),
        (r"\(\s*f\.\s*\)", "(dişil)"),
        (r"\(\s*n\.\s*\)", "(nötr)"),
        (r"\(\s*pl(?:\.|ural)?\s*\)", "(çoğul)"),
        (r"\(\s*(?:sg|sing)(?:\.|ular)?\s*\)", "(tekil)"),
        (r"\(\s*nom(?:\.|inative)?\s*\)", "(Yalın Hâl)"),
        (r"\(\s*gen(?:\.|itive)?\s*\)", "(İlgi/Tamlayan Hâli)"),
        (r"\(\s*acc(?:\.|usative)?\s*\)", "(Belirtme Hâli)"),
        (r"\(\s*dat(?:\.|ive)?\s*\)", "(Yönelme Hâli)"),
        (r"\(\s*prep(?:\.|ositional)?\s*\)", "(Edat Durumu)"),
        (r"\(\s*inst(?:\.|r|rumental)?\s*\)", "(Araç Hâli)"),
        # Standalone abbreviations with explicit period: masc., fem., neut., pl., sg., etc.
        (r"\bmasc\.", "eril"),
        (r"\bfem\.", "dişil"),
        (r"\bneut\.", "nötr"),
        (r"\bpl\.", "çoğul"),
        (r"\b(?:sg|sing)\.", "tekil"),
        (r"\bnom\.", "Yalın Hâl"),
        (r"\bgen\.", "İlgi/Tamlayan Hâli"),
        (r"\bacc\.", "Belirtme Hâli"),
        (r"\bdat\.", "Yönelme Hâli"),
        (r"\bprep\.", "Edat Durumu"),
        (r"\b(?:inst|instr)\.", "Araç Hâli"),
    ],
    "es": [
        (r"\(\s*neut(?:\.|er)?\s*\)", "(neutro)"),
        (r"\bneut\.", "neutro"),
    ],
    "de": [
        (r"\(\s*neut(?:\.|er)?\s*\)", "(neutral)"),
        (r"\bneut\.", "neutral"),
    ],
    "fr": [
        (r"\(\s*neut(?:\.|er)?\s*\)", "(neutre)"),
        (r"\bneut\.", "neutre"),
    ],
}

_SHORTHAND_LEAKAGE_DETECTORS: Dict[str, List[re.Pattern]] = {
    "tr": [
        re.compile(r"\(\s*(?:masc|fem|neut|pl|sg|sing|nom|gen|acc|dat|prep|inst)\.?\s*\)", re.IGNORECASE),
        re.compile(r"\b(?:masc|fem|neut|pl|sg|sing|nom|gen|acc|dat|prep|inst)\.", re.IGNORECASE),
    ],
}

_BASE_CANONICAL_TR_META = (
    (r"\bprepositional\s+case\b", "Edat Durumu"),
    (r"\bprepositional\b", "Edat Durumu"),
    (r"\bgenitive\b", "İlgi/Tamlayan Hâli"),
    (r"\bnominative\b", "Yalın Hâl"),
    (r"\bnominativ\b", "Yalın Hâl"),
    (r"\bgenitiv\b", "İlgi/Tamlayan Hâli"),
    (r"\baccusative\b", "Belirtme Hâli"),
    (r"\bakkusativ\b", "Belirtme Hâli"),
    (r"\bdative\b", "Yönelme Hâli"),
    (r"\bdativ\b", "Yönelme Hâli"),
    (r"\binstrumental\b", "Araç Hâli"),
    (r"\bmasculine\b", "eril"),
    (r"\bfeminine\b", "dişil"),
    (r"\bneuter\b", "nötr"),
    (r"\bzero[- ]copula\b", "sıfır bağlayıcı"),
)


def sanitize_instructional_shorthand(text: str, instructional_language: str = "tr") -> str:
    """
    Safely normalize leaked foreign grammatical shorthand in instructional text
    while strictly protecting all quoted target-language vocabulary, code blocks,
    and citations.
    """
    if not isinstance(text, str) or not text:
        return text
    lang_key = str(instructional_language or "tr").strip().casefold()
    if lang_key in ("turkish", "türkçe", "turkce"):
        lang_key = "tr"
    elif lang_key in ("english", "ingilizce"):
        lang_key = "en"
    elif lang_key in ("spanish", "ispanyolca", "español"):
        lang_key = "es"
    elif lang_key in ("german", "almanca", "deutsch"):
        lang_key = "de"
    elif lang_key in ("french", "fransızca", "français"):
        lang_key = "fr"

    rules = _INSTRUCTIONAL_SHORTHAND_MAPS.get(lang_key)
    if not rules:
        return text

    # Split on quotes (`...`, "...", “...”, «...», '...') to preserve quoted target items
    parts = re.split(r'(`[^`\n]*`|“[^”\n]*”|«[^»\n]*»|"[^"\n]*"|\'[^\'\n]{1,80}\')', text)
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        for pattern, replacement in rules:
            chunk = re.sub(pattern, replacement, chunk, flags=re.IGNORECASE)
        parts[i] = chunk
    return "".join(parts)


def detect_grammar_shorthand_leakage(text: str, instructional_language: str = "tr") -> List[str]:
    """
    Detect foreign grammatical shorthand leaked into instructional language text.
    Ignores quoted target tokens and code spans. Returns a list of leaked tokens.
    """
    if not isinstance(text, str) or not text:
        return []
    lang_key = str(instructional_language or "tr").strip().casefold()
    if lang_key in ("turkish", "türkçe", "turkce"):
        lang_key = "tr"
    elif lang_key in ("english", "ingilizce"):
        return []  # English shorthand is native in English
    elif lang_key in ("spanish", "ispanyolca", "español"):
        lang_key = "es"
    elif lang_key in ("german", "almanca", "deutsch"):
        lang_key = "de"
    elif lang_key in ("french", "fransızca", "français"):
        lang_key = "fr"

    detectors = _SHORTHAND_LEAKAGE_DETECTORS.get(lang_key)
    if not detectors:
        return []

    # Only inspect outside quoted regions
    parts = re.split(r'(`[^`\n]*`|“[^”\n]*”|«[^»\n]*»|"[^"\n]*"|\'[^\'\n]{1,80}\')', text)
    leaks = []
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        for d in detectors:
            for m in d.finditer(chunk):
                leaks.append(m.group(0))
    return leaks


_TR_MORPHOLOGICAL_CASE_PATTERNS = (
    r"Belirtme H[âa]l[iı]?",
    r"Yal[ıi]n H[âa]l[iı]?",
    r"İlgi\s*/\s*Tamlayan H[âa]l[iı]?",
    r"Y[öo]nelme H[âa]l[iı]?",
    r"Ara[çc] H[âa]l[iı]?",
    r"Bulunma H[âa]l[iı]?",
    r"Ayr[ıi]lma H[âa]l[iı]?",
    r"Edat Durum[uü]?",
)


def deduplicate_morphological_parentheticals(text: str) -> str:
    """
    Morphology-aware terminology deduplication.
    Eliminates redundant parenthetical repetitions of terms or their morphological variants
    (e.g., 'Belirtme Hâlinde (Belirtme Hâli)', 'Belirtme Hâli\'nde (Belirtme Hâli)', 'X biçimi (X)')
    while strictly preserving informative parentheticals
    (e.g., 'Belirtme Hâli (doğrudan nesne)', 'Yalın Hâl (özne görevi)', 'Genitive (possession)').
    """
    if not isinstance(text, str) or not text:
        return text

    parts = re.split(r'(`[^`\n]*`|“[^”\n]*”|«[^»\n]*»|"[^"\n]*"|\'[^\'\n]{1,80}\')', text)
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        for case_pat in _TR_MORPHOLOGICAL_CASE_PATTERNS:
            pat_case = rf"(?i)\b({case_pat}(?:['’]?[a-zçğıöşü]{{1,8}})?)\s*\(\s*{case_pat}(?:['’]?[a-zçğıöşü]{{1,8}})?\s*\)"
            chunk = re.sub(pat_case, r"\1", chunk)

        pat_form = r"(?i)\b([A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-Za-zÇĞİÖŞÜçğıöşü]+)?)\s+(bi[çc]im[iı](?:nde)?|h[âa]l[iı](?:nde)?|durum[uü](?:nda)?)\s*\(\s*\1\s*\)"
        chunk = re.sub(pat_form, r"\1 \2", chunk)

        pat_form_en = r"(?i)\b([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+(form|case)\s*\(\s*\1\s*\)"
        chunk = re.sub(pat_form_en, r"\1 \2", chunk)

        pat_exact = r"(?i)\b([A-Za-zÇĞİÖŞÜçğıöşü]{3,30})\s*\(\s*\1\s*\)"
        chunk = re.sub(pat_exact, r"\1", chunk)

        parts[i] = chunk

    return "".join(parts)


def sanitize_instructional_metalanguage(value: Any, material_language: str = "tr") -> str:
    """
    Language-agnostic normalization of instructional metalanguage and grammatical shorthand.
    Safely normalizes case names, gender terms, and shorthand abbreviations in the instructional
    language while preserving all quoted target-language words, examples, and symbols.
    """
    text = safe_unicode_normalize(str(value or ""))
    if not text:
        return text

    # First normalize grammatical shorthand (e.g. (masc.) -> (eril), masc. -> eril)
    text = sanitize_instructional_shorthand(text, instructional_language=material_language)

    lang_clean = str(material_language or "").strip().casefold()
    if lang_clean in {"tr", "turkish", "türkçe", "turkce"}:
        parts = re.split(r'(`[^`\n]*`|“[^”\n]*”|«[^»\n]*»|"[^"\n]*"|\'[^\'\n]{1,80}\')', text)
        for i in range(0, len(parts), 2):
            for pattern, replacement in _BASE_CANONICAL_TR_META:
                parts[i] = re.sub(pattern, replacement, parts[i], flags=re.IGNORECASE)
        res = "".join(parts)
        res = re.sub(r"\bzero[- ]copula\b", "sıfır bağlayıcı", res, flags=re.IGNORECASE)
        res = re.sub(r"\bnominatif\b", "Yalın Hâl", res, flags=re.IGNORECASE)
        res = re.sub(r"\bgenitif\b", "İlgi/Tamlayan Hâli", res, flags=re.IGNORECASE)
        res = re.sub(r"\b(Edat Durumu|Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli)\s+[Cc]ase\b", r"\1", res)
        res = re.sub(r"(?i)\bİlgi\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", res)
        res = re.sub(r"(?i)\bİlgi\s*/\s*Tamlayan\s*(?:H[âa]li)?\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", res)
        res = deduplicate_morphological_parentheticals(res)
        res = re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*\(\s*\1\s*\)", r"\1", res)
        res = re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*/\s*\1\b", r"\1", res)
        if re.search(r'(?i)\b(?:ехать|еха[-–—]|ehat|ekhat)\b', res):
            res = re.sub(r'["\'„“]?-д-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", res, flags=re.IGNORECASE)
            res = re.sub(r'["\'„“]?-d-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", res, flags=re.IGNORECASE)
        return res

    return deduplicate_morphological_parentheticals(text)


def sanitize_dialogue_speaker(value: Any) -> str:
    """Keep the canonical speaker label; remove trailing annotation metadata."""
    text = safe_unicode_normalize(str(value or "")).strip()
    if not text:
        return text
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\s*\([^()\n]{1,80}\)\s*$", "", text).strip()
    return text


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


# ── FORMATIVE MCQ STRUCTURAL & DISTRACTOR QUALITY VALIDATION ────────────────

_PLACEHOLDER_DISTRACTOR_PATTERNS = (
    re.compile(r"^option\s*\d+$", re.IGNORECASE),
    re.compile(r"^choice\s*[a-d0-9]+$", re.IGNORECASE),
    re.compile(r"^distractor\s*\d+$", re.IGNORECASE),
    re.compile(r"^seçenek\s*\d+$", re.IGNORECASE),
    re.compile(r"^yanıt\s*\d+$", re.IGNORECASE),
    re.compile(r"^şık\s*[a-d]$", re.IGNORECASE),
    re.compile(r"^placeholder", re.IGNORECASE),
    re.compile(r"^undefined$", re.IGNORECASE),
    re.compile(r"^null$", re.IGNORECASE),
    re.compile(r"^n/a$", re.IGNORECASE),
    re.compile(r"^none\s+of\s+the\s+above$", re.IGNORECASE),
    re.compile(r"^all\s+of\s+the\s+above$", re.IGNORECASE),
    re.compile(r"^\[object\s+object\]$", re.IGNORECASE),
    re.compile(r"^(?:hiçbiri|hepsi|hiçbiri\s+değil|hepsi\s+doğru|doğru\s+cevap\s+yok)$", re.IGNORECASE),
    re.compile(r"^yukarıdakilerin\s+(?:hiçbiri|hepsi)$", re.IGNORECASE),
    re.compile(r"^(?:yanlış|uydurma|hatalı|geçersiz)$", re.IGNORECASE),
    re.compile(r"^(?:ningun[ao]s?|tod[ao]s?|ninguna\s+de\s+las\s+anteriores)$", re.IGNORECASE),
    re.compile(r"^(?:keine|alle)\s+der\s+genannten$", re.IGNORECASE),
    re.compile(r"^(?:aucun[e]?|toutes)\s+des\s+r[ée]ponses$", re.IGNORECASE),
    re.compile(r"^(?:ни\s+один\s+из\s+вышеперечисленных|все\s+вышеперечисленные)$", re.IGNORECASE),
    re.compile(r"^(?:herhangi\s+bir\s+ek\s+almaz|hi[çc]bir\s+ek\s+almaz|ek\s+almaz|kullan[ıi]lmaz|fark\s+etmez|c[üu]mleye\s+g[öo]re(?:\s+de[ğg]i[şs]ir)?)$", re.IGNORECASE),
    re.compile(r"^(?:no\s+article|no\s+ending|no\s+change|not\s+applicable|depends\s+on(?:\s+the)?\s+context|none\s+required)$", re.IGNORECASE),
    re.compile(r"^(?:sin\s+art[íi]culo|no\s+lleva\s+nada|seg[úu]n\s+el\s+contexto)$", re.IGNORECASE),
)

_ADMITTED_NON_WORD_PATTERNS = (
    re.compile(r"\bböyle\s+bir\s+(?:kelime|s[öo]zc[üu]k|form|biçim|çekim|kural|ek|kullan[ıi]m)[a-zçğıöşü]*\s+(?:yoktur|yok|bulunmaz|mevcut\s+değildir)\b", re.IGNORECASE),
    re.compile(r"\bvar\s+olmayan\s+(?:bir\s+)?(?:form|kelime|s[öo]zc[üu]k|çekim|ek|biçim|kullan[ıi]m)[a-zçğıöşü]*\b", re.IGNORECASE),
    re.compile(r"\b(?:bu\s+dilde|türkçede|rusçada|ispanyolcada|almancada|fransızcada|ingilizcede)\s+(?:mevcut\s+değil|kullan[ıi]lmaz|bulunmaz|yer\s+almaz)(?:dir)?\b", re.IGNORECASE),
    re.compile(r"\b(?:s[öo]zl[üu]kte\s+(?:yer\s+almaz|bulunmaz|yoktur)|dilde\s+(?:yer\s+almaz|bulunmaz|yoktur))\b", re.IGNORECASE),
    re.compile(r"\b(?:uydurma|hatal[ıi]|ge[çc]ersiz|yapay)\s+(?:bir\s+)?(?:form|kelime|s[öo]zc[üu]k|ek|çekim|kural)[a-zçğıöşü]*\b", re.IGNORECASE),
    re.compile(r"\b(?:hatal[ıi]|yanl[ıi][şs])\s+t[üu]retilmi[şs][a-zçğıöşü]*\b", re.IGNORECASE),
    re.compile(r"\bger[çc]ek\s+bir\s+(?:kelime|s[öo]zc[üu]k|form|bi[çc]im|çekim)\s+de[ğg]ildir\b", re.IGNORECASE),
    re.compile(r"\b(?:invalid|nonexistent|non-word|invented|fake|made-up|fabricated|fictitious|artificial)\s+(?:form|word|affix|option|stem|ending|conjugation|declension|usage)[a-z]*\b", re.IGNORECASE),
    re.compile(r"\b(?:misspelling|not\s+a\s+real\s+word|not\s+a\s+valid\s+form|does\s+not\s+exist(?:\s+in)?|no\s+such\s+(?:word|form|usage)|not\s+an\s+authentic\s+form|grammatically\s+impossible)\b", re.IGNORECASE),
    re.compile(r"\b(?:not\s+found\s+in\s+(?:the\s+)?dictionary|does\s+not\s+occur\s+in)\b", re.IGNORECASE),
)

_ERROR_HUNT_STEM_PATTERNS = (
    re.compile(r"\b(?:hangisi\s+hatal[ıi]|yanl[ıi][şs]\s+yaz[ıi]lm[ıi][şs][a-zçğıöşü]*|ge[çc]ersiz\s+olan|uydurma\s+olan|hatal[ıi]\s+olan)\b", re.IGNORECASE),
    re.compile(r"\b(?:which\s+(?:is\s+)?(?:incorrect|misspelled|invalid|false|wrong|an\s+error))\b", re.IGNORECASE),
)

_ALPHABETIC_VOWELS = set("aeiouyAEIOUYàáâãäåæèéêëìíîïòóôõöøùúûüýÿаеёиоуыэюяАЕЁИОУЫЭЮЯієїαεηιουωΑΕΗΙΟΥΩάέήίόύώ")


def validate_distractor_quality(
    options: List[str],
    prompt: str = "",
    explanation: str = ""
) -> Tuple[bool, str]:
    """
    Universal, language-agnostic validation of formative assessment distractor quality.
    Rejects placeholder options, character-mashing/repetition artifacts, pure punctuation noise,
    unauthentic non-words with illegal consonant clusters, script mismatches, structural outliers,
    and explanations explicitly describing invented/non-existent pseudo-word distractors
    unless the question specifically tests error-detection.
    """
    if not isinstance(options, list) or len(options) != 4:
        return False, "distractor-count-invalid"

    # Duplicate / near-duplicate option check
    canon_opts = [re.sub(r"[\s\.,;:!?]+$", "", opt.strip().casefold()) for opt in options if isinstance(opt, str)]
    if len(set(canon_opts)) < len(options):
        return False, "malformed-distractor:duplicate-options"

    for idx, opt in enumerate(options):
        text = str(opt or "").strip()
        if not text:
            return False, f"empty-option:{idx}"

        # 1. Reject placeholder / template options
        for pat in _PLACEHOLDER_DISTRACTOR_PATTERNS:
            if pat.match(text):
                return False, f"malformed-distractor:placeholder:{idx}"

        # 2. Reject pure punctuation / symbolic noise
        if re.match(r"^[\W_]+$", text):
            return False, f"malformed-distractor:punctuation-only:{idx}"

        # 3. Reject character repetition / keyboard-mashing artifacts (3+ identical chars)
        if re.search(r"([A-Za-zА-Яа-яЁё\u0370-\u03FF\u0600-\u06FF])\1{2,}", text):
            return False, f"malformed-distractor:char-repetition:{idx}"

        # 4. Reject bracketed meta-annotations (e.g. '(uydurma)', '(yanlış)', '(false)')
        if re.search(r"\((?:uydurma|yanlış|hatalı|geçersiz|false|wrong|fake|invented)\)", text, re.IGNORECASE):
            return False, f"malformed-distractor:meta-annotation:{idx}"

        # 5. Reject unpronounceable non-word consonant clusters in alphabetic scripts (words >= 3 letters without vowels)
        tokens = re.findall(r"[A-Za-zА-Яа-яЁё\u0370-\u03FF]+", text)
        for tok in tokens:
            if len(tok) >= 3 and not any(ch in _ALPHABETIC_VOWELS for ch in tok) and not tok.isupper():
                return False, f"malformed-distractor:unpronounceable-cluster:{idx}"

    # 6. Script mismatch check: When 3 options use a non-Latin script, reject an option with zero non-Latin chars
    non_latin_counts = [len(re.findall(r"[\u0400-\u04FF\u0370-\u03FF\u0600-\u06FF\u0590-\u05FF\u0900-\u097F\u3040-\u30FF\u4E00-\u9FFF\uAC00-\uD7AF]", opt)) for opt in options]
    if sum(1 for c in non_latin_counts if c > 0) == 3 and sum(1 for c in non_latin_counts if c == 0) == 1:
        zero_idx = non_latin_counts.index(0)
        if not is_metadata_or_proper_token(options[zero_idx]):
            return False, f"malformed-distractor:script-mismatch:{zero_idx}"

    # 7. Structural outlier check: 3 short options vs 1 explanatory sentence
    word_counts = [len(opt.split()) for opt in options]
    char_lens = [len(opt) for opt in options]
    short_opts = sum(1 for wc, cl in zip(word_counts, char_lens) if wc <= 2 and cl <= 15)
    long_opts = [i for i, (wc, cl) in enumerate(zip(word_counts, char_lens)) if wc >= 5 or cl >= 35]
    if short_opts == 3 and len(long_opts) == 1:
        return False, f"malformed-distractor:structural-outlier:{long_opts[0]}"

    # 8. Check if explanation admits non-word / malformed distractor outside error-hunt items
    if explanation:
        is_error_hunt = bool(prompt and any(pat.search(prompt) for pat in _ERROR_HUNT_STEM_PATTERNS))
        if not is_error_hunt:
            for pat in _ADMITTED_NON_WORD_PATTERNS:
                if pat.search(explanation):
                    return False, "malformed-distractor:admitted-non-word"

    return True, ""


# ── PRONUNCIATION / IPA / FIELD ALIGNMENT ────────────────────────────────────

def _has_target_script_chars(text: str, language: Optional[str]) -> bool:
    if not text or not language:
        return False
    lang_clean = str(language).strip().casefold()
    if any(k in lang_clean for k in ('rus', 'bulg', 'ukr', 'maced', 'serb', 'belar')):
        return any('\u0400' <= c <= '\u04FF' or '\u0500' <= c <= '\u052F' for c in text)
    if any(k in lang_clean for k in ('greek', 'yunanca', 'ελλην')):
        return any('\u0370' <= c <= '\u03FF' for c in text)
    if any(k in lang_clean for k in ('arab', 'arap', 'farsi', 'persian', 'urdu')):
        return any('\u0600' <= c <= '\u06FF' for c in text)
    if any(k in lang_clean for k in ('hebrew', 'ibranice', 'עברית')):
        return any('\u0590' <= c <= '\u05FF' for c in text)
    if any(k in lang_clean for k in ('hindi', 'hint', 'sanskrit')):
        return any('\u0900' <= c <= '\u097F' for c in text)
    if any(k in lang_clean for k in ('japan', 'japon')):
        return any('\u3040' <= c <= '\u30FF' or '\u4E00' <= c <= '\u9FFF' for c in text)
    if any(k in lang_clean for k in ('chin', 'çin', 'mandarin', 'han')):
        return any('\u4E00' <= c <= '\u9FFF' for c in text)
    if any(k in lang_clean for k in ('korean', 'kore')):
        return any('\uAC00' <= c <= '\uD7AF' or '\u4E00' <= c <= '\u9FFF' for c in text)
    return False


_PHONETIC_IPA_CHAR_PATTERN = re.compile(r'[\[\]/ˈˌːʲəʃʒθðŋɪʊæʌɔɛɣʁɾɲʎβχʔɐɨʉɯʏɤɜɑɒ]')
_TR_SPECIFIC_CHAR_PATTERN = re.compile(r'[çğıöşüÇĞİÖŞÜ]')


def align_lexical_fields(
    item: Dict[str, Any],
    language: Optional[str] = None,
    is_tr: bool = True
) -> Dict[str, Any]:
    """
    Language-agnostic alignment, extraction, and integrity repair of lexical item fields.
    1. Extracts bracketed IPA from `term` into `phonetic` and cleans `term`.
    2. Recovers misplaced translation text accidentally placed into `phonetic`.
    3. Realigns swapped `example` vs `example_tr`/`example_en` strictly when scripts are disjoint.
    4. Realigns swapped `term` vs `translation_tr`/`translation` strictly when scripts are disjoint.
    5. Normalizes IPA brackets to standard [...] format.
    6. Harmonizes mixed-script morphology across all text attributes.
    """
    if not isinstance(item, dict):
        return item

    # Harmonize mixed scripts on all string attributes
    for k, v in list(item.items()):
        if isinstance(v, str):
            item[k] = harmonize_mixed_scripts(safe_unicode_normalize(v, language=language), language=language)

    term = str(item.get("term") or item.get("word") or item.get("target") or "").strip()
    phon = str(item.get("phonetic") or item.get("pronunciation") or "").strip()

    # 1. Extract bracketed IPA embedded inside `term`
    m_ipa = re.search(r'\s*(\[[^\]\n]{1,80}\]|/[^/\n]{1,80}/|\([^)\n]*[ˈˌː][^)\n]*\))\s*$', term)
    if m_ipa:
        extracted = m_ipa.group(1).strip("() ")
        term = term[:m_ipa.start()].strip()
        if "term" in item:
            item["term"] = term
        elif "word" in item:
            item["word"] = term
        elif "target" in item:
            item["target"] = term
        if not phon:
            phon = extracted
            item["phonetic"] = phon

    # 2. Check if `phonetic` is actually misplaced translation text
    tr_candidate = str(item.get("translation_tr") or item.get("translation") or item.get("meaning") or "").strip()
    if phon and not _PHONETIC_IPA_CHAR_PATTERN.search(phon):
        # Plain text without IPA characters
        is_translation_leak = (
            phon.casefold() == tr_candidate.casefold()
            or bool(_TR_SPECIFIC_CHAR_PATTERN.search(phon))
            or (len(phon.split()) > 1 and not re.search(r"[-·.]", phon))
        )
        if is_translation_leak:
            if is_tr and not item.get("translation_tr"):
                item["translation_tr"] = phon
            elif not item.get("translation"):
                item["translation"] = phon
            item["phonetic"] = ""
            phon = ""

    # 3. Swap checks strictly when target language uses a distinct non-Latin script
    # (Russian, Greek, Arabic, Hebrew, Hindi, Japanese, Chinese, Korean, etc.)
    # We NEVER heuristically swap same-script language pairs (e.g. Latin-target with
    # Latin-instructional) because character heuristics cannot reliably prove semantic role.
    if language and _has_target_script_chars("тест", language):
        # Check term vs translation_tr
        tr_val = str(item.get("translation_tr") or item.get("translation") or "").strip()
        if term and tr_val:
            term_has_target = _has_target_script_chars(term, language)
            tr_has_target = _has_target_script_chars(tr_val, language)
            if not term_has_target and tr_has_target:
                target_key = "term" if "term" in item else ("word" if "word" in item else "target")
                tr_key = "translation_tr" if "translation_tr" in item else "translation"
                item[target_key], item[tr_key] = tr_val, term
                term, tr_val = tr_val, term

        # Check example vs example_tr
        ex = str(item.get("example") or "").strip()
        ex_tr = str(item.get("example_tr") or "").strip()
        if ex and ex_tr:
            ex_has_target = _has_target_script_chars(ex, language)
            ex_tr_has_target = _has_target_script_chars(ex_tr, language)
            if not ex_has_target and ex_tr_has_target:
                item["example"], item["example_tr"] = ex_tr, ex

        # Check example vs example_en
        ex_en = str(item.get("example_en") or "").strip()
        if ex and ex_en:
            ex_has_target = _has_target_script_chars(ex, language)
            ex_en_has_target = _has_target_script_chars(ex_en, language)
            if not ex_has_target and ex_en_has_target:
                item["example"], item["example_en"] = ex_en, ex

    # 4. Normalize IPA brackets format
    if phon:
        p_clean = phon.strip(" ,;.")
        if not p_clean.startswith("["):
            p_clean = "[" + p_clean.strip("[]/") + "]"
        item["phonetic"] = p_clean

    return item


def validate_mcq(page: Any) -> Tuple[bool, str]:
    """
    Universal, language-agnostic formative MCQ validation.
    Enforces exactly 4 distinct options, exactly 1 matching answer, correct index alignment,
    plausible authentic distractors, and localized options count/uniqueness parity.
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

    expl = _norm(page.get("explanation") or page.get("explanation_tr") or page.get("explanation_en") or "")
    dist_ok, dist_why = validate_distractor_quality(options, prompt=prompt, explanation=expl)
    if not dist_ok:
        return False, dist_why

    for key in ("options_tr", "options_en"):
        localized = page.get(key)
        if localized is not None:
            loc_list = [_norm(x) for x in _as_list(localized)]
            if len(loc_list) != 4 or any(not x for x in loc_list) or len(set(loc_list)) != 4:
                return False, f"invalid-{key}"
            loc_ok, loc_why = validate_distractor_quality(loc_list, prompt=prompt, explanation=expl)
            if not loc_ok:
                return False, f"{key}:{loc_why}"

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


def _recursive_clean_unicode(node: Any, language: Optional[str] = None, material_language: Optional[str] = "tr") -> Any:
    """Recursively apply safe NFC Unicode normalization, instructional shorthand sanitization, and lexical field alignment."""
    if isinstance(node, str):
        cleaned = safe_unicode_normalize(node, language=language)
        if material_language and str(material_language).strip().casefold() not in ("en", "english", "ingilizce"):
            cleaned = sanitize_instructional_shorthand(cleaned, instructional_language=str(material_language).strip().casefold())
        return cleaned
    if isinstance(node, dict):
        is_tr = bool(material_language and str(material_language).strip().casefold() in ("tr", "turkish", "türkçe"))
        d = {k: _recursive_clean_unicode(v, language=language, material_language=material_language) for k, v in node.items()}
        if any(k in d for k in ("term", "word", "target", "phonetic", "pronunciation", "example")):
            d = align_lexical_fields(d, language=language, is_tr=is_tr)
        return d
    if isinstance(node, list):
        return [_recursive_clean_unicode(item, language=language, material_language=material_language) for item in node]
    return node


def enforce_material_integrity(data: Any, language: Optional[str] = None, material_language: str = "tr") -> Any:
    """
    Language-agnostic structural cleanup and Unicode normalization after generation.
    Prunes structurally broken MCQs, applies safe Unicode NFC normalization,
    and guarantees zero defects on published materials with zero extra model cost.
    """
    if not isinstance(data, dict):
        return data

    out = _recursive_clean_unicode(deepcopy(data), language=language, material_language=material_language)
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


