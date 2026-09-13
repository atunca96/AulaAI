from copy import deepcopy
import re
import unicodedata


class MaterialReleaseRejected(RuntimeError):
    pass


def _as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    if value in (None, ''):
        return []
    return [value]


def _norm(value):
    return str(value or '').strip()


def validate_mcq(page):
    """Return (ok, reason). Structural only; semantic truth is attested in the same generation call."""
    if not isinstance(page, dict):
        return False, 'mcq-not-dict'
    prompt = _norm(page.get('prompt') or page.get('question') or page.get('text'))
    options = [_norm(x) for x in _as_list(page.get('options') or page.get('choices'))]
    answer = _norm(page.get('answer'))
    if not prompt:
        return False, 'missing-prompt'
    if len(options) != 4:
        return False, 'option-count'
    if any(not x for x in options):
        return False, 'empty-option'
    if len(set(options)) != 4:
        return False, 'duplicate-options'
    if not answer:
        return False, 'missing-answer'
    if answer not in options:
        return False, 'answer-not-in-options'
    ci = page.get('correct_index')
    if isinstance(ci, int) and (ci < 0 or ci >= 4 or options[ci] != answer):
        return False, 'correct-index-mismatch'
    for key in ('options_tr', 'options_en'):
        localized = page.get(key)
        if localized is not None:
            localized = [_norm(x) for x in _as_list(localized)]
            if len(localized) != 4 or any(not x for x in localized) or len(set(localized)) != 4:
                return False, f'invalid-{key}'
    return True, ''


def _char_script(ch):
    if not ch.isalpha():
        return None
    name = unicodedata.name(ch, '')
    for script in ('CYRILLIC', 'GREEK', 'ARABIC', 'HEBREW', 'HIRAGANA', 'KATAKANA', 'HANGUL', 'LATIN'):
        if script in name:
            return script
    if 'CJK UNIFIED' in name or 'IDEOGRAPH' in name:
        return 'HAN'
    return 'OTHER'


def _allowed_scripts(language):
    lang = _norm(language).casefold()
    if any(x in lang for x in ('russian', 'рус', 'rusça', 'ukrain', 'bulgar', 'serbian', 'macedon')):
        return {'CYRILLIC'}
    if any(x in lang for x in ('greek', 'yunanca', 'ελλην')):
        return {'GREEK'}
    if any(x in lang for x in ('arabic', 'arapça', 'العربية', 'persian', 'farsi')):
        return {'ARABIC'}
    if any(x in lang for x in ('hebrew', 'ibranice', 'עברית')):
        return {'HEBREW'}
    if any(x in lang for x in ('japanese', 'japonca', '日本')):
        return {'HIRAGANA', 'KATAKANA', 'HAN'}
    if any(x in lang for x in ('chinese', 'çince', '中文', 'mandarin')):
        return {'HAN'}
    if any(x in lang for x in ('korean', 'korece', '한국')):
        return {'HANGUL', 'HAN'}
    return {'LATIN'}


_TARGET_KEYS = {
    'term', 'word', 'target', 'example', 'sentence', 'prompt', 'answer',
    'options', 'distractors', 'expression', 'phrase', 'form', 'native'
}


def _iter_target_strings(node, parent_key=''):
    if isinstance(node, dict):
        for key, value in node.items():
            k = str(key)
            kl = k.casefold()
            if kl.endswith('_en') or kl.endswith('_tr') or kl in {'translation', 'explanation', 'note', 'context', 'source_evidence', 'source_taught'}:
                continue
            if kl == 'text' and parent_key == 'dialogue' and isinstance(value, str):
                yield value
            elif kl in _TARGET_KEYS:
                if isinstance(value, str):
                    yield value
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            yield item
            if isinstance(value, (dict, list)):
                yield from _iter_target_strings(value, kl)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_target_strings(item, parent_key)


