"""Assessment Engine V2.

A clean, assessment-only pipeline. It reads already-generated lesson content, plans
source-backed learning objectives first, then writes exactly one MCQ per objective.
Lesson/material generation is never called or mutated here.
"""

import json
import math
import re
import threading
import unicodedata
from difflib import SequenceMatcher

from services.ai_engine import _call_ai, MODEL_STRUCTURAL
from services.assessment_evidence_balance import _build_balanced_evidence

_GEN_CHUNK_SIZE = 8
_MAX_CHUNK_ATTEMPTS = 2
_HISTORY_LIMIT = 80
_HISTORY_LOCK = threading.Lock()
_HISTORY = {}


def _norm(value):
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    return " ".join(
        "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in text if not unicodedata.combining(ch)).split()
    )


def _tokens(value):
    return {x for x in _norm(value).split() if len(x) >= 2}


def _overlap(a, b):
    a, b = _tokens(a), _tokens(b)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _near_repeat(q1, q2):
    p1, p2 = _norm(q1.get("prompt")), _norm(q2.get("prompt"))
    if not p1 or not p2:
        return False
    if p1 == p2 or SequenceMatcher(None, p1, p2).ratio() >= 0.88:
        return True
    a1, a2 = _norm(q1.get("answer")), _norm(q2.get("answer"))
    if a1 and a1 == a2 and _overlap(p1, p2) >= 0.45:
        return True
    return False


def _history_key(language, level, topics):
    topic_part = ",".join(str(t.get("id", "")) for t in topics)
    return f"{_norm(language)}|{_norm(level)}|{topic_part}"


def _get_history(key):
    with _HISTORY_LOCK:
        return list(_HISTORY.get(key, []))


def _remember(key, questions):
    with _HISTORY_LOCK:
        history = _HISTORY.setdefault(key, [])
        for q in questions:
            history.append({
                "objective_key": q.get("objective_key", ""),
                "prompt": q.get("prompt", ""),
                "answer": q.get("answer", ""),
            })
        if len(history) > _HISTORY_LIMIT:
            del history[:-_HISTORY_LIMIT]


def _topic_evidence(topics):
    blocks = []
    for topic in topics:
        content = topic.get("content") or {}
        pack = _build_balanced_evidence(content)
        if not pack:
            try:
                pack = json.dumps(content, ensure_ascii=False)[:5000]
            except Exception:
                pack = str(content)[:5000]
        if not pack:
            continue
        blocks.append(
            f"=== TOPIC id={topic.get('id')} | title={topic.get('title', '')} | type={topic.get('type', '')} ===\n{pack}"
        )
    return "\n\n".join(blocks)[:14000]


def _recent_text(previous_questions, history):
    rows = []
    for q in list(previous_questions or [])[-24:] + list(history or [])[-24:]:
        if not isinstance(q, dict):
            continue
        objective = q.get("objective_key") or q.get("_objective_key") or ""
        prompt = str(q.get("prompt", "")).strip()
        answer = str(q.get("answer", "")).strip()
        if objective or prompt or answer:
            rows.append(f"- objective={objective!s} | prompt={prompt[:180]!r} | answer={answer[:80]!r}")
    return "\n".join(rows[-32:])


def _parse_list(result, keys):
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in keys:
            value = result.get(key)
            if isinstance(value, list):
                return value
    return []


