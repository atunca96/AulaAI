"""Non-destructive publication leaf hygiene.

This module performs only high-confidence, leaf-level publication cleanup. It
never deletes list/dict content and never guesses semantic pronunciation.
"""
from __future__ import annotations

import re
import unicodedata

_RU_VOWELS = set("аеёиоуыэюяАЕЁИОУЫЭЮЯ")


def _is_russian(language: str) -> bool:
    value = str(language or "").casefold()
    return "russian" in value or "rusça" in value or "рус" in value


def _is_turkish_instruction(material_language: str) -> bool:
    value = str(material_language or "").casefold()
    return value in {"tr", "turkish", "türkçe", "turkce"} or "türk" in value or "turk" in value


def _strip_stress(text: str) -> str:
    nfd = unicodedata.normalize("NFD", str(text or ""))
    nfd = "".join(ch for ch in nfd if ch not in {"\u0300", "\u0301"})
    return unicodedata.normalize("NFC", nfd).casefold().strip()


def _normalize_ru_exact_text(text: str) -> str:
    """Repair only production-observed exact Russian Unicode/text defects."""
    if not isinstance(text, str) or not text:
        return text
    text = text.replace("пес́ня", "пе́сня").replace("Пес́ня", "Пе́сня")
    # Production-observed instructional gloss leaked inside a Russian dialogue.
    # Replace only the exact known mixed-language clause; do not translate free text.
    text = text.replace(
        "«Задание» — это task или exercise.",
        "«Задание» — это упражнение или учебная задача.",
    )
    return text


def _localize_known_structural_label(text: str, material_language: str) -> str:
    """Localize only exact observed structural labels; never translate free text."""
    if not _is_turkish_instruction(material_language) or not isinstance(text, str):
        return text
    replacements = {
        "Hard vowel indicators:": "Sert ünlü göstergeleri:",
        "Soft vowel indicators:": "Yumuşak ünlü göstergeleri:",
        "Present Tense: First Conjugation Verbs (-at/-yat)": "Şimdiki/Geniş Zaman: Birinci Grup Fiiller (-ать/-ять)",
    }
    stripped = text.strip()
    for source, target in replacements.items():
        if stripped.startswith(source):
            return text.replace(source, target, 1)
    return text


def _normalize_turkish_artificial_phrasing(text: str, material_language: str, language: str) -> str:
    """Remove only production-observed unnatural Turkish authority framing.

    This is deliberately narrow. General stylistic quality belongs in the generation
    contract; publication cleanup only rewrites phrases whose intended meaning is
    unchanged and unambiguous.
    """
    if not _is_turkish_instruction(material_language) or not isinstance(text, str):
        return text
    if _is_russian(language):
        replacements = {
            "Ana dili Rusça olan konuşucuların temel diyaloglarda ": "Temel diyaloglarda ",
            "Ana dili Rusça olan konuşucuların günlük ": "Günlük Rusçada ",
            "Anadili Rusça olanların günlük ": "Günlük Rusçada ",
            "Anadili Rusça olan konuşucuların günlük ": "Günlük Rusçada ",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
    return text


def _looks_like_non_sounding_sign(term: str) -> bool:
    compact = _strip_stress(term)
    return compact in {"ъ", "ь", "ъ ъ", "ь ь"} or compact.startswith("ъ (") or compact.startswith("ь (")


def _sanitize_phonetic(value: str, term: str, language: str) -> str:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not _is_russian(language):
        return value

    if _looks_like_non_sounding_sign(term) and text in {"[-]", "-", "[—]", "—"}:
        return ""

    if text.startswith("[[") or text.endswith("]]" ) or text.count("[") != text.count("]"):
        return ""

    return value


def sanitize_publication_leaves(node, language: str = "", material_language: str = ""):
    """Return a structure-preserving copy with leaf-only high-confidence fixes."""
    if isinstance(node, list):
        return [sanitize_publication_leaves(v, language, material_language) for v in node]
    if isinstance(node, str):
        text = _normalize_ru_exact_text(node) if _is_russian(language) else node
        return _normalize_turkish_artificial_phrasing(text, material_language, language)
    if not isinstance(node, dict):
        return node

    out = {k: sanitize_publication_leaves(v, language, material_language) for k, v in node.items()}

    if _is_russian(language):
        for key in ("term", "word", "target", "example", "text", "sentence"):
            if isinstance(out.get(key), str):
                out[key] = _normalize_ru_exact_text(out[key])

    # Known headings/labels can occur in title/text-like fields, not just term/word.
    for key in ("term", "word", "title", "title_tr", "text_tr", "heading", "label"):
        if isinstance(out.get(key), str):
            out[key] = _localize_known_structural_label(out[key], material_language)
            out[key] = _normalize_turkish_artificial_phrasing(out[key], material_language, language)

    phonetic = out.get("phonetic")
    if isinstance(phonetic, str):
        lexical_term = ""
        for key in ("term", "word"):
            if isinstance(out.get(key), str) and out[key].strip():
                lexical_term = out[key]
                break
        out["phonetic"] = _sanitize_phonetic(phonetic, lexical_term, language)

    return out
