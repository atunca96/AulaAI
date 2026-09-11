"""Runtime router for Assessment Engine V2 only.

Replaces content_engine.generate_assessment_set while leaving lesson/material generation
and the rest of content_engine untouched.
"""

import json
import random
import re
import uuid

from services.ai_engine import is_ai_available, _sanitize_blank_translations
from services.assessment_engine_v2 import generate_assessment_questions


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

    # One bounded top-up pass if a provider/JSON failure left the first V2 pass short.
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

    try:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[ASSESSMENT-V2-ROUTER] requested={requested} returned={len(questions)} topics={len(topics)}\n")
    except Exception:
        pass

    return questions[:requested]


def install(content_engine_module):
    if getattr(content_engine_module, "_assessment_engine_v2_installed", False):
        return
    # Keep the legacy implementation reachable for emergency rollback/debugging,
    # but all normal unified assessment calls route through V2.
    content_engine_module._legacy_generate_assessment_set = content_engine_module.generate_assessment_set
    content_engine_module.generate_assessment_set = _v2_generate_assessment_set
    content_engine_module._assessment_engine_v2_installed = True
