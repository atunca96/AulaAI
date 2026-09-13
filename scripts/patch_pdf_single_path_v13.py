from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "pdf_renderer_v12.py"
s = p.read_text(encoding="utf-8")

# Only edit the renderer that the proven download route already calls.
labels_anchor = "    'speaking': ('Speaking', 'Konuşma'),\n"
if "'pronunciation': ('Pronunciation', 'Telaffuz')" not in s:
    s = s.replace(labels_anchor, labels_anchor + "    'pronunciation': ('Pronunciation', 'Telaffuz'),\n    'communication': ('Communication', 'İletişim'),\n    'conversation': ('Conversation', 'Konuşma'),\n    'lesson': ('Lesson', 'Ders'),\n    'assessment': ('Assessment', 'Değerlendirme'),\n    'exercise': ('Exercise', 'Alıştırma'),\n    'review': ('Review', 'Tekrar'),\n", 1)

if "def _pdf_language_name(" not in s:
    anchor = "def render_course_pdf(course_id: str, lang: str = 'en') -> Tuple[bytes, str]:\n"
    helper = "def _pdf_language_name(value: str, is_tr: bool) -> str:\n    raw = str(value or '').strip()\n    if not is_tr:\n        return raw\n    return {'english':'İngilizce','german':'Almanca','spanish':'İspanyolca','french':'Fransızca','italian':'İtalyanca','portuguese':'Portekizce','russian':'Rusça','chinese':'Çince','japanese':'Japonca','arabic':'Arapça','turkish':'Türkçe','dutch':'Hollandaca','swedish':'İsveççe','korean':'Korece','greek':'Yunanca'}.get(raw.casefold(), raw)\n\n\n"
    if anchor not in s:
        raise RuntimeError("renderer function anchor missing")
    s = s.replace(anchor, helper + anchor, 1)

s = s.replace("        sem = f' ({_e(semester)})' if semester else ''\n", "        _semester = str(semester or '').strip()\n        _level = str(course_level or '').strip()\n        if _semester.casefold() in {_level.casefold(), (_level + ' level').casefold()}:\n            _semester = ''\n        sem = f' ({_e(_semester)})' if _semester else ''\n", 1)
s = s.replace("            f'<div class=\"cover-sub\">{_e(course_lang)} · {level_word} {_e(course_level)}{sem}</div>'\n", "            f'<div class=\"cover-sub\">{_e(_pdf_language_name(course_lang, is_tr))} · {level_word} {_e(course_level)}{sem}</div>'\n", 1)
s = s.replace("            page.insert_text(fitz.Point(38, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.7, color=(0.42,0.42,0.42))\n", "            footer_text = 'AulaAI Eğitim Sistemi · Bağımsız Ders Materyali' if self.is_tr else 'AulaAI Educational System · Self-Contained Course Material'\n            page.insert_text(fitz.Point(38, 823), footer_text, fontsize=6.7, color=(0.42,0.42,0.42))\n", 1)

p.write_text(s, encoding="utf-8")
print("Applied visible PDF renderer localization to active v12 renderer")
