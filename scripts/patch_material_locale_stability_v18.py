from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
app_path = root / 'public' / 'js' / 'app.js'
app = app_path.read_text(encoding='utf-8')

helper_marker = 'function aulaFinalizeAlphabetCards(container) {'
if helper_marker not in app:
    anchor = 'function showStudyTopic(topicId, pageIdx = 0, options = {}) {\n'
    if anchor not in app:
        raise RuntimeError('v18: showStudyTopic anchor missing')

    helper = r'''function aulaFinalizeAlphabetCards(container) {
  if (!container || typeof container.querySelectorAll !== 'function') return;

  const courseLang = (currentCourse && currentCourse.language) ? currentCourse.language : '';
  const langKey = (typeof aulaAlphabetLanguageKey === 'function') ? aulaAlphabetLanguageKey(courseLang) : '';
  const germanTr = {
    'Ä': "Açık bir 'e' sesine yakındır; dudaklar yayvan, dil önde tutulur.",
    'Ö': "Türkçedeki 'ö' sesine çok yakındır; dudaklar yuvarlanır ve dil önde tutulur.",
    'Ü': "Türkçedeki 'ü' sesine çok yakındır; dudaklar yuvarlak, dil önde tutulur.",
    'ß': "Keskin bir 's' sesidir ve 'ss' gibi okunur."
  };
  const germanEn = {
    'Ä': "An open front vowel, roughly like the 'e' in 'bed'; it may be short or long.",
    'Ö': "A rounded front vowel; pronounce an 'e' sound while rounding the lips.",
    'Ü': "A rounded front vowel; pronounce an 'ee' sound while rounding the lips.",
    'ß': "Represents a sharp 's' sound and is pronounced like 'ss'."
  };

  container.querySelectorAll('.study-vocab-card').forEach(card => {
    const termEl = card.querySelector('.vocab-term-text');
    const badgeEl = card.querySelector('.vocab-meaning-pill');
    const explEl = card.querySelector('.vocab-pedagogy-text');
    if (!termEl || !badgeEl) return;

    const rawTerm = safeStr(termEl.textContent).trim();
    const token = (typeof aulaCanonicalAlphabetToken === 'function')
      ? aulaCanonicalAlphabetToken(rawTerm)
      : ((rawTerm.split(/[,\\s/|]+/u).filter(Boolean)[0] || '').toUpperCase());
    if (!token) return;

    const badgeText = safeStr(badgeEl.textContent).trim();
    const looksAlphabet = /(?:harfi|^letter\\s+)/i.test(badgeText) || /^(?:[A-Za-zÀ-ÖØ-öø-ÿĀ-žΑ-ΩА-ЯЁÑÇÄÖÜß]{1,3})(?:\\s+[A-Za-zÀ-ÖØ-öø-ÿĀ-žΑ-ΩА-ЯЁÑÇÄÖÜß]{1,3})?$/u.test(rawTerm);
    if (!looksAlphabet) return;

    const phon = (typeof aulaStrictLetterPhonetics === 'function')
      ? (aulaStrictLetterPhonetics(courseLang, token) || {})
      : ((typeof getClientLetterPhonetics === 'function') ? (getClientLetterPhonetics(courseLang, token) || {}) : {});

    badgeEl.textContent = currentLang === 'tr' ? `${token} harfi` : `Letter ${token}`;

    if (!explEl) return;

    let text = '';
    if (currentLang === 'tr') {
      if (langKey === 'german' && germanTr[token]) text = germanTr[token];
      else if (phon.explanation_tr) text = safeStr(phon.explanation_tr).trim();
      else if (phon.phonetic_tr) text = `${token} harfi ${safeStr(phon.phonetic_tr).trim()} olarak telaffuz edilir.`;
      else text = `${token} harfi hedef dilin standart ses kurallarına göre telaffuz edilir.`;
    } else {
      if (langKey === 'german' && germanEn[token]) text = germanEn[token];
      else if (phon.explanation_en) text = safeStr(phon.explanation_en).trim();
      else if (phon.phonetic_en) text = `${token} is pronounced ${safeStr(phon.phonetic_en).trim()}.`;
      else text = `${token} follows the target language's standard pronunciation rules.`;
    }

    explEl.textContent = text;
  });
}

'''
    app = app.replace(anchor, helper + anchor, 1)

call_marker = '  aulaFinalizeAlphabetCards(container);\n\n  // Reset scroll to top of the study card on page navigation, unless preserving scroll\n'
if call_marker not in app:
    anchor = '  // Reset scroll to top of the study card on page navigation, unless preserving scroll\n'
    if anchor not in app:
        raise RuntimeError('v18: post-render anchor missing')
    app = app.replace(anchor, '  aulaFinalizeAlphabetCards(container);\n\n' + anchor, 1)

app_path.write_text(app, encoding='utf-8')

for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\\.js\\?v=[^\\"\\\']+', 'app.js?v=20260913_quality_v18', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')

print('Applied final alphabet card locale stabilizer v18')
