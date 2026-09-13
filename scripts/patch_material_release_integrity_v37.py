from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

helper = r'''
def _material_release_integrity_v37(data, language, level):
    """Final language-agnostic semantic audit followed by deterministic fail-closed MCQ validation."""
    from services.material_quality_guard import enforce_material_integrity
    if not isinstance(data, dict):
        return data
    system = f"""You are AulaAI's final release-integrity editor for {language} CEFR {level}. Return ONLY JSON {{"patches":[{{"path":"pages.12.answer","value":"..."}}]}}. Make only high-confidence corrections; preserve valid wording.

RELEASE INVARIANTS — APPLY TO EVERY LANGUAGE:
1) MCQ SELF-CONSISTENCY: every MCQ must have exactly four distinct non-empty options and exactly one defensible keyed answer. The `answer` value MUST be exactly one of the four option strings. The explanation MUST defend that same keyed option and must not name, imply, calculate, translate, or justify a different answer. If the stem asks for a quantity, grammatical form, meaning, register, case, tense, counter, classifier, particle, pronunciation, or other property, verify that the keyed option actually satisfies the stem. Never leave a correct explanation paired with a wrong key, or a correct key absent from the options.
2) LANGUAGE NECESSITY: the decisive evidence must be taught target-language knowledge, not arithmetic, trivia, stereotypes, family deduction, object-function guessing, or general world knowledge.
3) WRITING-SYSTEM INTEGRITY: when the target language normally uses a non-Latin script, ordinary target-language examples, dialogues, stems, blanks, and answer options use authentic native script. Romanization/transliteration may supplement native script or be the explicit skill under test, but must not silently replace it.
4) CLAIM CALIBRATION: words equivalent to always, never, only, must, impossible, without exception, or obligatory are allowed only when the claim is genuinely exceptionless in the explicitly stated scope. Otherwise scope the claim with standard usage, normally, generally, typically, in this construction, or equivalent wording. Beginner simplification is allowed when it remains true within a clearly stated scope.
5) PHONETIC/NOTATION TRUTH: keep IPA, phonemic notation, transliteration, romanization, and learner respelling distinguishable. Different legitimate detail levels are allowed; malformed notation or a pedagogical approximation presented as exact phonetic truth is not.
6) MEANING AND CAUSALITY: translations preserve person, number, polarity, time, quantity, role, referent and communicative force. Linguistic explanations must state the real cause; never invent morphology, etymology, derivation, or a productive rule from surface resemblance.
7) TABLE/DIALOGUE COHERENCE: vocabulary columns must describe the same lexical item and sense; dialogue roles, politeness, demonstratives and references must stay coherent.
8) CEFR FIT: keep A1-A2 concrete and transparent, B1-B2 productively contextual, C1-C2 nuanced. Do not rewrite correct material for elegance alone.

Patch only actual defects. For a broken MCQ, repair stem/options/answer/explanation together so the final item is internally consistent and has one answer."""
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    try:
        review = _call_ai([
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': payload},
        ], model=MODEL_STRUCTURAL, max_tokens=3200, temperature=0.0, json_mode=True, allow_fallback=False)
    except Exception as exc:
        print(f'[MATERIAL-QA-V37] semantic release audit unavailable: {exc}')
        review = None
    if isinstance(review, dict):
        for patch in (review.get('patches') or [])[:160]:
            if not isinstance(patch, dict):
                continue
            path = str(patch.get('path') or '')
            if path.startswith('pages.'):
                _apply_material_patch(data, path, patch.get('value'))
    return enforce_material_integrity(data)
'''

if 'def _material_release_integrity_v37(' not in s:
    anchor = "\ndef generate_full_lesson(topic, topic_type, language, count=6, level='A1', source_text=None, material_language=\"tr\"):\n"
    if anchor not in s:
        raise RuntimeError('v37 generate_full_lesson anchor missing')
    s = s.replace(anchor, '\n' + helper + anchor, 1)

call = "    lesson_dict = _material_release_integrity_v37(lesson_dict, language, level)\n"
if call not in s:
    publication = "    lesson_dict = _material_publication_audit(lesson_dict, language, level)\n"
    pos = s.rfind(publication)
    if pos < 0:
        raise RuntimeError('v37 final publication audit anchor missing')
    pos += len(publication)
    s = s[:pos] + call + s[pos:]

required = [
    'MCQ SELF-CONSISTENCY:',
    'WRITING-SYSTEM INTEGRITY:',
    'CLAIM CALIBRATION:',
    'PHONETIC/NOTATION TRUTH:',
    'enforce_material_integrity(data)',
    call.strip(),
]
missing = [x for x in required if x not in s]
if missing:
    raise RuntimeError('v37 verification failed: ' + ', '.join(missing))

p.write_text(s, encoding='utf-8')
print('Applied v37 universal semantic + deterministic release integrity gate')