def _plan_objectives(topics, language, level, requested_count, evidence, previous_questions, history):
    max_same_mode = max(2, int(math.ceil(requested_count * 0.30)))
    recent = _recent_text(previous_questions, history)
    topic_ids = [str(t.get("id")) for t in topics]

    system = f"""You are AulaAI Assessment Planner V2.
Plan exactly {requested_count} source-grounded assessment objectives for a {level} learner of {language}.

RULES:
- Use only the supplied lesson evidence. Never invent a target from the topic title alone.
- Each objective must test useful language competence: meaning/use, grammar, form-function, dialogue comprehension, register/pragmatics, pronunciation when genuinely taught, contextual interpretation, or another source-backed skill.
- Do not use arithmetic, general knowledge, chronology, trivia, etymology, historical roots, abstract linguistic terminology, letter-count/string trivia, or visual spelling tricks unless that is explicitly a central lesson objective and CEFR-appropriate.
- Different words/numbers/examples are not automatically different objectives if the learner performs the same lookup operation.
- However, when a user requests many questions, one broad lesson area may yield multiple legitimate sub-objectives if they test different forms, uses, contrasts, contexts, production/recognition skills, or communicative functions.
- Keep objective keys unique within this plan. Prefer objectives not seen in RECENT HISTORY when alternatives exist, but do not sacrifice quality merely to avoid a broad area used before.
- Vary question_mode. No one question_mode should normally exceed {max_same_mode} of {requested_count} objectives when the source offers alternatives.
- topic_id must be one of: {', '.join(topic_ids)}.

Return JSON only:
{{"objectives":[{{"id":"o1","key":"stable-lowercase-key","topic_id":"...","skill":"...","target":"one precise teachable point","evidence":"short supporting source fact","question_mode":"situational|dialogue|form-choice|meaning|contrast|completion|comprehension|other"}}]}}
Return exactly {requested_count} objectives."""

    user = f"SOURCE EVIDENCE:\n{evidence}\n\nRECENT HISTORY (avoid true repeats; broad reuse is allowed only for a genuinely different sub-objective):\n{recent or '(none)'}"
    result = _call_ai(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=MODEL_STRUCTURAL,
        max_tokens=1800,
        temperature=0.35,
        json_mode=True,
        allow_fallback=False,
    )
    raw = _parse_list(result, ("objectives", "data", "items"))

    allowed_topic_ids = {str(t.get("id")) for t in topics}
    objectives = []
    seen_keys = set()
    for i, obj in enumerate(raw):
        if not isinstance(obj, dict):
            continue
        key = _norm(obj.get("key"))
        target = str(obj.get("target", "")).strip()
        if not key or not target or key in seen_keys:
            continue
        topic_id = str(obj.get("topic_id", ""))
        if topic_id not in allowed_topic_ids:
            topic_id = str(topics[0].get("id"))
        objectives.append({
            "id": f"o{len(objectives)+1}",
            "key": key.replace(" ", "-"),
            "topic_id": topic_id,
            "skill": str(obj.get("skill", "language competence")).strip()[:120],
            "target": target[:320],
            "evidence": str(obj.get("evidence", "")).strip()[:360],
            "question_mode": str(obj.get("question_mode", "other")).strip()[:80],
        })
        seen_keys.add(key)
        if len(objectives) >= requested_count:
            break
    return objectives


def _question_prompt(language, level, objectives, evidence, previous_questions, history):
    objective_json = json.dumps(objectives, ensure_ascii=False)
    recent = _recent_text(previous_questions, history)
    return [
        {
            "role": "system",
            "content": f"""You are AulaAI Assessment Writer V2 for {language} at CEFR {level}.
Write exactly ONE multiple-choice question for EACH supplied objective and no extra questions.

STRICT OUTPUT RULES:
- `objective_id` must exactly match the supplied objective id.
- `prompt`, `answer`, and all distractors must be natural {language}.
- Exactly 3 distinct distractors per question. Answer + distractors must be the same grammatical/semantic class and plausible.
- The question must test the assigned objective, not merely mention it.
- Do not introduce outside facts, arithmetic, trivia, etymology, abstract terminology or meta-spelling unless the assigned objective explicitly requires it.
- Prefer practical/contextual learner competence over talking about language terminology.
- Do not repeat or closely paraphrase RECENT QUESTIONS.
- The prompt must not reveal the answer.
- If prompt contains _____, both translations must preserve _____.
- `translation_en` and `translation_tr` must be concise natural translations.
- `why` and `why_tr` must be concise explanations; do not include hidden markers.

Return JSON only:
{{"questions":[{{"objective_id":"o1","prompt":"...","translation_en":"...","translation_tr":"...","answer":"...","distractors":["...","...","..."],"why":"...","why_tr":"..."}}]}}""",
        },
        {
            "role": "user",
            "content": f"OBJECTIVES:\n{objective_json}\n\nSOURCE EVIDENCE:\n{evidence}\n\nRECENT QUESTIONS:\n{recent or '(none)'}",
        },
    ]


def _valid_question(raw, objective, prior, accepted):
    if not isinstance(raw, dict):
        return None
    prompt = str(raw.get("prompt", "")).strip()
    answer = str(raw.get("answer", "")).strip()
    distractors = raw.get("distractors")
    if not prompt or not answer or not isinstance(distractors, list):
        return None

    clean_d = []
    for value in distractors:
        value = str(value).strip()
        if value and _norm(value) != _norm(answer) and _norm(value) not in {_norm(x) for x in clean_d}:
            clean_d.append(value)
    if len(clean_d) != 3:
        return None

    t_en = str(raw.get("translation_en", "")).strip()
    t_tr = str(raw.get("translation_tr", "")).strip()
    if "_____" in prompt and ("_____" not in t_en or "_____" not in t_tr):
        return None

    candidate = {"prompt": prompt, "answer": answer}
    if any(_near_repeat(candidate, old) for old in list(prior or []) + list(accepted or [])):
        return None

    return {
        "objective_id": objective["id"],
        "objective_key": objective["key"],
        "topic_id": objective["topic_id"],
        "type": "mcq",
        "prompt": prompt,
        "translation_en": t_en,
        "translation_tr": t_tr,
        "answer": answer,
        "distractors": clean_d,
        "why": str(raw.get("why", "Correct answer based on the lesson.")).strip(),
        "why_tr": str(raw.get("why_tr", "Ders içeriğine göre doğru seçenek.")).strip(),
    }


