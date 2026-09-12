from pathlib import Path

server_path = Path("server.py")
src = server_path.read_text(encoding="utf-8")

patches = []

patches.append((
    "pdf layout css",
    '''.mcq-expl { font-size: 8pt; color: #64748b; margin-top: 5px; border-top: 0.5px solid #bbf7d0; padding-top: 4px; }
"""
''',
    '''.mcq-expl { font-size: 8pt; color: #64748b; margin-top: 5px; border-top: 0.5px solid #bbf7d0; padding-top: 4px; }

/* Print/PDF stability: keep logical blocks together and prevent PyMuPDF Story
   from producing split rows, orphan headings, overlapping dialogue, or clipped text. */
* { box-sizing: border-box; }
body { font-size: 9pt; line-height: 1.4; }
.cover { page-break-after: avoid; }
.unit-card { margin-top: 20px; margin-bottom: 10px; page-break-after: avoid; }
.unit-title { line-height: 1.25; }
.topic-card { margin-top: 12px; margin-bottom: 16px; }
.topic-title { line-height: 1.3; page-break-after: avoid; }
.badge { display: inline-block; vertical-align: middle; white-space: nowrap; margin-left: 6px; padding: 1px 5px; }
.sec-h { page-break-after: avoid; margin-top: 10px; }
.text-block, .cmp-box, .mcq-box { page-break-inside: avoid; break-inside: avoid; }
.diag-line { display: block; page-break-inside: avoid; break-inside: avoid; margin-bottom: 5px; }
.spkr { display: inline; min-width: 0; margin-right: 4px; }
.said { display: inline; }
.said-tr { display: inline; margin-left: 3px; }

table.vt { width: 100%; table-layout: fixed; border-collapse: collapse; margin: 6px 0 10px 0; font-size: 7.8pt; }
table.vt tr { page-break-inside: avoid; break-inside: avoid; }
table.vt th, table.vt td { overflow-wrap: anywhere; word-wrap: break-word; line-height: 1.3; }
table.vt th { padding: 4px 6px; }
table.vt td { padding: 4px 6px; }
.term, .phon, .trans, .ex, .ex-tr { overflow-wrap: anywhere; word-wrap: break-word; }
.mcq-q, .mcq-opt, .mcq-expl { line-height: 1.35; }
.mcq-opts { margin-left: 10px; }
"""
'''))

patches.append((
    "title map",
    '''            E = _html.escape

            def tx(page_dict, en_key, tr_key):
''',
    '''            E = _html.escape

            # Turkish PDF exports should localize curriculum headings as well as page content.
            pdf_title_map = {}
            if is_tr:
                try:
                    from services.curriculum_translator import translate_titles_batch
                    title_candidates = [ch[2] for ch in chapters if ch[2]]
                    with db_connection() as title_db:
                        topic_title_rows = title_db.execute(
                            """SELECT t.title FROM topics t
                               JOIN chapters ch ON t.chapter_id = ch.id
                               WHERE ch.course_id = ? AND t.title IS NOT NULL AND t.title != ''""",
                            (course_id,)
                        ).fetchall()
                    title_candidates.extend(row[0] for row in topic_title_rows if row[0])
                    pdf_title_map = translate_titles_batch(title_candidates, target_lang="tr")
                except Exception as title_err:
                    print(f"[PDF EXPORT] Title translation fallback: {title_err}")

            def tx(page_dict, en_key, tr_key):
'''))

patches.append((
    "chapter title",
    '''                for ch in chapters:
                    ch_id, ch_num, ch_title = ch
                    unit_word = "Ünite" if is_tr else "Unit"
                    parts.append(
                        f'<div class="unit-card"><div class="unit-title">{unit_word} {ch_num}: {E(ch_title or "")}</div></div>'
                    )
''',
    '''                for ch in chapters:
                    ch_id, ch_num, ch_title = ch
                    unit_word = "Ünite" if is_tr else "Unit"
                    display_ch_title = pdf_title_map.get(ch_title, ch_title) if is_tr else ch_title
                    parts.append(
                        f'<div class="unit-card"><div class="unit-title">{unit_word} {ch_num}: {E(display_ch_title or "")}</div></div>'
                    )
'''))

