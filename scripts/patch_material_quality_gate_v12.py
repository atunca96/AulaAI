from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
ai_path = root / 'services' / 'ai_engine.py'
bi_path = root / 'services' / 'bilingual_finisher.py'
app_path = root / 'public' / 'js' / 'app.js'
pdf_path = root / 'services' / 'pdf_renderer_v12.py'

# 1) Generation quality rules: idempotent, non-brittle.
ai = ai_path.read_text(encoding='utf-8')
marker = '- SELF-CONTAINED QUESTION RULE:'
if marker not in ai:
    anchor = '- Do NOT systematically put the correct answer first. Vary the correct option position across questions; post-processing may also reorder options while preserving index alignment.'
    extra = '''\n   - SELF-CONTAINED QUESTION RULE: every MCQ must contain ALL information needed to answer it inside the prompt and options. Never emit a stem such as "Complete the sentence", "Choose the correct conjugation", or "Choose the reflexive pronoun" without the actual sentence, subject, blank, or scenario.\n   - ANSWER CONSISTENCY RULE: `answer`, `correct_index`, and `explanation` must identify the SAME option. Verify `options[correct_index] == answer`, exactly one option is defensibly correct, and the explanation supports that same answer.\n   - UI LOCALIZATION COMPLETENESS: all learner-facing explanatory/meta-language strings must be complete in English and Turkish before the lesson is returned. Never leave English instructional prose as the Turkish display value. Target-language material being taught must remain unchanged.\n'''
    if anchor in ai:
        ai = ai.replace(anchor, anchor + extra, 1)

plain_anchor = '- For A1-A2, use short concrete learner-facing explanations, one main idea at a time, and everyday examples.'
if plain_anchor in ai and 'Never make A1 depth depend on jargon.' not in ai:
    ai = ai.replace(plain_anchor, plain_anchor + ' For A1 specifically, prefer plain descriptions instead of specialist labels such as apocope, oxytone/aguda, null-subject/pro-drop, univerbation, phoneme, allomorph, or morphophonology. Never make A1 depth depend on jargon.', 1)
ai_path.write_text(ai, encoding='utf-8')

# 2) Bilingual finalizer: complete nested learner-facing Turkish before build completion.
bi = bi_path.read_text(encoding='utf-8')
if 'UI_LOCALIZABLE_KEYS_V12' not in bi:
    collect_anchor = '    # 2. Batch translate everything missing\n'
    helper = r'''    UI_LOCALIZABLE_KEYS_V12 = {
        'title', 'text', 'explanation', 'intro', 'description', 'instructions',
        'rule', 'analysis', 'note', 'context', 'breakdown', 'label', 'hint'
    }

    def _collect_nested_ui_v12(node):
        if isinstance(node, list):
            for child in node:
                _collect_nested_ui_v12(child)
            return
        if not isinstance(node, dict):
            return
        for key, value in list(node.items()):
            if key in UI_LOCALIZABLE_KEYS_V12 and isinstance(value, str) and value.strip():
                tr_key = key + '_tr'
                existing = node.get(tr_key)
                if not existing or str(existing).strip() == value.strip():
                    to_translate_to_tr.append(value.strip())
            if isinstance(value, (dict, list)):
                _collect_nested_ui_v12(value)

    for _tid, _ttitle, _content in topic_data_list:
        _collect_nested_ui_v12(_content)

'''
    if collect_anchor in bi:
        bi = bi.replace(collect_anchor, helper + collect_anchor, 1)

    apply_anchor = '            # Save enriched bilingual content\n'
    apply = r'''            def _apply_nested_ui_v12(node):
                if isinstance(node, list):
                    for child in node:
                        _apply_nested_ui_v12(child)
                    return
                if not isinstance(node, dict):
                    return
                for key, value in list(node.items()):
                    if key in UI_LOCALIZABLE_KEYS_V12 and isinstance(value, str) and value.strip():
                        tr_key = key + '_tr'
                        existing = node.get(tr_key)
                        if not existing or str(existing).strip() == value.strip():
                            translated = trans_map.get(value.strip())
                            if translated and translated.strip() and translated.strip() != value.strip():
                                node[tr_key] = translated.strip()
                    if isinstance(value, (dict, list)):
                        _apply_nested_ui_v12(value)
            _apply_nested_ui_v12(content)

            # Keep answer / correct_index synchronized for persisted material.
            for _page in content.get('pages', []) if isinstance(content.get('pages', []), list) else []:
                if not isinstance(_page, dict):
                    continue
                _opts = _page.get('options') if isinstance(_page.get('options'), list) else []
                _opts = [str(x).strip() for x in _opts]
                _ans = str(_page.get('answer') or '').strip()
                if _ans in _opts:
                    _page['correct_index'] = _opts.index(_ans)
                    _page['distractors'] = [x for x in _opts if x != _ans]

'''
    if apply_anchor in bi:
        bi = bi.replace(apply_anchor, apply + apply_anchor, 1)
bi_path.write_text(bi, encoding='utf-8')

