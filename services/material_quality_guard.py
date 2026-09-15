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


def _resolve_mcq_prompt(page: Any) -> str:
    """Resolve an MCQ stem across canonical and localized prompt keys.

    A localized-only item (for example one carrying `prompt_tr` but no canonical
    `prompt`) is a legitimate persisted shape, not a malformed question. Requiring
    the canonical key would make structural validation reject valid material, which
    is how a stricter gate turns into content loss.
    """
    if not isinstance(page, dict):
        return ""
    for key in ("prompt", "question", "stem"):
        value = _norm(page.get(key))
        if value:
            return value
    for key, value in page.items():
        base = re.sub(r"_[a-z]{2}$", "", str(key).casefold())
        if base in ("prompt", "question", "stem") and _norm(value):
            return _norm(value)
    return _norm(page.get("text"))


def validate_mcq(page: Any) -> Tuple[bool, str]:
    """
    Universal, language-agnostic formative MCQ validation.
    Enforces exactly 4 distinct options, exactly 1 matching answer, correct index alignment,
    plausible authentic distractors, and localized options count/uniqueness parity.
    """
    if not isinstance(page, dict):
        return False, "mcq-not-dict"

    prompt = _resolve_mcq_prompt(page)
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




# AULAAI_RELEASE_HARDENING_V50
_V50_HYPHEN_EQUIV = {"\u00ad", "\u2010", "\u2011", "\ufe63", "\uff0d"}
_V50_DROP = {"\u200b", "\ufeff", "\u2060"}
_V50_NONCHARS = {"\ufffe", "\uffff"}
_V50_IPA_SIGNAL = set("ˈˌːˑəɐɛɪʊʌɨøœɶʏɯɤɑɒɕʑʂʐʒʃθðʔʲʷˤɣʁħʕŋɲɳɴɱɭʎʟɾɺⱱβɸɹɻɰʍçɡ")
_V50_CYRILLIC_GRAVE_MAP = {
    "\u0450": "\u0435",  # ѐ -> е
    "\u0400": "\u0415",  # Ѐ -> Е
    "\u045D": "\u0438",  # ѝ -> и
    "\u040D": "\u0418",  # Ѝ -> И
}


def _v50_is_russian(language=None):
    if not language:
        return False
    return str(language).strip().casefold() in ("russian", "rusça", "rusca", "rus", "ru")


def _v50_is_nonchar_or_forbidden(cp: int) -> bool:
    return (
        0xFDD0 <= cp <= 0xFDEF
        or (cp & 0xFFFE) == 0xFFFE
        or 0xD800 <= cp <= 0xDFFF
        or (cp < 0x20 and cp not in (0x09, 0x0A, 0x0D))
        or (0x7F <= cp <= 0x9F)
        or cp == 0xFFFD
    )


def _v50_is_cyrillic(char: str) -> bool:
    return '\u0400' <= char <= '\u04FF' or '\u0500' <= char <= '\u052F'


def _v50_is_latin(char: str) -> bool:
    return ('a' <= char <= 'z') or ('A' <= char <= 'Z') or ('\u00C0' <= char <= '\u024F')


def _v50_resolve_separator(text: str, i: int) -> str:
    n = len(text)
    p = i - 1
    while p >= 0 and (_v50_is_nonchar_or_forbidden(ord(text[p])) or text[p] in _V50_DROP):
        p -= 1
    nxt_idx = i + 1
    while nxt_idx < n and (_v50_is_nonchar_or_forbidden(ord(text[nxt_idx])) or text[nxt_idx] in _V50_DROP):
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

    prev_clean = re.sub(r'[\u0300-\u036f]', '', prev_word).lower()
    nxt_clean = re.sub(r'[\u0300-\u036f]', '', nxt_word).lower()

    if prev_clean in ('по', 'кое', 'из') and _v50_is_cyrillic(next_ch):
        return '-'
    if nxt_clean in ('то', 'либо', 'нибудь', 'таки') and _v50_is_cyrillic(prev_ch):
        return '-'
    if prev_word.startswith('-') and next_ch.isalnum():
        return ' '
    if (_v50_is_cyrillic(prev_ch) and _v50_is_latin(next_ch)) or (_v50_is_latin(prev_ch) and _v50_is_cyrillic(next_ch)):
        return ' '
    if nxt_clean in ('ve', 'ile', 'veya', 'and', 'or', 'und', 'y', 'и', 'или', 'а', 'но', 'de', 'da'):
        return ' '
    if prev_clean in ('ve', 'ile', 'veya', 'and', 'or', 'und', 'y', 'и', 'или', 'а', 'но', 'de', 'da'):
        return ' '
    if prev_clean.endswith(('lik', 'lık', 'luk', 'lük')) and nxt_clean.endswith(('lik', 'lık', 'luk', 'lük')):
        return '-'
    if prev_ch.isalnum() and next_ch.isalnum():
        return ' '
    return ''


def safe_unicode_normalize(text: str, language=None) -> str:
    if not text or not isinstance(text, str):
        return text
    if _v50_is_russian(language):
        for k, v in _V50_CYRILLIC_GRAVE_MAP.items():
            text = text.replace(k, v)
        text = re.sub(r'([\u0400-\u04FF])\u0300', r'\1', text)
    else:
        text = re.sub(r'(?i)\bпрофѐссор\b', 'профессор', text)
    text = unicodedata.normalize("NFC", text)
    out = []
    prev_was_sep = False
    for i, ch in enumerate(text):
        cp = ord(ch)
        if ch in _V50_HYPHEN_EQUIV:
            out.append("-")
            prev_was_sep = True
            continue
        if ch in _V50_DROP or ch == "\ufffd":
            continue
        if ch in _V50_NONCHARS or 0xFDD0 <= cp <= 0xFDEF or (cp & 0xFFFE) == 0xFFFE:
            if not prev_was_sep:
                sep = _v50_resolve_separator(text, i)
                if sep:
                    out.append(sep)
                    prev_was_sep = True
            continue
        if 0xD800 <= cp <= 0xDFFF:
            continue
        if (cp < 0x20 and cp not in (0x09, 0x0A, 0x0D)) or (0x7F <= cp <= 0x9F):
            continue
        prev_was_sep = False
        out.append(ch)
    return "".join(out)


