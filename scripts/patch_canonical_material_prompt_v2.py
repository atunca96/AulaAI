from pathlib import Path

p = Path("services/ai_engine.py")
s = p.read_text(encoding="utf-8")
if "# AULAAI_CANONICAL_MATERIAL_PROMPT" in s:
    raise SystemExit(0)

fn = s.find("def generate_full_lesson(")
end = s.find("\n    lesson_dict = None\n", fn)
start = s.find("\n    system_prompt = f", fn, end)
if fn < 0 or end < 0 or start < 0:
    raise RuntimeError("canonical prompt wiring boundary missing")

block = '''
    # AULAAI_CANONICAL_MATERIAL_PROMPT
    from services.material_generation_prompt import build_material_prompts
    system_prompt, user_prompt = build_material_prompts(
        language=language,
        level=level,
        topic=topic,
        topic_type=topic_type,
        official_institution=official_institution,
        source_text=source_text,
    )
'''
s = s[:start] + block + s[end:]
p.write_text(s, encoding="utf-8")
print("Applied canonical material prompt wiring v2")
