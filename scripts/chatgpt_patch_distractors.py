from pathlib import Path

p = Path('services/assessment_validation.py')
s = p.read_text(encoding='utf-8')

export_anchor = '    "instructional_prose_ratio", "out_of_scope_terms",\n]'
export_new = '    "instructional_prose_ratio", "out_of_scope_terms",\n    "giveaway_features", "normalize_option", "mixed_spelling_variants",\n]'
assert export_anchor in s
s = s.replace(export_anchor, export_new, 1)

norm_anchor = '\n\ndef normalize_token(text: Any) -> str:\n'
helpers = '''

_QUOTED_FEATURE = re.compile(r"[\\'\\\"‘’“”«»]\\s*([^\\s\\'\\\"‘’“”«»]{1,3})\\s*[\\'\\\"‘’“”«»]")
_CAPITALISED_FEATURE = re.compile(r"(?<![^\\W\\d_])([^\\W\\d_]{1,3})(?![^\\W\\d_])")


def giveaway_features(item: Dict[str, Any]) -> List[str]:
    """Named surface features that only the keyed option exhibits."""
    stem = str(item.get("prompt") or "")
    answer = str(item.get("answer") or "").casefold()
    if not stem or not answer:
        return []
    opts = item.get("options")
    if isinstance(opts, list) and opts:
        pool = [str(o).casefold() for o in opts if str(o).strip()]
    else:
        ds = item.get("distractors")
        pool = [answer] + [str(d).casefold() for d in (ds if isinstance(ds, list) else []) if str(d).strip()]
    if len(pool) < 3:
        return []
    candidates = list(_QUOTED_FEATURE.findall(stem))
    if any(ch.islower() for ch in stem):
        candidates += [tok for tok in _CAPITALISED_FEATURE.findall(stem) if tok.isupper()]
    found = []
    for raw in candidates:
        feature = raw.casefold()
        if not feature or not all(ch.isalpha() for ch in feature):
            continue
        if feature in answer and sum(1 for option in pool if feature in option) == 1 and feature not in found:
            found.append(feature)
    return found


def normalize_option(text: Any) -> str:
    """Normalize option identity without erasing meaningful diacritics."""
    if not text:
        return ""
    value = unicodedata.normalize("NFC", str(text).strip().casefold())
    value = re.sub(r"[^\\w\\s]", "", value, flags=re.UNICODE)
    return re.sub(r"\\s+", " ", value).strip()


def mixed_spelling_variants(options: Sequence[Any]) -> bool:
    """Catch one accent-stripped typo mixed among otherwise distinct forms."""
    opts = [str(o).strip() for o in (options or []) if str(o).strip()]
    if len(opts) < 4 or any(len(normalize_option(o)) < 3 for o in opts):
        return False
    groups = {normalize_token(o) for o in opts}
    return 1 < len(groups) < len(opts)
'''
assert norm_anchor in s
s = s.replace(norm_anchor, helpers + norm_anchor, 1)

for old, new in {
    'keys = [normalize_token(answer)] + [normalize_token(d) for d in clean_d]': 'keys = [normalize_option(answer)] + [normalize_option(d) for d in clean_d]',
    'if normalize_token(answer) in {normalize_token(d) for d in clean_d}:': 'if normalize_option(answer) in {normalize_option(d) for d in clean_d}:',
    'opt_keys = [normalize_token(o) for o in options]': 'opt_keys = [normalize_option(o) for o in options]',
    'if normalize_token(answer) and normalize_token(answer) not in set(opt_keys):': 'if normalize_option(answer) and normalize_option(answer) not in set(opt_keys):',
}.items():
    assert old in s, old
    s = s.replace(old, new, 1)

anchor = '    if looks_like_translation_question(stem):\n        problems.append("translation_question")\n\n'
block = anchor + '    for feature in giveaway_features(item):\n        problems.append(f"feature_only_in_key:{feature}")\n\n    if mixed_spelling_variants(item.get("options") or ([answer] + clean_d)):\n        problems.append("mixed_spelling_variants")\n\n'
assert anchor in s
s = s.replace(anchor, block, 1)

drop_anchor = '    "answer_revealed_in_", "out_of_scope:",\n)'
drop_new = '    "answer_revealed_in_", "out_of_scope:", "feature_only_in_key:",\n    "mixed_spelling_variants",\n)'
assert drop_anchor in s
s = s.replace(drop_anchor, drop_new, 1)
p.write_text(s, encoding='utf-8')

q = Path('services/question_contract.py')
qs = q.read_text(encoding='utf-8')
contract_anchor = '- Reject vocabulary that sounds elevated or formal but is semantically misselected in context. Superficial formality is not precision.\n'
contract_extra = '- REALISTIC ERROR: every distractor must be something a learner at CEFR {level} could genuinely choose: interference, an overgeneralised rule, the right form for the wrong category, or a confusable neighbour. Never use a correct option with an accent or letter mechanically removed as a throwaway typo among otherwise real forms.\n- SHARED TRIGGER: when the stem names a spelling, sound or form feature, every option must carry that feature on the surface; otherwise the answer can be found by scanning for the named letter instead of knowing the rule.\n'
assert contract_anchor in qs
qs = qs.replace(contract_anchor, contract_anchor + contract_extra, 1)
q.write_text(qs, encoding='utf-8')
