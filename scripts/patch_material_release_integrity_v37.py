from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

mission = "MISSION: make only high-confidence surgical repairs required for publication quality. Do not rewrite correct content for stylistic preference.\n"
release = """MISSION: make only high-confidence surgical repairs required for publication quality. Do not rewrite correct content for stylistic preference.

UNIVERSAL RELEASE INTEGRITY:
- MCQ SELF-CONSISTENCY: every MCQ has exactly four distinct non-empty options and exactly one defensible keyed answer. The answer must be one option, and the explanation must defend that same answer rather than naming, implying, calculating, translating, or justifying another one. Repair stem/options/answer/explanation together when needed.
- INTERNAL CONSISTENCY: compare every rule, summary, example, dialogue, table and assessment claim inside the lesson. No later statement may contradict an earlier taught rule, and no explanation may classify a meaning or construction under the wrong grammatical category merely because a nearby pattern looks similar.
- RULE-SCOPE CALIBRATION: distinguish productive rules from regular tendencies, restricted patterns, lexical conventions and exceptions. Do not say all/always/never/only/must/impossible/without exception unless the explicitly stated scope is genuinely exceptionless. Cultural tendencies and usage preferences must be scoped as typical/common/standard where appropriate rather than universalized.
- WRITING-SYSTEM INTEGRITY: non-Latin target-language text uses authentic native script for ordinary examples, dialogues and assessments. Romanization/transliteration may supplement it or be the explicit skill under test, but may not silently replace native script.
- PHONETIC/NOTATION TRUTH: IPA, phonemic notation, transliteration, romanization and learner respelling remain distinguishable. A pedagogical approximation is never presented as exact phonetic truth.
- MEANING AND CAUSALITY: preserve person, number, polarity, time, quantity, role, referent and communicative force. Never invent morphology, etymology, derivation or a productive rule from surface resemblance.
- TABLE/DIALOGUE COHERENCE: vocabulary columns describe the same lexical item and sense; dialogue roles, politeness, demonstratives and references stay coherent.
- CEFR FIT: keep A1-A2 concrete and transparent, B1-B2 productively contextual, C1-C2 nuanced. Do not rewrite correct material for elegance alone.
"""
if "UNIVERSAL RELEASE INTEGRITY:" not in s:
    if mission not in s:
        raise RuntimeError('v37 publication mission anchor missing')
    s = s.replace(mission, release, 1)

helper = r'''
def _material_release_integrity_v37(data, language, level):
    """Deterministic final fail-closed validation; semantic work is done by the single publication audit."""
    from services.material_quality_guard import enforce_material_integrity
    return enforce_material_integrity(data, language=language, material_language="tr") if isinstance(data, dict) else data
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
        raise RuntimeError('v37 publication audit anchor missing')
    pos += len(publication)
    s = s[:pos] + call + s[pos:]

# There must be no second semantic model call in v37.
start = s.find('def _material_release_integrity_v37(')
end = s.find('\ndef ', start + 5)
body = s[start:end if end > start else len(s)]
if '_call_ai(' in body:
    raise RuntimeError('v37 must remain deterministic-only')

required = [
    'MCQ SELF-CONSISTENCY:',
    'INTERNAL CONSISTENCY:',
    'RULE-SCOPE CALIBRATION:',
    'WRITING-SYSTEM INTEGRITY:',
    'PHONETIC/NOTATION TRUTH:',
    'enforce_material_integrity(data,',
    call.strip(),
]
missing = [x for x in required if x not in s]
if missing:
    raise RuntimeError('v37 verification failed: ' + ', '.join(missing))

p.write_text(s, encoding='utf-8')
print('Applied v37: universal rules in one semantic audit + deterministic release guard')
