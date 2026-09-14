from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_generation_prompt import build_material_prompts, structurally_valid_material

source = (ROOT / "services" / "material_generation_prompt.py").read_text(encoding="utf-8")
assert all(ord(ch) < 128 for ch in source), "raw material prompt source must contain no script-specific literal characters"

system, user = build_material_prompts(
    topic="Generic Topic",
    topic_type="grammar",
    language="TargetLanguage",
    level="A1",
    material_language="tr",
    source_text=None,
)

for marker in (
    "sole author and final academic editor",
    "educated native-level linguist",
    "CEFR curriculum designer",
    "phonologist",
    "assessment writer",
    "meticulous copy editor",
    "one silent editorial pass",
    "Return only one valid JSON object",
):
    assert marker in system, marker

assert "AULAAI_SCHEMA_FIRST" not in system
assert "GATE A" not in system
assert "GATE B" not in system
assert "language-specific" in source
assert structurally_valid_material({"pages": [{"type": "overview"}, {"type": "vocabulary"}, {"type": "mcq"}]})
assert not structurally_valid_material({"pages": [{"type": "overview"}]})

engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")
lesson_start = engine.find("def generate_full_lesson(")
lesson_end = engine.find("def ai_explain_word(", lesson_start)
assert lesson_start >= 0 and lesson_end > lesson_start
lesson_code = engine[lesson_start:lesson_end]
assert "build_material_prompts" in lesson_code
assert lesson_code.count("_call_ai(") == 1
for forbidden in (
    "get_reference_prompt",
    "get_special_chars_prompt",
    "get_pedagogical_guidelines",
    "LANGUAGE_CEFR_STANDARDS",
    "_sanitize_deep_bilingual",
    "translate_lesson_to_turkish(lesson_dict",
    "for attempt_idx in range",
):
    assert forbidden not in lesson_code, forbidden

print("[RAW-MATERIAL] universal raw prompt regression tests PASSED")
