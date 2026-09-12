from pathlib import Path
import re

path = Path('server.py')
src = path.read_text(encoding='utf-8')

pattern = re.compile(
    r'''            # Turkish PDF exports should localize curriculum headings as well as page content\.\n'''
    r'''            pdf_title_map = \{\}\n'''
    r'''            if is_tr:\n'''
    r'''                try:\n'''
    r'''                    from services\.curriculum_translator import translate_titles_batch\n'''
    r'''                    title_candidates = \[ch\[2\] for ch in chapters if ch\[2\]\]\n'''
    r'''                    with db_connection\(\) as title_db:\n'''
    r'''                        topic_title_rows = title_db\.execute\(\n'''
    r'''                            """SELECT t\.title FROM topics t\n'''
    r'''                               JOIN chapters ch ON t\.chapter_id = ch\.id\n'''
    r'''                               WHERE ch\.course_id = \? AND t\.title IS NOT NULL AND t\.title != ''""",\n'''
    r'''                            \(course_id,\)\n'''
    r'''                        \)\.fetchall\(\)\n'''
    r'''                    title_candidates\.extend\(row\[0\] for row in topic_title_rows if row\[0\]\)\n'''
    r'''                    pdf_title_map = translate_titles_batch\(title_candidates, target_lang="tr"\)\n'''
    r'''                except Exception as title_err:\n'''
    r'''                    print\(f"\[PDF EXPORT\] Title translation fallback: \{title_err\}"\)\n'''
)

replacement = '''            # PDF export must never invoke an LLM. Reuse translations already stored in DB.\n            pdf_title_map = {}\n            if is_tr:\n                try:\n                    with db_connection() as title_db:\n                        chapter_title_rows = title_db.execute(\n                            """SELECT title, title_tr FROM chapters\n                               WHERE course_id = ? AND title IS NOT NULL AND title != ''""",\n                            (course_id,)\n                        ).fetchall()\n                        topic_title_rows = title_db.execute(\n                            """SELECT t.title, t.title_tr FROM topics t\n                               JOIN chapters ch ON t.chapter_id = ch.id\n                               WHERE ch.course_id = ? AND t.title IS NOT NULL AND t.title != ''""",\n                            (course_id,)\n                        ).fetchall()\n                    for original, translated in list(chapter_title_rows) + list(topic_title_rows):\n                        if original and translated and str(translated).strip():\n                            pdf_title_map[str(original)] = str(translated).strip()\n                except Exception as title_err:\n                    print(f"[PDF EXPORT] Stored title localization fallback: {title_err}")\n'''

src2, count = pattern.subn(replacement, src, count=1)
if count != 1:
    raise RuntimeError(f'zero-AI PDF export patch matched {count} times')

path.write_text(src2, encoding='utf-8')
print('Applied zero-AI PDF export: stored DB translations only')
