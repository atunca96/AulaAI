from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "pdf_renderer_v12.py"
s = p.read_text(encoding="utf-8")

# Bind the installed Noto CJK font to PyMuPDF Story, but keep a safe fallback.
# The previous experiment failed because it injected pathlib.Path into the
# renderer without importing it. This version uses os.path, which the renderer
# already imports, and never makes the renderer depend on the font being found.
old_body = "body { font-family: sans-serif; font-size: 9pt;"
new_body = "body { font-family: AulaNotoCJK, sans-serif; font-size: 9pt;"
if old_body in s:
    s = s.replace(old_body, new_body, 1)
elif new_body not in s:
    raise RuntimeError("PDF body font anchor missing")

init_anchor = "        self.usable_height = self.bottom - self.top\n"
init_insert = """        self.usable_height = self.bottom - self.top
        self.font_archive = None
        self.font_css = ''
        for _font_dir in ('/usr/share/fonts/opentype/noto', '/usr/share/fonts/truetype/noto'):
            _regular = os.path.join(_font_dir, 'NotoSansCJK-Regular.ttc')
            _bold = os.path.join(_font_dir, 'NotoSansCJK-Bold.ttc')
            if os.path.exists(_regular):
                try:
                    self.font_archive = fitz.Archive(_font_dir)
                    self.font_css = "@font-face {font-family:AulaNotoCJK;src:url(NotoSansCJK-Regular.ttc);}" + ("@font-face {font-family:AulaNotoCJK;src:url(NotoSansCJK-Bold.ttc);font-weight:bold;}" if os.path.exists(_bold) else '')
                except Exception as _font_err:
                    print(f'[PDF V14] CJK font archive disabled: {_font_err}')
                    self.font_archive = None
                    self.font_css = ''
                break
"""
if "self.font_archive = None" not in s:
    if init_anchor not in s:
        raise RuntimeError("PDF paginator init anchor missing")
    s = s.replace(init_anchor, init_insert, 1)

story_old = "        return fitz.Story(html=_doc(fragment), user_css=css)\n"
story_new = "        css = css + ('\\n' + self.font_css if self.font_css else '')\n        if self.font_archive is not None:\n            return fitz.Story(html=_doc(fragment), user_css=css, archive=self.font_archive)\n        return fitz.Story(html=_doc(fragment), user_css=css)\n"
if story_old in s:
    s = s.replace(story_old, story_new, 1)
elif "archive=self.font_archive" not in s:
    raise RuntimeError("PDF Story archive anchor missing")

p.write_text(s, encoding="utf-8")
print("Applied safe embedded Noto CJK font binding to academic PDF renderer")
