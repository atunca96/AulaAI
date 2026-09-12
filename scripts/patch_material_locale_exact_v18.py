from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
app_path = root / 'public' / 'js' / 'app.js'
app = app_path.read_text(encoding='utf-8')

helper_marker = 'function aulaExactAlphabetExplanation('
if helper_marker not in app:
    anchor = 'function resolveItemExplanation(it, term, translation, lang = currentLang) {\n'
    if anchor not in app:
        raise RuntimeError('v18: explanation resolver anchor missing')
    helper = r'''function aulaExactAlphabetExplanation(it, rawTerm, courseLang, uiLang) {
  const item = (it && typeof it === 'object') ? it : {};
  const token = (typeof aulaCanonicalAlphabetToken === 'function')
    ? aulaCanonicalAlphabetToken(rawTerm)
    : safeStr(rawTerm).trim().split(/[,\s/|]+/u).filter(Boolean)[0]?.toUpperCase() || '';
  const langKey = (typeof aulaAlphabetLanguageKey === 'function')
    ? aulaAlphabetLanguageKey(courseLang)
    : safeStr(courseLang).toLowerCase().trim();
  const phon = (typeof aulaStrictLetterPhonetics === 'function')
    ? (aulaStrictLetterPhonetics(courseLang, token) || {})
    : {};

  if (uiLang === 'tr') {
    const explicitTr = safeStr(item.explanation_tr || item.turkish_explanation || item.desc_tr).trim();
    if (explicitTr) return explicitTr;
    const bankTr = safeStr(phon.explanation_tr).trim();
    if (bankTr) return bankTr;
    if (langKey === 'german' && typeof AULA_GERMAN_ALPHABET_TR !== 'undefined') {
      const deTr = safeStr(AULA_GERMAN_ALPHABET_TR[token]).trim();
      if (deTr) return deTr;
    }
    const englishSource = safeStr(item.explanation_en || item.english_explanation || item.desc_en || item.explanation).trim();
    if (englishSource && window.EDUCATIONAL_SENTENCE_MAP_EN_TR) {
      const exactTr = safeStr(window.EDUCATIONAL_SENTENCE_MAP_EN_TR[englishSource]).trim();
      if (exactTr) return exactTr;
    }
    return '';
  }

  const explicitEn = safeStr(item.explanation_en || item.english_explanation || item.desc_en || item.explanation).trim();
  if (explicitEn) return explicitEn;
  const bankEn = safeStr(phon.explanation_en).trim();
  if (bankEn) return bankEn;
  return '';
}

'''
    app = app.replace(anchor, helper + anchor, 1)

old = '''                    const _alphabetToken = isLetter ? aulaCanonicalAlphabetToken(kStr) : '';
                    const _letterPhon = isLetter ? (aulaStrictLetterPhonetics(courseLang, _alphabetToken) || {}) : {};
                    const briefExpl = isLetter
                      ? (currentLang === 'tr'
                          ? (_letterPhon.explanation_tr || (_letterPhon.phonetic_tr ? `${_alphabetToken} harfi ${_letterPhon.phonetic_tr} olarak telaffuz edilir.` : `${_alphabetToken} harfinin telaffuzu hedef dilin ses kurallarına göre yapılır.`))
                          : (_letterPhon.explanation_en || (_letterPhon.phonetic_en ? `${_alphabetToken} is pronounced ${_letterPhon.phonetic_en}.` : `${_alphabetToken} follows the target language's pronunciation rules.`)))
                      : resolveItemExplanation(it, kStr, safeStr(v), currentLang);'''
new = '''                    const _alphabetToken = isLetter ? aulaCanonicalAlphabetToken(kStr) : '';
                    const _letterPhon = isLetter ? (aulaStrictLetterPhonetics(courseLang, _alphabetToken) || {}) : {};
                    const briefExpl = isLetter
                      ? aulaExactAlphabetExplanation(it, kStr, courseLang, currentLang)
                      : resolveItemExplanation(it, kStr, safeStr(v), currentLang);'''
if old not in app:
    raise RuntimeError('v18: final alphabet explanation block not found')
app = app.replace(old, new, 1)

# No alphabet explanation may be synthesized from a generic placeholder.
banned = [
    "harfinin telaffuzu hedef dilin ses kurallarına göre yapılır",
    "harfi hedef dilin standart ses kurallarına göre telaffuz edilir",
    "follows the target language's pronunciation rules",
    "follows the target language's standard pronunciation rules",
]
for text in banned:
    app = app.replace(text, '')

app_path.write_text(app, encoding='utf-8')

# Cache-bust the client so stale fallback code cannot survive a deploy.
for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\.js\?v=[^\"\']+', 'app.js?v=20260913_quality_v18', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')

# Build-time guarantees: exact resolver must be present, generic alphabet prose absent.
final_app = app_path.read_text(encoding='utf-8')
if 'function aulaExactAlphabetExplanation(' not in final_app:
    raise RuntimeError('v18: exact alphabet resolver missing after patch')
for text in banned:
    if text in final_app:
        raise RuntimeError(f'v18: generic fallback still present: {text}')
print('Applied exact no-fallback alphabet localization v18')
