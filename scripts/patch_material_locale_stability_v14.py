from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
app_path = root / 'public' / 'js' / 'app.js'
app = app_path.read_text(encoding='utf-8')

# Universal guard: alphabet cards must never use the generic dictionary definition.
app = app.replace("const briefExpl = resolveItemExplanation(it, kStr, safeStr(v), currentLang);", "const briefExpl = isLetter ? ((currentLang === 'tr') ? (it.explanation_tr || it.phonetic_tr || it.pronunciation_tr || 'Bu harfin telaffuzu hedef dilin ses kurallarına göre yapılır.') : (it.explanation_en || it.phonetic_en || it.pronunciation_en || 'This letter follows the target language pronunciation rules.')) : resolveItemExplanation(it, kStr, safeStr(v), currentLang);", 1)
app_path.write_text(app, encoding='utf-8')
for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\.js\?v=[^\"\']+', 'app.js?v=20260913_quality_v15', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')
print('Applied universal alphabet fallback guard')
