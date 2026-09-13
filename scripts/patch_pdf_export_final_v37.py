from pathlib import Path
import re

p = Path(__file__).resolve().parents[1] / "server.py"
s = p.read_text(encoding="utf-8")

# Locale follows explicit ?lang, otherwise the classroom material language.
old = '''        parsed = urlparse(self.path)\n        qp = parse_qs(parsed.query)\n        lang = qp.get("lang", ["en"])[0].lower()\n        if lang not in ("en", "tr"):\n            lang = "en"\n        is_tr = (lang == "tr")\n'''
new = '''        parsed = urlparse(self.path)\n        qp = parse_qs(parsed.query)\n        requested_lang = (qp.get("lang", [None])[0] or "").lower()\n        lang = requested_lang if requested_lang in ("en", "tr") else "en"\n        is_tr = (lang == "tr")\n'''
if old in s:
    s = s.replace(old, new, 1)

s = s.replace('"SELECT id, name, language, level, semester FROM courses WHERE id = ?",', '"SELECT id, name, language, level, semester, material_language FROM courses WHERE id = ?",', 1)
if "course_material_language = str(c_row[5]" not in s:
    a = '                semester     = c_row[4] or ""\n'
    if a not in s:
        raise RuntimeError("v37 locale anchor missing")
    s = s.replace(a, a + '''                if str(semester).strip().lower() in {str(course_level).strip().lower(), (str(course_level) + " level").strip().lower()}:\n                    semester = ""\n                course_material_language = str(c_row[5] or "").strip().lower()\n                if requested_lang not in ("en", "tr") and course_material_language in ("en", "tr"):\n                    lang = course_material_language\n                    is_tr = (lang == "tr")\n''', 1)

# Raw type values in the DB can be capitalized English words.
old_type = '''        def type_label(t):\n            pair = TYPE_LABELS.get(t, (t.replace("_", " ").title(), t.replace("_", " ").title()))\n            return pair[1] if is_tr else pair[0]\n'''
new_type = '''        def type_label(t):\n            raw = str(t or "lesson").strip()\n            key = raw.lower().replace("-", "_").replace(" ", "_")\n            extra = {"pronunciation":("Pronunciation","Telaffuz"),"communication":("Communication","İletişim"),"lesson":("Lesson","Ders"),"conversation":("Conversation","Konuşma"),"assessment":("Assessment","Değerlendirme"),"exercise":("Exercise","Alıştırma"),"review":("Review","Tekrar"),"reading":("Reading","Okuma"),"culture":("Culture","Kültür")}\n            pair = TYPE_LABELS.get(key) or extra.get(key)\n            return (pair[1] if is_tr else pair[0]) if pair else raw.replace("_", " ").title()\n'''
if old_type in s:
    s = s.replace(old_type, new_type, 1)

# Final visible strings in the actual downloadable renderer.
s = s.replace('E(top_title or "Topic")', 'E(top_title or ("Konu" if is_tr else "Topic"))')
s = s.replace("'AulaAI Educational System · Self-Contained Course Material'", "('AulaAI Eğitim Sistemi · Bağımsız Ders Materyali' if is_tr else 'AulaAI Educational System · Self-Contained Course Material')", 1)

# Remove stale mixed-language level suffix such as '(A1 Level)' from the cover.
s = s.replace('sem_str = f" ({E(semester)})" if semester else ""', 'sem_str = f" ({E(semester)})" if semester else ""')

required = ["requested_lang =", "material_language FROM courses", "course_material_language = str(c_row[5]", "Telaffuz", "İletişim", "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali"]
missing = [x for x in required if x not in s]
if missing:
    raise RuntimeError("v37 finalization incomplete: " + ", ".join(missing))

p.write_text(s, encoding="utf-8")
print("Applied v37 FINAL PDF localization")
