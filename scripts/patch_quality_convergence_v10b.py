from pathlib import Path
import re

# Final convergence patch, intentionally last in Docker build.

# 1) CEFR-appropriate future material generation.
ai_path = Path('services/ai_engine.py')
ai = ai_path.read_text(encoding='utf-8')
old = """- Maintain high academic rigor, first-principles explanations, and exhaustive educational depth.
- Never write shallow, brief summaries or placeholder content. Treat every topic with the depth of a university textbook chapter."""
new = """- Maintain strict factual and grammatical accuracy, but match explanation language to CEFR Level {level}. Depth must come from useful examples, contrasts, dialogues, and practice rather than terminology density.
- For A1-A2, use short concrete learner-facing explanations, one main idea at a time, and everyday examples. Avoid specialist linguistic metalanguage beyond the learner's level; if a technical term is necessary, explain it immediately in plain language. For B1-B2, use moderate terminology with plain-language support. C1-C2 may use advanced metalanguage when it genuinely improves precision.
- Every vocabulary row must carry a real semantic meaning for the COMPLETE term or phrase in both English and Turkish display fields. Never infer meaning from the first character, a substring, spelling similarity, or an alphabet label. Do not leave a vocabulary meaning blank when the term has a normal translatable meaning.
- Never write shallow placeholder content, but do not inflate beginner material into university-level linguistic theory."""
if ai.count(old) != 1:
    raise RuntimeError(f'CEFR prompt anchor matched {ai.count(old)} times')
ai = ai.replace(old, new, 1)
needle = 'Generate a complete, exhaustive, textbook-quality {level} {language} lesson on:'
if ai.count(needle) != 1:
    raise RuntimeError(f'lesson request anchor matched {ai.count(needle)} times')
ai = ai.replace(needle, 'Generate a complete, CEFR-appropriate, textbook-quality {level} {language} lesson on:', 1)
ai_path.write_text(ai, encoding='utf-8')

# 2) Bilingual finalizer: do not ignore valid semantic aliases.
bi_path = Path('services/bilingual_finisher.py')
bi = bi_path.read_text(encoding='utf-8')
old_collect = '''                    v = it.get("translation") or it.get("meaning") or it.get("english") or ""
                    if v and isinstance(v, str) and len(v.strip()) > 1 and (not it.get("translation_tr") or it.get("translation_tr") == v):
                        to_translate_to_tr.append(v.strip())'''
new_collect = '''                    v = (it.get("translation") or it.get("translation_en") or it.get("meaning_en") or
                         it.get("meaning") or it.get("english") or it.get("gloss_en") or
                         it.get("definition_en") or it.get("gloss") or "")
                    explicit_tr = (it.get("translation_tr") or it.get("meaning_tr") or it.get("turkish") or
                                   it.get("gloss_tr") or it.get("definition_tr") or "")
                    if explicit_tr and not it.get("translation_tr"):
                        it["translation_tr"] = str(explicit_tr).strip()
                        it["turkish"] = str(explicit_tr).strip()
                    if v and isinstance(v, str) and len(v.strip()) > 1 and (not it.get("translation_tr") or it.get("translation_tr") == v):
                        to_translate_to_tr.append(v.strip())'''
if bi.count(old_collect) != 1:
    raise RuntimeError(f'vocab collect anchor matched {bi.count(old_collect)} times')
bi = bi.replace(old_collect, new_collect, 1)
old_apply = '''                        v = it.get("translation") or it.get("meaning") or it.get("english") or ""
                        if v and isinstance(v, str):
                            v_clean = v.strip()
                            if not it.get("translation_tr") or it.get("translation_tr") == v_clean:
                                v_tr = trans_map.get(v_clean, v_clean)
                                it["translation_tr"] = v_tr
                                it["turkish"] = v_tr
                            it["translation_en"] = v_clean'''
new_apply = '''                        v = (it.get("translation") or it.get("translation_en") or it.get("meaning_en") or
                             it.get("meaning") or it.get("english") or it.get("gloss_en") or
                             it.get("definition_en") or it.get("gloss") or "")
                        explicit_tr = (it.get("translation_tr") or it.get("meaning_tr") or it.get("turkish") or
                                       it.get("gloss_tr") or it.get("definition_tr") or "")
                        if explicit_tr:
                            it["translation_tr"] = str(explicit_tr).strip()
                            it["turkish"] = str(explicit_tr).strip()
                        if v and isinstance(v, str):
                            v_clean = v.strip()
                            if not it.get("translation_tr") or it.get("translation_tr") == v_clean:
                                v_tr = trans_map.get(v_clean, v_clean)
                                it["translation_tr"] = v_tr
                                it["turkish"] = v_tr
                            it["translation_en"] = v_clean'''
if bi.count(old_apply) != 1:
    raise RuntimeError(f'vocab apply anchor matched {bi.count(old_apply)} times')
bi = bi.replace(old_apply, new_apply, 1)
bi_path.write_text(bi, encoding='utf-8')

# 3) PDF semantic/layout cleanup, still fully local / zero AI.
pdf_path = Path('services/pdf_academic_renderer.py')
src = pdf_path.read_text(encoding='utf-8')
if 'import re\n' not in src.split('from typing', 1)[0]:
    src = src.replace('import os\n', 'import os\nimport re\n', 1)
src = src.replace("    cont = '<div class=\"cont\">devam</div>' if continued else ''\n", "    cont = ''\n", 1)

