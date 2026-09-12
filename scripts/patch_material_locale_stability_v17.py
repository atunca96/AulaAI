from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
app_path = root / 'public' / 'js' / 'app.js'
app = app_path.read_text(encoding='utf-8')

old = "${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(_aulaImmediateTurkishExplanation(it, kStr, briefExpl, courseLang))) : sanitizeEnglishExplanation(safeStr(briefExpl), kStr))}"
new = "${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(briefExpl)) : sanitizeEnglishExplanation(safeStr(briefExpl), kStr))}"
if old in app:
    app = app.replace(old, new, 1)

app_path.write_text(app, encoding='utf-8')
for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\.js\?v=[^\"\']+', 'app.js?v=20260913_quality_v17', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')
print('Applied final synchronous alphabet render guard')
