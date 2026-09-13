from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / "server.py"
s = p.read_text(encoding="utf-8")

# This patch deliberately targets the final downloadable endpoint itself.
# Earlier renderer patches can succeed while this legacy in-server renderer
# still emits its own literals. Run this LAST, immediately before server start.

# 1) Exact footer used by the live _export_course_pdf implementation.
old_footer = '                        "AulaAI Educational System \\u2014 Self-Contained Course Material",\n'
new_footer = '                        ("AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System — Self-Contained Course Material"),\n'
if old_footer in s:
    s = s.replace(old_footer, new_footer, 1)
elif '"AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr' not in s:
    raise RuntimeError("v38 live footer anchor missing")

# 2) Final HTML normalization. This executes after every topic has already been
# rendered to HTML, so no upstream label variant can escape localization.
html_anchor = '            full_html = "".join(parts)\n'
html_block = '''            full_html = "".join(parts)\n            if is_tr:\n                _pdf_tr_labels = {\n                    ">Pronunciation<": ">Telaffuz<",\n                    ">Phonetics<": ">Fonetik<",\n                    ">Communication<": ">İletişim<",\n                    ">Functional Language<": ">İşlevsel Dil<",\n                    ">Cultural Context<": ">Kültürel Bağlam<",\n                    ">Vocabulary<": ">Kelime Bilgisi<",\n                    ">Grammar<": ">Dilbilgisi<",\n                    ">Reading<": ">Okuma<",\n                    ">Writing<": ">Yazma<",\n                    ">Listening<": ">Dinleme<",\n                    ">Speaking<": ">Konuşma<",\n                    ">Lesson<": ">Ders<",\n                    ">Assessment<": ">Değerlendirme<",\n                    ">Exercise<": ">Alıştırma<",\n                    ">Review<": ">Tekrar<",\n                }\n                for _src, _dst in _pdf_tr_labels.items():\n                    full_html = full_html.replace(_src, _dst)\n'''
if "_pdf_tr_labels = {" not in s:
    if html_anchor not in s:
        raise RuntimeError("v38 live HTML anchor missing")
    s = s.replace(html_anchor, html_block, 1)

# 3) Normalize the cover language name at the last possible data point. v34
# normally handles this, but this guard makes the live endpoint independent of
# upstream patch ordering.
cover_anchor = "                course_lang  = c_row[2] or \"General\"\n"
cover_guard = '''                course_lang  = c_row[2] or "General"\n                if is_tr:\n                    _pdf_tr_language_names = {\n                        "english":"İngilizce", "german":"Almanca", "spanish":"İspanyolca",\n                        "french":"Fransızca", "italian":"İtalyanca", "portuguese":"Portekizce",\n                        "russian":"Rusça", "chinese":"Çince", "japanese":"Japonca",\n                        "arabic":"Arapça", "turkish":"Türkçe", "dutch":"Hollandaca",\n                        "swedish":"İsveççe", "korean":"Korece", "greek":"Yunanca"\n                    }\n                    course_lang = _pdf_tr_language_names.get(str(course_lang).strip().casefold(), course_lang)\n'''
if "_pdf_tr_language_names = {" not in s:
    if cover_anchor not in s:
        raise RuntimeError("v38 live cover-language anchor missing")
    s = s.replace(cover_anchor, cover_guard, 1)

# 4) Put a machine-verifiable marker in PDF metadata. It is not shown on pages,
# but proves which renderer produced a downloaded file when inspecting metadata.
open_anchor = "                doc = fitz.open(temp_path)\n"
meta_block = '''                doc = fitz.open(temp_path)\n                try:\n                    _meta = dict(doc.metadata or {})\n                    _meta["producer"] = "AulaAI PDF Engine v38"\n                    doc.set_metadata(_meta)\n                except Exception:\n                    pass\n'''
if '"AulaAI PDF Engine v38"' not in s:
    if open_anchor not in s:
        raise RuntimeError("v38 live PDF metadata anchor missing")
    s = s.replace(open_anchor, meta_block, 1)

required = [
    '"AulaAI Eğitim Sistemi — Bağımsız Ders Materyali" if is_tr',
    "_pdf_tr_labels = {",
    "_pdf_tr_language_names = {",
    '"AulaAI PDF Engine v38"',
]
missing = [x for x in required if x not in s]
if missing:
    raise RuntimeError("v38 final live endpoint verification failed: " + ", ".join(missing))

p.write_text(s, encoding="utf-8")
print("Applied v38: final live downloadable PDF endpoint normalization")
