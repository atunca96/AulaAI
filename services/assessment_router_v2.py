"""Runtime router for Assessment Engine V2, legacy, and shadow comparison modes.

ASSESSMENT_ENGINE=legacy|v2|shadow (default: v2)
ASSESSMENT_SHADOW_PRIMARY=legacy|v2 (default: v2)

Shadow mode returns only the primary result. The secondary engine is side-effect-free
and runs on a daemon thread for telemetry/scorecard comparison.
"""

import json
import os
import random
import re
import threading
import uuid

from services.ai_engine import is_ai_available, _sanitize_blank_translations
from services.assessment_engine_v2 import generate_assessment_questions
from services.assessment_scorecard import build_scorecard
from services.assessment_telemetry import complete_trace, log_shadow_comparison, trace_assessment

_LEGACY_GENERATOR = None


def _safe_int(value, default=10):
    try:
        return max(1, int(value))
    except Exception:
        return default


def _load_topic_content(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
    return {}


def _engine_mode():
    value = str(os.getenv("ASSESSMENT_ENGINE", "v2") or "v2").strip().lower()
    return value if value in {"legacy", "v2", "shadow"} else "v2"


def _shadow_primary():
    value = str(os.getenv("ASSESSMENT_SHADOW_PRIMARY", "v2") or "v2").strip().lower()
    return value if value in {"legacy", "v2"} else "v2"


def _source_text(topic_ids):
    """Read source material once for a cheap identical scorecard input."""
    try:
        from database import db_connection
        blocks = []
        with db_connection() as db_conn:
            for tid in topic_ids or []:
                row = db_conn.execute("SELECT title, type, content FROM topics WHERE id = ?", (tid,)).fetchone()
                if not row:
                    continue
                content = _load_topic_content(row["content"])
                blocks.append(
                    f"TOPIC {row['title']} ({row['type'] or ''})\n"
                    + json.dumps(content, ensure_ascii=False, separators=(",", ":"))
                )
        return "\n\n".join(blocks)[:120000]
    except Exception:
        return ""


def _persist_primary_questions(questions):
    """Persist only the primary result in shadow mode."""
    if not questions:
        return
    try:
        from database import db_connection
        with db_connection() as db_conn:
            for q in questions:
                if not isinstance(q, dict) or not q.get("id") or q.get("topic_id") is None:
                    continue
                distractors = q.get("distractors") or []
                if len(distractors) < 3:
                    continue
                db_conn.execute(
                    "INSERT OR IGNORE INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) VALUES (?,?,?,?,?,?,?,1)",
                    (
                        q["id"], q["topic_id"], q.get("type", "mcq"), q.get("prompt", ""),
                        q.get("answer", ""), json.dumps(distractors[:3], ensure_ascii=False),
                        q.get("difficulty", "A1"),
                    ),
                )
            db_conn.commit()
    except Exception:
        pass


def _v2_generate_assessment_set(topic_ids, count=10, is_quiz=False, ui_lang="en", existing_questions=None, progress_callback=None):
    from database import db_connection

    if not topic_ids:
        return []
    requested = _safe_int(count)
    topic_ids = list(topic_ids)

    if progress_callback:
        progress_callback(15, "Ders içeriği taranıyor..." if ui_lang == "tr" else "Scanning lesson content...")

    forbidden = list(existing_questions or [])
    topics = []
    base_lang = "Unknown"
    material_language = "en"
    course_level = "A1"

    with db_connection() as db_conn:
        first_tid = topic_ids[0]
        l_row = db_conn.execute("""
            SELECT co.language, co.material_language, co.level FROM courses co
            JOIN chapters ch ON co.id = ch.course_id
            JOIN topics t ON ch.id = t.chapter_id
            WHERE t.id = ?
        """, (first_tid,)).fetchone()
        if l_row:
            base_lang = l_row["language"] or "Unknown"
            if "material_language" in l_row.keys() and l_row["material_language"]:
                material_language = l_row["material_language"]
            if "level" in l_row.keys() and l_row["level"]:
                course_level = l_row["level"]

        for tid in topic_ids:
            row = db_conn.execute("SELECT id, title, type, content FROM topics WHERE id = ?", (tid,)).fetchone()
            if not row:
                continue
            topics.append({
                "id": row["id"],
                "title": row["title"],
                "type": row["type"] or "vocabulary",
                "content": _load_topic_content(row["content"]),
            })
            recent = db_conn.execute(
                "SELECT prompt, answer FROM questions WHERE topic_id = ? ORDER BY id DESC LIMIT 20",
                (tid,),
            ).fetchall()
            for item in recent:
                forbidden.append({"prompt": item["prompt"], "answer": item["answer"]})

    if not topics or not is_ai_available():
        return []

    if ui_lang in ("tr", "en"):
        material_language = ui_lang

    if progress_callback:
        progress_callback(35, "Soru hedefleri planlanıyor..." if ui_lang == "tr" else "Planning assessment objectives...")

    generated = generate_assessment_questions(
        topics=topics,
        language=base_lang,
        level=course_level,
        count=requested,
        previous_questions=forbidden,
        material_language=material_language,
    )

    if len(generated) < requested:
        missing = requested - len(generated)
        generated_history = forbidden + [
            {"prompt": q.get("prompt", ""), "answer": q.get("answer", "")} for q in generated
        ]
        top_up = generate_assessment_questions(
            topics=topics,
            language=base_lang,
            level=course_level,
            count=missing,
            previous_questions=generated_history,
            material_language=material_language,
        )
        generated.extend(top_up)

    if progress_callback:
        progress_callback(85, "Sorular doğrulanıyor..." if ui_lang == "tr" else "Validating questions...")

    valid_topic_ids = {str(t["id"]): t["id"] for t in topics}
    questions = []
    for q in generated:
        if len(questions) >= requested:
            break
        if not isinstance(q, dict):
            continue
        prompt = str(q.get("prompt", "")).strip()
        answer = str(q.get("answer", "")).strip()
        distractors = [str(x).strip() for x in (q.get("distractors") or []) if str(x).strip()]
        if not prompt or not answer or len(distractors) != 3:
            continue

        q_tid = valid_topic_ids.get(str(q.get("topic_id"))) or topics[0]["id"]
        t_en = str(q.get("translation_en") or q.get("translation") or "").strip()
        t_tr = str(q.get("translation_tr") or q.get("translation") or "").strip()
        why_en = str(q.get("why") or "Correct answer based on the lesson.").strip()
        why_tr = str(q.get("why_tr") or "Ders içeriğine göre doğru seçenek.").strip()

        if re.search(r"_{2,}", prompt):
            t_en, t_tr = _sanitize_blank_translations(prompt, answer, t_en, t_tr, why_en, why_tr)

        q_id = str(uuid.uuid4())
        options = [answer] + distractors
        random.shuffle(options)

        if is_quiz:
            with db_connection() as db_conn:
                db_conn.execute(
                    "INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) VALUES (?,?,?,?,?,?,?,1)",
                    (q_id, q_tid, "mcq", prompt, answer, json.dumps(distractors, ensure_ascii=False), course_level),
                )
                db_conn.commit()

        questions.append({
            "id": q_id,
            "topic_id": q_tid,
            "type": "mcq",
            "prompt": prompt,
            "translation": t_tr if material_language == "tr" else t_en,
            "translation_en": t_en,
            "translation_tr": t_tr,
            "answer": answer,
            "distractors": distractors,
            "options": options,
            "difficulty": course_level,
            "why": why_en,
            "why_tr": why_tr,
        })

    if progress_callback:
        progress_callback(100, "Tamamlandı." if ui_lang == "tr" else "Done.")

    return questions[:requested]


def _run_engine(engine, *, topic_ids, count, is_quiz, ui_lang, existing_questions, progress_callback, source_text, request_id, shadow=False):
    requested = _safe_int(count)
    target = _v2_generate_assessment_set if engine == "v2" else _LEGACY_GENERATOR
    if target is None:
        return [], complete_trace({
            "schema": "assessment_metric_v1", "request_id": request_id, "engine": engine,
            "shadow": shadow, "requested_count": requested, "topic_count": len(topic_ids or []),
            "provider_ms": 0.0, "provider_calls": 0, "provider_errors": 0,
            "provider_by_phase_ms": {}, "provider_calls_by_phase": {}, "models": {}, "total_ms": 0.0,
        }, 0, scorecard=build_scorecard([], requested, source_text), error="engine unavailable")

    result = []
    error = None
    with trace_assessment(engine, requested, len(topic_ids or []), request_id=request_id, shadow=shadow) as trace:
        try:
            result = target(
                topic_ids=topic_ids,
                count=requested,
                is_quiz=is_quiz,
                ui_lang=ui_lang,
                existing_questions=existing_questions,
                progress_callback=progress_callback,
            ) or []
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:220]}"
            result = []
    scorecard = build_scorecard(result, requested, source_text)
    complete_trace(trace, len(result), scorecard=scorecard, error=error)
    return result, trace


