from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
app_path = root / 'public' / 'js' / 'app.js'
app = app_path.read_text(encoding='utf-8')

# Alphabet cards must use one canonical token ("K k" -> "K", "LL ll" -> "LL")
# and an exact target-language phonetics bank. Never fall through to another
# language's alphabet data and never depend on lazy translation for the card.
helper_marker = 'function aulaCanonicalAlphabetToken('
if helper_marker not in app:
    anchor = 'function getClientLetterPhonetics(lang, letter) {\n'
    if anchor not in app:
        raise RuntimeError('v14 strict alphabet helper anchor missing')
    helper = r'''function aulaCanonicalAlphabetToken(raw) {
  const s = safeStr(raw).trim();
  if (!s) return '';
  const parts = s.split(/[,\s/|]+/u).filter(Boolean);
  let token = parts[0] || s;
  if (token === 'ß') return 'ß';
  if (token.length <= 3) token = token.toUpperCase();
  return token;
}

function aulaAlphabetLanguageKey(lang) {
  const l = safeStr(lang).toLowerCase().trim();
  const aliases = [
    ['spanish', ['spanish', 'español', 'espanol', 'ispanyol', 'ispanyolca']],
    ['german', ['german', 'deutsch', 'almanca', 'alman']],
    ['french', ['french', 'français', 'francais', 'fransızca', 'fransizca']],
    ['italian', ['italian', 'italiano', 'italyanca']],
    ['portuguese', ['portuguese', 'português', 'portugues', 'portekizce']],
    ['russian', ['russian', 'русский', 'rusça', 'rusca']],
    ['chinese', ['chinese', '中文', 'çince', 'cince']],
    ['japanese', ['japanese', '日本語', 'japonca']],
    ['arabic', ['arabic', 'العربية', 'arapça', 'arapca']],
    ['dutch', ['dutch', 'nederlands', 'felemenkçe', 'felemenkce', 'hollandaca']],
    ['swedish', ['swedish', 'svenska', 'isveççe', 'isvecce']],
    ['korean', ['korean', '한국어', 'korece']],
    ['greek', ['greek', 'ελληνικά', 'yunanca']],
    ['turkish', ['turkish', 'türkçe', 'turkce']]
  ];
  for (const [key, names] of aliases) {
    if (names.some(name => l.includes(name))) return key;
  }
  if (typeof ALPHABET_PHONETICS_MAP !== 'undefined' && ALPHABET_PHONETICS_MAP[l]) return l;
  return '';
}

function aulaStrictLetterPhonetics(lang, raw) {
  const token = aulaCanonicalAlphabetToken(raw);
  const langKey = aulaAlphabetLanguageKey(lang);
  if (!token || !langKey || typeof ALPHABET_PHONETICS_MAP === 'undefined') return {};
  const bank = ALPHABET_PHONETICS_MAP[langKey];
  if (!bank || typeof bank !== 'object') return {};
  return bank[token] || bank[token.toUpperCase()] || {};
}

'''
    app = app.replace(anchor, helper + anchor, 1)

# Never silently assume Spanish while the target course language is unresolved.
# That was the source of e.g. German/French "L l" receiving Spanish LL pedagogy.
app = app.replace(
    "const courseLang = (currentCourse && currentCourse.language) ? currentCourse.language : 'Spanish';",
    "const courseLang = (currentCourse && currentCourse.language) ? currentCourse.language : safeStr((topic && (topic.language || topic.target_language || topic.course_language)) || '');"
)

# Every alphabet lookup in the material renderer is strict and pair-aware.
app = app.replace('getClientLetterPhonetics(courseLang, sTrimmed)', 'aulaStrictLetterPhonetics(courseLang, sTrimmed)')
app = app.replace('getClientLetterPhonetics(courseLang, kStr)', 'aulaStrictLetterPhonetics(courseLang, kStr)')

old_badge = '''                      const baseL = extractBaseLetter(kStr);
                      const phon = getClientLetterPhonetics(courseLang, baseL) || {};'''
new_badge = '''                      const baseL = aulaCanonicalAlphabetToken(kStr);
                      const phon = aulaStrictLetterPhonetics(courseLang, baseL) || {};'''
if old_badge in app:
    app = app.replace(old_badge, new_badge, 1)

