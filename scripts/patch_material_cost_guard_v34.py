from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

# Keep one complete publication audit per topic. The previous stack also ran a
# page-by-page audit and then a second whole-lesson audit, which multiplied API
# calls and caused long-tail stalls on late topics.
page_call = "    lesson_dict = _material_page_release_audit(lesson_dict, language, level)\n"
s = s.replace(page_call, "")

whole = "    lesson_dict = _material_publication_audit(lesson_dict, language, level)\n"
while whole + whole in s:
    s = s.replace(whole + whole, whole, 1)

# Move the v33 contract into the remaining whole-lesson publication editor so
# quality checks are preserved even though the expensive per-page pass is off.
policy_path = Path(__file__).resolve().parents[1] / "config" / "material_quality_v33.txt"
policy = policy_path.read_text(encoding="utf-8").strip()
tag = "AULAAI_MATERIAL_QUALITY_V33_WHOLE"
needle = "MISSION: make only high-confidence surgical repairs required for publication quality. Do not rewrite correct content for stylistic preference.\n"
if tag not in s:
    if needle not in s:
        raise RuntimeError("v34 publication editor anchor missing")
    addition = needle + tag + ": " + policy + "\n"
    s = s.replace(needle, addition, 1)

if s.count(whole) != 1:
    raise RuntimeError(f"v34 expected exactly one publication audit call, found {s.count(whole)}")
if page_call in s:
    raise RuntimeError("v34 page audit call still active")
if tag not in s:
    raise RuntimeError("v34 whole-lesson quality contract missing")

p.write_text(s, encoding="utf-8")
print("Applied v34: single whole-lesson publication audit with v33 quality contract")
