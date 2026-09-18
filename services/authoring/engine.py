"""Generation: ask, repair, audit, and decide whether to ask again.

The loop this replaces retried a lesson when the answer was cut off, and
otherwise accepted whatever came back. Truncation is the one failure it could
see, so it was the one failure it could fix; everything else — a stray Greek
letter in a transcription, an invented word, an English sentence in a Turkish
lesson — was published.

Here the auditor decides. A draft is repaired first, because a defect that
`repair.py` can fix costs nothing to fix and paying a model to fix it again
would be silly. What survives repair is audited, and a draft with blocking
findings is regenerated ONCE, with the findings included in the request. That
last part is the whole difference: a blind retry samples the same distribution
and usually reproduces the same defect, while a retry that says "your
transcription of *cena* contained Greek epsilon, and your table left three rows
of the phonetic column blank" fixes those two things specifically.

One retry, never two. A second failure means the topic is fighting the level or
the source, and a third paid attempt at the same thing is how a build's cost
runs away — which is a decision the ledger enforces rather than trusts.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from services.authoring import audit as A
from services.authoring import budget as B
from services.authoring import prompts as P
from services.authoring import repair as R
from services.authoring import schema as S
from services.authoring import transport as T

__all__ = ["generate_lesson", "generate_assessment", "LessonResult", "AssessmentResult",
           "estimate_tokens"]


def estimate_tokens(*parts: Any) -> int:
    return int(sum(len(str(p)) for p in parts) / 4.0)


def _uid() -> str:
    return str(uuid.uuid4())


class LessonResult:
    __slots__ = ("lesson", "findings", "attempts", "cost", "error")

    def __init__(self, lesson=None, findings=None, attempts=0, cost=0.0, error=""):
        self.lesson = lesson
        self.findings: List[A.Finding] = findings or []
        self.attempts = attempts
        self.cost = cost
        self.error = error

    @property
    def ok(self) -> bool:
        return bool(self.lesson) and not self.error

    @property
    def clean(self) -> bool:
        return self.ok and not A.blocking(self.findings)


class AssessmentResult:
    __slots__ = ("items", "findings", "attempts", "cost", "error")

    def __init__(self, items=None, findings=None, attempts=0, cost=0.0, error=""):
        self.items: List[Dict[str, Any]] = items or []
        self.findings: List[A.Finding] = findings or []
        self.attempts = attempts
        self.cost = cost
        self.error = error

    @property
    def ok(self) -> bool:
        return bool(self.items) and not self.error


# ── Turning findings back into an instruction ────────────────────────────────

def _correction_note(findings: Sequence[A.Finding], limit: int = 10) -> str:
    """The retry's reason for existing: say exactly what was wrong.

    Grouped by code so twelve blank transcription cells arrive as one
    instruction rather than twelve, and capped, because a list long enough to
    dominate the request is evidence that regenerating wholesale is the answer.
    """
    blocking = A.blocking(findings)
    if not blocking:
        return ""
    seen: Dict[str, List[A.Finding]] = {}
    for finding in blocking:
        seen.setdefault(finding.code, []).append(finding)

    lines: List[str] = []
    for code, group in list(seen.items())[:limit]:
        first = group[0]
        where = f" at {first.path}" if first.path else ""
        detail = f" — {first.detail}" if first.detail else ""
        count = f" ({len(group)} places)" if len(group) > 1 else ""
        lines.append(f"- {_EXPLAIN.get(code, code)}{where}{count}{detail}")
        if first.value:
            lines.append(f"    you wrote: {first.value[:140]}")
    return ("\nYour previous draft was rejected. Fix exactly these defects and keep "
            "everything else that was correct:\n" + "\n".join(lines) + "\n")


_EXPLAIN = {
    "non_ipa_in_transcription":
        "a phonetic transcription contained characters that are not IPA",
    "respelling_in_notation":
        "a phonetic field held an ad-hoc respelling instead of IPA",
    "second_pronunciation_system":
        "you used a second pronunciation system beside IPA; use IPA only",
    "self_contradicting_transcription":
        "you transcribed the same form two different ways in one lesson",
    "partial_transcription_column":
        "a table transcribed some rows and left others blank; transcribe all or none",
    "invented_form_taught":
        "you printed a form you yourself called hypothetical or not a real word",
    "wrong_instructional_language":
        "a field carried the wrong language for its track",
    "instructional_prose_in_target_field":
        "a target-language field held instructional prose instead of the language itself",
    "mixed_script_token":
        "a single word mixed two writing systems",
    "unicode_corruption":
        "a string contained a corrupted or unprintable character",
    "missing_opening_question_mark":
        "a question was written without its opening mark",
    "duplicate_options":
        "two options of one question read identically",
    "mixed_spelling_variants":
        "one option was another with a diacritic changed, which is a typo not a distractor",
    "key_length_outlier":
        "the correct option stood out by its length",
    "feature_only_in_key":
        "the stem named a feature only the correct option had",
    "stem_in_instructional_language":
        "a question stem was written in the instructional language, not the taught one",
    "answer_revealed_in_gloss":
        "the reference gloss gave the answer away",
    "distractor_count": "an item did not have exactly three distractors",
    "missing_stem": "an item had no question", "missing_answer": "an item had no answer",
    "answer_not_in_options": "the keyed answer was not among the options",
    "option_distractor_mismatch": "stored options and distractors disagree",
}


# ── Lessons ──────────────────────────────────────────────────────────────────

_INVENTORY_HINTS = ("alphabet", "alfabe", "alfabeto", "abecedario", "writing system",
                    "hiragana", "katakana", "hangul", "kana", "script", "letters",
                    "numbers", "numeral", "sayılar", "números")


def _is_inventory_topic(topic: str, topic_type: str) -> bool:
    haystack = f"{topic} {topic_type}".casefold()
    return any(hint in haystack for hint in _INVENTORY_HINTS)


def generate_lesson(*, topic: str, topic_type: str, language: str, level: str,
                    track: str = "tr", ledger: Optional[B.BuildLedger] = None,
                    source_text: str = "", taught_so_far: Sequence[str] = (),
                    pages: int = 5, item_budget: int = 2, institution: str = "",
                    model: str = "", temperature: float = 0.55,
                    unit_title: str = "", unit_topics: Sequence[str] = ()) -> LessonResult:
    """One lesson, repaired and audited, regenerated at most once."""
    ledger = ledger or B.BuildLedger(label=f"{language} {level}")
    system = P.build_lesson_system(language=language, level=level, track=track,
                                   institution=institution)
    ceiling = B.lesson_output_ceiling(pages, inventory=_is_inventory_topic(topic, topic_type))
    system_tokens = estimate_tokens(system)

    findings: List[A.Finding] = []
    spent = 0.0
    correction = ""
    best: Optional[Dict[str, Any]] = None
    best_findings: List[A.Finding] = []

    for attempt in range(2):
        user = P.build_lesson_user(
            topic=topic, topic_type=topic_type, source_text=source_text,
            taught_so_far=taught_so_far, page_target=pages, item_budget=item_budget,
            track=track, language=language, request_id=f"{_uid()}",
            unit_title=unit_title, unit_topics=unit_topics)
        if correction:
            user = user + correction

        input_tokens = system_tokens + estimate_tokens(user)
        cached = system_tokens if attempt or ledger.entries else 0
        try:
            ledger.require(stage="lesson", input_tokens=input_tokens,
                           output_tokens=ceiling, cached_tokens=cached)
        except B.BudgetExceeded as exc:
            return LessonResult(lesson=best, findings=best_findings, attempts=attempt,
                                cost=spent, error=str(exc) if best is None else "")

        response = T.call_model(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=ceiling, temperature=temperature, model=model or B.MODEL)

        wasted = not response.ok
        spent += ledger.record(stage="lesson", subject=topic, wasted=wasted,
                               input_tokens=response.input_tokens or input_tokens,
                               output_tokens=response.output_tokens,
                               cached_tokens=response.cached_tokens,
                               reported_cost=response.cost)
        if not response.ok:
            correction = ""
            if attempt:
                return LessonResult(lesson=best, findings=best_findings, attempts=attempt + 1,
                                    cost=spent, error=response.error)
            continue

        lesson = response.data
        if isinstance(lesson, list):
            lesson = {"pages": lesson}
        if not isinstance(lesson, dict) or not isinstance(lesson.get("pages"), list):
            correction = "\nYour previous answer was not a JSON object with a 'pages' list.\n"
            continue

        R.repair_lesson(lesson, language=language)
        findings = A.audit_lesson(lesson, language=language, track=track)
        if best is None or len(A.blocking(findings)) < len(A.blocking(best_findings)):
            best, best_findings = lesson, findings

        if not A.blocking(findings):
            return LessonResult(lesson=lesson, findings=findings, attempts=attempt + 1,
                                cost=spent)
        correction = _correction_note(findings)

    return LessonResult(lesson=best, findings=best_findings, attempts=2, cost=spent)


# ── Assessments ──────────────────────────────────────────────────────────────

def _clean_item(raw: Any, *, track: str) -> Optional[Dict[str, Any]]:
    """Normalise one generated item into the wire shape, or drop it."""
    if not isinstance(raw, dict):
        return None
    stem = str(raw.get("prompt") or "").strip()
    answer = str(raw.get("answer") or "").strip()
    raw_d = raw.get("distractors")
    distractors: List[str] = []
    for value in (raw_d if isinstance(raw_d, list) else []):
        text = str(value).strip()
        if text and text.casefold() != answer.casefold() and \
                text.casefold() not in [d.casefold() for d in distractors]:
            distractors.append(text)
    if not (stem and answer and len(distractors) >= 3):
        return None
    distractors = distractors[:3]

    item: Dict[str, Any] = {
        "id": _uid(), "type": "mcq", "prompt": stem, "answer": answer,
        "distractors": distractors, "options": [answer] + distractors,
        "evidence": str(raw.get("evidence") or "").strip()[:180],
        "material_section": str(raw.get("material_section") or "").strip()[:100],
        "cognitive_task": str(raw.get("cognitive_task") or "").strip()[:40],
    }

    # Assessments are bilingual in their instructional metadata even though the
    # stem/options/key stay entirely in the taught language. Keep the two tracks
    # separate: the old single-track normaliser copied Turkish into the generic
    # English aliases, which is how the English reader ended up showing Turkish.
    why_en = str(raw.get("why") or raw.get("why_en") or "").strip()
    why_tr = str(raw.get("why_tr") or "").strip()
    if why_en:
        item["why"] = why_en
    if why_tr:
        item["why_tr"] = why_tr

    gloss_en = str(raw.get("translation_en") or raw.get("translation") or "").strip()
    gloss_tr = str(raw.get("translation_tr") or "").strip()
    if gloss_en:
        item["translation"] = gloss_en
        item["translation_en"] = gloss_en
    if gloss_tr:
        item["translation_tr"] = gloss_tr
    return item


def _shuffle_options(items: Sequence[Dict[str, Any]], seed: Optional[int] = None) -> None:
    import random
    rng = random.Random(seed)
    for item in items:
        options = list(item.get("options") or [])
        rng.shuffle(options)
        item["options"] = options


def generate_assessment(*, title: str, content: str, count: int, language: str, level: str,
                        track: str = "tr", ledger: Optional[B.BuildLedger] = None,
                        emphasis: str = "", already_asked: Sequence[str] = (),
                        model: str = "", temperature: float = 0.75,
                        seed: Optional[int] = None) -> AssessmentResult:
    """`count` publishable items, with two retries aimed only at the remaining shortfall."""
    ledger = ledger or B.BuildLedger(label=f"{language} {level}")
    system = P.build_assessment_system(language=language, level=level, track=track)
    system_tokens = estimate_tokens(system)

    kept: List[Dict[str, Any]] = []
    all_findings: List[A.Finding] = []
    spent = 0.0
    correction = ""
    asked = list(already_asked)

    for attempt in range(3):
        shortfall = count - len(kept)
        if shortfall <= 0:
            break
        request = B.overproduce(shortfall)
        ceiling = B.assessment_output_ceiling(request)
        user = P.build_assessment_user(
            title=title, content=content, count=request, language=language, track=track,
            emphasis=emphasis, already_asked=asked, request_id=_uid())
        if correction:
            user = user + correction

        input_tokens = system_tokens + estimate_tokens(user)
        cached = system_tokens if attempt or ledger.entries else 0
        try:
            ledger.require(stage="assessment", input_tokens=input_tokens,
                           output_tokens=ceiling, cached_tokens=cached)
        except B.BudgetExceeded as exc:
            return AssessmentResult(items=kept, findings=all_findings, attempts=attempt,
                                    cost=spent, error="" if kept else str(exc))

        response = T.call_model(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=ceiling, temperature=temperature, model=model or B.MODEL)
        spent += ledger.record(stage="assessment", subject=title, wasted=not response.ok,
                               input_tokens=response.input_tokens or input_tokens,
                               output_tokens=response.output_tokens,
                               cached_tokens=response.cached_tokens,
                               reported_cost=response.cost)
        if not response.ok:
            # A transient failure on one attempt is not a reason to throw away
            # valid items already kept. Continue while a bounded retry remains.
            if attempt >= 2:
                return AssessmentResult(items=kept, findings=all_findings,
                                        attempts=attempt + 1, cost=spent,
                                        error="" if kept else response.error)
            continue

        payload = response.data
        raw_items = payload if isinstance(payload, list) else (
            payload.get("items") or payload.get("data") or payload.get("questions") or [])

        rejected: List[A.Finding] = []
        for raw in raw_items:
            if len(kept) >= count:
                break
            item = _clean_item(raw, track=track)
            if item is None:
                continue
            R.repair_item(item, language=language)
            findings = A.audit_item(item, language=language, track=track)
            blocking = A.blocking(findings)
            if blocking:
                rejected.extend(blocking)
                continue
            if any(_same_target(item, k) for k in kept):
                continue
            kept.append(item)
            asked.append(item["prompt"])
            all_findings.extend(f for f in findings if f.severity != A.BLOCK)

        if len(kept) >= count:
            break
        correction = _correction_note(rejected)

    _shuffle_options(kept, seed)
    return AssessmentResult(items=kept[:count], findings=all_findings, attempts=min(3, attempt + 1), cost=spent)


def _same_target(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Two items assessing the same thing through the same route."""
    import difflib
    if str(a.get("answer", "")).casefold() == str(b.get("answer", "")).casefold():
        return True
    ratio = difflib.SequenceMatcher(
        None, str(a.get("prompt", "")).casefold(), str(b.get("prompt", "")).casefold()).ratio()
    return ratio > 0.86