# 3) Frontend: Turkish mode must never paint English instructional text first.
app = app_path.read_text(encoding='utf-8')
if 'function _aulaLooksEnglishInstruction' not in app:
    anchor = 'function resolveItemExplanation(it, term, translation, lang = currentLang) {\n'
    helper = r'''function _aulaLooksEnglishInstruction(value) {
  if (!value || typeof value !== 'string') return false;
  const s = value.trim();
  if (!s || /[çğıöşüÇĞİÖŞÜ]/.test(s)) return false;
  const words = s.toLowerCase().match(/[a-z]+/g) || [];
  if (words.length < 3) return false;
  const markers = new Set(['the','a','an','is','are','to','of','and','or','like','with','before','after','pronounced','sound','letter','word','used','means','identical','voiced','voiceless','vowel','consonant','stop','fricative','choose','select','complete','stressed','english']);
  return words.filter(w => markers.has(w)).length >= 2;
}

function _aulaTurkishNow(value) {
  if (!value || typeof value !== 'string') return value || '';
  const raw = value.trim();
  if (!raw) return '';
  if (!_aulaLooksEnglishInstruction(raw)) return raw;
  // translateEducationalText may schedule a lazy translation. Never expose the
  // English source while that async result is pending.
  const translated = (typeof translateEducationalText === 'function') ? translateEducationalText(raw, 'tr') : '';
  if (translated && translated.trim() && translated.trim() !== raw && !_aulaLooksEnglishInstruction(translated)) {
    return translated.trim();
  }
  return '';
}

'''
    if anchor in app:
        app = app.replace(anchor, helper + anchor, 1)

# Hard guard at the final explanation render boundary. This is intentionally
# independent of the internal fallback chain, so no English flash can escape.
old = "${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(briefExpl)) : sanitizeEnglishExplanation(safeStr(briefExpl), kStr))}"
new = "${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(_aulaTurkishNow(briefExpl))) : sanitizeEnglishExplanation(safeStr(briefExpl), kStr))}"
if old in app:
    app = app.replace(old, new, 1)

# Page prose gets the same no-English-flash rule.
old2 = "? ((p.text_tr || p.explanation_tr) ? text : translateEducationalText(text))"
new2 = "? ((p.text_tr || p.explanation_tr) ? text : _aulaTurkishNow(translateEducationalText(text, 'tr') || text))"
if old2 in app:
    app = app.replace(old2, new2, 1)

# Meaning pills: if Turkish value is missing, do not show the English meaning
# while lazy localization catches up.
old3 = "v = resolveDualLanguage(enRawV, trRawV, 'tr', enRawV);"
new3 = "v = _aulaTurkishNow(resolveDualLanguage(enRawV, trRawV, 'tr', enRawV) || enRawV);"
if old3 in app:
    app = app.replace(old3, new3, 1)

app_path.write_text(app, encoding='utf-8')
for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\.js\?v=[^\"\']+', 'app.js?v=20260913_quality_v12', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')

# 4) PDF: preserve Turkish capital İ in headers and keep answer index coherent.
pdf = pdf_path.read_text(encoding='utf-8')
if 'insert_htmlbox(fitz.Rect(38, 17, 557, 34)' not in pdf:
    old_header = """            if idx > 0:\n                page.insert_text(fitz.Point(38, 27), f'AulaAI · {self.course_name}', fontsize=7, color=(0.42,0.42,0.42))\n            page.insert_text(fitz.Point(38, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.7, color=(0.42,0.42,0.42))\n            page.insert_text(fitz.Point(493, 823), f'{page_word} {idx+1} / {total}', fontsize=6.7, color=(0.42,0.42,0.42))\n"""
    new_header = """            if idx > 0:\n                page.insert_htmlbox(fitz.Rect(38, 17, 557, 34), f'<span style=\"font-family:sans-serif;font-size:7pt;color:#6b7280\">AulaAI · {_e(self.course_name)}</span>')\n            page.insert_htmlbox(fitz.Rect(38, 814, 430, 829), '<span style=\"font-family:sans-serif;font-size:6.7pt;color:#6b7280\">AulaAI Educational System · Self-Contained Course Material</span>')\n            page.insert_htmlbox(fitz.Rect(470, 814, 557, 829), f'<div style=\"text-align:right;font-family:sans-serif;font-size:6.7pt;color:#6b7280\">{_e(page_word)} {idx+1} / {total}</div>')\n"""
    if old_header in pdf:
        pdf = pdf.replace(old_header, new_header, 1)

# Prefer correct_index only when answer is missing; otherwise answer remains canonical.
old_answer = "                        answer = page.get('answer') or ''\n"
new_answer = """                        answer = page.get('answer') or ''\n                        if not answer and isinstance(page.get('correct_index'), int) and 0 <= page.get('correct_index') < len(raw_options):\n                            answer = raw_options[page.get('correct_index')]\n"""
if old_answer in pdf and new_answer not in pdf:
    pdf = pdf.replace(old_answer, new_answer, 1)

pdf_path.write_text(pdf, encoding='utf-8')
print('Applied robust material quality gate v12')
