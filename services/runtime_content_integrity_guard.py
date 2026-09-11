"""Frontend-only integrity repairs for already-generated lesson content.

This module does not alter lesson/material generation or prompts. It appends a small
runtime guard to the bilingual frontend bundle so stale/legacy content is displayed
in the correct UI/course language.
"""

import os

_MARKER = "AULA_RUNTIME_CONTENT_INTEGRITY_V1"


def _runtime_js():
    return r'''

/* AULA_RUNTIME_CONTENT_INTEGRITY_V1 */
(function () {
  const CACHE_KEY = 'aula_runtime_translation_cache_v1';
  const pending = new Map();
  let refreshQueued = false;

  function currentUiLang() {
    try {
      return (typeof currentLang !== 'undefined' && currentLang === 'tr') ? 'tr' : 'en';
    } catch (_) {
      return 'en';
    }
  }

  function currentCourseLanguage() {
    try {
      return String((typeof currentCourse !== 'undefined' && currentCourse && currentCourse.language) || '').trim();
    } catch (_) {
      return '';
    }
  }

  function norm(value) {
    return String(value || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('tr-TR');
  }

  function looksEnglish(value) {
    const text = String(value || '').trim();
    if (!text) return false;
    if (/[А-Яа-яЁё\u0400-\u04FF\u0600-\u06FF\u3040-\u30FF\u3400-\u9FFF]/.test(text)) return false;
    const hits = text.match(/\b(the|a|an|is|are|was|were|how|what|which|why|when|where|word|letter|sound|vowel|consonant|stress|stressed|pronounced|pronunciation|first|final|always|used|means|correct|option|choose|read|written|syllable|reduce|reduced)\b/gi) || [];
    return hits.length >= 2;
  }

  function looksTurkish(value) {
    const text = String(value || '').trim();
    if (!text) return false;
    const hits = text.match(/[çğıöşüÇĞİÖŞÜ]|\b(bir|bu|şu|ve|ile|için|nasıl|nedir|hangisi|kelime|harf|ses|sesli|sessiz|vurgu|vurgulu|okunur|okunur|telaffuz|doğru|seçenek|ilk|son|daima|kullanılır|göre|olarak)\b/gi) || [];
    return hits.length >= 1;
  }

  function scrubEnglishCrossLanguageReferences(value) {
    let text = String(value || '');
    if (!text) return text;
    text = text.replace(/\b(?:the\s+)?Turkish\s+['“‘"]([^'”’"]+)['”’"](?:\s+sound)?/gi, "the '$1' sound");
    text = text.replace(/\bTurkish\s+([A-Za-z])\s+sound\b/gi, "the '$1' sound");
    text = text.replace(/\b(?:as|just\s+like|like)\s+in\s+Turkish\b/gi, 'clean and distinct');
    text = text.replace(/\bin\s+Turkish\b/gi, 'in standard pronunciation');
    text = text.replace(/\bTurkish\s+sound\b/gi, 'phonetic sound');
    return text;
  }

  function loadCache() {
    try {
      const parsed = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}');
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (_) {
      return {};
    }
  }

  function saveCache(cache) {
    try {
      const keys = Object.keys(cache);
      if (keys.length > 300) {
        keys.slice(0, keys.length - 300).forEach(k => delete cache[k]);
      }
      localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
    } catch (_) {}
  }

  function protectTerms(text) {
    const keep = [];
    const protectedText = String(text || '').replace(/«[^»]+»|“[^”]+”|'[^']+'|\[[^\]]+\]/g, match => {
      const token = `__AULA_KEEP_${keep.length}__`;
      keep.push(match);
      return token;
    });
    return {
      text: protectedText,
      restore(value) {
        let out = String(value || '');
        keep.forEach((segment, idx) => {
          out = out.replace(new RegExp(`__AULA_KEEP_${idx}__`, 'g'), segment);
        });
        return out;
      }
    };
  }

  function queueRefresh() {
    if (refreshQueued) return;
    refreshQueued = true;
    setTimeout(() => {
      refreshQueued = false;
      try {
        if (typeof refreshCurrentView === 'function') refreshCurrentView();
      } catch (_) {}
    }, 40);
  }

  function translateAsync(source, targetLang, onDone) {
    const raw = String(source || '').trim();
    if (!raw) return;
    const key = `${targetLang}|${raw}`;
    const cache = loadCache();
    if (cache[key]) {
      onDone(cache[key]);
      return;
    }
    if (pending.has(key)) {
      pending.get(key).then(onDone).catch(() => {});
      return;
    }

    const protectedValue = protectTerms(raw);
    const promise = fetch('/api/translate/material', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: protectedValue.text, target_lang: targetLang })
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        let translated = data && typeof data.translated === 'string' ? data.translated.trim() : '';
        translated = protectedValue.restore(translated).trim();
        if (!translated) return '';
        cache[key] = translated;
        saveCache(cache);
        return translated;
      })
      .finally(() => pending.delete(key));

    pending.set(key, promise);
    promise.then(value => { if (value) onDone(value); }).catch(() => {});
  }

  function installEnglishExplanationScrubber() {
    const original = window.sanitizeEnglishExplanation;
    if (typeof original !== 'function' || original.__aulaRuntimeIntegrity) return;
    function wrapped(text, term) {
      return scrubEnglishCrossLanguageReferences(original.call(this, text, term));
    }
    wrapped.__aulaRuntimeIntegrity = true;
    window.sanitizeEnglishExplanation = wrapped;
  }

  function installStudyPromptResolver() {
    const original = window.resolveStudyPrompt;
    if (typeof original !== 'function' || original.__aulaRuntimeIntegrity) return;

    function wrapped(page, topic) {
      if (!page || typeof page !== 'object') return original.call(this, page, topic);
      const target = currentUiLang();
      const field = target === 'tr' ? 'prompt_tr' : 'prompt_en';
      const direct = String(page[field] || '').trim();

      if (direct && ((target === 'tr' && looksTurkish(direct)) || (target === 'en' && looksEnglish(direct)))) {
        return direct;
      }

      const source = String(page.prompt || page.question || (target === 'en' ? page.prompt_tr : page.prompt_en) || '').trim();
      if (!source) return original.call(this, page, topic);

      if ((target === 'tr' && looksTurkish(source)) || (target === 'en' && looksEnglish(source))) {
        page[field] = source;
        return source;
      }

      const cache = loadCache();
      const key = `${target}|${source}`;
      if (cache[key]) {
        page[field] = cache[key];
        return cache[key];
      }

      translateAsync(source, target, translated => {
        if (!translated || norm(translated) === norm(source)) return;
        page[field] = translated;
        queueRefresh();
      });
      return target === 'tr' ? 'Çevriliyor…' : 'Translating…';
    }

    wrapped.__aulaRuntimeIntegrity = true;
    window.resolveStudyPrompt = wrapped;
  }

  const SPANISH_FALLBACK_MARKERS = [
    "¡Hola! ¿Cómo se escribe tu nombre?",
    "Se escribe con 'e', 'l', 'e', 'n', 'a': Elena.",
    "¿Todas las vocales suenan claras en español?",
    "Sí, exactamente. Cada vocal tiene un sonido único.",
    "Buenos días, ¿podemos repasar la lección?",
    "Por supuesto, practiquemos estos conceptos juntos.",
    "¿Es común usar estas frases a diario?",
    "Sí, son expresiones fundamentales en la conversación."
  ];

  function removeForeignSpanishFallback(root) {
    const lang = currentCourseLanguage().toLowerCase();
    if (!root || !lang || lang.includes('spanish') || lang.includes('español')) return;
    root.querySelectorAll('.study-dialogue-card').forEach(card => {
      const text = card.textContent || '';
      if (SPANISH_FALLBACK_MARKERS.some(marker => text.includes(marker))) {
        card.remove();
      }
    });
  }

  function localizeStudyOptionButton(button) {
    if (!button || button.disabled || button.querySelector('svg')) return;
    const raw = String(button.textContent || '').trim();
    const match = raw.match(/^(.*?)\s*\(([^()]*)\)\s*$/);
    if (!match) return;

    const prefix = match[1].trim();
    const note = match[2].trim();
    const target = currentUiLang();
    const needs = target === 'tr' ? looksEnglish(note) : looksTurkish(note);
    if (!needs) return;

    const key = `${target}|${note}`;
    const cache = loadCache();
    if (cache[key]) {
      button.textContent = `${prefix} (${cache[key]})`;
      return;
    }

    translateAsync(note, target, translated => {
      if (!button.isConnected || !translated) return;
      button.textContent = `${prefix} (${translated})`;
    });
  }

  function postProcessStudyContent() {
    ['ai-book-content-area', 's-ai-book-content-area'].forEach(id => {
      const root = document.getElementById(id);
      if (!root) return;
      removeForeignSpanishFallback(root);
      root.querySelectorAll('button[data-opt]').forEach(localizeStudyOptionButton);
    });
  }

  function installObserver() {
    const observer = new MutationObserver(() => postProcessStudyContent());
    observer.observe(document.body, { childList: true, subtree: true });
    postProcessStudyContent();
  }

  function install() {
    installEnglishExplanationScrubber();
    installStudyPromptResolver();
    installObserver();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    setTimeout(install, 0);
  }
})();
'''


def _append(module):
    bundle_file = getattr(module, "BUNDLE_FILE", None)
    if not bundle_file or not os.path.exists(bundle_file):
        return
    try:
        with open(bundle_file, "r", encoding="utf-8") as f:
            content = f.read()
        if _MARKER in content:
            return
        with open(bundle_file, "a", encoding="utf-8") as f:
            f.write(_runtime_js())
    except Exception as exc:
        print(f"[RUNTIME-INTEGRITY] Could not append frontend guard: {exc}", flush=True)


def install(bilingual_finisher_module):
    if getattr(bilingual_finisher_module, "_aula_runtime_integrity_installed", False):
        return

    raw_rebuild = bilingual_finisher_module.rebuild_bilingual_bundle

    def guarded_rebuild_bilingual_bundle():
        result = raw_rebuild()
        _append(bilingual_finisher_module)
        return result

    bilingual_finisher_module.rebuild_bilingual_bundle = guarded_rebuild_bilingual_bundle
    bilingual_finisher_module._aula_runtime_integrity_installed = True
    _append(bilingual_finisher_module)
