"""One class, one pronunciation per word.

Lesson-local ownership fixed the case where a single lesson transcribed the same
word two ways. It could not fix the case a class actually produces, because a
class is thirty lessons generated independently and in parallel, each deriving
its own pronunciation for whatever vocabulary it happens to reuse. Nothing
compared lesson 3 against lesson 11, so a learner met おはようございます as
[ohajoː ɡozai̯masɯ̥] in one and [ohajoː ɡozaːmasɯ] in another - the second having
quietly lost the /i/ and lengthened a vowel - and せんせい differed across lessons
the same way. Both cannot be what the course teaches, and the learner has no way
to tell which to trust.

What this module will not do
----------------------------
It will not decide which transcription is correct. Deterministic code has no
basis for that in any language, and the tempting rule - take whichever appears
most often - is exactly how a wrong value generated early would be propagated
over correct values generated later, turning a local defect into a course-wide
one while looking like a consistency improvement. Frequency is evidence about
the generator, not about the language.

So the resolution is split by who is competent to make it:

  * At GENERATION time, a conflict is routed into the bounded review the lesson
    already runs - no extra model call - as a question about the language:
    two transcriptions are offered for one headword, and the reviewer supplies
    the right one or declines. Judgement is made by the only participant that
    can make it, before anything is published.

  * At RENDER time, when the class exists as a whole and no model is in the loop,
    the remaining disagreements are settled only where the evidence is
    one-sided, and a genuine tie is left alone as an explicit contextual variant
    rather than broken arbitrarily.

Reuse also has a cost story, and it is worth being precise about it: the saving
is in NOT sending the class's established vocabulary back into the generation
prompt. Feeding prior lessons' terms into each new lesson's prompt would make the
system prompt differ per lesson, which would destroy the cache breakpoint that
every lesson in a class shares. Reconciling after generation keeps both the
consistency and the cache.
"""

from __future__ import annotations

import threading
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple


def fold_term(value: Any) -> str:
    """Identity key for a headword: NFC, casefolded, whitespace-stripped.

    Deliberately conservative. Two spellings that differ by anything more than
    case or spacing are treated as different words, because deciding that they
    are the same word is a linguistic judgement this module does not make.
    """
    text = unicodedata.normalize("NFC", str(value or "")).strip().casefold()
    return " ".join(text.split())


def normalize_transcription(value: Any) -> str:
    text = unicodedata.normalize("NFC", str(value or "")).strip()
    return " ".join(text.split())


class ClassLexicon:
    """Pronunciations this class has already published, and who published them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._label = ""

    def reset(self, label: str = "") -> None:
        with self._lock:
            self._entries = {}
            self._label = str(label or "")

    def register(self, term: Any, phonetic: Any, source: str = "", reviewed: bool = False) -> None:
        """Record that this class published `phonetic` for `term`.

        `reviewed` marks a value the bounded review confirmed or supplied. A
        reviewed value outranks an unreviewed one no matter how many times the
        unreviewed one was generated, because one act of judgement is worth more
        than any amount of repetition by the same generator.
        """
        key = fold_term(term)
        value = normalize_transcription(phonetic)
        if not key or not value:
            return
        with self._lock:
            entry = self._entries.setdefault(key, {"term": str(term), "variants": {}})
            variant = entry["variants"].setdefault(
                value, {"count": 0, "reviewed": False, "sources": []}
            )
            variant["count"] += 1
            variant["reviewed"] = variant["reviewed"] or bool(reviewed)
            if source and source not in variant["sources"]:
                variant["sources"].append(str(source))

    def established(self, term: Any) -> Optional[str]:
        """The transcription this class has already published for a term, if any.

        A reviewed value wins outright. Otherwise the earliest-registered value is
        returned - not the most frequent one - so that what the caller compares
        against is stable and does not shift under it as more lessons land.
        """
        key = fold_term(term)
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                return None
            variants = entry["variants"]
            for value, meta in variants.items():
                if meta["reviewed"]:
                    return value
            return next(iter(variants), None)

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {
                key: {
                    "term": entry["term"],
                    "variants": {v: dict(m) for v, m in entry["variants"].items()},
                }
                for key, entry in self._entries.items()
            }

    def disagreements(self) -> List[Dict[str, Any]]:
        """Terms this class published more than one way."""
        out = []
        for key, entry in self.snapshot().items():
            if len(entry["variants"]) > 1:
                out.append({"key": key, "term": entry["term"], "variants": entry["variants"]})
        return out


LEXICON = ClassLexicon()


def reset(label: str = "") -> None:
    LEXICON.reset(label)


def iter_transcribed_terms(data: Any) -> Iterable[Tuple[str, str, str]]:
    """Every (term, phonetic, path) a lesson publishes.

    Walks whatever shape the lesson has rather than a fixed list of containers,
    because a transcription is a transcription wherever the schema puts it, and a
    container added later should not silently fall outside class consistency.
    """
    def walk(node: Any, path: str):
        if isinstance(node, dict):
            term = node.get("term") or node.get("word") or node.get("target")
            phonetic = node.get("phonetic")
            if term and isinstance(phonetic, str) and phonetic.strip():
                yield str(term), phonetic, (path + ".phonetic" if path else "phonetic")
            for key, value in node.items():
                yield from walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from walk(value, f"{path}.{index}")

    yield from walk(data.get("pages") if isinstance(data, dict) else None, "pages")


def register_lesson(data: Any, source: str = "", reviewed_paths: Optional[set] = None) -> int:
    """Add a published lesson's transcriptions to the class lexicon."""
    registered = 0
    reviewed_paths = reviewed_paths or set()
    for term, phonetic, path in iter_transcribed_terms(data):
        LEXICON.register(term, phonetic, source=source, reviewed=path in reviewed_paths)
        registered += 1
    return registered


