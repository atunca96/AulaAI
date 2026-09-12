from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

# Apply pagination atomics after the stable PDF patch using only post-render HTML
# transformations. This avoids brittle source-code anchors that can change when an
# earlier build patch rewrites the MCQ/dialogue branches.

old = '''            full_html = "".join(parts)
'''
new = '''            full_html = "".join(parts)

            def _atomic_wrap(html_fragment):
                return '<table class="atomic-shell"><tr><td>' + html_fragment + '</td></tr></table>'

            # Keep section heading + MCQ box together where they are emitted adjacently.
            full_html = re.sub(
                r'(<div class="sec-h">.*?</div>)(<div class="mcq-box">.*?</div>)',
                lambda m: _atomic_wrap(m.group(1) + m.group(2)),
                full_html,
                flags=re.S,
            )

            # Keep any remaining standalone MCQ question + complete options together.
            full_html = re.sub(
                r'(?<!<td>)(<div class="mcq-box">.*?</div>)',
                lambda m: _atomic_wrap(m.group(1)),
                full_html,
                flags=re.S,
            )

            # Keep contiguous dialogue lines together so the final line cannot spill by itself.
            dialogue_group_re = r'((?:<div class="diag-line">.*?</div>){2,})'
            full_html = re.sub(
                dialogue_group_re,
                lambda m: _atomic_wrap(m.group(1)),
                full_html,
                flags=re.S,
            )

            # Keep short vocabulary tables together. Long tables remain splittable by row.
            def _keep_short_vocabulary_table(match):
                table_html = match.group(0)
                row_count = table_html.count('<tr>')
                if row_count <= 10:
                    return _atomic_wrap(table_html)
                return table_html

            full_html = re.sub(r'<table class="vt">.*?</table>', _keep_short_vocabulary_table, full_html, flags=re.S)
'''
if src.count(old) != 1:
    raise RuntimeError(f'full_html anchor matched {src.count(old)} times')
src = src.replace(old, new, 1)

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
print('Applied resilient post-render atomic PDF pagination')
