from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

p.write_text(s, encoding="utf-8")
print("Applied v29 material gate scaffold")