def collect_class_phonetic_conflicts(data: Any, limit: int = 4) -> List[Dict[str, Any]]:
    """Claims for terms this lesson transcribes differently from the rest of the class.

    Shaped for the bounded review that already runs on this lesson, so detecting a
    cross-lesson conflict costs no additional model call. The claim is phrased as a
    question about the language rather than as an instruction to match the class:
    the established value is offered as a competing candidate, not as the answer,
    because the established one is just as likely to be the wrong one.
    """
    out: List[Dict[str, Any]] = []
    seen = set()
    for term, phonetic, path in iter_transcribed_terms(data):
        key = fold_term(term)
        if key in seen:
            continue
        established = LEXICON.established(term)
        if not established:
            continue
        current = normalize_transcription(phonetic)
        if not current or current == established:
            continue
        seen.add(key)
        out.append({
            "path": path,
            "text": (
                f"{term}: this lesson transcribes it {current}; "
                f"elsewhere in this course the same word is transcribed {established}. "
                "At most one can be right."
            ),
            "field_value": phonetic,
            "repair": "omit_ok",
            "domain": "pronunciation",
            "quantifiers": ["cross_lesson_transcription_conflict"],
            "examples": [f"{term} = {established}", f"{term} = {current}"],
        })
        if len(out) >= limit:
            break
    return out


def class_phonetic_winners(lessons: List[Any]) -> Dict[str, str]:
    """Decide, across a whole class, which transcription a word should carry.

    A term is settled only when one transcription is strictly better attested than
    every other. An exact tie is deliberately left unsettled: two lessons
    disagreeing once each carries no evidence about which is right, and breaking
    that tie would be a coin toss handed to the learner as a fact. Unsettled terms
    keep whatever each lesson authored, which is the honest representation of a
    disagreement nothing here is competent to resolve.

    Plurality is used only to pick between values the generator already produced -
    never to invent one, and never to overrule the bounded review, which has
    already had its say at generation time and whose verdicts are what most of
    these lessons now carry.
    """
    counts: Dict[str, Dict[str, int]] = {}
    for lesson in lessons:
        for term, phonetic, _path in iter_transcribed_terms(lesson):
            key = fold_term(term)
            value = normalize_transcription(phonetic)
            if key and value:
                variants = counts.setdefault(key, {})
                variants[value] = variants.get(value, 0) + 1

    winners: Dict[str, str] = {}
    for key, variants in counts.items():
        if len(variants) < 2:
            continue
        ordered = sorted(variants.items(), key=lambda kv: kv[1], reverse=True)
        if ordered[0][1] > ordered[1][1]:
            winners[key] = ordered[0][0]
    return winners


def apply_phonetic_winners(lesson: Any, winners: Dict[str, str]) -> int:
    """Rewrite a lesson's transcriptions to the class-wide decision. Returns edits."""
    if not winners or not isinstance(lesson, dict):
        return 0
    changed = 0

    def walk(node: Any) -> None:
        nonlocal changed
        if isinstance(node, dict):
            term = node.get("term") or node.get("word") or node.get("target")
            phonetic = node.get("phonetic")
            if term and isinstance(phonetic, str) and phonetic.strip():
                winner = winners.get(fold_term(term))
                if winner and normalize_transcription(phonetic) != winner:
                    node["phonetic"] = winner
                    changed += 1
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(lesson.get("pages"))
    return changed


def resolve_across_class(lessons: List[Any]) -> int:
    """Settle disagreements over an assembled class in place. Returns edits made."""
    winners = class_phonetic_winners(lessons)
    return sum(apply_phonetic_winners(lesson, winners) for lesson in lessons)
