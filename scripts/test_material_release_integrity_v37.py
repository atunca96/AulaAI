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

# Script-agnostic structural validation.
for opts, ans in [
    (['дом', 'дома', 'дому', 'домом'], 'дому'),
    (['كتاب', 'كتب', 'بالكتاب', 'للكتاب'], 'كتاب'),
    (['책', '집', '물', '길'], '집'),
    (['Haus', 'Häuser', 'Hause', 'Hauses'], 'Haus'),
    (['σπίτι', 'δρόμος', 'νερό', 'βιβλίο'], 'νερό'),
    (['家', '学校', '水', '道'], '学校'),
]:
    ok, reason = validate_mcq(mcq('Q', opts, ans))
    assert ok, (opts, ans, reason)

# Universal Unicode repair: impossible/non-text corruption is removed without
# damaging combining marks, RTL controls, ZWJ/ZWNJ, CJK, Cyrillic or Hangul.
corrupt = {
    'pages': [{
        'type': 'overview',
        'text': 'mask\ufffeVA | cafe\u0301 | العربية\u200f | فارسی\u200cها | 한글 | 日本語 | русский'
    }]
}
repaired = enforce_material_integrity(corrupt)
text = repaired['pages'][0]['text']
assert 'mask-VA' in text, text
assert 'café' in text, text
assert '\ufffe' not in text and '\ufffd' not in text
assert 'العربية\u200f' in text
assert 'فارسی\u200cها' in text
assert '한글' in text and '日本語' in text and 'русский' in text
assert repaired.get('_integrity_unicode_repairs') == 1

engine = Path('services/ai_engine.py').read_text(encoding='utf-8')
for marker in (
    'def _material_release_integrity_v37(',
    'MCQ SELF-CONSISTENCY:',
    'INTERNAL CONSISTENCY:',
    'RULE-SCOPE CALIBRATION:',
    'WRITING-SYSTEM INTEGRITY:',
    'PHONETIC/NOTATION TRUTH:',
    'lesson_dict = _material_release_integrity_v37(lesson_dict, language, level)',
    'required predicates',
    'stress, position, neighboring sounds or register',
):
    assert marker in engine, marker

# The core quality contract must be language agnostic: no language-specific
# exception block is allowed in the shared policy.
policy = Path('config/material_quality_v33.txt').read_text(encoding='utf-8')
for forbidden in ('Japanese', 'Chinese', 'Arabic', 'Russian', 'Spanish', 'German'):
    assert forbidden not in policy, forbidden

# Performance invariant: exactly one semantic whole-lesson publication pass,
# no per-page semantic loop, and v37 itself is deterministic-only.
publication_call = 'lesson_dict = _material_publication_audit(lesson_dict, language, level)'
assert engine.count(publication_call) == 1, engine.count(publication_call)
assert '_material_page_release_audit(' not in engine
start = engine.index('def _material_release_integrity_v37(')
end = engine.find('\ndef ', start + 5)
body = engine[start:end if end > start else len(engine)]
assert '_call_ai(' not in body

print('v39 universal quality + Unicode integrity + single-audit performance self-test passed')
