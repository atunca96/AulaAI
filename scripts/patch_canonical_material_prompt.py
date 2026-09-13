from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
engine_path = ROOT / "services" / "ai_engine.py"
s = engine_path.read_text(encoding="utf-8")

TAG = "# AULAAI_CANONICAL_MATERIAL_PROMPT"
if TAG in s:
    print("Canonical material prompt already wired")
    raise SystemExit(0)

start_marker = "    # Build clean, universal, professor-level prompt with full pedagogical freedom\n"
end_marker = "    lesson_dict = None\n"

start = s.find(start_marker)
end = s.find(end_marker, start)
if start < 0 or end < 0 or end <= start:
    raise RuntimeError("canonical material prompt wiring anchors missing")

replacement = '''    # AULAAI_CANONICAL_MATERIAL_PROMPT\n    # Single source of truth: services/material_generation_prompt.py\n    # Release patches may harden guards/rendering, but must not own material prompt wording.\n    from services.material_generation_prompt import build_material_prompts\n    system_prompt, user_prompt = build_material_prompts(\n        language=language,\n        level=level,\n        topic=topic,\n        topic_type=topic_type,\n        official_institution=official_institution,\n        source_text=source_text,\n    )\n\n'''

s = s[:start] + replacement + s[end:]
engine_path.write_text(s, encoding="utf-8")
print("Applied canonical material prompt wiring; runtime lesson prompt now has one source of truth")
