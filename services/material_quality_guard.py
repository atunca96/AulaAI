from copy import deepcopy


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
    """Return (ok, reason). Structural only; semantic truth stays with AI audits."""
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
    for key in ('options_tr', 'options_en'):
        localized = page.get(key)
        if localized is not None:
            localized = [_norm(x) for x in _as_list(localized)]
            if len(localized) != 4 or any(not x for x in localized) or len(set(localized)) != 4:
                return False, f'invalid-{key}'
    return True, ''


def enforce_material_integrity(data):
    """
    Language-agnostic fail-closed release guard.
    Invalid MCQs are removed rather than published with a contradictory key.
    Correct content is preserved byte-for-byte.
    """
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
