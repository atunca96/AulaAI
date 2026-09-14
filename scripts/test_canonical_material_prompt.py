from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_generation_prompt import build_material_prompts


def run():
    engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")
    assert "# AULAAI_CANONICAL_MATERIAL_PROMPT" in engine
    assert "from services.material_generation_prompt import build_material_prompts" in engine
    assert "system_prompt, user_prompt = build_material_prompts(" in engine

    # Verify the active generate_full_lesson runtime segment is canonical.
    start = engine.find("def generate_full_lesson(")
    end = engine.find("def ai_explain_word(", start)
    assert start >= 0 and end > start
    lesson_fn = engine[start:end]
    assert "# AULAAI_CANONICAL_MATERIAL_PROMPT" in lesson_fn
    assert "system_prompt, user_prompt = build_material_prompts(" in lesson_fn
    assert "system_prompt = f\"\"\"<role>" not in lesson_fn
    assert "user_prompt = f\"\"\"Generate a complete" not in lesson_fn

    system_prompt, user_prompt = build_material_prompts(
        language="Example Language",
        level="A1",
        topic="Alphabet",
        topic_type="pronunciation",
        official_institution="Example Institute",
        source_text=None,
    )
    assert "A1/A2: concrete, high-frequency" in system_prompt
    assert "BASIC SOUND VALUE(S) IN STANDARD IPA" in system_prompt
    assert "Pronunciation data is publication-critical" in system_prompt
    assert "Never guess IPA from spelling" in system_prompt
    assert "Never insert a sound that is absent from the standard pronunciation" in system_prompt
    assert "Cross-check every `phonetic` against its exact `term` or example" in system_prompt
    assert "personal name alone never establishes grammatical gender" in system_prompt
    assert "Never ask for a Turkish meaning with English options" in system_prompt
    assert "unnecessary metalanguage" in user_prompt
    assert "publication-ready CEFR A1 Example Language lesson" in user_prompt

    print("[CANONICAL-PROMPT] single-source material prompt tests PASSED")


if __name__ == "__main__":
    run()
