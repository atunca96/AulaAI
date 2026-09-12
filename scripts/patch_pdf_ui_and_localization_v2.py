from pathlib import Path

# This patch runs AFTER patch_pdf_title_localization.py inside the Railway image.
# It only tightens PDF presentation/localization and PDF export UI behavior.

server_path = Path("server.py")
src = server_path.read_text(encoding="utf-8")

# 1) Make the PDF visually print-like instead of relying on large colored fills that
# PyMuPDF Story can fragment into full-width bars at page boundaries.
css_anchor = '''.mcq-opts { margin-left: 10px; }
"""
'''
css_override = '''.mcq-opts { margin-left: 10px; }

/* Final print-safe overrides. Keep the document minimal so Story pagination cannot
   turn colored inline/background elements into full-width artifacts. */
.cover { border-bottom: 2px solid #6366f1; }
.unit-card {
  background: transparent;
  border-left: 3px solid #6366f1;
  border-bottom: 0.7px solid #c7d2fe;
  padding: 5px 8px;
  margin-top: 18px;
  margin-bottom: 9px;
}
.unit-title { color: #312e81; font-size: 12pt; }
.topic-title {
  background: transparent;
  color: #0f172a;
  border-bottom: 0.7px solid #c7d2fe;
  padding: 0 0 4px 0;
  margin-bottom: 8px;
}
.badge {
  background: transparent;
  color: #6366f1;
  border: 0.5px solid #c7d2fe;
  padding: 1px 4px;
  font-size: 6.8pt;
  border-radius: 2px;
}
.sec-h {
  background: transparent;
  color: #4338ca;
  border-bottom: 0.5px solid #e2e8f0;
  padding: 0 0 2px 0;
}
.text-block {
  background: transparent;
  border-left: 2px solid #c7d2fe;
  padding: 5px 8px;
  margin-bottom: 8px;
}
table.vt { margin-top: 4px; margin-bottom: 9px; }
table.vt th {
  background: transparent;
  color: #312e81;
  border-top: 0.8px solid #818cf8;
  border-bottom: 0.8px solid #818cf8;
  border-left: 0.4px solid #e2e8f0;
  border-right: 0.4px solid #e2e8f0;
  font-size: 7.4pt;
}
table.vt td {
  background: transparent;
  border: 0.4px solid #dbeafe;
}
table.vt tr:nth-child(even) td { background: transparent; }
.cmp-box, .mcq-box {
  background: transparent;
  border: 0.6px solid #dbeafe;
  padding: 6px 8px;
}
.mcq-box { border-color: #bbf7d0; }
.mcq-expl { border-top: 0.5px solid #e2e8f0; }
.diag-line { line-height: 1.35; }
"""
'''
if src.count(css_anchor) != 1:
    raise RuntimeError(f"pdf final CSS anchor matched {src.count(css_anchor)} times")
src = src.replace(css_anchor, css_override, 1)

# 2) For Turkish PDF output, translate MCQ options in one cached batch for the whole
# course instead of leaving English options under a Turkish prompt.
parts_anchor = '''            parts = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"]
            answer_key_entries = []
            question_counter = 0
'''
parts_repl = '''            parts = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"]
            answer_key_entries = []
            question_counter = 0
            pdf_option_tr_map = {}
            if is_tr:
                try:
                    from services.bilingual_finisher import batch_translate_strings
                    option_candidates = []
                    with db_connection() as loc_db:
                        loc_rows = loc_db.execute(
                            """SELECT t.content FROM topics t
                               JOIN chapters ch ON t.chapter_id = ch.id
                               WHERE ch.course_id = ? AND t.content IS NOT NULL""",
                            (course_id,)
                        ).fetchall()
                    for loc_row in loc_rows:
                        try:
                            loc_obj = _json.loads(loc_row[0]) if loc_row[0] else {}
                        except Exception:
                            loc_obj = {}
                        for loc_page in loc_obj.get("pages") or []:
                            if loc_page.get("type") != "mcq":
                                continue
                            for loc_opt in loc_page.get("options") or []:
                                if isinstance(loc_opt, str) and loc_opt.strip():
                                    option_candidates.append(loc_opt.strip())
                            loc_answer = loc_page.get("answer")
                            if isinstance(loc_answer, str) and loc_answer.strip():
                                option_candidates.append(loc_answer.strip())
                    if option_candidates:
                        pdf_option_tr_map = batch_translate_strings(list(dict.fromkeys(option_candidates)), target_lang="tr")
                except Exception as option_loc_err:
                    print(f"[PDF EXPORT] MCQ option localization fallback: {option_loc_err}")
'''
if src.count(parts_anchor) != 1:
    raise RuntimeError(f"pdf option map anchor matched {src.count(parts_anchor)} times")
