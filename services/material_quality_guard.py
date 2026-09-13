from copy import deepcopy
import unicodedata


# Formatting controls that are meaningful in real writing systems and bidi text.
_SAFE_FORMAT_CONTROLS = {
    '\u061c',  # Arabic Letter Mark
    '\u200c',  # ZWNJ
    '\u200d',  # ZWJ
    '\u200e',  # LRM
    '\u200f',  # RLM
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
    '\u2066', '\u2067', '\u2068', '\u2069',
}


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


def _is_unicode_noncharacter(ch):
    cp = ord(ch)
    return 0xFDD0 <= cp <= 0xFDEF or (cp & 0xFFFF) in (0xFFFE, 0xFFFF)


def _sanitize_text(value):
    """Conservative, language-agnostic Unicode cleanup.

    Keeps real script controls/combining marks intact, normalizes canonically to
    NFC, and removes only impossible/non-text corruption. A corruption marker
    between two visible non-space characters becomes a hyphen so tokens such as
    phonetic learner forms do not silently collapse together.
    """
    text = unicodedata.normalize('NFC', str(value))
    chars = list(text)
    out = []
    repaired = 0
    for i, ch in enumerate(chars):
        category = unicodedata.category(ch)
        invalid = (
            ch == '\ufffd'
            or _is_unicode_noncharacter(ch)
            or category == 'Cs'
            or (category == 'Cc' and ch not in ('\n', '\r', '\t'))
            or (category == 'Cf' and ch not in _SAFE_FORMAT_CONTROLS)
        )
        if not invalid:
            out.append(ch)
            continue
        repaired += 1
        prev = out[-1] if out else ''
        nxt = chars[i + 1] if i + 1 < len(chars) else ''
        if prev and nxt and not prev.isspace() and not nxt.isspace():
            # Avoid gluing two visible token pieces after corruption removal.
            if prev not in '-–—/|' and nxt not in '-–—/|':
                out.append('-')
    return ''.join(out), repaired


def _sanitize_tree(value, stats):
    if isinstance(value, str):
        clean, repaired = _sanitize_text(value)
        stats['unicode_repairs'] += repaired
        return clean
    if isinstance(value, list):
        return [_sanitize_tree(v, stats) for v in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_tree(v, stats) for v in value)
    if isinstance(value, dict):
        return {k: _sanitize_tree(v, stats) for k, v in value.items()}
    return value


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
    """Language-agnostic deterministic release guard.

    No model/API call is made here. Unicode corruption is repaired conservatively
    across the entire lesson, and structurally invalid MCQs fail closed instead
    of being published with contradictory keys.
    """
    if not isinstance(data, dict):
        return data
    stats = {'unicode_repairs': 0}
    out = _sanitize_tree(deepcopy(data), stats)
    pages = out.get('pages')
    if not isinstance(pages, list):
        if stats['unicode_repairs']:
            out['_integrity_unicode_repairs'] = stats['unicode_repairs']
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
    if stats['unicode_repairs']:
        out['_integrity_unicode_repairs'] = stats['unicode_repairs']
    return out
