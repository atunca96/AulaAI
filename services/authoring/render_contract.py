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
    "explain_hidden_world",
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
_NAME_WORDS = re.compile(r"\b(ismi|adi|adinin|name)\b")

# The one refusal an item cannot argue with: the rationale says the personal
# name is what tells the learner the gender. Named once so the gate can route
# this blocker to the repair that can actually clear it.
NAME_GENDER_REASON = "answer depends on gender inferred from a personal name"

# ── The hidden-world invariant ───────────────────────────────────────────────
#
# Every blocker in this layer refuses an item because the learner cannot reach
# the keyed answer from what is in front of them. That is a statement about the
# ANSWER, so each blocker owes two things, not one:
#
#   1. the risky inference is present, and
#   2. that inference could change WHICH OPTION IS CORRECT.
#
# (2) is what the name/gender rule was missing, and missing it is what refused
# "The House and Locations / Prepositions of Place / pages[3]" in production. A
# preposition item whose subject happens to be called Ana, whose rationale
# explains the gender of a completely different noun («mesa» is feminine, so it
# takes «la»), was refused: a person appeared in the stem, gender vocabulary
# appeared in the rationale, and nothing checked that the two had anything to do
# with each other or with the answer. The answer was `debajo de`, chosen against
# `encima de`, `al lado de` and `detrás de` — no fact about anybody's gender can
# select among those.
#
# Turkish is where the co-occurrence approach also broke in the opposite
# direction: `isim` is the ordinary grammatical term for a noun, so the safe
# rationale an agreement item has to write was refused, while agglutination hid
# the genuinely unsafe "Ayşe kadın ismidir" (`ismidir` is not `\bismi\b`).
# Widening lexicons only trades one direction for the other, once per taught
# language, so the predicate is the relation instead: a statement is unsafe when
# it claims a gender, refers to a person the item names, AND the gender could
# decide the answer.
_STATEMENT_SPLIT = re.compile(r"[.!?;:\n\r…]+")
_WORD_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)

# Fields whose contents are taught vocabulary rather than a person: a capitalised
# token that is also an option, a key or a glossed term is a word the lesson
# teaches, not somebody's name.
_LEXICAL_KEYS = ("answer", "options", "choices", "distractors", "term", "word",
                 "target", "translation", "translation_tr", "translation_en")


def _lexical_tokens(page: Dict[str, Any]) -> set:
    out = set()
    for key in _LEXICAL_KEYS:
        value = page.get(key)
        if isinstance(value, dict):
            value = list(value.values())
        if not isinstance(value, (list, tuple)):
            value = [value]
        for item in value:
            out.update(_WORD_TOKEN.findall(_fold(item)))
    # Anything the material quotes is being mentioned as language, not as a
    # person: «mujer», "alta", 'el'.
    return out


def _quoted_common_tokens(text: Any) -> set:
    """Quoted tokens that are ordinary words, not quoted proper nouns.

    "«книga» dişil bir isimdir" cites a noun the material teaches. "'Марina'
    bir kadın ismidir" cites a PERSON. Capitalisation is the only
    lexicon-free way to tell them apart, and it is the one the writing system
    already provides.
    """
    out = set()
    for quoted in re.findall(r"[«\"'‘“]([^»\"'’”]{1,40})[»\"'’”]",
                             str(text or "")):
        for raw in _WORD_TOKEN.findall(quoted):
            if raw[:1].isupper():
                continue
            folded = _fold(raw)
            if folded:
                out.add(folded)
    return out


def _quoted_tokens(text: Any) -> set:
    out = set()
    for quoted in re.findall(r"[«\"'‘“]([^»\"'’”]{1,40})[»\"'’”]",
                             str(text or "")):
        out.update(_WORD_TOKEN.findall(_fold(quoted)))
    return out


def _quoted_language_tokens(text: Any) -> set:
    """Quoted tokens that are clearly cited as language material.

    A multi-token quoted phrase (for example an article+noun phrase) is a
    linguistic citation. A single quoted capitalised token is NOT enough to
    establish that: it may be a person's name repeated in the rationale.
    """
    out = set()
    for quoted in re.findall(r"[«\"'‘“]([^»\"'’”]{1,40})[»\"'’”]",
                             str(text or "")):
        tokens = _WORD_TOKEN.findall(_fold(quoted))
        if len(tokens) >= 2:
            out.update(tokens)
    return out


