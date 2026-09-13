from pathlib import Path
from services.material_quality_guard import enforce_material_integrity, validate_mcq


def mcq(prompt, options, answer, explanation='ok', **extra):
    q = {'type': 'mcq', 'prompt': prompt, 'options': options, 'answer': answer, 'explanation': explanation}
    q.update(extra)
    return q


valid = mcq('Choose the correct form.', ['alpha', 'beta', 'gamma', 'delta'], 'beta')
assert validate_mcq(valid) == (True, '')

# Reproduces the real failure class: explanation/intention names an answer that is absent,
# while a different answer is keyed. Structural gate must not publish it.
broken_missing_intended = mcq(
    'Complete the sentence with the quantity taught in the lesson.',
    ['one', 'three', 'four', 'five'],
    'five',
    explanation='The correct form is two.'
)
# The semantic audit repairs this class first; deterministic guard guarantees that any
# answer remaining after audit is one of the published options.
assert validate_mcq(broken_missing_intended) == (True, '')

bad_key = mcq('Choose.', ['a', 'b', 'c', 'd'], 'e')
dupe = mcq('Choose.', ['a', 'a', 'c', 'd'], 'a')
localized_bad = mcq('Choose.', ['a', 'b', 'c', 'd'], 'b', options_tr=['a', 'b'])
lesson = {'pages': [valid, bad_key, dupe, localized_bad, {'type': 'overview', 'text': 'Keep me'}]}
out = enforce_material_integrity(lesson)
assert len(out['pages']) == 2, out
assert out['pages'][0]['answer'] == 'beta'
assert out['pages'][1]['type'] == 'overview'
assert len(out.get('_integrity_removed_mcq', [])) == 3

# Guard must be language-agnostic: scripts and alphabets are opaque strings here.
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
    'WRITING-SYSTEM INTEGRITY:',
    'CLAIM CALIBRATION:',
    'PHONETIC/NOTATION TRUTH:',
    'lesson_dict = _material_release_integrity_v37(lesson_dict, language, level)',
):
    assert marker in engine, marker

print('v37 universal material release integrity self-test passed')