patches.append((
    "topic title",
    '''                        parts.append(
                            f'<div class="topic-card">'
                            f'<div class="topic-title">{E(top_title or "Topic")}'
                            f'<span class="badge">{E(type_label(top_type or "lesson"))}</span></div>'
                        )
''',
    '''                        display_top_title = pdf_title_map.get(top_title, top_title) if is_tr else top_title
                        topic_fallback = "Konu" if is_tr else "Topic"
                        parts.append(
                            f'<div class="topic-card">'
                            f'<div class="topic-title">{E(display_top_title or topic_fallback)}'
                            f'<span class="badge">{E(type_label(top_type or "lesson"))}</span></div>'
                        )
'''))

patches.append((
    "pdf answer-key init",
    '''            parts = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"]
''',
    '''            parts = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"]
            answer_key_entries = []
            question_counter = 0
'''))

patches.append((
    "pdf vocabulary examples",
    '''                                    h_ex    = "Örnek Cümle" if is_tr else "Example"
                                    h_extr  = "Çevirisi" if is_tr else "Meaning"
''',
    '''                                    h_ex    = "Hedef Dilde Örnek" if is_tr else "Target-Language Example"
                                    h_extr  = "Türkçe Çeviri" if is_tr else "English Translation"
'''))

patches.append((
    "pdf target-language example selection",
    '''                                        ex     = item.get("example") or item.get("example_en") or ""
                                        ex_tr  = item.get("example_tr") or item.get("example_en") or ""
                                        expl   = tx(item, "explanation", "explanation_tr") or ""
                                        if is_tr:
                                            ex_show = ex_tr
                                            transl_show = item.get("translation_tr") or item.get("translation") or ""
                                            ex_meaning = item.get("example_en") or ex
                                        else:
                                            ex_show = ex
                                            transl_show = item.get("translation") or item.get("translation_en") or ""
                                            ex_meaning = item.get("example_tr") or ""
''',
    '''                                        # `example` is the target-language sentence; *_tr / *_en are its translations.
                                        ex_target = item.get("example") or item.get("example_target") or item.get("target_example") or ""
                                        expl   = tx(item, "explanation", "explanation_tr") or ""
                                        ex_show = ex_target
                                        if is_tr:
                                            transl_show = item.get("translation_tr") or item.get("translation") or ""
                                            ex_meaning = item.get("example_tr") or ""
                                        else:
                                            transl_show = item.get("translation") or item.get("translation_en") or ""
                                            ex_meaning = item.get("example_en") or ""
'''))

patches.append((
    "pdf unanswered mcq",
    '''                                parts.append(f'<div class="mcq-box"><div class="mcq-q">{E(str(prompt))}</div>')
                                if options:
                                    parts.append('<div class="mcq-opts">')
                                    for opt in options:
                                        is_correct = (str(opt).strip() == str(answer).strip())
                                        cls = 'mcq-opt correct' if is_correct else 'mcq-opt'
                                        mark = " &#10003;" if is_correct else ""
                                        parts.append(f'<div class="{cls}">{E(str(opt))}{mark}</div>')
                                    parts.append('</div>')
                                if expl:
                                    parts.append(f'<div class="mcq-expl">{E(str(expl))}</div>')
                                parts.append('</div>')
''',
    '''                                question_counter += 1
                                parts.append(f'<div class="mcq-box"><div class="mcq-q">{question_counter}. {E(str(prompt))}</div>')
                                if options:
                                    parts.append('<div class="mcq-opts">')
                                    for opt_idx, opt in enumerate(options):
                                        letter = chr(65 + opt_idx)
                                        parts.append(f'<div class="mcq-opt">{letter}) {E(str(opt))}</div>')
                                    parts.append('</div>')
                                parts.append('</div>')
                                answer_letter = ""
                                try:
                                    answer_letter = chr(65 + [str(o).strip() for o in options].index(str(answer).strip()))
                                except Exception:
                                    pass
                                answer_key_entries.append({
                                    "number": question_counter,
                                    "letter": answer_letter,
                                    "answer": str(answer or ""),
                                    "explanation": str(expl or "")
                                })
'''))

