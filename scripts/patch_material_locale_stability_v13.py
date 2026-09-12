from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
app_path = root / 'public' / 'js' / 'app.js'
app = app_path.read_text(encoding='utf-8')

marker = 'function _aulaImmediateTurkishExplanation('
if marker not in app:
    anchor = 'function resolveItemExplanation(it, term, translation, lang = currentLang) {\n'
    if anchor not in app:
        raise RuntimeError('v13: resolveItemExplanation anchor missing')

    helper = r'''const AULA_GERMAN_ALPHABET_TR = {
  'A': "Türkçedeki 'a' sesine yakın, açık bir ünlüdür; Almancada kısa veya uzun söylenebilir.",
  'Ä': "Türkçedeki 'e' sesine yakın bir ünlüdür; kısa veya uzun söylenebilir.",
  'B': "Kelime veya hece başında 'b' gibi okunur; kelime sonunda çoğunlukla 'p' gibi duyulur.",
  'C': "Genellikle yabancı kökenli kelimelerde görülür; kelimeye göre 'k', 's' veya 'ts' benzeri okunabilir.",
  'D': "Genellikle Türkçedeki 'd' gibi okunur; kelime sonunda çoğunlukla 't' gibi duyulur.",
  'E': "Türkçedeki 'e' sesine yakın bir ünlüdür; kısa ve uzun biçimleri vardır.",
  'F': "Türkçedeki 'f' sesi gibi okunur.",
  'G': "Genellikle Türkçedeki 'g' gibi okunur; kelime sonunda sertleşerek 'k' benzeri duyulabilir.",
  'H': "Kelime başında 'h' gibi okunur; bazı konumlarda önceki ünlünün uzun okunmasına yardım eder ve kendisi duyulmaz.",
  'I': "Türkçedeki 'i' sesine yakın bir ünlüdür; kısa veya uzun söylenebilir.",
  'J': "Türkçedeki 'y' sesi gibi okunur; örneğin 'ja' yaklaşık 'ya' diye söylenir.",
  'K': "Türkçedeki 'k' sesi gibi okunur.",
  'L': "Türkçedeki ince 'l' sesine yakın okunur.",
  'M': "Türkçedeki 'm' sesi gibi okunur.",
  'N': "Türkçedeki 'n' sesi gibi okunur.",
  'O': "Türkçedeki 'o' sesine yakın bir ünlüdür; kısa veya uzun söylenebilir.",
  'Ö': "Türkçedeki 'ö' sesine çok yakın okunur.",
  'P': "Türkçedeki 'p' sesi gibi okunur.",
  'Q': "Neredeyse her zaman 'u' ile birlikte kullanılır ve 'kv' benzeri okunur.",
  'R': "Bölgeye göre farklı söylenebilir; standart Almancada çoğu zaman boğazdan gelen bir 'r' duyulur.",
  'S': "Kelime başında ünlüden önce çoğu zaman 'z' gibi, diğer birçok konumda ise 's' gibi okunur.",
  'ß': "Keskin bir 's' sesi verir; yaklaşık olarak 'ss' gibi okunur.",
  'T': "Türkçedeki 't' sesi gibi okunur.",
  'U': "Türkçedeki 'u' sesine yakın bir ünlüdür; kısa veya uzun söylenebilir.",
  'Ü': "Türkçedeki 'ü' sesine çok yakın okunur.",
  'V': "Almanca kökenli birçok kelimede 'f' gibi; bazı yabancı kelimelerde ise 'v' gibi okunur.",
  'W': "Türkçedeki 'v' sesine yakın okunur.",
  'X': "Genellikle 'ks' olarak okunur.",
  'Y': "Çoğunlukla yabancı kökenli kelimelerde görülür; kelimeye göre 'ü', 'i' veya 'y' benzeri okunabilir.",
  'Z': "'ts' birleşik sesi gibi okunur; örneğin 'Zeit' kelimesi 'ts' sesiyle başlar."
};

function _aulaImmediateTurkishExplanation(it, term, fallback, courseLang) {
  const rawTerm = safeStr(term).trim();
  const langKey = safeStr(courseLang || (currentCourse && currentCourse.language) || '').toLowerCase();
  const base = (typeof extractBaseLetter === 'function') ? extractBaseLetter(rawTerm) : rawTerm.toUpperCase();
  const isAlphabet = (typeof isLetterLike === 'function') ? isLetterLike(rawTerm) : /^[A-Za-zÄÖÜäöüßÑñ]{1,2}$/.test(rawTerm);

  // Alphabet pedagogy must be deterministic and synchronous. Never depend on
  // lazy translation state, so language toggles cannot change the explanation.
  if (isAlphabet) {
    if (/german|deutsch|almanca/.test(langKey)) {
      const deKey = rawTerm.length <= 2 ? rawTerm.toUpperCase().replace('SS', 'ß') : base;
      if (AULA_GERMAN_ALPHABET_TR[deKey]) return AULA_GERMAN_ALPHABET_TR[deKey];
      if (AULA_GERMAN_ALPHABET_TR[base]) return AULA_GERMAN_ALPHABET_TR[base];
    }

    const phon = (typeof getClientLetterPhonetics === 'function') ? (getClientLetterPhonetics(courseLang, base) || {}) : {};
    if (phon.explanation_tr && safeStr(phon.explanation_tr).trim()) return safeStr(phon.explanation_tr).trim();

    const explicitTr = it && safeStr(it.explanation_tr || it.turkish_explanation || it.desc_tr).trim();
    if (explicitTr) return explicitTr;

    const guide = safeStr(phon.phonetic_tr || '').trim();
    if (guide) return `${rawTerm || base} harfi ${guide} şeklinde okunur.`;
    return `${rawTerm || base} harfinin telaffuzu hedef dilin ses kurallarına göre yapılır.`;
  }

  const explicitTr = it && safeStr(it.explanation_tr || it.turkish_explanation || it.desc_tr).trim();
  if (explicitTr) return explicitTr;
  return (typeof _aulaTurkishNow === 'function') ? _aulaTurkishNow(safeStr(fallback)) : safeStr(fallback);
}

'''
    app = app.replace(anchor, helper + anchor, 1)

old = "${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(_aulaTurkishNow(briefExpl))) : sanitizeEnglishExplanation(safeStr(briefExpl), kStr))}"
new = "${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(_aulaImmediateTurkishExplanation(it, kStr, briefExpl, courseLang))) : sanitizeEnglishExplanation(safeStr(briefExpl), kStr))}"
if old not in app:
    raise RuntimeError('v13: final vocab explanation render anchor missing')
app = app.replace(old, new, 1)

# Prevent stale lazy-resolved Turkish values from leaking across language toggles.
# Re-rendered alphabet cards must always go through the synchronous resolver above.
stale = "if (it && typeof it === 'object' && it._resolved_tr) return it._resolved_tr;"
if stale in app:
    app = app.replace(stale, "if (it && typeof it === 'object' && it._resolved_tr && !isLetterLike(cleanTerm)) return it._resolved_tr;", 1)

app_path.write_text(app, encoding='utf-8')
for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\.js\?v=[^\"\']+', 'app.js?v=20260913_quality_v13', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')

print('Applied stable first-frame material localization v13')