def _v50_clean_tree(node, language=None, material_language="tr"):
    if isinstance(node, str):
        cleaned = safe_unicode_normalize(node, language=language)
        if material_language and str(material_language).strip().casefold() not in ("en", "english", "ingilizce"):
            try:
                from services.material_quality_guard import sanitize_instructional_shorthand
                cleaned = sanitize_instructional_shorthand(cleaned, instructional_language=str(material_language).strip().casefold())
            except Exception:
                pass
        return cleaned
    if isinstance(node, dict):
        return {k: _v50_clean_tree(v, language=language, material_language=material_language) for k, v in node.items()}
    if isinstance(node, list):
        return [_v50_clean_tree(v, language=language, material_language=material_language) for v in node]
    return node


def _v50_heal_bracketed_ipa(text: str) -> str:
    if not isinstance(text, str) or "[" not in text or "]" not in text:
        return text

    def repl(match):
        inner = match.group(1)
        if "-" not in inner or not any(ch in _V50_IPA_SIGNAL for ch in inner):
            return match.group(0)
        return "[" + re.sub(r"(?<=\w)-(?=[\wˈˌ])|(?<=[ˈˌ])-|-(?=[ˈˌ])", "", inner) + "]"

    return re.sub(r"\[([^\]\n]{1,160})\]", repl, text)


def _v50_pron_parentheticals(text: str):
    if not isinstance(text, str):
        return []
    found = []
    for m in re.finditer(r"\s*\(([^()]{1,80})\)", text):
        inner = m.group(1)
        brackets = re.findall(r"\[[^\]\n]{1,60}\]", inner)
        if len(brackets) != 1 or ":" not in inner:
            continue
        rest = inner.replace(brackets[0], "").strip()
        if len(rest) <= 40:
            found.append((m.span(), _v50_heal_bracketed_ipa(brackets[0])))
    return found


def _v50_strip_pron_parentheticals(text: str) -> str:
    spans = _v50_pron_parentheticals(text)
    if not spans:
        return text
    result = text
    for (start, end), _ in reversed(spans):
        result = result[:start] + result[end:]
    return re.sub(r"\s{2,}", " ", result).strip()


def _v50_repair_lexical_item(item):
    if not isinstance(item, dict):
        return
    phon = str(item.get("phonetic") or "").strip()
    fields = (
        "translation", "translation_tr", "meaning", "meaning_tr",
        "gloss", "gloss_tr", "definition", "definition_tr",
    )

    if not phon:
        for key in fields:
            value = item.get(key)
            spans = _v50_pron_parentheticals(value) if isinstance(value, str) else []
            if spans:
                item["phonetic"] = spans[0][1]
                item[key] = _v50_strip_pron_parentheticals(value)
                phon = item["phonetic"]
                break

    if phon:
        item["phonetic"] = _v50_heal_bracketed_ipa(phon)
        for key in fields:
            if isinstance(item.get(key), str):
                item[key] = _v50_strip_pron_parentheticals(item[key])


def _v50_walk(node):
    if isinstance(node, dict):
        if any(k in node for k in ("term", "word", "phrase", "expression", "target")):
            _v50_repair_lexical_item(node)
        for key, value in list(node.items()):
            if isinstance(value, str):
                node[key] = _v50_heal_bracketed_ipa(value)
            elif isinstance(value, (dict, list)):
                _v50_walk(value)
    elif isinstance(node, list):
        for value in node:
            _v50_walk(value)


def enforce_material_integrity(data, language=None, material_language="tr"):
    if not isinstance(data, dict):
        return data
    out = _v50_clean_tree(deepcopy(data), language=language, material_language=material_language)
    _v50_walk(out)

    pages = out.get("pages")
    if isinstance(pages, list):
        for page in pages:
            if not isinstance(page, dict):
                continue
            if str(page.get("type") or "").strip().lower() == "mcq":
                opts = [_norm(x) for x in _as_list(page.get("options") or page.get("choices"))]
                ans = _norm(page.get("answer"))
                if len(opts) == 4 and ans in opts:
                    page["correct_index"] = opts.index(ans)
    out.pop("_integrity_removed_mcq", None)
    return out


# AULAAI_RELEASE_HARDENING_V51
def sanitize_dialogue_speaker(value):
    """Keep the canonical speaker label; remove trailing annotation metadata."""
    text = safe_unicode_normalize(str(value or "")).strip()
    if not text:
        return text
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\s*\([^()\n]{1,80}\)\s*$", "", text).strip()
    return text


# AULAAI_RELEASE_HARDENING_V52
_TR_FIXED_META = (
    (r"\bprepositional\b", "Edat Durumu"),
    (r"\bgenitive\b", "İlgi/Tamlayan Hâli"),
    (r"\bnominative\b", "Yalın Hâl"),
    (r"\baccusative\b", "Belirtme Hâli"),
    (r"\bdative\b", "Yönelme Hâli"),
    (r"\binstrumental\b", "Araç Hâli"),
    (r"\bmasculine\b", "eril"),
    (r"\bfeminine\b", "dişil"),
    (r"\bneuter\b", "nötr"),
    (r"\bnominativ\b", "Yalın Hâl"),
    (r"\bgenitiv\b", "İlgi/Tamlayan Hâli"),
    (r"\bakkusativ\b", "Belirtme Hâli"),
    (r"\bdativ\b", "Yönelme Hâli"),
)