start = src.find('def _vocab_meaning(item: dict, is_tr: bool, term: str, course_lang: str) -> str:\n')
end = src.find('\ndef _mcq_prompt(', start)
if start < 0 or end < 0:
    raise RuntimeError('v10b vocab resolver anchors missing')
resolver = r'''def _norm_vocab_key(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip()).casefold()


def _direct_vocab_meaning(item: dict, is_tr: bool, term: str, course_lang: str) -> str:
    _letter_key, alphabet_data = _spanish_alphabet_info(term, course_lang)
    if alphabet_data:
        return str(alphabet_data.get('name_tr' if is_tr else 'name_en') or '')
    if is_tr:
        keys = ('translation_tr','meaning_tr','turkish','tr','gloss_tr','definition_tr','meaning','translation','translation_en','meaning_en','english','gloss_en')
        locale_keys = ('tr','turkish','translation_tr','meaning_tr','gloss_tr')
    else:
        keys = ('translation_en','meaning_en','english','gloss_en','definition_en','meaning','translation','translation_tr','meaning_tr','turkish','gloss_tr')
        locale_keys = ('en','english','translation_en','meaning_en','gloss_en')
    leak_values = _alphabet_leak_values(course_lang)
    candidates = [item.get(k) for k in keys]
    for ck in ('translations','meanings','glosses','localized','localizations'):
        container = item.get(ck)
        if isinstance(container, dict):
            candidates.extend(container.get(k) for k in locale_keys)
    for value in candidates:
        text = str(value or '').strip()
        if text and text.casefold() not in leak_values:
            return text
    return ''


def _aligned_example_gloss(item: dict, term: str, is_tr: bool) -> str:
    target = str(item.get('example') or item.get('example_target') or item.get('target_example') or '').strip()
    translated = str((item.get('example_tr') if is_tr else item.get('example_en')) or '').strip()
    if not target or not translated or not term:
        return ''
    def segs(text):
        return [p.strip(' \t\r\n“”\"') for p in re.split(r'(?:^|\s)[—–]\s*|\n+', text) if p and p.strip(' \t\r\n“”\"')]
    a, b = segs(target), segs(translated)
    if len(a) != len(b) or not a:
        return ''
    needle = _norm_vocab_key(term).strip(' .!?¿¡“”\"')
    for i, part in enumerate(a):
        if _norm_vocab_key(part).strip(' .!?¿¡“”\"') == needle:
            return b[i].strip()
    return ''


def _build_course_vocab_memory(db, course_id: str, course_lang: str):
    memory = {'en': {}, 'tr': {}}
    rows = db.execute(
        'SELECT t.content FROM topics t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.course_id = ?',
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
        if not isinstance(pages, list):
            continue
        for page in pages:
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
                term = item.get('term') or item.get('word') or item.get('phrase') or item.get('sentence') or item.get('target') or ''
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
    remembered = ((memory or {}).get('tr' if is_tr else 'en') or {}).get(key)
    if remembered:
        return remembered
    return _aligned_example_gloss(item, term, is_tr)

'''
src = src[:start] + resolver + src[end+1:]

anchor = "        semester = course[3] or ''\n\n        paginator = AcademicPaginator(course_name, is_tr)\n"
if src.count(anchor) != 1:
    raise RuntimeError(f'vocab memory course anchor matched {src.count(anchor)} times')
src = src.replace(anchor, "        semester = course[3] or ''\n        vocab_memory = _build_course_vocab_memory(db, course_id, course_lang)\n\n        paginator = AcademicPaginator(course_name, is_tr)\n", 1)
call = "                            meaning = _vocab_meaning(item, is_tr, term, course_lang)\n"
if src.count(call) != 1:
    raise RuntimeError(f'vocab meaning call matched {src.count(call)} times')
src = src.replace(call, "                            meaning = _vocab_meaning(item, is_tr, term, course_lang, vocab_memory)\n", 1)

# v5 already localized page titles via the zero-AI title map. Keep that behavior,
# but strip accidental ordinal prefixes and print one heading for consecutive MCQs.
title_anchor = "                    title = _localized_title(page.get('title') or '', is_tr, page, title_maps)\n                    section = f'<div class=\"sec\">{_e(title)}</div>' if title else ''\n"
title_repl = """                    title = _localized_title(page.get('title') or '', is_tr, page, title_maps)\n                    if ptype == 'mcq' and title:\n                        title = re.sub(r'^\\s*\\d+\\.\\s*', '', str(title)).strip()\n                    section_key = _norm_vocab_key(title) if title else ''\n                    if ptype == 'mcq':\n                        if section_key and section_key == last_mcq_section_key:\n                            section = ''\n                        else:\n                            section = f'<div class=\"sec\">{_e(title)}</div>' if title else ''\n                            last_mcq_section_key = section_key or None\n                    else:\n                        last_mcq_section_key = None\n                        section = f'<div class=\"sec\">{_e(title)}</div>' if title else ''\n"""
if src.count(title_anchor) != 1:
    raise RuntimeError(f'MCQ title anchor matched {src.count(title_anchor)} times')
src = src.replace(title_anchor, title_repl, 1)
loop = "                for page in pages:\n"
if src.count(loop) != 1:
    raise RuntimeError(f'page loop anchor matched {src.count(loop)} times')
src = src.replace(loop, "                last_mcq_section_key = None\n                for page in pages:\n", 1)

pdf_path.write_text(src, encoding='utf-8')
print('Applied quality convergence v10b')
