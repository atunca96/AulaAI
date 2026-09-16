from pathlib import Path

p = Path('services/legacy/pdf_pipeline.py')
s = p.read_text(encoding='utf-8')

# Persist both title tracks for synthetic unit-assessment topics.
old = '''        content = build_unit_assessment_content(unit["title"], questions, material_language, unit_title_tr=unit.get("title_tr"))\n        title = unit_assessment_title(unit["title"], material_language, unit_title_tr=unit.get("title_tr"))\n        with db_connection() as db:\n            existing = db.execute(\n                "SELECT id FROM topics WHERE chapter_id = ? AND type = ?",\n                (unit["chapter_id"], UNIT_ASSESSMENT_TYPE),\n            ).fetchone()\n            payload = json.dumps(content, ensure_ascii=False)\n            if existing:\n                db.execute("UPDATE topics SET title = ?, content = ? WHERE id = ?",\n                           (title, payload, existing[0]))\n            else:\n                db.execute(\n                    "INSERT INTO topics (id, chapter_id, type, title, content, sort_order) VALUES (?,?,?,?,?,?)",\n                    (_uid(), unit["chapter_id"], UNIT_ASSESSMENT_TYPE, title, payload, unit["next_sort"]),\n                )\n            db.commit()\n'''
new = '''        content = build_unit_assessment_content(unit["title"], questions, material_language, unit_title_tr=unit.get("title_tr"))\n        title_en = unit_assessment_title(unit["title"], "en", unit_title_tr=unit.get("title_tr"))\n        title_tr = unit_assessment_title(unit["title"], "tr", unit_title_tr=unit.get("title_tr"))\n        with db_connection() as db:\n            existing = db.execute(\n                "SELECT id FROM topics WHERE chapter_id = ? AND type = ?",\n                (unit["chapter_id"], UNIT_ASSESSMENT_TYPE),\n            ).fetchone()\n            payload = json.dumps(content, ensure_ascii=False)\n            if existing:\n                db.execute("UPDATE topics SET title = ?, title_tr = ?, content = ? WHERE id = ?",\n                           (title_en, title_tr, payload, existing[0]))\n            else:\n                db.execute(\n                    "INSERT INTO topics (id, chapter_id, type, title, title_tr, content, sort_order) VALUES (?,?,?,?,?,?,?)",\n                    (_uid(), unit["chapter_id"], UNIT_ASSESSMENT_TYPE, title_en, title_tr, payload, unit["next_sort"]),\n                )\n            db.commit()\n'''
if s.count(old) != 1:
    raise SystemExit(f'assessment persistence match count={s.count(old)}')
s = s.replace(old, new, 1)

# Run one bounded completion pass after all lesson topics exist and before assessments.
marker = '        # ── PHASE 2b: UNIT ASSESSMENTS ──\n'
insert = '''        # ── PHASE 2a.5: PHONETIC COMPLETENESS ──\n        # Material generation occasionally returns a real vocabulary row with an\n        # empty phonetic field. Repair only those blanks, once per class, without\n        # touching any existing transcription.\n        try:\n            _repair_missing_phonetics(course_id, language)\n        except Exception as phon_err:\n            _log(f"[PHONETIC-COMPLETE] repair skipped: {phon_err}")\n\n'''
if s.count(marker) != 1:
    raise SystemExit(f'phase marker match count={s.count(marker)}')
s = s.replace(marker, insert + marker, 1)

helper_marker = 'UNIT_ASSESSMENT_TYPE = "unit_assessment"\n'
helper = r'''def _repair_missing_phonetics(course_id, language):
    """Fill genuinely blank vocabulary-table phonetics in one conditional batch.

    Existing non-empty transcriptions are authoritative and never overwritten.
    Exact input-term echoing prevents the completion call from mutating spelling.
    """
    with db_connection() as db:
        rows = db.execute(
            "SELECT id, content FROM topics WHERE chapter_id IN "
            "(SELECT id FROM chapters WHERE course_id = ?) "
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
            phonetic = str(entry.get("phonetic") or "").strip()
            if not term or not any(ch.isalpha() for ch in term):
                continue
            if phonetic:
                if len(examples) < 16:
                    examples.append((term, phonetic))
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
            if not isinstance(page, dict):
                continue
            for key in ("items", "vocabulary", "words"):
                scan(page.get(key))

    if not missing:
        _log("[PHONETIC-COMPLETE] no blank phonetic rows.")
        return 0

    terms = list(missing)[:160]
    calibration = "\n".join(f"- {term}: {phon}" for term, phon in examples[:12]) or "(none)"
    prompt = f"""Fill missing phonetic transcriptions for a {language} language course.
Return ONLY valid JSON in this exact shape: {{"items":[{{"term":"EXACT INPUT TERM","phonetic":"[standard IPA]"}}]}}.
Preserve each term exactly. Return one item per input term. `phonetic` must be a pronunciation transcription, never a translation or a letter name. Match the IPA convention shown by the existing class examples. If a term genuinely has no spoken pronunciation, return an empty string.
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
        phonetic = str(item.get("phonetic") or "").strip()
        if term in allowed and phonetic and len(phonetic) <= 120:
            mapping[term] = phonetic

    filled = 0
    for term, entries in missing.items():
        phonetic = mapping.get(term)
        if not phonetic:
            continue
        for entry in entries:
            if not str(entry.get("phonetic") or "").strip():
                entry["phonetic"] = phonetic
                filled += 1

    changed_topics = 0
    with db_connection() as db:
        for topic_id, content in parsed:
            current = db.execute("SELECT content FROM topics WHERE id = ?", (topic_id,)).fetchone()
            serialized = json.dumps(content, ensure_ascii=False)
            if current and current[0] != serialized:
                db.execute("UPDATE topics SET content = ? WHERE id = ?", (serialized, topic_id))
                changed_topics += 1
        db.commit()

    _log(f"[PHONETIC-COMPLETE] filled {filled} blank row(s) across {changed_topics} topic(s) in one batch call.")
    if filled:
        bump_version()
    return filled


'''
if s.count(helper_marker) != 1:
    raise SystemExit(f'helper marker match count={s.count(helper_marker)}')
s = s.replace(helper_marker, helper + helper_marker, 1)
p.write_text(s, encoding='utf-8')
print('mainline patch applied')
