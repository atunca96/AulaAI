"""The boundary every reader crosses to obtain content.

A renderer must not be able to reach stored material without the material having
been repaired and checked, because that is exactly how two exporters came to
disagree about what was publishable: one parsed the stored JSON straight into
its layout code and shipped whatever was in the database, while the other
applied a set of invariants. A defect fixed in one simply did not exist in the
other.

Making the parse step the enforcement point removes that whole class of
divergence — crossing the boundary is how content is obtained, so it cannot be
skipped by forgetting to call something.

This also covers material generated before this rebuild existed. Those lessons
carry defects the new generator cannot produce, and they are still in the
database. Repair runs over them on the way to the page, and a structurally
invalid assessment item is dropped rather than rendered.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from services.authoring import audit as A
from services.authoring import repair as R
from services.authoring import schema as S

__all__ = [
    "load_publishable_content", "publishable", "safe_unicode_normalize",
    "sanitize_dialogue_speaker", "sanitize_instructional_metalanguage", "char_script",
]


# ── Character-level helpers the renderers use ────────────────────────────────

def safe_unicode_normalize(text: Any, language: Optional[str] = None) -> Any:
    """NFC, minus anything that must never reach a published text layer.

    Kept as a standalone entry point because the renderers apply it to strings
    they compose themselves — page furniture, headers, joined labels — which
    never passed through the schema and so have no declared role.
    """
    if not isinstance(text, str) or not text:
        return text
    return R._clean_characters(text)


_TRAILING_ANNOTATION = re.compile(r"\s*\([^()\n]{1,80}\)\s*$")


def sanitize_dialogue_speaker(value: Any) -> str:
    """The speaker's name, without the annotations a generator attaches to it."""
    text = safe_unicode_normalize(str(value or "")).strip()
    previous = None
    while previous != text:
        previous = text
        text = _TRAILING_ANNOTATION.sub("", text).strip()
    return text


# Grammar shorthand in the wrong language. The new generator cannot emit this —
# `audit.py` blocks a field whose prose is not in its declared track — but the
# database holds years of material that can, and this runs on the way to the
# page. It is a data table rather than a behaviour, which is why it survived a
# rebuild that deleted the five stacked functions that used to apply it.
_SHORTHAND: Dict[str, List[Tuple[str, str]]] = {
    "en": [
        (r"\beril\b", "masculine"), (r"\bdi[şs]il\b", "feminine"),
        (r"\btekil\b", "singular"), (r"\[cç]o[ğg]ul\b", "plural"),
        (r"\bn[öo]tr\b", "neuter"),
    ],
    "tr": [
        (r"\(\s*masc(?:\.|uline)?\s*\)", "(eril)"),
        (r"\(\s*fem(?:\.|inine)?\s*\)", "(dişil)"),
        (r"\(\s*neut(?:\.|er)?\s*\)", "(nötr)"),
        (r"\(\s*m\.\s*\)", "(eril)"), (r"\(\s*f\.\s*\)", "(dişil)"),
        (r"\(\s*n\.\s*\)", "(nötr)"),
        (r"\(\s*pl(?:\.|ural)?\s*\)", "(çoğul)"),
        (r"\(\s*(?:sg|sing)(?:\.|ular)?\s*\)", "(tekil)"),
        (r"\(\s*nom(?:\.|inative)?\s*\)", "(Yalın Hâl)"),
        (r"\(\s*gen(?:\.|itive)?\s*\)", "(İlgi/Tamlayan Hâli)"),
        (r"\(\s*acc(?:\.|usative)?\s*\)", "(Belirtme Hâli)"),
        (r"\(\s*dat(?:\.|ive)?\s*\)", "(Yönelme Hâli)"),
        (r"\(\s*prep(?:\.|ositional)?\s*\)", "(Edat Durumu)"),
        (r"\(\s*inst(?:\.|r|rumental)?\s*\)", "(Araç Hâli)"),
        (r"\bmasc\.", "eril"), (r"\bfem\.", "dişil"), (r"\bneut\.", "nötr"),
        (r"\bpl\.", "çoğul"), (r"\b(?:sg|sing)\.", "tekil"),
        (r"\bnom\.", "Yalın Hâl"), (r"\bgen\.", "İlgi/Tamlayan Hâli"),
        (r"\bacc\.", "Belirtme Hâli"), (r"\bdat\.", "Yönelme Hâli"),
        (r"\bprep\.", "Edat Durumu"), (r"\b(?:inst|instr)\.", "Araç Hâli"),
    ],
}
_SHORTHAND_COMPILED = {
    track: [(re.compile(p, re.IGNORECASE), r) for p, r in rules]
    for track, rules in _SHORTHAND.items()
}


