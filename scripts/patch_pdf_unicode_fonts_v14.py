from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "pdf_renderer_v12.py"
s = p.read_text(encoding="utf-8")
old = "body { font-family: sans-serif; font-size: 9pt;"
new = "body { font-family: 'Noto Sans', 'Noto Sans CJK JP', sans-serif; font-size: 9pt;"
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise RuntimeError("PDF body font anchor missing")
p.write_text(s, encoding="utf-8")
print("Applied Unicode-safe Noto font stack to PDF renderer")
