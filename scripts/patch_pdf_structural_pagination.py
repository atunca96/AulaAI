from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

# This patch runs after the stable localization/layout patches. It changes only the
# generated PDF HTML structure, not content, translation, or database behavior.
# PyMuPDF Story reliably keeps a table row intact; use that only for short coherent
# blocks that are known to fit on one A4 content frame.

# 1) Add invisible structural keep wrapper CSS.
css_anchor = '''.mcq-opts { margin-left: 10px; }
'''
css_repl = '''.mcq-opts { margin-left: 10px; }
.keep-block { width: 100%; border-collapse: collapse; border: none; margin: 0 0 6px 0; padding: 0; }
.keep-block > tbody > tr > td, .keep-block > tr > td { border: none; background: transparent; padding: 0; margin: 0; }
'''
if src.count(css_anchor) < 1:
    raise RuntimeError('keep-block CSS anchor missing')
src = src.replace(css_anchor, css_repl, 1)

# 2) MCQ: q_title + question + all options are one short assessment block.
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
                                parts.append('<table class="keep-block"><tr><td>')
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
if src.count(mcq_old) != 1:
    raise RuntimeError(f'MCQ structural anchor matched {src.count(mcq_old)} times')
src = src.replace(mcq_old, mcq_new, 1)

# 3) Dialogue/examples: atomize only genuinely short dialogue groups. Long groups remain
# naturally pageable, but each individual dialogue line is already non-breaking via CSS.
dlg_old = '''                            elif ptype == "examples":
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
dlg_new = '''                            elif ptype == "examples":
                                title = tx(page, "title", "title_tr")
                                text  = tx(page, "text", "text_tr")
                                dialogue_rows = page.get("dialogue") or []
                                dialogue_chars = sum(
                                    len(str(d.get("text") or d.get("line") or "")) +
                                    len(str((d.get("line_tr") if is_tr else d.get("line_en")) or ""))
                                    for d in dialogue_rows
                                )
                                keep_dialogue = bool(dialogue_rows) and len(dialogue_rows) <= 8 and dialogue_chars <= 1500
                                if keep_dialogue:
                                    parts.append('<table class="keep-block"><tr><td>')
                                if title:
                                    parts.append(f'<div class="sec-h">{E(title)}</div>')
                                if text:
                                    parts.append(f'<div class="text-block">{E(text)}</div>')
                                for d in dialogue_rows:
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
                                if keep_dialogue:
                                    parts.append('</td></tr></table>')
'''
if src.count(dlg_old) != 1:
    raise RuntimeError(f'Dialogue structural anchor matched {src.count(dlg_old)} times')
src = src.replace(dlg_old, dlg_new, 1)

# 4) Short vocabulary tables: put the heading + table into one row only when the table
# is small enough to fit comfortably. Larger tables keep normal row pagination.
vocab_start_old = '''                                items = page.get("items") or []
                                if items:
                                    h_term  = "Terim / Kelime" if is_tr else "Term / Word"
'''
vocab_start_new = '''                                items = page.get("items") or []
                                if items:
                                    keep_vocab = len(items) <= 6
                                    if keep_vocab:
                                        parts.append('<table class="keep-block"><tr><td>')
                                    h_term  = "Terim / Kelime" if is_tr else "Term / Word"
'''
if src.count(vocab_start_old) != 1:
    raise RuntimeError(f'Vocabulary start anchor matched {src.count(vocab_start_old)} times')
src = src.replace(vocab_start_old, vocab_start_new, 1)

vocab_end_old = '''                                    parts.append('</table>')

                            # ── COMPARISONS'''
vocab_end_new = '''                                    parts.append('</table>')
                                    if keep_vocab:
                                        parts.append('</td></tr></table>')

                            # ── COMPARISONS'''
if src.count(vocab_end_old) != 1:
    raise RuntimeError(f'Vocabulary end anchor matched {src.count(vocab_end_old)} times')
src = src.replace(vocab_end_old, vocab_end_new, 1)

path.write_text(src, encoding='utf-8')
print('Applied structural PDF pagination for MCQs, short dialogues, and short vocabulary tables')
