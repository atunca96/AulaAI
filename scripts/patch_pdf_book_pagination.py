from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

# Add small structural helpers inside the existing, proven PDF export path.
# PyMuPDF Story can ignore break-inside on divs, but it reliably keeps a single
# table row together. We only use that behavior for genuinely short logical
# blocks so we do not recreate the large-white-gap problem.
helper_anchor = '''            def tx(page_dict, en_key, tr_key):
                """Pick the right language text from a dict."""
                if is_tr:
                    return page_dict.get(tr_key) or page_dict.get(en_key) or ""
                return page_dict.get(en_key) or page_dict.get(tr_key) or ""

'''
helper_repl = helper_anchor + '''            def append_book_text_block(parts, text):
                raw = str(text or "")
                rendered = E(raw)
                # Short academic paragraphs should never be cut in half. Long
                # explanations are allowed to flow naturally across pages.
                if len(raw) <= 420:
                    parts.append(
                        f'<table class="keep-table"><tr><td>'
                        f'<div class="text-block">{rendered}</div>'
                        f'</td></tr></table>'
                    )
                else:
                    parts.append(f'<div class="text-block">{rendered}</div>')

'''
if src.count(helper_anchor) != 1:
    raise RuntimeError(f'book pagination helper anchor matched {src.count(helper_anchor)} times')
src = src.replace(helper_anchor, helper_repl, 1)

# Route every existing explanatory text block through the helper. There are three
# source sites in the current exporter: overview/grammar, comparisons, examples.
text_line = '''                                    parts.append(f'<div class="text-block">{E(text)}</div>')
'''
text_count = src.count(text_line)
if text_count != 3:
    raise RuntimeError(f'book pagination text-block anchor matched {text_count} times')
src = src.replace(text_line, '''                                    append_book_text_block(parts, text)
''')

# Replace only the student-visible MCQ body with a single native table row.
# This guarantees question + all options stay together without wrapping entire
# topics/tables and without forcing every content section onto a new page.
mcq_old = '''                                question_counter += 1
                                parts.append(f'<div class="mcq-box"><div class="mcq-q">{question_counter}. {E(str(prompt))}</div>')
                                if options:
                                    parts.append('<div class="mcq-opts">')
                                    for opt_idx, opt in enumerate(options):
                                        letter = chr(65 + opt_idx)
                                        parts.append(f'<div class="mcq-opt">{letter}) {E(str(opt))}</div>')
                                    parts.append('</div>')
                                parts.append('</div>')
                                answer_letter = ""
'''
mcq_new = '''                                question_counter += 1
                                parts.append('<table class="mcq-table"><tr><td>')
                                parts.append(f'<div class="mcq-q">{question_counter}. {E(str(prompt))}</div>')
                                if options:
                                    parts.append('<div class="mcq-opts">')
                                    for opt_idx, opt in enumerate(options):
                                        letter = chr(65 + opt_idx)
                                        parts.append(f'<div class="mcq-opt">{letter}) {E(str(opt))}</div>')
                                    parts.append('</div>')
                                parts.append('</td></tr></table>')
                                answer_letter = ""
'''
if src.count(mcq_old) != 1:
    raise RuntimeError(f'book pagination MCQ anchor matched {src.count(mcq_old)} times')
src = src.replace(mcq_old, mcq_new, 1)

# Add restrained academic layout rules. Long content and vocabulary tables still
# flow naturally; only rows and explicitly short logical blocks are atomic.
css_anchor = '''.mcq-opts { margin-left: 10px; }
"""
'''
css_repl = '''.mcq-opts { margin-left: 10px; }

/* Book-style pagination: compact, academic, no giant wrapper boxes. */
.keep-table, .mcq-table {
  width: 100%;
  border-collapse: collapse;
  border: none;
  margin: 0 0 7px 0;
  page-break-inside: avoid;
  break-inside: avoid;
}
.keep-table > tbody > tr > td,
.keep-table > tr > td {
  border: none;
  padding: 0;
  background: transparent;
}
.mcq-table > tbody > tr > td,
.mcq-table > tr > td {
  border: 0.5px solid #d1d5db;
  padding: 7px 9px;
  background: transparent;
}
.text-block { page-break-inside: auto; break-inside: auto; }
p { orphans: 2; widows: 2; }
.unit-card, .topic-title, .sec-h { page-break-after: avoid; break-after: avoid; }
table.vt { page-break-inside: auto; break-inside: auto; }
table.vt tr { page-break-inside: avoid; break-inside: avoid; }
.diag-line { page-break-inside: avoid; break-inside: avoid; }
"""
'''
if src.count(css_anchor) != 1:
    raise RuntimeError(f'book pagination CSS anchor matched {src.count(css_anchor)} times')
src = src.replace(css_anchor, css_repl, 1)

path.write_text(src, encoding='utf-8')
print('Applied compact academic PDF pagination on stable exporter')