# ── A whole classroom ────────────────────────────────────────────────────────

class CourseResult:
    __slots__ = ("plan", "lessons", "unit_assessments", "ledger", "findings", "errors")

    def __init__(self, plan, ledger):
        self.plan = plan
        self.ledger = ledger
        self.lessons: Dict[str, Dict[str, Any]] = {}
        self.unit_assessments: Dict[str, List[Dict[str, Any]]] = {}
        self.findings: List[A.Finding] = []
        self.errors: List[str] = []

    @property
    def cost(self) -> float:
        return self.ledger.spent

    @property
    def complete(self) -> bool:
        return bool(self.plan) and len(self.lessons) == self.plan.lesson_count and not self.errors


def build_course(*, language: str, level: str, track: str = "tr",
                 ceiling_usd: float = B.CLASSROOM_CEILING_USD, institution: str = "",
                 unit_items: int = 10, model: str = "",
                 progress=None) -> "CourseResult":
    """Plan a course, write every lesson, and close each unit with an assessment.

    The whole build shares ONE ledger, so the sixty-cent ceiling applies to the
    classroom rather than to each call inside it, and a lesson that needed a
    second attempt is paid for out of the same allowance as everything else.
    That is the only arrangement under which the limit means anything: a
    per-call budget with no total is how a build reaches eleven dollars one
    affordable call at a time.
    """
    from services.authoring import blueprint as BP

    ledger = B.BuildLedger(ceiling_usd, model=model or B.MODEL,
                           label=f"{language} {level} ({track})")
    plan = BP.plan_course(language=language, level=level, track=track, ledger=ledger,
                          model=model)
    result = CourseResult(plan, ledger)

    projected = B.project_classroom_cost(lessons=plan.lesson_count,
                                         units=len(plan.units),
                                         items_per_unit=unit_items,
                                         model=model or B.MODEL)
    if projected["total"] > ledger.remaining:
        result.errors.append(
            f"plan of {plan.lesson_count} lessons projects ${projected['total']:.3f}, "
            f"over the ${ledger.remaining:.3f} left")
        return result

    total = plan.lesson_count or 1
    done = 0
    for unit in plan.units:
        for topic in unit.topics:
            outcome = generate_lesson(
                topic=topic.title, topic_type=topic.type, language=language, level=level,
                track=track, ledger=ledger, taught_so_far=plan.taught_before(topic),
                institution=institution, model=model)
            done += 1
            if progress:
                progress(int(done * 80 / total), topic.title)
            if outcome.lesson:
                result.lessons[topic.id] = outcome.lesson
                result.findings.extend(outcome.findings)
            else:
                result.errors.append(f"{topic.title}: {outcome.error or 'no lesson'}")

        if unit.topics and ledger.remaining > 0:
            material = _unit_material(result, unit, track)
            if material:
                items = generate_assessment(
                    title=unit.title, content=material, count=unit_items, language=language,
                    level=level, track=track, ledger=ledger, model=model)
                result.unit_assessments[unit.title] = items.items
                result.findings.extend(items.findings)

    if progress:
        progress(100, "done")
    return result


def _unit_material(result: "CourseResult", unit, track: str) -> str:
    """The evidence a unit assessment may draw on: that unit's lessons, compacted."""
    suffix = "_tr" if str(track).casefold().startswith("tr") else ""
    parts: List[str] = []
    for topic in unit.topics:
        lesson = result.lessons.get(topic.id)
        if not isinstance(lesson, dict):
            continue
        lines = [f"[TOPIC: {topic.title}]"]
        for page in (lesson.get("pages") or [])[:8]:
            if not isinstance(page, dict):
                continue
            terms = [str(i.get("term") or "").strip()
                     for i in (page.get("items") or []) if isinstance(i, dict)]
            terms = [t for t in terms if t][:10]
            if terms:
                lines.append("  vocabulary: " + ", ".join(terms))
            for rule in (page.get("rules") or [])[:3]:
                if isinstance(rule, dict):
                    text = str(rule.get(f"rule{suffix}") or rule.get("rule") or "").strip()
                    example = str(rule.get("example") or "").strip()
                    if text:
                        lines.append(f"  rule: {text[:150]}" +
                                     (f" — e.g. '{example[:70]}'" if example else ""))
        if len(lines) > 1:
            parts.append("\n".join(lines))
    return "\n\n".join(parts)
