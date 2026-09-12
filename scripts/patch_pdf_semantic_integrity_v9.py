from pathlib import Path

# V9 fixes a semantic corruption path, not a language-specific PDF layout bug.
# The Spanish alphabet detector previously treated ordinary words/phrases that
# happened to begin with a letter as alphabet rows, then overwrote their stored
# translations with strings such as "a harfi (la a)".  The PDF renderer also
# trusted that corrupted field too eagerly.  Fix both the producer and consumer.

# ---------------------------------------------------------------------------
# 1) Root fix: alphabet detection must accept only explicit alphabet labels.
# ---------------------------------------------------------------------------
finisher_path = Path('services/bilingual_finisher.py')
bi = finisher_path.read_text(encoding='utf-8')
start = bi.find('def extract_letter_key(term):\n')
end = bi.find('\ndef _load_cache():', start)
if start < 0 or end < 0:
    raise RuntimeError('extract_letter_key function anchors not found')

new_detector = r'''def extract_letter_key(term):
    """Return a Spanish alphabet key only for an explicit alphabet label.

    Accepted examples: ``A``, ``A, a``, ``Ñ, ñ``, ``CH, ch``, ``LL, ll``,
    ``RR, rr``.  Ordinary lexical material such as ``tú`` or
    ``¿A qué te dedicas?`` must never be classified as an alphabet row.

    A lowercase one-character token is intentionally *not* treated as a letter
    label because it may be a real lexical item (for example Spanish ``a``).
    """
    if not term or not isinstance(term, str):
        return None
    s = term.strip()
    if not s:
        return None

    valid = set(SPANISH_ALPHABET_DATA.keys())

    # Single explicit uppercase label: A, Ñ, CH, LL, RR, ...
    if re.fullmatch(r'[A-ZÑ]{1,2}', s):
        candidate = s.upper()
        return candidate if candidate in valid else None

    # Explicit case-pair / repeated label: A, a | L/l | LL, ll | RR / rr.
    # Require a separator so ordinary words can never collapse into letters.
    m = re.fullmatch(r'([A-Za-zÑñ]{1,2})\s*[,/]\s*([A-Za-zÑñ]{1,2})', s)
    if m:
        left, right = m.group(1).upper(), m.group(2).upper()
        if left == right and left in valid:
            return left

    return None
'''
bi = bi[:start] + new_detector + bi[end:]
finisher_path.write_text(bi, encoding='utf-8')

# ---------------------------------------------------------------------------
# 2) Consumer fix: PDF resolves vocabulary semantically and rejects known
#    alphabet payload leakage for non-letter terms.  No AI/network calls.
# ---------------------------------------------------------------------------
pdf_path = Path('services/pdf_academic_renderer.py')
src = pdf_path.read_text(encoding='utf-8')

helper_anchor = '\ndef _table_html(headers: Sequence[str], rows: Sequence[str], continued: bool = False) -> str:\n'
if helper_anchor not in src:
    raise RuntimeError('PDF helper insertion anchor not found')

helpers = r'''
def _is_spanish_course(course_lang: str) -> bool:
    value = str(course_lang or '').strip().casefold()
    return ('spanish' in value) or ('españ' in value) or value in {'es', 'spa'}


def _spanish_alphabet_info(term: str, course_lang: str):
    if not _is_spanish_course(course_lang):
        return None, None
    try:
        from services.bilingual_finisher import extract_letter_key, SPANISH_ALPHABET_DATA
        key = extract_letter_key(str(term or ''))
        return key, (SPANISH_ALPHABET_DATA.get(key) if key else None)
    except Exception:
        return None, None


def _alphabet_leak_values(course_lang: str):
    if not _is_spanish_course(course_lang):
        return set()
    try:
        from services.bilingual_finisher import SPANISH_ALPHABET_DATA
        values = set()
        for data in SPANISH_ALPHABET_DATA.values():
            for key in ('spelling', 'name_tr', 'name_en'):
                value = str(data.get(key) or '').strip()
                if value:
                    values.add(value.casefold())
        return values
    except Exception:
        return set()


def _vocab_meaning(item: dict, is_tr: bool, term: str, course_lang: str) -> str:
    """Choose an existing semantic meaning without inventing or translating.

    Actual alphabet rows use the canonical local alphabet table.  For every
    other row, values that exactly match a known alphabet-name payload are
    rejected as leakage.  This lets old corrupted classrooms export safely while
    keeping PDF generation completely local / zero-token.
    """
    letter_key, alphabet_data = _spanish_alphabet_info(term, course_lang)
    if alphabet_data:
        return str(alphabet_data.get('name_tr' if is_tr else 'name_en') or '')

    if is_tr:
        keys = ('meaning_tr', 'turkish', 'tr', 'translation_tr',
                'meaning', 'translation', 'translation_en', 'english')
    else:
        keys = ('meaning_en', 'english', 'translation_en',
                'meaning', 'translation', 'translation_tr', 'turkish')

    leak_values = _alphabet_leak_values(course_lang)
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if text.casefold() in leak_values:
            continue
        return text
    return ''


def _mcq_prompt(page: dict, is_tr: bool) -> str:
    # Stored fields only: never synthesize a question stem in the PDF layer.
    preferred = ('prompt_tr', 'prompt', 'question_tr', 'question', 'stem_tr', 'stem', 'text_tr', 'text') if is_tr else (
        'prompt_en', 'prompt', 'question_en', 'question', 'stem_en', 'stem', 'text_en', 'text'
    )
    for key in preferred:
        value = page.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''

'''
src = src.replace(helper_anchor, '\n' + helpers + helper_anchor.lstrip('\n'), 1)

# Replace vocabulary term/meaning resolution.  This anchor exists in the source
# before v6/v8 and survives those build-time patches.
old_vocab = '''                            term = item.get('term') or item.get('word') or ''\n                            phon = item.get('phonetic') or ''\n                            meaning = item.get('translation_tr') if is_tr else (item.get('translation') or item.get('translation_en'))\n                            if not meaning:\n                                meaning = item.get('translation') or ''\n'''
new_vocab = '''                            term = (item.get('term') or item.get('word') or item.get('phrase') or\n                                    item.get('sentence') or item.get('target') or '')\n                            phon = item.get('phonetic') or item.get('pronunciation') or ''\n                            meaning = _vocab_meaning(item, is_tr, term, course_lang)\n'''
if src.count(old_vocab) != 1:
    raise RuntimeError(f'PDF vocabulary semantic anchor matched {src.count(old_vocab)} times')
src = src.replace(old_vocab, new_vocab, 1)

# Never render answer choices without a real stored question stem.  Support the
# historical question/stem field names, but do not generate missing content.
old_prompt = '''                        question_counter += 1\n                        prompt = _pick(page, 'prompt_en', 'prompt_tr', is_tr) or page.get('prompt') or ''\n                        raw_options = page.get('options') or []\n'''
new_prompt = '''                        prompt = _mcq_prompt(page, is_tr)\n                        if not prompt:\n                            # A question without a stem is unusable.  Skipping it is safer\n                            # than emitting orphan options or fabricating a stem at export.\n                            continue\n                        question_counter += 1\n                        raw_options = page.get('options') or page.get('choices') or page.get('distractors') or []\n'''
if src.count(old_prompt) != 1:
    raise RuntimeError(f'PDF MCQ prompt anchor matched {src.count(old_prompt)} times')
src = src.replace(old_prompt, new_prompt, 1)

pdf_path.write_text(src, encoding='utf-8')
print('Applied PDF semantic integrity v9: strict alphabet labels + safe vocabulary meanings + real MCQ stems only')
