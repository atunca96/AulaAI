from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

# Balanced pagination for PyMuPDF Story:
# - MCQs become a single native one-row table. MuPDF keeps table rows together.
# - Only genuinely short vocabulary tables are wrapped as one atomic row.
# - The printable rectangle is slightly taller to reduce needless carry-over.
# This avoids the previous extremes: split questions vs. half-empty pages.

css_anchor = '''.mcq-opts { margin-left: 10px; }
'''
css_repl = '''.mcq-opts { margin-left: 10px; }
.mcq-atomic { width: 100%; border-collapse: collapse; border: none; margin: 5px 0 7px 0; }
.mcq-atomic > tbody > tr > td, .mcq-atomic > tr > td { border: 0.5px solid #d1d5db; background: #fff; padding: 6px 8px; }
.mcq-atomic .mcq-q { font-weight: 700; margin: 0 0 4px 0; line-height: 1.28; }
.mcq-atomic .mcq-opt { margin: 2px 0; line-height: 1.25; }
.vt-keep { width: 100%; border-collapse: collapse; border: none; margin: 0; padding: 0; }
.vt-keep > tbody > tr > td, .vt-keep > tr > td { border: none; background: transparent; padding: 0; margin: 0; }
'''
if src.count(css_anchor) < 1:
    raise RuntimeError('pagination CSS anchor missing')
src = src.replace(css_anchor, css_repl, 1)

# Replace the generated MCQ block with a single-row table. Avoid nested outer wrappers:
# the one row itself is the indivisible unit documented by PyMuPDF Story.
mcq_old = '''                                q_title   = tx(page, "title", "title_tr") or ""
                                if q_title:
                                    parts.append(f'<div class="sec-h">{E(q_title)}</div>')
                                question_counter += 1
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
mcq_new = '''                                q_title   = tx(page, "title", "title_tr") or ""
                                question_counter += 1
                                parts.append('<table class="mcq-atomic"><tr><td>')
                                if q_title:
                                    parts.append(f'<div class="sec-h">{E(q_title)}</div>')
                                parts.append(f'<div class="mcq-q">{question_counter}. {E(str(prompt))}</div>')
                                if options:
                                    for opt_idx, opt in enumerate(options):
                                        letter = chr(65 + opt_idx)
                                        parts.append(f'<div class="mcq-opt">{letter}) {E(str(opt))}</div>')
                                parts.append('</td></tr></table>')
                                answer_letter = ""
'''
count = src.count(mcq_old)
if count != 1:
    raise RuntimeError(f'MCQ atomic anchor matched {count} times')
src = src.replace(mcq_old, mcq_new, 1)

# Wrap only short vocabulary tables (header + <= 6 data rows). These are small enough
# to fit on one A4 content area after compact styling; long tables remain naturally pageable.
full_html_anchor = '''            full_html = "".join(parts)

            # ── Render with fitz.Story ────────────────────────────────────────
'''
full_html_repl = '''            full_html = "".join(parts)

            def _keep_short_vt(match):
                table_html = match.group(0)
                row_count = table_html.count('<tr>')
                if row_count <= 7:
                    return '<table class="vt-keep"><tr><td>' + table_html + '</td></tr></table>'
                return table_html

            full_html = re.sub(r'<table class="vt">.*?</table>', _keep_short_vt, full_html, flags=re.S)

            # ── Render with fitz.Story ────────────────────────────────────────
'''
if src.count(full_html_anchor) != 1:
    raise RuntimeError(f'full_html pagination anchor matched {src.count(full_html_anchor)} times')
src = src.replace(full_html_anchor, full_html_repl, 1)

# Give the content a little more usable height without colliding with header/footer.
old_rect = '''story.write(writer, lambda n, f: (fitz.paper_rect("a4"), fitz.Rect(36, 44, 559, 800), None))'''
new_rect = '''story.write(writer, lambda n, f: (fitz.paper_rect("a4"), fitz.Rect(34, 38, 561, 812), None))'''
if src.count(old_rect) != 1:
    raise RuntimeError(f'PDF content rect anchor matched {src.count(old_rect)} times')
src = src.replace(old_rect, new_rect, 1)

path.write_text(src, encoding='utf-8')
print('Applied balanced MCQ/short-table pagination with expanded content area')
