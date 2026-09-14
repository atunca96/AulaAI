from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "services" / "material_quality_guard.py"
s = p.read_text(encoding="utf-8")
old1 = '    text = re.sub(r"(?i)\\u043f\\u0438\\u0441\\u043c\\u043e(?=\\b|[\\u0301\\u0300])", "\\u043f\\u0438\\u0441\\u044c\\u043c\\u043e", text)\n'
old2 = '    text = re.sub(r"(?i)\\u043a\\u043e\\u0437\\u0438\\u043d\\u0435(?=\\b|[\\u0301\\u0300])", "\\u043a\\u043e\\u0440\\u0437\\u0438\\u043d\\u0435", text)\n'
new1 = '    text = re.sub(r"(?i)\\u043f\\u0438\\u0441(?:[\\u0300\\u0301])?\\u043c\\u043e(?:[\\u0300\\u0301])?", "\\u043f\\u0438\\u0441\\u044c\\u043c\\u043e", text)\n'
new2 = '    text = re.sub(r"(?i)\\u043a\\u043e\\u0437\\u0438(?:[\\u0300\\u0301])?\\u043d\\u0435(?:[\\u0300\\u0301])?", "\\u043a\\u043e\\u0440\\u0437\\u0438\\u043d\\u0435", text)\n'
changed = 0
if old1 in s:
    s = s.replace(old1, new1, 1)
    changed += 1
if old2 in s:
    s = s.replace(old2, new2, 1)
    changed += 1
if changed != 2:
    raise RuntimeError(f"v56 compat anchors missing: {changed}/2")
p.write_text(s, encoding="utf-8")
print("Applied v56 stressed-token compatibility fix")
