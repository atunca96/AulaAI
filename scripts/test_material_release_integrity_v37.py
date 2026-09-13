from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_quality_guard import enforce_material_integrity, validate_mcq


def mcq(prompt, options, answer, explanation='ok', **extra):
    q = {'type': 'mcq', 'prompt': prompt, 'options': options, 'answer': answer, 'explanation': explanation}
    q.update(extra)
    return q


valid = mcq('Choose the correct form.', ['alpha', 'beta', 'gamma', 'delta'], 'beta')
assert validate_mcq(valid) == (True, '')

bad_key = mcq('Choose.', ['a', 'b', 'c', 'd'], 'e')
dupe = mcq('Choose.', ['a', 'a', 'c', 'd'], 'a')
localized_bad = mcq('Choose.', ['a', 'b', 'c', 'd'], 'b', options_tr=['a', 'b'])
lesson = {'pages': [valid, bad_key, dupe, localized_bad, {'type': 'overview', 'text': 'Keep me'}]}
out = enforce_material_integrity(lesson)
assert len(out['pages']) == 2, out
assert out['pages'][0]['answer'] == 'beta'
assert out['pages'][1]['type'] == 'overview'
assert len(out.get('_integrity_removed_mcq', [])) == 3

for opts, ans in [
    (['дом', 'дома', 'дому', 'домом'], 'дому'),
    (['كتاب', 'كتب', 'بالكتاب', 'للكتاب'], 'كتاب'),
    (['책', '집', '물', '길'], '집'),
    (['Haus', 'Häuser', 'Hause', 'Hauses'], 'Haus'),
    (['σπίτι', 'δρόμος', 'νερό', 'βιβλίο'], 'νερό'),
]:
    ok, reason = validate_mcq(mcq('Q', opts, ans))
    assert ok, (opts, ans, reason)

engine = Path('services/ai_engine.py').read_text(encoding='utf-8')
for marker in (
    'def _material_release_integrity_v37(',
    'MCQ SELF-CONSISTENCY:',
    'INTERNAL CONSISTENCY:',
    'RULE-SCOPE CALIBRATION:',
    'WRITING-SYSTEM INTEGRITY:',
    'PHONETIC/NOTATION TRUTH:',
    'lesson_dict = _material_release_integrity_v37(lesson_dict, language, level)',
):
    assert marker in engine, marker

# Performance invariant after v46: semantic publication QA is folded into the
# existing generation request. There must be no second whole-lesson LLM audit.
publication_call = 'lesson_dict = _material_publication_audit(lesson_dict, language, level)'
assert engine.count(publication_call) == 0, engine.count(publication_call)
assert 'AULAAI_INLINE_PUBLICATION_QA_V46' in engine
assert '_material_page_release_audit(' not in engine
start = engine.index('def _material_release_integrity_v37(')
end = engine.find('\ndef ', start + 5)
body = engine[start:end if end > start else len(engine)]
assert '_call_ai(' not in body

print('v37 deterministic release guard + v46 single-call inline QA self-test passed')
