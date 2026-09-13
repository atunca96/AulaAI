from pathlib import Path
p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')
a = '11) NEUTRALITY:'
if '12) TRANSLATION NATURALNESS:' not in s:
    i = s.find(a)
    if i < 0:
        raise RuntimeError('audit anchor missing')
    j = s.find('\n', i)
    s = s[:j+1] + '12) TRANSLATION NATURALNESS: verify that every translation preserves meaning and reads naturally in the instructional language; repair literal or awkward calques.\n' + s[j+1:]
p.write_text(s, encoding='utf-8')
