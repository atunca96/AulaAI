"""Curated canonical pronunciation overrides for publication safety.

This module is intentionally small and conservative.  It is NOT a G2P engine and
must never infer IPA from spelling.  Entries are added only when a canonical
learner-facing pronunciation has been independently verified.  Unmatched terms
return None and are left untouched by callers.
"""
from __future__ import annotations

import unicodedata


# Canonical Russian citation-form IPA.  Initial closed-set entries are limited to
# high-frequency A1 vocabulary for which we have independently verified a stable
# lexical pronunciation.  Sources: English Wiktionary Russian entries, checked
# 2026-09-14.  Optional/senior/colloquial variants are deliberately not used;
# the learner-facing value is the common citation-form reading.
_RUSSIAN_CANONICAL_IPA = {
    # Days of the week.
    "понедельник": "[pənʲɪˈdʲelʲnʲɪk]",
    "вторник": "[ˈftornʲɪk]",
    "среда": "[srʲɪˈda]",
    "четверг": "[t͡ɕɪtˈvʲerk]",
    "пятница": "[ˈpʲætʲnʲɪt͡sə]",
    "суббота": "[sʊˈbotə]",
    "воскресенье": "[vəskrʲɪˈsʲenʲje]",
    # High-frequency closed-inventory numerals with independently verified
    # citation forms.  For пятьдесят the source allows optional consonant
    # length; use the conservative form without optional length for learners.
    "сорок": "[ˈsorək]",
    "пятьдесят": "[pʲɪdʲɪˈsʲat]",
    "восемьдесят": "[ˈvosʲɪmdʲɪsʲɪt]",
}


def _strip_pedagogical_stress(text: str) -> str:
    """Normalize lookup spelling without destroying lexical letters such as й."""
    nfd = unicodedata.normalize("NFD", str(text or ""))
    # Only acute/grave pedagogical stress marks are removed.  Other combining
    # marks remain part of the spelling so unrelated terms cannot collide.
    nfd = "".join(ch for ch in nfd if ch not in {"\u0300", "\u0301"})
    return unicodedata.normalize("NFC", nfd).casefold().strip()


def _is_russian(language: str) -> bool:
    value = str(language or "").casefold()
    return "russian" in value or "rusça" in value or "рус" in value


def lookup_canonical_ipa(language: str, term: str):
    """Return verified canonical IPA for an exact lexical term, else None.

    This is deliberately an exact lexical lookup.  No stemming, token splitting,
    transliteration, fuzzy matching, or spelling-to-sound inference is allowed.
    """
    if not _is_russian(language):
        return None
    key = _strip_pedagogical_stress(term)
    if not key or any(ch.isspace() for ch in key) or "/" in key:
        return None
    return _RUSSIAN_CANONICAL_IPA.get(key)


def apply_canonical_pronunciation_overrides(node, language: str):
    """Leaf-only tree transform; never deletes or creates structural content.

    A value is changed only when a dict already contains a string `phonetic`
    field and an exact `term` or `word` with a verified lexicon entry.
    """
    if isinstance(node, list):
        return [apply_canonical_pronunciation_overrides(v, language) for v in node]
    if not isinstance(node, dict):
        return node

    out = {k: apply_canonical_pronunciation_overrides(v, language) for k, v in node.items()}
    if not isinstance(out.get("phonetic"), str):
        return out

    lexical_term = None
    for key in ("term", "word"):
        value = out.get(key)
        if isinstance(value, str) and value.strip():
            lexical_term = value
            break
    if lexical_term is None:
        return out

    canonical = lookup_canonical_ipa(language, lexical_term)
    if canonical is not None:
        out["phonetic"] = canonical
    return out
