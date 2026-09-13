from pathlib import Path

root = Path(__file__).resolve().parents[1]
engine = root / "services" / "ai_engine.py"
policy = (root / "config" / "material_quality_v33.txt").read_text(encoding="utf-8").strip()
s = engine.read_text(encoding="utf-8")

page_marker = "For an MCQ that cannot be repaired using PRIOR taught content without introducing new knowledge"
page_tag = "AULAAI_MATERIAL_QUALITY_V33_PAGE"
if page_tag not in s:
    i = s.find(page_marker)
    if i < 0:
        raise RuntimeError("v33 page-audit insertion point missing")
    s = s[:i] + page_tag + ": " + policy + "\n\n" + s[i:]

publication_anchor = "MISSION: make only high-confidence surgical repairs required for publication quality. Do not rewrite correct content for stylistic preference.\n"
publication_tag = "AULAAI_MATERIAL_QUALITY_V33_PUBLICATION"
if publication_tag not in s:
    i = s.find(publication_anchor)
    if i < 0:
        raise RuntimeError("v33 publication-audit insertion point missing")
    i += len(publication_anchor)
    s = s[:i] + publication_tag + ": " + policy + "\n" + s[i:]

s = s.replace("model=MODEL_STRUCTURAL, max_tokens=1700, temperature=0.0", "model=MODEL_STRUCTURAL, max_tokens=2200, temperature=0.0", 1)

required = (page_tag, publication_tag, "max_tokens=2200")
missing = [x for x in required if x not in s]
if missing:
    raise RuntimeError("v33 verification failed: " + ", ".join(missing))

engine.write_text(s, encoding="utf-8")
print("Applied v33 material quality contract to page and publication audits")
