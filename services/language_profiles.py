"""Taught language, instructional track, and interface language — kept apart.

Three things in this product are easy to confuse and must never be merged:

  * the **interface language** (`ui_lang`) — the chrome the person clicked,
    stored in the browser, changeable at any moment;
  * the **taught / target language** (`courses.language`) — what the class
    teaches, fixed when the class is created;
  * the **instructional track** (`courses.material_language`) — the language the
    explanations, rubrics and rationales of the published material are written
    in. Material is generated with BOTH the `en` and `tr` field families
    populated; the track decides which family is published and read.

For most taught languages the reader may follow the interface language: a
Spanish course explained in Turkish and the same course explained in English are
both coherent products, and the learner picks.

Two taught languages are different, because for them one of the two tracks *is*
the target language, and explaining English in English (or Turkish in Turkish)
to a beginner is a different product, not a translation of this one:

  * English taught  -> instructional track locked to Turkish.
  * Turkish taught  -> instructional track locked to English.

That lock is a property of the course, not of the session. Switching the site
language must not move it, so every place that used to read `ui_lang` straight
into `material_language` now asks this module instead. `resolve_track()` is the
only supported way to answer "which track does this course publish?".
"""

import unicodedata
from typing import Dict, List, Optional

# ── Taught languages ───────────────────────────────────────────────────────────
# Canonical English name -> ISO-ish chip shown in the picker. This list is the
# product's allowlist: a language absent here is not offered and not accepted.
TAUGHT_LANGUAGES: Dict[str, str] = {
    "English": "EN",
    "Spanish": "ES",
    "German": "DE",
    "French": "FR",
    "Italian": "IT",
    "Portuguese": "PT",
    "Russian": "RU",
    "Chinese": "ZH",
    "Japanese": "JA",
    "Arabic": "AR",
    "Turkish": "TR",
    "Dutch": "NL",
    "Swedish": "SV",
    "Korean": "KO",
    "Greek": "EL",
}

# Names the rest of the system (and lecturers) actually type.
_ALIASES: Dict[str, str] = {
    "ingilizce": "English", "inglés": "English", "ingles": "English",
    "en": "English", "eng": "English",
    "türkçe": "Turkish", "turkce": "Turkish", "turkish": "Turkish", "tr": "Turkish",
    "español": "Spanish", "espanol": "Spanish", "ispanyolca": "Spanish", "es": "Spanish",
    "deutsch": "German", "almanca": "German", "de": "German",
    "français": "French", "francais": "French", "fransızca": "French", "fransizca": "French", "fr": "French",
    "italiano": "Italian", "italyanca": "Italian", "it": "Italian",
    "português": "Portuguese", "portugues": "Portuguese", "portekizce": "Portuguese", "pt": "Portuguese",
    "русский": "Russian", "rusça": "Russian", "rusca": "Russian", "ru": "Russian",
    "中文": "Chinese", "çince": "Chinese", "cince": "Chinese", "zh": "Chinese",
    "日本語": "Japanese", "japonca": "Japanese", "ja": "Japanese",
    "العربية": "Arabic", "arapça": "Arabic", "arapca": "Arabic", "ar": "Arabic",
    "nederlands": "Dutch", "felemenkçe": "Dutch", "felemenkce": "Dutch", "hollandaca": "Dutch", "nl": "Dutch",
    "svenska": "Swedish", "isveççe": "Swedish", "isvecce": "Swedish", "sv": "Swedish",
    "한국어": "Korean", "korece": "Korean", "ko": "Korean",
    "ελληνικά": "Greek", "yunanca": "Greek", "el": "Greek",
}

# ── The special pair ───────────────────────────────────────────────────────────
# Taught language (canonical) -> the ONLY instructional track it may publish.
SPECIAL_PAIR_TRACK: Dict[str, str] = {
    "English": "tr",
    "Turkish": "en",
}

VALID_TRACKS = ("tr", "en")
DEFAULT_TRACK = "tr"

_TRACK_NAME = {"tr": "Turkish", "en": "English"}
_TRACK_NAME_TR = {"tr": "Türkçe", "en": "İngilizce"}


