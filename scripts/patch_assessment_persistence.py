from pathlib import Path
import re

path = Path('server.py')
src = path.read_text(encoding='utf-8')

# ---------------------------------------------------------------------------
# 1) Assessment questions must exist in `questions` before mapping them into
# quiz_questions / assignment_questions. Generated drafts already carry UUIDs,
# but older publish paths assumed every UUID was already persisted. That left
# valid-looking assessments whose JOIN returned zero questions.
# ---------------------------------------------------------------------------
uid_anchor = '''def _uid():\n    return str(uuid.uuid4())\n'''
if uid_anchor not in src:
    raise RuntimeError('assessment persistence: _uid anchor not found')
if 'def _persist_assessment_question(' not in src:
    helper = r'''

def _resolve_assessment_topic(db, q, course_id=None, chapter_id=None):
    """Return a valid topic for grading/mastery without trusting stale draft IDs."""
    requested = q.get("topic_id") if isinstance(q, dict) else None
    if requested:
        row = db.execute("""
            SELECT t.id FROM topics t
            JOIN chapters ch ON t.chapter_id = ch.id
            WHERE t.id = ? AND (? IS NULL OR ch.course_id = ?)
            LIMIT 1
        """, (requested, course_id, course_id)).fetchone()
        if row:
            return row["id"]

    if chapter_id and chapter_id not in ("all", ""):
        # The UI normally sends a chapter id, but accept a topic id defensively.
        row = db.execute("""
            SELECT t.id FROM topics t
            JOIN chapters ch ON t.chapter_id = ch.id
            WHERE ch.id = ? AND (? IS NULL OR ch.course_id = ?)
            ORDER BY t.sort_order, t.rowid LIMIT 1
        """, (chapter_id, course_id, course_id)).fetchone()
        if row:
            return row["id"]
        row = db.execute("""
            SELECT t.id FROM topics t
            JOIN chapters ch ON t.chapter_id = ch.id
            WHERE t.id = ? AND (? IS NULL OR ch.course_id = ?)
            LIMIT 1
        """, (chapter_id, course_id, course_id)).fetchone()
        if row:
            return row["id"]

    if course_id:
        row = db.execute("""
            SELECT t.id FROM topics t
            JOIN chapters ch ON t.chapter_id = ch.id
            WHERE ch.course_id = ?
            ORDER BY ch.number, t.sort_order, t.rowid LIMIT 1
        """, (course_id,)).fetchone()
        if row:
            return row["id"]
    return None


def _persist_assessment_question(db, q, course_id=None, chapter_id=None, preferred_id=None):
    """
    Persist a publish-time assessment snapshot and return the durable question id.
    If preferred_id already exists with different content, clone instead of
    mutating a question that another assessment may already reference.
    """
    if not isinstance(q, dict):
        q = {}
    prompt = str(q.get("prompt") or "").strip()
    answer = str(q.get("answer") or "").strip()
    if not prompt or not answer:
        raise ValueError("Assessment question is missing prompt or answer")

    qid = str(preferred_id or q.get("id") or _uid())
    existing = db.execute("SELECT prompt, answer FROM questions WHERE id = ?", (qid,)).fetchone()
    if existing:
        same = (str(existing["prompt"] or "").strip() == prompt and
                str(existing["answer"] or "").strip() == answer)
        if same:
            return qid
        qid = _uid()

    topic_id = _resolve_assessment_topic(db, q, course_id, chapter_id)
    distractors = q.get("distractors") or []
    if isinstance(distractors, str):
        try:
            parsed = json.loads(distractors)
            distractors = parsed if isinstance(parsed, list) else [distractors]
        except Exception:
            distractors = [d.strip() for d in distractors.split(",") if d.strip()]
    if not isinstance(distractors, list):
        distractors = list(distractors) if distractors else []
    if not distractors and isinstance(q.get("options"), list):
        distractors = [o for o in q.get("options", []) if str(o).strip() != answer]

    metadata = {
        "assessment_snapshot": True,
        "source_question_id": q.get("id"),
        "translation": q.get("translation"),
        "translation_en": q.get("translation_en"),
        "translation_tr": q.get("translation_tr"),
        "why": q.get("why"),
        "why_tr": q.get("why_tr"),
        "evidence": q.get("evidence"),
        "material_section": q.get("material_section"),
    }
    db.execute("""
        INSERT INTO questions
            (id, topic_id, type, prompt, answer, distractors, difficulty, metadata, is_active, approved)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        qid, topic_id, q.get("type", "mcq"), prompt, answer,
        json.dumps(distractors, ensure_ascii=False), q.get("difficulty") or "custom",
        json.dumps(metadata, ensure_ascii=False), 1, 1
    ))
    return qid


def _repair_assessment_questions_from_draft(db, kind, assessment_id, course_id):
    """
    Safely repairs already-published broken assessments only when the missing
    mapping id exactly matches an id still present in the course's draft_result.
    No fuzzy matching and no invented question association.
    """
    if kind == "quiz":
        map_table, id_col = "quiz_questions", "quiz_id"
    else:
        map_table, id_col = "assignment_questions", "assignment_id"

    mapped = db.execute(
        f"SELECT question_id FROM {map_table} WHERE {id_col} = ? ORDER BY sort_order",
        (assessment_id,)
    ).fetchall()
    if not mapped:
        return 0

    missing = []
    for row in mapped:
        qid = row["question_id"]
        if not db.execute("SELECT 1 FROM questions WHERE id = ?", (qid,)).fetchone():
            missing.append(qid)
    if not missing:
        return 0

    draft_row = db.execute("SELECT draft_result FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not draft_row or not draft_row["draft_result"]:
        return 0
    try:
        draft = json.loads(draft_row["draft_result"])
    except Exception:
        return 0
    if not isinstance(draft, list):
        return 0

    by_id = {str(q.get("id")): q for q in draft if isinstance(q, dict) and q.get("id")}
    repaired = 0
    for qid in missing:
        q = by_id.get(str(qid))
        if not q:
            continue
        _persist_assessment_question(db, q, course_id=course_id, preferred_id=qid)
        repaired += 1
    if repaired:
        db.commit()
        print(f"[ASSESSMENT-REPAIR] Restored {repaired} missing {kind} question(s) for {assessment_id}")
    return repaired
'''
    src = src.replace(uid_anchor, uid_anchor + helper, 1)


