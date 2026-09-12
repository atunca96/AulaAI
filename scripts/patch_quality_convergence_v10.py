from pathlib import Path
import re

# Quality convergence v10
# - Future lesson generation: CEFR-readable rather than university-jargon-heavy
# - Bilingual vocabulary finalization: preserve/fill explicit semantic fields reliably
# - PDF: reuse stored/localized titles, group repeated MCQ headings, recover safe meanings
#   from existing material without AI/network calls, and keep export zero-token.

# ---------------------------------------------------------------------------
# 1) Generation prompt: accuracy + depth through examples, not excessive metalanguage.
# ---------------------------------------------------------------------------
ai_path = Path('services/ai_engine.py')
ai = ai_path.read_text(encoding='utf-8')

old_rigor = '''- Maintain high academic rigor, first-principles explanations, and exhaustive educational depth.\n- Never write shallow, brief summaries or placeholder content. Treat every topic with the depth of a university textbook chapter.'''
new_rigor = '''- Maintain strict factual and grammatical accuracy, but match the explanation language to CEFR Level {level}. Depth must come from useful examples, contrasts, dialogues, and practice rather than terminology density.\n- For A1-A2, use short concrete learner-facing explanations, one main idea at a time, and everyday examples. Avoid specialist linguistic metalanguage beyond the learner's level; if a technical term is genuinely necessary, explain it immediately in plain language. For B1-B2, use moderate terminology with plain-language support. C1-C2 may use advanced metalanguage when it genuinely improves precision.\n- Every vocabulary row must carry a real semantic meaning for the COMPLETE term or phrase in both English and Turkish display fields. Never infer a meaning from the first character, a substring, spelling similarity, or an alphabet label. Do not leave a vocabulary meaning blank when the term has a normal translatable meaning.\n- Never write shallow placeholder content, but do not inflate beginner material into university-level linguistic theory.'''
if ai.count(old_rigor) != 1:
    raise RuntimeError(f'CEFR rigor anchor matched {ai.count(old_rigor)} times')
ai = ai.replace(old_rigor, new_rigor, 1)

old_user = 'Generate a complete, exhaustive, textbook-quality {level} {language} lesson on:'
new_user = 'Generate a complete, CEFR-appropriate, textbook-quality {level} {language} lesson on:'
if ai.count(old_user) != 1:
    raise RuntimeError(f'lesson request anchor matched {ai.count(old_user)} times')
ai = ai.replace(old_user, new_user, 1)
ai_path.write_text(ai, encoding='utf-8')

# ---------------------------------------------------------------------------
# 2) Bilingual finalizer: use every legitimate stored semantic field before AI.
# ---------------------------------------------------------------------------
bi_path = Path('services/bilingual_finisher.py')
bi = bi_path.read_text(encoding='utf-8')

old_collect = '''                    v = it.get("translation") or it.get("meaning") or it.get("english") or ""\n                    if v and isinstance(v, str) and len(v.strip()) > 1 and (not it.get("translation_tr") or it.get("translation_tr") == v):\n                        to_translate_to_tr.append(v.strip())'''
new_collect = '''                    v = (it.get("translation") or it.get("translation_en") or it.get("meaning_en") or\n                         it.get("meaning") or it.get("english") or it.get("gloss_en") or\n                         it.get("definition_en") or it.get("gloss") or "")\n                    explicit_tr = (it.get("translation_tr") or it.get("meaning_tr") or it.get("turkish") or\n                                   it.get("gloss_tr") or it.get("definition_tr") or "")\n                    if explicit_tr and not it.get("translation_tr"):\n                        it["translation_tr"] = str(explicit_tr).strip()\n                        it["turkish"] = str(explicit_tr).strip()\n                    if v and isinstance(v, str) and len(v.strip()) > 1 and (not it.get("translation_tr") or it.get("translation_tr") == v):\n                        to_translate_to_tr.append(v.strip())'''
if bi.count(old_collect) != 1:
    raise RuntimeError(f'bilingual vocab collection anchor matched {bi.count(old_collect)} times')
bi = bi.replace(old_collect, new_collect, 1)

