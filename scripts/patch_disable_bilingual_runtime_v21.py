from pathlib import Path

root = Path(__file__).resolve().parents[1]
pipeline_path = root / 'services' / 'legacy' / 'pdf_pipeline.py'
ai_path = root / 'services' / 'ai_engine.py'

# 1) Remove the post-generation bilingual finalizer. The lesson generator already
# returns bilingual material fields; a second translation pass is both redundant
# and destructive for pronunciation pedagogy.
p = pipeline_path.read_text(encoding='utf-8')
old = '''        _log(f"Phase 2 Complete for {course_id}.")
        try:
            with db_connection() as db:
                db.execute("UPDATE courses SET build_stage = 'finalizing', build_message = 'Finalizing bilingual translations...' WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')", (course_id, gen_id, gen_id))
                db.commit()
            from services.bilingual_finisher import finalize_course_bilingual_data
            finalize_course_bilingual_data(course_id)
        except Exception as b_err:
            _log(f"Warning: finalize_course_bilingual_data failed: {b_err}")
        with db_connection() as db:
'''
new = '''        _log(f"Phase 2 Complete for {course_id}.")
        _log("Bilingual post-processor disabled: using persisted bilingual lesson fields from the AI engine.")
        with db_connection() as db:
'''
count = p.count(old)
if count != 1:
    raise RuntimeError(f'v21 bilingual finalizer anchor expected 1, found {count}')
p = p.replace(old, new, 1)
pipeline_path.write_text(p, encoding='utf-8')

# 2) Reject alphabet / pronunciation lessons that are not already bilingual at
# generation time. This keeps the UI stateless: no runtime translation, no lazy
# replacement, no secondary model pass.
ai = ai_path.read_text(encoding='utf-8')
marker = 'AULA_BILINGUAL_PRONUNCIATION_GATE_V21'
if marker not in ai:
    anchor = '        return _sanitize_deep_bilingual(data)\n'
    if ai.count(anchor) < 1:
        raise RuntimeError('v21 normalize return anchor missing')
    gate = '''        # AULA_BILINGUAL_PRONUNCIATION_GATE_V21
        _topic_l = str(topic or '').lower()
        _is_pronunciation_topic = any(k in _topic_l for k in (
            'alphabet', 'alfabeto', 'alfabe', 'letter', 'letters', 'harf',
            'pronunciation', 'pronunciación', 'telaffuz', 'phonetic', 'fonetik',
            'vowel', 'consonant', 'vocal', 'consonante', 'sound', 'sesli', 'sessiz'
        ))
        if _is_pronunciation_topic:
            _missing = []
            for _pg in data.get('pages', []):
                if not isinstance(_pg, dict):
                    continue
                for _it in _pg.get('items', []) if isinstance(_pg.get('items', []), list) else []:
                    if not isinstance(_it, dict):
                        continue
                    _term = str(_it.get('term') or _it.get('word') or '').strip()
                    if not _term:
                        continue
                    _en = str(_it.get('explanation_en') or '').strip()
                    _tr = str(_it.get('explanation_tr') or '').strip()
                    if not _en or not _tr:
                        _missing.append(_term)
            if _missing:
                # Returning an empty lesson makes generate_full_lesson retry the
                # original generator instead of translating after the fact.
                print(f"[LESSON-GATE] Missing persisted bilingual pronunciation for {len(_missing)} items: {_missing[:8]}", flush=True)
                return {'pages': []}

'''
    ai = ai.replace(anchor, gate + anchor, 1)

# Strengthen the generator contract in case a provider tries to omit the fields.
prompt_anchor = 'ALPHABET_PRONUNCIATION_PERSISTENCE_V19:'
if prompt_anchor in ai and 'If any pronunciation item lacks either field, the lesson is invalid' not in ai:
    ai = ai.replace(
        '- Never use a generic definition of a letter or generic target-language pronunciation prose.\n',
        '- Never use a generic definition of a letter or generic target-language pronunciation prose.\n- If any pronunciation item lacks either explanation_en or explanation_tr, the lesson is invalid and must be regenerated before returning.\n',
        1,
    )

ai_path.write_text(ai, encoding='utf-8')

# 3) Hard build checks: no finalizer call may remain in Phase 2 and the generation
# gate must exist.
final_p = pipeline_path.read_text(encoding='utf-8')
if 'finalize_course_bilingual_data(course_id)' in final_p:
    raise RuntimeError('v21 bilingual finalizer call still present')
final_ai = ai_path.read_text(encoding='utf-8')
if 'AULA_BILINGUAL_PRONUNCIATION_GATE_V21' not in final_ai:
    raise RuntimeError('v21 bilingual pronunciation gate missing')

print('Applied v21: bilingual post-processor disabled; persisted dual-language pronunciation required at generation time')
