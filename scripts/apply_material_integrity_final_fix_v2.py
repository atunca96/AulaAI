from pathlib import Path


def replace_once(path, old, new, label):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, found {n}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


# 1) Unit assessment completion after publication filtering.
p = Path("services/ai_engine.py")
s = p.read_text(encoding="utf-8")
old = '''    if len(questions) < UNIT_ASSESSMENT_COUNT:\n        with open("pipeline.log", "a", encoding="utf-8") as f:\n            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [UNIT-ASSESSMENT] '{unit_title}' "\n                    f"produced {len(questions)}/{UNIT_ASSESSMENT_COUNT}; not published.\\n")\n        return []\n\n    # Attribute each question to a topic in the unit, preferring what the model\n'''
new = '''    if len(questions) < UNIT_ASSESSMENT_COUNT:\n        # `ai_generate_questions` can reach 10 before its publication boundary and\n        # lose one structurally invalid item afterwards. Complete the published set\n        # from already-published formative MCQs in THIS unit only. No provider call.\n        try:\n            from services.publication_invariants import apply_assessment_invariants\n            from services.assessment_validation import looks_like_translation_question\n            seen_prompts = {_normalize_token(q.get("prompt", "")) for q in questions if isinstance(q, dict)}\n            for t, content in zip(usable, contents):\n                if len(questions) >= UNIT_ASSESSMENT_COUNT:\n                    break\n                for page in (content.get("pages") or []):\n                    if len(questions) >= UNIT_ASSESSMENT_COUNT:\n                        break\n                    if not isinstance(page, dict) or str(page.get("type") or "").casefold() != "mcq":\n                        continue\n                    prompt = str(page.get("prompt") or "").strip()\n                    answer = str(page.get("answer") or "").strip()\n                    if not prompt or not answer or looks_like_translation_question(prompt):\n                        continue\n                    prompt_key = _normalize_token(prompt)\n                    if not prompt_key or prompt_key in seen_prompts:\n                        continue\n                    options = list(page.get("options") or [])\n                    if not options:\n                        options = [answer] + list(page.get("distractors") or [])\n                    options = [str(o).strip() for o in options if str(o).strip()]\n                    if len(options) < 4 or answer not in options:\n                        continue\n                    candidate = {\n                        "id": _uid(),\n                        "type": "mcq",\n                        "stem_scope": "target_complete",\n                        "prompt": prompt,\n                        "answer": answer,\n                        "options": options[:4],\n                        "distractors": [o for o in options if _normalize_token(o) != _normalize_token(answer)][:3],\n                        "why": page.get("explanation") or "Correct choice based on the unit material.",\n                        "why_tr": page.get("explanation_tr") or "Ünite içeriğine göre doğru seçenek.",\n                        "topic_id": t.get("id"),\n                    }\n                    published = apply_assessment_invariants(\n                        [candidate], language=language, material_language=material_language\n                    )\n                    if published:\n                        questions.append(published[0])\n                        seen_prompts.add(prompt_key)\n        except Exception as recovery_exc:\n            with open("pipeline.log", "a", encoding="utf-8") as f:\n                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [UNIT-ASSESSMENT] deterministic completion failed: {recovery_exc}\\n")\n\n    if len(questions) < UNIT_ASSESSMENT_COUNT:\n        with open("pipeline.log", "a", encoding="utf-8") as f:\n            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [UNIT-ASSESSMENT] '{unit_title}' "\n                    f"produced {len(questions)}/{UNIT_ASSESSMENT_COUNT}; not published.\\n")\n        return []\n\n    # Attribute each question to a topic in the unit, preferring what the model\n'''
if s.count(old) != 1:
    raise SystemExit(f"unit completion patch count={s.count(old)}")
p.write_text(s.replace(old, new, 1), encoding="utf-8")


# 2) Unit-assessment titles/content must remain bilingual at rest.
p = Path("services/legacy/pdf_pipeline.py")
s = p.read_text(encoding="utf-8")

old = '            "SELECT id, title, number FROM chapters WHERE course_id = ? ORDER BY number", (course_id,)\n'
new = '            "SELECT id, title, title_tr, number FROM chapters WHERE course_id = ? ORDER BY number", (course_id,)\n'
if s.count(old) != 1:
    raise SystemExit(f"chapter title_tr query patch count={s.count(old)}")
s = s.replace(old, new, 1)

old = '''            if topics:\n                units.append({"chapter_id": ch[0], "title": ch[1], "number": ch[2],\n                              "topics": topics, "next_sort": max_sort + 1})\n'''
new = '''            if topics:\n                units.append({"chapter_id": ch[0], "title": ch[1], "title_tr": ch[2] or ch[1], "number": ch[3],\n                              "topics": topics, "next_sort": max_sort + 1})\n'''
if s.count(old) != 1:
    raise SystemExit(f"unit metadata patch count={s.count(old)}")
