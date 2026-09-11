"""Integrity guard for bilingual finishing and stale frontend lesson data.

This module does not change lesson/material generation. It only makes the
English→Turkish finishing pass fail closed instead of storing English text in
*_tr fields, and installs a small browser compatibility guard for already-built
classrooms that may contain stale English explanation_tr values.
"""

import json
import os
import re

_FRONTEND_MARKER = "AULA_BILINGUAL_TR_GUARD_V1"

_ENGLISH_MARKERS = re.compile(
    r"\b(the|and|is|are|was|were|in|on|at|for|with|of|to|from|used|use|"
    r"noun|verb|adjective|adverb|feminine|masculine|gender|standard|"
    r"term|speech|notice|stress|syllable|ending|everyday|grammatically|"
    r"pronounced|means|refers|expression|phrase)\b",
    re.IGNORECASE,
)
_TURKISH_MARKERS = re.compile(
    r"[çğıöşüÇĞİÖŞÜ]|\b(ve|bir|bu|şu|ile|için|olarak|kullanılır|"
    r"kullanılan|isim|fiil|sıfat|zarf|dişil|eril|vurgu|hece|ek|"
    r"günlük|konuşma|anlamına|gelir|telaffuz|edilir|ifade|sözcük|"
    r"kelime|cümle|zamir|çekim|çoğul|tekil|resmi|samimi)\b",
    re.IGNORECASE,
)


def _norm(text):
    return re.sub(r"\s+", " ", str(text or "").strip()).casefold()


def _looks_obviously_english(text):
    text = str(text or "").strip()
    if not text:
        return False
    en_hits = len(_ENGLISH_MARKERS.findall(text))
    tr_hits = len(_TURKISH_MARKERS.findall(text))
    return en_hits >= 2 and tr_hits == 0


def _looks_turkish(text):
    text = str(text or "").strip()
    if not text:
        return False
    return bool(_TURKISH_MARKERS.search(text)) and not _looks_obviously_english(text)


def _is_bad_translation(source, translated, target_lang="tr"):
    source = str(source or "").strip()
    translated = str(translated or "").strip()
    if not source or not translated:
        return True
    if _norm(source) == _norm(translated):
        # Some lesson fields are already authored in Turkish and legitimately need
        # no translation. Do not force a second model rewrite of correct Turkish.
        return not (target_lang == "tr" and _looks_turkish(source))
    if target_lang == "tr" and _looks_obviously_english(translated):
        return True
    return False


def _needs_translation(source, translated):
    source = str(source or "").strip()
    translated = str(translated or "").strip()
    if not source:
        return False
    if not translated:
        return True
    if _norm(source) == _norm(translated) and not _looks_turkish(source):
        return True
    return _looks_obviously_english(translated)


def _clean_lines(value):
    if not isinstance(value, str):
        return []
    result = []
    for line in value.split("\n"):
        clean = re.sub(r"^[•\-\*\s]+", "", line).strip()
        if len(clean) > 2:
            result.append(clean)
    return result


def _collect_independently_missing_page_sources(course_id):
    """Cover page text/explanation fields independently.

    The legacy finisher used one combined condition for text_tr and explanation_tr.
    If one already existed, the other source could be omitted from the translation
    batch and later copied into a *_tr field unchanged. These extra sources are fed
    into the same translation batch without altering generated lesson content.
    """
    try:
        from database import db_connection
        with db_connection() as db:
            rows = db.execute(
                """
                SELECT t.content
                FROM topics t
                JOIN chapters ch ON t.chapter_id = ch.id
                WHERE ch.course_id = ?
                """,
                (course_id,),
            ).fetchall()
    except Exception:
        return []

    extra = []

    def add(value):
        for clean in _clean_lines(value):
            if clean not in extra:
                extra.append(clean)

    for row in rows:
        try:
            raw = row["content"]
        except Exception:
            raw = row[0]
        try:
            content = json.loads(raw or "{}") if isinstance(raw, str) else (raw or {})
        except Exception:
            continue
        if not isinstance(content, dict):
            continue

        for page in content.get("pages", []) or []:
            if not isinstance(page, dict):
                continue

            page_text = page.get("text") or page.get("intro") or ""
            if _needs_translation(page_text, page.get("text_tr")):
                add(page_text)

            page_expl = page.get("explanation") or ""
            if _needs_translation(page_expl, page.get("explanation_tr")):
                add(page_expl)

    return extra


