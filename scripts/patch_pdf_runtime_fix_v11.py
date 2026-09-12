from pathlib import Path

# Forward-only PDF runtime fix.
# Production DB schema stores canonical chapter/topic titles in `title`; there are
# no `title_tr` columns. Turkish/localized titles live in structured content and
# the zero-AI title caches. Never make the renderer depend on non-existent columns.

path = Path('services/pdf_academic_renderer.py')
src = path.read_text(encoding='utf-8')

helper_anchor = '\ndef _table_html(headers: Sequence[str], rows: Sequence[str], continued: bool = False) -> str:\n'
if helper_anchor not in src:
    raise RuntimeError('v11 helper anchor missing')

helper = r'''
def _localized_curriculum_title(title: str, is_tr: bool, content, title_maps) -> str:
    """Localize chapter/topic titles without assuming locale columns in SQLite.

    Only top-level curriculum metadata and the existing zero-AI title maps are
    allowed here. We intentionally do not steal the first page heading as a topic
    title, because that caused topic/page title mismatches in older exports.
    """
    title = str(title or '').strip()
    if not is_tr:
        return title
    if isinstance(content, dict):
        candidates = [
            content.get('topic_title_tr'), content.get('chapter_title_tr'),
            content.get('localized_title_tr'), content.get('title_tr'),
        ]
        metadata = content.get('metadata')
        if isinstance(metadata, dict):
            candidates.extend([
                metadata.get('topic_title_tr'), metadata.get('chapter_title_tr'),
                metadata.get('localized_title_tr'), metadata.get('title_tr'),
            ])
        for value in candidates:
            if value and str(value).strip() and str(value).strip() != title:
                return str(value).strip()
    exact, ci_cache, ci_canonical = title_maps
    if title in exact and str(exact[title]).strip():
        return str(exact[title]).strip()
    folded = title.casefold()
    if folded in ci_cache:
        return ci_cache[folded]
    if folded in ci_canonical:
        return ci_canonical[folded]
    return title

'''
src = src.replace(helper_anchor, '\n' + helper + helper_anchor.lstrip('\n'), 1)

old_ch_query = "            'SELECT id, number, title, title_tr FROM chapters WHERE course_id = ? ORDER BY number ASC, id ASC',\n"
new_ch_query = "            'SELECT id, number, title FROM chapters WHERE course_id = ? ORDER BY number ASC, id ASC',\n"
if src.count(old_ch_query) != 1:
    raise RuntimeError(f'v11 chapter query anchor matched {src.count(old_ch_query)} times')
src = src.replace(old_ch_query, new_ch_query, 1)

old_ch_loop = '''        for ch_id, ch_num, ch_title, ch_title_tr in chapters:
            if is_tr and ch_title_tr and str(ch_title_tr).strip() and str(ch_title_tr).strip() != str(ch_title or '').strip():
                display_ch = str(ch_title_tr).strip()
            else:
                display_ch = _localized_title(ch_title, is_tr, None, title_maps)
'''
new_ch_loop = '''        for ch_id, ch_num, ch_title in chapters:
            display_ch = _localized_curriculum_title(ch_title, is_tr, None, title_maps)
'''
if src.count(old_ch_loop) != 1:
    raise RuntimeError(f'v11 chapter loop anchor matched {src.count(old_ch_loop)} times')
src = src.replace(old_ch_loop, new_ch_loop, 1)

old_top_query = "                'SELECT id, type, title, title_tr, content FROM topics WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC',\n"
new_top_query = "                'SELECT id, type, title, content FROM topics WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC',\n"
if src.count(old_top_query) != 1:
    raise RuntimeError(f'v11 topic query anchor matched {src.count(old_top_query)} times')
src = src.replace(old_top_query, new_top_query, 1)

old_top_loop = '''            for _top_id, top_type, top_title, top_title_tr, top_content in topics:
'''
new_top_loop = '''            for _top_id, top_type, top_title, top_content in topics:
'''
if src.count(old_top_loop) != 1:
    raise RuntimeError(f'v11 topic loop anchor matched {src.count(old_top_loop)} times')
src = src.replace(old_top_loop, new_top_loop, 1)

old_top_title = '''                if is_tr and top_title_tr and str(top_title_tr).strip() and str(top_title_tr).strip() != str(top_title or '').strip():
                    display_top = str(top_title_tr).strip()
                else:
                    # Do not substitute the first page title for the topic title.
                    # If DB title_tr is unavailable, use only the zero-AI title map.
                    display_top = _localized_title(top_title, is_tr, None, title_maps)
'''
new_top_title = '''                display_top = _localized_curriculum_title(top_title, is_tr, content, title_maps)
'''
if src.count(old_top_title) != 1:
    raise RuntimeError(f'v11 topic title anchor matched {src.count(old_top_title)} times')
src = src.replace(old_top_title, new_top_title, 1)

# Cross-row semantic memory is a quality enhancement, never a hard dependency.
# If an old/heterogeneous payload cannot be indexed, continue with direct fields
# and aligned examples rather than failing the whole export.
old_memory = "        vocab_memory = _build_course_vocab_memory(db, course_id, course_lang)\n\n        paginator = AcademicPaginator(course_name, is_tr)\n"
new_memory = '''        try:
            vocab_memory = _build_course_vocab_memory(db, course_id, course_lang)
        except Exception as vocab_memory_err:
            print(f"[PDF] Vocabulary memory skipped safely: {vocab_memory_err}")
            vocab_memory = {'en': {}, 'tr': {}}

        paginator = AcademicPaginator(course_name, is_tr)
'''
if src.count(old_memory) != 1:
    raise RuntimeError(f'v11 vocab memory anchor matched {src.count(old_memory)} times')
src = src.replace(old_memory, new_memory, 1)

path.write_text(src, encoding='utf-8')
print('Applied PDF runtime v11: production-schema-safe titles + nonfatal semantic memory')