s = s.replace(old, new, 1)

old = '''        content = build_unit_assessment_content(unit["title"], questions, material_language)\n        title = unit_assessment_title(unit["title"], material_language)\n        with db_connection() as db:\n            existing = db.execute(\n                "SELECT id FROM topics WHERE chapter_id = ? AND type = ?",\n                (unit["chapter_id"], UNIT_ASSESSMENT_TYPE),\n            ).fetchone()\n            payload = json.dumps(content, ensure_ascii=False)\n            if existing:\n                db.execute("UPDATE topics SET title = ?, content = ? WHERE id = ?",\n                           (title, payload, existing[0]))\n            else:\n                db.execute(\n                    "INSERT INTO topics (id, chapter_id, type, title, content, sort_order) VALUES (?,?,?,?,?,?)",\n                    (_uid(), unit["chapter_id"], UNIT_ASSESSMENT_TYPE, title, payload, unit["next_sort"]),\n                )\n            db.commit()\n'''
new = '''        content = build_unit_assessment_content(\n            unit["title"], questions, material_language, unit_title_tr=unit.get("title_tr")\n        )\n        title_en = unit_assessment_title(unit["title"], "en", unit_title_tr=unit.get("title_tr"))\n        title_tr = unit_assessment_title(unit["title"], "tr", unit_title_tr=unit.get("title_tr"))\n        with db_connection() as db:\n            existing = db.execute(\n                "SELECT id FROM topics WHERE chapter_id = ? AND type = ?",\n                (unit["chapter_id"], UNIT_ASSESSMENT_TYPE),\n            ).fetchone()\n            payload = json.dumps(content, ensure_ascii=False)\n            if existing:\n                db.execute("UPDATE topics SET title = ?, title_tr = ?, content = ? WHERE id = ?",\n                           (title_en, title_tr, payload, existing[0]))\n            else:\n                db.execute(\n                    "INSERT INTO topics (id, chapter_id, type, title, title_tr, content, sort_order) VALUES (?,?,?,?,?,?,?)",\n                    (_uid(), unit["chapter_id"], UNIT_ASSESSMENT_TYPE, title_en, title_tr, payload, unit["next_sort"]),\n                )\n            db.commit()\n'''
if s.count(old) != 1:
    raise SystemExit(f"assessment persistence patch count={s.count(old)}")
s = s.replace(old, new, 1)

old = '''def unit_assessment_title(unit_title, material_language="tr"):\n    label = "Ünite Değerlendirmesi" if str(material_language).casefold() == "tr" else "Unit Assessment"\n    return f"{label}: {unit_title}" if unit_title else label\n\n\ndef build_unit_assessment_content(unit_title, questions, material_language="tr"):\n'''
new = '''def unit_assessment_title(unit_title, material_language="tr", unit_title_tr=None):\n    is_tr = str(material_language).casefold() == "tr"\n    label = "Ünite Değerlendirmesi" if is_tr else "Unit Assessment"\n    chosen = (unit_title_tr or unit_title) if is_tr else unit_title\n    return f"{label}: {chosen}" if chosen else label\n\n\ndef build_unit_assessment_content(unit_title, questions, material_language="tr", unit_title_tr=None):\n'''
if s.count(old) != 1:
    raise SystemExit(f"assessment title function patch count={s.count(old)}")
s = s.replace(old, new, 1)

old = '''    heading = unit_assessment_title(unit_title, material_language)\n    intro = ("Bu ünitede öğrendiklerinizi değerlendirin." if is_tr\n             else "Check what you have learned in this unit.")\n    return {"pages": [{"type": "overview", "title": heading, "title_tr": heading,\n                       "text": intro, "text_tr": intro}] + pages}\n'''
new = '''    heading_en = unit_assessment_title(unit_title, "en", unit_title_tr=unit_title_tr)\n    heading_tr = unit_assessment_title(unit_title, "tr", unit_title_tr=unit_title_tr)\n    return {"pages": [{\n        "type": "overview",\n        "title": heading_en,\n        "title_tr": heading_tr,\n        "text": "Check what you have learned in this unit.",\n        "text_tr": "Bu ünitede öğrendiklerinizi değerlendirin.",\n    }] + pages}\n'''
if s.count(old) != 1:
    raise SystemExit(f"assessment overview patch count={s.count(old)}")
s = s.replace(old, new, 1)