def _drop_bad_cached_values(module, sources, target_lang):
    """Remove only exact/bad cache entries so a retry cannot reuse them."""
    try:
        cache = module._load_cache()
    except Exception:
        return

    bucket_names = ["sentence_pairs"] if target_lang == "tr" else ["sentence_pairs_tr_en"]
    # Older code can also surface generic title/vocab cache entries for these strings.
    bucket_names += ["vocab_pairs", "title_pairs"]
    changed = False
    for bucket_name in bucket_names:
        bucket = cache.get(bucket_name)
        if not isinstance(bucket, dict):
            continue
        for source in sources:
            value = bucket.get(source)
            if value is not None and _is_bad_translation(source, value, target_lang):
                bucket.pop(source, None)
                changed = True
    if changed:
        try:
            module._save_cache(cache)
        except Exception:
            pass


def _frontend_guard_js():
    # Deliberately plain ES6: this is appended to bilingual_materials.js, which is
    # already loaded before app.js. Installation waits until DOMContentLoaded so
    # resolveItemExplanation exists before it is wrapped.
    return r'''

/* AULA_BILINGUAL_TR_GUARD_V1 */
(function () {
  const CACHE_KEY = 'aula_tr_explanation_guard_v1';
  const pending = new Set();

  function norm(value) {
    return String(value || '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('tr-TR');
  }

  function looksEnglish(value) {
    const text = String(value || '').trim();
    if (!text) return false;
    const en = text.match(/\b(the|and|is|are|was|were|in|on|at|for|with|of|to|from|used|use|noun|verb|adjective|adverb|feminine|masculine|gender|standard|term|speech|notice|stress|syllable|ending|everyday|grammatically|pronounced|means|refers|expression|phrase)\b/gi) || [];
    const tr = text.match(/[çğıöşüÇĞİÖŞÜ]|\b(ve|bir|bu|şu|ile|için|olarak|kullanılır|kullanılan|isim|fiil|sıfat|zarf|dişil|eril|vurgu|hece|ek|günlük|konuşma|anlamına|gelir|telaffuz|edilir|ifade|sözcük|kelime|cümle|zamir|çekim|çoğul|tekil|resmi|samimi)\b/gi) || [];
    return en.length >= 2 && tr.length === 0;
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
      if (keys.length > 200) {
        keys.slice(0, keys.length - 200).forEach(k => delete cache[k]);
      }
      localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
    } catch (_) {}
  }

  function scheduleTranslation(item, englishText) {
    const source = String(englishText || '').trim();
    if (!source || pending.has(source)) return;
    const cache = loadCache();
    const cached = cache[source];
    if (cached && norm(cached) !== norm(source) && !looksEnglish(cached)) {
      item.explanation_tr = cached;
      return;
    }

    pending.add(source);
    fetch('/api/translate/material', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: source, target_lang: 'tr' })
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        const translated = data && typeof data.translated === 'string' ? data.translated.trim() : '';
        if (!translated || norm(translated) === norm(source) || looksEnglish(translated)) return;
        cache[source] = translated;
        saveCache(cache);
        item.explanation_tr = translated;
        item.turkish_explanation = translated;
        if (typeof window.refreshCurrentView === 'function') {
          setTimeout(() => window.refreshCurrentView(), 0);
        }
      })
      .catch(() => {})
      .finally(() => pending.delete(source));
  }

  function install() {
    const original = window.resolveItemExplanation;
    if (typeof original !== 'function' || original.__aulaBilingualTrGuard) return;

    function guardedResolveItemExplanation(item, term, translation, lang) {
      if (lang === 'tr' && item && typeof item === 'object') {
        const english = String(item.explanation_en || item.explanation || item.english_explanation || '').trim();
        const turkish = String(item.explanation_tr || item.turkish_explanation || item.desc_tr || '').trim();
        const badStoredTurkish = turkish && looksEnglish(turkish);

        if (badStoredTurkish) {
          const cache = loadCache();
          const cached = cache[english];
          if (english && cached && norm(cached) !== norm(english) && !looksEnglish(cached)) {
            const repaired = Object.assign({}, item, {
              explanation_tr: cached,
              turkish_explanation: cached
            });
            return original.call(this, repaired, term, translation, lang);
          }

          if (english) scheduleTranslation(item, english);
          const cleaned = Object.assign({}, item);
          delete cleaned.explanation_tr;
          delete cleaned.turkish_explanation;
          delete cleaned.desc_tr;
          const candidate = original.call(this, cleaned, term, translation, lang);
          if (!candidate || looksEnglish(candidate) || (english && norm(candidate) === norm(english))) return '';
          return candidate;
        }
      }

      const candidate = original.call(this, item, term, translation, lang);
      if (lang === 'tr' && candidate && looksEnglish(candidate)) {
        const english = item && typeof item === 'object'
          ? String(item.explanation_en || item.explanation || item.english_explanation || candidate).trim()
          : String(candidate).trim();
        if (item && typeof item === 'object' && english) scheduleTranslation(item, english);
        return '';
      }
      return candidate;
    }

    guardedResolveItemExplanation.__aulaBilingualTrGuard = true;
    window.resolveItemExplanation = guardedResolveItemExplanation;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    setTimeout(install, 0);
  }
})();
'''