# v13 deliberately changed the final render path. Replace the regular-card
# explanation source with a synchronous, immutable alphabet resolver.
old_brief = "                    const briefExpl = resolveItemExplanation(it, kStr, safeStr(v), currentLang);"
new_brief = '''                    const _alphabetToken = isLetter ? aulaCanonicalAlphabetToken(kStr) : '';
                    const _letterPhon = isLetter ? (aulaStrictLetterPhonetics(courseLang, _alphabetToken) || {}) : {};
                    const briefExpl = isLetter
                      ? (currentLang === 'tr'
                          ? (_letterPhon.explanation_tr || (_letterPhon.phonetic_tr ? `${_alphabetToken} harfi ${_letterPhon.phonetic_tr} olarak telaffuz edilir.` : `${_alphabetToken} harfinin telaffuzu hedef dilin ses kurallarına göre yapılır.`))
                          : (_letterPhon.explanation_en || (_letterPhon.phonetic_en ? `${_alphabetToken} is pronounced ${_letterPhon.phonetic_en}.` : `${_alphabetToken} follows the target language's pronunciation rules.`)))
                      : resolveItemExplanation(it, kStr, safeStr(v), currentLang);'''
if old_brief not in app:
    raise RuntimeError('v14 strict alphabet explanation anchor missing')
app = app.replace(old_brief, new_brief, 1)

# The v13 helper can consult permissive legacy fallbacks. For alphabet cards the
# briefExpl above is already final, so render it directly and synchronously.
old_render = "${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(_aulaImmediateTurkishExplanation(it, kStr, briefExpl, courseLang))) : sanitizeEnglishExplanation(safeStr(briefExpl), kStr))}"
new_render = "${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(briefExpl)) : sanitizeEnglishExplanation(safeStr(briefExpl), _alphabetToken || kStr))}"
if old_render in app:
    app = app.replace(old_render, new_render, 1)

# Alphabet examples must also be locale-ready on first paint. Reuse stored or
# exact-bank bilingual values; do not launch a lazy translation just for a card.
old_bank = '''                    const bankHit = getClientVocabExample(courseLang, kStr) || {};
                    const exampleTarget = it.example || bankHit.example || '';
                    const rawExEn = it.example_en || bankHit.example_en || '';
                    const rawExTr = it.example_tr || bankHit.example_tr || '';
                    let exampleTrans = '';
                    if (currentLang === 'tr') {
                      if (rawExTr && rawExTr.trim()) {
                        exampleTrans = rawExTr.trim();
                      } else if (rawExEn && rawExEn.trim()) {
                        exampleTrans = translateEducationalText(rawExEn, 'tr');
                      }
                    } else {
                      if (rawExEn && rawExEn.trim()) {
                        exampleTrans = rawExEn.trim();
                      } else if (rawExTr && rawExTr.trim()) {
                        exampleTrans = translateEducationalText(rawExTr, 'en');
                      }
                    }'''
new_bank = '''                    const bankHit = isLetter ? _letterPhon : (getClientVocabExample(courseLang, kStr) || {});
                    const exampleTarget = it.example || bankHit.example || '';
                    const rawExEn = it.example_en || bankHit.example_en || (isLetter ? enRawV : '') || '';
                    const rawExTr = it.example_tr || bankHit.example_tr || (isLetter ? trRawV : '') || '';
                    let exampleTrans = '';
                    if (isLetter) {
                      exampleTrans = currentLang === 'tr' ? safeStr(rawExTr).trim() : safeStr(rawExEn).trim();
                    } else if (currentLang === 'tr') {
                      if (rawExTr && rawExTr.trim()) {
                        exampleTrans = rawExTr.trim();
                      } else if (rawExEn && rawExEn.trim()) {
                        exampleTrans = translateEducationalText(rawExEn, 'tr');
                      }
                    } else {
                      if (rawExEn && rawExEn.trim()) {
                        exampleTrans = rawExEn.trim();
                      } else if (rawExTr && rawExTr.trim()) {
                        exampleTrans = translateEducationalText(rawExTr, 'en');
                      }
                    }'''
if old_bank not in app:
    raise RuntimeError('v14 alphabet example anchor missing')
app = app.replace(old_bank, new_bank, 1)

# Build-time invariants: if any of these fail, do not deploy a half-applied fix.
if "getClientLetterPhonetics(courseLang, kStr)" in app:
    raise RuntimeError('v14 invariant failed: permissive kStr alphabet lookup remains')
if "_aulaImmediateTurkishExplanation(it, kStr, briefExpl, courseLang)" in app:
    raise RuntimeError('v14 invariant failed: lazy/permissive alphabet render remains')
if "const _alphabetToken = isLetter ? aulaCanonicalAlphabetToken(kStr) : '';" not in app:
    raise RuntimeError('v14 invariant failed: canonical alphabet token missing')

app_path.write_text(app, encoding='utf-8')
for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\.js\?v=[^\"\']+', 'app.js?v=20260913_quality_v17', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')

print('Applied strict synchronous alphabet locale resolver v17')