def patch_function(name, transform):
    global src
    marker = f"    def {name}(self"
    start = src.find(marker)
    if start < 0:
        raise RuntimeError(f'assessment persistence: function {name} not found')
    nxt = src.find("\n    def ", start + len(marker))
    if nxt < 0:
        raise RuntimeError(f'assessment persistence: end of {name} not found')
    chunk = src[start:nxt]
    new_chunk = transform(chunk)
    if new_chunk == chunk:
        raise RuntimeError(f'assessment persistence: no change made in {name}')
    src = src[:start] + new_chunk + src[nxt:]


# Direct quiz creation also receives generated UUIDs that are not yet DB rows.
def fix_create_quiz(chunk):
    old = '''        quiz_id = _uid()\n        with db_connection() as db:\n            db.execute("INSERT INTO quizzes (id, course_id, title, due_date, is_published, created_at) VALUES (?,?,?,datetime('now','+1 day'),1,datetime('now'))",\n                       (quiz_id, course_id, title))\n\n            for i, q in enumerate(questions):\n                db.execute("INSERT OR IGNORE INTO quiz_questions VALUES (?,?,?)",\n                           (quiz_id, q["id"], i))\n            db.commit()\n'''
    new = '''        if not questions:\n            return self._send_error("Quiz generation produced no questions", 409)\n\n        quiz_id = _uid()\n        with db_connection() as db:\n            db.execute("INSERT INTO quizzes (id, course_id, title, due_date, is_published, created_at) VALUES (?,?,?,datetime('now','+1 day'),1,datetime('now'))",\n                       (quiz_id, course_id, title))\n\n            for i, q in enumerate(questions):\n                qid = _persist_assessment_question(db, q, course_id=course_id, chapter_id=chapter_id)\n                db.execute("INSERT OR IGNORE INTO quiz_questions VALUES (?,?,?)",\n                           (quiz_id, qid, i))\n            mapped = db.execute("""\n                SELECT COUNT(*) FROM quiz_questions qq\n                JOIN questions q ON q.id = qq.question_id\n                WHERE qq.quiz_id = ?\n            """, (quiz_id,)).fetchone()[0]\n            if mapped != len(questions):\n                db.rollback()\n                return self._send_error("Quiz could not persist all questions", 500)\n            db.commit()\n'''
    if old not in chunk:
        raise RuntimeError('assessment persistence: _create_quiz anchor changed')
    return chunk.replace(old, new, 1)
patch_function('_create_quiz', fix_create_quiz)