def _append_frontend_guard(module):
    bundle_file = getattr(module, "BUNDLE_FILE", None)
    if not bundle_file or not os.path.exists(bundle_file):
        return
    try:
        with open(bundle_file, "r", encoding="utf-8") as f:
            content = f.read()
        if _FRONTEND_MARKER in content:
            return
        with open(bundle_file, "a", encoding="utf-8") as f:
            f.write(_frontend_guard_js())
    except Exception as exc:
        print(f"[BILINGUAL-GUARD] Could not append frontend guard: {exc}", flush=True)


def install(module):
    """Install translation completeness + stale-data display guards."""
    if getattr(module, "_aula_bilingual_guard_installed", False):
        return

    raw_batch = module.batch_translate_strings
    raw_rebuild = module.rebuild_bilingual_bundle
    raw_finalize = module.finalize_course_bilingual_data

    def guarded_batch_translate_strings(strings, target_lang="tr"):
        requested = []
        for value in strings or []:
            if isinstance(value, str) and value.strip() and value.strip() not in requested:
                requested.append(value.strip())

        # The active course finalizer can contribute sources independently omitted by
        # the legacy combined text/explanation condition. They enter the same batch,
        # so downstream trans_map contains them before persistence.
        if target_lang == "tr":
            for source in getattr(module, "_aula_bilingual_extra_sources", []) or []:
                if source and source not in requested:
                    requested.append(source)

        results = raw_batch(requested, target_lang=target_lang) or {}
        if target_lang != "tr" or not requested:
            return results

        # Strings already authored in Turkish are legitimate identity mappings.
        for source in requested:
            if source not in results and _looks_turkish(source):
                results[source] = source

        unresolved = [
            source for source in requested
            if _is_bad_translation(source, results.get(source), target_lang)
        ]
        if unresolved:
            print(f"[BILINGUAL-GUARD] Retrying {len(unresolved)} missing/invalid Turkish translations...", flush=True)
            _drop_bad_cached_values(module, unresolved, target_lang)
            retry_results = raw_batch(unresolved, target_lang=target_lang) or {}
            results.update(retry_results)

        unresolved = [
            source for source in requested
            if _is_bad_translation(source, results.get(source), target_lang)
        ]
        if unresolved:
            sample = "; ".join(unresolved[:3])
            suffix = "" if len(unresolved) <= 3 else f" (+{len(unresolved) - 3} more)"
            raise RuntimeError(
                f"Bilingual Turkish finishing incomplete for {len(unresolved)} string(s): {sample}{suffix}"
            )
        return results

    def guarded_rebuild_bilingual_bundle():
        result = raw_rebuild()
        _append_frontend_guard(module)
        return result

    def guarded_finalize_course_bilingual_data(course_id):
        module._aula_bilingual_extra_sources = _collect_independently_missing_page_sources(course_id)
        try:
            return raw_finalize(course_id)
        finally:
            module._aula_bilingual_extra_sources = []

    module.batch_translate_strings = guarded_batch_translate_strings
    module.rebuild_bilingual_bundle = guarded_rebuild_bilingual_bundle
    module.finalize_course_bilingual_data = guarded_finalize_course_bilingual_data
    module._aula_bilingual_guard_installed = True

    # Cover classrooms built before this guard existed. The tiny JS guard rejects
    # stale English explanation_tr values and lazily repairs them through the existing
    # translation endpoint, without regenerating lesson material.
    _append_frontend_guard(module)
