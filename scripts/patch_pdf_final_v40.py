from pathlib import Path

p = Path(__file__).resolve().parents[1] / "server.py"
s = p.read_text(encoding="utf-8")

# Work only inside the live exporter so unrelated code cannot be touched.
start = s.find("    def _export_course_pdf(self, course_id):\n")
end = s.find("    def _wipe_curriculum(self):\n", start)
if start < 0 or end < 0:
    raise RuntimeError("v40 live PDF exporter anchors missing")
body = s[start:end]

# Normalize topic labels case-insensitively so DB values like Pronunciation work.
old_type = '''        def type_label(t):\n            pair = TYPE_LABELS.get(t, (t.replace("_", " ").title(), t.replace("_", " ").title()))\n            return pair[1] if is_tr else pair[0]\n'''
new_type = '''        def type_label(t):\n            raw = str(t or "lesson").strip()\n            key = raw.lower().replace("-", "_").replace(" ", "_")\n            extra = {\n                "pronunciation": ("Pronunciation", "Telaffuz"),\n                "communication": ("Communication", "İletişim"),\n                "conversation": ("Conversation", "Konuşma"),\n                "lesson": ("Lesson", "Ders"),\n                "assessment": ("Assessment", "Değerlendirme"),\n                "exercise": ("Exercise", "Alıştırma"),\n                "review": ("Review", "Tekrar"),\n            }\n            pair = TYPE_LABELS.get(key) or extra.get(key)\n            if pair:\n                return pair[1] if is_tr else pair[0]\n            return raw.replace("_", " ").title()\n'''
if old_type in body:
    body = body.replace(old_type, new_type, 1)

# Localize target-language name at render time.
if "def _pdf_language_name(" not in body:
    anchor = '        is_tr = (lang == "tr")\n'
    helper = '''        is_tr = (lang == "tr")\n\n        def _pdf_language_name(value):\n            raw = str(value or "").strip()\n            key = raw.casefold()\n            tr = {\n                "english":"İngilizce", "german":"Almanca", "spanish":"İspanyolca",\n                "french":"Fransızca", "italian":"İtalyanca", "portuguese":"Portekizce",\n                "russian":"Rusça", "chinese":"Çince", "japanese":"Japonca",\n                "arabic":"Arapça", "turkish":"Türkçe", "dutch":"Hollandaca",\n                "swedish":"İsveççe", "korean":"Korece", "greek":"Yunanca"\n            }\n            return tr.get(key, raw) if is_tr else raw\n'''
    if anchor in body:
        body = body.replace(anchor, helper, 1)

# Remove stale duplicated level suffix and localize the cover language.
body = body.replace('            sem_str = f" ({E(semester)})" if semester else ""\n', '            sem_clean = str(semester or "").strip()\n            level_clean = str(course_level or "").strip()\n            if sem_clean.casefold() in {level_clean.casefold(), (level_clean + " level").casefold()}:\n                sem_clean = ""\n            sem_str = f" ({E(sem_clean)})" if sem_clean else ""\n', 1)
body = body.replace('f\'<div class="cover-sub">{E(course_lang)} &middot; Seviye {E(course_level)}{sem_str}</div>\'', 'f\'<div class="cover-sub">{E(_pdf_language_name(course_lang))} &middot; {"Seviye" if is_tr else "Level"} {E(course_level)}{sem_str}</div>\'', 1)

# Replace the literal footer in the actual page.insert_text call.
body = body.replace('                        "AulaAI Educational System \\u2014 Self-Contained Course Material",\n', '                        ("AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System — Self-Contained Course Material"),\n', 1)
body = body.replace('                        "AulaAI Educational System — Self-Contained Course Material",\n', '                        ("AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System — Self-Contained Course Material"),\n', 1)

# Mark the generated file itself so we can prove the live renderer ran.
if '"AulaAI PDF Engine v40"' not in body:
    open_anchor = "                doc = fitz.open(temp_path)\n"
    if open_anchor in body:
        body = body.replace(open_anchor, '''                doc = fitz.open(temp_path)\n                try:\n                    _meta = dict(doc.metadata or {})\n                    _meta["producer"] = "AulaAI PDF Engine v40"\n                    doc.set_metadata(_meta)\n                except Exception:\n                    pass\n''', 1)

required = [
    "def _pdf_language_name(",
    "raw.lower().replace",
    "AulaAI Eğitim Sistemi — Bağımsız Ders Materyali",
    '"AulaAI PDF Engine v40"',
]
missing = [x for x in required if x not in body]
if missing:
    raise RuntimeError("v40 final PDF patch incomplete: " + ", ".join(missing))

s = s[:start] + body + s[end:]
p.write_text(s, encoding="utf-8")
print("Applied v40: direct live PDF renderer fix")
