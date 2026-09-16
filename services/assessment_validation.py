"""Deterministic checks on generated assessment items. No model call, ever.

Every rule the assessment contract states is worth stating once to the
generator; the ones that can be MEASURED are worth checking afterwards, because
a rule that is only ever asked for is a rule that silently degrades. Nothing
here asks a model whether a model's output was acceptable — that pattern costs a
second generation per assessment and was explicitly ruled out.

Two design constraints shaped what is checkable:

  * The TAUGHT language can be any of fifteen, so nothing here may depend on
    knowing how a particular target language works. Checks about the taught
    language are structural (option counts, gap runs, duplicate keys,
    provenance).
  * The INSTRUCTIONAL language is only ever Turkish or English — that is the
    whole set, by product design. So detecting instructional-language prose
    where the contract requires target-language prose is a closed problem, and
    a small marker list for exactly two languages is a legitimate solution
    rather than a per-language heuristic pile.

`violations()` returns a list of short machine-readable reasons; empty means the
item is publishable. Callers decide whether a violation drops the item or is
merely reported — dropping is right for a malformed item and wrong for a
localization gap, and that judgement belongs at the call site.
"""

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

__all__ = [
    "violations", "filter_publishable", "normalize_token",
    "TRANSLATION_REQUEST", "looks_like_translation_question",
    "instructional_prose_ratio", "out_of_scope_terms",
]


