from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "pdf_renderer_v12.py"
s = p.read_text(encoding="utf-8")

# Use an explicitly embedded CJK font inside PyMuPDF Story. Merely installing
# system fonts is insufficient because Story only resolves custom fonts through
# an Archive + @font-face binding.
old_body = "body { font-family: sans-serif; font-size: 9pt;"
old_body2 = "body { font-family: 'Noto Sans', 'Noto Sans CJK JP', sans-serif; font-size: 9pt;"
new_body = "body { font-family: AulaNotoCJK, sans-serif; font-size: 9pt;"
if old_body in s:
    s = s.replace(old_body, new_body, 1)
elif old_body2 in s:
    s = s.replace(old_body2, new_body, 1)
elif new_body not in s:
    raise RuntimeError("PDF body font anchor missing")

init_anchor = "        self.usable_height = self.bottom - self.top\n"
init_insert = """        self.usable_height = self.bottom - self.top
        self.font_archive = None
        self.font_css = ''
        for _font_dir in ('/usr/share/fonts/opentype/noto', '/usr/share/fonts/truetype/noto'):
            _regular = Path(_font_dir) / 'NotoSansCJK-Regular.ttc'
            _bold = Path(_font_dir) / 'NotoSansCJK-Bold.ttc'
            if _regular.exists():
                self.font_archive = fitz.Archive(_font_dir)
                self.font_css = "@font-face {font-family:AulaNotoCJK;src:url(NotoSansCJK-Regular.ttc);}" + ("@font-face {font-family:AulaNotoCJK;src:url(NotoSansCJK-Bold.ttc);font-weight:bold;}" if _bold.exists() else '')
                break
"""
if "self.font_archive = None" not in s:
    if init_anchor not in s:
        raise RuntimeError("PDF paginator init anchor missing")
    s = s.replace(init_anchor, init_insert, 1)

story_old = "        return fitz.Story(html=_doc(fragment), user_css=css)\n"
story_new = "        css = css + '\\n' + self.font_css\n        return fitz.Story(html=_doc(fragment), user_css=css, archive=self.font_archive)\n"
if story_old in s:
    s = s.replace(story_old, story_new, 1)
elif "archive=self.font_archive" not in s:
    raise RuntimeError("PDF Story archive anchor missing")

p.write_text(s, encoding="utf-8")
print("Applied embedded Noto CJK Archive to PDF Story renderer")
