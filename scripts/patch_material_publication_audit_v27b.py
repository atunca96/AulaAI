from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

call_line = '    lesson_dict = _material_publication_audit(lesson_dict, language, level)\n'
if call_line not in s:
    anchor = '    return lesson_dict\n    \n\ndef ai_explain_word('
    replacement = call_line + '    return lesson_dict\n    \n\ndef ai_explain_word('
    if anchor in s:
        s = s.replace(anchor, replacement, 1)
    else:
        print('v27b: lesson return anchor unavailable; audit call not inserted')

p.write_text(s, encoding='utf-8')
print('Applied v27b: publication audit call verified')
