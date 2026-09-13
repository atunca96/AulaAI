from pathlib import Path

p = Path(__file__).resolve().parents[1] / "server.py"
s = p.read_text(encoding="utf-8")

# Patch the LAST exporter definition. In a duplicated class/module, Python uses the later definition.
start_marker = "    def _export_course_pdf(self, course_id):\n"
end_marker = "    def _wipe_curriculum(self):\n"
start = s.rfind(start_marker)
end = s.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("active PDF exporter anchors missing")
body = s[start:end]

old_type = '''        def type_label(t):\n            pair = TYPE_LABELS.get(t, (t.replace("_", " ").title(), t.replace("_", " ").title()))\n            return pair[1] if is_tr else pair[0]\n'''
new_type = '''        def type_label(t):\n            raw = str(t or "lesson").strip()\n            key = raw.lower().replace("-", "_").replace(" ", "_")\n            pair = TYPE_LABELS.get(key)\n            return (pair[1] if is_tr else pair[0]) if pair else raw.replace("_", " ").title()\n'''
if old_type in body:
    body = body.replace(old_type, new_type, 1)

if "def _pdf_language_name(" not in body:
    anchor = '        is_tr = (lang == "tr")\n'
    helper = '''        is_tr = (lang == "tr")\n\n        def _pdf_language_name(value):\n            raw = str(value or "").strip()\n            key = raw.casefold()\n            tr = {"english":"İngilizce","german":"Almanca","spanish":"İspanyolca","french":"Fransızca","italian":"İtalyanca","portuguese":"Portekizce","russian":"Rusça","chinese":"Çince","japanese":"Japonca","arabic":"Arapça","turkish":"Türkçe","dutch":"Hollandaca","swedish":"İsveççe","korean":"Korece","greek":"Yunanca"}\n            return tr.get(key, raw) if is_tr else raw\n'''
    if anchor not in body:
        raise RuntimeError("active PDF language anchor missing")
    body = body.replace(anchor, helper, 1)

# Cover: handle both raw exporter and the v34 exporter form.
body = body.replace('f\'<div class="cover-sub">{E(course_lang)} &middot; Seviye {E(course_level)}{sem_str}</div>\'', 'f\'<div class="cover-sub">{E(_pdf_language_name(course_lang))} &middot; {"Seviye" if is_tr else "Level"} {E(course_level)}{sem_str}</div>\'')
body = body.replace('f\'<div class="cover-sub">{E(_pdf_export_language_name(course_lang, is_tr))} &middot; {level_word} {E(course_level)}{sem_str}</div>\'', 'f\'<div class="cover-sub">{E(_pdf_language_name(course_lang))} &middot; {"Seviye" if is_tr else "Level"} {E(course_level)}{sem_str}</div>\'')

# Remove duplicate semester text such as (A1 Level).
body = body.replace('            sem_str = f" ({E(semester)})" if semester else ""\n', '            _sem = str(semester or "").strip()\n            _lvl = str(course_level or "").strip()\n            if _sem.casefold() in {_lvl.casefold(), (_lvl + " level").casefold()}:\n                _sem = ""\n            sem_str = f" ({E(_sem)})" if _sem else ""\n')

# Final rendered HTML localization catches any label path missed earlier.
html_anchor = '            full_html = "".join(parts)\n'
if "_pdf_active_labels" not in body:
    if html_anchor not in body:
        raise RuntimeError("active PDF full_html anchor missing")
    body = body.replace(html_anchor, html_anchor + '''            if is_tr:\n                _pdf_active_labels = {\n                    ">Pronunciation<": ">Telaffuz<",\n                    ">Communication<": ">İletişim<",\n                    ">Phonetics<": ">Fonetik<",\n                    ">Functional Language<": ">İşlevsel Dil<",\n                    ">Cultural Context<": ">Kültürel Bağlam<",\n                }\n                for _src, _dst in _pdf_active_labels.items():\n                    full_html = full_html.replace(_src, _dst)\n''', 1)

# Footer: support raw and already-patched variants.
body = body.replace('"AulaAI Educational System \\u2014 Self-Contained Course Material"', '("AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System — Self-Contained Course Material")')
body = body.replace('"AulaAI Educational System — Self-Contained Course Material"', '("AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System — Self-Contained Course Material")')
body = body.replace('footer_text = "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System · Self-Contained Course Material"', 'footer_text = "AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System — Self-Contained Course Material"')

# Metadata marker proves the active exporter was patched.
body = body.replace('AulaAI PDF Engine v37-final', 'AulaAI PDF Engine v42')
body = body.replace('AulaAI PDF Engine v40', 'AulaAI PDF Engine v42')
if 'AulaAI PDF Engine v42' not in body:
    open_anchor = "                doc = fitz.open(temp_path)\n"
    if open_anchor not in body:
        raise RuntimeError("active PDF metadata anchor missing")
    body = body.replace(open_anchor, '''                doc = fitz.open(temp_path)\n                try:\n                    _meta = dict(doc.metadata or {})\n                    _meta["producer"] = "AulaAI PDF Engine v42"\n                    doc.set_metadata(_meta)\n                except Exception:\n                    pass\n''', 1)

required = ["def _pdf_language_name(", "_pdf_active_labels", "AulaAI Eğitim Sistemi — Bağımsız Ders Materyali", "AulaAI PDF Engine v42"]
missing = [x for x in required if x not in body]
if missing:
    raise RuntimeError("active PDF exporter patch incomplete: " + ", ".join(missing))

s = s[:start] + body + s[end:]
p.write_text(s, encoding="utf-8")
print(f"Applied v42 to active PDF exporter; exporter_count={s.count(start_marker)}")
