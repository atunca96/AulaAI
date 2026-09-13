from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')
policy = (root / 'config' / 'material_quality_v33.txt').read_text(encoding='utf-8').strip()

# Fold the publication-quality contract into the existing lesson-generation request.
# This preserves semantic QA without paying for a second full-context model call.
tag = 'AULAAI_INLINE_PUBLICATION_QA_V46'
anchor = '<output_schema>\n'
if tag not in s:
    if anchor not in s:
        raise RuntimeError('v46 generation anchor missing')
    inline = (
        tag + ': Before returning final JSON, silently inspect and repair your own draft against '
        'the following release contract. Do not describe the audit, do not add audit fields, and do '
        'not reduce lesson coverage merely to avoid checking it. ' + policy + '\n\n'
    )
    s = s.replace(anchor, inline + anchor, 1)

# Remove the expensive post-generation whole-lesson semantic audit. The deterministic
# structural release guard remains active after generation.
call = '    lesson_dict = _material_publication_audit(lesson_dict, language, level)\n'
removed = s.count(call)
s = s.replace(call, '')

release = '    lesson_dict = _material_release_integrity_v37(lesson_dict, language, level, material_language=material_language)\n'
if release not in s:
    raise RuntimeError('v46 deterministic release guard missing')
if tag not in s:
    raise RuntimeError('v46 inline quality contract missing')
if call in s:
    raise RuntimeError('v46 semantic publication audit call still active')
if removed < 1:
    raise RuntimeError('v46 expected at least one publication audit call to remove')

p.write_text(s, encoding='utf-8')
print(f'Applied v46: inlined release QA and removed {removed} duplicate semantic audit call(s)')
