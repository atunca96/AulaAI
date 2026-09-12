from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

# Narrow structural pagination fix: only keep each MCQ heading + question + all options
# together. Do not wrap dialogues or vocabulary tables, because those broader wrappers
# caused large blank areas in previous builds.

css_anchor = '''.mcq-opts { margin-left: 10px; }\n'''
css_repl = '''.mcq-opts { margin-left: 10px; }\n.keep-mcq { width: 100%; border-collapse: collapse; border: none; margin: 0 0 6px 0; padding: 0; }\n.keep-mcq > tbody > tr > td, .keep-mcq > tr > td { border: none; background: transparent; padding: 0; margin: 0; }\n'''
if src.count(css_anchor) < 1:
    raise RuntimeError('keep-mcq CSS anchor missing')
src = src.replace(css_anchor, css_repl, 1)

mcq_old = '''                                q_title   = tx(page, "title", "title_tr") or ""\n                                if q_title:\n                                    parts.append(f'<div class="sec-h">{E(q_title)}</div>')\n                                question_counter += 1\n                                parts.append(f'<div class="mcq-box"><div class="mcq-q">{question_counter}. {E(str(prompt))}</div>')\n                                if options:\n                                    parts.append('<div class="mcq-opts">')\n                                    for opt_idx, opt in enumerate(options):\n                                        letter = chr(65 + opt_idx)\n                                        parts.append(f'<div class="mcq-opt">{letter}) {E(str(opt))}</div>')\n                                    parts.append('</div>')\n                                parts.append('</div>')\n                                answer_letter = ""\n'''
mcq_new = '''                                q_title   = tx(page, "title", "title_tr") or ""\n                                question_counter += 1\n                                parts.append('<table class="keep-mcq"><tr><td>')\n                                if q_title:\n                                    parts.append(f'<div class="sec-h">{E(q_title)}</div>')\n                                parts.append(f'<div class="mcq-box"><div class="mcq-q">{question_counter}. {E(str(prompt))}</div>')\n                                if options:\n                                    parts.append('<div class="mcq-opts">')\n                                    for opt_idx, opt in enumerate(options):\n                                        letter = chr(65 + opt_idx)\n                                        parts.append(f'<div class="mcq-opt">{letter}) {E(str(opt))}</div>')\n                                    parts.append('</div>')\n                                parts.append('</div></td></tr></table>')\n                                answer_letter = ""\n'''
count = src.count(mcq_old)
if count != 1:
    raise RuntimeError(f'MCQ structural anchor matched {count} times')
src = src.replace(mcq_old, mcq_new, 1)

path.write_text(src, encoding='utf-8')
print('Applied MCQ-only structural pagination')