src = src.replace(parts_anchor, parts_repl, 1)

mcq_anchor = '''                                options   = page.get("options") or []
                                answer    = page.get("answer") or ""
'''
mcq_repl = '''                                raw_options = page.get("options") or []
                                answer    = page.get("answer") or ""
                                options = [pdf_option_tr_map.get(str(opt).strip(), opt) for opt in raw_options] if is_tr else raw_options
                                answer_display = pdf_option_tr_map.get(str(answer).strip(), answer) if is_tr else answer
'''
if src.count(mcq_anchor) != 1:
    raise RuntimeError(f"pdf MCQ localization anchor matched {src.count(mcq_anchor)} times")
src = src.replace(mcq_anchor, mcq_repl, 1)

answer_index_anchor = '''                                    answer_letter = chr(65 + [str(o).strip() for o in options].index(str(answer).strip()))
'''
answer_index_repl = '''                                    answer_letter = chr(65 + [str(o).strip() for o in raw_options].index(str(answer).strip()))
'''
if src.count(answer_index_anchor) != 1:
    raise RuntimeError(f"pdf answer index anchor matched {src.count(answer_index_anchor)} times")
src = src.replace(answer_index_anchor, answer_index_repl, 1)

answer_value_anchor = '''                                    "answer": str(answer or ""),
'''
answer_value_repl = '''                                    "answer": str(answer_display or ""),
'''
if src.count(answer_value_anchor) != 1:
    raise RuntimeError(f"pdf answer display anchor matched {src.count(answer_value_anchor)} times")
src = src.replace(answer_value_anchor, answer_value_repl, 1)

server_path.write_text(src, encoding="utf-8")

