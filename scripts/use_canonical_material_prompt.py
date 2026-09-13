from pathlib import Path

path = Path("services/ai_engine.py")
text = path.read_text(encoding="utf-8")
marker = "# AULAAI_CANONICAL_MATERIAL_PROMPT"

if marker not in text:
    start_text = "    # Build clean, universal, professor-level prompt with full pedagogical freedom\n"
    end_text = "    lesson_dict = None\n"
    start = text.find(start_text)
    end = text.find(end_text, start)
    if start == -1 or end == -1:
        raise RuntimeError("canonical material prompt wiring anchors not found")

    wiring = """    # AULAAI_CANONICAL_MATERIAL_PROMPT
    from services.material_generation_prompt import build_material_prompts
    system_prompt, user_prompt = build_material_prompts(
        language=language,
        level=level,
        topic=topic,
        topic_type=topic_type,
        official_institution=official_institution,
        source_text=source_text,
    )

"""
    text = text[:start] + wiring + text[end:]
    path.write_text(text, encoding="utf-8")

print("Canonical material prompt wired")