old_apply = '''                        v = it.get("translation") or it.get("meaning") or it.get("english") or ""\n                        if v and isinstance(v, str):\n                            v_clean = v.strip()\n                            if not it.get("translation_tr") or it.get("translation_tr") == v_clean:\n                                v_tr = trans_map.get(v_clean, v_clean)\n                                it["translation_tr"] = v_tr\n                                it["turkish"] = v_tr\n                            it["translation_en"] = v_clean'''
new_apply = '''                        v = (it.get("translation") or it.get("translation_en") or it.get("meaning_en") or\n                             it.get("meaning") or it.get("english") or it.get("gloss_en") or\n                             it.get("definition_en") or it.get("gloss") or "")\n                        explicit_tr = (it.get("translation_tr") or it.get("meaning_tr") or it.get("turkish") or\n                                       it.get("gloss_tr") or it.get("definition_tr") or "")\n                        if explicit_tr:\n                            it["translation_tr"] = str(explicit_tr).strip()\n                            it["turkish"] = str(explicit_tr).strip()\n                        if v and isinstance(v, str):\n                            v_clean = v.strip()\n                            if not it.get("translation_tr") or it.get("translation_tr") == v_clean:\n                                v_tr = trans_map.get(v_clean, v_clean)\n                                it["translation_tr"] = v_tr\n                                it["turkish"] = v_tr\n                            it["translation_en"] = v_clean'''
if bi.count(old_apply) != 1:
    raise RuntimeError(f'bilingual vocab apply anchor matched {bi.count(old_apply)} times')
bi = bi.replace(old_apply, new_apply, 1)
bi_path.write_text(bi, encoding='utf-8')

# ---------------------------------------------------------------------------
# 3) Academic PDF v10. This runs after v9, so it patches the built renderer state.
# ---------------------------------------------------------------------------
pdf_path = Path('services/pdf_academic_renderer.py')
src = pdf_path.read_text(encoding='utf-8')

if 'import re\n' not in src.split('from typing', 1)[0]:
    src = src.replace('import os\n', 'import os\nimport re\n', 1)

src = src.replace("    cont = '<div class=\"cont\">devam</div>' if continued else ''\n", "    cont = ''\n", 1)

start = src.find('def _vocab_meaning(item: dict, is_tr: bool, term: str, course_lang: str) -> str:\n')
end = src.find('\ndef _mcq_prompt(', start)
if start < 0 or end < 0:
    raise RuntimeError('v10 vocabulary resolver anchors not found')

resolver = r'''def _norm_vocab_key(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip()).casefold()


def _direct_vocab_meaning(item: dict, is_tr: bool, term: str, course_lang: str) -> str:
    letter_key, alphabet_data = _spanish_alphabet_info(term, course_lang)
    if alphabet_data:
        return str(alphabet_data.get('name_tr' if is_tr else 'name_en') or '')

    if is_tr:
        keys = ('translation_tr', 'meaning_tr', 'turkish', 'tr', 'gloss_tr', 'definition_tr',
                'meaning', 'translation', 'translation_en', 'meaning_en', 'english', 'gloss_en')
        locale_keys = ('tr', 'turkish', 'translation_tr', 'meaning_tr', 'gloss_tr')
    else:
        keys = ('translation_en', 'meaning_en', 'english', 'gloss_en', 'definition_en',
                'meaning', 'translation', 'translation_tr', 'meaning_tr', 'turkish', 'gloss_tr')
        locale_keys = ('en', 'english', 'translation_en', 'meaning_en', 'gloss_en')

    leak_values = _alphabet_leak_values(course_lang)
    candidates = [item.get(key) for key in keys]

    for container_key in ('translations', 'meanings', 'glosses', 'localized', 'localizations'):
        container = item.get(container_key)
        if isinstance(container, dict):
            for key in locale_keys:
                candidates.append(container.get(key))

    for value in candidates:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if text.casefold() in leak_values:
            continue
        return text
    return ''


def _aligned_example_gloss(item: dict, term: str, is_tr: bool) -> str:
    target_example = str(item.get('example') or item.get('example_target') or item.get('target_example') or '').strip()
    translated = str((item.get('example_tr') if is_tr else item.get('example_en')) or '').strip()
    if not target_example or not translated or not term:
        return ''

    def segments(text):
        parts = re.split(r'(?:^|\s)[—–]\s*|\n+', text)
        return [p.strip(' \t\r\n“”\"') for p in parts if p and p.strip(' \t\r\n“”\"')]

    target_parts = segments(target_example)
    translated_parts = segments(translated)
    if len(target_parts) != len(translated_parts) or not target_parts:
        return ''

    needle = _norm_vocab_key(term).strip(' .!?¿¡“”\"')
    for idx, part in enumerate(target_parts):
        candidate = _norm_vocab_key(part).strip(' .!?¿¡“”\"')
        if candidate == needle:
            return translated_parts[idx].strip()
    return ''


def _build_course_vocab_memory(db, course_id: str, course_lang: str):
    memory = {'en': {}, 'tr': {}}
    rows = db.execute(
        'SELECT t.content FROM topics t '
        'JOIN chapters ch ON t.chapter_id = ch.id '
        'WHERE ch.course_id = ?',
        (course_id,),
    ).fetchall()
    for row in rows:
        raw = row[0] if not hasattr(row, 'keys') else row['content']
        try:
            content = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            continue
        if isinstance(content, list):
            content = {'pages': content}
        if not isinstance(content, dict):
            continue
        pages = content.get('pages') or []
        if isinstance(pages, dict):
            pages = [pages]
        for page in pages if isinstance(pages, list) else []:
            if not isinstance(page, dict):
                continue
            items = page.get('items') or page.get('vocabulary') or page.get('words') or []
            if isinstance(items, dict):
                items = list(items.values()) if items and all(isinstance(v, dict) for v in items.values()) else [items]
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                term = (item.get('term') or item.get('word') or item.get('phrase') or
                        item.get('sentence') or item.get('target') or '')
                key = _norm_vocab_key(term)
                if not key:
                    continue
                en = _direct_vocab_meaning(item, False, term, course_lang)
                tr = _direct_vocab_meaning(item, True, term, course_lang)
                if en:
                    memory['en'].setdefault(key, en)
                if tr:
                    memory['tr'].setdefault(key, tr)
    return memory


def _vocab_meaning(item: dict, is_tr: bool, term: str, course_lang: str, memory=None) -> str:
    direct = _direct_vocab_meaning(item, is_tr, term, course_lang)
    if direct:
        return direct
    key = _norm_vocab_key(term)
    if memory and key:
        remembered = (memory.get('tr' if is_tr else 'en') or {}).get(key)
        if remembered:
            return remembered
    aligned = _aligned_example_gloss(item, term, is_tr)
    if aligned:
        return aligned
    return ''

'''
src = src[:start] + resolver + src[end+1:]

