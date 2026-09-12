from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

# PyMuPDF Story does not reliably honor break-inside/avoid on nested divs. The prior
# post-render regex wrapping also corrupted nested MCQ HTML. Use a safer rule instead:
# start coherent learning blocks on a fresh PDF page. This prevents questions,
# dialogues, and vocabulary lists from beginning at the bottom of a page and then
# spilling immediately onto the next one, without rewriting their HTML structure.

replacements = [
    (
        '''                            elif ptype == "vocabulary":\n''',
        '''                            elif ptype == "vocabulary":\n                                parts.append('<div style="page-break-before:always"></div>')\n''',
        'vocabulary',
    ),
    (
        '''                            elif ptype == "examples":\n''',
        '''                            elif ptype == "examples":\n                                parts.append('<div style="page-break-before:always"></div>')\n''',
        'examples',
    ),
    (
        '''                            elif ptype == "mcq":\n''',
        '''                            elif ptype == "mcq":\n                                parts.append('<div style="page-break-before:always"></div>')\n''',
        'mcq',
    ),
]

for old, new, label in replacements:
    count = src.count(old)
    if count != 1:
        raise RuntimeError(f'{label} pagination anchor matched {count} times')
    src = src.replace(old, new, 1)

path.write_text(src, encoding='utf-8')
print('Applied safe fresh-page pagination for PDF vocabulary, dialogue, and MCQ blocks')
