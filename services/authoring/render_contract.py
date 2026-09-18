"""The one place that decides whether the renderer will publish a page.

A Spanish A1 classroom reached READY with a complete ten-question Unit 3
assessment in the database and only eight of those questions in the exported
PDF. Nothing was corrupted and nothing failed: the publication integrity gate
proved the stored assessment had ten MCQs, and the renderer then silently
dropped two of them on its way to the page.

It could do that because THREE separate pieces of code decided what was
publishable and had to agree with each other by hand:

  * `audit.py`, which judges typed content;
  * `quality_gate.validate_publication_integrity`, which modelled the renderer
    by importing `legacy_text._v57_unsafe_mcq`;
  * `pdf_renderer_v12`, which actually renders and used a DIFFERENT predicate,
    `_v54_pdf_unsafe_mcq` — a chain whose later layer adds two rules the gate
    never knew about (a workplace fact answered by a profession question, and a
    character-trait fact answered by an absolute-frequency option);
  * and `pdf_renderer_v12._normalize_pages`, which filtered pages through a
    THIRD predicate, `legacy_text._v57_unsafe_mcq`, before the render loop ever
    saw them — so a page could disappear without either of the other two being
    asked.

A Spanish unit about jobs produces "María trabaja en una oficina. ¿Cuál es su
profesión?" as a matter of course. That item passes the gate's predicate and
fails the renderer's, so it was validated and then discarded. Because each
stored MCQ page carries its own `"title": "Question N"`, the gap was visible in
the PDF as an assessment that begins at "Question 3".

The renderer's second drop is subtler and locale-dependent: it resolves a stem
with `_mcq_prompt`, which searches a DIFFERENT key order per locale and returns
empty when the stem exists only in the other locale's field. The gate's
`_stem_text` searches all keys in one order and always found something. So a
page could render in Turkish and vanish from English.

This module ends that class of bug by construction. It owns the decision, the
renderer calls it instead of deciding for itself, and the gate calls the same
function for every locale the course will be exported in. There is no second
implementation left to drift from, and a future rule added here is enforced by
the gate on the day it changes the renderer.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "EXPORT_LOCALES", "resolve_stem", "page_is_renderable", "unrenderable_pages",
    "mcq_pages", "mcq_like", "hidden_world_reason", "strip_unit_prefix",
]


# Every locale a course can be exported in. The gate checks a page against all
# of them, because a classroom is READY for both exports or it is not READY.
EXPORT_LOCALES: Tuple[bool, ...] = (True, False)   # is_tr


def _locale_name(is_tr: bool) -> str:
    return "tr" if is_tr else "en"


# ── Stem resolution ──────────────────────────────────────────────────────────
# Exactly the key order the renderer uses, kept here so there is one answer to
# "what question will the learner see" rather than one per caller.

_STEM_KEYS_TR = ("prompt_tr", "prompt", "question_tr", "question",
                 "stem_tr", "stem", "text_tr", "text")
_STEM_KEYS_EN = ("prompt_en", "prompt", "question_en", "question",
                 "stem_en", "stem", "text_en", "text")


def resolve_stem(page: Dict[str, Any], is_tr: bool) -> str:
    """The stem the renderer would print for this locale, or '' if none."""
    if not isinstance(page, dict):
        return ""
    for key in (_STEM_KEYS_TR if is_tr else _STEM_KEYS_EN):
        value = page.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


# ── The unsafe-item predicate ────────────────────────────────────────────────
# The composed behaviour of the renderer's `_v54_pdf_unsafe_mcq` chain, written
# out once. These rules exist because an MCQ that infers an identity fact from
# a biographical one has no defensible answer: where somebody works does not
# establish their profession, and being punctual does not make an absolute
# frequency claim true. The renderer refused to print them; it simply refused
# after the course had already been declared publishable.

def _fold(text: Any) -> str:
    folded = unicodedata.normalize("NFD", str(text or "")).casefold()
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return folded.replace("ı", "i")


_GENDER_WORDS = re.compile(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b")
_NAME_WORDS = re.compile(r"\b(isim|ismi|adi|adinin|name)\b")

_BIOGRAPHY = ("dogdu", "dogmus", "yasiyor", "yasadi", "calisiyor", "born", "lives",
              "works", "resides", "родил", "жив", "работ", "nacio", "vive",
              "trabaja", "geboren", "lebt", "arbeitet", "habite", "travaille")
_IDENTITY = re.compile(
    r"\b(milliyet|uyruk|nationality|national|dil|konus|language|speak|speaks|"
    r"spoken|meslek|profession|occupation|job)\b")

_WORKPLACE_FACT = ("calisiyor", "calisir", "work at", "works at", "works in",
                   "working at", "working in", "arbeitet", "travaille", "trabaja",
                   "lavora", "trabalha", "работает", "работа в")
_PROFESSION_QUESTION = ("meslegi", "meslek nedir", "profession", "occupation",
                        "job is", "what does", "beruf", "profession est",
                        "profesion", "profissão", "професс", "кем он", "кем она")
_TRAIT_FACT = ("dakik", "punctual", "punktlich", "ponctuel", "puntual", "pontual",
               "пунктуал")
_ABSOLUTE_FREQUENCY = ("nikogda", "vsegda", "never", "always", "niemals", "immer",
                       "jamais", "toujours", "nunca", "siempre", "mai", "sempre",
                       "никогда", "всегда")


def _has_biography_marker(text: str, markers: Sequence[str]) -> bool:
    """Whether text actually states a biographical fact.

    Most entries are deliberate stems (for example Russian работ-) and therefore
    use substring matching. Spanish nació folds to nacio, though, and that byte
    sequence is also the beginning of nacionalidad. Treat that marker as a whole
    word so asking about nationality is not itself mistaken for a birthplace fact.
    """
    for marker in markers:
        if marker == "nacio":
            if re.search(r"(?<!\w)nacio(?!\w)", text):
                return True
            continue
        if marker in text:
            return True
    return False


def unsafe_reason(page: Dict[str, Any], stem: str, is_tr: bool) -> str:
    """Why the renderer would refuse this item, or '' if it would print it."""
    if not isinstance(page, dict):
        return "not an object"

    explanation = page.get("explanation_tr") if is_tr else page.get("explanation_en")
    explanation = explanation or page.get("explanation") or ""
    prompt, expl = _fold(stem), _fold(explanation)

    explicit_gender = bool(_GENDER_WORDS.search(prompt))
    if _NAME_WORDS.search(expl) and _GENDER_WORDS.search(expl) and not explicit_gender:
        return "answer depends on gender inferred from a personal name"

    if _has_biography_marker(prompt, _BIOGRAPHY) and _IDENTITY.search(expl):
        return "answer depends on an identity fact inferred from a biographical one"

    options = page.get("options") or page.get("choices") or []
    if isinstance(options, dict):
        options = list(options.values())
    folded_options = _fold(" ".join(str(v or "") for v in (options or [])))

    if any(x in prompt for x in _WORKPLACE_FACT) and \
            any(x in prompt for x in _PROFESSION_QUESTION):
        return "profession asked from a workplace fact"

    if any(x in prompt for x in _TRAIT_FACT) and \
            any(x in folded_options for x in _ABSOLUTE_FREQUENCY):
        return "character trait answered by an absolute-frequency option"

    return ""


# ── The locale-independent hidden-world layer ────────────────────────────────
# The renderer drops pages in TWO places, not one. Besides the MCQ branch above,
# `_normalize_pages` filtered every page through `legacy_text._v57_unsafe_mcq`
# before the render loop ever saw it — a broader predicate that reads the union
# of all explanation fields rather than one locale's, recognises a page as an
# MCQ by its shape rather than its `type`, and carries longer word lists. A page
# it refused disappeared from the export without either the render loop or the
# gate being consulted, which is the same divergence one layer earlier.
#
# So it lives here now, and `_normalize_pages` no longer filters at all.

_V57_STEM_KEYS = ("prompt_tr", "question_tr", "stem_tr", "prompt_en", "question_en",
                  "stem_en", "prompt", "question", "stem", "text_tr", "text_en", "text")
_V57_EXPLANATION_KEYS = ("explanation_tr", "analysis_tr", "explanation_en",
                         "analysis_en", "explanation", "analysis")

_V57_GENDER_WORDS = re.compile(
    r"\b(kadin|erkek|disil|eril|female|male|woman|man|feminine|masculine)\b")
_V57_NAME_WORDS = re.compile(r"\b(isim|ismi|adi|adinin|name)\b")
_V57_GENDER_NOUNS = (
    "женщина", "мужчина", "девушка", "мальчик", "девочка", "мать", "отец", "мама",
    "папа", "сестра", "брат", "бабушка", "дедушка", "wife", "husband", "mother",
    "father", "sister", "brother")
_V57_BIOGRAPHY = (
    "dogdu", "dogmus", "dogum", "yasiyor", "yasadi", "ikamet", "calisiyor", "calisti",
    "born", "birthplace", "lives", "lived", "resides", "resided", "works", "worked",
    "родил", "рожден", "жив", "работ", "nacio", "nacido", "vive", "trabaja",
    "geboren", "lebt", "arbeitet", "nee", "habite", "travaille")
_V57_IDENTITY = re.compile(
    r"\b(milliyet|uyruk|nationality|national|ethnicity|etnisite|dil|konus|language|"
    r"speak|speaks|spoken|meslek|profession|occupation|job|disil|eril|female|male|"
    r"feminine|masculine)\b")


def _v57_stem(page: Dict[str, Any]) -> str:
    for key in _V57_STEM_KEYS:
        value = page.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def mcq_like(page: Any) -> bool:
    """Whether the renderer's page filter treats this page as a question.

    Shape, not `type`: a page carrying options and a stem is filtered as an MCQ
    even when it calls itself something else.
    """
    if not isinstance(page, dict):
        return False
    if str(page.get("type") or "").strip().casefold() == "mcq":
        return True
    return bool((page.get("options") or page.get("choices")) and _v57_stem(page))


def hidden_world_reason(page: Dict[str, Any]) -> str:
    """Why the renderer's page filter would remove this item, or ''."""
    if not mcq_like(page):
        return ""
    prompt = _fold(_v57_stem(page))
    expl = _fold(" ".join(str(page.get(key) or "") for key in _V57_EXPLANATION_KEYS))

    explicit_gender = bool(_V57_GENDER_WORDS.search(prompt)) or \
        any(noun in prompt for noun in _V57_GENDER_NOUNS)
    if _V57_NAME_WORDS.search(expl) and _V57_GENDER_WORDS.search(expl) \
            and not explicit_gender:
        return "answer depends on gender inferred from a personal name"

    if _has_biography_marker(prompt, _V57_BIOGRAPHY) and _V57_IDENTITY.search(expl):
        return "answer depends on an identity fact inferred from a biographical one"
    return ""


