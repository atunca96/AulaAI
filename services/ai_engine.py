"""The API the rest of the product calls. Generation itself lives in `authoring`.

This file used to be 4,139 lines and contained the whole generation system: two
prompt builders, a validator, a distractor supplementer, a claim verifier, a
lesson synthesiser, a Turkish syntax healer, a cognate detector, a curriculum
planner, a cost estimator and the HTTP client, with `ai_generate_questions`
alone running to a thousand lines inside a single function.

Everything that authors or judges content now lives in `services/authoring/`,
where each concern is one module with its own tests. What remains here is what
the rest of the product actually imports: a stable set of function names, with
the signatures `server.py`, `content_engine.py` and `worker.py` already pass,
delegating to the new core.

Keeping the names is deliberate. A rebuild that also renamed every call site
would have mixed two kinds of risk — "is the new generator good?" and "did we
wire it up correctly?" — into one deployment, and only one of those is worth
taking at a time.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from services.authoring import audit as _audit
from services.authoring import blueprint as _blueprint
from services.authoring import budget as _budget
from services.authoring import engine as _engine
from services.authoring import publish as _publish
from services.authoring import transport as _transport

__all__ = [
    "MODEL", "is_ai_available", "generate_full_lesson", "ai_generate_questions",
    "generate_unit_assessment", "ai_generate_activity", "ai_generate_activity_batch",
    "ai_generate_curriculum", "ai_explain_word", "ai_explain_activity",
    "ai_grade_open_response", "ai_generate_report_insights", "detect_language",
    "save_blueprint_cache", "delete_blueprint_cache", "list_blueprint_cache",
]

# The model, in one place. Overridable per deployment, but the default is the
# model this system was designed, priced and tested against.
MODEL = os.getenv("AULAAI_MODEL", _budget.MODEL)
TERRA_REVIEW_MODEL = "openai/gpt-5.6-terra"

_LOG = "pipeline.log"


def _log(message: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
    print(line)
    try:
        with open(_LOG, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def is_ai_available() -> bool:
    return _transport.available()


def _call_ai(messages: List[Dict[str, Any]], model: str = "", max_tokens: int = 1000,
             temperature: float = 0.7, json_mode: bool = True, **_ignored) -> Optional[Dict]:
    """The small-call path kept for callers that ask the model a one-off question.

    Lesson and assessment generation do NOT come through here — they go through
    `authoring.engine`, which audits what comes back. This exists for the short
    utility calls (explain a word, grade an answer) where there is no lesson to
    audit and the answer is shown to one person once.
    """
    response = _transport.call_model(messages, max_tokens=max_tokens,
                                     temperature=temperature, model=model or MODEL,
                                     cache_system=False)
    return response.data if response.ok else None


def detect_language(text: str, hint: str = "") -> str:
    result = _call_ai(
        [{"role": "user",
          "content": f"Identify the language of this text. Hint: {hint}\n\n{str(text)[:800]}"
                     '\n\nReturn only: {"language": "<English name>"}'}],
        max_tokens=60, temperature=0.0)
    return (result or {}).get("language", "Unknown")


# ── Lessons ──────────────────────────────────────────────────────────────────

def generate_full_lesson(topic, topic_type, language, count=6, level="A1", source_text=None,
                         material_language="tr", unit_index=None, unit_total=None,
                         topics_completed=0, taught_so_far=(), ledger=None):
    """One publication-ready lesson, or a review notice if it could not be made.

    The signature is the one the callers already pass. `count` is read as the
    page target and `topics_completed` is unused — it was a progress counter the
    old retry ladder needed and the new one does not.
    """
    started = time.perf_counter()
    _log(f"[LESSON] '{topic}' ({topic_type}) {language} {level} -> {MODEL}")

    result = _engine.generate_lesson(
        topic=str(topic), topic_type=str(topic_type or "vocabulary"), language=str(language),
        level=str(level or "A1"), track=str(material_language or "tr"),
        ledger=ledger, source_text=str(source_text or ""), taught_so_far=taught_so_far,
        pages=max(3, min(8, int(count or 5))), model=MODEL)

    # Terra is intentionally NOT the bulk generator. At 30 topics it measured
    # about $2/classroom by itself. Use it only as a narrow rescue path when the
    # cheap primary model cannot produce a clean lesson after its bounded retry.
    # That preserves the quality escape hatch without paying Terra rates thirty
    # times on every classroom.
    if (str(os.getenv("AULAAI_TERRA_RESCUE", "0")).strip().lower() in
            ("1", "true", "on", "yes")
            and _audit.blocking(result.findings) and not result.lesson):
        rescue = _engine.generate_lesson(
            topic=str(topic), topic_type=str(topic_type or "vocabulary"), language=str(language),
            level=str(level or "A1"), track=str(material_language or "tr"),
            ledger=None, source_text=str(source_text or ""), taught_so_far=taught_so_far,
            pages=max(3, min(8, int(count or 5))), model=TERRA_REVIEW_MODEL)
        if rescue.lesson and not _audit.blocking(rescue.findings):
            result = rescue

    blocking = _audit.blocking(result.findings)
    _log(f"[LESSON] '{topic}' attempts={result.attempts} cost=${result.cost:.4f} "
         f"blocking={len(blocking)} in {time.perf_counter() - started:.1f}s")
    if blocking:
        _log("[LESSON] unresolved: " + json.dumps(_audit.summarise(blocking), ensure_ascii=False))

    if not result.lesson:
        return _review_notice(topic, language, level, material_language,
                              result.error or "generation failed")
    lesson = result.lesson
    lesson.setdefault("_generated_by", MODEL)
    if blocking:
        lesson["_quality_findings"] = [f.as_dict() for f in blocking[:20]]
    return lesson


def _review_notice(topic, language, level, material_language, reason: str) -> Dict[str, Any]:
    """What a learner sees when a lesson genuinely could not be produced.

    Deliberately honest and deliberately small. The old pipeline synthesised a
    plausible-looking lesson from vocabulary lists when generation failed, which
    published material nobody had checked under the same styling as material
    that had been. A visible gap is a better product than an invisible fake.
    """
    is_tr = str(material_language or "tr").casefold().startswith("tr")
    title = f"{topic}" if not is_tr else f"{topic}"
    body = ("Bu ders şu anda hazırlanamadı ve incelenmek üzere işaretlendi. "
            "Lütfen daha sonra yeniden oluşturun."
            if is_tr else
            "This lesson could not be prepared and has been flagged for review. "
            "Please regenerate it later.")
    key = "title_tr" if is_tr else "title"
    text_key = "text_tr" if is_tr else "text"
    return {"pages": [{"type": "overview", key: title, text_key: body}],
            "_review_required": True, "_reason": reason}


def synthesize_substantive_lesson(topic, topic_type, language, level="A1", source_text=None,
                                  material_language="tr"):
    """Retained for callers that expect it; now a review notice.

    It used to assemble a lesson out of whatever vocabulary was to hand when the
    model failed. That is the one behaviour a quality rebuild cannot keep: it
    produced unreviewed material that looked exactly like reviewed material.
    """
    return _review_notice(topic, language, level, material_language, "synthesis requested")


# ── Assessments ──────────────────────────────────────────────────────────────

def ai_generate_questions(topic_title, topic_type, topic_content, language, count=10,
                          level="A1", existing_questions=None, is_pdf_source=False,
                          is_quiz=False, source_text_override=None, model_override=None,
                          material_language="en", generation_seed=None, focus_directive=None,
                          timing_ctx=None, scope=None, progression=None, coverage_plan="",
                          forbidden_terms=None, ledger=None, allow_partial=False, **_ignored):
    """`count` publishable assessment items.

    Ordinary quizzes remain all-or-nothing. Unit assessments may opt into a
    partial return so their already-published lesson MCQs can deterministically
    fill a tiny shortfall instead of deleting nine valid questions because the
    model produced nine rather than ten.
    """
    started = time.perf_counter()
    wanted = int(count or 10)
    content = _material_for_assessment(topic_content, source_text_override)
    if not content.strip():
        _log(f"[ASSESS] '{topic_title}' has no usable source material")
        return []

    asked = [str(q.get("prompt") or "") for q in (existing_questions or [])
             if isinstance(q, dict)]

    result = _engine.generate_assessment(
        title=str(topic_title), content=content, count=wanted, language=str(language),
        level=str(level or "A1"), track=str(material_language or "tr"), ledger=ledger,
        emphasis=_emphasis(focus_directive), already_asked=asked,
        model=model_override or MODEL, seed=generation_seed)

    if isinstance(timing_ctx, dict):
        timing_ctx["total_elapsed"] = time.perf_counter() - started
        timing_ctx["total_cost"] = result.cost

    _log(f"[ASSESS] '{topic_title}' req={wanted} got={len(result.items)} "
         f"attempts={result.attempts} cost=${result.cost:.4f}")
    if len(result.items) < wanted:
        if allow_partial and result.items:
            _log(f"[ASSESS] '{topic_title}' short of {wanted}; returning {len(result.items)} "
                 "validated item(s) for deterministic unit completion")
            return result.items
        _log(f"[ASSESS] '{topic_title}' short of {wanted}; returning nothing rather than a partial set")
        return []
    return result.items


def _emphasis(focus_directive) -> str:
    return {
        "focus_grammar": "structure and form: the rules and contrasts the material states",
        "focus_lexicon": "lexis, idiom and situational reaction, not verb morphology",
    }.get(str(focus_directive or ""), "")


def _material_for_assessment(topic_content: Any, override: Any = None) -> str:
    """Flatten whatever the caller has into evidence the generator can assess.

    Accepts the three shapes the product stores: a lesson dict with `pages`, a
    multi-topic review dict with `topics`, or raw text.
    """
    if override:
        return str(override)[:8000]
    if isinstance(topic_content, str):
        return topic_content[:8000]
    if not isinstance(topic_content, dict):
        return str(topic_content or "")[:8000]

    if "_preassembled_content_str" in topic_content:
        return str(topic_content["_preassembled_content_str"])[:8000]

    parts: List[str] = []
    if isinstance(topic_content.get("topics"), list):
        for index, topic in enumerate(topic_content["topics"][:8], 1):
            if not isinstance(topic, dict):
                continue
            lines = [f"[MODULE {index}: {topic.get('title', '')}]"]
            vocab = [str(v) for v in (topic.get("key_vocab") or [])[:10] if str(v).strip()]
            grammar = [str(g) for g in (topic.get("key_grammar") or [])[:4] if str(g).strip()]
            if grammar:
                lines.append("  rules: " + " | ".join(grammar))
            if vocab:
                lines.append("  vocabulary: " + ", ".join(vocab))
            parts.append("\n".join(lines))
        return "\n\n".join(parts)[:8000]

    for index, page in enumerate(topic_content.get("pages") or [], 1):
        if not isinstance(page, dict):
            continue
        title = page.get("title_tr") or page.get("title") or f"Part {index}"
        lines = [f"[PART {index}: {title}]"]
        for rule in (page.get("rules") or [])[:4]:
            if isinstance(rule, dict):
                text = str(rule.get("rule_tr") or rule.get("rule") or "").strip()
                example = str(rule.get("example") or "").strip()
                if text:
                    lines.append(f"  [RULE] {text[:170]}" +
                                 (f" — e.g. '{example[:80]}'" if example else ""))
        for comparison in (page.get("comparisons") or [])[:3]:
            if isinstance(comparison, dict) and str(comparison.get("target") or "").strip():
                note = str(comparison.get("note_tr") or comparison.get("note") or "").strip()
                lines.append(f"  [CONTRAST] {comparison['target']}" +
                             (f": {note[:120]}" if note else ""))
        terms: List[str] = []
        for item in (page.get("items") or [])[:14]:
            if isinstance(item, dict) and str(item.get("term") or "").strip():
                gloss = str(item.get("translation_tr") or item.get("translation") or "").strip()
                example = str(item.get("example") or "").strip()
                terms.append(f"{item['term']}" + (f" ({gloss})" if gloss else "") +
                             (f" — '{example[:70]}'" if example else ""))
        if terms:
            lines.append("  vocabulary:\n    " + "\n    ".join(terms))
        text = str(page.get("text_tr") or page.get("text") or "").strip()
        if text and len(lines) == 1:
            lines.append("  " + text[:400])
        if len(lines) > 1:
            parts.append("\n".join(lines))
    return "\n\n".join(parts)[:8000]


def generate_unit_assessment(unit_title, unit_topics, language, level="A1",
                             material_language="tr", unit_index=None, unit_total=None,
                             model_override=None, timing_ctx=None, count=10, ledger=None):
    """Close a unit with exactly `count` validated questions.

    The model authors the assessment first. If only a tiny shortfall survives,
    reuse clean MCQ pages that were already generated and published inside this
    unit's lessons. Those questions are grounded in exactly the same unit and
    cross the same audit boundary, so completion adds no invented material and
    needs no extra paid call.
    """
    parts: List[str] = []
    lesson_mcqs: List[Dict[str, Any]] = []

    for topic in (unit_topics or []):
        if not isinstance(topic, dict):
            continue
        content = topic.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except Exception:
                content = {}
        if not isinstance(content, dict):
            continue

        block = _material_for_assessment(content)
        if block.strip():
            parts.append(f"=== {topic.get('title', '')} ===\n{block}")

        for page in (content.get("pages") or []):
            if not isinstance(page, dict) or str(page.get("type") or "").casefold() != "mcq":
                continue
            prompt = str(page.get("prompt") or page.get("question") or page.get("stem") or "").strip()
            answer = str(page.get("answer") or "").strip()
            options = [str(v).strip() for v in (page.get("options") or page.get("choices") or [])
                       if str(v).strip()]
            if answer and answer not in options:
                options.insert(0, answer)
            # Preserve order but remove exact duplicates.
            distinct: List[str] = []
            for value in options:
                if value.casefold() not in [x.casefold() for x in distinct]:
                    distinct.append(value)
            if not prompt or not answer or len(distinct) != 4 or answer not in distinct:
                continue
            raw = {
                "prompt": prompt,
                "answer": answer,
                "distractors": [v for v in distinct if v != answer][:3],
                "evidence": str(page.get("evidence") or "").strip(),
                "material_section": str(topic.get("title") or unit_title or "").strip(),
                "cognitive_task": str(page.get("cognitive_task") or "lesson_review").strip(),
                "why": str(page.get("why") or page.get("explanation") or "").strip(),
                "why_tr": str(page.get("why_tr") or page.get("explanation_tr") or "").strip(),
                "translation_en": str(page.get("translation_en") or page.get("translation") or "").strip(),
                "translation_tr": str(page.get("translation_tr") or "").strip(),
            }
            item = _engine._clean_item(raw, track=material_language)
            if item is None:
                continue
            from services.authoring import repair as _repair
            _repair.repair_item(item, language=language)
            findings = _audit.audit_item(item, language=language, track=material_language)
            if not _audit.blocking(findings):
                lesson_mcqs.append(item)

    if not parts:
        return []

    questions = ai_generate_questions(
        unit_title, "review", {"_preassembled_content_str": "\n\n".join(parts)[:9000]},
        language, count=count, level=level, material_language=material_language,
        model_override=model_override, timing_ctx=timing_ctx, ledger=ledger,
        allow_partial=True)

    if len(questions) >= count:
        return questions[:count]

    for candidate in lesson_mcqs:
        if len(questions) >= count:
            break
        if any(_engine._same_target(candidate, existing) for existing in questions):
            continue
        questions.append(candidate)

    if len(questions) < count:
        _log(f"[UNIT-ASSESS] '{unit_title}' still short after lesson-MCQ completion: "
             f"{len(questions)}/{count}")
    else:
        _log(f"[UNIT-ASSESS] '{unit_title}' completed to {count} with validated lesson MCQs")
    return questions[:count]


def ai_generate_activity_batch(topic_title, topic_type, topic_content, language, count=10,
                               level="A1", existing_questions=None, is_pdf_source=False,
                               model_override=None, material_language="en", **_ignored):
    return ai_generate_questions(
        topic_title, topic_type, topic_content, language, count=count, level=level,
        existing_questions=existing_questions, model_override=model_override,
        material_language=material_language)


ai_generate_activity = ai_generate_activity_batch


# ── Curriculum ───────────────────────────────────────────────────────────────

def _monolingual_rows(chapters) -> int:
    """How many units or topics lack a real title in one of the two columns.

    A row counts as monolingual when either title is empty or the two are the
    same string — the second being the case that made every row look
    untranslated and sent the whole curriculum through a translation pass it did
    not need.
    """
    gaps = 0
    for chapter in chapters or []:
        if not isinstance(chapter, dict):
            continue
        rows = [chapter] + [t for t in (chapter.get("topics") or []) if isinstance(t, dict)]
        for row in rows:
            english = str(row.get("title") or "").strip()
            turkish = str(row.get("title_tr") or "").strip()
            if not english or not turkish or english.casefold() == turkish.casefold():
                gaps += 1
    return gaps


def ai_generate_curriculum(language, level, prompt_extra=""):
    """The course structure, in the chapter shape the server stores."""
    started = time.perf_counter()
    ledger = _budget.BuildLedger(label=f"curriculum {language} {level}")
    plan = _blueprint.plan_curriculum_draft(
        language=str(language), level=str(level or "A1"), track="tr",
        extra=str(prompt_extra or ""))
    chapters: List[Dict[str, Any]] = []
    for number, unit in enumerate(plan.units, 1):
        chapters.append({
            "number": number,
            "title": unit.title,
            "title_tr": unit.title_tr,
            "topics": [{"title": t.title, "title_tr": t.title_tr, "type": t.type}
                       for t in unit.topics],
        })

    # The planner emits both titles now, so the translation pass has nothing to
    # do and is skipped. It used to run on every build: filling `title` and
    # `title_tr` with the SAME string made every row look untranslated, which
    # triggered a batch translation call per chapter and per topic — most of the
    # 45 seconds a curriculum took — and where a topic's translation did not
    # come back, the editor showed Turkish under ENGLISH UNIT NAME with an empty
    # box beside it. It stays as a repair for a model that answers with a title
    # missing, which is the only case it can still help with.
    gaps = _monolingual_rows(chapters)
    if gaps:
        try:
            from services.curriculum_translator import ensure_bilingual_curriculum
            _log(f"[CURRICULUM] {gaps} row(s) came back monolingual; translating the gaps")
            chapters = ensure_bilingual_curriculum(chapters)
        except Exception as exc:
            _log(f"[CURRICULUM] bilingual repair skipped: {exc}")
    for chapter in chapters:
        if isinstance(chapter, dict):
            chapter["_aulaai_bilingual_healed"] = True
    _log(f"[CURRICULUM] {language} {level} units={len(chapters)} "
         f"topics={sum(len(ch.get('topics') or []) for ch in chapters)} "
         f"source={plan.notes or 'model'} "
         f"in {time.perf_counter() - started:.1f}s")
    return chapters


# ── Blueprint cache ──────────────────────────────────────────────────────────

def _blueprint_dir() -> str:
    base = os.getenv("AULAAI_DATA_DIR") or os.path.join(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))), "data")
    path = os.path.join(base, "blueprints")
    os.makedirs(path, exist_ok=True)
    return path


def _blueprint_path(language, level) -> str:
    safe = "".join(c for c in f"{language}_{level}" if c.isalnum() or c in "_-").lower()
    return os.path.join(_blueprint_dir(), f"{safe}.json")


def _load_blueprint_chapters(language, level, require_four=True):
    path = _blueprint_path(language, level)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            chapters = (json.load(handle) or {}).get("chapters") or []
    except Exception:
        return None
    if not chapters or (require_four and len(chapters) < 4):
        return None
    return chapters


def save_blueprint_cache(language, level, chapters) -> bool:
    try:
        from services.curriculum_translator import ensure_bilingual_curriculum
        clean = ensure_bilingual_curriculum(chapters)
        with open(_blueprint_path(language, level), "w", encoding="utf-8") as handle:
            json.dump({"chapters": clean}, handle, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def delete_blueprint_cache(language, level) -> bool:
    try:
        os.remove(_blueprint_path(language, level))
        return True
    except Exception:
        return False


def list_blueprint_cache() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        for name in sorted(os.listdir(_blueprint_dir())):
            if not name.endswith(".json"):
                continue
            path = os.path.join(_blueprint_dir(), name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    chapters = (json.load(handle) or {}).get("chapters") or []
            except Exception:
                chapters = []
            out.append({"key": name[:-5], "units": len(chapters)})
    except Exception:
        pass
    return out


# ── Short utility calls ──────────────────────────────────────────────────────

def ai_explain_word(word, language, context=None, material_language="en"):
    inst = "Turkish" if str(material_language).startswith("tr") else "English"
    return _call_ai([
        {"role": "system",
         "content": f"You are a {language} teacher. You explain a term to one student, "
                    f"briefly, in {inst}."},
        {"role": "user",
         "content": f"Explain the {language} term '{word}'."
                    f"\nContext: {context or '(none)'}\n\n"
                    f"Write 'explanation', 'usage' and 'tip' entirely in {inst}; only the "
                    f"term itself stays in {language}. Two or three sentences in total.\n"
                    'Return only: {"explanation": "...", "usage": "...", "tip": "..."}'}],
        max_tokens=420, temperature=0.3)


def ai_explain_activity(prompt, correct_answer, student_answer, language,
                        material_language="en"):
    inst = "Turkish" if str(material_language).startswith("tr") else "English"
    clean = str(language).split("(")[0].strip()
    return _call_ai([
        {"role": "system",
         "content": f"You are a {clean} teacher explaining one mistake to one student. "
                    f"Every explanatory sentence is in {inst}. You may quote {clean} words, "
                    f"but never write a whole sentence in {clean}. Two or three sentences."},
        {"role": "user",
         "content": f"Question: {prompt}\nCorrect: {correct_answer}\n"
                    f"The student answered: {student_answer}\n\n"
                    f"Explain the mistake and the correct reasoning.\n"
                    'Return only: {"explanation": "..."}'}],
        max_tokens=420, temperature=0.3)


def ai_grade_open_response(question, student_answer, correct_answer):
    result = _call_ai([
        {"role": "user",
         "content": f"Grade this short answer.\nQuestion: {question}\n"
                    f"Expected: {correct_answer}\nStudent: {student_answer}\n"
                    'Return only: {"score": <0.0-1.0>, "feedback": "<one sentence>"}'}],
        max_tokens=160, temperature=0.0)
    if not result:
        return 0.0, ""
    try:
        return float(result.get("score", 0.0)), str(result.get("feedback", ""))
    except Exception:
        return 0.0, ""


def ai_generate_report_insights(cohort_data):
    result = _call_ai([
        {"role": "user",
         "content": "Three actionable teaching insights from this cohort's performance. "
                    "Be specific about what to reteach.\n"
                    f"{json.dumps(cohort_data, ensure_ascii=False)[:4000]}\n"
                    'Return only: {"explanation": "..."}'}],
        max_tokens=520, temperature=0.4)
    return (result or {}).get("explanation", "Insufficient data for insights.")


# ── Compatibility shims ──────────────────────────────────────────────────────
# Named by callers that have not moved yet. Each is one line and points at where
# the behaviour now lives, so the next reader does not go looking in this file.

def _is_substantive_lesson(data: Any) -> bool:
    if not isinstance(data, dict) or data.get("_review_required"):
        return False
    pages = data.get("pages")
    return isinstance(pages, list) and len(pages) >= 2


def is_transparent_cognate(word_a: str, word_b: str, threshold: float = 0.65) -> bool:
    import difflib
    a, b = str(word_a or "").casefold(), str(word_b or "").casefold()
    if not a or not b:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= threshold


def _sanitize_blank_translations(prompt, answer, t_en, t_tr, why="", why_tr="",
                                 topic_content=None):
    """Keep a gap a gap in both glosses. `audit.py` reports when one is lost."""
    import re as _re
    gap = _re.compile(r"[_＿﹍﹏‗]{2,}")
    if not gap.search(str(prompt or "")):
        return t_en, t_tr
    out = []
    for gloss in (t_en, t_tr):
        text = str(gloss or "")
        if text and not gap.search(text) and answer:
            text = text.replace(str(answer), "_____")
        out.append(text)
    return out[0], out[1]
