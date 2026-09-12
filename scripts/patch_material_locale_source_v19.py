from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
app_path = root / 'public' / 'js' / 'app.js'
ai_path = root / 'services' / 'ai_engine.py'
bi_path = root / 'services' / 'bilingual_finisher.py'

app = app_path.read_text(encoding='utf-8')
start = app.find('function aulaExactAlphabetExplanation(')
end = app.find('\n}\n', start)
if start < 0 or end < 0:
    raise RuntimeError('v19 alphabet resolver missing')
end += 3
new_fn = '''function aulaExactAlphabetExplanation(it, rawTerm, courseLang, uiLang) {
  const item = (it && typeof it === 'object') ? it : {};
  if (uiLang === 'tr') {
    return safeStr(item.explanation_tr || item.turkish_explanation || item.desc_tr).trim();
  }
  return safeStr(item.explanation_en || item.english_explanation || item.desc_en || item.explanation).trim();
}
'''
app = app[:start] + new_fn + app[end:]

for text in [
    'harfinin telaffuzu hedef dilin ses kurallarına göre yapılır',
    'harfi hedef dilin standart ses kurallarına göre telaffuz edilir',
    "follows the target language's pronunciation rules",
    "follows the target language's standard pronunciation rules",
]:
    app = app.replace(text, '')

# Any post-render helper may normalize badges only; it must not replace explanations.
fstart = app.find('function aulaFinalizeAlphabetCards(')
if fstart >= 0:
    fend = app.find('\n}\n', fstart)
    if fend >= 0:
        fend += 3
        badge_only = '''function aulaFinalizeAlphabetCards(container) {
  if (!container || typeof container.querySelectorAll !== 'function') return;
  container.querySelectorAll('.study-vocab-card').forEach(card => {
    const termEl = card.querySelector('.vocab-term-text');
    const badgeEl = card.querySelector('.vocab-meaning-pill');
    if (!termEl || !badgeEl) return;
    const rawTerm = safeStr(termEl.textContent).trim();
    const token = (typeof aulaCanonicalAlphabetToken === 'function') ? aulaCanonicalAlphabetToken(rawTerm) : rawTerm;
    const badgeText = safeStr(badgeEl.textContent).trim();
    if (!/(?:harfi|^letter\\s+)/i.test(badgeText) || !token) return;
    badgeEl.textContent = currentLang === 'tr' ? `${token} harfi` : `Letter ${token}`;
  });
}
'''
        app = app[:fstart] + badge_only + app[fend:]

app_path.write_text(app, encoding='utf-8')

ai = ai_path.read_text(encoding='utf-8')
marker = 'ALPHABET_PRONUNCIATION_PERSISTENCE_V19'
if marker not in ai:
    anchor = '4. Strict Two-Track Isolation:'
    if anchor not in ai:
        raise RuntimeError('v19 AI prompt anchor missing')
    rule = '''ALPHABET_PRONUNCIATION_PERSISTENCE_V19:
- For every alphabet, letter, or phonetics item in pages[].items, pronunciation pedagogy is persisted material data.
- Each item must include both explanation_en and explanation_tr when the material is created.
- explanation_en is natural learner-facing English pronunciation guidance.
- explanation_tr is natural learner-facing Turkish pronunciation guidance.
- Never defer either field to frontend translation, runtime AI, dictionary fallback, or viewer-side enrichment.
- Never use a generic definition of a letter or generic target-language pronunciation prose.

'''
    ai = ai.replace(anchor, rule + anchor, 1)
ai_path.write_text(ai, encoding='utf-8')

bi = bi_path.read_text(encoding='utf-8')
marker2 = 'ALPHABET_PRONUNCIATION_FINALIZER_V19'
if marker2 not in bi:
    anchor = '    # 2. Batch translate everything missing\n'
    if anchor not in bi:
        raise RuntimeError('v19 bilingual anchor missing')
    extra = '''    # ALPHABET_PRONUNCIATION_FINALIZER_V19
    def _collect_pronunciation_explanations_v19(node):
        if isinstance(node, list):
            for child in node:
                _collect_pronunciation_explanations_v19(child)
            return
        if not isinstance(node, dict):
            return
        en = str(node.get('explanation_en') or node.get('explanation') or '').strip()
        tr = str(node.get('explanation_tr') or '').strip()
        if en and not tr:
            to_translate_to_tr.append(en)
        for value in node.values():
            if isinstance(value, (dict, list)):
                _collect_pronunciation_explanations_v19(value)

    for _tid, _ttitle, _content in topic_data_list:
        _collect_pronunciation_explanations_v19(_content)

'''
    bi = bi.replace(anchor, extra + anchor, 1)

    anchor2 = '            # Save enriched bilingual content\n'
    if anchor2 not in bi:
        raise RuntimeError('v19 bilingual save anchor missing')
    extra2 = '''            def _apply_pronunciation_explanations_v19(node):
                if isinstance(node, list):
                    for child in node:
                        _apply_pronunciation_explanations_v19(child)
                    return
                if not isinstance(node, dict):
                    return
                en = str(node.get('explanation_en') or node.get('explanation') or '').strip()
                tr = str(node.get('explanation_tr') or '').strip()
                if en and not node.get('explanation_en'):
                    node['explanation_en'] = en
                if en and not tr:
                    translated = trans_map.get(en)
                    if translated and str(translated).strip() and str(translated).strip() != en:
                        node['explanation_tr'] = str(translated).strip()
                for value in node.values():
                    if isinstance(value, (dict, list)):
                        _apply_pronunciation_explanations_v19(value)
            _apply_pronunciation_explanations_v19(content)

'''
    bi = bi.replace(anchor2, extra2 + anchor2, 1)
bi_path.write_text(bi, encoding='utf-8')

for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\\.js\\?v=[^\"\']+', 'app.js?v=20260913_quality_v19', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')

final_app = app_path.read_text(encoding='utf-8')
if 'return safeStr(item.explanation_tr' not in final_app or 'return safeStr(item.explanation_en' not in final_app:
    raise RuntimeError('v19 stored bilingual explanation guard failed')
print('Applied persisted bilingual pronunciation source v19')