def _script_gate(data, language):
    allowed = _allowed_scripts(language)
    for text in _iter_target_strings(data):
        for token in re.findall(r"[^\W\d_]+", text, flags=re.UNICODE):
            scripts = {_char_script(ch) for ch in token if _char_script(ch)}
            scripts.discard('OTHER')
            if not scripts:
                continue
            native = scripts & allowed
            foreign = scripts - allowed
            if native and foreign:
                return False, f'mixed-script:{token}'
            if allowed != {'LATIN'} and scripts == {'LATIN'}:
                return False, f'foreign-script-token:{token}'
            if allowed == {'LATIN'} and any(s in scripts for s in {'CYRILLIC', 'GREEK', 'ARABIC', 'HEBREW', 'HIRAGANA', 'KATAKANA', 'HANGUL', 'HAN'}):
                return False, f'foreign-script-token:{token}'
    return True, ''


def _iter_phonetic_strings(node, key=''):
    if isinstance(node, dict):
        for k, value in node.items():
            kl = str(k).casefold()
            is_phon = any(tag in kl for tag in ('pronun', 'phonetic', 'transcription', 'ipa'))
            if is_phon and isinstance(value, str) and value.strip():
                yield value.strip()
            if isinstance(value, (dict, list)):
                yield from _iter_phonetic_strings(value, kl)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_phonetic_strings(item, key)


def _phonetic_gate(data):
    values = list(_iter_phonetic_strings(data))
    for text in values:
        if re.search(r'/(?:[^/\n]{1,120})/', text):
            return False, 'slash-phonemic-notation'
        if '[' not in text or ']' not in text:
            return False, 'non-ipa-phonetic-field'
        outside = re.sub(r'\[[^\]]*\]', '', text)
        if re.search(r'\b[A-Za-z]{2,}(?:-[A-Za-z]{2,})+\b', outside):
            return False, 'learner-respelling-mixed-with-ipa'
    return True, ''


def _mcq_gate(data):
    pages = data.get('pages') if isinstance(data, dict) else None
    if not isinstance(pages, list):
        return False, 'missing-pages'
    for index, page in enumerate(pages):
        if isinstance(page, dict) and str(page.get('type') or '').strip().lower() == 'mcq':
            ok, reason = validate_mcq(page)
            if not ok:
                return False, f'page-{index}:{reason}'
    return True, ''


def enforce_release_hard_gate(data, language):
    """Zero-model-call release gate. Semantic rules 3/4 are attested by the same generation call; objective rules are rechecked here."""
    if not isinstance(data, dict):
        raise MaterialReleaseRejected('MATERIAL_RELEASE_HARD_GATE:invalid-data')

    gate = data.get('release_gate')
    expected = {'1': 'PASS', '2': 'PASS', '3': 'PASS', '4': 'PASS'}
    if not isinstance(gate, dict) or any(_norm(gate.get(k)).upper() != 'PASS' for k in expected):
        raise MaterialReleaseRejected('MATERIAL_RELEASE_HARD_GATE:missing-pass-attestation')

    ok1, why1 = _script_gate(data, language)
    if not ok1:
        raise MaterialReleaseRejected('MATERIAL_RELEASE_HARD_GATE:1:' + why1)
    ok2, why2 = _phonetic_gate(data)
    if not ok2:
        raise MaterialReleaseRejected('MATERIAL_RELEASE_HARD_GATE:2:' + why2)
    ok4, why4 = _mcq_gate(data)
    if not ok4:
        raise MaterialReleaseRejected('MATERIAL_RELEASE_HARD_GATE:4:' + why4)

    out = deepcopy(data)
    out.pop('release_gate', None)
    return out


def enforce_material_integrity(data):
    """Language-agnostic structural cleanup after the fail-closed hard gate has passed."""
    if not isinstance(data, dict):
        return data
    out = deepcopy(data)
    pages = out.get('pages')
    if not isinstance(pages, list):
        return out
    clean = []
    removed = []
    for index, page in enumerate(pages):
        if isinstance(page, dict) and str(page.get('type') or '').strip().lower() == 'mcq':
            ok, reason = validate_mcq(page)
            if not ok:
                removed.append((index, reason))
                continue
        clean.append(page)
    out['pages'] = clean
    if removed:
        out['_integrity_removed_mcq'] = [{'index': i, 'reason': r} for i, r in removed]
    return out