def sanitize_instructional_metalanguage(value: Any, material_language: str = "tr") -> str:
    """Put grammar shorthand into the language the reader is reading."""
    text = safe_unicode_normalize(str(value or ""))
    if not text:
        return text
    track = str(material_language or "tr").strip().casefold()[:2]
    for pattern, replacement in _SHORTHAND_COMPILED.get(track, ()):
        text = pattern.sub(replacement, text)
    return text


def char_script(ch: str) -> Optional[str]:
    """The writing system one character belongs to, or None if it is not a letter."""
    if not isinstance(ch, str) or not ch or not ch.isalpha():
        return None
    return S.script_of(ch) or "Other"


# ── The boundary ─────────────────────────────────────────────────────────────

def _coerce(raw: Any) -> Dict[str, Any]:
    data: Any = raw
    if isinstance(raw, (bytes, bytearray)):
        try:
            data = raw.decode("utf-8", "replace")
        except Exception:
            data = ""
    if isinstance(data, str):
        text = data.strip()
        if not text:
            return {"pages": []}
        try:
            data = json.loads(text)
        except Exception:
            return {"pages": []}
    if isinstance(data, list):
        return {"pages": data}
    if not isinstance(data, dict):
        return {"pages": []}
    if not isinstance(data.get("pages"), list):
        data["pages"] = []
    return data


def _localise_shorthand(node: Any, track: str) -> None:
    """Put grammar shorthand into the reader's language, everywhere it appears.

    Runs over learner-facing prose only. A target-language example may contain
    the letters 'pl.' as part of a word in some language, and rewriting inside
    the material being taught would corrupt it — so this follows the schema's
    roles like everything else here.
    """
    readable = {S.INSTRUCTION, S.GLOSS, S.EVIDENCE}
    for owner, key, spec, value in S.walk_fields(node):
        if spec.role not in readable:
            continue
        fixed = sanitize_instructional_metalanguage(value, track)
        if fixed != value:
            owner[key] = fixed


def load_publishable_content(raw: Any, language: Optional[str] = None,
                             material_language: str = "tr",
                             topic: str = "") -> Dict[str, Any]:
    """Parse stored lesson content and put it through the boundary.

    Accepts a JSON string, a dict or a list of pages and always returns a dict
    with a `pages` list, so a caller never has to guess at the shape. Repair is
    idempotent, so content that already crossed the boundary is unchanged and it
    is safe to apply at generation and again at render.
    """
    data = _coerce(raw)
    R.repair_lesson(data, language=language or "")
    _localise_shorthand(data, material_language)

    pages = data.get("pages")
    if isinstance(pages, list):
        kept: List[Any] = []
        dropped: List[Dict[str, str]] = []
        for index, page in enumerate(pages):
            if isinstance(page, dict) and \
                    str(page.get("type") or "").strip().casefold() == "mcq":
                blocking = A.blocking(A.audit_item(page, language=language or "",
                                                   track=material_language))
                # Only STRUCTURAL invalidity removes a page. A question whose
                # rationale is missing a translation still teaches; one whose key
                # is not among its options cannot be answered at all.
                fatal = [f for f in blocking if f.code in _UNANSWERABLE]
                if fatal:
                    dropped.append({"index": str(index),
                                    "why": ",".join(f.code for f in fatal)})
                    continue
            kept.append(page)
        data["pages"] = kept
        if dropped:
            data["_dropped_items"] = dropped
    return data


# An item with any of these cannot be answered as printed, so rendering it does
# the learner harm. Everything else the auditor reports is a quality finding
# that belongs to generation, not to the page.
_UNANSWERABLE = frozenset({
    "missing_stem", "missing_answer", "distractor_count", "duplicate_options",
    "empty_option", "answer_not_in_options", "not_an_object",
})


def publishable(lesson: Any, *, language: str = "", track: str = "tr") -> Tuple[bool, List[A.Finding]]:
    """Whether a freshly generated lesson may be stored, and why not if not."""
    findings = A.audit_lesson(lesson, language=language, track=track)
    return (not A.blocking(findings)), findings
