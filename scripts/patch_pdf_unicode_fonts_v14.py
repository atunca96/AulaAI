from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "pdf_renderer_v12.py"
s = p.read_text(encoding="utf-8")

old_e = "def _e(value):\n    return html.escape(str(value or ''))\n"
new_e = """def _e(value):
    raw = str(value or '')
    raw = raw.replace('゛', '†').replace('゜', '‡')
    raw = re.sub(r'(?<![\\u3040-\\u30ff\\u3400-\\u9fff\\uff66-\\uff9f])ー(?![\\u3040-\\u30ff\\u3400-\\u9fff\\uff66-\\uff9f])', '¤', raw)
    return html.escape(raw)
"""
if old_e in s:
    s = s.replace(old_e, new_e, 1)
elif "raw = raw.replace('゛', '†')" not in s:
    raise RuntimeError("PDF escape anchor missing")

finish_anchor = "        doc = fitz.open(self.temp_path)\n        total = len(doc)\n"
finish_insert = """        doc = fitz.open(self.temp_path)
        _fontfile = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
        if os.path.exists(_fontfile):
            for _page in doc:
                _placements = []
                for _placeholder, _symbol in (('†', '゛'), ('‡', '゜'), ('¤', 'ー')):
                    for _rect in _page.search_for(_placeholder):
                        _placements.append((_rect, _symbol))
                        _page.add_redact_annot(_rect, fill=None)
                if _placements:
                    _page.apply_redactions()
                    for _rect, _symbol in _placements:
                        _fontsize = max(6.0, _rect.height * 0.80)
                        _baseline = _rect.y1 - (_rect.height * 0.15)
                        _page.insert_text((_rect.x0, _baseline), _symbol, fontname='AulaNotoCJK', fontfile=_fontfile, fontsize=_fontsize)
        total = len(doc)
"""
if finish_anchor in s:
    s = s.replace(finish_anchor, finish_insert, 1)
elif "AulaNotoCJK" not in s:
    raise RuntimeError("PDF symbol postprocess anchor missing")

p.write_text(s, encoding="utf-8")
print("Applied safe standalone Japanese symbol repair to academic PDF renderer")
