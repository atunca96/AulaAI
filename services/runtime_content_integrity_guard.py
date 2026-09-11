"""Frontend integrity/state guard for bilingual lesson rendering."""

import os

_MARKER = "AULA_RUNTIME_CONTENT_INTEGRITY_V2"


def _runtime_js():
    return r'''

/* AULA_RUNTIME_CONTENT_INTEGRITY_V2 */
(function () {
  const CACHE_KEY = 'aula_runtime_translation_cache_v2';
  const pending = new Map();
  let activeStudyTopicId = null;

  function uiLang() {
    try { return (typeof currentLang !== 'undefined' && currentLang === 'tr') ? 'tr' : 'en'; }
    catch (_) { return 'en'; }
  }

  function courseLang() {
    try { return String((typeof currentCourse !== 'undefined' && currentCourse && currentCourse.language) || '').trim(); }
    catch (_) { return ''; }
  }

  function norm(v) { return String(v || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('tr-TR'); }
  function looksEnglish(v) {
    const s = String(v || '').trim();
    if (!s || /[А-Яа-яЁё\u0400-\u04FF\u0600-\u06FF\u3040-\u30FF\u3400-\u9FFF]/.test(s)) return false;
    return (s.match(/\b(the|a|an|is|are|and|or|in|for|with|of|to|word|letter|sound|vowel|consonant|stress|pronounced|first|final|always|used|means|home|house|build|homeless|correct|option)\b/gi) || []).length >= 1;
  }
  function looksTurkish(v) {
    const s = String(v || '').trim();
    return !!s && /[çğıöşüÇĞİÖŞÜ]|\b(bir|bu|şu|ve|ile|için|nasıl|nedir|hangisi|kelime|harf|ses|vurgu|okunur|telaffuz|doğru|seçenek|evde|evler)\b/i.test(s);
  }

  function scrubEnglish(v) {
    let s = String(v || '');
    if (!s) return s;
    s = s.replace(/\b(?:the\s+)?Turkish\s+['“‘"]([^'”’"]+)['”’"](?:\s+sound)?/gi, "the '$1' sound");
    s = s.replace(/\bTurkish\s+([A-Za-z])\s+sound\b/gi, "the '$1' sound");
    s = s.replace(/\b(?:as|just\s+like|like)\s+in\s+Turkish\b/gi, 'in standard pronunciation');
    s = s.replace(/\bin\s+Turkish\b/gi, 'in standard pronunciation');
    return s;
  }

  function loadCache() {
    try { const x = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}'); return x && typeof x === 'object' ? x : {}; }
    catch (_) { return {}; }
  }
  function saveCache(c) { try { localStorage.setItem(CACHE_KEY, JSON.stringify(c)); } catch (_) {} }

  function protectTerms(text) {
    const keep = [];
    const safe = String(text || '').replace(/«[^»]+»|“[^”]+”|'[^']+'|\[[^\]]+\]/g, m => {
      const t = `__AULA_KEEP_${keep.length}__`; keep.push(m); return t;
    });
    return { text: safe, restore(v) { let s = String(v || ''); keep.forEach((x,i) => { s = s.replaceAll(`__AULA_KEEP_${i}__`, x); }); return s; } };
  }

  function translateAsync(source, target, done) {
    const raw = String(source || '').trim();
    if (!raw) return;
    const key = `${target}|${raw}`;
    const cache = loadCache();
    if (cache[key]) { done(cache[key]); return; }
    if (pending.has(key)) { pending.get(key).then(done).catch(() => {}); return; }
    const protectedValue = protectTerms(raw);
    const promise = fetch('/api/translate/material', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({text: protectedValue.text, target_lang: target})
    }).then(r => r.ok ? r.json() : null).then(data => {
      const value = protectedValue.restore(data && data.translated || '').trim();
      if (value) { cache[key] = value; saveCache(cache); }
      return value;
    }).finally(() => pending.delete(key));
    pending.set(key, promise); promise.then(v => { if (v) done(v); }).catch(() => {});
  }

  // Alphabet cards must use one canonical phonetics bank in both UI languages.
  function installExplanationResolver() {
    const original = window.resolveItemExplanation;
    if (typeof original !== 'function' || original.__aulaCanonicalV2) return;
    function wrapped(item, term, translation, lang) {
      const target = lang || uiLang();
      try {
        const clean = String(term || '').trim();
        if (typeof isLetterLike === 'function' && isLetterLike(clean) &&
            typeof extractBaseLetter === 'function' && typeof getClientLetterPhonetics === 'function') {
          const phon = getClientLetterPhonetics(courseLang() || 'Spanish', extractBaseLetter(clean)) || {};
          const canonical = target === 'tr' ? phon.explanation_tr : phon.explanation_en;
          if (canonical) return target === 'en' ? scrubEnglish(canonical) : canonical;
        }
      } catch (_) {}
      const value = original.call(this, item, term, translation, target);
      return target === 'en' ? scrubEnglish(value) : value;
    }
    wrapped.__aulaCanonicalV2 = true;
    window.resolveItemExplanation = wrapped;
  }

  function installEnglishScrubber() {
    const original = window.sanitizeEnglishExplanation;
    if (typeof original !== 'function' || original.__aulaCanonicalV2) return;
    function wrapped(text, term) { return scrubEnglish(original.call(this, text, term)); }
    wrapped.__aulaCanonicalV2 = true;
    window.sanitizeEnglishExplanation = wrapped;
  }

  // Prefer persisted prompt_en/prompt_tr. Lazy translation remains legacy-only fallback.
  function installPromptResolver() {
    const original = window.resolveStudyPrompt;
    if (typeof original !== 'function' || original.__aulaCanonicalV2) return;
    function wrapped(page, topic) {
      if (!page || typeof page !== 'object') return original.call(this, page, topic);
      const target = uiLang();
      const direct = String(target === 'tr' ? page.prompt_tr : page.prompt_en || '').trim();
      if (direct) return direct;
      const source = String(page.prompt || page.question || '').trim();
      if (!source) return original.call(this, page, topic);
      if ((target === 'tr' && looksTurkish(source)) || (target === 'en' && looksEnglish(source))) return source;
      const cache = loadCache(), key = `${target}|${source}`;
      if (cache[key]) return cache[key];
      translateAsync(source, target, translated => { if (translated) { page[target === 'tr' ? 'prompt_tr' : 'prompt_en'] = translated; } });
      // Never flash the wrong-language source. A neutral placeholder is legacy fallback only.
      return target === 'tr' ? 'Soru hazırlanıyor…' : 'Preparing question…';
    }
    wrapped.__aulaCanonicalV2 = true;
    window.resolveStudyPrompt = wrapped;
  }

  function findTopic(topicId) {
    try {
      for (const ch of (typeof curriculum !== 'undefined' ? curriculum : [])) {
        for (const tp of (ch.topics || [])) if (String(tp.id) === String(topicId)) return tp;
      }
    } catch (_) {}
    return null;
  }

  function prepareLocalizedMcq(topic) {
    if (!topic || !topic.content) return;
    let content = topic.content;
    if (typeof content === 'string') { try { content = JSON.parse(content); } catch (_) { return; } }
    const target = uiLang();
    for (const p of (content.pages || [])) {
      if (!p || !(p.type === 'mcq' || p.prompt)) continue;
      if (!p.__aulaBaseMcq) {
        p.__aulaBaseMcq = {
          options: Array.isArray(p.options) ? p.options.slice() : [],
          distractors: Array.isArray(p.distractors) ? p.distractors.slice() : [],
          answer: p.answer
        };
      }
      const opts = target === 'tr' ? p.options_tr : p.options_en;
      const ds = target === 'tr' ? p.distractors_tr : p.distractors_en;
      const ans = target === 'tr' ? p.answer_tr : p.answer_en;
      p.options = Array.isArray(opts) && opts.length ? opts.slice() : p.__aulaBaseMcq.options.slice();
      p.distractors = Array.isArray(ds) && ds.length ? ds.slice() : p.__aulaBaseMcq.distractors.slice();
      p.answer = ans || p.__aulaBaseMcq.answer;
    }
  }

  function applyActiveTopicHighlight() {
    if (!activeStudyTopicId) return;
    const id = String(activeStudyTopicId).replace(/['"\\]/g, '');
    const selectors = [
      `[onclick*="showStudyTopic('${id}'"]`, `[onclick*="showStudyTopic(\"${id}\""]`,
      `[onclick*="startStudyFirst('${id}'"]`, `[onclick*="startStudyFirst(\"${id}\""]`
    ];
    document.querySelectorAll('[data-aula-active-study="1"]').forEach(el => {
      el.removeAttribute('data-aula-active-study');
      el.style.removeProperty('background'); el.style.removeProperty('border-left'); el.style.removeProperty('color');
    });
    for (const sel of selectors) {
      document.querySelectorAll(sel).forEach(el => {
        el.setAttribute('data-aula-active-study','1');
        el.style.background = 'var(--accent-glow)';
        el.style.borderLeft = '3px solid var(--accent)';
        el.style.color = 'var(--text-primary)';
      });
    }
  }

  function installStudyWrapper() {
    const original = window.showStudyTopic;
    if (typeof original !== 'function' || original.__aulaCanonicalV2) return;
    function wrapped(topicId, pageIdx, options) {
      activeStudyTopicId = topicId;
      prepareLocalizedMcq(findTopic(topicId));
      const result = original.call(this, topicId, pageIdx, options);
      setTimeout(applyActiveTopicHighlight, 0);
      return result;
    }
    wrapped.__aulaCanonicalV2 = true;
    window.showStudyTopic = wrapped;
  }

  function installToggleWrapper() {
    const original = window.toggleLanguage;
    if (typeof original !== 'function' || original.__aulaCanonicalV2) return;
    function wrapped() {
      const result = original.apply(this, arguments);
      if (activeStudyTopicId) {
        prepareLocalizedMcq(findTopic(activeStudyTopicId));
        setTimeout(applyActiveTopicHighlight, 20);
        setTimeout(applyActiveTopicHighlight, 150);
      }
      return result;
    }
    wrapped.__aulaCanonicalV2 = true;
    window.toggleLanguage = wrapped;
  }

  const SPANISH_FALLBACK_MARKERS = [
    "¡Hola! ¿Cómo se escribe tu nombre?", "Se escribe con 'e', 'l', 'e', 'n', 'a': Elena.",
    "¿Todas las vocales suenan claras en español?", "Sí, exactamente. Cada vocal tiene un sonido único."
  ];
  function removeForeignSpanishFallback(root) {
    const lang = courseLang().toLowerCase();
    if (!root || !lang || lang.includes('spanish') || lang.includes('español')) return;
    root.querySelectorAll('.study-dialogue-card').forEach(card => {
      if (SPANISH_FALLBACK_MARKERS.some(m => (card.textContent || '').includes(m))) card.remove();
    });
  }

  function postProcess() {
    ['ai-book-content-area','s-ai-book-content-area'].forEach(id => removeForeignSpanishFallback(document.getElementById(id)));
    applyActiveTopicHighlight();
  }

  function install() {
    installExplanationResolver();
    installEnglishScrubber();
    installPromptResolver();
    installStudyWrapper();
    installToggleWrapper();
    const observer = new MutationObserver(postProcess);
    observer.observe(document.body, {childList:true, subtree:true});
    postProcess();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true});
  else setTimeout(install, 0);
})();
'''


def _append(module):
    bundle_file = getattr(module, "BUNDLE_FILE", None)
    if not bundle_file or not os.path.exists(bundle_file):
        return
    try:
        with open(bundle_file, "r", encoding="utf-8") as f:
            content = f.read()
        # Do not append duplicate V2 guard. V1 may remain in static history; V2 owns the final wrappers.
        if _MARKER in content:
            return
        with open(bundle_file, "a", encoding="utf-8") as f:
            f.write(_runtime_js())
    except Exception as exc:
        print(f"[RUNTIME-INTEGRITY] Could not append frontend guard: {exc}", flush=True)


def install(bilingual_finisher_module):
    if getattr(bilingual_finisher_module, "_aula_runtime_integrity_v2_installed", False):
        return
    raw_rebuild = bilingual_finisher_module.rebuild_bilingual_bundle

    def guarded_rebuild_bilingual_bundle():
        result = raw_rebuild()
        _append(bilingual_finisher_module)
        return result

    bilingual_finisher_module.rebuild_bilingual_bundle = guarded_rebuild_bilingual_bundle
    bilingual_finisher_module._aula_runtime_integrity_v2_installed = True
    _append(bilingual_finisher_module)