def normalize_token(text: Any) -> str:
    """Lowercase, strip diacritics and punctuation. Works across scripts."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text).lower().strip())
    no_marks = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s]", "", no_marks).strip()


# ── Translation questions ─────────────────────────────────────────────────────
# Asked in one of the two instructional languages, or as a bare-English gloss
# request. These are the forms a translation drill actually takes; the check is
# on the STEM, which the contract requires to be target-language anyway, so a
# match is a violation twice over.
TRANSLATION_REQUEST = [
    # English instructional phrasings
    r"\bwhat does\b.{0,40}\bmean\b",
    r"\bwhat is the (?:english|turkish|meaning|translation)\b",
    r"\bhow do you say\b",
    r"\btranslate\b",
    r"\bin english\b.{0,20}\?",
    r"\bthe (?:english|turkish) (?:for|equivalent|translation) of\b",
    r"\bwhich (?:option|word|one) means\b",
    # Turkish instructional phrasings
    r"\bne demek(?:tir)?\b",
    r"\bne anlama gel",
    r"\bt[uü]rk[cç]e(?:si|ye)?\s+(?:nedir|kar[sş][ıi]l[ıi][ğg][ıi]|anlam[ıi])",
    r"\b[ıi]ngilizce(?:si|ye)?\s+(?:nedir|kar[sş][ıi]l[ıi][ğg][ıi])",
    r"\bkar[sş][ıi]l[ıi][ğg][ıi]\s+nedir\b",
    r"\b[cç]evir(?:in|iniz|isi)\b",
    r"\banlam[ıi]\s+nedir\b",
]
_TRANSLATION_RE = [re.compile(p, re.IGNORECASE) for p in TRANSLATION_REQUEST]


def looks_like_translation_question(stem: Any) -> bool:
    text = str(stem or "")
    return any(rx.search(text) for rx in _TRANSLATION_RE)


# ── Instructional-language prose where target-language is required ────────────
# Function words, not content words: these carry almost no risk of colliding
# with a target language's vocabulary, and they are what instructional prose is
# built out of.
_EN_FUNCTION = {
    "the", "which", "what", "choose", "correct", "sentence", "word", "option",
    "following", "answer", "complete", "select", "best", "means", "meaning",
    "of", "is", "are", "to", "for", "and", "with", "from", "that",
}
_TR_FUNCTION = {
    "hangisi", "hangi", "asagidakilerden", "asagidaki", "seciniz", "secin",
    "cumleyi", "cumlede", "dogru", "uygun", "kelimeyi", "kelime", "bosluga",
    "tamamlayin", "anlamina", "karsiligi", "secenek", "verilen", "icin",
}


def instructional_prose_ratio(stem: Any, instructional_track: str = "tr") -> float:
    """Share of stem tokens that are instructional-language function words.

    A target-language stem scores near zero. A stem written in the instructional
    language scores high. Deliberately blunt: it is a tripwire for prose in the
    wrong language, not a language identifier.
    """
    tokens = [t for t in normalize_token(stem).split() if t]
    if not tokens:
        return 0.0
    vocab = _TR_FUNCTION if str(instructional_track).casefold() == "tr" else _EN_FUNCTION
    # Both sets are checked when the target language is neither, because an item
    # may leak either instructional language regardless of the published track.
    hits = sum(1 for t in tokens if t in vocab or t in _EN_FUNCTION or t in _TR_FUNCTION)
    return hits / len(tokens)


_GAP_RUN = re.compile(r"[_＿﹍﹏‗]{2,}")


# ── Scope leakage ─────────────────────────────────────────────────────────────

def out_of_scope_terms(item: Dict[str, Any], forbidden_terms: Iterable[str]) -> List[str]:
    """Terms from OUTSIDE the authorized scope that appear in the item.

    Framed as leakage detection rather than membership proof on purpose. Demanding
    that a keyed answer appear verbatim in the source would reject every correctly
    inflected form and every legitimate scenario transfer the contract allows.
    Detecting a term that provably belongs to a topic this assessment may not
    touch has no such false-positive class: if Topic 5's vocabulary is in a
    Topic 3 question, that is leakage whatever the phrasing.
    """
    haystack = " ".join(
        str(item.get(k) or "") for k in ("prompt", "answer", "why", "evidence")
    )
    haystack += " " + " ".join(str(d) for d in (item.get("distractors") or []))
    hay = f" {normalize_token(haystack)} "
    found = []
    for term in forbidden_terms:
        key = normalize_token(term)
        if len(key) < 4:
            continue  # too short to attribute safely across languages
        if f" {key} " in hay:
            found.append(term)
    return found


# ── The item check ────────────────────────────────────────────────────────────

def violations(
    item: Dict[str, Any],
    *,
    instructional_track: str = "tr",
    forbidden_terms: Optional[Iterable[str]] = None,
    require_rationale_track: bool = True,
    max_instructional_ratio: float = 0.55,
) -> List[str]:
    """Every deterministic rule this item breaks. Empty list means publishable."""
    problems: List[str] = []
    if not isinstance(item, dict):
        return ["not_an_object"]

    stem = str(item.get("prompt") or "").strip()
    answer = str(item.get("answer") or "").strip()
    distractors = item.get("distractors")
    distractors = [str(d).strip() for d in distractors] if isinstance(distractors, list) else []

    # Structure — language-agnostic.
    if not stem:
        problems.append("missing_stem")
    if not answer:
        problems.append("missing_answer")
    clean_d = [d for d in distractors if d]
    if len(clean_d) != 3:
        problems.append(f"distractor_count_{len(clean_d)}")
    keys = [normalize_token(answer)] + [normalize_token(d) for d in clean_d]
    if len(set(k for k in keys if k)) != len([k for k in keys if k]):
        problems.append("duplicate_options")
    if normalize_token(answer) in {normalize_token(d) for d in clean_d}:
        problems.append("answer_among_distractors")

    options = item.get("options")
    if isinstance(options, list) and options:
        if len(options) != 4:
            problems.append(f"option_count_{len(options)}")
        opt_keys = [normalize_token(o) for o in options]
        present = [k for k in opt_keys if k]
        # `options` is the list the learner actually reads, and it is assembled
        # separately from `distractors` (shuffled, sometimes supplemented). A
        # duplicate can therefore exist here while the distractor list is clean,
        # which is exactly the case that reaches a learner as two identical
        # buttons — so it is checked on its own terms rather than inferred.
        if len(set(present)) != len(present) and "duplicate_options" not in problems:
            problems.append("duplicate_options")
        if normalize_token(answer) and normalize_token(answer) not in set(opt_keys):
            problems.append("answer_not_in_options")

    # The question must not be a translation drill.
    if looks_like_translation_question(stem):
        problems.append("translation_question")

    # The stem must be target-language prose, not instructional-language prose.
    if stem and instructional_prose_ratio(stem, instructional_track) >= max_instructional_ratio:
        problems.append("stem_in_instructional_language")

    # A gap must not be given away by the reference gloss.
    if _GAP_RUN.search(stem):
        for gloss_key in ("translation_en", "translation_tr"):
            gloss = str(item.get(gloss_key) or "")
            if gloss and not _GAP_RUN.search(gloss):
                problems.append(f"gap_lost_in_{gloss_key}")
            elif gloss and normalize_token(answer) and len(normalize_token(answer)) >= 3:
                if f" {normalize_token(answer)} " in f" {normalize_token(gloss)} ":
                    problems.append(f"answer_revealed_in_{gloss_key}")

    # The answer key must speak the published instructional track.
    if require_rationale_track:
        preferred = "why_tr" if str(instructional_track).casefold() == "tr" else "why"
        if not str(item.get(preferred) or "").strip():
            problems.append(f"missing_{preferred}")

    # Scope.
    if forbidden_terms:
        leaked = out_of_scope_terms(item, forbidden_terms)
        if leaked:
            problems.append("out_of_scope:" + ",".join(leaked[:3]))

    return problems


# Violations that mean the item is broken, versus ones that mean it is merely
# incomplete. A malformed item must not reach a learner; a missing rationale
# translation is a gap the renderer can fall back through, and dropping the
# question over it would cost an assessment item to save a sentence.
_DROP_PREFIXES = (
    "missing_stem", "missing_answer", "distractor_count_", "duplicate_options",
    "answer_among_distractors", "option_count_", "answer_not_in_options",
    "translation_question", "stem_in_instructional_language",
    "answer_revealed_in_", "out_of_scope:",
)


def is_fatal(problem: str) -> bool:
    return any(problem.startswith(p) for p in _DROP_PREFIXES)


def filter_publishable(
    items: Sequence[Dict[str, Any]],
    *,
    instructional_track: str = "tr",
    forbidden_terms: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Split a batch into publishable items and a per-item reason log."""
    kept: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    reported: List[str] = []
    for item in items or []:
        problems = violations(
            item,
            instructional_track=instructional_track,
            forbidden_terms=forbidden_terms,
        )
        fatal = [p for p in problems if is_fatal(p)]
        if fatal:
            rejected.append({"prompt": str((item or {}).get("prompt") or "")[:80], "why": fatal})
            continue
        reported.extend(p for p in problems if p not in fatal)
        kept.append(item)
    return {"kept": kept, "rejected": rejected, "reported": reported}
