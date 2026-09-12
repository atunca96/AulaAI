from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
app_path = root / 'public' / 'js' / 'app.js'
app = app_path.read_text(encoding='utf-8')

old = "                    const briefExpl = resolveItemExplanation(it, kStr, safeStr(v), currentLang);"
new = """                    const _letterPhon = isLetter && typeof getClientLetterPhonetics === 'function' ? (getClientLetterPhonetics(courseLang, kStr) || {}) : {};
                    const briefExpl = isLetter
                      ? (currentLang === 'tr'
                          ? (_letterPhon.explanation_tr || (_letterPhon.phonetic_tr ? `${kStr} harfi ${_letterPhon.phonetic_tr} olarak telaffuz edilir.` : `${kStr} harfi hedef dilin standart ses kurallarına göre telaffuz edilir.`))
                          : (_letterPhon.explanation_en || (_letterPhon.phonetic_en ? `${kStr} is pronounced ${_letterPhon.phonetic_en}.` : `${kStr} follows the target language's standard pronunciation rules.`)))
                      : resolveItemExplanation(it, kStr, safeStr(v), currentLang);"""
if old not in app:
    raise RuntimeError('alphabet explanation anchor missing')
app = app.replace(old, new, 1)

app_path.write_text(app, encoding='utf-8')
for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\.js\?v=[^\"\']+', 'app.js?v=20260913_quality_v16', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')
print('Applied synchronous universal alphabet phonetics')