def _generate_for_objectives(language, level, objectives, evidence, previous_questions, history, accepted):
    pending = list(objectives)
    by_id = {obj["id"]: obj for obj in objectives}
    produced = []

    for attempt in range(_MAX_CHUNK_ATTEMPTS):
        if not pending:
            break
        result = _call_ai(
            _question_prompt(language, level, pending, evidence, previous_questions, history + accepted + produced),
            model=MODEL_STRUCTURAL,
            max_tokens=2000,
            temperature=0.45 if attempt == 0 else 0.30,
            json_mode=True,
            allow_fallback=False,
        )
        raw_questions = _parse_list(result, ("questions", "data", "items"))
        pending_ids = {obj["id"] for obj in pending}
        got_ids = set()
        for raw in raw_questions:
            if not isinstance(raw, dict):
                continue
            objective_id = str(raw.get("objective_id", "")).strip()
            if objective_id not in pending_ids or objective_id in got_ids:
                continue
            obj = by_id.get(objective_id)
            valid = _valid_question(raw, obj, list(previous_questions or []) + list(history or []), accepted + produced)
            if valid:
                produced.append(valid)
                got_ids.add(objective_id)
        pending = [obj for obj in pending if obj["id"] not in got_ids]
    return produced, pending


def generate_assessment_questions(*, topics, language, level, count, previous_questions=None, material_language="en"):
    """Generate a dynamic-size assessment set from read-only lesson topics.

    `count` is never hard-coded: 5, 10, 15, 20, etc. all use the same planner/writer flow.
    """
    try:
        requested = max(1, int(count))
    except Exception:
        requested = 10
    topics = [t for t in (topics or []) if isinstance(t, dict) and t.get("id") is not None]
    if not topics:
        return []

    evidence = _topic_evidence(topics)
    if not evidence:
        return []

    h_key = _history_key(language, level, topics)
    history = _get_history(h_key)
    objectives = _plan_objectives(
        topics, language, level, requested, evidence, previous_questions or [], history
    )
    if not objectives:
        return []

    # If the planner was truncated, ask once for the missing objective slots rather than
    # silently lowering the user's requested question count.
    if len(objectives) < requested:
        missing = requested - len(objectives)
        extra_history = history + [
            {"objective_key": o["key"], "prompt": o["target"], "answer": ""} for o in objectives
        ]
        extra = _plan_objectives(
            topics, language, level, missing, evidence, previous_questions or [], extra_history
        )
        used = {o["key"] for o in objectives}
        for obj in extra:
            if obj["key"] in used:
                continue
            obj = dict(obj)
            obj["id"] = f"o{len(objectives)+1}"
            objectives.append(obj)
            used.add(obj["key"])
            if len(objectives) >= requested:
                break

    objectives = objectives[:requested]
    accepted = []
    unresolved = []
    for start in range(0, len(objectives), _GEN_CHUNK_SIZE):
        chunk = objectives[start:start + _GEN_CHUNK_SIZE]
        made, missing_objs = _generate_for_objectives(
            language, level, chunk, evidence, previous_questions or [], history, accepted
        )
        accepted.extend(made)
        unresolved.extend(missing_objs)

    # One final targeted refill for any objectives that survived both chunk attempts.
    if unresolved:
        made, _ = _generate_for_objectives(
            language, level, unresolved, evidence, previous_questions or [], history, accepted
        )
        accepted.extend(made)

    # Preserve planner order so the result is stable and predictable.
    order = {obj["id"]: i for i, obj in enumerate(objectives)}
    accepted.sort(key=lambda q: order.get(q.get("objective_id"), 10**9))
    accepted = accepted[:requested]
    _remember(h_key, accepted)

    try:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(
                f"[ASSESSMENT-V2] requested={requested} planned={len(objectives)} generated={len(accepted)} "
                f"topics={len(topics)} history={len(history)}\n"
            )
    except Exception:
        pass

    # objective metadata is internal; topic_id is retained for persistence/routing.
    for q in accepted:
        q.pop("objective_id", None)
        q.pop("objective_key", None)
    return accepted
