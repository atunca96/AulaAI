from pathlib import Path

p = Path(__file__).resolve().parents[1] / "server.py"
s = p.read_text(encoding="utf-8")

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

old_type = '''        def type_label(t):\n            pair = TYPE_LABELS.get(t, (t.replace("_", " ").title(), t.replace("_", " ").title()))\n            return pair[1] if is_tr else pair[0]\n'''
new_type = '''        def type_label(t):\n            raw = str(t or "lesson").strip()\n            key = raw.lower().replace("-", "_").replace(" ", "_")\n            extra = {"pronunciation":("Pronunciation","Telaffuz"),"phonetics":("Phonetics","Fonetik"),"communication":("Communication","İletişim"),"functional_language":("Functional Language","İşlevsel Dil"),"cultural_context":("Cultural Context","Kültürel Bağlam"),"lesson":("Lesson","Ders"),"conversation":("Conversation","Konuşma"),"assessment":("Assessment","Değerlendirme"),"exercise":("Exercise","Alıştırma"),"review":("Review","Tekrar"),"reading":("Reading","Okuma"),"writing":("Writing","Yazma"),"listening":("Listening","Dinleme"),"speaking":("Speaking","Konuşma"),"vocabulary":("Vocabulary","Kelime Bilgisi"),"grammar":("Grammar","Dilbilgisi"),"culture":("Culture","Kültür")}\n            pair = TYPE_LABELS.get(key) or extra.get(key)\n            return (pair[1] if is_tr else pair[0]) if pair else raw.replace("_", " ").title()\n'''
if old_type in s:
    s = s.replace(old_type, new_type, 1)

s = s.replace('E(top_title or "Topic")', 'E(top_title or ("Konu" if is_tr else "Topic"))')
s = s.replace("'AulaAI Educational System · Self-Contained Course Material'", "('AulaAI Eğitim Sistemi · Bağımsız Ders Materyali' if is_tr else 'AulaAI Educational System · Self-Contained Course Material')", 1)

html_anchor = '            full_html = "".join(parts)\n'
if "_pdf_final_tr_labels" not in s and html_anchor in s:
    block = '''            full_html = "".join(parts)\n            if is_tr:\n                _pdf_final_tr_labels = {\n                    ">Pronunciation<": ">Telaffuz<",\n                    ">Phonetics<": ">Fonetik<",\n                    ">Communication<": ">İletişim<",\n                    ">Functional Language<": ">İşlevsel Dil<",\n                    ">Cultural Context<": ">Kültürel Bağlam<",\n                    ">Vocabulary<": ">Kelime Bilgisi<",\n                    ">Grammar<": ">Dilbilgisi<",\n                    ">Reading<": ">Okuma<",\n                    ">Writing<": ">Yazma<",\n                    ">Listening<": ">Dinleme<",\n                    ">Speaking<": ">Konuşma<",\n                    ">Assessment<": ">Değerlendirme<",\n                    ">Exercise<": ">Alıştırma<",\n                    ">Review<": ">Tekrar<",\n                }\n                for _src, _dst in _pdf_final_tr_labels.items():\n                    full_html = full_html.replace(_src, _dst)\n'''
    s = s.replace(html_anchor, block, 1)

open_anchor = '                doc = fitz.open(temp_path)\n'
if '"AulaAI PDF Engine v37-final"' not in s and open_anchor in s:
    s = s.replace(open_anchor, '''                doc = fitz.open(temp_path)\n                try:\n                    _meta = dict(doc.metadata or {})\n                    _meta["producer"] = "AulaAI PDF Engine v37-final"\n                    doc.set_metadata(_meta)\n                except Exception:\n                    pass\n''', 1)

required = ["requested_lang =", "material_language FROM courses", "course_material_language = str(c_row[5]", "Telaffuz", "İletişim", "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali", "_pdf_final_tr_labels", "AulaAI PDF Engine v37-final"]
missing = [x for x in required if x not in s]
if missing:
    raise RuntimeError("v37 finalization incomplete: " + ", ".join(missing))

p.write_text(s, encoding="utf-8")
print("Applied v37 FINAL PDF localization")
