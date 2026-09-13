from pathlib import Path

p = Path(__file__).resolve().parents[1] / "server.py"
s = p.read_text(encoding="utf-8")

start = s.find("    def _export_course_pdf(self, course_id):\n")
end = s.find("    def _wipe_curriculum(self):\n", start)
if start < 0 or end < 0:
    raise RuntimeError("v40 live PDF exporter anchors missing")
body = s[start:end]

# v37 already normalizes topic keys. If an older body reaches here, upgrade it.
old_type = '''        def type_label(t):\n            pair = TYPE_LABELS.get(t, (t.replace("_", " ").title(), t.replace("_", " ").title()))\n            return pair[1] if is_tr else pair[0]\n'''
new_type = '''        def type_label(t):\n            raw = str(t or "lesson").strip()\n            key = raw.lower().replace("-", "_").replace(" ", "_")\n            extra = {"pronunciation":("Pronunciation","Telaffuz"),"communication":("Communication","İletişim"),"conversation":("Conversation","Konuşma"),"lesson":("Lesson","Ders"),"assessment":("Assessment","Değerlendirme"),"exercise":("Exercise","Alıştırma"),"review":("Review","Tekrar")}\n            pair = TYPE_LABELS.get(key) or extra.get(key)\n            return (pair[1] if is_tr else pair[0]) if pair else raw.replace("_", " ").title()\n'''
if old_type in body:
    body = body.replace(old_type, new_type, 1)

# Localize the target-language name shown on the cover.
if "def _pdf_language_name(" not in body:
    anchor = '        is_tr = (lang == "tr")\n'
    helper = '''        is_tr = (lang == "tr")\n\n        def _pdf_language_name(value):\n            raw = str(value or "").strip()\n            key = raw.casefold()\n            tr = {\n                "english":"İngilizce", "german":"Almanca", "spanish":"İspanyolca",\n                "french":"Fransızca", "italian":"İtalyanca", "portuguese":"Portekizce",\n                "russian":"Rusça", "chinese":"Çince", "japanese":"Japonca",\n                "arabic":"Arapça", "turkish":"Türkçe", "dutch":"Hollandaca",\n                "swedish":"İsveççe", "korean":"Korece", "greek":"Yunanca"\n            }\n            return tr.get(key, raw) if is_tr else raw\n'''
    if anchor not in body:
        raise RuntimeError("v40 language anchor missing")
    body = body.replace(anchor, helper, 1)

if 'E(_pdf_language_name(course_lang))' not in body:
    body = body.replace(
        'f\'<div class="cover-sub">{E(course_lang)} &middot; Seviye {E(course_level)}{sem_str}</div>\'',
        'f\'<div class="cover-sub">{E(_pdf_language_name(course_lang))} &middot; {"Seviye" if is_tr else "Level"} {E(course_level)}{sem_str}</div>\'',
        1,
    )
    body = body.replace(
        'f\'<div class="cover-sub">{E(_pdf_export_language_name(course_lang, is_tr))} &middot; {level_word} {E(course_level)}{sem_str}</div>\'',
        'f\'<div class="cover-sub">{E(_pdf_language_name(course_lang))} &middot; {"Seviye" if is_tr else "Level"} {E(course_level)}{sem_str}</div>\'',
        1,
    )

# v37 transforms the raw footer before v40 runs, so handle both pre- and post-v37 forms.
footer_replacements = (
    ('                        "AulaAI Educational System \\u2014 Self-Contained Course Material",\n', '                        ("AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System — Self-Contained Course Material"),\n'),
    ('                        "AulaAI Educational System — Self-Contained Course Material",\n', '                        ("AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System — Self-Contained Course Material"),\n'),
    ("                        ('AulaAI Eğitim Sistemi · Bağımsız Ders Materyali' if is_tr else 'AulaAI Educational System · Self-Contained Course Material'),\n", '                        ("AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System — Self-Contained Course Material"),\n'),
    ('                footer_text = "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System · Self-Contained Course Material"\n', '                footer_text = "AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System — Self-Contained Course Material"\n'),
)
for old, new in footer_replacements:
    if old in body:
        body = body.replace(old, new, 1)

# Replace/upgrade the metadata marker without stacking duplicate metadata blocks.
body = body.replace('"AulaAI PDF Engine v37-final"', '"AulaAI PDF Engine v40"')
if '"AulaAI PDF Engine v40"' not in body:
    open_anchor = "                doc = fitz.open(temp_path)\n"
    if open_anchor not in body:
        raise RuntimeError("v40 metadata anchor missing")
    body = body.replace(open_anchor, '''                doc = fitz.open(temp_path)\n                try:\n                    _meta = dict(doc.metadata or {})\n                    _meta["producer"] = "AulaAI PDF Engine v40"\n                    doc.set_metadata(_meta)\n                except Exception:\n                    pass\n''', 1)

required = {
    "language helper": "def _pdf_language_name(" in body,
    "case-normalized labels": "raw.lower().replace" in body,
    "turkish footer": "AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" in body,
    "v40 metadata": '"AulaAI PDF Engine v40"' in body,
}
missing = [name for name, ok in required.items() if not ok]
if missing:
    raise RuntimeError("v40 final PDF patch incomplete: " + ", ".join(missing))

s = s[:start] + body + s[end:]
p.write_text(s, encoding="utf-8")
print("Applied v40: direct live PDF renderer fix")