def personal_name_tokens(page: Dict[str, Any], stem: str) -> set:
    """Folded tokens of the people this item names.

    A personal name is a proper noun the item introduces as a person. Taught
    vocabulary and quoted language are excluded, so a Spanish item about «mujer»
    or an item whose key is `España` introduces nobody.
    """
    if not isinstance(page, dict):
        return set()
    # Quoted COMMON words are the material citing its own vocabulary («mesa»,
    # «книга»). A quoted proper noun ('Анна') is the rationale citing the very
    # person this rule is about, so excluding it would hide the defect.
    skip = _lexical_tokens(page) | _quoted_common_tokens(stem)
    for key in _V57_EXPLANATION_KEYS:
        skip |= _quoted_common_tokens(page.get(key))
    names = set()
    for raw in _WORD_TOKEN.findall(str(stem or "")):
        if len(raw) < 3 or not raw[:1].isupper() or raw.isupper():
            continue
        folded = _fold(raw)
        if folded and folded not in skip:
            names.add(folded)
    return names


def _normalised_options(page: Dict[str, Any]) -> List[str]:
    options = page.get("options") or page.get("choices") or []
    if isinstance(options, dict):
        options = list(options.values())
    if not isinstance(options, (list, tuple)):
        options = [options]
    out = []
    for value in options:
        folded = " ".join(_WORD_TOKEN.findall(_fold(value)))
        if folded:
            out.append(folded)
    return out


def _same_paradigm(a: str, b: str) -> bool:
    """Whether two options are forms of one word rather than different words."""
    if a == b:
        return False
    shared = 0
    for left, right in zip(a, b):
        if left != right:
            break
        shared += 1
    shorter = min(len(a), len(b))
    if shorter < 3 or shared < 3:
        return False
    return (shared >= 0.6 * shorter
            and (len(a) - shared) <= 3 and (len(b) - shared) <= 3)


def answer_turns_on_form(page: Dict[str, Any]) -> bool:
    """Whether choosing among the options is choosing a FORM of one word.

    This is the deterministic, language-agnostic half of the hidden-world
    invariant for gender: a fact about somebody's gender can only decide the
    answer when at least two options are the same stem with different endings.
    `alta / alto / altos / altas` is such a set. `debajo de / encima de /
    al lado de / detrás de` is not — those are four different words, and no
    inference about a person selects among them.

    Nothing here knows any language. It compares the option strings to each
    other, which is exactly what a learner choosing between them does.
    """
    options = _normalised_options(page)
    return any(
        _same_paradigm(options[i], options[j])
        for i in range(len(options))
        for j in range(i + 1, len(options))
    )


def _options_are_gender_values(page: Dict[str, Any],
                               gender_words: "re.Pattern[str]") -> bool:
    """Whether picking an option IS picking a gender.

    `kadın / erkek / genç / yaşlı` is not a form paradigm — those are four
    different words — but two of them are the genders themselves, so inferring
    a person's gender answers the question outright. Uses the gender lexicon
    this rule already has; nothing is added to it.
    """
    matched = 0
    for option in _normalised_options(page):
        if gender_words.search(option) or any(
            noun in option for noun in _V57_GENDER_NOUNS
        ):
            matched += 1
    return matched >= 2


def question_is_about_a_quoted_word(stem: Any) -> bool:
    """Whether the item asks about a word it quotes, rather than about a person.

    "Ella trabaja en un hospital. ¿Qué significa «hospital»?" mentions a
    workplace and quotes the very token it is asking the learner to gloss. The
    answer is a translation; no fact about the speaker's life can change it.
    The quoted token has to appear unquoted in the same stem, so an item that
    merely quotes what it is asking for — "¿Cuál es su «nacionalidad»?" — is
    not exempted.
    """
    text = str(stem or "")
    quoted = _quoted_tokens(text)
    if not quoted:
        return False
    plain = re.sub(r"[«\"'‘“][^»\"'’”]{1,40}[»\"'’”]", " ", text)
    return bool(quoted & set(_WORD_TOKEN.findall(_fold(plain))))