# 3) Client-side fixes: localize English material MCQ options in Turkish UI,
# replace the PDF language picker with the same two-letter language markers used by
# the classroom language selector, and keep PDF 'preparing' text synced while the UI
# language is toggled.
app_path = Path("public/js/app.js")
app_src = app_path.read_text(encoding="utf-8")
marker = "AULA_PDF_UI_LOCALIZATION_V2"
if marker not in app_src:
    app_src += r'''

// AULA_PDF_UI_LOCALIZATION_V2
(() => {
  const optionCache = new Map();
  const optionPending = new Map();
  const englishSignal = /\b(the|and|is|are|it|changes|tone|first|second|third|fourth|remains|full|rising|falling|high|flat|correct|sentence|choose|means|response|appropriate|naturally|please|thank|sorry|excuse|morning|afternoon|teacher|student)\b/i;

  async function translateStudyOption(btn) {
    if (!btn || btn.nodeType !== 1) return;
    if (!btn.closest('#ai-book-content-area, #s-ai-book-content-area')) return;
    if (btn.classList.contains('tts-btn') || btn.hasAttribute('data-i18n')) return;
    const onclick = btn.getAttribute('onclick') || '';
    if (/TTS|toggle|edit|delete|close|next|prev/i.test(onclick)) return;

    const visible = (btn.dataset.aulaOriginalOption || btn.textContent || '').trim();
    if (!btn.dataset.aulaOriginalOption) btn.dataset.aulaOriginalOption = visible;
    const original = btn.dataset.aulaOriginalOption.trim();
    if (!original || original.length < 8 || !englishSignal.test(original)) return;

    if (typeof currentLang !== 'undefined' && currentLang !== 'tr') {
      if (btn.dataset.aulaTranslatedOption === '1') btn.textContent = original;
      return;
    }

    try {
      if (optionCache.has(original)) {
        btn.textContent = optionCache.get(original);
        btn.dataset.aulaTranslatedOption = '1';
        return;
      }
      let p = optionPending.get(original);
      if (!p) {
        p = fetch('/api/translate/material', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({text: original, target_lang: 'tr'})
        }).then(r => r.ok ? r.json() : null)
          .then(data => (data && data.translated) ? String(data.translated).trim() : '')
          .finally(() => optionPending.delete(original));
        optionPending.set(original, p);
      }
      const translated = await p;
      if (translated && translated !== original && currentLang === 'tr') {
        optionCache.set(original, translated);
        btn.textContent = translated;
        btn.dataset.aulaTranslatedOption = '1';
      }
    } catch (_) {}
  }

  function scanStudyOptions(root = document) {
    const buttons = [];
    if (root.matches && root.matches('#ai-book-content-area button, #s-ai-book-content-area button')) buttons.push(root);
    if (root.querySelectorAll) buttons.push(...root.querySelectorAll('#ai-book-content-area button, #s-ai-book-content-area button'));
    buttons.forEach(translateStudyOption);
  }

  const observer = new MutationObserver(mutations => {
    for (const m of mutations) {
      m.addedNodes.forEach(n => {
        if (n && n.nodeType === 1) scanStudyOptions(n);
      });
    }
  });

  function syncPdfExportLanguageUI() {
    const isTr = (typeof currentLang !== 'undefined' && currentLang === 'tr');
    document.querySelectorAll('#export-pdf-btn[disabled], #s-export-pdf-btn[disabled]').forEach(btn => {
      const span = btn.querySelector('span');
      if (span) span.textContent = isTr ? 'Hazırlanıyor...' : 'Preparing...';
    });
    const title = document.getElementById('pdf-lang-picker-title');
    const sub = document.getElementById('pdf-lang-picker-sub');
    const cancel = document.getElementById('pdf-lang-picker-cancel');
    if (title) title.textContent = isTr ? 'PDF Dili' : 'PDF Language';
    if (sub) sub.textContent = isTr ? 'İndirilecek materyalin dilini seçin.' : 'Choose the language of the exported material.';
    if (cancel) cancel.textContent = isTr ? 'İptal' : 'Cancel';
    scanStudyOptions(document);
  }

  // Replace the old picker. The compact EN/TR marker is the same visual language
  // marker used by the classroom-creation language grid.
  showPdfLangPicker = function() {
    return new Promise(resolve => {
      const prev = document.getElementById('pdf-lang-modal');
      if (prev) prev.remove();
      const isTr = currentLang === 'tr';
      const modal = document.createElement('div');
      modal.id = 'pdf-lang-modal';
      modal.style.cssText = 'position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.5);backdrop-filter:blur(4px);padding:20px;';
      modal.innerHTML = `
        <div style="width:min(420px,100%);background:var(--bg-card);border:1px solid var(--border);border-radius:16px;padding:22px;box-shadow:0 24px 70px rgba(0,0,0,.35);">
          <div id="pdf-lang-picker-title" style="font-size:20px;font-weight:800;color:var(--text-primary);margin-bottom:6px;">${isTr ? 'PDF Dili' : 'PDF Language'}</div>
          <div id="pdf-lang-picker-sub" style="font-size:13px;color:var(--text-secondary);margin-bottom:18px;">${isTr ? 'İndirilecek materyalin dilini seçin.' : 'Choose the language of the exported material.'}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <button type="button" data-pdf-lang="tr" class="btn btn-ghost" style="height:auto;padding:16px 12px;border:2px solid var(--border);border-radius:12px;display:flex;flex-direction:column;align-items:center;gap:8px;">
              <span style="font-size:13px;font-weight:800;letter-spacing:.5px;padding:4px 8px;border-radius:6px;background:rgba(99,102,241,.12);color:var(--accent);">TR</span>
              <span style="font-size:13px;font-weight:700;">Türkçe</span>
            </button>
            <button type="button" data-pdf-lang="en" class="btn btn-ghost" style="height:auto;padding:16px 12px;border:2px solid var(--border);border-radius:12px;display:flex;flex-direction:column;align-items:center;gap:8px;">
              <span style="font-size:13px;font-weight:800;letter-spacing:.5px;padding:4px 8px;border-radius:6px;background:rgba(99,102,241,.12);color:var(--accent);">EN</span>
              <span style="font-size:13px;font-weight:700;">English</span>
            </button>
          </div>
          <button id="pdf-lang-picker-cancel" type="button" class="btn btn-ghost" style="width:100%;margin-top:12px;">${isTr ? 'İptal' : 'Cancel'}</button>
        </div>`;
      document.body.appendChild(modal);

      const finish = value => { if (modal.isConnected) modal.remove(); resolve(value); };
      modal.querySelectorAll('[data-pdf-lang]').forEach(btn => btn.addEventListener('click', () => finish(btn.dataset.pdfLang)));
      modal.querySelector('#pdf-lang-picker-cancel').addEventListener('click', () => finish(null));
      modal.addEventListener('click', e => { if (e.target === modal) finish(null); });
    });
  };
  window.showPdfLangPicker = showPdfLangPicker;

  if (typeof toggleLanguage === 'function' && !toggleLanguage.__aulaPdfWrapped) {
    const originalToggleLanguage = toggleLanguage;
    const wrapped = function(...args) {
      const result = originalToggleLanguage.apply(this, args);
      setTimeout(syncPdfExportLanguageUI, 0);
      return result;
    };
    wrapped.__aulaPdfWrapped = true;
    toggleLanguage = wrapped;
    window.toggleLanguage = wrapped;
  }

  const start = () => {
    scanStudyOptions(document);
    syncPdfExportLanguageUI();
    observer.observe(document.body, {childList:true, subtree:true});
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
'''
    app_path.write_text(app_src, encoding="utf-8")

print("Applied PDF UI/localization v2 patch")
