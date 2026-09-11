"""Frontend-only guard for deterministic lesson toggles and active-topic state."""

import os

_MARKER = "AULA_RUNTIME_CONTENT_INTEGRITY_V4"


def _runtime_js():
    return r'''

/* AULA_RUNTIME_CONTENT_INTEGRITY_V4 */
(function () {
  function uiLang() {
    try { return (typeof currentLang !== 'undefined' && currentLang === 'tr') ? 'tr' : 'en'; }
    catch (_) { return 'en'; }
  }

  function stableField(item, lang) {
    if (!item || typeof item !== 'object') return '';
    if (lang === 'tr') {
      return String(item.explanation_tr || item.turkish_explanation || '').trim();
    }
    return String(item.explanation_en || item.english_explanation || item.explanation || '').trim();
  }

  function installExplanationResolver() {
    const original = window.resolveItemExplanation;
    if (typeof original !== 'function' || original.__aulaStableV4) return false;

    function wrapped(item, term, translation, lang) {
      const target = lang || uiLang();
      let isLetter = false;
      try { isLetter = typeof isLetterLike === 'function' && isLetterLike(String(term || '').trim()); } catch (_) {}
      if (isLetter && item && typeof item === 'object') {
        const direct = stableField(item, target);
        if (direct) return direct;
      }
      return original.call(this, item, term, translation, target);
    }
    wrapped.__aulaStableV4 = true;
    window.resolveItemExplanation = wrapped;
    return true;
  }

  function installPromptResolver() {
    const original = window.resolveStudyPrompt;
    if (typeof original !== 'function' || original.__aulaStableV4) return false;

    function wrapped(page, topic) {
      if (page && typeof page === 'object') {
        const target = uiLang();
        const direct = String(target === 'tr' ? page.prompt_tr : page.prompt_en || '').trim();
        if (direct) return direct;
      }
      return original.call(this, page, topic);
    }
    wrapped.__aulaStableV4 = true;
    window.resolveStudyPrompt = wrapped;
    return true;
  }

  function findTopic(topicId) {
    try {
      for (const chapter of (typeof curriculum !== 'undefined' ? curriculum : [])) {
        for (const topic of (chapter.topics || [])) {
          if (String(topic.id) === String(topicId)) return topic;
        }
      }
    } catch (_) {}
    return null;
  }

  function prepareMcq(topic) {
    if (!topic || !topic.content) return;
    let content = topic.content;
    if (typeof content === 'string') {
      try { content = JSON.parse(content); topic.content = content; } catch (_) { return; }
    }
    const target = uiLang();
    for (const page of (content.pages || [])) {
      if (!page || !(page.type === 'mcq' || page.prompt || page.question)) continue;
      if (!page.__aulaOriginalMcq) {
        page.__aulaOriginalMcq = {
          options: Array.isArray(page.options) ? page.options.slice() : [],
          distractors: Array.isArray(page.distractors) ? page.distractors.slice() : [],
          answer: page.answer
        };
      }
      const options = target === 'tr' ? page.options_tr : page.options_en;
      const distractors = target === 'tr' ? page.distractors_tr : page.distractors_en;
      const answer = target === 'tr' ? page.answer_tr : page.answer_en;
      page.options = Array.isArray(options) && options.length ? options.slice() : page.__aulaOriginalMcq.options.slice();
      page.distractors = Array.isArray(distractors) && distractors.length ? distractors.slice() : page.__aulaOriginalMcq.distractors.slice();
      page.answer = answer || page.__aulaOriginalMcq.answer;
    }
  }

  function syncActiveTopic() {
    let topicId = null;
    try { topicId = localStorage.getItem('aula_last_topic'); } catch (_) {}
    const buttons = Array.from(document.querySelectorAll('.study-topic-btn[data-topic-id]'));
    if (!buttons.length) return;

    // Prefer the app's actual active class if it already exists. This prevents a stale
    // localStorage/default-first-topic value from overwriting the real selection.
    const activeButton = buttons.find(button => button.classList.contains('active'));
    if (activeButton) topicId = activeButton.getAttribute('data-topic-id');
    if (!topicId) return;

    buttons.forEach(button => {
      const active = String(button.getAttribute('data-topic-id')) === String(topicId);
      button.classList.toggle('active', active);
      button.style.background = active ? 'var(--accent-glow)' : '';
      button.style.borderLeft = active ? '3px solid var(--accent)' : '';
    });
  }

  function installStudyWrapper() {
    const original = window.showStudyTopic;
    if (typeof original !== 'function' || original.__aulaStableV4) return false;
    function wrapped(topicId, pageIdx, options) {
      prepareMcq(findTopic(topicId));
      const result = original.call(this, topicId, pageIdx, options);
      setTimeout(syncActiveTopic, 0);
      return result;
    }
    wrapped.__aulaStableV4 = true;
    window.showStudyTopic = wrapped;
    return true;
  }

  function installToggleWrapper() {
    const original = window.toggleLanguage;
    if (typeof original !== 'function' || original.__aulaStableV4) return false;
    function wrapped() {
      const result = original.apply(this, arguments);
      let topicId = null;
      try { topicId = localStorage.getItem('aula_last_topic'); } catch (_) {}
      if (topicId) prepareMcq(findTopic(topicId));
      [0, 30, 120].forEach(delay => setTimeout(syncActiveTopic, delay));
      return result;
    }
    wrapped.__aulaStableV4 = true;
    window.toggleLanguage = wrapped;
    return true;
  }

  const SPANISH_FALLBACK_MARKERS = [
    "¡Hola! ¿Cómo se escribe tu nombre?",
    "Se escribe con 'e', 'l', 'e', 'n', 'a': Elena.",
    "¿Todas las vocales suenan claras en español?",
    "Sí, exactamente. Cada vocal tiene un sonido único."
  ];

  function removeForeignSpanishFallback() {
    let lang = '';
    try { lang = String((currentCourse && currentCourse.language) || '').toLowerCase(); } catch (_) {}
    if (!lang || lang.includes('spanish') || lang.includes('español')) return;
    document.querySelectorAll('.study-dialogue-card').forEach(card => {
      const text = card.textContent || '';
      if (SPANISH_FALLBACK_MARKERS.some(marker => text.includes(marker))) card.remove();
    });
  }

  function installAll() {
    const a = installExplanationResolver();
    const b = installPromptResolver();
    const c = installStudyWrapper();
    const d = installToggleWrapper();
    if (a || b || c || d) syncActiveTopic();
    return [
      window.resolveItemExplanation,
      window.resolveStudyPrompt,
      window.showStudyTopic,
      window.toggleLanguage
    ].every(fn => typeof fn === 'function');
  }

  // app.js may still be defining functions when this bundle loads. Install as soon as
  // they exist instead of waiting only for DOMContentLoaded, which previously allowed
  // the first lesson paint to use a different resolver than later toggles.
  let attempts = 0;
  const timer = setInterval(() => {
    attempts += 1;
    const done = installAll();
    if (done || attempts > 500) clearInterval(timer);
  }, 10);

  const observer = new MutationObserver(() => {
    removeForeignSpanishFallback();
    syncActiveTopic();
  });
  if (document.body) observer.observe(document.body, {childList: true, subtree: true});
  else document.addEventListener('DOMContentLoaded', () => observer.observe(document.body, {childList: true, subtree: true}), {once: true});
})();
'''


def _append(module):
    bundle_file = getattr(module, "BUNDLE_FILE", None)
    if not bundle_file or not os.path.exists(bundle_file):
        return
    try:
        with open(bundle_file, "r", encoding="utf-8") as handle:
            content = handle.read()
        if _MARKER in content:
            return
        with open(bundle_file, "a", encoding="utf-8") as handle:
            handle.write(_runtime_js())
    except Exception as exc:
        print(f"[RUNTIME-V4] Could not append guard: {exc}", flush=True)


def install(bilingual_finisher_module):
    if getattr(bilingual_finisher_module, "_aula_runtime_integrity_v4_installed", False):
        return
    raw_rebuild = bilingual_finisher_module.rebuild_bilingual_bundle

    def wrapped_rebuild():
        result = raw_rebuild()
        _append(bilingual_finisher_module)
        return result

    bilingual_finisher_module.rebuild_bilingual_bundle = wrapped_rebuild
    bilingual_finisher_module._aula_runtime_integrity_v4_installed = True
    _append(bilingual_finisher_module)
