from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

# Compact pagination strategy for PyMuPDF Story:
# - Use native single-row tables only for SHORT logical blocks.
# - Do not wrap vocabulary tables: nested tables caused large blank areas.
# - Keep long content flowing normally.

css_anchor = '''.mcq-opts { margin-left: 10px; }\n'''
css_repl = '''.mcq-opts { margin-left: 10px; }\n.keep-short { width:100%; border-collapse:collapse; border:none; margin:5px 0 7px 0; padding:0; }\n.keep-short > tbody > tr > td, .keep-short > tr > td { border:none; background:#fff; padding:0; margin:0; vertical-align:top; }\n.mcq-atomic { width:100%; border-collapse:collapse; border:0.5px solid #d1d5db; margin:5px 0 7px 0; }\n.mcq-atomic > tbody > tr > td, .mcq-atomic > tr > td { border:none; background:#fff; padding:6px 8px; vertical-align:top; }\n.mcq-atomic .qtitle { font-weight:700; color:#374151; margin-bottom:4px; line-height:1.25; }\n.mcq-atomic .qprompt { font-weight:700; line-height:1.3; margin-bottom:4px; }\n.mcq-atomic .qopt { line-height:1.3; margin-left:10px; }\n'''
if src.count(css_anchor) < 1:
    raise RuntimeError('pagination CSS anchor missing')
src = src.replace(css_anchor, css_repl, 1)

# MCQ: render heading + prompt + all options as one simple native table row.
# Avoid nested div-box wrappers, which made Story overestimate height.
mcq_old = '''                                q_title   = tx(page, "title", "title_tr") or ""\n                                if q_title:\n                                    parts.append(f'<div class="sec-h">{E(q_title)}</div>')\n                                question_counter += 1\n                                parts.append(f'<div class="mcq-box"><div class="mcq-q">{question_counter}. {E(str(prompt))}</div>')\n                                if options:\n                                    parts.append('<div class="mcq-opts">')\n                                    for opt_idx, opt in enumerate(options):\n                                        letter = chr(65 + opt_idx)\n                                        parts.append(f'<div class="mcq-opt">{letter}) {E(str(opt))}</div>')\n                                    parts.append('</div>')\n                                parts.append('</div>')\n                                answer_letter = ""\n'''
mcq_new = '''                                q_title   = tx(page, "title", "title_tr") or ""\n                                question_counter += 1\n                                parts.append('<table class="mcq-atomic"><tr><td>')\n                                if q_title:\n                                    parts.append(f'<div class="qtitle">{E(q_title)}</div>')\n                                parts.append(f'<div class="qprompt">{question_counter}. {E(str(prompt))}</div>')\n                                if options:\n                                    for opt_idx, opt in enumerate(options):\n                                        letter = chr(65 + opt_idx)\n                                        parts.append(f'<div class="qopt">{letter}) {E(str(opt))}</div>')\n                                parts.append('</td></tr></table>')\n                                answer_letter = ""\n'''
count = src.count(mcq_old)
if count != 1:
    raise RuntimeError(f'MCQ pagination anchor matched {count} times')
src = src.replace(mcq_old, mcq_new, 1)

# Short overview/grammar notes should not split mid-paragraph. Long notes still flow.
overview_old = '''                            if ptype in ("overview", "grammar"):\n                                title = tx(page, "title", "title_tr")\n                                text  = tx(page, "text", "text_tr")\n                                if title:\n                                    parts.append(f'<div class="sec-h">{E(title)}</div>')\n                                if text:\n                                    parts.append(f'<div class="text-block">{E(text)}</div>')\n'''
overview_new = '''                            if ptype in ("overview", "grammar"):\n                                title = tx(page, "title", "title_tr")\n                                text  = tx(page, "text", "text_tr")\n                                if text and len(str(text)) <= 720:\n                                    parts.append('<table class="keep-short"><tr><td>')\n                                    if title:\n                                        parts.append(f'<div class="sec-h">{E(title)}</div>')\n                                    parts.append(f'<div class="text-block">{E(text)}</div>')\n                                    parts.append('</td></tr></table>')\n                                else:\n                                    if title:\n                                        parts.append(f'<div class="sec-h">{E(title)}</div>')\n                                    if text:\n                                        parts.append(f'<div class="text-block">{E(text)}</div>')\n'''
count = src.count(overview_old)
if count != 1:
    raise RuntimeError(f'overview pagination anchor matched {count} times')
