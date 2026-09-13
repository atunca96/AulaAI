from pathlib import Path

root = Path(__file__).resolve().parents[1]
app = root / "public" / "js" / "app.js"
index = root / "public" / "index.html"

s = app.read_text(encoding="utf-8")
old = "const response = await fetch(`/api/courses/${encodeURIComponent(courseId)}/export-pdf?lang=${pdfLang}`, {\n      method: 'GET',\n      headers: { 'X-Session-Token': localStorage.getItem('aula_session') || '' }\n    });"
new = "const response = await fetch(`/api/courses/${encodeURIComponent(courseId)}/export-pdf?lang=${pdfLang}&_pdfv=${Date.now()}`, {\n      method: 'GET',\n      cache: 'no-store',\n      headers: {\n        'X-Session-Token': localStorage.getItem('aula_session') || '',\n        'Cache-Control': 'no-cache'\n      }\n    });"
if old in s:
    s = s.replace(old, new, 1)
elif "&_pdfv=${Date.now()}" not in s:
    raise RuntimeError("v39 PDF fetch anchor missing")
app.write_text(s, encoding="utf-8")

h = index.read_text(encoding="utf-8")
import re
h = re.sub(r'/js/app\.js\?v=[^\"\']+', '/js/app.js?v=20260913_v239', h, count=1)
index.write_text(h, encoding="utf-8")
print("Applied v39: fresh PDF requests + frontend cache bust")