def _name_gender_rationale(explanation: Any, name_words: "re.Pattern[str]",
                           gender_words: "re.Pattern[str]", names: set,
                           page: Dict[str, Any]) -> bool:
    """Whether one statement grounds a gender claim in a person the item names.

    Both halves of the invariant are required: the statement must tie a gender
    claim to a person this item introduces, and the gender must be able to
    decide the answer — either because the options are forms of one word, or
    because that very statement names the keyed answer.
    """
    if not names:
        # No candidate person is introduced, so no rationale can be refusing
        # personal-name inference. Grammatical terminology is free.
        return False

    # Could a gender fact actually decide which option is correct?
    decisive = (answer_turns_on_form(page)
                or _options_are_gender_values(page, gender_words))

    for statement in _STATEMENT_SPLIT.split(str(explanation or "")):
        folded = _fold(statement)
        if not gender_words.search(folded):
            continue

        tokens = set(_WORD_TOKEN.findall(folded))
        candidate_hits = tokens & names
        explicitly_about_a_name = bool(name_words.search(folded))

        # An explicit personal-name reference may be anaphoric ("ismi", "adı",
        # "the name") and need not repeat the person's token in this statement.
        # Bare Turkish "isim" is intentionally absent from the personal-name
        # lexicon because it is also the ordinary grammatical word for "noun".
        if explicitly_about_a_name:
            return True

        if not candidate_hits:
            continue

        quoted_language = _quoted_language_tokens(statement)

        # Quoting a SINGLE candidate token does not prove it is language
        # material; rationales often quote a person's name. Only a clearly
        # lexical multi-token citation is exempted here. This keeps genuine
        # name->gender cases blocked while allowing cited noun phrases such as
        # an article+noun expression to explain grammatical agreement.
        person_hits = candidate_hits - quoted_language
        if decisive and person_hits:
            return True

    return False


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
    if not explicit_gender and _name_gender_rationale(
        explanation, _NAME_WORDS, _GENDER_WORDS,
        personal_name_tokens(page, stem), page,
    ):
        return NAME_GENDER_REASON

    # Same invariant: the biographical fact must be able to decide the answer.
    # A gloss item that quotes the very word it asks about ("Ella trabaja en un
    # hospital. ¿Qué significa «hospital»?") is asking for a translation, and no
    # fact about the speaker's life selects among its options.
    if _has_biography_marker(prompt, _BIOGRAPHY) and _IDENTITY.search(expl) \
            and not question_is_about_a_quoted_word(stem):
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
_V57_NAME_WORDS = re.compile(r"\b(ismi|adi|adinin|name)\b")
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
    # Per explanation field, not over their concatenation: each locale's reader
    # sees only their own rationale, and joining them let a name word in one
    # locale pair with a grammar word in the other and refuse both exports.
    names = personal_name_tokens(page, _v57_stem(page))
    if not explicit_gender and any(
        _name_gender_rationale(page.get(key), _V57_NAME_WORDS, _V57_GENDER_WORDS,
                               names, page)
        for key in _V57_EXPLANATION_KEYS
    ):
        return NAME_GENDER_REASON

    if _has_biography_marker(prompt, _V57_BIOGRAPHY) and _V57_IDENTITY.search(expl) \
            and not question_is_about_a_quoted_word(_v57_stem(page)):
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


# ── Diagnostic decomposition ─────────────────────────────────────────────────
# A production page refused with NAME_GENDER_REASON that no fixture reproduces
# is not debuggable from the reason string: the string is one bit of output from
# a predicate with six inputs and two independent firing routes. `pages[4]` of
# "Relative Clauses with Nominative, Accusative, and Dative" survived three
# repair strategies while every regression stayed green, which means the
# fixtures and the live page differ in an input nobody has measured.
#
# This function measures them. It reads nothing but the page, changes nothing,
# and is never consulted by `page_is_renderable`: adding it cannot alter which
# pages publish. It exists so the next production retry names the statement and
# the boolean that produced the refusal instead of the refusal alone.
#
# The per-statement trace is written independently of `_name_gender_rationale`
# rather than by instrumenting it, so the live predicate keeps exactly the bytes
# it has today. `trace_agrees` cross-checks the two; a False there is itself a
# finding and means this decomposition, not the predicate, is what to fix.