patches.append((
    "pdf answer-key footer",
    '''            parts.append('</body></html>')
            full_html = "".join(parts)
''',
    '''            if answer_key_entries:
                key_title = "Cevap Anahtarı" if is_tr else "Answer Key"
                parts.append('<div style="page-break-before:always;"></div>')
                parts.append(f'<div class="unit-card"><div class="unit-title">{key_title}</div></div>')
                for entry in answer_key_entries:
                    key_text = f"{entry['number']}. "
                    if entry.get("letter"):
                        key_text += f"{entry['letter']}) "
                    key_text += entry.get("answer", "")
                    parts.append(f'<div class="mcq-box"><div class="mcq-q">{E(key_text)}</div>')
                    if entry.get("explanation"):
                        parts.append(f'<div class="mcq-expl">{E(entry["explanation"])}</div>')
                    parts.append('</div>')

            parts.append('</body></html>')
            full_html = "".join(parts)
'''))

for label, old, new in patches:
    count = src.count(old)
    if count != 1:
        raise RuntimeError(f"PDF/material patch anchor '{label}' matched {count} times")
    src = src.replace(old, new, 1)

server_path.write_text(src, encoding="utf-8")

# Turkish UI: if a vocabulary pedagogy explanation is English because the stored
# material lacks explanation_tr, translate it lazily once and cache it client-side.
app_path = Path("public/js/app.js")
app_src = app_path.read_text(encoding="utf-8")
marker = "AULA_TR_PEDAGOGY_LAZY_LOCALIZER"
if marker not in app_src:
    app_src += r'''

// AULA_TR_PEDAGOGY_LAZY_LOCALIZER
(() => {
  const cache = new Map();
  const pending = new Map();
  const englishSignal = /\b(the|and|is|are|indicates|represents|preceding|consonant|vowel|always|standard|pronounced|softens|hard|soft|sound|word|before|after|used|means)\b/i;

  async function localizeNode(el) {
    if (!el || el.dataset.aulaTrLocalized === '1') return;
    if (typeof currentLang !== 'undefined' && currentLang !== 'tr') return;
    const text = (el.textContent || '').trim();
    if (!text || text.length < 8 || !englishSignal.test(text)) return;
    el.dataset.aulaTrLocalized = '1';

    try {
      if (cache.has(text)) {
        el.textContent = cache.get(text);
        return;
      }
      let promise = pending.get(text);
      if (!promise) {
        promise = fetch('/api/translate/material', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({text, target_lang: 'tr'})
        }).then(r => r.ok ? r.json() : null)
          .then(data => (data && data.translated) ? String(data.translated).trim() : '')
          .finally(() => pending.delete(text));
        pending.set(text, promise);
      }
      const translated = await promise;
      if (translated && translated !== text) {
        cache.set(text, translated);
        el.textContent = translated;
      }
    } catch (_) {
      el.dataset.aulaTrLocalized = '0';
    }
  }

  function scan(root = document) {
    if (typeof currentLang !== 'undefined' && currentLang !== 'tr') return;
    if (root.matches && root.matches('.vocab-pedagogy-text')) localizeNode(root);
    if (root.querySelectorAll) root.querySelectorAll('.vocab-pedagogy-text').forEach(localizeNode);
  }

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(node => {
        if (node && node.nodeType === 1) scan(node);
      });
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      scan(document);
      observer.observe(document.body, {childList: true, subtree: true});
    }, {once: true});
  } else {
    scan(document);
    observer.observe(document.body, {childList: true, subtree: true});
  }
})();
'''
    app_path.write_text(app_src, encoding="utf-8")

print("Applied Turkish material/PDF localization, answer-key, and stable PDF layout patch")