# 3) Fill only genuinely blank phonetic table cells in one class-level batch.
phase_marker = "        # ── PHASE 2b: UNIT ASSESSMENTS ──\n"
phase_insert = '''        # ── PHASE 2a.5: PHONETIC COMPLETENESS ──\n        try:\n            _repair_missing_phonetics(course_id, language)\n        except Exception as phon_err:\n            _log(f"[PHONETIC-COMPLETE] repair skipped: {phon_err}")\n\n'''
if s.count(phase_marker) != 1:
    raise SystemExit(f"phase marker count={s.count(phase_marker)}")
s = s.replace(phase_marker, phase_insert + phase_marker, 1)

helper_marker = 'UNIT_ASSESSMENT_TYPE = "unit_assessment"\n'
helper = r'''def _repair_missing_phonetics(course_id, language):
    """Fill blank table phonetics in one bounded batch; never overwrite existing IPA."""
    with db_connection() as db:
        rows = db.execute(
            "SELECT id, content FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id = ?) "
            "AND (type IS NULL OR type != ?)",
            (course_id, UNIT_ASSESSMENT_TYPE),
        ).fetchall()

    parsed = []
    missing = {}
    examples = []

    def scan(container):
        if not isinstance(container, list):
            return
        for entry in container:
            if not isinstance(entry, dict):
                continue
            term = str(entry.get("term") or entry.get("word") or entry.get("target") or "").strip()
            phon = str(entry.get("phonetic") or "").strip()
            if not term or not any(ch.isalpha() for ch in term):
                continue
            if phon:
                if len(examples) < 16:
                    examples.append((term, phon))
            else:
                missing.setdefault(term, []).append(entry)

    for topic_id, raw in rows:
        try:
            content = json.loads(raw or "{}") if isinstance(raw, str) else (raw or {})
        except Exception:
            continue
        if not isinstance(content, dict):
            continue
        parsed.append((topic_id, content))
        for page in content.get("pages") or []:
            if isinstance(page, dict):
                for key in ("items", "vocabulary", "words"):
                    scan(page.get(key))

    if not missing:
        _log("[PHONETIC-COMPLETE] no blank phonetic rows.")
        return 0

    terms = list(missing)[:160]
    calibration = "\n".join(f"- {term}: {phon}" for term, phon in examples[:12]) or "(none)"
    prompt = f"""Fill missing phonetic transcriptions for a {language} language course.
Return ONLY valid JSON: {{"items":[{{"term":"EXACT INPUT TERM","phonetic":"[standard IPA]"}}]}}.
Preserve each term exactly. Return one item per input term. `phonetic` must be pronunciation, never translation or a letter name. Match the IPA convention used in the class examples. If a term genuinely has no spoken pronunciation, return an empty string.
Existing class examples:\n{calibration}\n\nTerms missing phonetics:\n""" + "\n".join(f"- {term}" for term in terms)
    response = _call_ai(
        [{"role": "user", "content": prompt}],
        max_tokens=min(3600, 180 + 28 * len(terms)),
        temperature=0.0,
        json_mode=True,
        allow_fallback=True,
        cost_stage="phonetic_completion",
        cost_subject=f"course {course_id}",
    )
    payload = response.get("items") if isinstance(response, dict) else response
    if not isinstance(payload, list):
        _log(f"[PHONETIC-COMPLETE] provider returned no usable mapping for {len(terms)} blank terms.")
        return 0

    allowed = set(terms)
    mapping = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        phon = str(item.get("phonetic") or "").strip()
        if term in allowed and phon and len(phon) <= 120:
            mapping[term] = phon

    filled = 0
    for term, entries in missing.items():
        phon = mapping.get(term)
        if not phon:
            continue
        for entry in entries:
            if not str(entry.get("phonetic") or "").strip():
                entry["phonetic"] = phon
                filled += 1

    changed = 0
    with db_connection() as db:
        for topic_id, content in parsed:
            row = db.execute("SELECT content FROM topics WHERE id = ?", (topic_id,)).fetchone()
            serialized = json.dumps(content, ensure_ascii=False)
            if row and row[0] != serialized:
                db.execute("UPDATE topics SET content = ? WHERE id = ?", (serialized, topic_id))
                changed += 1
        db.commit()
    _log(f"[PHONETIC-COMPLETE] filled {filled} blank row(s) across {changed} topic(s) in one batch call.")
    if filled:
        bump_version()
    return filled


'''
if s.count(helper_marker) != 1:
    raise SystemExit(f"helper marker count={s.count(helper_marker)}")
s = s.replace(helper_marker, helper + helper_marker, 1)
p.write_text(s, encoding="utf-8")

print("patch applied")
