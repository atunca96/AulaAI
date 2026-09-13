from pathlib import Path

root = Path(__file__).resolve().parents[1]
server_path = root / "server.py"
renderer_path = root / "services" / "pdf_renderer_v12.py"

# --- 1) Make the committed v12 renderer the only live exporter. ---
s = server_path.read_text(encoding="utf-8")
fn = "    def _export_course_pdf(self, course_id):\n"
start = s.rfind(fn)
if start < 0:
    raise RuntimeError("_export_course_pdf not found")
body_start = start + len(fn)
marker = "        # AULAAI_SINGLE_PDF_PATH_V13\n"
if marker not in s[start:start + 1600]:
    delegate = '''        # AULAAI_SINGLE_PDF_PATH_V13
        try:
            from services.pdf_renderer_v12 import render_course_pdf
            import urllib.parse
            import unicodedata

            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            lang = (params.get("lang", ["en"])[0] or "en").lower()
            if lang not in ("en", "tr"):
                lang = "en"

            pdf_bytes, pdf_course_name = render_course_pdf(course_id, lang)
            display_filename = f"{pdf_course_name}_AulaAI_{lang.upper()}.pdf"
            ascii_base = unicodedata.normalize("NFKD", str(pdf_course_name or "Course_Materials"))
            ascii_base = ascii_base.encode("ascii", "ignore").decode("ascii")
            ascii_base = "".join(c if (c.isalnum() or c in "-_") else "_" for c in ascii_base).strip("_") or "Course_Materials"
            ascii_filename = f"{ascii_base}_AulaAI_{lang.upper()}.pdf"
            encoded_filename = urllib.parse.quote(display_filename, safe="")

            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f"attachment; filename={ascii_filename}; filename*=UTF-8''{encoded_filename}")
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("X-AulaAI-PDF-Renderer", "v13-single-path")
            self.end_headers()
            self.wfile.write(pdf_bytes)
            return
        except Exception as pdf_err:
            print(f"[PDF V13 ERROR] {pdf_err}")
            traceback.print_exc()
            return self._send_error(f"PDF generation failed: {pdf_err}", 500)
'''
    s = s[:body_start] + delegate + s[body_start:]
server_path.write_text(s, encoding="utf-8")

# --- 2) Finalize localization/metadata in the one active renderer. ---
r = renderer_path.read_text(encoding="utf-8")

# Complete topic-type localization without another runtime layer.
if "'pronunciation': ('Pronunciation', 'Telaffuz')" not in r:
    anchor = "    'speaking': ('Speaking', 'Konuşma'),\n"
    if anchor not in r:
        raise RuntimeError("TYPE_LABELS anchor missing")
    r = r.replace(anchor, anchor + "    'pronunciation': ('Pronunciation', 'Telaffuz'),\n    'communication': ('Communication', 'İletişim'),\n    'conversation': ('Conversation', 'Konuşma'),\n    'lesson': ('Lesson', 'Ders'),\n    'assessment': ('Assessment', 'Değerlendirme'),\n    'exercise': ('Exercise', 'Alıştırma'),\n    'review': ('Review', 'Tekrar'),\n", 1)

# Localized target-language name on the cover.
if "def _pdf_language_name(" not in r:
    anchor = "\ndef render_course_pdf(course_id: str, lang: str = 'en') -> Tuple[bytes, str]:\n"
    helper = '''
def _pdf_language_name(value: str, is_tr: bool) -> str:
    raw = str(value or '').strip()
    if not is_tr:
        return raw
    names = {
        'english':'İngilizce','german':'Almanca','spanish':'İspanyolca','french':'Fransızca',
        'italian':'İtalyanca','portuguese':'Portekizce','russian':'Rusça','chinese':'Çince',
        'japanese':'Japonca','arabic':'Arapça','turkish':'Türkçe','dutch':'Hollandaca',
        'swedish':'İsveççe','korean':'Korece','greek':'Yunanca'
    }
    return names.get(raw.casefold(), raw)

'''
    if anchor not in r:
        raise RuntimeError("render_course_pdf anchor missing")
    r = r.replace(anchor, "\n" + helper + anchor.lstrip("\n"), 1)

old_sem = "        sem = f' ({_e(semester)})' if semester else ''\n"
new_sem = "        _semester = str(semester or '').strip()\n        _level = str(course_level or '').strip()\n        if _semester.casefold() in {_level.casefold(), (_level + ' level').casefold()}:\n            _semester = ''\n        sem = f' ({_e(_semester)})' if _semester else ''\n"
if old_sem in r:
    r = r.replace(old_sem, new_sem, 1)

old_cover = "            f'<div class=\"cover-sub\">{_e(course_lang)} · {level_word} {_e(course_level)}{sem}</div>'\n"
new_cover = "            f'<div class=\"cover-sub\">{_e(_pdf_language_name(course_lang, is_tr))} · {level_word} {_e(course_level)}{sem}</div>'\n"
if old_cover in r:
    r = r.replace(old_cover, new_cover, 1)

old_footer = "            page.insert_text(fitz.Point(38, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.7, color=(0.42,0.42,0.42))\n"
new_footer = "            footer_text = 'AulaAI Eğitim Sistemi · Bağımsız Ders Materyali' if self.is_tr else 'AulaAI Educational System · Self-Contained Course Material'\n            page.insert_text(fitz.Point(38, 823), footer_text, fontsize=6.7, color=(0.42,0.42,0.42))\n"
if old_footer in r:
    r = r.replace(old_footer, new_footer, 1)

# Stable metadata lets us verify the real renderer from any exported PDF.
old_doc = "        doc = fitz.open(self.temp_path)\n        total = len(doc)\n"
new_doc = "        doc = fitz.open(self.temp_path)\n        try:\n            meta = dict(doc.metadata or {})\n            meta['producer'] = 'AulaAI PDF Renderer v13 Single Path'\n            doc.set_metadata(meta)\n        except Exception:\n            pass\n        total = len(doc)\n"
if "AulaAI PDF Renderer v13 Single Path" not in r:
    if old_doc not in r:
        raise RuntimeError("metadata anchor missing")
    r = r.replace(old_doc, new_doc, 1)

renderer_path.write_text(r, encoding="utf-8")
print("Applied PDF v13: one live route, one renderer, localized cover/footer, no runtime PDF patches")
