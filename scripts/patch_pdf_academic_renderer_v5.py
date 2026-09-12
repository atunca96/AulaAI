from pathlib import Path

path = Path('services/pdf_academic_renderer.py')
src = path.read_text(encoding='utf-8')

replacements = [
    (
        "'SELECT id, number, title FROM chapters WHERE course_id = ? ORDER BY number ASC, id ASC',",
        "'SELECT id, number, title, title_tr FROM chapters WHERE course_id = ? ORDER BY number ASC, id ASC',",
        'chapter query',
    ),
    (
        '        for ch_id, ch_num, ch_title in chapters:\n            display_ch = _localized_title(ch_title, is_tr, None, title_maps)\n',
        '''        for ch_id, ch_num, ch_title, ch_title_tr in chapters:\n            if is_tr and ch_title_tr and str(ch_title_tr).strip() and str(ch_title_tr).strip() != str(ch_title or '').strip():\n                display_ch = str(ch_title_tr).strip()\n            else:\n                display_ch = _localized_title(ch_title, is_tr, None, title_maps)\n''',
        'chapter title selection',
    ),
    (
        "'SELECT id, type, title, content FROM topics WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC',",
        "'SELECT id, type, title, title_tr, content FROM topics WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC',",
        'topic query',
    ),
    (
        '            for _top_id, top_type, top_title, top_content in topics:\n',
        '            for _top_id, top_type, top_title, top_title_tr, top_content in topics:\n',
        'topic loop',
    ),
    (
        '                display_top = _localized_title(top_title, is_tr, content, title_maps)\n',
        '''                if is_tr and top_title_tr and str(top_title_tr).strip() and str(top_title_tr).strip() != str(top_title or '').strip():\n                    display_top = str(top_title_tr).strip()\n                else:\n                    # Do not substitute the first page title for the topic title.\n                    # If DB title_tr is unavailable, use only the zero-AI title map.\n                    display_top = _localized_title(top_title, is_tr, None, title_maps)\n''',
        'topic title selection',
    ),
    (
        "                    title = _pick(page, 'title', 'title_tr', is_tr)\n",
        "                    title = _localized_title(page.get('title') or '', is_tr, page, title_maps)\n",
        'page title selection',
    ),
]

for old, new, label in replacements:
    count = src.count(old)
    if count != 1:
        raise RuntimeError(f'{label} anchor matched {count} times')
    src = src.replace(old, new, 1)

path.write_text(src, encoding='utf-8')
print('Applied academic PDF v5: DB-backed Turkish chapter/topic/page titles')
