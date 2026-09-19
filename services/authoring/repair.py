"""Deterministic repairs. Everything here is provably safe or it is not here.

The division of labour with `audit.py` is the point of this module existing
separately. The auditor says what is wrong and never touches anything; this
fixes the subset that can be fixed without an opinion, and leaves the rest
reported so the engine can decide to regenerate.

The old pipeline merged the two, which cost it in both directions. Guards that
repaired as they detected could not be asked what they would have done, so the
only way to test one was to run the whole pipeline; and because repairing felt
free, several of them repaired things they should have refused — a phonetic
transcription guessed at, a claim hedged into vagueness rather than rejected.

The rule this module keeps: **repair changes presentation, never substance.**
Inserting an opening ¿ that Spanish requires does not change what the sentence
says. Mapping a Greek ε to the IPA ɛ it was obviously meant to be does not
change which sound is claimed. Deciding whether a Greek α meant `a` or `ɑ`
WOULD change it, so that one is refused and reported instead — the material is
regenerated rather than quietly guessed at, because a transcription is a factual
claim about a language and a wrong one teaches a wrong sound.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from services.authoring import schema as S

__all__ = ["repair_lesson", "repair_item", "repair_text", "open_spanish_punctuation",
           "rebuild_mcq_option_set"]


# ── Opening punctuation ──────────────────────────────────────────────────────
# Spanish opens a question with ¿ and an exclamation with ¡. Omitting them is a
# spelling error, not a stylistic choice, and the learner copies whatever the
# lesson prints.

# Where a question can begin inside a sentence: after a terminator, a colon or
# semicolon, a line break, or an opening quote or bracket — a quoted question
# opens inside its quotation marks, not before them.
_CLAUSE_OPENERS = set('.!?…\n\r«»"“”\'‘’()[]{}—–')

# After a vocative or a courtesy opener the question does not begin at the start
# of the sentence: "Perdone, ¿dónde está?". An interrogative word right after a
# comma is that boundary, and is the only comma this moves the mark to.
_INTERROGATIVE_AFTER_COMMA = re.compile(
    r",\s+(?=(?:por\s+qu[eé]|para\s+qu[eé]|a\s+d[oó]nde|ad[oó]nde|de\s+d[oó]nde|"
    r"qu[eé]|c[oó]mo|d[oó]nde|cu[aá]ndo|cu[aá]l(?:es)?|qui[eé]n(?:es)?|"
    r"cu[aá]nt[oa]s?)\b)", re.IGNORECASE)


def _insert_opener(text: str, closer: str, opener: str) -> str:
    """Give every unopened `closer` in `text` its `opener`.

    Walks right to left so an insertion never moves an index still to be
    handled. A run of closers ('???') counts once.
    """
    out = text
    index = len(out)
    while True:
        index = out.rfind(closer, 0, index)
        if index < 0:
            return out
        while index > 0 and out[index - 1] == closer:
            index -= 1

        cursor, opened = index - 1, False
        while cursor >= 0:
            if out[cursor] == opener:
                opened = True
                break
            if out[cursor] == closer:
                break
            cursor -= 1
        if opened:
            continue

        start = 0
        for pos in range(index - 1, -1, -1):
            if out[pos] in _CLAUSE_OPENERS:
                start = pos + 1
                break
        while start < index and out[start].isspace():
            start += 1
        segment = out[start:index]
        if not any(ch.isalpha() for ch in segment):
            continue
        vocative = None
        for match in _INTERROGATIVE_AFTER_COMMA.finditer(segment):
            vocative = match
        if vocative is not None:
            start += vocative.end()
        out = out[:start] + opener + out[start:]


def open_spanish_punctuation(text: str) -> str:
    out = text
    if "?" in out:
        out = _insert_opener(out, "?", "¿")
    if "!" in out:
        out = _insert_opener(out, "!", "¡")
    return out


# ── Character hygiene ────────────────────────────────────────────────────────
# Stripping a control or private-use character is safe: it carried no meaning
# and rendered as garbage in the PDF text layer. A U+FFFD replacement character
# is NOT stripped, because it marks a place where a real character was already
# lost — deleting it would hide the loss rather than repair it, and the auditor
# blocks on it so the field is regenerated instead.

_DROP_CATEGORIES = frozenset({"Co", "Cs", "Cc"})
_KEEP_FORMAT = frozenset({"‌", "‍", "‎", "‏", "⁠", "\n", "\t"})


def _clean_characters(text: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFC", text):
        if ch in _KEEP_FORMAT:
            out.append(ch)
            continue
        if unicodedata.category(ch) in _DROP_CATEGORIES:
            continue
        out.append(ch)
    return "".join(out)


def _repair_transcription(text: str) -> Tuple[str, bool]:
    """Never guess a phoneme from a Unicode look-alike.

    A Greek epsilon in a Spanish transcription can visually resemble either
    intended [e] or [ɛ]; turning it into one deterministically makes the string
    syntactically valid while potentially making the lesson factually wrong.
    Mechanical repair therefore only accepts already-clean IPA. The semantic
    quality gate owns corrections that require knowing the word and variety.
    """
    stray = S.stray_ipa_codepoints(text)
    return (text, not stray)


# ── Prose that prints itself twice ───────────────────────────────────────────
# A published B1 German reading passage printed two of its sentences twice in a
# row. `audit.duplicate_prose_sentence` blocks it; this removes it, so the
# defect costs nothing to fix and never reaches a model call. Deleting a second
# printing of a sentence the field already contains restores the text the
# lesson meant to have — the only other outcome is a reader seeing it twice.
#
# The identity is `audit.repeated_sentences`, imported rather than re-derived:
# a repair that deduplicated by a different rule than the auditor blocks on
# would leave the blocker standing and loop.

def _drop_repeated_sentences(text: str) -> str:
    from services.authoring import audit as A

    if not A.repeated_sentences(text):
        return text
    kept: List[str] = []
    seen: set = set()
    pos = 0
    for match in A._SENTENCE_SPLIT.finditer(text):
        kept, seen, pos = _keep_once(text, kept, seen, pos, match.end(), match.start())
    tail = text[pos:]
    if tail.strip():
        key = " ".join(A._TRAILING_TERMINATOR.sub("", tail).split()).casefold()
        if len(key.split()) < A._MIN_REPEAT_WORDS or key not in seen:
            kept.append(tail)
    return "".join(kept).strip()


def _keep_once(text, kept, seen, pos, end, split_at):
    """Keep one chunk of `text` unless it repeats a long sentence already kept."""
    from services.authoring import audit as A

    chunk = text[pos:end]
    body = text[pos:split_at]
    key = " ".join(A._TRAILING_TERMINATOR.sub("", body).split()).casefold()
    short = len(key.split()) < A._MIN_REPEAT_WORDS
    if short or key not in seen:
        kept.append(chunk)
        if not short:
            seen.add(key)
    return kept, seen, end


def repair_text(text: str, spec: S.FieldSpec, profile: Optional[S.ScriptProfile]) -> str:
    """Repair one string according to what kind of field it is."""
    if not isinstance(text, str) or not text.strip():
        return text
    out = _clean_characters(text)
    out = _drop_repeated_sentences(out)
    if spec.role == S.NOTATION:
        out, _ok = _repair_transcription(out)
    elif spec.role == S.TARGET and profile is not None:
        if profile.opens_questions or profile.opens_exclamations:
            out = open_spanish_punctuation(out)
    return out


# ── Whole objects ────────────────────────────────────────────────────────────

def repair_lesson(lesson: Any, *, language: str = "") -> Any:
    """Apply every safe repair to a lesson, in place. Idempotent.

    Target-language fields, phonetic fields and every other typed string are
    each handled by the rule for their own role, which is the whole reason the
    schema exists: a Turkish rationale in a Spanish course ends in '?' too and
    must not be given a '¿'.
    """
    if not isinstance(lesson, dict):
        return lesson
    profile = S.profile_for_language(language)
    for owner, key, spec, value in S.walk_fields(lesson):
        fixed = repair_text(value, spec, profile)
        if fixed != value:
            owner[key] = fixed
    return lesson


def repair_item(item: Dict[str, Any], *, language: str = "") -> Dict[str, Any]:
    """Repair one assessment item.

    The key and the option list are repaired by the same rule in the same pass,
    so they stay the same strings as each other — a repair that moved one and
    not the other would make the key unfindable among the options and the item
    would be dropped for a defect the repair itself introduced.
    """
    if not isinstance(item, dict):
        return item
    return repair_lesson(item, language=language)


def repair_all(items, *, language: str = "") -> List[Dict[str, Any]]:
    return [repair_item(item, language=language) for item in (items or [])]


# ── MCQ option-set shape ─────────────────────────────────────────────────────
# Deliberately NOT part of repair_lesson/repair_item. Those normalise text and
# run over every field of every page; this rebuilds one MCQ's answer/options/
# distractors as a single consistent tuple. Mixing the two would mean every
# text pass silently restructured assessment items, and a structural rebuild
# that only half-applied would create the very inconsistency the auditor exists
# to catch. Callers apply the returned tuple atomically or not at all.

def rebuild_mcq_option_set(item: Any) -> Optional[Dict[str, Any]]:
    """Rebuild one MCQ's option set from the strings the item already carries.

    `duplicate_options`, `distractor_count`, `empty_option`,
    `answer_not_in_options` and `option_distractor_mismatch` are all the same
    defect seen from different sides: the answer, the options and the stored
    distractors have stopped describing one coherent four-way choice. Repairing
    `options` alone cannot settle them, because the other two fields are what
    the remaining findings are computed from.

    Returns ``{"answer", "options", "distractors"}`` with four options distinct
    under `audit.option_identity`, the answer among them, and exactly the other
    three as distractors — but only when the item's own surviving text contains
    three usable wrong choices. Nothing is invented and no option is reworded:
    when the item is one short, this returns None and the caller must obtain the
    missing content some other way. Idempotent — a healthy item rebuilds to
    itself, order included.
    """
    from services.authoring import audit as A

    if not isinstance(item, dict):
        return None
    answer = str(item.get("answer") or "").strip()
    if not answer:
        # Without a key there is no fact to keep the option set consistent with,
        # and choosing one would be inventing the answer to the question.
        return None
    answer_key = A.option_identity(answer)
    if not answer_key:
        return None

    raw_options = item.get("options")
    if not isinstance(raw_options, list) or not raw_options:
        raw_options = item.get("choices") if isinstance(item.get("choices"), list) else []
    raw_distractors = item.get("distractors")
    if not isinstance(raw_distractors, list):
        raw_distractors = []

    # Learner-visible order is the option order; stored distractors only
    # contribute choices the option list lost. First spelling of an identity
    # wins, so a repair never silently reworks an option the learner has read.
    wrong: List[str] = []
    wrong_keys: set = set()
    answer_position: Optional[int] = None
    for source in (raw_options, raw_distractors):
        for raw in source:
            text = str(raw or "").strip()
            if not text:
                continue
            key = A.option_identity(text)
            if not key:
                continue
            if key == answer_key:
                if answer_position is None and source is raw_options:
                    answer_position = len(wrong)
                continue
            if key in wrong_keys:
                continue
            wrong_keys.add(key)
            wrong.append(text)

    if len(wrong) < 3:
        return None
    wrong = wrong[:3]

    # Put the key back exactly where the learner already saw it; an item whose
    # options never contained it gets it first rather than at a guessed slot.
    position = 0 if answer_position is None else min(answer_position, 3)
    options = wrong[:position] + [answer] + wrong[position:]
    return {"answer": answer, "options": options, "distractors": list(wrong)}
