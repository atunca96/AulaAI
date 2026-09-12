from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
app_path = root / 'public' / 'js' / 'app.js'
app = app_path.read_text(encoding='utf-8')

marker = 'const AULA_GERMAN_ALPHABET_EN = {'
if marker not in app:
    anchor = "const AULA_GERMAN_ALPHABET_TR = {\n"
    if anchor not in app:
        raise RuntimeError('v14: German Turkish alphabet bank anchor missing')

    english_bank = r'''const AULA_GERMAN_ALPHABET_EN = {
  'A': "An open vowel close to the 'a' in 'father'; it can be short or long in German.",
  'Ä': "A front vowel similar to the 'e' in 'bed'; it can be short or long.",
  'B': "Usually pronounced like English 'b' at the start of a syllable; at the end of a word it is often devoiced and sounds closer to 'p'.",
  'C': "Mostly found in loanwords; depending on the word it may sound like 'k', 'ts', or 's'.",
  'D': "Usually pronounced like English 'd'; at the end of a word it is often devoiced and sounds closer to 't'.",
  'E': "A front vowel with both short and long forms; its exact quality depends on the word.",
  'F': "Pronounced like English 'f'.",
  'G': "Usually pronounced like a hard English 'g'; at the end of a word it may be devoiced and sound closer to 'k'.",
  'H': "Pronounced as 'h' at the start of a word or syllable; in some positions it is silent and marks the preceding vowel as long.",
  'I': "A front vowel similar to the 'i' in 'machine' when long; German also has a shorter form.",
  'J': "Pronounced like English 'y' in 'yes'; for example, 'ja' begins with a 'y' sound.",
  'K': "Pronounced like English 'k'.",
  'L': "Pronounced as a clear 'l' sound, similar to the 'l' in 'light'.",
  'M': "Pronounced like English 'm'.",
  'N': "Pronounced like English 'n'.",
  'O': "A rounded back vowel with short and long forms.",
  'Ö': "A rounded front vowel; English has no exact equivalent, roughly between 'e' and 'o'.",
  'P': "Pronounced like English 'p'.",
  'Q': "Almost always appears as 'qu' and is normally pronounced like 'kv'.",
  'R': "Pronunciation varies by region; in standard German it is often produced farther back in the mouth or throat.",
  'S': "Before a vowel at the start of a word it is often pronounced like English 'z'; in many other positions it sounds like 's'.",
  'ß': "Represents a sharp 's' sound and is pronounced like 'ss'.",
  'T': "Pronounced like English 't'.",
  'U': "A rounded back vowel with short and long forms, similar to the vowel in 'food' when long.",
  'Ü': "A rounded front vowel; English has no exact equivalent, roughly an 'ee' sound pronounced with rounded lips.",
  'V': "In many native German words it is pronounced like English 'f'; in some loanwords it is pronounced like 'v'.",
  'W': "Pronounced like English 'v'.",
  'X': "Usually pronounced 'ks'.",
  'Y': "Mostly appears in loanwords and may represent sounds similar to German 'ü', 'i', or 'y' depending on the word.",
  'Z': "Pronounced 'ts', as at the beginning of the German word 'Zeit'."
};

'''
    app = app.replace(anchor, english_bank + anchor, 1)

helper_marker = 'function _aulaImmediateEnglishExplanation('
if helper_marker not in app:
    anchor = 'function _aulaImmediateTurkishExplanation(it, term, fallback, courseLang) {\n'
    if anchor not in app:
        raise RuntimeError('v14: immediate Turkish resolver anchor missing')

    helper = r'''function _aulaImmediateEnglishExplanation(it, term, fallback, courseLang) {
  const rawTerm = safeStr(term).trim();
  const langKey = safeStr(courseLang || (currentCourse && currentCourse.language) || '').toLowerCase();
  const base = (typeof extractBaseLetter === 'function') ? extractBaseLetter(rawTerm) : rawTerm.toUpperCase();
  const isAlphabet = (typeof isLetterLike === 'function') ? isLetterLike(rawTerm) : /^[A-Za-zÄÖÜäöüßÑñ]{1,2}$/.test(rawTerm);

  if (isAlphabet) {
    if (/german|deutsch|almanca/.test(langKey)) {
      const deKey = rawTerm === 'ß' ? 'ß' : (rawTerm.length <= 2 ? rawTerm.toUpperCase() : base);
      if (AULA_GERMAN_ALPHABET_EN[deKey]) return AULA_GERMAN_ALPHABET_EN[deKey];
      if (AULA_GERMAN_ALPHABET_EN[base]) return AULA_GERMAN_ALPHABET_EN[base];
    }

    const phon = (typeof getClientLetterPhonetics === 'function') ? (getClientLetterPhonetics(courseLang, base) || {}) : {};
    if (phon.explanation_en && safeStr(phon.explanation_en).trim()) return safeStr(phon.explanation_en).trim();

    const explicitEn = it && safeStr(it.explanation_en || it.english_explanation || it.desc_en).trim();
    if (explicitEn) return explicitEn;

    const guide = safeStr(phon.phonetic_en || '').trim();
    if (guide) return `${rawTerm || base} is pronounced ${guide}.`;
  }

  return safeStr(fallback);
}

'''
    app = app.replace(anchor, helper + anchor, 1)

old = "${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(_aulaImmediateTurkishExplanation(it, kStr, briefExpl, courseLang))) : sanitizeEnglishExplanation(safeStr(briefExpl), kStr))}"
new = "${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(_aulaImmediateTurkishExplanation(it, kStr, briefExpl, courseLang))) : sanitizeEnglishExplanation(safeStr(_aulaImmediateEnglishExplanation(it, kStr, briefExpl, courseLang)), kStr))}"
if old not in app:
    raise RuntimeError('v14: final vocab explanation render anchor missing')
app = app.replace(old, new, 1)

app_path.write_text(app, encoding='utf-8')
for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\.js\?v=[^\"\']+', 'app.js?v=20260913_quality_v14', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')

print('Applied stable bilingual alphabet pedagogy v14')
