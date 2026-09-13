from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
app = root / "public" / "js" / "app.js"
index = root / "public" / "index.html"

s = app.read_text(encoding="utf-8")
old = "const response = await fetch(`/api/courses/${encodeURIComponent(courseId)}/export-pdf?lang=${pdfLang}`, {\n      method: 'GET',\n      headers: { 'X-Session-Token': localStorage.getItem('aula_session') || '' }\n    });"
new = "const response = await fetch(`/api/courses/${encodeURIComponent(courseId)}/export-pdf?lang=${pdfLang}&_pdfv=${Date.now()}`, {\n      method: 'GET',\n      cache: 'no-store',\n      headers: {\n        'X-Session-Token': localStorage.getItem('aula_session') || '',\n        'Cache-Control': 'no-cache'\n      }\n    });"

# app.js contains two copies of downloadCourseMaterialPDF; patch every copy, not just the first.
count = s.count(old)
if count:
    s = s.replace(old, new)

# Make downloaded files unique too, so the browser/OS cannot reopen an older same-name file.
old_name = "a.download = `${safeFilename}_AulaAI_${pdfLang.toUpperCase()}.pdf`;"
new_name = "a.download = `${safeFilename}_AulaAI_${pdfLang.toUpperCase()}_${Date.now()}.pdf`;"
if old_name in s:
    s = s.replace(old_name, new_name)

if "&_pdfv=${Date.now()}" not in s:
    raise RuntimeError("v39 PDF fetch cache-bust missing")
if new_name not in s:
    raise RuntimeError("v39 unique PDF filename missing")

app.write_text(s, encoding="utf-8")

h = index.read_text(encoding="utf-8")
h = re.sub(r'/js/app\.js\?v=[^\"\']+', '/js/app.js?v=20260913_v240', h, count=1)
index.write_text(h, encoding="utf-8")
print(f"Applied v39/v240: patched {count} PDF fetch copies + unique filenames")