src = src.replace(overview_old, overview_new, 1)

# Short dialogues are one logical teaching block; long dialogues remain pageable.
examples_old = '''                            elif ptype == "examples":\n                                title = tx(page, "title", "title_tr")\n                                text  = tx(page, "text", "text_tr")\n                                if title:\n                                    parts.append(f'<div class="sec-h">{E(title)}</div>')\n                                if text:\n                                    parts.append(f'<div class="text-block">{E(text)}</div>')\n                                for d in page.get("dialogue") or []:\n                                    spk    = d.get("speaker") or "?"\n                                    said   = d.get("text") or d.get("line") or ""\n                                    line_en = d.get("line_en") or ""\n                                    line_tr = d.get("line_tr") or ""\n                                    tr_text = line_tr if is_tr else line_en\n                                    parts.append(\n                                        f'<div class="diag-line">'\n                                        f'<span class="spkr">{E(str(spk))}:</span>'\n                                        f'<span class="said">&ldquo;{E(str(said))}&rdquo;'\n                                        f'{(" <span class=\\"said-tr\\">(" + E(str(tr_text)) + ")</span>") if tr_text else ""}'\n                                        f'</span></div>'\n                                    )\n'''
examples_new = '''                            elif ptype == "examples":\n                                title = tx(page, "title", "title_tr")\n                                text  = tx(page, "text", "text_tr")\n                                dialogue_rows = page.get("dialogue") or []\n                                approx_len = len(str(text or "")) + sum(len(str(d.get("text") or d.get("line") or "")) + len(str((d.get("line_tr") if is_tr else d.get("line_en")) or "")) for d in dialogue_rows)\n                                keep_dialogue = bool(dialogue_rows) and len(dialogue_rows) <= 5 and approx_len <= 780\n                                if keep_dialogue:\n                                    parts.append('<table class="keep-short"><tr><td>')\n                                if title:\n                                    parts.append(f'<div class="sec-h">{E(title)}</div>')\n                                if text:\n                                    parts.append(f'<div class="text-block">{E(text)}</div>')\n                                for d in dialogue_rows:\n                                    spk    = d.get("speaker") or "?"\n                                    said   = d.get("text") or d.get("line") or ""\n                                    line_en = d.get("line_en") or ""\n                                    line_tr = d.get("line_tr") or ""\n                                    tr_text = line_tr if is_tr else line_en\n                                    parts.append(\n                                        f'<div class="diag-line">'\n                                        f'<span class="spkr">{E(str(spk))}:</span>'\n                                        f'<span class="said">&ldquo;{E(str(said))}&rdquo;'\n                                        f'{(" <span class=\\"said-tr\\">(" + E(str(tr_text)) + ")</span>") if tr_text else ""}'\n                                        f'</span></div>'\n                                    )\n                                if keep_dialogue:\n                                    parts.append('</td></tr></table>')\n'''
count = src.count(examples_old)
if count != 1:
    raise RuntimeError(f'examples pagination anchor matched {count} times')
src = src.replace(examples_old, examples_new, 1)

# Remove previous short-vocabulary nested-table wrapper entirely. Table rows can break
# naturally and individual rows are already protected by CSS.
full_html_anchor = '''            full_html = "".join(parts)\n\n            # ── Render with fitz.Story ────────────────────────────────────────\n'''
if src.count(full_html_anchor) != 1:
    raise RuntimeError(f'full_html pagination anchor matched {src.count(full_html_anchor)} times')
# no replacement needed beyond keeping the original render marker

# Expand usable page area slightly to reduce needless carry-over while keeping footer safe.
old_rect = '''story.write(writer, lambda n, f: (fitz.paper_rect("a4"), fitz.Rect(36, 44, 559, 800), None))'''
new_rect = '''story.write(writer, lambda n, f: (fitz.paper_rect("a4"), fitz.Rect(30, 38, 565, 814), None))'''
if src.count(old_rect) != 1:
    raise RuntimeError(f'PDF content rect anchor matched {src.count(old_rect)} times')
src = src.replace(old_rect, new_rect, 1)

path.write_text(src, encoding='utf-8')
print('Applied compact short-block pagination with minimal blank-space carryover')
