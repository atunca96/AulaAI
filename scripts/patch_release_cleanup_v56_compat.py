from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "services" / "material_quality_guard.py"
s = p.read_text(encoding="utf-8")

marker = "# canonical corrections, not generative guesses.\n"
pos = s.find(marker)
if pos < 0:
    raise RuntimeError("v56 compat marker missing")
start = pos + len(marker)

m = re.match(r'    text = re\.sub\([^\n]+\)\n    text = re\.sub\([^\n]+\)\n', s[start:])
if not m:
    raise RuntimeError("v56 compat typo lines missing")

replacement = (
    '    text = re.sub(r"(?i)\\u043f\\u0438\\u0441(?:[\\u0300\\u0301])?\\u043c\\u043e(?:[\\u0300\\u0301])?", "\\u043f\\u0438\\u0441\\u044c\\u043c\\u043e", text)\n'
    '    text = re.sub(r"(?i)\\u043a\\u043e\\u0437\\u0438(?:[\\u0300\\u0301])?\\u043d\\u0435(?:[\\u0300\\u0301])?", "\\u043a\\u043e\\u0440\\u0437\\u0438\\u043d\\u0435", text)\n'
)
s = s[:start] + replacement + s[start + m.end():]
p.write_text(s, encoding="utf-8")
print("Applied v56 stressed-token compatibility fix")