course_anchor = "        semester = course[3] or ''\n\n        paginator = AcademicPaginator(course_name, is_tr)\n"
course_repl = "        semester = course[3] or ''\n        vocab_memory = _build_course_vocab_memory(db, course_id, course_lang)\n\n        paginator = AcademicPaginator(course_name, is_tr)\n"
if src.count(course_anchor) != 1:
    raise RuntimeError(f'course vocab-memory anchor matched {src.count(course_anchor)} times')
src = src.replace(course_anchor, course_repl, 1)

old_meaning_call = "                            meaning = _vocab_meaning(item, is_tr, term, course_lang)\n"
new_meaning_call = "                            meaning = _vocab_meaning(item, is_tr, term, course_lang, vocab_memory)\n"
if src.count(old_meaning_call) != 1:
    raise RuntimeError(f'vocab meaning call anchor matched {src.count(old_meaning_call)} times')
src = src.replace(old_meaning_call, new_meaning_call, 1)

old_title = "                    title = _pick(page, 'title', 'title_tr', is_tr)\n                    section = f'<div class=\"sec\">{_e(title)}</div>' if title else ''\n"
new_title = """                    raw_page_title = str(page.get('title') or '').strip()\n                    title = _pick(page, 'title', 'title_tr', is_tr)\n                    if is_tr and raw_page_title and not str(page.get('title_tr') or '').strip():\n                        title = _localized_title(raw_page_title, True, page, title_maps)\n                    if ptype == 'mcq' and title:\n                        title = re.sub(r'^\\s*\\d+\\.\\s*', '', str(title)).strip()\n                    section_key = _norm_vocab_key(title) if title else ''\n                    if ptype == 'mcq':\n                        if section_key and section_key == last_mcq_section_key:\n                            section = ''\n                        else:\n                            section = f'<div class=\"sec\">{_e(title)}</div>' if title else ''\n                            last_mcq_section_key = section_key or None\n                    else:\n                        last_mcq_section_key = None\n                        section = f'<div class=\"sec\">{_e(title)}</div>' if title else ''\n"""
if src.count(old_title) != 1:
    raise RuntimeError(f'page title/grouping anchor matched {src.count(old_title)} times')
src = src.replace(old_title, new_title, 1)

loop_anchor = "                for page in pages:\n"
if src.count(loop_anchor) != 1:
    raise RuntimeError(f'page loop anchor matched {src.count(loop_anchor)} times')
src = src.replace(loop_anchor, "                last_mcq_section_key = None\n                for page in pages:\n", 1)

pdf_path.write_text(src, encoding='utf-8')
print('Applied quality convergence v10: CEFR readability + semantic vocab recovery + compact MCQ sections')
