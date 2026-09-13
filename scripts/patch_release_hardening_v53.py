from pathlib import Path

engine = Path("services/ai_engine.py")
s = engine.read_text(encoding="utf-8")

# Tighten field semantics at the source. Keep this replacement-only so prompt size
# stays essentially flat and runtime model-call/retry topology is unchanged.
s = s.replace(
    '"phonetic": "[IPA / phonetic guide]"',
    '"phonetic": "[standard IPA only; never learner respelling]"',
    1,
)
s = s.replace(
    '"speaker": "Speaker",',
    '"speaker": "Proper name or target-language role",\n          "speaker_en": "English role or same proper name",\n          "speaker_tr": "Turkish role or same proper name",',
    1,
)
s = s.replace(
    '"text": "Utterance in {language}"',
    '"text": "Utterance only in {language}; no instructional-language gloss words"',
    1,
)
s = s.replace(
    'FINAL SILENT PASS: canonical spelling/Unicode; pronunciation completeness and one-system consistency;',
    'FINAL SILENT PASS: canonical spelling/Unicode; pronunciation completeness and one-system consistency; verify every stated count/list/category agrees internally; verify grammatical case labels/functions are not conflated;',
    1,
)
engine.write_text(s, encoding="utf-8")

guard = Path("services/material_quality_guard.py")
g = guard.read_text(encoding="utf-8")
anchor = '    (r"\\bneuter\\b", "nötr"),\n)'
if anchor in g:
    g = g.replace(
        anchor,
        '    (r"\\bneuter\\b", "nötr"),\n'
        '    (r"\\bnominativ\\b", "Yalın Hâl"),\n'
        '    (r"\\bgenitiv\\b", "İlgi/Tamlayan Hâli"),\n'
        '    (r"\\bakkusativ\\b", "Belirtme Hâli"),\n'
        '    (r"\\bdativ\\b", "Yönelme Hâli"),\n'
        ')',
        1,
    )

old_return = '    return "".join(parts)\n\n\ndef sanitize_dialogue_speaker'
new_return = '''    text = "".join(parts)
    text = re.sub(r"\\b(Yalın Hâl|İlgi/Tamlayan Hâli|Belirtme Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\\s+[Cc]ase\\b", r"\\1", text)
    return text


def sanitize_dialogue_speaker'''
if old_return in g:
    g = g.replace(old_return, new_return, 1)
guard.write_text(g, encoding="utf-8")

renderer = Path("services/pdf_renderer_v12.py")
r = renderer.read_text(encoding="utf-8")
if "# AULAAI_RELEASE_HARDENING_V53" not in r:
    replacements = [
        (
            "r_title = _pick(rule, 'rule', 'rule_tr', is_tr) or rule.get('name') or ''",
            "r_title = _v53_instructional(_pick(rule, 'rule', 'rule_tr', is_tr) or rule.get('name') or '', is_tr)",
        ),
        (
            "r_expl = _pick(rule, 'explanation', 'explanation_tr', is_tr) or rule.get('desc') or ''",
            "r_expl = _v53_instructional(_pick(rule, 'explanation', 'explanation_tr', is_tr) or rule.get('desc') or '', is_tr)",
        ),
        (
            "r_analysis = _pick(rule, 'analysis', 'analysis_tr', is_tr) or rule.get('breakdown') or ''",
            "r_analysis = _v53_instructional(_pick(rule, 'analysis', 'analysis_tr', is_tr) or rule.get('breakdown') or '', is_tr)",
        ),
        (
            "r_example_trans = (rule.get('example_tr') or rule.get('translation_tr') or rule.get('turkish') or '') if is_tr else (rule.get('example_en') or rule.get('translation') or '')",
            "r_example_trans = _v53_instructional((rule.get('example_tr') or rule.get('translation_tr') or rule.get('turkish') or '') if is_tr else (rule.get('example_en') or rule.get('translation') or ''), is_tr)",
        ),
        (
            "blocks.append(f'<div class=\"rule\"><p class=\"p\">{_e(rule)}</p></div>')",
            "blocks.append(f'<div class=\"rule\"><p class=\"p\">{_e(_v53_instructional(rule, is_tr))}</p></div>')",
        ),
        (
            "trans_html = f' <span class=\"translation\">({_e(translated)})</span>' if translated else ''",
            "translated = _v53_instructional(translated, is_tr) if translated else translated\n                            trans_html = f' <span class=\"translation\">({_e(translated)})</span>' if translated else ''",
        ),
    ]
    for old, new in replacements:
        if old not in r:
            raise RuntimeError(f"v53 renderer anchor missing: {old[:48]}")
        r = r.replace(old, new, 1)

    r += r'''

# AULAAI_RELEASE_HARDENING_V53
def _v53_instructional(value, is_tr):
    try:
        return _v52_meta(value, "tr" if is_tr else "en")
    except Exception:
        return value
'''
    renderer.write_text(r, encoding="utf-8")

print("Applied v53 precision hardening")
