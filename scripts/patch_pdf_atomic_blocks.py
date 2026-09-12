from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

# Make MCQ blocks structurally atomic for PyMuPDF Story by wrapping each whole
# question+options block in a single table row/cell. Story reliably keeps table rows
# together even when CSS page-break-inside on divs is ignored.
old = '''                                question_counter += 1
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
new = '''                                question_counter += 1
                                parts.append(f'<table class="atomic-shell"><tr><td><div class="mcq-box"><div class="mcq-q">{question_counter}. {E(str(prompt))}</div>')
                                if options:
                                    parts.append('<div class="mcq-opts">')
                                    for opt_idx, opt in enumerate(options):
                                        letter = chr(65 + opt_idx)
                                        parts.append(f'<div class="mcq-opt">{letter}) {E(str(opt))}</div>')
                                    parts.append('</div>')
                                parts.append('</div></td></tr></table>')
                                answer_letter = ""
'''
if src.count(old) != 1:
    raise RuntimeError(f'MCQ atomic anchor matched {src.count(old)} times')
src = src.replace(old, new, 1)

# Wrap short vocabulary tables after HTML assembly. This avoids splitting a small
# coherent list across pages, while long tables remain naturally pageable.
old2 = '''            full_html = "".join(parts)
'''
new2 = '''            full_html = "".join(parts)

            def _keep_short_vocabulary_table(match):
                table_html = match.group(0)
                # Header + up to 9 data rows: safe to keep together on a normal page.
                row_count = table_html.count('<tr>')
                if row_count <= 10:
                    return '<table class="atomic-shell"><tr><td>' + table_html + '</td></tr></table>'
                return table_html

            full_html = re.sub(r'<table class="vt">.*?</table>', _keep_short_vocabulary_table, full_html, flags=re.S)
'''
if src.count(old2) != 1:
    raise RuntimeError(f'full_html anchor matched {src.count(old2)} times')
src = src.replace(old2, new2, 1)

# Atomic shell itself is invisible; it exists only to give Story an unsplittable row.
css_anchor = '''.mcq-opts { margin-left: 10px; }
'''
css_add = '''.mcq-opts { margin-left: 10px; }
.atomic-shell { width: 100%; border-collapse: collapse; border: none; margin: 0; padding: 0; page-break-inside: avoid; break-inside: avoid; }
.atomic-shell > tbody > tr > td, .atomic-shell > tr > td { border: none; padding: 0; margin: 0; background: transparent; }
'''
if src.count(css_anchor) < 1:
    raise RuntimeError('atomic-shell CSS anchor missing')
src = src.replace(css_anchor, css_add, 1)

path.write_text(src, encoding='utf-8')
print('Applied structural atomic pagination for PDF questions and short vocabulary tables')
