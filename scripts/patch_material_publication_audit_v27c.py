from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

old = '''    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if len(payload) > 26000:
        payload = payload[:26000]
'''
new = '''    # Keep the audit payload structurally complete. Lesson outputs are already bounded by
    # the generation token limit; truncating raw JSON can hide tail-page defects and break
    # reviewer path addressing.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
'''
if old in s:
    s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('Applied v27c: complete structured payload for independent publication audit')