def _fold(text: str) -> str:
    """Case- and diacritic-insensitive key.

    Plain `.casefold()` is not enough for the two languages this module cares
    most about: 'İngilizce'.casefold() keeps a combining dot above, so it never
    matches 'ingilizce', and 'Türkçe' never matches 'turkce'. Decomposing and
    dropping combining marks makes both resolve, which matters because these
    spellings are exactly what a Turkish-speaking lecturer types.
    """
    decomposed = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


_ALIASES = {_fold(k): v for k, v in _ALIASES.items()}


def normalize_language(language: Optional[str]) -> str:
    """Canonical taught-language name, or '' when it is not one we teach.

    Accepts the canonical name, the lecturer's own spelling, and the handful of
    endonyms/codes that reach us from PDF language detection.
    """
    if not language:
        return ""
    raw = str(language).strip()
    if not raw or raw.lower() in ("detecting...", "unknown", "auto", "none"):
        return ""
    key = _fold(raw)
    for canonical in TAUGHT_LANGUAGES:
        if key == _fold(canonical):
            return canonical
    return _ALIASES.get(key, "")


def is_taught_language(language: Optional[str]) -> bool:
    return bool(normalize_language(language))


def language_chip(language: Optional[str]) -> str:
    return TAUGHT_LANGUAGES.get(normalize_language(language), "")


def locked_track(language: Optional[str]) -> Optional[str]:
    """The instructional track this taught language forces, or None if free."""
    return SPECIAL_PAIR_TRACK.get(normalize_language(language))


def is_special_pair(language: Optional[str]) -> bool:
    return normalize_language(language) in SPECIAL_PAIR_TRACK


def _clean_track(track: Optional[str]) -> Optional[str]:
    if not track:
        return None
    value = str(track).strip().casefold()
    return value if value in VALID_TRACKS else None


def resolve_track(
    language: Optional[str],
    requested: Optional[str] = None,
    declared: Optional[str] = None,
) -> str:
    """Which instructional track this course publishes. The single entry point.

    `requested` is what the session asked for (usually `ui_lang`); `declared` is
    what the course row already stores. For a special-pair language the answer
    ignores both, which is the entire point: the interface may be in any
    language without moving the material onto a track the course does not have.
    """
    forced = locked_track(language)
    if forced:
        return forced
    return _clean_track(requested) or _clean_track(declared) or DEFAULT_TRACK


def instruction_language_name(track: Optional[str], in_turkish: bool = False) -> str:
    """Human name of a track: 'Turkish'/'English' (or 'Türkçe'/'İngilizce')."""
    key = _clean_track(track) or DEFAULT_TRACK
    return (_TRACK_NAME_TR if in_turkish else _TRACK_NAME)[key]


def track_notice(language: Optional[str], ui_lang: str = "en") -> str:
    """One professional sentence explaining the lock, or '' when none applies.

    Shown before generation begins, so the constraint reads as a product
    decision rather than as a defect discovered in the reader.
    """
    canonical = normalize_language(language)
    forced = SPECIAL_PAIR_TRACK.get(canonical)
    if not forced:
        return ""
    turkish_ui = str(ui_lang or "en").strip().casefold().startswith("tr")
    if turkish_ui:
        return (
            f"{_TRACK_NAME_TR[_lang_track(canonical)]} dersinde açıklamalar ve ders materyali "
            f"{_TRACK_NAME_TR[forced]} hazırlanır. Arayüz dilini değiştirmek bunu değiştirmez."
        )
    return (
        f"{canonical} classes are explained in {_TRACK_NAME[forced]}. "
        "Changing the interface language does not change the instructional language."
    )


def _lang_track(canonical: str) -> str:
    """The track that *is* the taught language itself, for the notice copy."""
    return "en" if canonical == "English" else "tr"


def supported_language_rows() -> List[Dict[str, str]]:
    """Picker rows: canonical id, chip, and the locked track when there is one."""
    return [
        {"id": name, "code": code, "locked_track": SPECIAL_PAIR_TRACK.get(name, "")}
        for name, code in TAUGHT_LANGUAGES.items()
    ]