_DIAG_CLIP = 400


def _clip(value: Any) -> str:
    text = str(value or "")
    return text if len(text) <= _DIAG_CLIP else text[:_DIAG_CLIP] + "…"


def _name_gender_statements(explanation: Any, name_words: "re.Pattern[str]",
                            gender_words: "re.Pattern[str]", names: set,
                            page: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per-statement decomposition of `_name_gender_rationale`, read-only."""
    decisive = (answer_turns_on_form(page)
                or _options_are_gender_values(page, gender_words))
    answer_tokens = set(_WORD_TOKEN.findall(_fold(page.get("answer"))))
    choice_tokens = set(answer_tokens)
    for option in _normalised_options(page):
        choice_tokens.update(option.split())

    rows: List[Dict[str, Any]] = []
    for statement in _STATEMENT_SPLIT.split(str(explanation or "")):
        folded = _fold(statement)
        gender_hits = gender_words.findall(folded)
        if not gender_hits:
            continue
        tokens = set(_WORD_TOKEN.findall(folded))
        name_hits = name_words.findall(folded)
        explicitly_about_a_name = bool(name_hits)
        names_in_statement = sorted(tokens & names)
        quoted_tokens = sorted(_quoted_tokens(statement))
        quoted_language_tokens = sorted(_quoted_language_tokens(statement))
        person_hits = sorted((tokens & names) - set(quoted_language_tokens))
        quoted_common = sorted(_quoted_common_tokens(statement))

        # Explicit personal-name wording may be anaphoric and omit the person's
        # token ("ismi", "adı", "the name"). Bare Turkish "isim" is excluded
        # from the name-word lexicon because it also means the grammatical NOUN.
        route_explicit_name = explicitly_about_a_name
        route_decisive_person = bool(person_hits) and decisive

        rows.append({
            "statement": _clip(statement.strip()),
            "folded": _clip(folded.strip()),
            "gender_word_hits": gender_hits,
            "name_word_hits": name_hits,
            "names_in_statement": names_in_statement,
            "person_hits_unquoted": person_hits,
            "answer_tokens_all_present": bool(answer_tokens
                                              and answer_tokens <= tokens),
            "quoted_tokens": quoted_tokens,
            "quoted_language_tokens": quoted_language_tokens,
            "quoted_common_tokens": quoted_common,
            "route_explicit_name": route_explicit_name,
            "route_decisive_person": route_decisive_person,
            "fires": route_explicit_name or route_decisive_person,
        })
    return rows


def explain_hidden_world(page: Dict[str, Any]) -> Dict[str, Any]:
    """The complete predicate decomposition behind one page's render verdict.

    Pure. Returns the booleans, not the page: every field here is an INPUT to a
    branch in `hidden_world_reason` / `unsafe_reason`, so the output identifies
    which branch refused the item and on which statement. `classification` is a
    mechanical label, derived only from the booleans beside it, that maps one
    log line onto one root cause.
    """
    if not isinstance(page, dict):
        return {"mcq_like": False, "classification": "not_an_object"}

    stem = _v57_stem(page)
    stem_field = next((key for key in _V57_STEM_KEYS
                       if isinstance(page.get(key), str) and page[key].strip()), "")
    names = personal_name_tokens(page, stem)
    folded_prompt = _fold(stem)

    # Which aliases actually carry text, so a repair that wrote the wrong one
    # or left a higher-priority one behind is visible rather than inferred.
    stem_aliases = {key: _clip(page[key]) for key in _V57_STEM_KEYS
                    if isinstance(page.get(key), str) and page[key].strip()}
    rationale_aliases = {key: _clip(page[key]) for key in _V57_EXPLANATION_KEYS
                         if isinstance(page.get(key), str) and page[key].strip()}

    explicit_gender_v57 = (bool(_V57_GENDER_WORDS.search(folded_prompt))
                           or any(noun in folded_prompt
                                  for noun in _V57_GENDER_NOUNS))
    # `unsafe_reason` computes this from a DIFFERENT lexicon and without the
    # gender-noun list, so the two layers can disagree. Report both.
    explicit_gender_unsafe = bool(_GENDER_WORDS.search(folded_prompt))

    fields: List[Dict[str, Any]] = []
    for key in _V57_EXPLANATION_KEYS:
        value = page.get(key)
        if value in (None, ""):
            continue
        statements = _name_gender_statements(
            value, _V57_NAME_WORDS, _V57_GENDER_WORDS, names, page)
        predicate = _name_gender_rationale(
            value, _V57_NAME_WORDS, _V57_GENDER_WORDS, names, page)
        fields.append({
            "field": key,
            "raw": _clip(value),
            "folded": _clip(_fold(value)),
            "quoted_common_tokens": sorted(_quoted_common_tokens(value)),
            "statements": statements,
            "name_gender_rationale": predicate,
            "trace_agrees": any(row["fires"] for row in statements) == predicate,
        })

    hidden = hidden_world_reason(page)
    stem_tr, stem_en = resolve_stem(page, True), resolve_stem(page, False)
    unsafe_tr = unsafe_reason(page, stem_tr, True) if stem_tr else "no stem"
    unsafe_en = unsafe_reason(page, stem_en, False) if stem_en else "no stem"
    ok_tr, why_tr = page_is_renderable(page, True)
    ok_en, why_en = page_is_renderable(page, False)

    decisive_form = answer_turns_on_form(page)
    decisive_values = _options_are_gender_values(page, _V57_GENDER_WORDS)
    firing = [
        {"field": f["field"], "statement": row["statement"],
         "route_explicit_name": row["route_explicit_name"],
         "route_decisive_person": row["route_decisive_person"],
         "name_word_hits": row["name_word_hits"],
         "names_in_statement": row["names_in_statement"],
         "person_hits_unquoted": row["person_hits_unquoted"]}
        for f in fields for row in f["statements"] if row["fires"]
    ]

    # One mechanical label per root cause, from the booleans above only.
    if hidden != NAME_GENDER_REASON and NAME_GENDER_REASON not in (unsafe_tr, unsafe_en):
        classification = "clean_of_name_gender"
    elif hidden == NAME_GENDER_REASON and not firing:
        classification = "predicate_bug_no_statement_accounts_for_it"
    elif (hidden == NAME_GENDER_REASON) != (
            NAME_GENDER_REASON in (unsafe_tr, unsafe_en)):
        classification = "layer_disagreement_hidden_world_vs_unsafe_reason"
    elif decisive_form or decisive_values:
        classification = "decisive_option_shape"
    elif any(row["route_explicit_name"] for row in firing):
        classification = "explicit_personal_name_claim"
    elif any(row["route_decisive_person"] for row in firing):
        classification = "decisive_unquoted_person_candidate"
    else:
        classification = "unclassified"

    return {
        "mcq_like": mcq_like(page),
        "type": str(page.get("type") or ""),
        "title": _clip(page.get("title")),
        "v57_stem_field": stem_field,
        "v57_stem_value": _clip(stem),
        "stem_aliases_present": stem_aliases,
        "rationale_aliases_present": rationale_aliases,
        "resolved_tr_stem": _clip(stem_tr),
        "resolved_en_stem": _clip(stem_en),
        "personal_name_tokens": sorted(names),
        "lexical_tokens": sorted(_lexical_tokens(page)),
        "options_normalised": _normalised_options(page),
        "answer": _clip(page.get("answer")),
        "answer_turns_on_form": decisive_form,
        "options_are_gender_values": decisive_values,
        "decisive": decisive_form or decisive_values,
        "explicit_gender_v57": explicit_gender_v57,
        "explicit_gender_unsafe_reason": explicit_gender_unsafe,
        "rationale_fields": fields,
        "firing_statements": firing,
        "hidden_world_reason": hidden,
        "unsafe_reason_tr": unsafe_tr,
        "unsafe_reason_en": unsafe_en,
        "page_is_renderable_tr": [ok_tr, why_tr],
        "page_is_renderable_en": [ok_en, why_en],
        "classification": classification,
    }