# ── The contract ─────────────────────────────────────────────────────────────

def page_is_renderable(page: Dict[str, Any], is_tr: bool) -> Tuple[bool, str]:
    """Whether the renderer will print this page, and why not if it will not.

    Both of the renderer's drop points are asked: the page filter that runs
    before the render loop, which is locale-independent and recognises a
    question by its shape, and the MCQ branch of the loop itself, which is
    locale-dependent and only sees pages typed `mcq`.
    """
    if not isinstance(page, dict):
        return False, "page is not an object"

    hidden = hidden_world_reason(page)
    if hidden:
        return False, hidden

    if str(page.get("type") or "").casefold() != "mcq":
        return True, ""

    stem = resolve_stem(page, is_tr)
    if not stem:
        return False, f"no stem resolves in the {_locale_name(is_tr)} export"

    reason = unsafe_reason(page, stem, is_tr)
    if reason:
        return False, reason
    return True, ""


def mcq_pages(content: Any) -> List[Dict[str, Any]]:
    pages = (content or {}).get("pages") if isinstance(content, dict) else None
    return [p for p in (pages or [])
            if isinstance(p, dict) and str(p.get("type") or "").casefold() == "mcq"]


def unrenderable_pages(content: Any,
                       locales: Sequence[bool] = EXPORT_LOCALES) -> List[Dict[str, str]]:
    """Every page that some export locale would silently discard.

    This is what the publication gate asks before a course may become READY.
    A page that renders in Turkish and disappears from English is still a
    divergence between the validated state and an exported one, so both locales
    are checked and either one failing is a failure.
    """
    pages = (content or {}).get("pages") if isinstance(content, dict) else None
    lost: List[Dict[str, str]] = []
    for index, page in enumerate(pages or []):
        if not isinstance(page, dict):
            lost.append({"index": str(index), "locale": "*", "why": "page is not an object"})
            continue
        for is_tr in locales:
            ok, why = page_is_renderable(page, is_tr)
            if not ok:
                lost.append({
                    "index": str(index),
                    "title": str(page.get("title") or "")[:60],
                    "locale": _locale_name(is_tr),
                    "why": why,
                })
    return lost


# ── Heading composition ──────────────────────────────────────────────────────
# The renderer prints a chapter as "Ünite {n}: {title}". The curriculum planner
# now writes bilingual unit titles, and a model asked for a unit title very
# reasonably answers "Ünite 1: İlk Kelimeler ve Selamlaşma" — so the heading
# came out as "Ünite 1: Ünite 1: İlk Kelimeler ve Selamlaşma". Stripping a
# prefix the renderer is about to add is the narrow fix, and it belongs beside
# the other rules about what actually reaches the page.

_UNIT_PREFIX = re.compile(
    r"^\s*(?:ünite|unite|unit|unidad|unità|unidade|einheit|unité|блок|раздел|단원|课|課)"
    r"\s*[0-9IVXivx]*\s*[:.\-–—]\s*",
    re.IGNORECASE)


def strip_unit_prefix(title: Any) -> str:
    """A chapter title without the 'Unit N:' the renderer supplies itself."""
    text = str(title or "").strip()
    for _ in range(3):
        stripped = _UNIT_PREFIX.sub("", text, count=1).strip()
        if stripped == text or not stripped:
            break
        text = stripped
    return text or str(title or "").strip()
