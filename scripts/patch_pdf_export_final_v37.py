from pathlib import Path

p = Path(__file__).resolve().parents[1] / "server.py"
s = p.read_text(encoding="utf-8")

old_lang = '''        parsed = urlparse(self.path)\n        qp = parse_qs(parsed.query)\n        lang = qp.get("lang", ["en"])[0].lower()\n        if lang not in ("en", "tr"):\n            lang = "en"\n        is_tr = (lang == "tr")\n'''
new_lang = '''        parsed = urlparse(self.path)\n        qp = parse_qs(parsed.query)\n        requested_lang = (qp.get("lang", [None])[0] or "").lower()\n        lang = requested_lang if requested_lang in ("en", "tr") else "en"\n        is_tr = (lang == "tr")\n'''
if old_lang in s:
    s = s.replace(old_lang, new_lang, 1)
elif "requested_lang =" not in s:
    raise RuntimeError("v37 PDF language anchor missing")

old_query = '                    "SELECT id, name, language, level, semester FROM courses WHERE id = ?",\n'
new_query = '                    "SELECT id, name, language, level, semester, material_language FROM courses WHERE id = ?",\n'
if old_query in s:
    s = s.replace(old_query, new_query, 1)
elif "semester, material_language FROM courses" not in s:
    raise RuntimeError("v37 PDF course query anchor missing")

semester_line = '                semester     = c_row[4] or ""\n'
locale_block = '''                semester     = c_row[4] or ""\n                course_material_language = str(c_row[5] or "").strip().lower()\n                if requested_lang not in ("en", "tr") and course_material_language in ("en", "tr"):\n                    lang = course_material_language\n                    is_tr = (lang == "tr")\n'''
if "course_material_language = str(c_row[5]" not in s:
    if semester_line not in s:
        raise RuntimeError("v37 PDF locale insertion anchor missing")
    s = s.replace(semester_line, locale_block, 1)

# Normalize topic type keys so values like "Pronunciation" and "Communication"
# hit the localized label map instead of falling back to English title-case text.
old_type = '''        def type_label(t):\n            pair = TYPE_LABELS.get(t, (t.replace("_", " ").title(), t.replace("_", " ").title()))\n            return pair[1] if is_tr else pair[0]\n'''
new_type = '''        def type_label(t):\n            raw = str(t or "lesson").strip()\n            key = raw.lower().replace("-", "_").replace(" ", "_")\n            extra = {\n                "pronunciation": ("Pronunciation", "Telaffuz"),\n                "communication": ("Communication", "İletişim"),\n                "lesson": ("Lesson", "Ders"),\n                "conversation": ("Conversation", "Konuşma"),\n                "assessment": ("Assessment", "Değerlendirme"),\n                "exercise": ("Exercise", "Alıştırma"),\n                "review": ("Review", "Tekrar"),\n                "reading": ("Reading", "Okuma"),\n                "culture": ("Culture", "Kültür"),\n            }\n            pair = TYPE_LABELS.get(key) or extra.get(key)\n            if pair:\n                return pair[1] if is_tr else pair[0]\n            return raw.replace("_", " ").title()\n'''
if old_type in s:
    s = s.replace(old_type, new_type, 1)
elif '"pronunciation": ("Pronunciation", "Telaffuz")' not in s:
    raise RuntimeError("v37 PDF type-label anchor missing")

# Localize generic topic fallback as well.
s = s.replace('f\'<div class="topic-title">{E(top_title or "Topic")}\'', 'f\'<div class="topic-title">{E(top_title or ("Konu" if is_tr else "Topic"))}\'', 1)

required = [
    "requested_lang =",
    "semester, material_language FROM courses",
    "course_material_language = str(c_row[5]",
    '"pronunciation": ("Pronunciation", "Telaffuz")',
    '"communication": ("Communication", "İletişim")',
]
missing = [x for x in required if x not in s]
if missing:
    raise RuntimeError("v37 PDF finalization incomplete: " + ", ".join(missing))

p.write_text(s, encoding="utf-8")
print("Applied v37: course-aware PDF localization + normalized topic labels")