# Draft publish: always persist the exact edited/generated question before mapping.
def fix_draft_publish(chunk):
    if 'questions = body.get("questions", [])' not in chunk:
        raise RuntimeError('assessment persistence: draft questions anchor missing')
    chunk = chunk.replace(
        '        questions = body.get("questions", [])\n\n        with db_connection() as db:\n',
        '        questions = body.get("questions", [])\n        if not isinstance(questions, list) or not questions:\n            return self._send_error("Cannot publish an assessment without questions", 409)\n\n        with db_connection() as db:\n',
        1
    )
    pattern = re.compile(r'''            seen_ids = set\(\)\n.*?            db\.commit\(\)''', re.S)
    replacement = '''            seen_ids = set()\n            for i, q in enumerate(questions):\n                if not isinstance(q, dict):\n                    continue\n                preferred = q.get("id")\n                if preferred in seen_ids:\n                    preferred = None\n                qid = _persist_assessment_question(\n                    db, q, course_id=course_id, chapter_id=chapter_id, preferred_id=preferred\n                )\n                if qid in seen_ids:\n                    qid = _persist_assessment_question(\n                        db, dict(q, id=None), course_id=course_id, chapter_id=chapter_id, preferred_id=None\n                    )\n                seen_ids.add(qid)\n                if pub_type == "quiz":\n                    db.execute("INSERT OR IGNORE INTO quiz_questions VALUES (?,?,?)", (pub_id, qid, len(seen_ids)-1))\n                else:\n                    db.execute("INSERT OR IGNORE INTO assignment_questions VALUES (?,?,?)", (pub_id, qid, len(seen_ids)-1))\n\n            map_table = "quiz_questions" if pub_type == "quiz" else "assignment_questions"\n            id_col = "quiz_id" if pub_type == "quiz" else "assignment_id"\n            mapped = db.execute(\n                f"SELECT COUNT(*) FROM {map_table} m JOIN questions q ON q.id = m.question_id WHERE m.{id_col} = ?",\n                (pub_id,)\n            ).fetchone()[0]\n            if mapped != len(questions):\n                db.rollback()\n                return self._send_error("Assessment could not persist all questions", 500)\n            db.commit()'''
    chunk2, n = pattern.subn(replacement, chunk, count=1)
    if n != 1:
        raise RuntimeError(f'assessment persistence: draft publish loop matched {n} times')
    return chunk2
patch_function('_draft_publish', fix_draft_publish)


# Direct assignment creation has the same missing-persistence bug.
def fix_create_assignment(chunk):
    old = '''        from services.content_engine import generate_quiz\n        questions = generate_quiz(topic_ids, count=count, is_quiz=False)\n        \n        with db_connection() as db:\n            for i, q in enumerate(questions):\n                db.execute("INSERT OR IGNORE INTO assignment_questions VALUES (?,?,?)",\n                           (assignment_id, q["id"], i))\n            db.commit()\n'''
    new = '''        from services.content_engine import generate_quiz\n        questions = generate_quiz(topic_ids, count=count, is_quiz=False)\n        if not questions:\n            with db_connection() as db:\n                db.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))\n                db.commit()\n            return self._send_error("Assignment generation produced no questions", 409)\n        \n        with db_connection() as db:\n            for i, q in enumerate(questions):\n                qid = _persist_assessment_question(db, q, course_id=course_id, chapter_id=chapter_id)\n                db.execute("INSERT OR IGNORE INTO assignment_questions VALUES (?,?,?)",\n                           (assignment_id, qid, i))\n            mapped = db.execute("""\n                SELECT COUNT(*) FROM assignment_questions aq\n                JOIN questions q ON q.id = aq.question_id\n                WHERE aq.assignment_id = ?\n            """, (assignment_id,)).fetchone()[0]\n            if mapped != len(questions):\n                db.rollback()\n                return self._send_error("Assignment could not persist all questions", 500)\n            db.commit()\n'''
    if old not in chunk:
        raise RuntimeError('assessment persistence: _create_assignment anchor changed')
    return chunk.replace(old, new, 1)
patch_function('_create_assignment', fix_create_assignment)


# Student quiz listing: a [STARTED] lock is in-progress, not completed.
def fix_get_quizzes(chunk):
    old = '''                        "SELECT 1 FROM responses WHERE student_id = ? AND context_id = ? LIMIT 1",\n                        (student_id, q["id"])\n'''
    new = '''                        "SELECT 1 FROM responses WHERE student_id = ? AND context_id = ? AND context_type = 'quiz' AND answer != '[STARTED]' LIMIT 1",\n                        (student_id, q["id"])\n'''
    if old not in chunk:
        raise RuntimeError('assessment persistence: quiz completed anchor changed')
    return chunk.replace(old, new, 1)
patch_function('_get_quizzes', fix_get_quizzes)


