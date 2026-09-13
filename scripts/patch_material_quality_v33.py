from pathlib import Path

root = Path(__file__).resolve().parents[1]
engine = root / "services" / "ai_engine.py"
policy = (root / "config" / "material_quality_v33.txt").read_text(encoding="utf-8").strip()
s = engine.read_text(encoding="utf-8")
marker = "For an MCQ that cannot be repaired using PRIOR taught content without introducing new knowledge"
tag = "AULAAI_MATERIAL_QUALITY_V33"
if tag not in s:
    i = s.find(marker)
    if i < 0:
        raise RuntimeError("v33 insertion point missing")
    s = s[:i] + tag + ": " + policy + "\n\n" + s[i:]
s = s.replace("model=MODEL_STRUCTURAL, max_tokens=1700, temperature=0.0", "model=MODEL_STRUCTURAL, max_tokens=2200, temperature=0.0", 1)
if tag not in s:
    raise RuntimeError("v33 verification failed")
engine.write_text(s, encoding="utf-8")
print("Applied v33 material quality contract")
