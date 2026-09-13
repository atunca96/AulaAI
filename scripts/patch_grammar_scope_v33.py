from pathlib import Path
p=Path(__file__).resolve().parents[1]/'services'/'ai_engine.py'
s=p.read_text(encoding='utf-8')
a='12) TRANSLATION NATURALNESS:'
if '13) GRAMMAR SCOPE:' not in s:
 i=s.find(a); j=s.find('\n',i)
 if i<0 or j<0: raise RuntimeError('audit anchor missing')
 s=s[:j+1]+'13) GRAMMAR SCOPE: verify the grammatical categories that actually apply in the target language, including agreement, case, word order, tense/aspect, mood, particles, valency, and register; do not project categories the language does not use.\n'+s[j+1:]
p.write_text(s,encoding='utf-8')
