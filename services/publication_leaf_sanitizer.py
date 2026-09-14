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
    """Repair only production-observed exact Russian Unicode stress defects."""
    if not isinstance(text, str) or not text:
        return text
    # Production-observed misplaced acute in пес́ня. Exact lexical repair only;
    # do not attempt a general stress-placement algorithm.
    return text.replace("пес́ня", "пе́сня").replace("Пес́ня", "Пе́сня")


def _localize_known_structural_label(text: str, material_language: str) -> str:
    """Localize only exact observed structural labels; never translate free text."""
    if not _is_turkish_instruction(material_language) or not isinstance(text, str):
        return text
    replacements = {
        "Hard vowel indicators:": "Sert ünlü göstergeleri:",
        "Soft vowel indicators:": "Yumuşak ünlü göstergeleri:",
    }
    stripped = text.strip()
    for source, target in replacements.items():
        if stripped.startswith(source):
            return text.replace(source, target, 1)
    return text


def _looks_like_non_sounding_sign(term: str) -> bool:
    compact = _strip_stress(term)
    # Keep scope deliberately narrow: Russian hard/soft signs as standalone
    # grapheme entries, optionally accompanied by their Russian label.
    return compact in {"ъ", "ь", "ъ ъ", "ь ь"} or compact.startswith("ъ (") or compact.startswith("ь (")


def _sanitize_phonetic(value: str, term: str, language: str) -> str:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not _is_russian(language):
        return value

    if _looks_like_non_sounding_sign(term) and text in {"[-]", "-", "[—]", "—"}:
        return ""

    # Nested/multiply-opened bracket payloads are structurally malformed IPA
    # fields. Do not guess a replacement; blank the leaf instead.
    if text.startswith("[[") or text.endswith("]]" ) or text.count("[") != text.count("]"):
        return ""

    return value


def sanitize_publication_leaves(node, language: str = "", material_language: str = ""):
    """Return a structure-preserving copy with leaf-only high-confidence fixes."""
    if isinstance(node, list):
        return [sanitize_publication_leaves(v, language, material_language) for v in node]
    if isinstance(node, str):
        return _normalize_ru_exact_text(node) if _is_russian(language) else node
    if not isinstance(node, dict):
        return node

    out = {k: sanitize_publication_leaves(v, language, material_language) for k, v in node.items()}

    if _is_russian(language):
        for key in ("term", "word", "target", "example", "text", "sentence"):
            if isinstance(out.get(key), str):
                out[key] = _normalize_ru_exact_text(out[key])

    if isinstance(out.get("term"), str):
        out["term"] = _localize_known_structural_label(out["term"], material_language)
    if isinstance(out.get("word"), str):
        out["word"] = _localize_known_structural_label(out["word"], material_language)

    phonetic = out.get("phonetic")
    if isinstance(phonetic, str):
        lexical_term = ""
        for key in ("term", "word"):
            if isinstance(out.get(key), str) and out[key].strip():
                lexical_term = out[key]
                break
        out["phonetic"] = _sanitize_phonetic(phonetic, lexical_term, language)

    return out
