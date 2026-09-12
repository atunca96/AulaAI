from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

# MCQ: keep section heading + question + all options in one structural row.
old = '''                                q_title   = tx(page, "title", "title_tr") or ""
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
new = '''                                q_title   = tx(page, "title", "title_tr") or ""
                                question_counter += 1
                                parts.append('<table class="atomic-shell"><tr><td>')
                                if q_title:
                                    parts.append(f'<div class="sec-h">{E(q_title)}</div>')
                                parts.append(f'<div class="mcq-box"><div class="mcq-q">{question_counter}. {E(str(prompt))}</div>')
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

# Dialogue/examples: keep the heading, explanatory text, and all dialogue lines in one
# structural row. These blocks are short enough to fit on a page in current materials;
# if they do not fit in the remaining space, Story moves the whole group forward.
old_dialogue = '''                            elif ptype == "examples":
                                title = tx(page, "title", "title_tr")
                                text  = tx(page, "text", "text_tr")
                                if title:
                                    parts.append(f'<div class="sec-h">{E(title)}</div>')
                                if text:
                                    parts.append(f'<div class="text-block">{E(text)}</div>')
                                for d in page.get("dialogue") or []:
                                    spk    = d.get("speaker") or "?"
                                    said   = d.get("text") or d.get("line") or ""
                                    line_en = d.get("line_en") or ""
                                    line_tr = d.get("line_tr") or ""
                                    tr_text = line_tr if is_tr else line_en
                                    parts.append(
                                        f'<div class="diag-line">'
                                        f'<span class="spkr">{E(str(spk))}:</span>'
                                        f'<span class="said">&ldquo;{E(str(said))}&rdquo;'
                                        f'{(" <span class=\"said-tr\">(" + E(str(tr_text)) + ")</span>") if tr_text else ""}'
                                        f'</span></div>'
                                    )
'''
new_dialogue = '''                            elif ptype == "examples":
                                title = tx(page, "title", "title_tr")
                                text  = tx(page, "text", "text_tr")
                                parts.append('<table class="atomic-shell"><tr><td>')
                                if title:
                                    parts.append(f'<div class="sec-h">{E(title)}</div>')
                                if text:
                                    parts.append(f'<div class="text-block">{E(text)}</div>')
                                for d in page.get("dialogue") or []:
                                    spk    = d.get("speaker") or "?"
                                    said   = d.get("text") or d.get("line") or ""
                                    line_en = d.get("line_en") or ""
                                    line_tr = d.get("line_tr") or ""
                                    tr_text = line_tr if is_tr else line_en
                                    parts.append(
                                        f'<div class="diag-line">'
                                        f'<span class="spkr">{E(str(spk))}:</span>'
                                        f'<span class="said">&ldquo;{E(str(said))}&rdquo;'
                                        f'{(" <span class=\"said-tr\">(" + E(str(tr_text)) + ")</span>") if tr_text else ""}'
                                        f'</span></div>'
                                    )
                                parts.append('</td></tr></table>')
'''
if src.count(old_dialogue) != 1:
    raise RuntimeError(f'Dialogue atomic anchor matched {src.count(old_dialogue)} times')
src = src.replace(old_dialogue, new_dialogue, 1)

# After all HTML is assembled, wrap short vocabulary tables in an unsplittable shell.
old2 = '''            full_html = "".join(parts)
'''
new2 = '''            full_html = "".join(parts)

            def _keep_short_vocabulary_table(match):
                table_html = match.group(0)
                row_count = table_html.count('<tr>')
                if row_count <= 10:
                    return '<table class="atomic-shell"><tr><td>' + table_html + '</td></tr></table>'
                return table_html

            full_html = re.sub(r'<table class="vt">.*?</table>', _keep_short_vocabulary_table, full_html, flags=re.S)
'''
if src.count(old2) != 1:
    raise RuntimeError(f'full_html anchor matched {src.count(old2)} times')
src = src.replace(old2, new2, 1)

# Atomic shell itself is invisible. The table-row structure is what PyMuPDF Story
# reliably treats as indivisible when ordinary CSS break rules are ignored.
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
print('Applied structural atomic pagination for PDF questions, dialogues, and short vocabulary tables')
