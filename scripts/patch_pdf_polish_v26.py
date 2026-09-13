from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'pdf_academic_renderer.py'
s = p.read_text(encoding='utf-8')

marker = "    'phonetics': ('Phonetics', 'Fonetik'),\n"
if "'alphabet': ('Alphabet', 'Alfabe')," not in s and marker in s:
    s = s.replace(marker, marker + "    'alphabet': ('Alphabet', 'Alfabe'),\n", 1)

old_cover = "f'<div class=\"cover-sub\">{_e(course_lang)} · {level_word} {_e(course_level)}{sem}</div>'"
new_cover = "f'<div class=\"cover-sub\">{_e(_target_language_label(course_lang, is_tr))} · {level_word} {_e(course_level)}{sem}</div>'"
if old_cover in s:
    s = s.replace(old_cover, new_cover, 1)

p.write_text(s, encoding='utf-8')
print('Applied v26 PDF polish')
