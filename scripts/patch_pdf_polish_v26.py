from pathlib import Path
import runpy

root = Path(__file__).resolve().parents[1]
p = root / 'services' / 'pdf_academic_renderer.py'
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

patch_path = root / 'scripts' / 'patch_pdf_publication_polish_v28.py'
if patch_path.exists():
    runpy.run_path(str(patch_path), run_name='__main__')
else:
    print('v26 chain warning: patch_pdf_publication_polish_v28.py not found')

# The downloadable course PDF is rendered directly in server.py, not by the
# academic renderer above. Make that endpoint inherit courses.material_language
# unless the caller explicitly supplies ?lang=en/tr.
sp = root / 'server.py'
ss = sp.read_text(encoding='utf-8')
old_lang = '''        parsed = urlparse(self.path)\n        qp = parse_qs(parsed.query)\n        lang = qp.get("lang", ["en"])[0].lower()\n        if lang not in ("en", "tr"):\n            lang = "en"\n        is_tr = (lang == "tr")\n'''
new_lang = '''        parsed = urlparse(self.path)\n        qp = parse_qs(parsed.query)\n        requested_lang = (qp.get("lang", [None])[0] or "").lower()\n        lang = requested_lang if requested_lang in ("en", "tr") else "en"\n        is_tr = (lang == "tr")\n'''
if old_lang in ss:
    ss = ss.replace(old_lang, new_lang, 1)

old_query = '                    "SELECT id, name, language, level, semester FROM courses WHERE id = ?",\n'
new_query = '                    "SELECT id, name, language, level, semester, material_language FROM courses WHERE id = ?",\n'
if old_query in ss:
    ss = ss.replace(old_query, new_query, 1)

semester = '                semester     = c_row[4] or ""\n'
locale = '''                semester     = c_row[4] or ""\n                course_material_language = str(c_row[5] or "").strip().lower()\n                if requested_lang not in ("en", "tr") and course_material_language in ("en", "tr"):\n                    lang = course_material_language\n                    is_tr = (lang == "tr")\n                level_word = "Seviye" if is_tr else "Level"\n'''
if 'course_material_language = str(c_row[5]' not in ss:
    if semester not in ss:
        raise RuntimeError('v26 actual-export locale anchor missing')
    ss = ss.replace(semester, locale, 1)

old_type = '''        def type_label(t):\n            pair = TYPE_LABELS.get(t, (t.replace("_", " ").title(), t.replace("_", " ").title()))\n            return pair[1] if is_tr else pair[0]\n'''
new_type = '''        def type_label(t):\n            raw = str(t or "lesson").strip()\n            key = raw.lower().replace("-", "_").replace(" ", "_")\n            extra = {"pronunciation": ("Pronunciation", "Telaffuz"), "communication": ("Communication", "İletişim"), "lesson": ("Lesson", "Ders"), "conversation": ("Conversation", "Konuşma"), "assessment": ("Assessment", "Değerlendirme"), "exercise": ("Exercise", "Alıştırma"), "review": ("Review", "Tekrar"), "reading": ("Reading", "Okuma"), "culture": ("Culture", "Kültür")}\n            pair = TYPE_LABELS.get(key) or extra.get(key)\n            if pair:\n                return pair[1] if is_tr else pair[0]\n            return raw.replace("_", " ").title()\n'''
if old_type in ss:
    ss = ss.replace(old_type, new_type, 1)

checks = ['requested_lang =', 'semester, material_language FROM courses', 'course_material_language = str(c_row[5]', '"pronunciation": ("Pronunciation", "Telaffuz")', '"communication": ("Communication", "İletişim")']
missing = [x for x in checks if x not in ss]
if missing:
    raise RuntimeError('v26 actual-export locale verification failed: ' + ', '.join(missing))
sp.write_text(ss, encoding='utf-8')
print('Applied v26 actual-export course locale + topic label normalization')