def sanitize_instructional_metalanguage(value, material_language="tr"):
    text = safe_unicode_normalize(str(value or ""))
    if str(material_language or "").strip().casefold() not in {"tr", "turkish", "türkçe", "turkce"}:
        return text
    parts = re.split(r'(`[^`\n]*`|“[^”\n]*”|«[^»\n]*»|"[^"\n]*")', text)
    for i in range(0, len(parts), 2):
        for pattern, replacement in _TR_FIXED_META:
            parts[i] = re.sub(pattern, replacement, parts[i], flags=re.IGNORECASE)
    res = "".join(parts)
    res = re.sub(r"(?i)\bİlgi\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", res)
    res = re.sub(r"(?i)\bİlgi\s*/\s*Tamlayan\s*(?:H[âa]li)?\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", res)
    res = re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*\(\s*\1\s*\)", r"\1", res)
    if re.search(r'(?i)\b(?:ехать|еха[-–—]|ehat|ekhat)\b', res):
        res = re.sub(r'["\'„“]?-д-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", res, flags=re.IGNORECASE)
        res = re.sub(r'["\'„“]?-d-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", res, flags=re.IGNORECASE)
    return res


# AULAAI_V54_META_COMPAT
import re as _v54_meta_re
_v54_meta_previous = sanitize_instructional_metalanguage


def sanitize_instructional_metalanguage(value, material_language="tr"):
    text = _v54_meta_previous(value, material_language)
    if str(material_language or "").strip().casefold() not in {"tr", "turkish", "türkçe", "turkce"}:
        return text
    labels = r"Yalın Hâl|İlgi/Tamlayan Hâli|Belirtme Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu"
    text = _v54_meta_re.sub(rf"\b({labels})\s+[Cc]ase\b", r"\1", text)
    text = _v54_meta_re.sub(r"\bEdat Durumu\s*/\s*Edat Hali\b", "Edat Durumu", text, flags=_v54_meta_re.IGNORECASE)
    return text


# AULAAI_RELEASE_HARDENING_V54
_v54_previous_integrity = enforce_material_integrity


def _v54_fold(text):
    text = unicodedata.normalize("NFD", str(text or "")).casefold()
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _v54_collect_authoritative_phonetics(node, out):
    if isinstance(node, dict):
        term = node.get("term") or node.get("word") or node.get("phrase") or node.get("target")
        phon = str(node.get("phonetic") or "").strip()
        if term and phon.startswith("[") and phon.endswith("]"):
            key = _v54_fold(term).strip()
            if len(key) >= 2:
                out[key] = phon
        for value in node.values():
            _v54_collect_authoritative_phonetics(value, out)
    elif isinstance(node, list):
        for value in node:
            _v54_collect_authoritative_phonetics(value, out)


def _v54_compact(text):
    """Script-agnostic identity key: fold, then drop punctuation/space/format chars."""
    folded = _v54_fold(text)
    return "".join(
        ch for ch in folded
        if not unicodedata.category(ch).startswith(("P", "Z", "C"))
    )


def _v54_sync_one_string(text, phonetics):
    """Align a bracketed transcription in prose with the authoritative `phonetic`
    of the headword it actually annotates.

    The original implementation replaced the transcription with the IPA of the
    FIRST headword found anywhere in the sentence, in dictionary order. A sentence
    that mentions two headwords therefore had a good chance of being rebound to the
    wrong one, which is what produced answer-key defects of the shape
    "<phrase A> [<IPA of phrase B>]".

    The rule now is: sync only when the sentence unambiguously identifies which
    headword the transcription belongs to.
      * exactly one known headword in the sentence -> that one is the referent;
      * several headwords -> only a headword immediately preceding the bracket
        qualifies (longest wins);
      * no adjacent headword, or a tie between different transcriptions -> leave
        the text exactly as authored.
    """
    if not isinstance(text, str) or "[" not in text or "]" not in text:
        return text
    groups = list(re.finditer(r"\[[^\]\n]{1,100}\]", text))
    if len(groups) != 1:
        return text
    group = groups[0]

    sentence_key = _v54_compact(text)
    present = [
        (term, phon) for term, phon in phonetics.items()
        if term and _v54_compact(term) and _v54_compact(term) in sentence_key
    ]
    if not present:
        return text

    if len(present) == 1:
        authoritative = present[0][1]
    else:
        lead_key = _v54_compact(text[: group.start()])
        adjacent = [
            (term, phon) for term, phon in present
            if lead_key.endswith(_v54_compact(term))
        ]
        if not adjacent:
            # Several candidate headwords and none of them annotates this bracket:
            # guessing here is exactly the defect this function used to cause.
            return text
        longest = max(len(_v54_compact(term)) for term, _ in adjacent)
        best = [phon for term, phon in adjacent if len(_v54_compact(term)) == longest]
        if len({_v54_fold(p) for p in best}) != 1:
            return text
        authoritative = best[0]

    if _v54_fold(group.group(0)) == _v54_fold(authoritative):
        return text
    return text[: group.start()] + authoritative + text[group.end():]


def _v54_sync_prose_phonetics(node, phonetics, parent_key=""):
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key == "phonetic":
                continue
            if isinstance(value, str):
                node[key] = _v54_sync_one_string(value, phonetics)
            elif isinstance(value, (dict, list)):
                _v54_sync_prose_phonetics(value, phonetics, key)
    elif isinstance(node, list):
        for value in node:
            _v54_sync_prose_phonetics(value, phonetics, parent_key)


def _v54_prompt_key(page, material_language):
    tr = str(material_language or "").casefold() in {"tr", "turkish", "türkçe", "turkce"}
    candidates = ("prompt_tr", "question_tr", "stem_tr", "prompt", "question", "stem") if tr else ("prompt_en", "question_en", "stem_en", "prompt", "question", "stem")
    return next((k for k in candidates if isinstance(page.get(k), str) and page.get(k).strip()), None)


def _v54_explanation_key(page, material_language):
    tr = str(material_language or "").casefold() in {"tr", "turkish", "türkçe", "turkce"}
    candidates = ("explanation_tr", "explanation", "explanation_en") if tr else ("explanation_en", "explanation", "explanation_tr")
    return next((k for k in candidates if isinstance(page.get(k), str) and page.get(k).strip()), None)


def _v54_is_mcq(page, material_language):
    if not isinstance(page, dict):
        return False
    if str(page.get("type") or "").casefold() == "mcq":
        return True
    return bool((page.get("options") or page.get("choices")) and _v54_prompt_key(page, material_language))


def _v54_unsafe_mcq(page, material_language):
    """High-precision rejection only: remove questions whose keyed answer needs an unstated identity fact."""
    if not _v54_is_mcq(page, material_language):
        return False
    pk = _v54_prompt_key(page, material_language)
    ek = _v54_explanation_key(page, material_language)
    prompt = str(page.get(pk) or "") if pk else ""
    explanation = str(page.get(ek) or "") if ek else ""
    p = _v54_fold(prompt)
    e = _v54_fold(explanation)

    explicit_gender = bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", p))
    gender_reason = bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", e))
    name_reason = bool(re.search(r"\b(isim|adi|adinin|name)\b", e))
    if name_reason and gender_reason and not explicit_gender:
        return True

    biography_markers = (
        "dogdu", "dogmus", "yasiyor", "yasadi", "calisiyor", "calisti",
        "born", "lives", "lived", "works", "worked", "resides", "resided",
        "родил", "жив", "работ", "nacio", "nacido", "vive", "trabaja",
        "geboren", "lebt", "arbeitet", "nee", "habite", "travaille",
    )
    biography = any(marker in p for marker in biography_markers)
    identity_result = bool(re.search(
        r"\b(milliyet|uyruk|nationality|national|dil|konus|language|speak|speaks|spoken|meslek|profession|occupation|job)\b",
        e,
    ))
    if biography and identity_result:
        return True
    return False


def _v54_prune_unsafe_mcqs(node, material_language):
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if isinstance(value, list):
                kept = []
                for item in value:
                    if isinstance(item, dict) and _v54_unsafe_mcq(item, material_language):
                        continue
                    _v54_prune_unsafe_mcqs(item, material_language)
                    kept.append(item)
                node[key] = kept
            elif isinstance(value, dict):
                _v54_prune_unsafe_mcqs(value, material_language)
    elif isinstance(node, list):
        kept = []
        for item in node:
            if isinstance(item, dict) and _v54_unsafe_mcq(item, material_language):
                continue
            _v54_prune_unsafe_mcqs(item, material_language)
            kept.append(item)
        node[:] = kept


def _v54_repair_mcq_entailment(page, material_language):
    # Remaining MCQs may still receive harmless explicit-cue repair, but unsafe
    # name/biography identity questions are pruned before this function runs.
    if not _v54_is_mcq(page, material_language):
        return
    pk = _v54_prompt_key(page, material_language)
    ek = _v54_explanation_key(page, material_language)
    if not pk or not ek:
        return
    prompt = page[pk]
    explanation = page[ek]
    p = _v54_fold(prompt)
    e = _v54_fold(explanation)
    tr = str(material_language or "").casefold() in {"tr", "turkish", "türkçe", "turkce"}

    female = bool(re.search(r"\b(kadin|disil|female|woman)\b", e))
    male = bool(re.search(r"\b(erkek|eril|male|man)\b", e))
    explicit_gender = bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", p))
    if (female or male) and not explicit_gender and "isim" not in e and "name" not in e:
        cue = ("Bu soruda özne açıkça kadın olarak verilmiştir. " if female else "Bu soruda özne açıkça erkek olarak verilmiştir. ") if tr else ("In this question, the subject is explicitly female. " if female else "In this question, the subject is explicitly male. ")
        page[pk] = cue + prompt


def _v54_walk_mcqs(node, material_language):
    if isinstance(node, dict):
        _v54_repair_mcq_entailment(node, material_language)
        for value in node.values():
            if isinstance(value, (dict, list)):
                _v54_walk_mcqs(value, material_language)
    elif isinstance(node, list):
        for value in node:
            _v54_walk_mcqs(value, material_language)


def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v54_previous_integrity(data, language=language, material_language=material_language)
    if not isinstance(out, dict):
        return out
    # Prefer omission to invented facts. A weak MCQ is less valuable than no MCQ.
    _v54_prune_unsafe_mcqs(out, material_language)
    phonetics = {}
    _v54_collect_authoritative_phonetics(out, phonetics)
    if phonetics:
        _v54_sync_prose_phonetics(out, phonetics)
    _v54_walk_mcqs(out, material_language)
    return out


# AULAAI_RELEASE_HARDENING_V55
_v55_previous_unsafe_mcq = _v54_unsafe_mcq
_v55_previous_meta = sanitize_instructional_metalanguage


def _v55_fold(text):
    # v54's Unicode fold intentionally preserves letters; for deterministic
    # Turkish keyword matching, normalize dotless i as well.
    return _v54_fold(text).replace("ı", "i")


def _v55_option_text(page):
    values = page.get("options") or page.get("choices") or []
    return " ".join(str(v or "") for v in values)


def _v54_unsafe_mcq(page, material_language):
    if _v55_previous_unsafe_mcq(page, material_language):
        return True
    if not _v54_is_mcq(page, material_language):
        return False
    pk = _v54_prompt_key(page, material_language)
    prompt = str(page.get(pk) or "") if pk else ""
    p = _v55_fold(prompt)
    opts = _v55_fold(_v55_option_text(page))

    # High-confidence workplace -> profession inference. Do not fabricate a cue;
    # remove the item and let the rest of the assessment stand.
    workplace_fact = any(x in p for x in (
        "calisiyor", "calisir", "work at", "works at", "works in", "working at", "working in",
        "arbeitet", "travaille", "trabaja", "lavora", "trabalha", "работает", "работа в",
    ))
    profession_question = any(x in p for x in (
        "meslegi", "meslek nedir", "profession", "occupation", "job is", "what does", "beruf",
        "profession est", "profesion", "profissão", "професс", "кем он", "кем она",
    ))
    if workplace_fact and profession_question:
        return True

    # High-confidence trait -> absolute-frequency inference. A trait such as
    # punctuality does not entail NEVER/ALWAYS behavior.
    trait_fact = any(x in p for x in (
        "dakik", "punctual", "punktlich", "ponctuel", "puntual", "pontual", "пунктуал",
    ))
    absolute_frequency_option = any(x in opts for x in (
        "nikogda", "vsegda", "never", "always", "niemals", "immer", "jamais", "toujours",
        "nunca", "siempre", "mai", "sempre", "никогда", "всегда",
    ))
    if trait_fact and absolute_frequency_option:
        return True
    return False


def _v54_repair_mcq_entailment(page, material_language):
    # v54 used to prepend invented gender cues to otherwise valid questions.
    # Never change the semantic premise of an assessment deterministically.
    # Unsafe items are pruned by _v54_unsafe_mcq; safe items remain untouched.
    return None


def sanitize_instructional_metalanguage(value, material_language="tr"):
    text = _v55_previous_meta(value, material_language)
    if str(material_language or "").strip().casefold() not in {"tr", "turkish", "türkçe", "turkce"}:
        return text
    text = re.sub(r"\bzero[- ]copula\b", "sıfır bağlayıcı", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnominatif\b", "Yalın Hâl", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgenitif\b", "İlgi/Tamlayan Hâli", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)\bİlgi\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = re.sub(r"(?i)\bİlgi\s*/\s*Tamlayan\s*(?:H[âa]li)?\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*\(\s*\1\s*\)", r"\1", text)
    text = re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*/\s*\1\b", r"\1", text)
    if re.search(r'(?i)\b(?:ехать|еха[-–—]|ehat|ekhat)\b', text):
        text = re.sub(r'["\'„“]?-д-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", text, flags=re.IGNORECASE)
        text = re.sub(r'["\'„“]?-d-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", text, flags=re.IGNORECASE)
    return text


# AULAAI_RELEASE_CLEANUP_V56
# Final zero-LLM publication cleanup. This layer is deliberately narrow:
# repair only high-confidence orthographic/script defects; prune unsafe MCQs/pages
# rather than inventing semantic content.
_V56_LATIN_TO_CYR = {
    "A":"А", "a":"а", "B":"В", "C":"С", "c":"с", "E":"Е", "e":"е",
    "H":"Н", "K":"К", "k":"к", "M":"М", "m":"м", "O":"О", "o":"о",
    "P":"Р", "p":"р", "T":"Т", "t":"т", "U":"У", "u":"у",
    "X":"Х", "x":"х", "Y":"У", "y":"у",
}
_V56_TR_KEYS = {
    "title_tr", "text_tr", "translation_tr", "explanation_tr", "analysis_tr", "note_tr",
    "context_tr", "meaning_tr", "definition_tr", "prompt_tr", "question_tr", "stem_tr",
    "line_tr", "speaker_tr", "rule_tr", "tip_tr", "pitfall_tr", "breakdown_tr",
}
_V56_TARGET_KEYS = {
    "term", "word", "target", "example", "sentence", "answer", "expression", "phrase", "form", "native", "text",
}


def _v56_strip_marks(text):
    n = unicodedata.normalize("NFD", str(text or ""))
    return "".join(ch for ch in n if unicodedata.category(ch) != "Mn")


def _v56_scripts(token):
    out = set()
    for ch in str(token or ""):
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        if "CYRILLIC" in name:
            out.add("CYRILLIC")
        elif "LATIN" in name:
            out.add("LATIN")
        elif "GREEK" in name:
            out.add("GREEK")
        elif "ARABIC" in name:
            out.add("ARABIC")
        elif "HEBREW" in name:
            out.add("HEBREW")
    return out


def _v56_repair_cyrillic_mixed_token(token):
    token = str(token or "")
    scripts = _v56_scripts(token)
    if not ({"CYRILLIC", "LATIN"} <= scripts):
        return token, False
    out = []
    changed = False
    for ch in token:
        if ch.isalpha() and "LATIN" in unicodedata.name(ch, ""):
            mapped = _V56_LATIN_TO_CYR.get(ch)
            if not mapped:
                return token, False
            out.append(mapped)
            changed = True
        else:
            out.append(ch)
    repaired = "".join(out)
    if changed and _v56_scripts(repaired) <= {"CYRILLIC"}:
        return repaired, True
    return token, False


def _v56_russian_text(text):
    if not isinstance(text, str) or not text:
        return text, False
    # Known high-confidence lexical slips observed in production. These are exact
    # canonical corrections, not generative guesses.
    text = re.sub(r"(?i)\u043f\u0438\u0441(?:[\u0300\u0301])?\u043c\u043e(?:[\u0300\u0301])?", "\u043f\u0438\u0441\u044c\u043c\u043e", text)
    text = re.sub(r"(?i)\u043a\u043e\u0437\u0438(?:[\u0300\u0301])?\u043d\u0435(?:[\u0300\u0301])?", "\u043a\u043e\u0440\u0437\u0438\u043d\u0435", text)

    unsafe = False
    def repl(match):
        nonlocal unsafe
        tok = match.group(0)
        scripts = _v56_scripts(tok)
        if scripts == {"CYRILLIC", "LATIN"}:
            fixed, ok = _v56_repair_cyrillic_mixed_token(tok)
            if ok:
                return fixed
            unsafe = True
        return tok

    text = re.sub(r"[^\W\d_]+", repl, text, flags=re.UNICODE)
    return text, unsafe


def _v56_turkish_text(text):
    if not isinstance(text, str) or not text:
        return text
    # Collapse sanitizer-generated duplicate labels.
    text = re.sub(r"(?i)\bİlgi\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = re.sub(r"(?i)\bİlgi\s*/\s*Tamlayan\s+H[âa]li\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = re.sub(r"(?i)\bYalın\s+H[âa]l\s*/\s*Yalın\s+H[âa]l\b", "Yalın Hâl", text)
    # High-confidence foreign artefact observed in a Turkish learner-facing field.
    # Remove only the isolated token; do not attempt broad language detection.
    text = re.sub(r"(?<!\w)Physik(?!\w)\s*", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _v56_impossible_russian_option(value):
    raw = _v56_strip_marks(str(value or "")).casefold()
    # Orthographically impossible -ы after the 7-letter spelling-rule consonants.
    if re.search(r"[гкхжчшщ]ы", raw):
        return True
    # Production-observed fabricated forms: prune the MCQ rather than fabricate a replacement.
    compact = re.sub(r"[^а-яё]", "", raw)
    return compact in {"городи", "ребеноки", "ребёноки"}


def _v56_is_russian(language):
    return "russian" in str(language or "").casefold() or "rusça" in str(language or "").casefold() or "рус" in str(language or "").casefold()


def _v56_clean_node(node, language="", parent_key=""):
    """Recursively apply safe, in-place textual repairs.

    Returns (cleaned, unsafe). 'unsafe' is only ever allowed to reach the
    caller (and therefore cause deletion) when the dict being processed IS
    itself an assessment/mcq item - in this codebase one page == one MCQ, so
    dropping such a dict drops exactly that one question and nothing else.
    An unrepairable orthographic defect found anywhere inside a
    vocabulary/grammar/dialogue/examples/overview page must never delete
    that page: this function still repairs what it safely can, but a defect
    it cannot repair is left as-is rather than used to justify deleting the
    surrounding substantive content. This is what actually prevents a single
    bad token from emptying a lesson/topic.
    """
    is_russian = _v56_is_russian(language)
    if isinstance(node, str):
        if parent_key in _V56_TR_KEYS or str(parent_key).endswith("_tr"):
            return _v56_turkish_text(node), False
        if is_russian and parent_key in _V56_TARGET_KEYS:
            cleaned, unsafe = _v56_russian_text(node)
            return cleaned, unsafe
        return node, False
    if isinstance(node, list):
        out = []
        unsafe = False
        for item in node:
            cleaned, bad = _v56_clean_node(item, language, parent_key)
            out.append(cleaned)
            unsafe = unsafe or bad
        return out, unsafe
    if not isinstance(node, dict):
        return node, False

    # A dict is only ever treated as a droppable assessment unit when its own
    # declared type is "mcq". This intentionally does NOT include dicts that
    # merely contain an mcq-like child somewhere below them.
    node_is_mcq_item = is_russian and str(node.get("type") or "").strip().casefold() == "mcq"

    # High-confidence fabricated distractor => drop this (single) MCQ item later.
    if node_is_mcq_item:
        opts = node.get("options") or node.get("choices") or []
        if isinstance(opts, list) and any(_v56_impossible_russian_option(x) for x in opts if isinstance(x, str)):
            return None, True

    out = {}
    unsafe = False
    for key, value in node.items():
        cleaned, bad = _v56_clean_node(value, language, str(key))
        out[key] = cleaned
        # Do NOT let a child's unsafe flag escape this dict unless this dict
        # is itself the mcq item being evaluated. This is the boundary that
        # stops "one bad token in one field" from turning into "delete this
        # whole vocabulary/grammar/dialogue page".
        if node_is_mcq_item:
            unsafe = unsafe or bad
    return out, unsafe


def _v56_release_cleanup(data, language=""):
    if not isinstance(data, dict):
        return data
    out = deepcopy(data)
    pages = out.get("pages")
    if not isinstance(pages, list):
        cleaned, _ = _v56_clean_node(out, language)
        return cleaned

    kept = []
    removed = []
    for idx, page in enumerate(pages):
        page_type = str(page.get("type") or "").strip().casefold() if isinstance(page, dict) else ""
        cleaned, unsafe = _v56_clean_node(page, language)
        # Defense in depth, independent of the mcq-only gate inside
        # _v56_clean_node: this cleanup layer is only ever allowed to remove
        # a page whose OWN declared type is "mcq". Substantive content pages
        # (vocabulary/grammar/dialogue/examples/overview/...) are never
        # dropped here, no matter what unsafe signal was computed for them.
        if page_type != "mcq":
            kept.append(cleaned if cleaned is not None else page)
            continue
        if cleaned is None or unsafe:
            removed.append({"index": idx, "reason": "v56-publication-safety"})
            continue
        kept.append(cleaned)
    out["pages"] = kept
    if removed:
        prior = out.get("_integrity_removed_mcq")
        if not isinstance(prior, list):
            prior = []
        out["_integrity_removed_mcq"] = prior + removed
    return out


_v56_previous_integrity = enforce_material_integrity

def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v56_previous_integrity(data, language=language, material_language=material_language)
    return _v56_release_cleanup(out, language or "")


# AULAAI_RELEASE_CLEANUP_V56_QUALITY
# Zero-LLM quality cleanup with a hard structural invariant:
# this overlay may remove only a page whose OWN type is exactly "mcq".
# It never returns unsafe flags and never removes substantive content pages.
import re as _v56q_re
import unicodedata as _v56q_ud

_V56Q_BAD_RU_OPTIONS = {
    "готовю", "италие", "городи", "ребеноки", "ребёноки", "другы", "книгы",
}
_V56Q_IPA_SINGLE = {
    "б":"b", "в":"v", "г":"ɡ", "д":"d", "ж":"ʐ", "з":"z", "к":"k",
    "л":"ɫ", "м":"m", "н":"n", "п":"p", "р":"r", "с":"s", "т":"t",
    "ф":"f", "х":"x", "ц":"t͡s", "ч":"t͡ɕ", "ш":"ʂ", "щ":"ɕː", "й":"j",
}


def _v56q_fold(value):
    text = _v56q_ud.normalize("NFD", str(value or "")).casefold()
    return "".join(ch for ch in text if _v56q_ud.category(ch) != "Mn").replace("ı", "i")


def _v56q_page_is_mcq(page):
    return isinstance(page, dict) and str(page.get("type") or "").strip().casefold() == "mcq"


def _v56q_prompt(page):
    for key in ("prompt_tr", "question_tr", "stem_tr", "prompt", "question", "stem", "text_tr", "text"):
        value = page.get(key) if isinstance(page, dict) else None
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _v56q_explanation(page):
    if not isinstance(page, dict):
        return ""
    return " ".join(str(page.get(k) or "") for k in (
        "explanation_tr", "analysis_tr", "explanation", "analysis", "explanation_en"
    ))


def _v56q_stressless(value):
    # Remove only pedagogical stress marks. Do not strip all combining marks:
    # doing so turns Cyrillic й into и and breaks exact lexical checks.
    text = _v56q_ud.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if ch not in {"\u0300", "\u0301"})
    return _v56q_ud.normalize("NFC", text).casefold()


def _v56q_bad_option(value):
    raw = _v56q_stressless(value).strip()
    if _v56_impossible_russian_option(value):
        return True
    compact = _v56q_re.sub(r"[^а-яё]", "", raw)
    if compact in _V56Q_BAD_RU_OPTIONS:
        return True
    normalized_space = _v56q_re.sub(r"\s+", " ", raw)
    if normalized_space in {"по русский", "на русскому"}:
        return True
    return False


def _v56q_explanation_admits_malformed_distractor(page):
    e = _v56q_fold(_v56q_explanation(page))
    if any(x in e for x in (
        "hatali bir form", "hatali form", "hatali durum eki", "gecersiz bir form",
        "uydurma form", "invalid form", "non-word", "misspelling",
    )):
        return True
    if "dogru ek icermez" in e:
        return True
    if "zorunlu" in e and "icermedigi icin" in e and "yanlistir" in e:
        return True
    return False


def _v56q_hidden_name_gender(page):
    prompt = _v56q_prompt(page)
    explanation = _v56q_explanation(page)
    p = _v56q_fold(prompt)
    e = _v56q_fold(explanation)

    if not any(x in e for x in ("ozne", "subject")):
        return False
    if not any(x in e for x in ("disil", "eril", "female", "male", "feminine", "masculine")):
        return False

    if any(x in p for x in (
        "disil", "eril", "kadin", "erkek", "female", "male", "woman", "man",
        "женщина", "мужчина", "девушка", "мальчик", "девочка", "мать", "отец",
        "мама", "папа", "сестра", "брат", "бабушка", "дедушка",
        "wife", "husband", "mother", "father", "sister", "brother",
    )):
        return False

    quoted = _v56q_re.findall(
        r"['«“\"]([A-ZА-ЯЁÇĞİÖŞÜ][A-Za-zА-Яа-яЁёÇĞİÖŞÜçğıöşü-]{1,30})['»”\"]",
        explanation,
    )
    return any(token in prompt for token in quoted)


def _v56q_unsafe_mcq(page, material_language="tr"):
    if not _v56q_page_is_mcq(page):
        return False
    try:
        if _v54_unsafe_mcq(page, material_language):
            return True
    except Exception:
        pass
    options = page.get("options") or page.get("choices") or []
    if isinstance(options, list) and any(_v56q_bad_option(v) for v in options if isinstance(v, str)):
        return True
    if _v56q_explanation_admits_malformed_distractor(page):
        return True
    if _v56q_hidden_name_gender(page):
        return True
    return False


def _v56q_strip_cyrillic_respelling(text):
    if not isinstance(text, str) or not text:
        return text
    return _v56q_re.sub(
        r"([А-Яа-яЁё\u0300\u0301]{3,})\s*\[([А-Яа-яЁё\u0300\u0301]{3,})\]",
        r"\1",
        text,
    )


def _v56q_normalize_alphabet_item(item):
    if not isinstance(item, dict):
        return item
    term = str(item.get("term") or item.get("word") or "")
    compact = "".join(
        ch for ch in _v56q_ud.normalize("NFD", term).casefold()
        if _v56q_ud.category(ch) != "Mn" and ch.isalpha()
    )
    if compact in {"ч", "чч"}:
        item["phonetic"] = "[t͡ɕ]"
    elif compact in {"щ", "щщ"}:
        item["phonetic"] = "[ɕː]"
    elif compact in {"ъ", "ъъ", "ь", "ьь"}:
        item["phonetic"] = ""
    return item


def _v56q_clean_tree(node, language="", parent_key=""):
    """Leaf-only cleanup. Never deletes a dict/list/item and never emits unsafe."""
    is_russian = _v56_is_russian(language)
    if isinstance(node, str):
        text = node
        if parent_key in _V56_TR_KEYS or str(parent_key).endswith("_tr"):
            text = _v56_turkish_text(text)
        if is_russian and parent_key in _V56_TARGET_KEYS:
            text, _ignored_unsafe = _v56_russian_text(text)
            text = _v56q_strip_cyrillic_respelling(text)
        return text
    if isinstance(node, list):
        return [_v56q_clean_tree(v, language, parent_key) for v in node]
    if not isinstance(node, dict):
        return node
    out = {k: _v56q_clean_tree(v, language, str(k)) for k, v in node.items()}
    if is_russian:
        _v56q_normalize_alphabet_item(out)
    return out


_v56q_previous_release_cleanup = _v56_release_cleanup

def _v56_release_cleanup(data, language=""):
    out = _v56q_previous_release_cleanup(data, language)
    if not isinstance(out, dict):
        return out

    if not _v56_is_russian(language):
        return _v56q_clean_tree(out, language)

    pages = out.get("pages")
    if not isinstance(pages, list):
        return _v56q_clean_tree(out, language)

    kept = []
    removed = []
    for idx, page in enumerate(pages):
        if _v56q_page_is_mcq(page) and _v56q_unsafe_mcq(page, "tr"):
            removed.append({"index": idx, "reason": "v56-quality-mcq-only"})
            continue
        kept.append(_v56q_clean_tree(page, language))

    out["pages"] = kept
    if removed:
        prior = out.get("_integrity_removed_mcq")
        if not isinstance(prior, list):
            prior = []
        out["_integrity_removed_mcq"] = prior + removed
    return out


# AULAAI_RELEASE_FINAL_V57
# Final zero-LLM publication invariants. This layer is intentionally narrow:
# it never invents semantic content, never retries generation, and never drops
# substantive lesson pages. It may omit only an MCQ whose keyed answer depends
# on an unstated identity/biographical fact.
import re as _v57_re
import unicodedata as _v57_ud


def _v57_fold(value):
    text = _v57_ud.normalize("NFD", str(value or "")).casefold()
    text = "".join(ch for ch in text if _v57_ud.category(ch) != "Mn")
    return text.replace("ı", "i")


def _v57_mcq_prompt(page):
    if not isinstance(page, dict):
        return ""
    for key in ("prompt_tr", "question_tr", "stem_tr", "prompt_en", "question_en", "stem_en", "prompt", "question", "stem", "text_tr", "text_en", "text"):
        value = page.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _v57_mcq_explanation(page):
    if not isinstance(page, dict):
        return ""
    return " ".join(str(page.get(key) or "") for key in (
        "explanation_tr", "analysis_tr", "explanation_en", "analysis_en", "explanation", "analysis"
    ))


def _v57_mcq_like(page):
    if not isinstance(page, dict):
        return False
    if str(page.get("type") or "").strip().casefold() == "mcq":
        return True
    return bool((page.get("options") or page.get("choices")) and _v57_mcq_prompt(page))


def _v57_unsafe_mcq(page):
    if not _v57_mcq_like(page):
        return False
    prompt = _v57_mcq_prompt(page)
    explanation = _v57_mcq_explanation(page)
    p = _v57_fold(prompt)
    e = _v57_fold(explanation)

    gender_words = r"\b(kadin|erkek|disil|eril|female|male|woman|man|feminine|masculine)\b"
    explicit_gender = bool(_v57_re.search(gender_words, p)) or any(x in p for x in (
        "женщина", "мужчина", "девушка", "мальчик", "девочка", "мать", "отец", "мама", "папа",
        "сестра", "брат", "бабушка", "дедушка", "wife", "husband", "mother", "father", "sister", "brother",
    ))
    explanation_uses_gender = bool(_v57_re.search(gender_words, e))
    explanation_uses_name = bool(_v57_re.search(r"\b(isim|ismi|adi|adinin|name)\b", e))
    if explanation_uses_name and explanation_uses_gender and not explicit_gender:
        return True

    # Hidden-world entailment: birthplace/residence/workplace does not establish
    # nationality, language ability, profession, ethnicity or gender. Require the
    # explanation itself to reveal that the answer depends on such an identity fact.
    biography = any(marker in p for marker in (
        "dogdu", "dogmus", "dogum", "yasiyor", "yasadi", "ikamet", "calisiyor", "calisti",
        "born", "birthplace", "lives", "lived", "resides", "resided", "works", "worked",
        "родил", "рожден", "жив", "работ", "nacio", "nacido", "vive", "trabaja",
        "geboren", "lebt", "arbeitet", "nee", "habite", "travaille",
    ))
    identity = bool(_v57_re.search(
        r"\b(milliyet|uyruk|nationality|national|ethnicity|etnisite|dil|konus|language|speak|speaks|spoken|meslek|profession|occupation|job|disil|eril|female|male|feminine|masculine)\b",
        e,
    ))
    if biography and identity:
        return True
    return False


def _v57_prune_only_unsafe_mcq_children(node):
    if isinstance(node, list):
        kept = []
        for item in node:
            if isinstance(item, dict) and _v57_mcq_like(item) and _v57_unsafe_mcq(item):
                continue
            kept.append(_v57_prune_only_unsafe_mcq_children(item))
        return kept
    if isinstance(node, dict):
        return {key: _v57_prune_only_unsafe_mcq_children(value) for key, value in node.items()}
    return node


_v57_previous_integrity = enforce_material_integrity

def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v57_previous_integrity(data, language=language, material_language=material_language)
    if not isinstance(out, dict):
        return out
    pages = out.get("pages")
    if isinstance(pages, list):
        kept = []
        removed = []
        for idx, page in enumerate(pages):
            if isinstance(page, dict) and _v57_mcq_like(page) and _v57_unsafe_mcq(page):
                removed.append({"index": idx, "reason": "v57-hidden-world-mcq"})
                continue
            kept.append(_v57_prune_only_unsafe_mcq_children(page))
        out["pages"] = kept
        if removed:
            prior = out.get("_integrity_removed_mcq")
            if not isinstance(prior, list):
                prior = []
            out["_integrity_removed_mcq"] = prior + removed
    else:
        out = _v57_prune_only_unsafe_mcq_children(out)
    return out

# AULAAI_MICRO_QUALITY_POLISH
try:
    _v58_previous_safe_unicode = safe_unicode_normalize
except NameError:
    _v58_previous_safe_unicode = lambda t, l=None: str(t or "")


def safe_unicode_normalize(text: str, language=None) -> str:
    res = _v58_previous_safe_unicode(text, language=language)
    res = harmonize_mixed_scripts(res, language=language)
    return _strip_unpublishable_codepoints(res)


# Characters that must never reach a published text layer. Private-use and
# unassigned codepoints rendered as harmless-looking glyphs in the PDF but
# extracted as garbage, which is how corrupted characters kept appearing in
# hyphenated forms. Deliberately narrow: this removes only what no script can
# legitimately need, so IPA, combining marks, joiners, bidi controls and every
# supported writing system pass through untouched.
_UNPUBLISHABLE_CATEGORIES = frozenset({"Co", "Cn", "Cs"})
# Format/control characters that carry real typographic meaning are exempt.
_FORMAT_KEEP = frozenset({
    "‌",  # ZWNJ - required by Persian, Indic scripts
    "‍",  # ZWJ  - required by Indic conjuncts, emoji sequences
    "‎", "‏",  # LTR/RTL marks - required by Arabic/Hebrew
    "⁠",  # word joiner
    "\n", "\t",
})


def _strip_unpublishable_codepoints(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    out = []
    for ch in text:
        if ch in _FORMAT_KEEP:
            out.append(ch)
            continue
        cat = unicodedata.category(ch)
        if cat in _UNPUBLISHABLE_CATEGORIES:
            continue
        if cat == "Cc":
            continue
        out.append(ch)
    return "".join(out)


try:
    _v58_previous_meta = sanitize_instructional_metalanguage
except NameError:
    _v58_previous_meta = lambda v, m="tr": str(v or "")


def sanitize_instructional_metalanguage(value, material_language="tr"):
    text = _v58_previous_meta(value, material_language)
    text = sanitize_instructional_shorthand(text, instructional_language=material_language)
    try:
        return deduplicate_morphological_parentheticals(text)
    except NameError:
        return text


try:
    _v58_previous_validate_mcq = validate_mcq
except NameError:
    _v58_previous_validate_mcq = None


def validate_mcq(page):
    if _v58_previous_validate_mcq:
        ok, why = _v58_previous_validate_mcq(page)
        if not ok:
            return ok, why
    if not isinstance(page, dict):
        return False, "mcq-not-dict"
    opts = _as_list(page.get("options") or page.get("choices"))
    prompt = _norm(page.get("prompt") or page.get("question") or page.get("text"))
    expl = _norm(page.get("explanation") or page.get("explanation_tr") or page.get("explanation_en") or "")
    return validate_distractor_quality(opts, prompt=prompt, explanation=expl)


try:
    _v58_previous_integrity = enforce_material_integrity
except NameError:
    _v58_previous_integrity = lambda d, l=None, m="tr": d


def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v58_previous_integrity(data, language=language, material_language=material_language)
    if not isinstance(out, dict):
        return out
    pages = out.get("pages")
    if isinstance(pages, list):
        is_tr = bool(str(material_language or "").strip().casefold() in ("tr", "turkish", "türkçe"))
        for page in pages:
            if isinstance(page, dict):
                for container in ("items", "vocabulary", "words", "examples", "rules", "comparisons"):
                    sub = page.get(container)
                    if isinstance(sub, list):
                        for idx, item in enumerate(sub):
                            if isinstance(item, dict):
                                sub[idx] = align_lexical_fields(item, language=language, is_tr=is_tr)
    # This function is deliberately non-destructive: it repairs fields and never
    # removes a page. Removal of structurally invalid assessment items belongs to
    # prune_invalid_mcq_pages at the publication boundary, which owns that
    # decision and records what it dropped. Splitting removal across both layers
    # is how two guards end up disagreeing about what shipped.
    return out
