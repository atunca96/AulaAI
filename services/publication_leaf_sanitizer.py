"""Non-destructive publication leaf hygiene.

Only high-confidence leaf-level cleanup. Never deletes page/item/topic content and
never guesses semantic pronunciation.
"""
from __future__ import annotations

import re
import unicodedata


def _is_russian(language: str) -> bool:
    v = str(language or "").casefold()
    return "russian" in v or "rusça" in v or "рус" in v


def _is_japanese(language: str) -> bool:
    v = str(language or "").casefold()
    return "japanese" in v or "japon" in v or "日本" in v


def _is_turkish_instruction(material_language: str) -> bool:
    v = str(material_language or "").casefold()
    return v in {"tr", "turkish", "türkçe", "turkce"} or "türk" in v or "turk" in v


def _strip_stress(text: str) -> str:
    nfd = unicodedata.normalize("NFD", str(text or ""))
    nfd = "".join(ch for ch in nfd if ch not in {"\u0300", "\u0301"})
    return unicodedata.normalize("NFC", nfd).casefold().strip()


def _normalize_ru_exact_text(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    text = text.replace("пес́ня", "пе́сня").replace("Пес́ня", "Пе́сня")
    text = text.replace("«Задание» — это task или exercise.", "«Задание» — это упражнение или учебная задача.")
    return text


def _normalize_japanese_exact_text(text: str, language: str) -> str:
    """Repair only observed unambiguous loss of the katakana long-vowel mark."""
    if not _is_japanese(language) or not isinstance(text, str):
        return text
    # The prose explicitly names choonpu/uzatma çizgisi; empty quotes cannot mean
    # anything else here. Restore the actual grapheme without touching free text.
    text = re.sub(r"(?:''|\"\"|‘’|“”)\s+(uzatma çizgisi|uzatma işareti)\s*\(çōonpu\)", r"「ー」 \1 (çōonpu)", text, flags=re.I)
    text = re.sub(r"Yatay çizgi olan\s+(?:''|\"\"|‘’|“”)", "Yatay çizgi olan 「ー」", text, flags=re.I)
    text = re.sub(r"Katakana'da özel\s+(?:''|\"\"|‘’|“”)\s+uzatma", "Katakana'da özel 「ー」 uzatma", text, flags=re.I)
    return text


def _localize_known_structural_label(text: str, material_language: str) -> str:
    if not _is_turkish_instruction(material_language) or not isinstance(text, str):
        return text
    replacements = {
        "Hard vowel indicators:": "Sert ünlü göstergeleri:",
        "Soft vowel indicators:": "Yumuşak ünlü göstergeleri:",
        "Present Tense: First Conjugation Verbs (-at/-yat)": "Şimdiki/Geniş Zaman: Birinci Grup Fiiller (-ать/-ять)",
        "Theory": "Kuram",
    }
    stripped = text.strip()
    for source, target in replacements.items():
        if stripped == source or stripped.startswith(source):
            return text.replace(source, target, 1)
    return text


def _normalize_turkish_artificial_phrasing(text: str, material_language: str, language: str) -> str:
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


def _strip_fake_silence_placeholder(text: str) -> str:
    """Remove non-IPA silence placeholders while preserving real IPA alternatives."""
    s = str(text or "").strip()
    if s in {"[-]", "-", "[—]", "—", "[]"}:
        return ""
    # Examples: [u] / [-] -> [u], [-] / [u] -> [u].
    parts = [p.strip() for p in re.split(r"\s*/\s*", s)]
    kept = [p for p in parts if p not in {"[-]", "-", "[—]", "—", "[]"}]
    if len(kept) != len(parts):
        return " / ".join(kept)
    return s


def _sanitize_phonetic(value: str, term: str, language: str) -> str:
    if not isinstance(value, str):
        return value
    text = _strip_fake_silence_placeholder(value)
    if not text:
        return ""
    # Structurally malformed brackets: omit rather than invent a transcription.
    if text.startswith("[[") or text.endswith("]]" ) or text.count("[") != text.count("]"):
        return ""
    # High-confidence pseudo-IPA: a multiword phonetic field identical to the
    # written term (e.g. term='nitelikte olmak', phonetic='[nitelikte olmak]').
    # Single-word forms are intentionally not touched because orthography can
    # legitimately coincide with a broad IPA transcription.
    if isinstance(term, str) and " " in term.strip() and text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if unicodedata.normalize("NFC", inner).casefold() == unicodedata.normalize("NFC", term.strip()).casefold():
            return ""
    return text


def sanitize_publication_leaves(node, language: str = "", material_language: str = ""):
    """Return a structure-preserving copy with leaf-only high-confidence fixes."""
    if isinstance(node, list):
        return [sanitize_publication_leaves(v, language, material_language) for v in node]
    if isinstance(node, str):
        text = _normalize_ru_exact_text(node) if _is_russian(language) else node
        text = _normalize_japanese_exact_text(text, language)
        return _normalize_turkish_artificial_phrasing(text, material_language, language)
    if not isinstance(node, dict):
        return node

    out = {k: sanitize_publication_leaves(v, language, material_language) for k, v in node.items()}

    for key in ("term", "word", "title", "title_tr", "text", "text_tr", "heading", "label", "sentence", "example"):
        if isinstance(out.get(key), str):
            out[key] = _localize_known_structural_label(out[key], material_language)
            out[key] = _normalize_turkish_artificial_phrasing(out[key], material_language, language)
            out[key] = _normalize_japanese_exact_text(out[key], language)

    phonetic = out.get("phonetic")
    if isinstance(phonetic, str):
        lexical_term = ""
        for key in ("term", "word"):
            if isinstance(out.get(key), str) and out[key].strip():
                lexical_term = out[key]
                break
        out["phonetic"] = _sanitize_phonetic(phonetic, lexical_term, language)

    return out
