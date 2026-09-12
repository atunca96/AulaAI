from pathlib import Path

path = Path("server.py")
src = path.read_text(encoding="utf-8")

old1 = '''            E = _html.escape

            def tx(page_dict, en_key, tr_key):
'''
new1 = '''            E = _html.escape

            # Turkish PDF exports should localize curriculum headings as well as page content.
            pdf_title_map = {}
            if is_tr:
                try:
                    from services.curriculum_translator import translate_titles_batch
                    title_candidates = [ch[2] for ch in chapters if ch[2]]
                    with db_connection() as title_db:
                        topic_title_rows = title_db.execute(
                            """SELECT t.title FROM topics t
                               JOIN chapters ch ON t.chapter_id = ch.id
                               WHERE ch.course_id = ? AND t.title IS NOT NULL AND t.title != ''""",
                            (course_id,)
                        ).fetchall()
                    title_candidates.extend(row[0] for row in topic_title_rows if row[0])
                    pdf_title_map = translate_titles_batch(title_candidates, target_lang="tr")
                except Exception as title_err:
                    print(f"[PDF EXPORT] Title translation fallback: {title_err}")

            def tx(page_dict, en_key, tr_key):
'''

old2 = '''                for ch in chapters:
                    ch_id, ch_num, ch_title = ch
                    unit_word = "Ünite" if is_tr else "Unit"
                    parts.append(
                        f'<div class="unit-card"><div class="unit-title">{unit_word} {ch_num}: {E(ch_title or "")}</div></div>'
                    )
'''
new2 = '''                for ch in chapters:
                    ch_id, ch_num, ch_title = ch
                    unit_word = "Ünite" if is_tr else "Unit"
                    display_ch_title = pdf_title_map.get(ch_title, ch_title) if is_tr else ch_title
                    parts.append(
                        f'<div class="unit-card"><div class="unit-title">{unit_word} {ch_num}: {E(display_ch_title or "")}</div></div>'
                    )
'''

old3 = '''                        parts.append(
                            f'<div class="topic-card">'
                            f'<div class="topic-title">{E(top_title or "Topic")}'
                            f'<span class="badge">{E(type_label(top_type or "lesson"))}</span></div>'
                        )
'''
new3 = '''                        display_top_title = pdf_title_map.get(top_title, top_title) if is_tr else top_title
                        topic_fallback = "Konu" if is_tr else "Topic"
                        parts.append(
                            f'<div class="topic-card">'
                            f'<div class="topic-title">{E(display_top_title or topic_fallback)}'
                            f'<span class="badge">{E(type_label(top_type or "lesson"))}</span></div>'
                        )
'''

for label, old, new in (("title map", old1, new1), ("chapter title", old2, new2), ("topic title", old3, new3)):
    count = src.count(old)
    if count != 1:
        raise RuntimeError(f"PDF title localization patch anchor '{label}' matched {count} times")
    src = src.replace(old, new, 1)

path.write_text(src, encoding="utf-8")
print("Applied Turkish PDF curriculum-heading localization patch")