# Quiz take: repair exact draft IDs when possible, then never lock/submit an empty assessment.
def fix_get_quiz(chunk):
    anchor = '''            questions = db.execute("""\n                SELECT q.* FROM questions q\n                JOIN quiz_questions qq ON q.id = qq.question_id\n                WHERE qq.quiz_id = ?\n                ORDER BY qq.sort_order\n            """, (quiz_id,)).fetchall()\n\n            if student_id:\n'''
    replacement = '''            questions = db.execute("""\n                SELECT q.* FROM questions q\n                JOIN quiz_questions qq ON q.id = qq.question_id\n                WHERE qq.quiz_id = ?\n                ORDER BY qq.sort_order\n            """, (quiz_id,)).fetchall()\n\n            mapped_count = db.execute("SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = ?", (quiz_id,)).fetchone()[0]\n            if len(questions) < mapped_count:\n                _repair_assessment_questions_from_draft(db, "quiz", quiz_id, quiz["course_id"])\n                questions = db.execute("""\n                    SELECT q.* FROM questions q\n                    JOIN quiz_questions qq ON q.id = qq.question_id\n                    WHERE qq.quiz_id = ?\n                    ORDER BY qq.sort_order\n                """, (quiz_id,)).fetchall()\n\n            if not questions:\n                return self._send_error("This quiz has no available questions. Re-publish the quiz.", 409)\n\n            if student_id:\n'''
    if anchor not in chunk:
        raise RuntimeError('assessment persistence: _get_quiz anchor changed')
    return chunk.replace(anchor, replacement, 1)
patch_function('_get_quiz', fix_get_quiz)


# Assignment take: same repair + empty guard, preventing the instant 0% completion.
def fix_get_assignment(chunk):
    anchor = '''            questions = db.execute("""\n                SELECT q.* FROM questions q\n                JOIN assignment_questions aq ON q.id = aq.question_id\n                WHERE aq.assignment_id = ?\n                ORDER BY aq.sort_order\n            """, (assignment_id,)).fetchall()\n\n            if student_id:\n'''
    replacement = '''            questions = db.execute("""\n                SELECT q.* FROM questions q\n                JOIN assignment_questions aq ON q.id = aq.question_id\n                WHERE aq.assignment_id = ?\n                ORDER BY aq.sort_order\n            """, (assignment_id,)).fetchall()\n\n            mapped_count = db.execute("SELECT COUNT(*) FROM assignment_questions WHERE assignment_id = ?", (assignment_id,)).fetchone()[0]\n            if len(questions) < mapped_count:\n                _repair_assessment_questions_from_draft(db, "assignment", assignment_id, assignment["course_id"])\n                questions = db.execute("""\n                    SELECT q.* FROM questions q\n                    JOIN assignment_questions aq ON q.id = aq.question_id\n                    WHERE aq.assignment_id = ?\n                    ORDER BY aq.sort_order\n                """, (assignment_id,)).fetchall()\n\n            if not questions:\n                return self._send_error("This assignment has no available questions. Re-publish the assignment.", 409)\n\n            if student_id:\n'''
    if anchor not in chunk:
        raise RuntimeError('assessment persistence: _get_assignment anchor changed')
    return chunk.replace(anchor, replacement, 1)
patch_function('_get_assignment', fix_get_assignment)


# ---------------------------------------------------------------------------
# 2) Curriculum regeneration must not delete question rows referenced by a
# published assessment. Protect every course-topic question cleanup statement.
# ---------------------------------------------------------------------------
one_line = 'DELETE FROM questions WHERE topic_id IN (SELECT t.id FROM topics t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.course_id = ?)'
protected_one_line = '''DELETE FROM questions WHERE topic_id IN (SELECT t.id FROM topics t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.course_id = ?) AND id NOT IN (SELECT question_id FROM quiz_questions) AND id NOT IN (SELECT question_id FROM assignment_questions)'''
src = src.replace(one_line, protected_one_line)

multiline_pattern = re.compile(r'''DELETE FROM questions WHERE topic_id IN \(\n\s*SELECT t\.id FROM topics t\n\s*JOIN chapters ch ON t\.chapter_id = ch\.id\n\s*WHERE ch\.course_id = \?\n\s*\)''')
def protect_multiline(m):
    return m.group(0) + '''\n                  AND id NOT IN (SELECT question_id FROM quiz_questions)\n                  AND id NOT IN (SELECT question_id FROM assignment_questions)'''
src, protected_count = multiline_pattern.subn(protect_multiline, src)

path.write_text(src, encoding='utf-8')
print(f'Applied assessment persistence fix; protected {protected_count} multiline curriculum cleanup(s)')