def _shadow_worker(primary_done, holder, shadow_engine, call_kwargs, source_text, request_id):
    shadow_result, shadow_trace = _run_engine(
        shadow_engine,
        source_text=source_text,
        request_id=request_id,
        shadow=True,
        **call_kwargs,
    )
    primary_done.wait()
    primary_trace = holder.get("primary_trace")
    if primary_trace:
        log_shadow_comparison(request_id, primary_trace, shadow_trace)


def _routed_generate_assessment_set(topic_ids, count=10, is_quiz=False, ui_lang="en", existing_questions=None, progress_callback=None):
    mode = _engine_mode()
    request_id = uuid.uuid4().hex
    source_text = _source_text(topic_ids)
    common = {
        "topic_ids": list(topic_ids or []),
        "count": count,
        "ui_lang": ui_lang,
        "existing_questions": existing_questions,
        "progress_callback": progress_callback,
    }

    if mode in {"legacy", "v2"}:
        result, _ = _run_engine(
            mode,
            is_quiz=is_quiz,
            source_text=source_text,
            request_id=request_id,
            shadow=False,
            **common,
        )
        return result

    primary_engine = _shadow_primary()
    shadow_engine = "legacy" if primary_engine == "v2" else "v2"

    # Both engines generate side-effect-free in shadow mode. Only the primary is persisted.
    shadow_kwargs = dict(common)
    shadow_kwargs["is_quiz"] = False
    shadow_kwargs["progress_callback"] = None
    primary_kwargs = dict(common)
    primary_kwargs["is_quiz"] = False

    primary_done = threading.Event()
    holder = {}
    thread = threading.Thread(
        target=_shadow_worker,
        args=(primary_done, holder, shadow_engine, shadow_kwargs, source_text, request_id),
        daemon=True,
        name=f"assessment-shadow-{request_id[:8]}",
    )
    thread.start()

    primary_result, primary_trace = _run_engine(
        primary_engine,
        source_text=source_text,
        request_id=request_id,
        shadow=False,
        **primary_kwargs,
    )
    holder["primary_trace"] = primary_trace
    if is_quiz:
        _persist_primary_questions(primary_result)
    primary_done.set()
    return primary_result


def install(content_engine_module):
    global _LEGACY_GENERATOR
    if getattr(content_engine_module, "_assessment_engine_v2_installed", False):
        return
    _LEGACY_GENERATOR = content_engine_module.generate_assessment_set
    content_engine_module._legacy_generate_assessment_set = _LEGACY_GENERATOR
    content_engine_module.generate_assessment_set = _routed_generate_assessment_set
    content_engine_module._assessment_engine_v2_installed = True
