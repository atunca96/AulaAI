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
assert len(out['pages']) == 5, out
assert out['pages'][0]['answer'] == 'beta'
assert out['pages'][4]['type'] == 'overview'
assert '_integrity_removed_mcq' not in out

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
prompt_source = Path('services/material_generation_prompt.py').read_text(encoding='utf-8')

# Runtime release architecture must remain deterministic and canonical-prompt wired.
for marker in (
    'def _material_release_integrity_v37(',
    'lesson_dict = _material_release_integrity_v37(lesson_dict, language, level, material_language=material_language)',
    '# AULAAI_CANONICAL_MATERIAL_PROMPT',
    'from services.material_generation_prompt import build_material_prompts',
    'system_prompt, user_prompt = build_material_prompts(',
):
    assert marker in engine, marker

# Semantic publication invariants now belong to the canonical prompt source of truth,
# not to versioned V49/V50/V51 strings embedded in ai_engine.py.
for marker in (
    '<language_integrity>',
    '<pronunciation>',
    '<linguistic_truth>',
    '<mcq_quality>',
    'one authoritative learner-facing pronunciation system',
    'The stem itself must contain all answer-relevant facts',
    'Never infer gender, nationality, ethnicity, profession, language ability',
    '<final_same_pass_check>',
):
    assert marker in prompt_source, marker

publication_call = 'lesson_dict = _material_publication_audit(lesson_dict, language, level)'
assert engine.count(publication_call) == 0, engine.count(publication_call)
assert '_material_page_release_audit(' not in engine
start = engine.index('def _material_release_integrity_v37(')
end = engine.find('\ndef ', start + 5)
body = engine[start:end if end > start else len(engine)]
assert '_call_ai(' not in body

print('v37 deterministic release guard + canonical prompt quality self-test passed')
